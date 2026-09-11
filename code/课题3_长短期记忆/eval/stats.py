# -*- coding: utf-8 -*-
"""
eval.stats — 统计推断工具（零依赖：均值/置信区间/置换检验/随机基线）
======================================================================
为什么消融必须有这套东西？（评审 §3.5 的落地）

  早期消融只输出均值（"hit@5=1.0"），问题有二：
    1. **没有随机基线**——不知道这个数字是"好"还是"运气"。
       比如旧种子集 n=6、top-5 时，闭眼随机排序 hit@5 也有 0.83，
       1.0 相对随机只高 0.17，几乎没有判别力；
    2. **没有不确定性/显著性**——G2 与 G3 差 0.3，到底是真差异
       还是三两个用例的偶然？需要置信区间 + 置换检验回答。

  因此本模块提供四个能力：
    mean/std         基础统计（确保两组的均值差可计算）
    bootstrap_ci     给均值一个 95% 置信区间（不依赖正态假设）
    paired_permutation_test  逐用例配对的显著性检验（零依赖）
    random_*         随机排序基线的解析期望（Monte Carlo 对照）

  设计原则：全程只用 math/random——不引 scipy/numpy，任何环境可跑。
"""

from __future__ import annotations

import math
import random
from typing import List, Sequence, Tuple


def mean(xs: Sequence[float]) -> float:
    """算术平均：\bar{x} = Σx / n。空序列返回 0（调用方避免除零）。"""
    return sum(xs) / len(xs) if xs else 0.0


def std(xs: Sequence[float]) -> float:
    """样本标准差（分母 n-1，无偏估计）。

    用途：配合均值输出"均值±标准差"；n 很小时（如 G6 只有 4 对）
    它本身波动很大——此时以 bootstrap CI 为主。
    """
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def bootstrap_ci(xs: Sequence[float], n_boot: int = 10000,
                 alpha: float = 0.05, seed: int = 42) -> Tuple[float, float]:
    """均值的 bootstrap 95% 置信区间（百分位法，无分布假设）。

    原理：把样本当作总体，反复**有放回抽样** n_boot 次，每次算一个
    bootstrap 均值；取这些均值分布的 [α/2, 1-α/2] 分位数作为 CI。
    优点：不假设数据正态（hit@5 是 0/1 二值，正态假设显然不成立）；
    缺点：样本量极小时（n<5）CI 很宽——这正好诚实地告诉我们
    "证据不足"。

    参数：n_boot 抽样次数（越大越稳，1 万次足够）；seed 固定保证可复现。
    """
    if not xs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(xs)
    stats = []
    for _ in range(n_boot):
        # 有放回抽样：每次从 n 个观测里抽 n 个（允许重复）
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

    为什么是"配对"？消融里 G2/G3 的指标来自**同一批用例**的逐条结果
    （同一个 c1 在 G2 和 G3 下各有一个 hit@5），天然配对——不能当
    两组独立样本处理，要用配对检验。

    原理：
      1. 计算每对差值 d_i = x_i - y_i，得到观测均值差 D；
      2. 在 H0 成立下，每个 d_i 的正负号概率各半。于是把差值随机
         翻转符号，得到"假如没有真差异"时的均值差分布；
      3. 看 |观测D| 落在该分布的什么位置 → 双侧 p 值。
    零依赖：完全由 random 实现，不依赖 scipy 的 permutation_test。

    注意：n<5 时最小 p 值有下限（如 n=4 最小 p=0.125），检验功效不足
    ——调用方要如实标注（消融 G6 就是如此，p=0.127 只能当方向证据）。
    """
    if len(x) != len(y) or not x:
        return float("nan")          # 长度不匹配或无数据：无法检验
    diff = [a - b for a, b in zip(x, y)]
    obs = abs(mean(diff))
    if obs == 0:
        return 1.0                   # 均值差为 0 → 显然不显著
    rng = random.Random(seed)
    n = len(diff)
    count = 0
    for _ in range(n_perm):
        # 每个差值以 1/2 概率翻号：H0（无方向）下的零分布
        flipped = [d if rng.random() < 0.5 else -d for d in diff]
        if abs(mean(flipped)) >= obs - 1e-12:
            count += 1
    return round(count / n_perm, 4)


def random_hit_at_k(n_items: int, k: int, n_gold: int) -> float:
    """随机排序下 hit@k 的**解析期望**（精确，非蒙特卡洛）。

    公式：P(top-k 至少含一个 gold)
         = 1 - C(n - g, k) / C(n, k)
    其中 C 是组合数。为什么给解析式？1) 精确无噪声；2) 快；
    3) 便于在任何报告里给"随机基线"列。

    例子：n=14（事实库种子数）、k=5、g=1 → 0.3571；n=6 旧种子 → 0.8333。
    """
    if n_gold <= 0 or n_items <= 0:
        return 0.0
    if n_gold >= n_items:
        return 1.0
    k_eff = min(k, n_items)
    return 1.0 - (math.comb(n_items - n_gold, k_eff)
                  / math.comb(n_items, k_eff))


def random_recall_at_k(n_items: int, k: int, n_gold: int) -> float:
    """随机排序下 recall@k 的期望（超几何均值，精确）：min(k,n)/n。

    推导：top-k 与 gold 的交集期望 = k·g/n（每个 gold 落入 top-k
    的概率都是 k/n），再除以 g 得 k/n。与 hit 不同，recall 是多
    gold 时的"平均覆盖比例"。
    """
    if n_gold <= 0 or n_items <= 0:
        return 0.0
    return min(k, n_items) / n_items


def random_mrr(n_items: int, n_gold: int = 1, n_trials: int = 20000,
               seed: int = 42) -> float:
    """随机排序下 MRR 的期望。

    单 gold 有解析式：E[RR] = H_n / n = (Σ_{i=1..n} 1/i) / n。
    多 gold 无简洁解析式 → 蒙特卡洛（可选 n_trials，seed 固定可复现）。
    Mock 消融库规模小，2 万次模拟 ≤ 几十毫秒，完全够用。
    """
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
        # 第一个 gold 出现的位置的倒数；ids 前 n_gold 个视为 gold
        for pos, i in enumerate(ids, start=1):
            if i < n_gold:
                rr = 1.0 / pos
                break
        total += rr
    return round(total / n_trials, 4)
