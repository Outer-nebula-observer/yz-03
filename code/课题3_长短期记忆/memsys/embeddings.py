# -*- coding: utf-8 -*-
"""
memsys.embeddings — 向量化抽象
==============================
目标与 llm.py 相同：离线可跑（MockEmbedding），随时可换真模型（BGE/OpenAI）。

MockEmbedding 采用**哈希词袋向量**：
  - 分词（ASCII 连续串 + 中文字符逐字）→ 词 hash 到固定维度桶 → L2 归一化；
  - 优点：确定性、零依赖、语义上"词重叠≈相似"，足够跑通检索链路与消融；
  - 局限：无真正语义泛化（同义不同词不相似）——换真模型只需实现 embed() 接口。

向量存储：MVP 用内存 dict（id→vector），接口留出 save/load 位置；
后续接 FAISS 时替换 MemoryVectorIndex 即可（ExpeL 用 Faiss，见其 memory/episode.py）。
"""

from __future__ import annotations

import hashlib
import math
from typing import Dict, List, Protocol, Sequence, Tuple


class EmbeddingModel(Protocol):
    """向量化模型协议。"""

    dim: int

    def embed(self, text: str) -> List[float]:
        """把文本编码为单位向量（L2 归一化，方便直接做内积=余弦）。"""
        ...


# ---------------------------------------------------------------- 分词（与 SDK template 一致）
def tokenize(text: str) -> List[str]:
    """轻量分词：ASCII 字母数字下划线连续串 + 中文逐字。

    与老师 SDK template/engine.py 的 _tokenize 保持一致（方便复用/对照）。
    """
    tokens: List[str] = []
    buf = ""
    for ch in text.lower():
        if ch.isascii() and (ch.isalnum() or ch == "_"):
            buf += ch
        else:
            if buf:
                tokens.append(buf)
                buf = ""
            if 0x4E00 <= ord(ch) <= 0x9FFF:  # CJK 基本区
                tokens.append(ch)
    if buf:
        tokens.append(buf)
    return tokens


class MockEmbedding:
    """哈希词袋向量（离线确定性 embedding）。

    实现：每个 token hash 到 [0, dim) 的桶并 +1，最后 L2 归一化。
    分桶用 sha1 前几字节，保证跨进程稳定（不要用内置 hash——有随机种子！）。
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for tok in tokenize(text):
            # sha1 前 4 字节 → 桶下标（跨进程确定性）
            h = hashlib.sha1(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self.dim
            # 用 token 长度做加权：长词信息量更大（简单启发式）
            vec[idx] += 1.0 + 0.1 * min(len(tok), 8)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class OpenAIEmbedding:
    """真模型骨架（OpenAI 兼容 /embeddings 接口）。默认不启用。

    接智戎或本地 BGE 网关时实现此类即可，业务代码零改动。
    """

    def __init__(self, base_url: str, api_key: str, model: str, dim: int = 1024) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        import requests  # 延迟导入
        resp = requests.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """余弦相似度（输入已是单位向量时可退化为内积，这里保守做完整计算）。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


class MemoryVectorIndex:
    """内存向量索引（id → 向量），带 CRUD。

    对应 ExpeL 的向量库角色（其用 Faiss；MVP 用 dict，规模到万级再换）。
    save/load 预留：接 FAISS 时替换内部结构即可。
    """

    def __init__(self, model: EmbeddingModel) -> None:
        self.model = model
        self._vectors: Dict[str, List[float]] = {}

    # ---------- CRUD ----------
    def add(self, key: str, text: str) -> List[float]:
        """编码并登记一条向量。"""
        vec = self.model.embed(text)
        self._vectors[key] = vec
        return vec

    def remove(self, key: str) -> None:
        self._vectors.pop(key, None)

    def __contains__(self, key: str) -> bool:
        return key in self._vectors

    def __len__(self) -> int:
        return len(self._vectors)

    # ---------- 检索 ----------
    def search(self, query: str, top_k: int = 5,
               candidates: "Sequence[str] | None" = None) -> List[Tuple[str, float]]:
        """按余弦相似度检索 top-k。

        candidates: 限定候选 id 集合（如只在'经验'类型里检索），None=全部。
        返回 [(id, cosine_score)] 按分降序。
        """
        q = self.model.embed(query)
        keys = list(self._vectors) if candidates is None else [k for k in candidates if k in self._vectors]
        scored = [(k, cosine(q, self._vectors[k])) for k in keys]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
