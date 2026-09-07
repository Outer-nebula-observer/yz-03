# -*- coding: utf-8 -*-
"""
memsys.retrieval.bm25 — 轻量 BM25 实现（零依赖）
=================================================
用途：混合检索的"词法路"（MIRIX 的 bm25_match 思路，见 笔记_Wang2025-MIRIX）。
     向量召回语义、BM25 召回字面——两者互补，缺一不可。

实现：标准 Okapi BM25（k1=1.5, b=0.75），语料为 {key: text}。
规模假设：万级以下条目全量打分足够快（>10 万条再换 rank_bm25/倒排优化）。
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Tuple

from ..embeddings import tokenize  # 复用同一分词器，保证向量/BM25 口径一致


class BM25:
    """Okapi BM25 打分器。

    用法：
        bm25 = BM25({"m1": "红方 T-90 坦克 最大速度 60km/h", ...})
        bm25.score_topk("T-90 速度", top_k=5)  # → [("m1", 3.42), ...]
    """

    def __init__(self, corpus: Dict[str, str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_len: Dict[str, int] = {}
        self.doc_tf: Dict[str, Counter] = {}
        self.df: Counter = Counter()      # 词 → 出现文档数
        for key, text in corpus.items():
            toks = tokenize(text)
            self.doc_len[key] = len(toks)
            tf = Counter(toks)
            self.doc_tf[key] = tf
            for term in tf:
                self.df[term] += 1
        self.n_docs = max(len(corpus), 1)
        self.avg_len = (sum(self.doc_len.values()) / self.n_docs) or 1.0

    def _idf(self, term: str) -> float:
        """标准 BM25 IDF（带下界防负）。"""
        df = self.df.get(term, 0)
        return math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def score(self, key: str, query: str) -> float:
        """单文档打分：Σ IDF(q) * tf*(k1+1) / (tf + k1*(1-b+b*len/avg))。"""
        tf = self.doc_tf.get(key)
        if not tf:
            return 0.0
        s = 0.0
        for q in tokenize(query):
            f = tf.get(q, 0)
            if f == 0:
                continue
            denom = f + self.k1 * (1 - self.b + self.b * self.doc_len[key] / self.avg_len)
            s += self._idf(q) * f * (self.k1 + 1) / denom
        return s

    def score_topk(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """全量打分取 top-k（小语料下足够快）。"""
        scored = [(k, self.score(k, query)) for k in self.doc_tf]
        scored = [(k, s) for k, s in scored if s > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
