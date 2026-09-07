# -*- coding: utf-8 -*-
"""课题3_长短期记忆 包入口：导出 engine_plugin（老师平台发现点）+ memsys 快捷导入。

- 在 SDK 服务环境：平台扫描 engines 目录时读取 engine_plugin 自动注册；
- 独立运行：from 课题3_长短期记忆 import MemoryPipeline 等价于 from memsys import ...
"""

from .memsys import (  # noqa: F401  再导出，方便单层导入
    MemoryPipeline, MemoryController, MemoryEvolution, EvolutionReport,
    HybridRetriever, FactualStore, ExperientialStore, WorkingMemory,
    QueryItem, MemoryEntry, MemoryType, new_entry,
    MockLLM, MockEmbedding, get_llm,
)

try:
    from .engine import engine_plugin  # SDK 环境注册点
except Exception:  # engine 依赖缺失时不应阻塞包导入
    engine_plugin = None  # type: ignore[assignment]

__all__ = [
    "MemoryPipeline", "MemoryController", "MemoryEvolution", "EvolutionReport",
    "HybridRetriever", "FactualStore", "ExperientialStore", "WorkingMemory",
    "QueryItem", "MemoryEntry", "MemoryType", "new_entry",
    "MockLLM", "MockEmbedding", "get_llm", "engine_plugin",
]
