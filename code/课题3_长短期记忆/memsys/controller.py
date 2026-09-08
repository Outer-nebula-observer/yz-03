# -*- coding: utf-8 -*-
"""
memsys.controller — 记忆调度控制器（SCM 思想）
===============================================
职责（docs/04 七步闭环的"总调度"）：
  ① 场次开始：创建工作记忆槽位（goal/constraints/查询列表）；
  ② 场次中：检索装载、memory_pressure 预警时触发压缩；
  ③ 场次结束：把工作记忆的归档物（archived）+ 复盘文本交给进化器沉淀。

设计来源：SCM 的 memory controller（笔记_Liang2023-SCM，paper_code/
04_记忆进化/SCM4LLMs/core/chat.py）——"何时写、何时读、读什么"显式化；
加上 MemGPT 的阈值驱动（memory_pressure → 主动归档）。

控制器是**唯一**允许同时碰"短期、长期、检索、进化"的角色，
其余模块相互之间只通过 schema 里的数据对象交互（保证可独立评测）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .schema import QueryItem, RetrievedMemory
from .llm import LLMClient, MockLLM
from .embeddings import MockEmbedding
from .short_term.working_memory import WorkingMemory
from .short_term.compression import get_strategy
from .long_term.factual_store import FactualStore
from .long_term.experiential_store import ExperientialStore
from .retrieval.hybrid import HybridRetriever
from .evolution.memory_evolution import MemoryEvolution, EvolutionReport


class MemoryController:
    """赛题③记忆系统总控制器。

    用法（与 pipeline.py 配合，一般不直接用）：
        ctl = MemoryController()                     # 默认全 Mock，离线可跑
        ctl.start_session("P001", goal="夺占 2 号高地",
                          constraints=["禁止越境"], queries=[...])
        results = ctl.retrieve_and_load()            # ③④ 检索并装载
        ...（规划管线执行，期间 ctl.push/record 消息与中间结果）
        report = ctl.close_session(review_text="...")  # ⑦ 复盘沉淀
    """

    def __init__(self, factual: Optional[FactualStore] = None,
                 experiential: Optional[ExperientialStore] = None,
                 llm: Optional[LLMClient] = None,
                 embedding: Optional[MockEmbedding] = None,
                 compression: str = "truncate",
                 capacity_tokens: int = 4000) -> None:
        # 依赖注入：全部可替换（测试/消融时注入不同实现）
        # llm 缺省落 MockLLM：保证"零配置离线可跑"，接真模型时注入即可
        self.llm: LLMClient = llm if llm is not None else MockLLM()
        self.embedding = embedding or MockEmbedding()
        self.factual = factual or FactualStore(":memory:", self.embedding)
        self.experiential = experiential or ExperientialStore(self.embedding)
        self.retriever = HybridRetriever(self.factual, self.experiential)
        self.evolution = MemoryEvolution(self.factual, self.experiential,
                                         self.llm, self.embedding)
        self.compression_name = compression
        self.capacity_tokens = capacity_tokens
        self._wm: Optional[WorkingMemory] = None
        # 会话级检索统计（评估：每场命中多少条、走了哪些路）
        self.session_stats: Dict[str, int] = {"retrieved": 0, "loaded": 0,
                                              "compressed": 0}

    # ---------------------------------------------------------------- ① 开场
    def start_session(self, plan_id: str, goal: str,
                      constraints: Optional[List[str]] = None,
                      queries: Optional[List[QueryItem]] = None) -> WorkingMemory:
        """① 规划开始：建槽位、设置目标约束、装载查询列表。"""
        self._wm = WorkingMemory(plan_id=plan_id, capacity_tokens=self.capacity_tokens,
                                 llm=self.llm)
        self._wm.set_goal(goal, constraints)
        if queries:
            self._wm.set_query_list(queries)
        self.session_stats = {"retrieved": 0, "loaded": 0, "compressed": 0}
        return self._wm

    # ---------------------------------------------------------------- ③④ 检索装载
    def retrieve_and_load(self, top_k: int = 3) -> List[RetrievedMemory]:
        """执行查询列表并装载：对每个 q 检索 top-k，全部登记进工作记忆。"""
        if self._wm is None:
            raise RuntimeError("先 start_session() 再检索")
        all_hits: List[RetrievedMemory] = []
        for q in self._wm.slot.query_list:
            hits = self.retriever.retrieve(q, top_k=top_k)
            for h in hits:
                self._wm.load_memory(h.entry.id)  # 溯源：记录装载了谁
                all_hits.append(h)
                self.session_stats["retrieved"] += 1
                self.session_stats["loaded"] += 1
        # 装载后若触发 memory_pressure → 立即压缩（SCM/MemGPT 阈值驱动）
        if self._wm.memory_pressure:
            get_strategy(self.compression_name).apply(
                self._wm, int(self.capacity_tokens * 0.7))
            self.session_stats["compressed"] += 1
        return all_hits

    # ---------------------------------------------------------------- 场次中消息
    def push(self, msg: str) -> None:
        """规划管线推消息进工作记忆（自动处理超限 flush）。"""
        if self._wm:
            self._wm.push_message(msg)

    def record(self, step: str, result) -> None:
        """记录管线某步中间结果（分析/生成/比较…）。"""
        if self._wm:
            self._wm.record_result(step, result)

    # ---------------------------------------------------------------- ⑦ 收场
    def close_session(self, review_text: str = "") -> EvolutionReport:
        """场次结束：关闭工作记忆 + 复盘驱动进化沉淀。

        review_text: 复盘对话/总结文本（含"教训/经验/参数"等关键词的行
                     会被 MockLLM 规则抽取为记忆——真模型时是 LLM 抽取）。
        返回 EvolutionReport（write/merge/forget/abstract 统计）。
        """
        if self._wm is None:
            raise RuntimeError("没有活动场次")
        # 工作记忆归档物并入复盘材料（MemGPT flush 出的内容不丢）
        material = review_text
        if self._wm.archived:
            arch_text = "\n".join(a.get("summary", "") for a in self._wm.archived)
            material = f"{review_text}\n[工作记忆归档]\n{arch_text}"
        report = self.evolution.evolve_from_review(material,
                                                   session_id=self._wm.slot.plan_id)
        self._wm.close()
        # 【语义修复】场次结束后清除引用——working_memory 返回 None、
        # render_context 返回空串（此前仍持已关闭槽位，状态查询与
        # webui 会把"已关场次"当成活动场次展示）。
        self._wm = None
        return report

    # ---------------------------------------------------------------- 便捷读取
    @property
    def working_memory(self) -> Optional[WorkingMemory]:
        return self._wm

    def render_context(self) -> str:
        """当前应注入规划 LLM 的完整上下文（含目标/约束/装载记忆）。"""
        return self._wm.render() if self._wm else ""
