# -*- coding: utf-8 -*-
"""
eval.stats — 统计推断工具（零依赖：均值/置信区间/置换检验/随机基线）
======================================================================
评审 §3.5 的落地：消融数字必须有"随机基线对照 + 置信区间 + 显著性检验"，
否则全是 1.0 的指标无判别力（旧集 n=6、top-5 下随机 hit@5 高达 0.83）。

工具：
  mean/std                      基础统计
  bootstrap_ci                  均值的 bootstrap 95% 置信区间
  paired_permutation_test       配对置换检验（两组逐用例指标的显著性）
  random_hit_at_k               随机排序基线（解析式，精确）
  random_recall_at_k            同上
  random_mrr                    蒙特卡洛（多 gold 的 MRR 无简洁解析式）
"""

from __future__ import annotations

import math
import random
from typing import List, Sequence, Tuple


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def std(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def bootstrap_ci(xs: Sequence[float], n_boot: int = 10000,
                 alpha: float = 0.05, seed: int = 42) -> Tuple[float, float]:
    """均值的 bootstrap 置信区间（百分位法）。"""
    if not xs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(xs)
    stats = []
    for _ in range(n_boot):
        sample = [xs[rng.randrange(n)] for _ in range(n)]
        stats.append(mean(sample))
    stats.sort()
    lo = stats[int((alpha / 2) * n_boot)]
    hi = stats[min(int((1 - alpha / 2) * n_boot), n_boot - 1)]
    return (round(lo, 4), round(hi, 4))


def paired_permutation_test(x: Sequence[float], y: Sequence[float],
                            n_perm: int = 10000,
                            seed: int = 42) -> float:
    """配对置换检验：H0 = 两组逐用例指标同分布（均值差为 0）。

    返回双侧 p 值。x/y 必须等长（逐用例配对——同一用例在两组配置下的
    hit/recall 等）。n<5 时结果仅供参考（检验功效不足，调用方应注明）。
    """
    if len(x) != len(y) or not x:
        return float("nan")
    diff = [a - b for a, b in zip(x, y)]
    obs = abs(mean(diff))
    if obs == 0:
        return 1.0
    rng = random.Random(seed)
    n = len(diff)
    count = 0
    for _ in range(n_perm):
        flipped = [d if rng.random() < 0.5 else -d for d in diff]
        if abs(mean(flipped)) >= obs - 1e-12:
            count += 1
    return round(count / n_perm, 4)


def random_hit_at_k(n_items: int, k: int, n_gold: int) -> float:
    """随机排序下 hit@k 的期望（解析式，精确）。

    = 1 - C(n-g, k) / C(n, k)（top-k 至少含一个 gold 的概率）
    """
    if n_gold <= 0 or n_items <= 0:
        return 0.0
    if n_gold >= n_items:
        return 1.0
    k_eff = min(k, n_items)
    return 1.0 - (math.comb(n_items - n_gold, k_eff)
                  / math.comb(n_items, k_eff))


def random_recall_at_k(n_items: int, k: int, n_gold: int) -> float:
    """随机排序下 recall@k 的期望（超几何均值，精确）：min(k,n)/n。"""
    if n_gold <= 0 or n_items <= 0:
        return 0.0
    return min(k, n_items) / n_items


def random_mrr(n_items: int, n_gold: int = 1, n_trials: int = 20000,
               seed: int = 42) -> float:
    """随机排序下 MRR 的期望（蒙特卡洛；单 gold 有解析式 H_n/n）。"""
    if n_gold <= 0 or n_items <= 0:
        return 0.0
    if n_gold == 1:
        return round(sum(1.0 / i for i in range(1, n_items + 1)) / n_items, 4)
    rng = random.Random(seed)
    ids = list(range(n_items))
    total = 0.0
    for _ in range(n_trials):
        rng.shuffle(ids)
        rr = 0.0
        for pos, i in enumerate(ids, start=1):
            if i < n_gold:
                rr = 1.0 / pos
                break
        total += rr
    return round(total / n_trials, 4)
