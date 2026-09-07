# -*- coding: utf-8 -*-
"""
eval.ablation — G0–G5 六组消融跑批（docs/04 5.3 节）
=====================================================
用同一批"场次 → gold 记忆"测试集，逐组关闭/开启记忆能力，统计检索指标：

  G0 无记忆          （纯 LLM 基线——检索指标无意义，仅对照规划质量）
  G1 仅短期          （工作记忆装载，不检索长期）
  G2 G1+长期事实     （只开事实库检索）
  G3 G2+经验         （双库全开）
  G4 G3+进化         （双库 + 复盘进化写入/合并/遗忘/抽象）
  G5 G4+检索策略对比  （vector / bm25 / sql / hybrid 路由各自打分）

用法：
    python -m eval.ablation        # 在 课题3_长短期记忆/ 目录下运行
输出：G1–G5 的 hit/recall/mrr/ndcg 表 + 库规模对照（验证 G4 的'遗忘控规模'）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from memsys.schema import MemoryType, QueryItem, new_entry
from memsys.controller import MemoryController
from memsys.retrieval.hybrid import HybridRetriever
from .metrics import evaluate_retrieval


@dataclass
class AblationCase:
    """单条消融测试用例（自建作战测试集的最小单元，后续扩充为 JSON 数据集）。"""

    query: QueryItem          # 该场要回答的检索问题
    gold_ids: List[str]       # 标注的相关记忆 id（人工/脚本预置）
    review_text: str = ""     # 场次复盘（G4 才会用到）


# ---------------------------------------------------------------- 种子数据
def seed_stores(ctl: MemoryController) -> None:
    """预置一批'历史记忆'（模拟已有多场次沉淀），并返回 gold 对照。

    内容刻意覆盖：装备参数（事实）、历史教训（经验）——
    使不同检索路（字面 vs 语义）各有可命中的目标。
    """
    facts = [
        ("红方 T-90 主战坦克：最大速度 60km/h，主炮 125mm。",
         {"装备": "T-90", "阵营": "红方"}),
        ("蓝方 M1A2 主战坦克：最大速度 67km/h，主炮 120mm。",
         {"装备": "M1A2", "阵营": "蓝方"}),
        ("2 号高地海拔 320 米，北坡缓南坡陡，仅有东侧一条装甲通行道路。",
         {"地点": "2号高地"}),
    ]
    exps = [
        "教训：夜间行军未派先遣侦察，先头连在东侧隘口遭遇伏击。",
        "经验：炮火准备前置 20 分钟，可显著压制敌方反坦克火力点。",
        "教训：渡河架桥耗时超预估 40%，导致主攻梯队迟到。",
    ]
    gold: List[str] = []
    for content, attrs in facts:
        e = new_entry(MemoryType.FACT, content, source="seed", attrs=attrs)
        ctl.factual.add(e)
        gold.append(e.id)
    for content in exps:
        e = new_entry(MemoryType.EXPERIENCE, content, source="seed", importance=2.0)
        ctl.experiential.add(e)
        gold.append(e.id)
    return gold


def build_cases(gold: List[str]) -> List[AblationCase]:
    """构造 3 个查询用例（gold 取自种子记忆，模拟自建测试集）。"""
    fact_ids = [g for g in gold if g.startswith("fact-")]
    exp_ids = [g for g in gold if g.startswith("experience-")]
    return [
        AblationCase(
            query=QueryItem(q_id="c1", intent="查装备参数", target="fact",
                            route="vector", query_text="T-90 坦克 最大速度"),
            gold_ids=fact_ids[:1]),
        AblationCase(
            query=QueryItem(q_id="c2", intent="查地形通行条件", target="fact",
                            route="vector", query_text="2 号高地 装甲 通行 道路"),
            gold_ids=[fact_ids[2]] if len(fact_ids) > 2 else fact_ids),
        AblationCase(
            query=QueryItem(q_id="c3", intent="召回历史教训", target="experience",
                            route="vector", query_text="夜战 侦察 伏击 教训"),
            gold_ids=exp_ids[:1]),
    ]


# ---------------------------------------------------------------- 各组跑批
def run_group(group: str, cases: List[AblationCase], ctl: MemoryController,
              review_text: str = "") -> Dict[str, object]:
    """跑一组消融，返回该组的平均检索指标 + 库规模。

    实现方式：按组别控制 controller 的可用能力（用注入/旁路模拟开关）：
      G1：绕过 retriever，检索结果恒空（只验证短期装载链路不炸）；
      G2：只对 factual 检索（经验库查询旁路）；
      G3：双库全开（hybrid 默认）；
      G4：G3 基础上先跑一遍进化（复盘写入新记忆）再检索；
      G5：G4 基础上对三种路由分别检索打分。
    """
    if group == "G1":
        return {"group": "G1", "note": "仅短期（检索旁路）",
                "store_size": ctl.factual.stats()["count"] + ctl.experiential.stats()["count"]}

    metrics_all: List[Dict[str, float]] = []
    routes: Dict[str, List[float]] = {} if group == "G5" else None  # type: ignore

    if group == "G4":
        # 先进化（复盘沉淀新记忆），再检索——验证'越用越强'
        ctl.evolution.evolve_from_review(review_text, session_id="ablation")

    for case in cases:
        q = case.query
        if group == "G2" and q.target != "fact":
            continue  # G2 只评事实检索
        # G5：三种路由各评一次；其它组用查询自带路由
        route_list = ["vector", "bm25", "sql"] if group == "G5" else [q.route]
        for route in route_list:
            qq = QueryItem(q_id=q.q_id, intent=q.intent, target=q.target,
                           route=route, query_text=q.query_text)
            hits = ctl.retriever.retrieve(qq, top_k=5)
            ranked = [h.entry.id for h in hits]
            m = evaluate_retrieval(ranked, case.gold_ids, ks=(3, 5))
            metrics_all.append(m)
            if group == "G5":
                routes.setdefault(route, []).append(m["hit@5"])

    if not metrics_all:
        return {"group": group, "note": "无有效用例"}

    avg = {k: round(sum(m[k] for m in metrics_all) / len(metrics_all), 4)
           for k in metrics_all[0]}
    out: Dict[str, object] = {
        "group": group,
        "store_size": ctl.factual.stats()["count"] + ctl.experiential.stats()["count"],
        **avg,
    }
    if group == "G5" and routes:
        out["by_route"] = {r: round(sum(v) / len(v), 4) for r, v in routes.items()}
    return out


def run_all() -> List[Dict[str, object]]:
    """G0–G5 全量跑批（每组建独立 controller，互不污染）。"""
    results: List[Dict[str, object]] = []
    for group in ("G0", "G1", "G2", "G3", "G4", "G5"):
        if group == "G0":
            results.append({"group": "G0", "note": "无记忆基线（纯 LLM，检索指标不适用）"})
            continue
        ctl = MemoryController()
        gold = seed_stores(ctl)
        cases = build_cases(gold)
        review = ("复盘：教训：夜战中通信静默过久导致协同脱节。"
                  "经验：预备队投入时机应提前至突破口形成后 10 分钟。")
        results.append(run_group(group, cases, ctl, review_text=review))
    return results


if __name__ == "__main__":
    print("=" * 72)
    print("G0–G5 消融跑批（种子测试集 · MockEmbedding · 离线）")
    print("=" * 72)
    for row in run_all():
        print(row)
    print("=" * 72)
    print("说明：G1 检索旁路无指标；G4 先进化再检索（验证越用越强）；"
          "G5 分路由统计 hit@5（验证混合检索增益）。")
