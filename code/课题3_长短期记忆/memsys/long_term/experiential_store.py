# -*- coding: utf-8 -*-
"""
memsys.long_term.experiential_store — 经验记忆库（向量 + 摘要 + SQLite 持久化）
================================================================================
思路来源：
  - ExpeL（笔记_Zhao2023-ExpeL）：Faiss 向量召回相似"成功轨迹/教训"；
  - Reflexion（笔记_Shinn2023-Reflexion）：语言形式经验（教训文本即记忆）；
  - Memp（笔记_Fang2025-Memp）：程序性经验（Build/Retrieve/Update 生命周期）。

【评审修复·持久化】原实现为纯内存 dict（重启即失，验收底线 #3"长期记忆
≥100 条持久化"无法达成）。现支持 SQLite 落盘：
  - ExperientialStore(emb)                → 内存态（演示/测试默认，行为不变）
  - ExperientialStore(emb, db_path="x.db") → 落盘态（add/remove/persist_recall
    全部写穿；启动时自动加载并重建向量索引）

与事实库的差异：
  - 检索以**语义相似**为主（同义不同词也能召回），不做属性精确过滤；
  - 条目天然带 importance（失败教训权重更高——Reflexion 的"失败学得更多"）。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Dict, List, Optional

from ..schema import MemoryEntry, MemoryType, RetrievedMemory, new_entry
from ..embeddings import MemoryVectorIndex, MockEmbedding
from .base import BaseLongTermStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiences (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    timestamp REAL,
    importance REAL DEFAULT 1.0,
    decay_strength REAL DEFAULT 1.0,
    recall_count INTEGER DEFAULT 0,
    last_recalled_at REAL,
    attrs_json TEXT DEFAULT '{}',
    merged_from_json TEXT DEFAULT '[]',
    op_history_json TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_exp_ts ON experiences(timestamp);
"""


def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
    return MemoryEntry(
        id=row["id"], type=MemoryType.EXPERIENCE, content=row["content"],
        source=row["source"], session_id=row["session_id"],
        timestamp=row["timestamp"], importance=row["importance"],
        decay_strength=row["decay_strength"], recall_count=row["recall_count"],
        last_recalled_at=row["last_recalled_at"],
        metadata=json.loads(row["attrs_json"]),
        merged_from=json.loads(row["merged_from_json"]),
        op_history=json.loads(row["op_history_json"]),
    )


def _entry_params(e: MemoryEntry) -> tuple:
    return (e.id, e.content, e.source, e.session_id, e.timestamp, e.importance,
            e.decay_strength, e.recall_count, e.last_recalled_at,
            json.dumps(e.metadata, ensure_ascii=False),
            json.dumps(e.merged_from), json.dumps(e.op_history))


class ExperientialStore(BaseLongTermStore):
    """经验记忆库：向量召回 + 摘要条目（可选 SQLite 持久化）。

    用法：
        store = ExperientialStore()                      # 内存态（默认）
        store = ExperientialStore(db_path="memory.db")   # 落盘态（跨进程持久）
        e = new_entry(MemoryType.EXPERIENCE,
                      "教训：夜战中未派先遣侦察导致遭遇伏击；对策：先遣侦察前置 30 分钟",
                      importance=2.0, source="场次#12 复盘")
        store.add(e)
        store.search("夜间行军 侦察")   # → 语义召回该教训
    """

    def __init__(self, embedding: Optional[MockEmbedding] = None,
                 db_path: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        self._entries: Dict[str, MemoryEntry] = {}
        self.vindex = MemoryVectorIndex(embedding or MockEmbedding())
        self.version = 0          # 语料版本号（BM25 缓存失效用）
        self._db: Optional[sqlite3.Connection] = None
        if db_path:
            self._db = sqlite3.connect(db_path, check_same_thread=False)
            self._db.row_factory = sqlite3.Row
            self._db.executescript(_SCHEMA)
            # 启动加载：条目入内存 + 向量索引重建（幂等）
            with self._lock:
                for row in self._db.execute(
                        "SELECT * FROM experiences"):
                    e = _row_to_entry(row)
                    self._entries[e.id] = e
                    self.vindex.add(e.id, f"{e.content}\n{e.source}")

    # ------------------------- 写路径（进化层专用） -------------------------
    def add(self, entry: MemoryEntry) -> MemoryEntry:
        with self._lock:
            self._entries[entry.id] = entry
            if self._db is not None:
                self._db.execute(
                    "INSERT OR REPLACE INTO experiences VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    _entry_params(entry))
                self._db.commit()
        # 向量编码内容 = 教训正文 + 元信息（提高"情境相似"的召回质量）
        self.vindex.add(entry.id, f"{entry.content}\n{entry.source}")
        self.version += 1  # 语料变了 → BM25 缓存需重建
        return entry

    def update(self, entry: MemoryEntry) -> None:
        self.add(entry)  # 幂等覆盖 + 索引刷新

    def remove(self, entry_id: str) -> None:
        with self._lock:
            self._entries.pop(entry_id, None)
            if self._db is not None:
                self._db.execute("DELETE FROM experiences WHERE id=?",
                                 (entry_id,))
                self._db.commit()
        self.vindex.remove(entry_id)
        self.version += 1

    # ------------------------- 读路径（检索层） -------------------------
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        return self._entries.get(entry_id)

    def candidates(self) -> List[str]:
        return list(self._entries)

    def search(self, query: str, top_k: int = 5) -> List[RetrievedMemory]:
        """语义召回 + 重要性加权（重要教训更容易浮上来）。

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
            results.append(RetrievedMemory(entry=e, score=score, route="vector"))
        results.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(results[:top_k]):
            r.rank = i + 1
        return results[:top_k]

    def persist_recall(self, entry: MemoryEntry) -> None:
        """命中强化持久化：落盘态回写 SQLite（重启后 S/召回史不丢）。"""
        if self._db is None:
            return None  # 内存态：mark_recalled 已即时生效
        with self._lock:
            self._db.execute(
                "UPDATE experiences SET recall_count=?, decay_strength=?, "
                "last_recalled_at=? WHERE id=?",
                (entry.recall_count, entry.decay_strength,
                 entry.last_recalled_at, entry.id))
            self._db.commit()
        return None
