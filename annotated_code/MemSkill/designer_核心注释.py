# ============================================================================
# MemSkill: src/designer.py 核心节选【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2602.02474 §Method（Designer 部分）：
#   designer 周期性复盘"难例"（选了技能但记忆产出错误/不完整的 case），
#   归因到技能模板 → 改旧模板 / 提新技能 → 进化操作库。
#
# 【为什么精读】"复盘驱动进化"与我们 evolve_from_review() 同构——
#   我们复盘"作战任务"，它复盘"记忆操作失败案例"。CaseCollector 的
#   滚动窗口 + 频次聚合设计，是我们 EvolutionReport 的直接升级模板。
#
# 【我们的实现对照】
#   DesignerCase（失败档案）   →  EvolutionReport.skipped（仅计数，无档案）
#   _prune_failure_pool（滚动）→  我们无（进化即时消费，不攒池）
#   fail_count 聚合           →  值得搬：反复失败才算"难例"，一次失败可能是噪声
# ============================================================================

from dataclasses import dataclass
from typing import Dict, List, Optional
import threading


@dataclass
class DesignerCase:
    """一次失败案例的完整档案（designer 的分析原料）。

    分两类属性：
      - 查询侧：question / ground_truth / category（错在哪类题型）
      - 记忆侧：当时用了哪些技能、生成了什么记忆、检索返回了什么
        （memory_bank_snapshot——**当时的记忆库快照**，归因必需：
        不看快照就无法区分"技能差"还是"库里本来就没货"）
    """
    query_id: str
    question: str
    ground_truth: str
    # ... 记忆侧属性见原文件


class CaseCollector:
    """失败案例收集器：滚动窗口池（rolling pool）。

    两个防噪声机制（进化质量的保险丝）：
      1) 时间窗：只保留最近 failure_window_epochs(20) 个 epoch 的失败
         ——技能进化后，旧失败已不反映现状，必须遗忘；
      2) 容量上限：failure_pool_size(200) 封顶，超出按
         (epoch, fail_count) 降序保留——**新且反复失败的优先留**。
    【论文对应】§Method："选错技能≠技能差，可能只是状态罕见"——
    所以进化只看"反复失败"的案例，避免过拟合噪声。
    """

    def __init__(self, failure_window_epochs: int = 20,
                 failure_pool_size: int = 200, logger=None):
        self.failure_pool: Dict[str, DesignerCase] = {}
        self.failure_window_epochs = max(0, int(failure_window_epochs))
        self.failure_pool_size = max(0, int(failure_pool_size))
        self._lock = threading.RLock()   # 线程安全：训练多进程收集案例

    def _case_key(self, case) -> str:
        """案例主键：有 query_id 用 id，否则用问题文本小写归一。"""
        if case.query_id:
            return str(case.query_id)
        return case.question.strip().lower()

    def _prune_failure_pool(self, current_epoch):
        """修剪池子（每次 add 后调用）——滚动的实现。"""
        if current_epoch is None:
            return
        with self._lock:
            # ① 时间窗：删掉 epoch < current - 20 的陈旧失败
            if self.failure_window_epochs > 0:
                cutoff = current_epoch - self.failure_window_epochs
                stale_keys = [k for k, c in self.failure_pool.items()
                              if c.epoch < cutoff]
                for k in stale_keys:
                    del self.failure_pool[k]

            # ② 容量上限：超了按 (epoch 新, fail_count 高) 降序保留前 200
            if self.failure_pool_size > 0 and len(self.failure_pool) > self.failure_pool_size:
                sorted_keys = sorted(
                    self.failure_pool.keys(),
                    key=lambda k: (self.failure_pool[k].epoch,
                                   self.failure_pool[k].fail_count),
                    reverse=True)
                keep = set(sorted_keys[:self.failure_pool_size])
                for k in list(self.failure_pool.keys()):
                    if k not in keep:
                        del self.failure_pool[k]

    def add_case(self, case):
        """收集一个案例——只收失败的（is_correct 直接 return）。

        同一问题**重复失败**不新增条目，而是 fail_count += 1 并
        刷新记忆侧快照——"反复失败"才是 designer 关注的难例信号。
        【值得搬进我们进化】同一作战任务反复失误 → 累计次数 →
        达阈值才触发"该类经验抽取模板需要进化"，单次失误只记档不动模板。
        """
        if case.is_correct:
            return
        with self._lock:
            key = self._case_key(case)
            existing = self.failure_pool.get(key)
            if existing is not None:
                existing.fail_count += 1
                # 刷新为**最新一次**失败的记忆侧快照（旧快照无归因价值）
                existing.prediction = case.prediction
                existing.retrieved_memories = case.retrieved_memories
                existing.memory_bank_snapshot = case.memory_bank_snapshot
                ...
            else:
                case.fail_count = max(int(getattr(case, 'fail_count', 1)), 1)
                self.failure_pool[key] = case
            self.latest_epoch = case.epoch
            self._prune_failure_pool(self.latest_epoch)

    def get_all_cases(self) -> List[DesignerCase]:
        """给 designer 的分析输入（读取前再修剪一次，保证新鲜）。"""
        with self._lock:
            if self.latest_epoch is not None:
                self._prune_failure_pool(self.latest_epoch)
            return list(self.failure_pool.values())


# ============================================================================ 
# 【进化主流程】（designer_prompts 三段式，原文其余部分）
#   ① DESIGNER_ANALYSIS_PROMPT   → LLM 逐案分析"为什么错"
#   ② DESIGNER_REFLECTION_PROMPT → 归因到技能："哪个模板的输出导致错误"
#   ③ DESIGNER_REFINEMENT_PROMPT → 产出动作：改旧模板/提新技能/标记淘汰
#   产物写回 OperationBank（add_operation，见 operation_bank_注释.py）
#   json_repair 库容错 LLM 的 JSON 输出——LLM 输出解析的必备工具
# ============================================================================

# ============================================================================
# 【给基础开发者的三条读懂线索】
# 1) "复盘驱动进化"的完整闭环 = 失败档案（带现场快照）→ 滚动池
#    （防陈旧防过载）→ 频次聚合（反复失败才算真难例）→ 三段式归因
#    （案例→技能→改进动作）；
# 2) 归因必须带 memory_bank_snapshot：不看"当时的库"，无法区分
#    "技能差"与"库里没货"——任何记忆系统调试都要这个现场；
# 3) 滚动窗口 = 进化版的"遗忘"：旧失败不反映新技能，留在池里
#    只会让 designer 过拟合历史——进化系统自己也要会忘。
# ============================================================================
