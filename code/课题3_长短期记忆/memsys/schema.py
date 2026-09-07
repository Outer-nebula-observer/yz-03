# -*- coding: utf-8 -*-
"""
memsys.schema — 赛题③ 记忆系统统一数据模型
==========================================
对应 `docs/04_赛题三长短期记忆系统完整方案.md` 第 1.3 节"概念数据模型"。

四类核心对象：
  1. WorkingMemorySlot  短期工作记忆槽位（单场次）
  2. MemoryEntry        长期记忆条目（事实 fact / 经验 experience 两类）
  3. QueryItem          查询列表项（规划阶段显式化的检索计划）
  4. RetrievedMemory    检索结果（带评分与溯源）

设计约定（全模块共用）：
  - 时间统一用 Unix 时间戳（float 秒），由 time.time() 产生；
  - 记忆条目唯一 id 用 "<type>-<uuid8>" 形式，便于日志排查；
  - 所有字段可 JSON 序列化（dataclasses.asdict 即可落盘），方便 eval 回放；
  - embeddings 不存在条目里（存向量库/内存索引侧），条目只存业务字段——
    与 Zep 的"非损式 episode + 侧挂语义"思路一致（见 笔记_Rasmussen2025-Zep）。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------- 长期记忆类型
class MemoryType(str, Enum):
    """长期记忆两类（对应 docs/04 2.2 节）。

    - FACT: 事实记忆——装备参数、条令、战例客观信息（要求参数级精确召回）
    - EXPERIENCE: 经验记忆——成败教训、可复用策略（语义召回即可）
    """

    FACT = "fact"
    EXPERIENCE = "experience"


class MemoryOp(str, Enum):
    """记忆进化四操作（对应 docs/04 2.4 节，TiM 的 insert/forget/merge + 抽象）。

    进化操作由 evolution 模块统一执行；此处枚举用于在日志/回放里标记
    "这条记忆经历过哪些操作"，支撑消融实验 G4 的可解释性。
    """

    WRITE = "write"      # 写入新记忆
    MERGE = "merge"      # 合并去重（相似度阈值 θ，PREMem 链接对思路）
    FORGET = "forget"    # 遗忘（艾宾浩斯时间衰减，MemoryBank 思路）
    ABSTRACT = "abstract"  # 抽象（低层记忆→高层教训/画像）


# ---------------------------------------------------------------- 短期工作记忆
@dataclass
class WorkingMemorySlot:
    """短期工作记忆槽位——**一个规划场次（session）对应一个槽位**。

    组织范式来自 MemGPT（笔记_Packer2023-MemGPT）：
      - working_context  ≈ MemGPT 的 working context（高频关键信息常驻）
      - fifo_queue       ≈ MemGPT 的 FIFO queue（消息/中间结果滚动）
      - 超限时由 compression 模块触发"memory pressure"归档（阈值驱动）
    """

    plan_id: str                      # 场次/规划任务唯一 id
    goal: str = ""                    # 本次规划目标
    constraints: List[str] = field(default_factory=list)   # 作战约束（不可压缩字段）
    query_list: List["QueryItem"] = field(default_factory=list)  # ② 查询列表
    loaded_memory: List[str] = field(default_factory=list)  # ④ 已装载记忆的 id 列表
    intermediate_results: List[Dict[str, Any]] = field(default_factory=list)  # 管线中间结果
    working_context: str = ""         # 高频关键信息（常驻，压缩时最后动它）
    fifo_queue: List[str] = field(default_factory=list)   # 滚动消息队列（最旧先出）
    status: str = "open"              # open / closed
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        """任何写操作后调用——统一刷新 updated_at。"""
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------- 长期记忆条目
@dataclass
class MemoryEntry:
    """长期记忆条目（事实或经验）。

    字段对照：
      - importance/decay_strength/recall_count/last_recalled_at
          服务"艾宾浩斯遗忘"（MemoryBank：R = e^(-t/S)，S 随召回 +1 并重置 t）；
      - source/session_id/timestamp
          服务"可解释溯源"（创新点 E：每条注入规划的记忆必须能回查来历）；
      - merged_from/op_history
          服务"进化可回放"（G4 消融要能解释每条记忆怎么来的）。
    """

    id: str
    type: MemoryType                  # fact / experience
    content: str                      # 记忆正文（事实=结构化描述；经验=教训摘要）
    source: str = ""                  # 来源（场次/文档/推演日志）
    session_id: str = ""              # 产生该记忆的场次
    timestamp: float = field(default_factory=time.time)
    importance: float = 1.0           # 重要性打分（遗忘公式的 S 初值）
    decay_strength: float = 1.0       # 艾宾浩斯 S：每次召回 +1（命中强化）
    recall_count: int = 0             # 被召回次数
    last_recalled_at: Optional[float] = None  # 上次召回时间（t 的起点）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展字段（领域标签等）
    merged_from: List[str] = field(default_factory=list)    # 合并来源条目 id
    op_history: List[str] = field(default_factory=list)     # 经历过的操作序列

    # ---------- 遗忘模型（MemoryBank，R = e^(-t/S)） ----------
    def retention(self, now: Optional[float] = None) -> float:
        """计算当前留存率 R ∈ (0, 1]。

        R = e^(-t/S)：t = 距上次召回（或创建）的秒数；S = 强度。
        - 新记忆 S=1 → 几小时内衰减明显（艾宾浩斯"先快后慢"）；
        - 每被召回一次：S += 1 且 t 重置 → 越常用越不容易忘（间隔效应）。
        """
        now = now if now is not None else time.time()
        t = now - (self.last_recalled_at or self.timestamp)
        # 防御：时间倒退/未初始化时视为刚创建
        t = max(t, 0.0)
        import math
        return math.exp(-t / max(self.decay_strength, 1e-6))

    def mark_recalled(self) -> None:
        """检索命中后调用——实现'命中强化'（S+1，重置 t）。"""
        self.recall_count += 1
        self.decay_strength += 1.0
        self.last_recalled_at = time.time()

    # ---------- 溯源（创新点 E） ----------
    def provenance(self) -> Dict[str, Any]:
        """返回溯源信息（规划输出强制引用时使用）。"""
        return {
            "id": self.id,
            "type": self.type.value,
            "source": self.source,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "recall_count": self.recall_count,
        }

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value  # 枚举转字符串，保证 JSON 可序列化
        return d


def new_entry(type_: MemoryType, content: str, **kwargs: Any) -> MemoryEntry:
    """构造新记忆条目的便捷函数（自动生成 id）。

    兼容别名：attrs= 会被映射为 metadata=（事实库的属性键值对）。
    """
    if "attrs" in kwargs:  # 事实库属性键值对别名 → metadata
        kwargs.setdefault("metadata", kwargs.pop("attrs"))
    return MemoryEntry(
        id=f"{type_.value}-{uuid.uuid4().hex[:8]}", type=type_, content=content, **kwargs
    )


# ---------------------------------------------------------------- 查询列表
@dataclass
class QueryItem:
    """查询列表项——规划阶段显式化"我需要什么知识/经验"（创新点 C）。

    对应 ChatDB 的 Chain-of-Memory（把检索变成可审计的计划）：
      - intent:     这个查询想干什么（目标/约束/事实/经验）；
      - target:     要查哪类记忆（fact/experience/short_term）；
      - route:      走哪条检索路（vector/bm25/sql）——检索层按此路由（MIRIX 式）；
      - query_text: 自然语言查询串。
    """

    q_id: str
    intent: str                       # 查询意图描述（如"查红方装甲单位参数"）
    target: str = "fact"              # fact / experience / short_term
    route: str = "vector"             # vector / bm25 / sql
    query_text: str = ""              # 实际查询文本
    answer_memory_ids: List[str] = field(default_factory=list)  # 命中的记忆 id（回填）

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------- 检索结果
@dataclass
class RetrievedMemory:
    """一次检索返回的单条结果（带评分与溯源）。

    score 的量纲依 route 而异（cosine ∈ [-1,1]、BM25 ≥ 0），
    hybrid 检索层会做归一化后再融合排序。
    """

    entry: MemoryEntry                # 命中的记忆条目
    score: float                      # 相关性得分
    route: str                        # 命中路径（vector/bm25/sql）
    rank: int = 0                     # 融合后的名次

    def to_dict(self) -> Dict[str, Any]:
        return {"score": self.score, "route": self.route, "rank": self.rank,
                "entry": self.entry.to_dict()}
