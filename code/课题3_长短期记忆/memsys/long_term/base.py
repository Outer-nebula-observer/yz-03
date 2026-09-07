# -*- coding: utf-8 -*-
"""
memsys.long_term.base — 长期记忆抽象基类
=========================================
统一"事实库"与"经验库"的接口（检索只读、进化只写——docs/04 避坑点 3）：

  读路径（检索层调用）：search / get / candidates
  写路径（仅进化层调用）：add / update / remove

两库差异体现在**实现**而非接口：
  - FactualStore：SQLite 结构化行（参数级精确召回，ChatDB 思路）
  - ExperientialStore：向量 + 摘要（语义召回，ExpeL/Reflexion 思路）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List, Optional

from ..schema import MemoryEntry, RetrievedMemory


class BaseLongTermStore(ABC):
    """长期记忆库抽象基类（事实/经验两库共同接口）。"""

    # ------------------------- 读路径（检索层） -------------------------
    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> List[RetrievedMemory]:
        """按查询检索 top-k（各库自实现打分与路由）。"""

    @abstractmethod
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """按 id 精确取（溯源/回放用）。"""

    @abstractmethod
    def candidates(self) -> List[str]:
        """全部条目 id（供向量索引限定候选集 / 消融统计）。"""

    # ------------------------- 写路径（仅进化层） -------------------------
    @abstractmethod
    def add(self, entry: MemoryEntry) -> MemoryEntry:
        """写入新条目（同时登记索引）。"""

    @abstractmethod
    def update(self, entry: MemoryEntry) -> None:
        """更新已有条目（合并/抽象后回写）。"""

    @abstractmethod
    def remove(self, entry_id: str) -> None:
        """删除条目（遗忘操作落地）。"""

    # ------------------------- 统计（评估用） -------------------------
    def stats(self) -> dict:
        """库规模统计（消融实验记录'存储规模 vs 检索精度'）。"""
        return {"count": len(self.candidates())}
