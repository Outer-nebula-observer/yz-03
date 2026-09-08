# ============================================================================
# SCM: core/chat.py 核心节选【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2304.13343 (ACL'23 Findings)
#   §2：SCM 三组件 = LLM agent + memory stream + **memory controller**。
#   本文件的 ChatBot 就是控制器：决定"何时读、读什么、历史怎么降级
#   （raw→summary→drop）"。
#
# 【为什么精读】我们 memsys/controller.py 的直系祖先——看懂它的
#   judge_drop_or_summary（LLM 决策）与 get_related_turn（预算内检索），
#   就明白我们的"确定性阈值"改造（docs/09 决策 4）改的是什么。
#
# 【我们的实现对照】
#   Turn（含 summ/embedding，写入时算）→ 我们 MemoryEntry（衰减字段写入时初始化）
#   judge_drop_or_summary（LLM 三态决策）→ 我们 _flush()（阈值二态：留/摘要）
#   get_related_turn 预算内保留      →  我们 retrieve(top_k*2) 后重排截断
#   get_binary_answer 保守策略       →  值得直接搬（见文末线索 3）
# ============================================================================

import numpy as np


class Turn(object):
    """一轮对话的记忆单元（原文+摘要+向量三态并存）。

    注意 summ 和 embedding 在**写入时**就算好——检索/降级时零 LLM 成本。
    （与 PREMem"把负担移到存储时"同哲学；我们是 decay_strength 写入时初始化）
    """
    def __init__(self, user_input, system_response, user_sys_text, summ, embedding):
        ...


class ChatBot(object):
    # ------------------------------------------------------------------
    # 【方法 1】get_binary_answer —— 让 LLM 只答"是/否"的保守工具（L116）
    # ------------------------------------------------------------------
    def get_binary_answer(self, prompt, false_choices=[]):
        """把模糊回答一律归为"否"——宁错杀不漏判。

        【为什么保守】本类的所有决策（能否回答/是否相关）都走它；
        模糊答案若算"是"，会往上下文塞垃圾记忆——污染比遗漏更难清理。
        false_choices：可自定义"哪些回答算否"（如 'maybe', 'not sure'）。
        """
        ...

    # ------------------------------------------------------------------
    # 【方法 2】judge_drop_or_summary —— 控制器核心决策（L164）
    # ------------------------------------------------------------------
    # 每轮历史有三个去向：raw（原文保留）/ summary（摘要降级）/ drop（丢弃）
    # 决策依据 = "这段历史对**当前问题**还有用吗"（问题感知，非无脑截断）
    def judge_drop_or_summary(self, user_query, turn_index):
        turn_raw = self.history[turn_index].user_sys_text      # 该轮原文
        turn_summary = self.history[turn_index].summ           # 该轮摘要

        # 第一问：**原文**能否回答当前问题？
        input_text = judge_answerable_prompt.format(content=turn_raw, query=user_query)
        is_answerable = self.get_binary_answer(input_text)
        if not is_answerable:
            return 'drop'        # 原文都答不了 → 摘要更答不了 → 直接丢

        # 第二问：**摘要**能否回答？
        input_text = judge_answerable_prompt.format(content=turn_summary, query=user_query)
        is_answerable = self.get_binary_answer(input_text)
        if is_answerable:
            return 'summary'     # 摘要就够 → 降级（省 token，信息无损可用）
        else:
            return 'raw'         # 只有原文能答 → 原文保留（最贵但保真）

        # 【三级降级链】raw > summary > drop，两次 LLM 判断定位档位。
        # 【对照我们】我们的 _flush() 只有两态（驱逐+递归摘要，永不真丢
        # ——archived 可回放）；SCM 的 drop 是真删。我们的选择更保守，
        # 代价是 archived 无限增长（README 不足清单待办）。

    # ------------------------------------------------------------------
    # 【方法 3】get_related_turn_naive —— 预算内检索（L186）
    # ------------------------------------------------------------------
    def get_related_turn_naive(self, query, k=3):
        # ① 查询向量化，与历史每轮算相似度
        #    细节：只检索 [0, 上一轮)——**上一轮文本直接拼进对话**无需检索
        #    （最近一轮永远可见——对应我们 render() 尾部放最新消息）
        q_embedding = self.vectorize(query)
        sim_lst = [self._similarity(q_embedding, v.embedding)
                   for v in self.history[:-1]]

        # ② 取 top-k 相似轮（argsort 无序——后面会重排，这里不急着排）
        arr = np.array(sim_lst)
        topk_indices = arr.argsort()[-k:].tolist()

        # ③ 相似度降序逐条**装进 token 预算**：
        #    第一条超预算 → 硬截断（保头部 500 token 余量）也留住；
        #    后续条累计超预算 → 停止装填
        #    【贪心装填】最相似的优先占预算，次要的装不下就放弃
        for p, (idx, score, turn) in enumerate(sorted_desc):  # sorted_desc=按相似度降序的 (idx,分,轮) 列表
            if p == 0:
                if turn_tokens > self.MAX_HISTORY_TOKENS:
                    cur_text = cur_text[:(self.MAX_HISTORY_TOKENS - 500)]  # 截断保命
                    keep_idx_text_lst.append([idx, cur_text])
                    break
                ...
            else:
                if cur_tokens + turn_tokens < self.MAX_HISTORY_TOKENS:
                    cur_tokens += turn_tokens
                    keep_idx_text_lst.append([idx, cur_text])
                else:
                    break

        # ④ 按**时间先后**重排被选中的轮次再拼接——
        #    相似度决定"选谁"，时间序决定"怎么摆"（保持叙事因果）
        sorted_index_text_asc_lst = sorted(keep_idx_text_lst, key=lambda x: x[0])
        retrieve_history_text = '\n\n'.join(text for _, text in sorted_index_text_asc_lst)
        # 【对照我们】hybrid.retrieve() 的"多取再筛"同源思想：
        #   我们按融合分截断 top_k；SCM 按 token 预算贪心装填——
        #   token 预算版更贴近实际部署（LLM 窗口是 token 不是条数）。

    # ------------------------------------------------------------------
    # 【方法 4】get_related_turn —— 完整版检索（L238，338 行文件的主体）
    # ------------------------------------------------------------------
    # naive 之上叠加：缓存相似度、按轮分块剪枝、与 judge_drop_or_summary
    # 联动（检索到的轮先判降级档位再拼接）——工程优化都在这 100 行，
    # 思路同上，读通 naive 版即可。
    def get_related_turn(self, query, k=3, naive=False):
        if naive:
            return self.get_related_turn_naive(query, k)
        ...

# ============================================================================
# 【给基础开发者的三条读懂线索】
# 1) SCM 的"自控"= 每条历史有**三态**（raw/summary/drop）而非二态
#    （留/删）——降级链让"省 token"与"保信息"可以折中；
# 2) 决策全部**问题感知**（能否回答当前问题），不是按时间无脑截断——
#    这是它比"滑动窗口"高级的本质；
# 3) get_binary_answer 的保守策略（模糊=否）值得直接搬进我们进化判定：
#    LLM 说"可能重复"时按不重复处理，宁可多存不可错删。
# ============================================================================
