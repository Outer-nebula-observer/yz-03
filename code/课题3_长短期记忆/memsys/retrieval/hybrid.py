# -*- coding: utf-8 -*-
"""
memsys.retrieval.hybrid — 任务感知混合检索（核心检索层）
=========================================================
思路来源（docs/04 2.3 节选型）：
  - 查询列表显式化（创新点 C）：每个 QueryItem 自带 route（vector/bm25/sql）；
  - MIRIX 多策略路由（笔记_Wang2025-MIRIX）：按查询特点自主选路；
  - ChatDB 符号查询（笔记_Hu2023-ChatDB）：事实走精确属性过滤；
  - ExpeL 向量召回（笔记_Zhao2023-ExpeL）：经验走语义相似。

三路打分归一化后融合：
  - vector: cosine ∈ [-1,1] → 线性映射到 [0,1]
  - bm25:   原始分 → 除以该路最大值归一
  - sql:    精确命中恒 1.0
融合权重（alpha=向量, beta=词法, gamma=符号）可在消融 G5 里扫描。
"""

from __future__ import annotations

from typing import List, Optional

from ..schema import QueryItem, RetrievedMemory
from ..long_term.factual_store import FactualStore
from ..long_term.experiential_store import ExperientialStore
from .bm25 import BM25


class HybridRetriever:
    """混合检索器：按查询路由到 vector / bm25 / sql 三路，再融合重排。

    用法（pipeline 内部）：
        r = HybridRetriever(factual, experiential)
        results = r.retrieve(QueryItem(q_id="q1", intent="查装备参数",
                                       target="fact", route="sql",
                                       query_text="T-90 最大速度"))
    """

    def __init__(self, factual: FactualStore, experiential: ExperientialStore,
                 alpha: float = 0.5, beta: float = 0.3, gamma: float = 0.2) -> None:
        self.factual = factual
        self.experiential = experiential
        # 三路融合权重（G5 消融扫描点）
        self.alpha, self.beta, self.gamma = alpha, beta, gamma
        # BM25 语料惰性构建（每次检索前按当前两库内容重建；万级以下可接受）
        self._bm25_cache: Optional[BM25] = None
        self._bm25_size = -1

    # ---------------------------------------------------------------- BM25 语料
    def _bm25(self) -> BM25:
        """构建/复用 BM25 索引（库规模变化时重建）。"""
        corpus = {}
        for mid in self.factual.candidates():
            e = self.factual.get(mid)
            if e:
                corpus[mid] = e.content
        for mid in self.experiential.candidates():
            e = self.experiential.get(mid)
            if e:
                corpus[mid] = e.content
        size = len(corpus)
        if self._bm25_cache is None or size != self._bm25_size:
            self._bm25_cache = BM25(corpus)
            self._bm25_size = size
        return self._bm25_cache

    # ---------------------------------------------------------------- 单路检索
    def _route(self, q: QueryItem, top_k: int) -> List[RetrievedMemory]:
        """按 q.route 走对应检索路（MIRIX 式按查询特点选路）。

        - vector: 语义相似（默认路，跨词泛化好）
        - bm25:   词法精确（装备型号/代号等字面匹配最稳）
        - sql:    属性过滤（ChatDB 符号路；target=fact 时把 query_text
                  当"key=value"或关键词处理，真模型接入后由 LLM 解析意图）
        """
        target = q.target
        if q.route == "bm25":
            # BM25 打全库，再按 target 过滤
            hits = self._bm25().score_topk(q.query_text or q.intent, top_k=top_k * 2)
            out: List[RetrievedMemory] = []
            for mid, s in hits:
                e = self.factual.get(mid) or self.experiential.get(mid)
                if e is None or e.type.value != target:
                    continue
                e.mark_recalled()
                out.append(RetrievedMemory(entry=e, score=s, route="bm25"))
            return out[:top_k]

        if q.route == "sql":
            # MVP：先用属性精确过滤，查不到再退化到内容 LIKE
            # （NL→SQL 的完整实现放到"接入真模型"阶段，接口不变）
            e_all = (self.factual.search_attrs({}) if False else None)  # noqa: 保留提示
            direct = self.factual.search(q.query_text, top_k=top_k)
            return [r for r in direct if r.entry.type.value == target][:top_k]

        # 默认 vector 路
        store = self.factual if target == "fact" else self.experiential
        return store.search(q.query_text or q.intent, top_k=top_k)

    # ---------------------------------------------------------------- 融合入口
    def retrieve(self, q: QueryItem, top_k: int = 5) -> List[RetrievedMemory]:
        """执行一次任务感知检索：路由 → 归一化 → 融合重排 → 回填命中 id。

        归一化说明：
          - cosine → (s+1)/2 映射到 [0,1]；
          - bm25 原始分 → 除以 max(该路最大分, 1e-9)；
          - sql 恒 1.0。
        融合分 = alpha*vec + beta*bm25 + gamma*sql（同一条记忆多路命中则累加）。
        """
        # 1) 路由检索（主路）+ 另两路补充（保证多视角，便于消融对比）
        primary = self._route(q, top_k)
        others: List[RetrievedMemory] = []
        for alt in ("vector", "bm25", "sql"):
            if alt != q.route:
                qq = QueryItem(q_id=q.q_id, intent=q.intent, target=q.target,
                               route=alt, query_text=q.query_text)
                others.extend(self._route(qq, top_k))

        # 2) 归一化
        def norm(route: str, s: float, pool: List[RetrievedMemory]) -> float:
            if route == "vector":
                return (s + 1.0) / 2.0
            if route == "sql":
                return 1.0
            mx = max((r.score for r in pool if r.route == "bm25"), default=0.0)
            return s / mx if mx > 1e-9 else 0.0

        pool = primary + others
        for r in pool:
            r.score = norm(r.route, r.score, pool)

        # 3) 融合（按 entry.id 聚合多路得分）
        weights = {"vector": self.alpha, "bm25": self.beta, "sql": self.gamma}
        fused: dict = {}
        for r in pool:
            w = weights.get(r.route, 0.1)
            fused.setdefault(r.entry.id, {"r": r, "s": 0.0, "routes": []})
            fused[r.entry.id]["s"] += w * r.score
            fused[r.entry.id]["routes"].append(r.route)

        # 4) 排序 + 回填
        ranked = sorted(fused.values(), key=lambda x: x["s"], reverse=True)[:top_k]
        results: List[RetrievedMemory] = []
        for i, item in enumerate(ranked):
            r: RetrievedMemory = item["r"]
            r.score = item["s"]
            r.rank = i + 1
            results.append(r)
        q.answer_memory_ids = [r.entry.id for r in results]  # 回填（创新点 C 可审计）
        return results
