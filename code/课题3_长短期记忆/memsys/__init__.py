# -*- coding: utf-8 -*-
"""
memsys — 赛题③「长短期记忆系统」核心包
=======================================
分层（与 docs/04 四大模块一一对应）：
  schema       统一数据模型（槽位/条目/查询/结果）
  llm          LLM 抽象（MockLLM 离线可跑 / OpenAI 兼容真模型骨架）
  embeddings   向量化抽象（Mock 哈希向量 / OpenAI 骨架 + 内存向量索引）
  short_term   短期工作记忆（MemGPT 分层 + 压缩策略）
  long_term    长期双库（事实 SQLite 精确 / 经验 向量+摘要）
  retrieval    任务感知混合检索（vector + BM25 + SQL 路由融合）
  evolution    记忆进化四操作（写入/合并/遗忘/抽象）
  controller   总调度（SCM 思想：何时写/读/归档）
  pipeline     七步闭环编排（离线可演示全链路）

快速上手：
    from memsys import MemoryPipeline
    pipe = MemoryPipeline()                  # 全 Mock，零依赖
    result = pipe.run_session("P001", "夺占 2 号高地")
"""

from .schema import (MemoryType, MemoryOp, WorkingMemorySlot, MemoryEntry,
                     QueryItem, RetrievedMemory, new_entry)
from .llm import LLMClient, MockLLM, OpenAICompatibleClient, get_llm
from .embeddings import (EmbeddingModel, MockEmbedding, OpenAIEmbedding,
                         MemoryVectorIndex, cosine, tokenize)
from .short_term import WorkingMemory, get_strategy
from .long_term import BaseLongTermStore, FactualStore, ExperientialStore
from .retrieval import BM25, HybridRetriever
from .evolution import MemoryEvolution, EvolutionReport
from .controller import MemoryController
from .pipeline import MemoryPipeline, SessionResult

__version__ = "0.1.0"

__all__ = [
    # schema
    "MemoryType", "MemoryOp", "WorkingMemorySlot", "MemoryEntry",
    "QueryItem", "RetrievedMemory", "new_entry",
    # llm / embeddings
    "LLMClient", "MockLLM", "OpenAICompatibleClient", "get_llm",
    "EmbeddingModel", "MockEmbedding", "OpenAIEmbedding",
    "MemoryVectorIndex", "cosine", "tokenize",
    # 模块
    "WorkingMemory", "get_strategy",
    "BaseLongTermStore", "FactualStore", "ExperientialStore",
    "BM25", "HybridRetriever",
    "MemoryEvolution", "EvolutionReport",
    "MemoryController", "MemoryPipeline", "SessionResult",
]
