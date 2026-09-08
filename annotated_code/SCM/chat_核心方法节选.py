# ============================================================================
# SCM: core/chat.py（核心方法节选）【赛题③逐行注释版】
# ============================================================================
# 【论文定位】arXiv 2304.13343 (Findings of ACL 2023)：
#   Self-Controlled Memory——"记忆控制器决定何时写/读/压缩"。
#   本文件的 ChatBot 类就是 controller 的原型实现（我们的 memsys/controller.py
#   的直系祖先）。
#
# 【为什么精读】答辩讲"我们的 controller 借鉴 SCM 什么、改了什么"时，
#   引用的就是下面这几个方法。核心差异：
#   SCM 每个决策都调 LLM（is_history_need / judge_drop_or_summary）——
#   灵活但贵且不确定；我们全部改为确定性阈值/规则（可测试可复现），
#   LLM 只在"进化抽取"一处介入（docs/09 决策 4）。
#
# 【我们的实现对照表】
#   SCM chat.py                    →  memsys
#   ------------------------------------------------------------------
#   _is_concat_history_too_long    →  WorkingMemory.memory_pressure（属性化）
#   judge_drop_or_summary（LLM判） →  _flush() + compress()（阈值规则）
#   get_related_turn（相似检索）    →  HybridRetriever.retrieve（三路融合）
#   Turn.summ/embedding 写入时算   →  experiential_store.add() 编码（同哲学）
#   is_history_need（LLM 二值问）  →  无对应（我们不做逐轮判断）
# 完整原文件：paper_code/04_记忆进化/SCM4LLMs/core/chat.py（本地 clone）
# ============================================================================

# ----------------------------------------------------------------------------
# ① is_history_need —— "当前问题需要查历史吗？"（LLM 二值判断）
# ----------------------------------------------------------------------------
def is_history_need(self, prompt) -> str:
    output = self.api_func(prompt)          # 调 LLM
    LOCAL_CHAT_LOGGER.info(...)             # 全程落日志——控制器决策必须可审计
    # 判断逻辑：LLM 按 "(A)是/(B)否" 格式回答；输出含 (B) 即否
    if '(B)否' in output or '(B)' in output:
        return False
    return True
    # 【我们的对照】我们不做这一步——查询列表（QueryItem）在规划阶段
    # 就显式声明了"要查什么"，无需运行时再问 LLM"要不要查"。
    # 【权衡】SCM 更自适应（冷启动也能用）；我们更显式可审计（创新点 C）。


# ----------------------------------------------------------------------------
# ② get_binary_answer —— 二值判断的工具方法（保守策略值得学）
# ----------------------------------------------------------------------------
def get_binary_answer(self, prompt, false_choices=[]) -> str:
    output = self.api_func(prompt)
    if false_choices:
        # 自定义"否"选项：任何一个出现就算否——
        # 【值得学】把模糊回答也归为否 = 保守策略：宁可多做一次检索，
        # 不可漏掉一次判断（作战场景同理：宁多查，不可漏查）
        for ch in false_choices:
            if ch in output:
                return False
        return True
    else:
        if '(B)否' in output or '(B)' in output:
            return False
        return True


def vectorize(self, text) -> list:
    """文本 → 向量（embedding_func 可注入：OpenAI/本地模型均可）——依赖注入思想"""
    output = self.embedding_func(text, verbo=False)
    return output


def add_turn_history(self, turn: Turn):
    """一轮对话入历史流——注意：token 计数在【写入时】完成（不在读取时算），
    与 PREMem"写入时干活"同一哲学（读路径越轻越好）"""
    turn.content_tokens_length = len(self.tokenize_func(turn.user_sys_text))
    turn.summary_tokens_length = len(self.tokenize_func(turn.summ))
    self.history.append(turn)


def get_turn_for_previous(self):
    """取上一轮内容：原文太长（超 MAX_PRE_TURN_TOKENS）就用摘要——
    分级供给：近处给原文，太长降级为摘要。
    【我们的对照】WorkingMemory FIFO 保留原文、flush 后用 _recursive_summary
    ——同样是"原文优先、超限降级"的两级供给。"""
    turn = self.history[-1]
    if turn.content_tokens_length < self.MAX_PRE_TURN_TOKENS:
        return turn.user_sys_text      # 短：给原文
    else:
        return turn.summ               # 长：给摘要


# ----------------------------------------------------------------------------
# ③ _is_concat_history_too_long —— 容量判断（我们 memory_pressure 的原型）
# ----------------------------------------------------------------------------
def _is_concat_history_too_long(self, length_lst):
    """拼接历史是否超长？——朴素版：全部 token 求和 + 上一轮（原文或摘要）
    【我们的对照】WorkingMemory.memory_pressure 把它变成属性：
        used_ratio >= warning_ratio（70% 预警）——SCM 是布尔值（超/不超），
        我们是比率（可分级预警+自动 flush 两档），粒度更细。"""
    total_tokens = sum(length_lst)
    pre_turn = self.history[-1]
    pre_turn_length = pre_turn.content_tokens_length
    if pre_turn_length > self.MAX_PRE_TURN_TOKENS:
        pre_turn_length = pre_turn.summary_tokens_length  # 上一轮超长→按摘要算
    total_tokens += pre_turn_length
    if total_tokens > self.MAX_HISTORY_TOKENS:
        return True
    else:
        return False


# ----------------------------------------------------------------------------
# ④ judge_drop_or_summary —— SCM 的灵魂：这轮历史"丢弃/摘要/保留原文"？
# ----------------------------------------------------------------------------
def judge_drop_or_summary(self, user_query, turn_index):
    """三级判定（两次 LLM 调用）：
       ① 原文能回答当前问题吗？ 不能 → 'drop'（丢弃这轮历史）
       ② 摘要能回答吗？        能   → 'summary'（用摘要替代原文，省 token）
       ③ 都不能                → 'raw'（保留原文）
    【论文 §2】这就是"自控"：不是无脑全存/全摘要，
    而是"按当前问题的需要"决定每轮历史的形态。
    【我们的对照】我们用容量驱动（超限才 flush）替代相关性驱动——
    差异本质：SCM 优化"每轮的存储形态"（读时省），
    我们优化"整体容量"（写时省）。两者可叠加（进阶项）。"""
    turn_raw = self.history[turn_index].user_sys_text      # 该轮原文
    turn_summary = self.history[turn_index].summ           # 该轮摘要

    # 判定①：原文能否回答当前 query
    input_text = judge_answerable_prompt.format(content=turn_raw, query=user_query)
    is_answerable = self.get_binary_answer(input_text)
    if not is_answerable:
        return 'drop'          # 原文答不了 → 摘要更答不了 → 直接丢

    # 判定②：摘要能否回答（原文能答的前提下，试更省 token 的摘要）
    input_text = judge_answerable_prompt.format(content=turn_summary, query=user_query)
    is_answerable = self.get_binary_answer(input_text)
    if is_answerable:
        return 'summary'       # 摘要够用 → 用摘要（省 token）
    else:
        return 'raw'           # 摘要丢失关键信息 → 保留原文


# ----------------------------------------------------------------------------
# ⑤ get_related_turn_naive —— 相似轮检索（我们的检索层原型）
# ----------------------------------------------------------------------------
def get_related_turn_naive(self, query, k=3):
    """找与当前 query 最相关的 k 轮历史（朴素版：全量算相似度）"""
    q_embedding = self.vectorize(query)
    # 只检索 [0, 上一轮)——上一轮文本直接拼进对话，无需检索
    # 【细节】排除最近一轮避免"刚说完又检索回来"的冗余
    sim_lst = [self._similarity(q_embedding, v.embedding)
               for v in self.history[:-1]]
    arr = np.array(sim_lst)
    topk_indices = arr.argsort()[-k:].tolist()   # argsort 取 top-k（无序）
    topk_values = arr[topk_indices].tolist()
    turns = [self.history[t] for t in topk_indices]
    # 重新按分数降序排（argsort 的 top-k 是乱序的——常见坑）
    index_value_turn_lst = [(idx, v, turn)
                            for idx, v, turn in zip(topk_indices, topk_values, turns)]
    sorted_desc = sorted(index_value_turn_lst, key=lambda x: x[1], reverse=True)

    # ---- 预算装配：按相似度降序装入，直到 token 预算耗尽 ----
    # 【我们的对照】HybridRetriever 的"top_k*2 多取再筛"同思想：
    # 检索质量 × 预算控制 = 装配策略
    keep_idx_text_lst = []
    cur_tokens = 0
    for p, (idx, score, turn) in enumerate(sorted_desc):
        cur_text = turn.user_sys_text
        turn_tokens = turn.content_tokens_length
        if p == 0:
            # 第一条就超预算 → 硬截断（保命：至少带一条最相关的）
            if turn_tokens > self.MAX_HISTORY_TOKENS:
                cur_text = cur_text[:(self.MAX_HISTORY_TOKENS - 500)]
                keep_idx_text_lst.append([idx, cur_text])
                break
        # （原文后续：累计 cur_tokens，超预算即 break——贪心装配）
