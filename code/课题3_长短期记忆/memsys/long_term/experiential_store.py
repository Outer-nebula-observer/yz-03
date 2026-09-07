# -*- coding: utf-8 -*-
"""
memsys.long_term.experiential_store — 经验记忆库（向量 + 摘要）
================================================================
思路来源：
  - ExpeL（笔记_Zhao2023-ExpeL）：Faiss 向量召回相似"成功轨迹/教训"；
  - Reflexion（笔记_Shinn2023-Reflexion）：语言形式经验（教训文本即记忆）；
  - Memp（笔记_Fang2025-Memp）：程序性经验（Build/Retrieve/Update 生命周期）。

MVP 形态：内存 dict 存条目 + 向量索引做召回（不落盘——经验库重启重建即可；
后续接 FAISS/Chroma 时替换 _entries+vindex 的持久化层）。

与事实库的差异：
  - 检索以**语义相似**为主（同义不同词也能召回），不做属性精确过滤；
  - 条目天然带 importance（失败教训权重更高——Reflexion 的"失败学得更多"）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..schema import MemoryEntry, MemoryType, RetrievedMemory, new_entry
from ..embeddings import MemoryVectorIndex, MockEmbedding
from .base import BaseLongTermStore


class ExperientialStore(BaseLongTermStore):
    """经验记忆库：向量召回 + 摘要条目。

    用法：
        store = ExperientialStore()
        e = new_entry(MemoryType.EXPERIENCE,
                      "教训：夜战中未派先遣侦察导致遭遇伏击；对策：先遣侦察前置 30 分钟",
                      importance=2.0, source="场次#12 复盘")
        store.add(e)
        store.search("夜间行军 侦察")   # → 语义召回该教训
    """

    def __init__(self, embedding: Optional[MockEmbedding] = None) -> None:
        self._entries: Dict[str, MemoryEntry] = {}
        self.vindex = MemoryVectorIndex(embedding or MockEmbedding())

    # ------------------------- 写路径（进化层专用） -------------------------
    def add(self, entry: MemoryEntry) -> MemoryEntry:
        self._entries[entry.id] = entry
        # 向量编码内容 = 教训正文 + 元信息（提高"情境相似"的召回质量）
        self.vindex.add(entry.id, f"{entry.content}\n{entry.source}")
        return entry

    def update(self, entry: MemoryEntry) -> None:
        self.add(entry)  # 幂等覆盖 + 索引刷新

    def remove(self, entry_id: str) -> None:
        self._entries.pop(entry_id, None)
        self.vindex.remove(entry_id)

    # ------------------------- 读路径（检索层） -------------------------
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        return self._entries.get(entry_id)

    def candidates(self) -> List[str]:
        return list(self._entries)

    def search(self, query: str, top_k: int = 5) -> List[RetrievedMemory]:
        """语义召回 + 重要性加权（重要教训更容易浮上来）+ 命中强化。

        score = 0.8 * cosine + 0.2 * min(importance/3, 1)
        （权重写死为 MVP 常数；消融 G3 可调，观察'重要性加权'是否增益。）
        """
        raw = self.vindex.search(query, top_k=top_k * 2)  # 多取一倍再重排
        results: List[RetrievedMemory] = []
        for mid, cos in raw:
            e = self._entries.get(mid)
            if e is None:
                continue
            score = 0.8 * cos + 0.2 * min(e.importance / 3.0, 1.0)
            e.mark_recalled()
            results.append(RetrievedMemory(entry=e, score=score, route="vector"))
        results.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(results[:top_k]):
            r.rank = i + 1
        return results[:top_k]
