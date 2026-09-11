# -*- coding: utf-8 -*-
"""
eval.metrics — 检索质量指标（hit / recall / MRR / NDCG）
=================================================================
对应 docs/03 第 20 节 / docs/04 §5.1；消融 v2 与真模型验证的统一计量口径。

为什么需要这些指标？
  检索层的核心问题是：给定查询，系统排出来的 top-k 列表质量如何？
  四个指标从不同角度回答：
    - hit@k      ：是否至少有一个正确答案进了 top-k（召回"有没有"）
    - recall@k   ：正确答案被覆盖的比例（多 gold 时比 hit 更细）
    - MRR        ：第一个正确答案排多前（排序"有多快"命中）
    - NDCG@k     ：整个 top-k 的位置加权质量（排序"整体有多好"）

为什么全部零依赖纯 Python？
  课程环境不保证有 scikit/numpy；指标实现本身只有组合数与对数，
  Python 内建 math 足够——这也贯彻了 memsys"零第三方依赖"哲学。
  输入输出均可 JSON 序列化，方便消融回放与报告落盘。

口径约定（重要）：
  - gold_ids 使用"记忆条目 id"的集合/列表；ranked_ids 是检索返回的
    top-k 条目 id 列表（按排名升序，第一位是系统认为最相关的）。
  - 所有指标 ∈ [0,1]，越高越好；gold 为空时 recall=0（避免除零，
    同时语义是"没有正确答案可召回的查询记 0 分"——负例查询走
    noise 指标，不混入这里的均值）。
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List


def hit_rate_at_k(ranked_ids: List[str], gold_ids: Iterable[str], k: int) -> float:
    """hit@k：top-k 中**是否至少包含一个** gold。

    二值指标：命中任一 gold 记 1.0，否则 0.0。
    典型用途：报告"这个问题系统有没有找对"；对单 gold 检索，
    hit@k 与"随机排序基线"直接可比（见 stats.random_hit_at_k）。
    """
    gold = set(gold_ids)          # 转集合：O(1) 成员判断
    topk = ranked_ids[:k]          # 只取前 k 个
    return 1.0 if any(mid in gold for mid in topk) else 0.0


def recall_at_k(ranked_ids: List[str], gold_ids: Iterable[str], k: int) -> float:
    """recall@k：top-k 覆盖 gold 的**比例**（多 gold 时更有区分度）。

    公式：|top-k ∩ gold| / |gold|。
    注意：一条正确记忆算一次覆盖；若 gold 为空返回 0.0（防除零，
    且语义为"无可召回"——负例查询不应进正例均值）。
    """
    gold = set(gold_ids)
    if not gold:
        return 0.0
    topk = set(ranked_ids[:k])
    return len(topk & gold) / len(gold)


def reciprocal_rank(ranked_ids: List[str], gold_ids: Iterable[str]) -> float:
    """MRR 的单查询 RR：第一个 gold 的排名倒数。

    公式：1 / rank_of_first_gold；未命中返回 0。
    为什么用"倒数"？rank=1（榜首命中）得 1.0，rank=3 得 0.33——
    排序越靠前奖励越大，惩罚快速衰减。单 gold 情况最直观。
    """
    gold = set(gold_ids)
    for i, mid in enumerate(ranked_ids, start=1):
        if mid in gold:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked_ids: List[str], gold_ids: Iterable[str], k: int) -> float:
    """NDCG@k：归一化折损累计增益（位置越靠前贡献越大）。

    实现要点（relevance ∈ {0,1}）：
      DCG  = Σ_{i=1..k} rel_i / log2(i+1)     # 排名折损
      IDCG = 理想排序（gold 全在最前）下的 DCG  # 归一化分母
      NDCG = DCG / IDCG
    为什么比 hit/MRR 更全面？hit 只看"有没有"，MRR 只看"第一个"，
    NDCG 同时奖励"多个 gold 都被排得很靠前"。
    """
    gold = set(gold_ids)
    dcg = 0.0
    for i, mid in enumerate(ranked_ids[:k], start=1):
        if mid in gold:
            dcg += 1.0 / math.log2(i + 1)
    n_rel = min(len(gold), k)      # 理想情况下最多 k 个 gold 有贡献
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, n_rel + 1))
    return dcg / idcg if idcg > 0 else 0.0   # 防除零（gold 为空或 k=0）


def evaluate_retrieval(ranked_ids: List[str], gold_ids: Iterable[str],
                       ks=(3, 5)) -> Dict[str, float]:
    """一次性算齐四类指标（评估脚本/消融统一入口）。

    参数：
      ranked_ids  检索返回的条目 id 列表（排名升序）
      gold_ids    标注的正确答案 id 集合
      ks          需要报告哪些 k（默认 3/5；与消融 v2 口径一致）
    返回：
      {"mrr", "hit@3", "recall@3", "ndcg@3", "hit@5", ...}

    为什么默认 ks=(3,5) 而不是 1？
      1) 生成式检索往往不要求榜首精确，"前 3/前 5 命中"更贴近
         "把相关记忆送进上下文"的任务目标；
      2) 消融 v2 的随机基线对照就是按 g1e(3,5) 算的，口径统一。
    """
    gold = list(gold_ids)
    out: Dict[str, float] = {"mrr": reciprocal_rank(ranked_ids, gold)}
    for k in ks:
        out[f"hit@{k}"] = hit_rate_at_k(ranked_ids, gold, k)
        out[f"recall@{k}"] = recall_at_k(ranked_ids, gold, k)
        out[f"ndcg@{k}"] = ndcg_at_k(ranked_ids, gold, k)
    return {k: round(v, 4) for k, v in out.items()}   # 统一 4 位小数，方便对齐
