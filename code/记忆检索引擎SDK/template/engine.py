"""
倒排索引示例引擎 —— 第三方开发起点（契约 A 最小实现）。

用法：
  1. 复制整个 _template/ 目录为你的引擎目录（如 my_search_engine/）
  2. 重命名类名与 name/engine_label/engine_color
  3. 实现 search()（必选）及可选的 ingest/generate
  4. 保持 __init__.py 导出 engine_plugin（相对导入，复制改名无需改动）
  5. 重启服务 → 自动注册 → 前后端自动出现
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Dict, List

from server.engines.memory_plugin_api import EngineCapabilities, MemoryEnginePlugin


class InvertedIndexEngine(MemoryEnginePlugin):
    """内存倒排索引关键词检索示例引擎。"""

    name = "inverted_index"
    engine_label = "倒排索引"
    engine_color = "#16a085"
    version = "1.0.0"
    description = "内存倒排索引关键词检索示例引擎"
    contract_version = "1.0.0"

    def __init__(self) -> None:
        self._docs: Dict[str, str] = {}
        self._inverted: Dict[str, set] = defaultdict(set)
        self._lock = asyncio.Lock()

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            supports_ingest=True,
            supports_delete=True,
            supports_generate=False,   # 本示例不支持生成，SSE 会发 engine_done(unsupported)
            supports_stream=False,
            supported_suffixes=[".txt"],
            ingest_granularity="file",
            storage_backend="in-memory",
        )

    async def check_availability(self) -> bool:
        return True

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # 简化分词：ASCII 字母数字下划线连续串 + 中文字符逐个（用码点区间，避免正则转义）
        tokens: List[str] = []
        buf = ""
        for ch in text.lower():
            if ch.isascii() and (ch.isalnum() or ch == "_"):
                buf += ch
            else:
                if buf:
                    tokens.append(buf)
                    buf = ""
                if 0x4E00 <= ord(ch) <= 0x9FFF:
                    tokens.append(ch)
        if buf:
            tokens.append(buf)
        return tokens

    async def search(self, query: str, top_k: int = 10, timeout: float = 30.0) -> List[dict]:
        q = set(self._tokenize(query))
        if not q:
            return []
        scored = []
        for doc_id, doc in self._docs.items():
            hit = len(q & set(self._tokenize(doc)))
            if hit == 0:
                continue
            scored.append((hit / len(q), doc_id, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "content": doc[:500],
                "score": round(s, 4),
                "source_file": doc_id,
                "chunk_id": doc_id,
                "engine": self.name,
                "metadata": {},
            }
            for s, doc_id, doc in scored[:top_k]
        ]

    async def ingest_file(self, rel_path: str) -> Dict[str, Any]:
        # rel_path 相对检索数据根；异步读取避免阻塞事件循环
        from server.config import knowledge_base_dir
        path = knowledge_base_dir() / rel_path
        content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        async with self._lock:
            self._docs[rel_path] = content
            for term in set(self._tokenize(content)):
                self._inverted[term].add(rel_path)
        return {"indexed": 1}

    async def remove_file(self, rel_path: str) -> Dict[str, Any]:
        async with self._lock:
            self._docs.pop(rel_path, None)
            for term in self._inverted:
                self._inverted[term].discard(rel_path)
        return {"removed": 1}

    async def list_data(self) -> Dict[str, Any]:
        return {"directories": [], "files": list(self._docs.keys())}


engine_plugin = InvertedIndexEngine()
