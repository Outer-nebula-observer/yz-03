# -*- coding: utf-8 -*-
"""eval 子包：检索指标 + G0–G5 消融跑批。

注意：不在此处 import .ablation（避免 `python -m eval.ablation` 的
runpy "found in sys.modules" 告警）；需要时显式 `from eval.ablation import run_all`。
"""

from .metrics import (hit_rate_at_k, recall_at_k, reciprocal_rank,
                      ndcg_at_k, evaluate_retrieval)

__all__ = [
    "hit_rate_at_k", "recall_at_k", "reciprocal_rank", "ndcg_at_k",
    "evaluate_retrieval",
]
