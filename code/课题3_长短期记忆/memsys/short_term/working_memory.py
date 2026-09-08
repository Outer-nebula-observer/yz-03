# -*- coding: utf-8 -*-
"""
memsys.short_term.working_memory — 短期 / 工作记忆层
====================================================
组织范式：MemGPT 分层（笔记_Packer2023-MemGPT）
  - working_context：高频关键信息常驻（最后才压缩）
  - fifo_queue：消息/中间结果滚动队列（最旧先出）
  - 阈值驱动：达到 warning 阈值→标记 memory_pressure（提示上层主动归档）；
              达到 flush 阈值→自动 flush（驱逐旧消息 + 递归摘要）。

调度思想：SCM 记忆控制器（笔记_Liang2023-SCM）——"何时写、何时读、何时归档"显式化。
压缩策略：截断（MVP）→ 摘要（MockLLM/真模型）→ LLMLingua（预留接口，见 compression.py）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..schema import WorkingMemorySlot, QueryItem
from ..llm import LLMClient


class WorkingMemory:
    """单场次工作记忆管理器。

    容量模型（简化版 token 计量：1 中文字≈1 token，英文按词）：
      - capacity_tokens: 硬上限（≈ LLM 上下文预算）；
      - warning_ratio:   达到该比例 → memory_pressure=True（SCM 式预警）；
      - flush_ratio:     达到该比例 → 自动 flush 旧消息并生成递归摘要。

    用法（pipeline 内部调用，一般不直接用）：
        wm = WorkingMemory(plan_id="P001", capacity_tokens=4000)
        wm.set_goal("夺占 2 号高地", constraints=["禁止越境", "限时 4 小时"])
        wm.push_message("指挥所：红方 3 营于东侧集结")
        wm.load_memory(mid)            # 记录装载的长期记忆 id
        if wm.memory_pressure: ...     # 上层决定是否压缩/归档
    """

    def __init__(self, plan_id: str, capacity_tokens: int = 4000,
                 warning_ratio: float = 0.7, flush_ratio: float = 1.0,
                 llm: Optional[LLMClient] = None) -> None:
        self.slot = WorkingMemorySlot(plan_id=plan_id)
        self.capacity_tokens = capacity_tokens
        self.warning_ratio = warning_ratio
        self.flush_ratio = flush_ratio
        self.llm = llm
        self.archived: List[Dict[str, Any]] = []   # flush 出去的消息（含摘要），供长期归档
        self._recursive_summary: str = ""          # 递归摘要（MemGPT flush 机制）

    # ---------- 基础读写 ----------
    def set_goal(self, goal: str, constraints: Optional[List[str]] = None) -> None:
        """设置本次规划目标与约束（约束字段在压缩时**永不删除**）。"""
        self.slot.goal = goal
        self.slot.constraints = constraints or []
        self.slot.touch()

    def set_query_list(self, queries: List[QueryItem]) -> None:
        """② 查询列表装载（创新点 C：检索计划显式化）。"""
        self.slot.query_list = queries
        self.slot.touch()

    def set_stage(self, stage_id: str) -> None:
        """进入指定规划阶段（MDMP 七步之一，stages.py 的 stage_id）。"""
        self.slot.current_stage = stage_id
        self.slot.touch()

    def push_message(self, msg: str) -> None:
        """消息进入 FIFO 队列；超 flush 阈值自动驱逐最旧并更新递归摘要。"""
        self.slot.fifo_queue.append(msg)
        self.slot.touch()
        if self.used_ratio >= self.flush_ratio:
            self._flush()

    def record_result(self, step: str, result: Any) -> None:
        """记录管线中间结果（分析/生成/比较等步骤产物）。"""
        self.slot.intermediate_results.append({"step": step, "result": result,
                                               "at": self.slot.updated_at})
        self.slot.touch()

    def load_memory(self, memory_id: str) -> None:
        """④ 记录已装载进上下文的长期记忆 id（用于溯源与消融统计）。"""
        if memory_id not in self.slot.loaded_memory:
            self.slot.loaded_memory.append(memory_id)
            self.slot.touch()

    # ---------- 容量与阈值（MemGPT 式） ----------
    @staticmethod
    def _count_tokens(text: str) -> int:
        """简化 token 计数：中文字符逐个计，ASCII 按空白切词。"""
        cn = sum(1 for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF)
        ascii_words = len([w for w in text.split() if w.isascii()])
        return cn + ascii_words

    @property
    def used_tokens(self) -> int:
        return self._count_tokens(self.render())

    @property
    def used_ratio(self) -> float:
        return self.used_tokens / max(self.capacity_tokens, 1)

    @property
    def memory_pressure(self) -> bool:
        """SCM 式预警：达 warning 阈值即 True，上层可提前归档关键信息。"""
        return self.used_ratio >= self.warning_ratio

    # ---------- 渲染（装载进 LLM 上下文的最终形态） ----------
    def render(self) -> str:
        """把槽位渲染为喂给 LLM 的上下文文本。

        顺序有讲究（对齐 LongLLMLingua 的位置偏置结论：关键信息放首尾）：
          头部：目标+约束（不可压缩）→ working_context
          尾部：查询列表 + 最近消息（FIFO 末尾=最新）
        """
        parts: List[str] = []
        if self.slot.current_stage:
            parts.append(f"【规划阶段】{self.slot.current_stage}")
        if self.slot.goal:
            parts.append(f"【目标】{self.slot.goal}")
        if self.slot.constraints:
            parts.append("【约束】" + "；".join(self.slot.constraints))
        # 【Bug 修复】原写法 slot._recursive_summary 恒不存在（hasattr 恒 False），
        # 属残留混乱代码；摘要本体就挂在管理器 self 上。
        if self._recursive_summary:
            parts.append(f"【历史摘要】{self._recursive_summary}")
        if self.slot.working_context:
            parts.append(f"【关键信息】{self.slot.working_context}")
        if self.slot.query_list:
            ql = "；".join(q.query_text or q.intent for q in self.slot.query_list)
            parts.append(f"【查询列表】{ql}")
        if self.slot.fifo_queue:
            parts.append("【近期消息】" + " | ".join(self.slot.fifo_queue[-20:]))
        return "\n".join(parts)

    # ---------- flush：驱逐 + 递归摘要（MemGPT 机制） ----------
    def _flush(self, keep_ratio: float = 0.5) -> None:
        """驱逐最旧的 ~50% 队列消息，用旧递归摘要+被驱逐消息生成新摘要。

        被驱逐消息存 self.archived（不丢——对应 MemGPT recall storage 思想），
        由 controller 决定是否进一步沉淀进长期记忆。
        """
        n = len(self.slot.fifo_queue)
        if n <= 2:
            return
        cut = max(1, int(n * keep_ratio))
        evicted = self.slot.fifo_queue[:cut]
        self.slot.fifo_queue = self.slot.fifo_queue[cut:]
        # 递归摘要：旧摘要 + 新驱逐消息 → 新摘要（真模型时由 LLM 完成）
        material = (self._recursive_summary + "\n" + "\n".join(evicted)).strip()
        if self.llm is not None:
            self._recursive_summary = self.llm.summarize(material, max_words=120)
        else:
            self._recursive_summary = material[:300]  # 无 LLM 时粗暴截断（保底）
        self.archived.append({"evicted": evicted, "summary": self._recursive_summary})
        self.slot.touch()

    # ---------- 压缩入口 ----------
    def compress(self, strategy: str = "truncate", budget_tokens: Optional[int] = None) -> str:
        """对外压缩接口（strategy: truncate / summarize / llmlingua-预留）。

        实现：先压缩 FIFO（历史消息可压），最后才动 working_context；
        约束字段永不被删（docs/04 避坑点 6"关键约束打不可压缩标记"）。
        """
        budget = budget_tokens or int(self.capacity_tokens * self.warning_ratio)
        if strategy == "summarize" and self.llm is not None:
            # 摘要式：整段历史一次性摘要
            material = "\n".join(self.slot.fifo_queue)
            self._recursive_summary = self.llm.summarize(material, max_words=120)
            self.archived.append({"evicted": list(self.slot.fifo_queue),
                                  "summary": self._recursive_summary})
            self.slot.fifo_queue = []
        else:
            # 截断式（MVP 保底）：删最旧消息直到回到预算内
            while self.used_tokens > budget and len(self.slot.fifo_queue) > 2:
                self.slot.fifo_queue.pop(0)
        self.slot.touch()
        return self.render()

    def close(self) -> None:
        """场次结束：标记 closed（controller 会触发长期沉淀）。"""
        self.slot.status = "closed"
        self.slot.touch()
