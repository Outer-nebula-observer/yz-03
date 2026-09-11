# -*- coding: utf-8 -*-
"""
memsys.long_term.base — 长期记忆抽象基类（接口契约）
=====================================================
统一"事实库"与"经验库"的接口（检索只读、进化只写——docs/04 避坑点 3）：

  读路径（检索层调用）：search / get / candidates —— 只读，无副作用
  写路径（仅进化层调用）：add / update / remove —— 写入，与检索解耦

为什么这样切分？
  - **独立评测**：检索层可以在不改变任何数据的前提下测命中率；
    进化层的写操作可以单独做回放审计。如果读写混在一个方法里，
    检索一次就可能污染库状态，消融无法公平对比。
  - **依赖倒置**：业务代码只认这个接口，事实库换 SQLite 版本、
    经验库换 FAISS 底层，都不影响上层。

两库差异体现在**实现**而非接口：
  - FactualStore      ：SQLite 结构化行（参数级精确召回，ChatDB 思路）
  - ExperientialStore ：向量 + 摘要 + SQLite 持久化（语义召回，ExpeL/Reflexion 思路）

统计接口 stats() 供消融记录"库规模 vs 检索精度"曲线。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..schema import MemoryEntry, RetrievedMemory


class BaseLongTermStore(ABC):
    """长期记忆库抽象基类（事实/经验两库共同接口）。

    子类必须实现 6 个抽象方法；stats() 有基类默认实现。
    约定：add/update/remove 只能由 evolution 层调用；search/get/
    candidates 供 retrieval 层调用。
    """

    # ------------------------- 读路径（检索层调用，只读） -------------------------
    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[RetrievedMemory]:
        """按查询检索 top-k（各库自实现打分与路由）。

        - FactualStore.search      向量+LIKE 兜底（通用查询）；
        - ExperientialStore.search 向量+重要性加权（语义召回）。
        注意：检索**不得修改条目状态**（命中强化由 hybrid 统一负责）。
        """

    @abstractmethod
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """按 id 精确取（溯源/回放/删除前确认用）。未命中返回 None。"""

    @abstractmethod
    def candidates(self) -> List[str]:
        """全部条目 id（供向量索引限定候选集 / 消融统计 / 全量扫描）。"""

    # ------------------------- 写路径（仅进化层调用） -------------------------
    @abstractmethod
    def add(self, entry: MemoryEntry) -> MemoryEntry:
        """写入新条目（同时登记索引）。

        子类各自保证：条目进容器 + 向量索引更新 + 语料版本号+1
        （BM25 缓存失效依据）。返回同一 entry 便于链式调用。
        """

    @abstractmethod
    def update(self, entry: MemoryEntry) -> None:
        """更新已有条目（合并/抽象后回写）。

        约定：按 id 覆盖（insert-or-replace 语义），内容换血时索引
        与版本号必须同步刷新——否则 BM25 缓存会命中陈旧内容。
        """

    @abstractmethod
    def remove(self, entry_id: str) -> None:
        """删除条目（遗忘操作落地）。必须同步清理向量索引与版本号。"""

    # ------------------------- 统计（评估用） -------------------------
    def stats(self) -> dict:
        """库规模统计（消融实验记录'存储规模 vs 检索精度'）。"""
        return {"count": len(self.candidates())}
