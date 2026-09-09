# -*- coding: utf-8 -*-
"""
memsys.retrieval.hybrid — 任务感知混合检索（核心检索层）
=========================================================
思路来源（docs/04 2.3 节选型）：
  - 查询列表显式化（创新点 C）：每个 QueryItem 自带 route（vector/bm25/sql）；
  - MIRIX 多策略检索 + ChatDB 符号查询（sql 路 = **属性精确过滤**）；
  - ExpeL 向量召回（经验走语义相似）。

【评审修复·两种检索模式】（此前"按查询特点选路"名不副实——无论 route
填什么，三路全部执行后融合，route 只是统计标签，G5 消融因此无效）：
  mode="hybrid"（默认）: 三路并行检索 → 归一化 → 加权融合重排
  mode="single"       : **只执行 q.route 指定的那一路**，不做融合
                        （供消融 G5 真正对比单路 vs 混合的贡献）

三路打分归一化：
  - vector: cosine ∈ [-1,1] → 线性映射到 [0,1]（纯向量路，不含 LIKE 兜底）
  - bm25:   原始分 → 除以该路最大值归一
  - sql:    属性精确命中恒 1.0（q.attrs 非空走 search_attrs 参数级过滤；
            为空退化到 LIKE 子串兜底——NL→attrs 解析层留待真模型）
"""
from __future__ import annotations

import time
from typing import List, Optional

from ..schema import QueryItem, RetrievedMemory
from ..long_term.factual_store import FactualStore
from ..long_term.experiential_store import ExperientialStore
from .bm25 import BM25


class HybridRetriever:
    """混合检索器：hybrid 三路融合 / single 单路执行（消融用）。

    用法（pipeline 内部）：
        r = HybridRetriever(factual, experiential)
        results = r.retrieve(QueryItem(q_id="q1", intent="查装备参数",
                                       target="fact", route="sql",
                                       attrs={"装备": "T-90"}))
        # 消融 G5：单路执行
        results = r.retrieve(q, top_k=5, mode="single")
    """

    def __init__(self, factual: FactualStore, experiential: ExperientialStore,
                 alpha: float = 0.5, beta: float = 0.3, gamma: float = 0.2,
                 min_score: float = 0.16, stage_bonus: float = 0.15,
                 time_decay_weight: float = 0.0) -> None:
        self.factual = factual
        self.experiential = experiential
        # 三路融合权重（G5 消融扫描点）
        self.alpha, self.beta, self.gamma = alpha, beta, gamma
        # min_score 阈值（ExpeL/Mem-α/MemP 共有技巧）：低分噪声不返回。
        # 【标定协议】量纲 = 融合分（归一化加权和，范围 [0, α+β+γ]=1；
        # vector 路归一化后即余弦本身）。默认 0.16 是在 Mock 测试集
        # （eval/testset.py，44 条）上按"负例 top1 分数最大值"标定的：
        #   正例 top1 分布 [0.14, 0.82]，p25=0.30；负例 top1 ≤ 0.159
        # → 0.16 为零噪声点（牺牲 1 条最弱正例）。
        # **换 embedding 后必须重新标定**（E 噪声研究即标定协议，
        # 见 eval/ablation.py）——这不是可跨模型复用的常数。
        self.min_score = min_score
        # 阶段亲和加分：记忆 metadata.stage 与查询 stage 一致时融合分
        # 加这么多（G6 消融扫描点，stage_bonus=0 即关闭）。
        self.stage_bonus = stage_bonus
        # 【创新点 F 钩子】时间敏感检索：>0 时融合分乘以
        # (1 - w*(1-retention))——久未召回的记忆轻微降权。
        # 默认 0.0 关闭（保证既有结果可复现；消融可开）。
        self.time_decay_weight = time_decay_weight
        # BM25 语料惰性构建（语料版本号失效：add/update/remove 都会 +1）
        self._bm25_cache: Optional[BM25] = None
        self._bm25_key: tuple = (-1, -1, -1)

    # ---------------------------------------------------------------- BM25 语料
    def _bm25(self) -> BM25:
        """构建/复用 BM25 索引（语料 (size, 两库 version) 变化时重建）。"""
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
        key = (size, getattr(self.factual, "version", 0),
               getattr(self.experiential, "version", 0))
        if self._bm25_cache is None or key != self._bm25_key:
            self._bm25_cache = BM25(corpus)
            self._bm25_key = key
        return self._bm25_cache

    # ---------------------------------------------------------------- 单路检索
    def _route(self, q: QueryItem, top_k: int) -> List[RetrievedMemory]:
        """按 q.route 走对应检索路（single 模式即本方法 + 归一化）。

        - vector: 纯向量相似（跨词泛化好；事实库走 search_vector，
                  不含 LIKE 兜底——保证"vector 单路"是纯语义路）
        - bm25:   词法精确（装备型号/代号等字面匹配最稳）
        - sql:    属性精确过滤（q.attrs 非空 → search_attrs 参数级召回，
                  ChatDB 符号路；为空退化 LIKE 子串兜底）
        """
        target = q.target
        if q.route == "bm25":
            hits = self._bm25().score_topk(q.query_text or q.intent, top_k=top_k * 2)
            out: List[RetrievedMemory] = []
            for mid, s in hits:
                e = self.factual.get(mid) or self.experiential.get(mid)
                if e is None or e.type.value != target:
                    continue
                out.append(RetrievedMemory(entry=e, score=s, route="bm25"))
            return out[:top_k]

        if q.route == "sql":
            # 首选：属性精确过滤（参数级召回——"sql 路"的本义）
            if getattr(q, "attrs", None):
                direct = self.factual.search_attrs(q.attrs, top_k=top_k)
                return [r for r in direct if r.entry.type.value == target][:top_k]
            # 兜底：LIKE 子串（无 attrs 时；空文本必须挡住——'%%' 全表命中）
            if not (q.query_text or "").strip():
                return []
            direct = self.factual.search_content_like(q.query_text, top_k=top_k)
            return [r for r in direct if r.entry.type.value == target][:top_k]

        # 默认 vector 路：纯向量（事实库）/ 向量+重要性加权（经验库）
        store = self.factual if target == "fact" else self.experiential
        if isinstance(store, FactualStore):
            return store.search_vector(q.query_text or q.intent, top_k=top_k)
        return store.search(q.query_text or q.intent, top_k=top_k)

    # ---------------------------------------------------------------- 归一化
    def _norm(self, route: str, s: float, pool: List[RetrievedMemory],
              query: str) -> float:
        if route == "vector":
            # 【评审修复·归一化口径】原 (cos+1)/2 把零相关映射到 0.5——
            # 下半量程浪费、上半量程压缩，导致 min_score 的语义失真
            # （阶段模板查询 cos=0.29 → 0.65 →×0.5=0.32 恰低于 0.35 被滤；
            # 而负例 cos=0.1 → 0.55 又能过阈值）。改为标准裁剪余弦：
            # cos 直接作为相关度（负值截 0），阈值语义 = "余弦下限"。
            return max(0.0, min(s, 1.0))
        if route == "sql":
            return 1.0
        # bm25：用"查询自匹配得分"作归一化上界（评审修复——原"池内最大值"
        # 归一会把单字巧合放大到 1.0，负例噪声返回率 58%）
        ceiling = self._bm25().self_score(query)
        return min(s / ceiling, 1.0) if ceiling > 1e-9 else 0.0

    # ---------------------------------------------------------------- 融合入口
    def retrieve(self, q: QueryItem, top_k: int = 5,
                 mode: str = "hybrid") -> List[RetrievedMemory]:
        """执行一次任务感知检索。

        mode="hybrid"（默认）: 主路 + 另两路补充 → 归一化 → 加权融合重排
        mode="single"       : 只执行 q.route 一路 → 归一化 → 排序
                              （无跨路融合——G5 消融的单路对照）
        """
        if mode not in ("hybrid", "single"):
            raise ValueError(f"未知检索模式: {mode}（hybrid/single）")
        primary = self._route(q, top_k)
        others: List[RetrievedMemory] = []
        if mode == "hybrid":
            for alt in ("vector", "bm25", "sql"):
                if alt != q.route:
                    qq = QueryItem(q_id=q.q_id, intent=q.intent, target=q.target,
                                   route=alt, query_text=q.query_text,
                                   attrs=q.attrs, stage=q.stage)
                    others.extend(self._route(qq, top_k))

        pool = primary + others
        for r in pool:
            r.score = self._norm(r.route, r.score, pool,
                                 q.query_text or q.intent)

        # 融合（按 entry.id 聚合多路得分）
        # 【评审修复·单路口径】single 模式用归一化分本身（权重=1）——否则
        # 单路得分 = w×score（如 sql 路 0.2×1.0=0.2）恒低于 min_score=0.35，
        # "sql 单路"会恒空、消融 G5 失真。单路模式测"该路自身质量"，
        # 应与融合权重解耦（hybrid 模式的阈值-权重交互另见下方注释）。
        if mode == "single":
            weights = {"vector": 1.0, "bm25": 1.0, "sql": 1.0}
        else:
            weights = {"vector": self.alpha, "bm25": self.beta, "sql": self.gamma}
        fused: dict = {}
        for r in pool:
            w = weights.get(r.route, 0.1)
            fused.setdefault(r.entry.id, {"r": r, "s": 0.0, "routes": []})
            fused[r.entry.id]["s"] += w * r.score
            fused[r.entry.id]["routes"].append(r.route)

        now = time.time()
        # 阶段亲和加分（min_score 过滤之前——对口记忆应能借亲和分过阈值）
        if getattr(q, "stage", ""):
            for item in fused.values():
                if item["r"].entry.metadata.get("stage") == q.stage:
                    item["s"] += self.stage_bonus
        # 时间敏感检索（创新点 F，默认关闭）
        if self.time_decay_weight > 0:
            w = self.time_decay_weight
            for item in fused.values():
                item["s"] *= 1.0 - w * (1.0 - item["r"].entry.retention(now))

        # 排序 + 阈值过滤 + top_k + 统一命中强化（只对最终结果执行一次）
        # 【设计决策·阈值-权重交互】融合分是加权和：某路权重 w < min_score 时，
        # 仅靠该路命中的记忆永远过不了阈值（如 γ=0.2 < 0.35 时"纯 sql 命中"
        # 必被滤掉——参数级精确召回的主张会被阈值破坏）。
        # 处理：**属性精确命中（attrs 显式条件）是构造性相关**——查询方明确
        # 指定了过滤条件，命中即相关，不参与相似度阈值（符号路的语义特权）。
        exact_ids = set()
        if getattr(q, "attrs", None):
            for item in fused.values():
                if "sql" in item["routes"]:
                    exact_ids.add(item["r"].entry.id)
        ranked = sorted(fused.values(), key=lambda x: x["s"], reverse=True)
        ranked = [item for item in ranked
                  if item["s"] >= self.min_score
                  or item["r"].entry.id in exact_ids][:top_k]
        results: List[RetrievedMemory] = []
        for i, item in enumerate(ranked):
            r: RetrievedMemory = item["r"]
            r.score = item["s"]
            r.rank = i + 1
            r.entry.mark_recalled()          # S+1、t 重置（间隔效应）
            store = (self.factual if r.entry.type.value == "fact"
                     else self.experiential)
            if hasattr(store, "persist_recall"):
                store.persist_recall(r.entry)
            results.append(r)
        q.answer_memory_ids = [r.entry.id for r in results]  # 回填（创新点 C）
        return results
