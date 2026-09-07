# -*- coding: utf-8 -*-
"""
memsys.long_term.factual_store — 事实记忆库（SQLite）
=====================================================
思路来源：ChatDB（笔记_Hu2023-ChatDB）——"数据库当符号记忆"。
  - 事实 = 结构化行：content(原文) + attr/value 键值对（装备参数、条令条款…）；
  - 精确查询：属性键值过滤（MVP 内置 mini 过滤器，后续可升级 NL→SQL）；
  - 辅助语义检索：向量索引做近似召回（参数名记不清时兜底）。

存储：单文件 SQLite（stdlib sqlite3，零依赖）。表结构：
    facts(id TEXT PK, type TEXT, content TEXT, source TEXT, session_id TEXT,
          timestamp REAL, importance REAL, decay_strength REAL,
          recall_count INTEGER, last_recalled_at REAL,
          attrs_json TEXT, merged_from_json TEXT, op_history_json TEXT)
"""

from __future__ import annotations

import json
import sqlite3
from typing import List, Optional

from ..schema import MemoryEntry, MemoryType, RetrievedMemory, new_entry
from ..embeddings import MemoryVectorIndex, MockEmbedding
from .base import BaseLongTermStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
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
CREATE INDEX IF NOT EXISTS idx_facts_ts ON facts(timestamp);
"""


class FactualStore(BaseLongTermStore):
    """事实记忆库：SQLite 行存 + 向量辅助索引。

    用法：
        store = FactualStore("facts.db")
        e = new_entry(MemoryType.FACT, "红方 T-90 主战坦克",
                      attrs={"单位": "红方", "装备": "T-90", "最大速度": "60km/h"})
        store.add(e)
        store.search("T-90 速度")             # 语义/关键词混合
        store.search_attrs({"装备": "T-90"})   # 精确属性过滤（参数级召回）
    """

    def __init__(self, db_path: str = ":memory:",
                 embedding: Optional[MockEmbedding] = None) -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.vindex = MemoryVectorIndex(embedding or MockEmbedding())
        # 启动时把已有行登记进向量索引（幂等）
        for row in self.conn.execute("SELECT id, content FROM facts"):
            self.vindex.add(row["id"], row["content"])

    # ------------------------- 行 <-> 条目 转换 -------------------------
    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"], type=MemoryType.FACT, content=row["content"],
            source=row["source"], session_id=row["session_id"],
            timestamp=row["timestamp"], importance=row["importance"],
            decay_strength=row["decay_strength"], recall_count=row["recall_count"],
            last_recalled_at=row["last_recalled_at"],
            metadata=json.loads(row["attrs_json"]),
            merged_from=json.loads(row["merged_from_json"]),
            op_history=json.loads(row["op_history_json"]),
        )

    @staticmethod
    def _entry_params(e: MemoryEntry) -> tuple:
        return (e.id, e.content, e.source, e.session_id, e.timestamp, e.importance,
                e.decay_strength, e.recall_count, e.last_recalled_at,
                json.dumps(e.metadata, ensure_ascii=False),
                json.dumps(e.merged_from), json.dumps(e.op_history))

    # ------------------------- 写路径（进化层专用） -------------------------
    def add(self, entry: MemoryEntry) -> MemoryEntry:
        self.conn.execute(
            "INSERT OR REPLACE INTO facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            self._entry_params(entry))
        self.conn.commit()
        self.vindex.add(entry.id, entry.content)
        return entry

    def update(self, entry: MemoryEntry) -> None:
        self.add(entry)  # INSERT OR REPLACE 幂等

    def remove(self, entry_id: str) -> None:
        self.conn.execute("DELETE FROM facts WHERE id=?", (entry_id,))
        self.conn.commit()
        self.vindex.remove(entry_id)

    # ------------------------- 读路径（检索层） -------------------------
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        row = self.conn.execute("SELECT * FROM facts WHERE id=?", (entry_id,)).fetchone()
        return self._row_to_entry(row) if row else None

    def candidates(self) -> List[str]:
        return [r["id"] for r in self.conn.execute("SELECT id FROM facts")]

    def search(self, query: str, top_k: int = 5) -> List[RetrievedMemory]:
        """混合检索：向量相似（主）+ 内容关键词包含（兜底），并做'命中强化'。"""
        results: List[RetrievedMemory] = []
        # 1) 向量近似召回
        for mid, score in self.vindex.search(query, top_k=top_k):
            e = self.get(mid)
            if e:
                e.mark_recalled()  # 艾宾浩斯：命中即强化
                results.append(RetrievedMemory(entry=e, score=score, route="vector"))
        # 2) 关键词直查兜底（低级但精确——参数名直给时最稳）
        for row in self.conn.execute(
                "SELECT * FROM facts WHERE content LIKE ?", (f"%{query}%",)).fetchall():
            e = self._row_to_entry(row)
            if not any(r.entry.id == e.id for r in results):
                e.mark_recalled()
                results.append(RetrievedMemory(entry=e, score=1.0, route="sql"))
        results.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(results[:top_k]):
            r.rank = i + 1
        return results[:top_k]

    def search_attrs(self, attrs: dict, top_k: int = 5) -> List[RetrievedMemory]:
        """属性精确过滤（参数级召回——ChatDB 符号查询的 MVP 形态）。

        NL→SQL 的落地路径：LLM 把"红方 T-90 多快"解析为 attrs 过滤条件，
        再调本方法（后续接真模型时在 retrieval 层做意图解析）。
        """
        hits: List[RetrievedMemory] = []
        for row in self.conn.execute("SELECT * FROM facts").fetchall():
            e = self._row_to_entry(row)
            if all(e.metadata.get(k) == v for k, v in attrs.items()):
                e.mark_recalled()
                hits.append(RetrievedMemory(entry=e, score=1.0, route="sql"))
        return hits[:top_k]
