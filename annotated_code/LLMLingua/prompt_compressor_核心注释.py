# ============================================================================
# LLMLingua: prompt_compressor.py 核心节选【赛题③精读注释版】
# ============================================================================
# 【论文定位】
#   LLMLingua（EMNLP'23, arXiv 2310.05736）§4：粗到细压缩 = 预算控制器 + ITPC；
#   LongLLMLingua（ACL'24, 2310.06839）§3：问题感知打分 + 子序列恢复。
#   一个 PromptCompressor 类承载三篇论文（rank_method 参数切换）。
#
# 【为什么精读】赛题③短期记忆压缩（memsys/short_term/compression.py）的
#   LLMLinguaStrategy 适配的就是这个类——看懂打分与预算分配，才知道
#   "删 token"背后在算什么。
#
# 【我们的实现对照】
#   get_ppl 的条件困惑度  →  我们未实现打分（直接调 PromptCompressor）
#   force_tokens 强制保留 →  我们的"约束字段不进压缩器"是更彻底的版本
#   三级过滤(context/sentence/token) →  我们只做 FIFO 级（历史消息整段处理）
#
# 注：原文件 2455 行，此处节选两个核心方法（打分 + 主流程），行号与原文件一致。
# ============================================================================

from typing import List
import torch


class PromptCompressor:
    """微软官方提示压缩器：LLMLingua / LongLLMLingua / LLMLingua-2 三合一。"""

    # ------------------------------------------------------------------
    # 【核心方法 1】get_ppl —— 一切压缩决策的打分基础（原文件 L165-211）
    # ------------------------------------------------------------------
    # ppl = perplexity（困惑度）。直觉：**模型越"猜得中"的 token 越冗余可删**；
    # 猜不中的（低概率、信息量大）保留。这就是"删 token"背后的唯一信号。
    def get_ppl(
        self,
        text: str,
        granularity: str = "sentence",   # sentence=均值（段级打分）/ token=逐 token（细粒度）
        input_ids=None,
        attention_mask=None,
        past_key_values=None,            # KV cache：迭代压缩时复用前文计算（省大量推理）
        return_kv: bool = False,
        end=None,
        condition_mode: str = "none",    # LongLLMLingua 的"问题感知"开关（见下）
        condition_pos_id: int = 0,
    ):
        if input_ids is None:
            tokenized_text = self.tokenizer(text, return_tensors="pt")
            input_ids = tokenized_text["input_ids"].to(self.device)
            attention_mask = tokenized_text["attention_mask"].to(self.device)

        # ---- KV cache 长度处理：只算"新增部分"，历史部分直接复用 ----
        if past_key_values is not None:
            past_length = past_key_values[0][0].shape[2]
        else:
            past_length = 0
        if end is None:
            end = input_ids.shape[1]
        end = min(end, past_length + self.max_position_embeddings)  # 防超窗口

        with torch.no_grad():  # 推理模式，不算梯度（我们只是打分，不训练）
            response = self.model(
                input_ids[:, past_length:end],        # 只喂新增 token
                attention_mask=attention_mask[:, :end],
                past_key_values=past_key_values,
                use_cache=True,
            )
            past_key_values = response.past_key_values  # 更新缓存供下轮用

        # ---- 经典"shift"技巧：用第 i 个位置的预测分布 对 第 i+1 个真实 token 算损失 ----
        # shift_logits: 每个位置对下一个 token 的预测分布
        shift_logits = response.logits[..., :-1, :].contiguous()
        # shift_labels: 右移一位的真实 token（即"被预测的对象"）
        shift_labels = input_ids[..., past_length + 1: end].contiguous()

        # 排除 padding 位置（attention_mask=0 的地方不算）
        active = (attention_mask[:, past_length:end] == 1)[..., :-1].view(-1)
        active_logits = shift_logits.view(-1, shift_logits.size(-1))[active]
        active_labels = shift_labels.view(-1)[active]

        # 逐 token 交叉熵：每个 token 得到一个"困惑度"分（高=意外=信息量大=该保留）
        loss_fct = torch.nn.CrossEntropyLoss(reduction="none")  # none=保留逐项，不求均值
        loss = loss_fct(active_logits, active_labels)

        # ---- LongLLMLingua 的"问题感知"核心（论文 §3.1）----
        # 只统计 question 之后（after）或之前（before）的 loss：
        #   condition_mode="after" → 打分只看问题之后的上下文（问题引导注意力）
        if condition_mode == "before":
            loss = loss[:condition_pos_id]
        elif condition_mode == "after":
            loss = loss[condition_pos_id:]

        # granularity=sentence → 返回均值（整段一个分，用于粗筛）
        # granularity=token   → 返回逐 token（用于 ITPC 细删）
        res = loss.mean() if granularity == "sentence" else loss
        return (res, past_key_values) if return_kv else res

    # ------------------------------------------------------------------
    # 【核心方法 2】compress_prompt —— 主流程（原文件 L426 起，节选关键段）
    # ------------------------------------------------------------------
    def compress_prompt(
        self,
        context: List[str],        # 待压缩的上下文（RAG 场景=检索到的文档列表）
        instruction: str = "",     # 指令（默认给更小压缩率——保护）
        question: str = "",        # 问题（LongLLMLingua 必填：打分的锚）
        rate: float = 0.5,         # 目标压缩率（压缩后/原始），越小压得越狠
        target_token: float = -1,  # 直接给 token 预算（给了则忽略 rate）
        iterative_size: int = 200, # ITPC 每轮迭代的 token 窗口
        force_context_ids: List[int] = None,  # 强制保留的 context 编号
        use_context_level_filter: bool = True,  # 第一级：context 级粗筛（默认开）
        use_sentence_level_filter: bool = False, # 第二级：句子级（默认关）
        use_token_level_filter: bool = True,     # 第三级：token 级 ITPC（默认开）
        condition_in_question: str = "none",     # 问题感知开关
        reorder_context: str = "original",       # 重排策略（LongLLMLingua 缓解中部遗忘）
        rank_method: str = "llmlingua",          # llmlingua / longllmlingua
        force_tokens: List[str] = [],            # 强制保留的 token（如关键实体名）
        # ...（其余参数见原文件，均有完整 docstring）
    ):
        # ---- ① 路由：LLMLingua-2 走独立方法（蒸馏式，另一套机制）----
        if self.use_llmlingua2:
            return self.compress_prompt_llmlingua2(context, rate=rate)  # 其余参数透传（略）

        # ---- ② LongLLMLingua 的前置检查与默认值 ----
        # rank_method="longllmlingua" 必须给 question（问题感知打分的锚），
        # 否则退化成纯熵压缩——论文实验证明这在冗余场景反而低于 zero-shot
        assert not (rank_method == "longllmlingua" and not question)
        if rank_method == "longllmlingua":
            if condition_in_question == "none":
                condition_in_question = "after"   # 默认：只看问题之后的上下文

        # ---- ③ 统计原始 token 数（用目标 LLM 的 tokenizer 估，跨模型公平）----
        origin_tokens = len(self.oai_tokenizer.encode(
            "\n\n".join([instruction] + context + [question]).strip()))
        context_tokens_length = [self.get_token_length(c) for c in context]
        instruction_tokens_length, question_tokens_length = \
            self.get_token_length(instruction), self.get_token_length(question)

        # ---- ④ 算总预算：rate 只作用于 context（instruction/question 全额保护）----
        # 【预算控制器，论文 Algorithm 1】
        # target = (总长 × rate) - 指令长 - 问题长
        # → 指令/问题不参与压缩，压缩压力全由 context（文档/历史）承担
        if target_token == -1:
            target_token = (
                (instruction_tokens_length + question_tokens_length
                 + sum(context_tokens_length)) * rate
                - instruction_tokens_length
                - (question_tokens_length if concate_question else 0)
            )

        # ---- ⑤ 第一级：context 级粗筛（control_context_budget）----
        # 多文档时先做"文档级去留"：每个 context 整体打分排序，
        # 低分的整段丢弃；reorder_context 可选重排（缓解 lost-in-the-middle）
        if len(context) > 1 and use_context_level_filter:
            context, dynamic_ratio, context_used = self.control_context_budget(
                context, context_tokens_length, target_token,
                force_context_ids, force_context_number, question,
                condition_in_question, reorder_context=reorder_context)

        # ---- ⑥ 第二级（可选）：句子级过滤 control_sentence_budget ----
        # keep_first/last_sentence：首尾句子强制保留（位置偏置的显式保护）
        if use_sentence_level_filter:
            context, segments_info = self.control_sentence_budget(
                context, target_token,
                keep_first_sentence=keep_first_sentence,
                keep_last_sentence=keep_last_sentence)

        # ---- ⑦ 第三级：token 级迭代压缩 ITPC（论文 Algorithm 2）----
        # 把剩余文本按 iterative_size(200) 切窗，迭代处理：
        #   每轮：get_ppl(granularity="token") 逐 token 打分
        #        → 阈值 γ 之上的保留 → 已保留部分进 KV cache
        #        → 下一轮窗口基于"已保留前文"打分（条件依赖！）
        # 【关键】不是独立打分：删 token 会影响后续 token 的困惑度，
        #         迭代 + KV cache 让"依赖"被建模（论文 §4.2 核心）
        # ...（后续为 ITPC 循环与 force_tokens 强制保留、结果拼装）

        # ---- ⑧ 返回 dict：compressed_prompt / origin_tokens / compressed_tokens /
        #        ratio（原始/压缩，如 20x）/ rate / saving（省多少 GPT-4 token 费）----
        pass  # （后续为 ITPC 循环与结果拼装，见原文件）

# ============================================================================
# 【给我们基础开发者的三条读懂线索】
# 1) 所有压缩决策 = 一个信号（困惑度）× 一个预算（rate 只压 context）；
# 2) "粗到细"= context 级→句子级→token 级三级漏斗，先扔整段再抠字；
# 3) ITPC 的"迭代"不是重复压缩，而是"每轮基于已保留内容重打分"——
#    这就是为什么它比一次性打分的 Selective-Context 保真（论文 Table 1）。
# ============================================================================
