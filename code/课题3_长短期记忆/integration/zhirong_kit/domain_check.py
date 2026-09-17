# -*- coding: utf-8 -*-
"""
zhirong_kit.domain_check — 领域迁移巡检 + 阈值建议（P0）
==========================================================
目的：接入智戎真实数据后，快速检查“这套记忆系统在真实分布上是否还能用”，
并为 min_score / θ 给出标定建议。

输入（--samples JSON）示例：
{
  "queries": [
    {"query": "T-90 最大速度", "target": "fact", "route": "vector",
     "gold_keywords": ["60km/h"]},
    {"query": "夜间行军侦察", "target": "experience", "route": "bm25"}
  ],
  "negative": [
    {"query": "食堂菜单", "target": "fact", "route": "vector"}
  ]
}

输出：
  - 每条查询的 top-5 命中（内容/来源/分数）；
  - 有 gold_keywords 时计算 hit@5；
  - 负例 top1 分数分布 → min_score 建议；
  - 查询词在库中的“词表覆盖”（粗略）；
  - 报告落盘 reports/domain_check.json。

用法：
    python integration/zhirong_kit/domain_check.py \
        --samples samples.json \
        --fact-db ../data/facts.db --exp-db ../data/exps.db
    python integration/zhirong_kit/domain_check.py --seed-campaign heights_battle
        # 没有真实库时，用内置战役种子做示例运行
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_KIT = os.path.dirname(os.path.abspath(__file__))
_INT = os.path.dirname(_KIT)
_ROOT = os.path.dirname(_INT)
for _p in (_ROOT, _INT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from memsys import QueryItem, MemoryType, new_entry
from memsys.embeddings import tokenize
from adapter import create_adapter


def _seed_campaign(adapter, name: str) -> None:
    from campaign.campaign_data import CAMPAIGNS, SEED_FACTS, SEED_EXPS
    for content, attrs in SEED_FACTS:
        e = new_entry(MemoryType.FACT, content, source="domain-seed", attrs=attrs)
        e.id = "seed-f-" + str(abs(hash(content)) % 10 ** 8)
        adapter.ctl.factual.add(e)
    for content, imp, stage in SEED_EXPS:
        e = new_entry(MemoryType.EXPERIENCE, content, source="domain-seed",
                      importance=imp, attrs={"stage": stage})
        e.id = "seed-e-" + str(abs(hash(content)) % 10 ** 8)
        adapter.ctl.experiential.add(e)
    print(f"[domain_check] 已注入战役种子：事实 {len(SEED_FACTS)} / 经验 {len(SEED_EXPS)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default="", help="样本 JSON 路径")
    ap.add_argument("--fact-db", default="")
    ap.add_argument("--exp-db", default="")
    ap.add_argument("--seed-campaign", default="",
                    help="先用内置战役种子填充库（示例运行）")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--embed-glm", action="store_true")
    args = ap.parse_args()

    if args.samples:
        with open(args.samples, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"queries": [], "negative": []}

    adapter = create_adapter(real=args.real, embed_glm=args.embed_glm,
                             fact_db=args.fact_db or None,
                             exp_db=args.exp_db or None)
    if args.seed_campaign:
        _seed_campaign(adapter, args.seed_campaign)

    ctl = adapter.ctl
    report = {"n_facts": ctl.factual.stats()["count"],
              "n_exps": ctl.experiential.stats()["count"],
              "checks": []}

    def _run(qd):
        q = QueryItem(qd.get("q_id", "dc"), qd.get("intent", "巡检"),
                      qd.get("target", "fact"), qd.get("route", "vector"),
                      qd.get("query", qd.get("query_text", "")),
                      attrs=qd.get("attrs"))
        hits = ctl.retriever.retrieve(q, top_k=5)
        return [{"id": h.entry.id, "type": h.entry.type.value,
                 "content": h.entry.content[:60], "score": round(h.score, 4),
                 "source": h.entry.source} for h in hits]

    # 正例巡检
    for qd in data.get("queries", []):
        hits = _run(qd)
        gold = [str(k) for k in qd.get("gold_keywords", [])]
        hit5 = 1.0 if gold and any(any(k in h["content"] for k in gold) for h in hits) else (0.0 if gold else None)
        # 词表覆盖：查询 token 是否出现在任一库内容
        toks = set(tokenize(qd.get("query", "")))
        corpus = " ".join([ctl.factual.get(i).content for i in ctl.factual.candidates()]
                          + [ctl.experiential.get(i).content for i in ctl.experiential.candidates()])
        cover = round(len([t for t in toks if t in corpus]) / max(len(toks), 1), 3)
        report["checks"].append({"kind": "query", "query": qd.get("query"),
                                 "target": qd.get("target"), "hit@5": hit5,
                                 "word_coverage": cover, "top": hits})
        print(f"QI {qd.get('query')!r:24s} hit@5={hit5 if hit5 is not None else '-'} "
              f"词表覆盖={cover} top={len(hits)}")

    # 负例分布 → min_score 建议
    neg_tops = []
    for qd in data.get("negative", []):
        hits = _run(qd)
        top = hits[0]["score"] if hits else 0.0
        neg_tops.append(round(top, 4))
        print(f"NEG {qd.get('query')!r:24s} top1={top:.4f} "
              f"{'⚠>0.16' if top > 0.16 else 'OK'}")
    if neg_tops:
        m = max(neg_tops)
        suggestion = round(min(max(m + 0.02, 0.12), 0.30), 4)
        report["min_score_suggestion"] = {
            "negative_top1_max": m, "suggestion": suggestion,
            "note": "建议 min_score ≈ 负例top1最大值 + 0.02（并留正例余量）；"
                    "真 embedding 后按 E 噪声研究协议正式扫描"}
        print(f"\n[min_score 建议] 负例 top1 max={m:.4f} → 建议阈值 {suggestion}")
    else:
        report["min_score_suggestion"] = {"suggestion": None,
                                          "note": "未提供 negative 样本"}

    os.makedirs(os.path.join(_KIT, "reports"), exist_ok=True)
    out = os.path.join(_KIT, "reports", "domain_check.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[报告已落盘] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
