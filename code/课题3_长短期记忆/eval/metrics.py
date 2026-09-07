# -*- coding: utf-8 -*-
"""
eval.metrics — 检索质量指标（docs/03 第 20 节 / docs/04 5.1 节）
=================================================================
全部零依赖纯 Python 实现，输入输出可 JSON 序列化（方便回放对比）。

指标：
  hit_rate@k    命中率（top-k 里是否含任一 gold）
  recall@k      召回率（top-k 覆盖 gold 的比例）
  mrr           平均倒数排名（第一个 gold 的位置）
  ndcg@k        归一化折损累计增益（位置越靠前贡献越大）
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List


def hit_rate_at_k(ranked_ids: List[str], gold_ids: Iterable[str], k: int) -> float:
    """top-k 命中率：命中任一 gold 记 1，否则 0。"""
    gold = set(gold_ids)
    topk = ranked_ids[:k]
    return 1.0 if any(i in gold for i in topk) else 0.0


def recall_at_k(ranked_ids: List[str], gold_ids: Iterable[str], k: int) -> float:
    """top-k 召回率：|topk ∩ gold| / |gold|（gold 空时返回 0）。"""
    gold = set(gold_ids)
    if not gold:
        return 0.0
    topk = set(ranked_ids[:k])
    return len(topk & gold) / len(gold)


def reciprocal_rank(ranked_ids: List[str], gold_ids: Iterable[str]) -> float:
    """RR：第一个 gold 的排名倒数（未命中=0）。"""
    gold = set(gold_ids)
    for i, mid in enumerate(ranked_ids, start=1):
        if mid in gold:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked_ids: List[str], gold_ids: Iterable[str], k: int) -> float:
    """NDCG@k： relevance ∈ {0,1}（gold=1），DCG/IDCG 归一。"""
    gold = set(gold_ids)
    dcg = 0.0
    for i, mid in enumerate(ranked_ids[:k], start=1):
        if mid in gold:
            dcg += 1.0 / math.log2(i + 1)
    n_rel = min(len(gold), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, n_rel + 1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_retrieval(ranked_ids: List[str], gold_ids: Iterable[str],
                       ks=(1, 3, 5)) -> Dict[str, float]:
    """一次性算齐四类指标（评估脚本/消融统一入口）。"""
    gold = list(gold_ids)
    out: Dict[str, float] = {"mrr": reciprocal_rank(ranked_ids, gold)}
    for k in ks:
        out[f"hit@{k}"] = hit_rate_at_k(ranked_ids, gold, k)
        out[f"recall@{k}"] = recall_at_k(ranked_ids, gold, k)
        out[f"ndcg@{k}"] = ndcg_at_k(ranked_ids, gold, k)
    return {k: round(v, 4) for k, v in out.items()}
