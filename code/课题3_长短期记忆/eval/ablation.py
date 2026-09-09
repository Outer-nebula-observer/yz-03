# -*- coding: utf-8 -*-
"""
eval.ablation — G0–G6 消融跑批 v2（测试集 50 条 · 真对照组 · 统计推断）
==========================================================================
【v2 重写缘由（评审 §一）】v1 的消融存在四个设计缺陷，即使接真模型也产不出
有效结论：
  ① G5 分路对比无效——hybrid 模式下 route 不影响结果（三路全跑后融合），
    by_route 三个数字是同一次融合的三份拷贝；v2 用 mode="single" 真单路；
  ② G2 对照被污染——通过"跳过经验类用例"实现对照，两组分母不同；
    v2 固定用例集，用依赖注入空经验库实现真对照；
  ③ G4 不能证明"进化有用"——进化写入的新记忆不在 gold 里，指标必然
    不变；v2 增设 H 类跨场次用例（场次1 复盘写入 → 场次2 查询，gold
    运行期解析），"越用越强"首次可量化；
  ④ 无任务层指标、无随机基线、无显著性检验——赛题主张"检索增强规划"
    零证据；v2 补任务层三指标 + 解析随机基线 + 配对置换检验 + bootstrap CI。

实验组（检索指标在 A–G 44 条固定用例集上；任务指标在 3 个任务场次上）：
  G0 无记忆基线      任务层（无检索装载）——约束满足/引用率对照
  G1 仅短期          检索旁路 → 任务层
  G2 仅事实库        空经验库注入（真对照）→ 检索+任务
  G3 双库全开        → 检索+任务（主配置）
  G4 +进化(跨场次)   H 类 6 条：先跑场次1 复盘进化再查场次2；对照 G3 的
                    H 类（无场次1，gold 不可达应全 miss）
  G5 检索策略对比    hybrid vs 真单路(vector/bm25/sql) × 融合权重变体
  G6 阶段亲和        stage_bonus=0 vs 0.15（G 类阶段决胜对）
  E  噪声研究        负例查询返回率 × min_score 扫描
  F  遗忘研究        保护线行为 / 阈值×时间扫描 / 误删率
  C  压缩研究        truncate vs summarize：压缩率/约束保留/关键信息保留
  S  敏感性扫描      θ 查重 / min_score / stage_bonus
  显著性             G3vsG2、hybrid vs vector 单路、G6 on/off

用法：
    python -m eval.ablation            # 全量跑批，打印报告 + 落盘 JSON
    python -m eval.ablation --quick    # 只跑 G0–G6 主线
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memsys import (MemoryController, MemoryPipeline, MemoryType, MockLLM,
                    MockEmbedding, QueryItem, WorkingMemory,
                    FactualStore, ExperientialStore, new_entry,
                    MemoryEvolution, HybridRetriever, get_strategy)
from .metrics import evaluate_retrieval
from . import stats as st
from .testset import (build_stores, RETRIEVAL_CASES, CROSS_SESSION_CASES,
                      resolve_cross_session_gold, SEED_FACTS, SEED_EXPS)

KS = (3, 5)
TOP_K = 5


# ================================================================ 通用工具
class _NullRetriever:
    """G1 检索旁路：任何查询返回空（只保留短期装载链路）。"""

    def retrieve(self, q, top_k=5, mode="hybrid"):
        q.answer_memory_ids = []
        return []


def _fresh(with_exps: bool = True, with_stage_pairs: bool = True
           ) -> MemoryController:
    """每组独立 controller（消融互不污染）。"""
    emb = MockEmbedding()
    ctl = MemoryController(experiential=ExperientialStore(emb),
                           factual=FactualStore(":memory:", emb))
    return build_stores(ctl, with_stage_pairs=with_stage_pairs,
                        with_exps=with_exps)


def run_retrieval(ctl: MemoryController, cases: List[dict],
                  mode: str = "hybrid", top_k: int = TOP_K,
                  categories: Optional[List[str]] = None,
                  route_override: Optional[str] = None) -> Dict[str, List]:
    """跑一批检索用例，返回逐用例指标（供配对检验）+ 汇总。

    route_override: 强制覆盖所有用例的路由（G5 单路对比的关键——
    用例自带 route 各不相同，不覆盖则"单路配置"名不副实）。
    返回 {per_case: [{qid, category, mrr, hit@3, ...}]}
    """
    per_case: List[dict] = []
    for case in cases:
        if categories and case["category"] not in categories:
            continue
        q = case["query"]
        # 每配置独立 QueryItem（retrieve 会回填 answer_memory_ids/强化）
        qq = QueryItem(q.q_id, q.intent, q.target,
                       route_override or q.route,
                       query_text=q.query_text, attrs=q.attrs, stage=q.stage)
        hits = ctl.retriever.retrieve(qq, top_k=top_k, mode=mode)
        ranked = [h.entry.id for h in hits]
        m = evaluate_retrieval(ranked, case["gold"], ks=KS)
        # 干扰项压制：gold 应排在 distractor 之前（F/G 类专用）
        if case.get("distractor"):
            gold_pos = next((i for i, mid in enumerate(ranked)
                             if mid in case["gold"]), None)
            dist_pos = next((i for i, mid in enumerate(ranked)
                             if mid == case["distractor"]), None)
            m["gold_above_distractor"] = (
                1.0 if (gold_pos is not None
                        and (dist_pos is None or gold_pos < dist_pos)) else 0.0)
        m["qid"] = case["qid"]
        m["category"] = case["category"]
        m["n_returned"] = len(hits)
        per_case.append(m)
    return {"per_case": per_case}


def summarize(per_case: List[dict]) -> Dict[str, float]:
    """逐用例指标 → 均值（+关键指标的 bootstrap CI）。"""
    if not per_case:
        return {}
    keys: set = set()
    for m in per_case:
        keys |= {k for k, v in m.items() if isinstance(v, (int, float))}
    out: Dict[str, float] = {}
    for k in sorted(keys):
        # 指标只对"有该指标的用例"求均值（如 gold_above_distractor
        # 仅 F/G 类携带；n_returned 对负例才有意义）
        vals = [m[k] for m in per_case if k in m]
        if not vals:
            continue
        out[k] = round(st.mean(vals), 4)
        if k in ("hit@5", "recall@5") and len(vals) > 1:
            lo, hi = st.bootstrap_ci(vals)
            out[f"{k}_ci"] = f"[{lo},{hi}]"
    out["_n"] = len(per_case)
    return out


def by_category(per_case: List[dict]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, List[dict]] = {}
    for m in per_case:
        out.setdefault(m["category"], []).append(m)
    return {cat: summarize(ms) for cat, ms in sorted(out.items())}


# ================================================================ 任务层
TASK_MISSIONS = [
    {"goal": "夜间夺占 2 号高地",
     "constraints": ["禁止越境", "限时 4 小时", "优先保存装甲力量"],
     "queries": [
         ("t1a", "查目标地形", "fact", "vector", "2 号高地 地形 装甲 通行 道路", None),
         ("t1b", "召回夜战教训", "experience", "vector", "夜间 行军 侦察 伏击", None),
         ("t1c", "无关查询(噪声)", "fact", "vector", "电影 票房 统计", None)]},
    {"goal": "强渡青川河建立桥头堡",
     "constraints": ["天亮前完成渡河", "工兵分队随行"],
     "queries": [
         ("t2a", "查渡口水文", "fact", "vector", "渡口 水深 流速 舟桥", None),
         ("t2b", "召回渡河教训", "experience", "vector", "渡河 架桥 超时", None),
         ("t2c", "无关查询(噪声)", "experience", "vector", "诗词 格律 押韵", None)]},
    {"goal": "组织仓促防御迟滞蓝方装甲",
     "constraints": ["无空中支援", "反坦克弹药有限"],
     "queries": [
         ("t3a", "查反坦克武器参数", "fact", "sql", "反坦克 导弹 参数", {"装备": "红箭-9"}),
         ("t3b", "召回防御教训", "experience", "vector", "反坦克 阵地 覆盖", None),
         ("t3c", "无关查询(噪声)", "fact", "vector", "足球 阵型 安排", None)]},
]


def run_task_group(ctl: MemoryController, disable_retrieval: bool = False
                   ) -> List[dict]:
    """跑 3 个任务场次的任务层指标（约束满足率/记忆引用率）。"""
    if disable_retrieval:
        ctl.retriever = _NullRetriever()  # type: ignore[assignment]
    results = []
    for mission in TASK_MISSIONS:
        queries = [QueryItem(qid, intent, target, route,
                             query_text=text, attrs=attrs)
                   for (qid, intent, target, route, text, attrs)
                   in mission["queries"]]
        ctl.start_session(f"TASK-{mission['goal'][:4]}", mission["goal"],
                          mission["constraints"], queries)
        ctl.retrieve_and_load(top_k=TOP_K)
        context = ctl.render_context()
        output = ctl.llm.chat("你是作战规划智能体。基于以下记忆上下文生成规划方案。", context)
        # 任务层指标（评审 §1.4 落地）
        from .task_metrics import evaluate_task, memory_citation_rate
        tm = evaluate_task(output, mission["constraints"], ctl.working_memory)
        # 噪声污染：负例查询（第 3 条）命中的记忆是否进了输出
        neg_briefs = [b for mid, b in
                      ctl.working_memory.slot.loaded_briefs.items()
                      if mid in (queries[2].answer_memory_ids or [])]
        tm["noise_pollution"] = round(
            memory_citation_rate(output, neg_briefs) if neg_briefs else 0.0, 4)
        tm["goal"] = mission["goal"]
        results.append(tm)
        ctl.close_session("")  # 空复盘：不产生进化写入（保持组间可比）
    return results


# ================================================================ G4 跨场次
def run_cross_session(with_evolution: bool) -> Dict[str, object]:
    """H 类：场次1（复盘进化）→ 场次2（查询复用）。

    with_evolution=True  → G4：完整跑场次1（复盘写入）
    with_evolution=False → G3 对照：不跑场次1（gold 不存在，应全 miss）
    """
    ctl = _fresh(with_stage_pairs=False)
    cases = CROSS_SESSION_CASES()
    per_case: List[dict] = []
    for c in cases:
        if with_evolution:
            # 场次 1：目标 + 复盘 → 进化写入
            ctl.start_session(f"S1-{c['qid']}", c["s1_goal"], [], [])
            ctl.close_session(c["s1_review"])
        gold = resolve_cross_session_gold(ctl, c["expect_keyword"]) \
            if with_evolution else []
        qid, intent, target, route, text = c["s2_query"]
        # 场次 2：新目标下查询（gold = 场次1 沉淀）
        ctl.start_session(f"S2-{c['qid']}", c["s2_goal"], [],
                          [QueryItem(qid, intent, target, route, text)])
        q = ctl.working_memory.slot.query_list[0]
        hits = ctl.retriever.retrieve(q, top_k=TOP_K)
        ranked = [h.entry.id for h in hits]
        m = evaluate_retrieval(ranked, gold, ks=KS)
        m["qid"] = c["qid"]
        # h6 负控：场次1"渡口/浅滩"教训不得混入巷战查询结果
        if c["expect_keyword"] is None:
            intrusion = [h.entry.id for h in hits
                         if "浅滩" in h.entry.content or "渡口选择" in h.entry.content]
            m["false_cross_recall"] = 1.0 if intrusion else 0.0
        # 复用来源统计：命中里多少来自场次1 复盘
        m["from_s1_review"] = sum(
            1 for h in hits if h.entry.source.startswith("复盘:"))
        per_case.append(m)
        ctl.close_session("")
    return {"per_case": per_case,
            "summary": summarize(per_case),
            "store_size": (ctl.factual.stats()["count"]
                           + ctl.experiential.stats()["count"])}


# ================================================================ 主流程
def run_all(quick: bool = False) -> Dict[str, object]:
    report: Dict[str, object] = {}
    t0 = time.time()

    # ---------------- G0/G1/G2/G3：主对照（固定 44 条用例 + 3 任务场）----------------
    groups = {}
    # G0：无记忆（任务层对照；不执行检索）
    ctl0 = _fresh()
    task0 = run_task_group(ctl0, disable_retrieval=True)
    groups["G0"] = {"task": {k: round(st.mean([t[k] for t in task0]), 4)
                             for k in ("constraint_sat", "memory_citation",
                                       "noise_pollution")},
                    "note": "无记忆基线：检索旁路（任务层对照）"}

    # G1：仅短期（同样旁路检索，但走完整会话流程）
    ctl1 = _fresh()
    task1 = run_task_group(ctl1, disable_retrieval=True)
    groups["G1"] = {"task": {k: round(st.mean([t[k] for t in task1]), 4)
                             for k in ("constraint_sat", "memory_citation",
                                       "noise_pollution")},
                    "note": "仅短期：检索旁路（与 G0 的差异=会话流程本身）"}

    # G2：仅事实库（真对照：固定用例集 + 空经验库注入）
    ctl2 = _fresh(with_exps=False, with_stage_pairs=False)
    cases = RETRIEVAL_CASES(ctl2)
    r2 = run_retrieval(ctl2, cases)
    task2 = run_task_group(ctl2)
    groups["G2"] = {"retrieval": summarize(r2["per_case"]),
                    "by_category": by_category(r2["per_case"]),
                    "task": {k: round(st.mean([t[k] for t in task2]), 4)
                             for k in ("constraint_sat", "memory_citation",
                                       "noise_pollution")},
                    "note": "仅事实库：空经验库注入（固定用例集真对照）"}

    # G3：双库全开（主配置）
    ctl3 = _fresh()
    cases3 = RETRIEVAL_CASES(ctl3)
    r3 = run_retrieval(ctl3, cases3)
    task3 = run_task_group(ctl3)
    groups["G3"] = {"retrieval": summarize(r3["per_case"]),
                    "by_category": by_category(r3["per_case"]),
                    "task": {k: round(st.mean([t[k] for t in task3]), 4)
                             for k in ("constraint_sat", "memory_citation",
                                       "noise_pollution")},
                    "note": "双库全开（主配置）"}

    # G3 vs G2 显著性（配对置换：逐用例 hit@5；用例 id 配对）
    g2_map = {m["qid"]: m for m in r2["per_case"]}
    g3_map = {m["qid"]: m for m in r3["per_case"]}
    common = [qid for qid in g3_map if qid in g2_map]
    x = [g3_map[q]["hit@5"] for q in common]
    y = [g2_map[q]["hit@5"] for q in common]
    groups["G3_vs_G2"] = {
        "paired_n": len(common),
        "mean_diff_hit5": round(st.mean(x) - st.mean(y), 4),
        "p_perm": st.paired_permutation_test(x, y)}

    # ---------------- G4：+进化（跨场次复用）----------------
    g4 = run_cross_session(with_evolution=True)
    g4_ctl_size = g4["store_size"]
    groups["G4"] = {"summary": g4["summary"],
                    "store_size": g4_ctl_size,
                    "note": "H 类 6 条：场次1 复盘进化 → 场次2 查询（gold=场次1 沉淀）"}
    g4c = run_cross_session(with_evolution=False)
    groups["G4_control(无场次1)"] = {"summary": g4c["summary"],
                                     "note": "对照：不跑场次1（gold 不可达应全 miss）"}
    # G4 vs 对照 显著性
    a = {m["qid"]: m for m in g4["per_case"] if m["qid"] != "h6"}
    b = {m["qid"]: m for m in g4c["per_case"] if m["qid"] != "h6"}
    ids = [q for q in a if q in b]
    groups["G4_vs_control"] = {
        "paired_n": len(ids),
        "p_perm": st.paired_permutation_test([a[q]["hit@5"] for q in ids],
                                             [b[q]["hit@5"] for q in ids]),
        "note": "h6 为负控不入检验（gold=None）"}

    # ---------------- G5：检索策略对比（真单路 vs 混合）----------------
    g5: Dict[str, object] = {}
    eval_cats = ["A", "B", "C", "D", "F"]  # G 需阶段字段、E 为负例（单列）
    for config in ("hybrid", "vector", "bm25", "sql"):
        ctl = _fresh()
        cs = RETRIEVAL_CASES(ctl)
        r = run_retrieval(ctl, cs,
                          mode=("single" if config != "hybrid" else "hybrid"),
                          categories=eval_cats,
                          route_override=(None if config == "hybrid"
                                          else config))
        g5[config] = summarize(r["per_case"])
    # 融合权重变体（hybrid 模式下扫描 α/β/γ）
    for wname, (a_, b_, g_) in {
            "hybrid(α.5,β.3,γ.2)": (0.5, 0.3, 0.2),
            "hybrid(α.7,β.2,γ.1)": (0.7, 0.2, 0.1),
            "hybrid(α.34,β.33,γ.33)": (0.34, 0.33, 0.33),
            "hybrid(α.2,β.5,γ.3)": (0.2, 0.5, 0.3)}.items():
        ctl = _fresh()
        ctl.retriever.alpha, ctl.retriever.beta, ctl.retriever.gamma = a_, b_, g_
        cs = RETRIEVAL_CASES(ctl)
        r = run_retrieval(ctl, cs, categories=eval_cats)
        g5[wname] = summarize(r["per_case"])
    groups["G5"] = g5
    # 显著性：hybrid vs 强制 vector 单路（A/B/C/D/F 逐用例配对）
    ctl_h = _fresh(); cs_h = RETRIEVAL_CASES(ctl_h)
    rh = run_retrieval(ctl_h, cs_h, mode="hybrid", categories=eval_cats)
    ctl_v = _fresh(); cs_v = RETRIEVAL_CASES(ctl_v)
    rv = run_retrieval(ctl_v, cs_v, mode="single", categories=eval_cats,
                       route_override="vector")
    hm = {m["qid"]: m for m in rh["per_case"]}
    vm = {m["qid"]: m for m in rv["per_case"]}
    ids = [q for q in hm if q in vm]
    groups["G5_hybrid_vs_vector"] = {
        "paired_n": len(ids),
        "p_perm": st.paired_permutation_test(
            [hm[q]["hit@5"] for q in ids], [vm[q]["hit@5"] for q in ids])}

    # ---------------- G6：阶段亲和 on/off ----------------
    g6: Dict[str, object] = {}
    for bonus, tag in ((0.15, "on(0.15)"), (0.0, "off(0)")):
        ctl = _fresh()
        ctl.retriever.stage_bonus = bonus
        cs = RETRIEVAL_CASES(ctl)
        r = run_retrieval(ctl, cs, categories=["G"])
        g6[tag] = summarize(r["per_case"])
    groups["G6"] = g6
    # 显著性（4 对——功效有限，注明）
    ctl6a = _fresh(); ctl6a.retriever.stage_bonus = 0.15
    ra = run_retrieval(ctl6a, RETRIEVAL_CASES(ctl6a), categories=["G"])
    ctl6b = _fresh(); ctl6b.retriever.stage_bonus = 0.0
    rb = run_retrieval(ctl6b, RETRIEVAL_CASES(ctl6b), categories=["G"])
    groups["G6_significance"] = {
        "metric": "gold_above_distractor（排序指标——同内容平局下 hit@5 无判别力）",
        "paired_n": len(ra["per_case"]),
        "p_perm": st.paired_permutation_test(
            [m["gold_above_distractor"] for m in ra["per_case"]],
            [m["gold_above_distractor"] for m in rb["per_case"]]),
        "note": "G 类仅 4 对，置换检验功效不足，结果仅供方向参考"}

    report["groups"] = groups

    # ---------------- 随机基线 ----------------
    n_facts = len(SEED_FACTS)          # 14
    n_exps_all = len(SEED_EXPS)        # 14（G2 时经验库 0 条）
    report["random_baseline"] = {
        "note": "随机排序基线（解析式）——消融数字必须高于此才有意义",
        "fact库(n=14)": {"hit@5_单gold": round(st.random_hit_at_k(n_facts, 5, 1), 4),
                          "hit@5_3gold": round(st.random_hit_at_k(n_facts, 5, 3), 4),
                          "mrr_单gold": st.random_mrr(n_facts, 1)},
        "exp库(n=14)": {"hit@5_单gold": round(st.random_hit_at_k(n_exps_all, 5, 1), 4),
                         "mrr_单gold": st.random_mrr(n_exps_all, 1)},
        "旧种子集(n=6)参照": {"hit@5_单gold": round(st.random_hit_at_k(6, 5, 1), 4),
                              "mrr": st.random_mrr(6, 1),
                              "说明": "v1 全 1.0 的指标在此基线 0.83 之上——判别力不足的量化证明"},
    }

    if not quick:
        # ---------------- E：噪声研究（min_score 扫描）----------------
        noise: Dict[str, object] = {}
        for ms in (0.05, 0.10, 0.16, 0.25):
            ctl = _fresh()
            ctl.retriever.min_score = ms
            cs = RETRIEVAL_CASES(ctl)
            # 负例返回率
            r = run_retrieval(ctl, cs, categories=["E"])
            pc = r["per_case"]
            noise[f"min_score={ms}"] = {
                "负例返回率": round(st.mean(
                    [1.0 if m["n_returned"] > 0 else 0.0 for m in pc]), 4),
                "负例均返回条数": round(st.mean([m["n_returned"] for m in pc]), 4)}
            # 同阈值下正例 recall（trade-off 曲线的另一端）
            rp = run_retrieval(ctl, cs, categories=["A", "B", "C", "D", "F"])
            noise[f"min_score={ms}"]["正例hit@5"] = summarize(rp["per_case"])["hit@5"]
        report["E_noise_study"] = noise

        # ---------------- F：遗忘研究 ----------------
        forget: Dict[str, object] = {}
        emb = MockEmbedding()
        ctl = _fresh(with_stage_pairs=False)
        now = time.time()
        aged_unprot, aged_prot, fresh_ids = [], [], []
        for i in range(10):   # 30 天前 · 未保护（复盘自动抽取级 importance=1.5）
            e = new_entry(MemoryType.EXPERIENCE,
                          f"经验：老旧战术要点第{i}条，行军宿营注意事项。")
            e.timestamp = now - 30 * 86400
            e.last_recalled_at = e.timestamp
            ctl.experiential.add(e)
            aged_unprot.append(e.id)
        for i in range(5):    # 30 天前 · 保护（人工标注保命教训 importance=2.0）
            e = new_entry(MemoryType.EXPERIENCE,
                          f"教训：血泪教训第{i}条，火力压制不足致伤亡。", importance=2.0)
            e.timestamp = now - 30 * 86400
            e.last_recalled_at = e.timestamp
            ctl.experiential.add(e)
            aged_prot.append(e.id)
        for i in range(5):    # 刚写入
            e = new_entry(MemoryType.EXPERIENCE, f"经验：最新要点第{i}条，侦察警戒部署。")
            ctl.experiential.add(e)
            fresh_ids.append(e.id)
        forgot = ctl.evolution.forget()
        fs, as_ = set(forgot), set(aged_unprot)
        forget["保护线行为"] = {
            "30天未召回·未保护(1.5) 应删10": len(as_ & fs),
            "30天未召回·保护(2.0) 应删0": len(set(aged_prot) & fs),
            "新写入 应删0": len(set(fresh_ids) & fs),
            "说明": ("保护线生效：自动抽取的复盘教训(1.5)会被遗忘淘汰，"
                      "人工标注保命教训(2.0)与抽象产物(max+0.5)受保护——"
                      "v1 的 importance 交互缺陷已修复（教训自动 2.0=保护线，"
                      "遗忘机制系统性失效）")}
        # 遗忘对检索的影响：gold 为被删记忆的查询应 miss（正确遗忘），
        # gold 为保护/新记忆的查询应仍命中（无误删）
        def _hit(queries_gold):
            hits = 0
            for qtext, golds in queries_gold:
                qq = QueryItem("f", "查", "experience", "vector", qtext)
                r = ctl.retriever.retrieve(qq, top_k=5)
                if any(h.entry.id in golds for h in r):
                    hits += 1
            return hits
        forget["检索影响"] = {
            "被删记忆查询命中(应0)": _hit(
                [(f"老旧 战术 要点 第{i}", [aged_unprot[i]]) for i in range(5)]),
            "保护记忆查询命中(应5)": _hit(
                [(f"血泪 教训 第{i} 火力 压制", [aged_prot[i]]) for i in range(5)]),
            "新记忆查询命中(应5)": _hit(
                [(f"最新 要点 第{i} 侦察 警戒", [fresh_ids[i]]) for i in range(5)])}
        # 强度S × 时间 扫描（遗忘的有效判别维度：t/S 比值，非阈值本身——
        # S=1 时任何 threshold 下 3 天全删，阈值扫描无判别力）
        sweep = {}
        for S in (1.0, 3.0, 7.0):
            row = {}
            for days in (3, 10, 30):
                emb2 = MockEmbedding()
                c2 = MemoryController(experiential=ExperientialStore(emb2),
                                      factual=FactualStore(":memory:", emb2))
                for i in range(20):
                    e = new_entry(MemoryType.EXPERIENCE, f"经验：扫描用第{i}条。")
                    e.timestamp = now - days * 86400
                    e.last_recalled_at = e.timestamp
                    e.decay_strength = S   # 模拟被召回过 S 次（间隔效应）
                    c2.experiential.add(e)
                row[f"{days}天"] = len(c2.evolution.forget())
            sweep[f"S={S}"] = row
        forget["强度S×时间扫描(20条未保护记忆删除数)"] = sweep
        report["F_forgetting_study"] = forget

        # ---------------- C：压缩研究 ----------------
        comp: Dict[str, object] = {}
        marker = "补给点坐标XK-77仅限营级知晓"
        msgs = ([marker]
                + [f"战报{i}：红方装甲梯队向东机动，距离高地约{100 - i}公里，"
                   f"沿途侦察报告敌情变化，弹药油料消耗正常" for i in range(8)]
                + [f"战报{j}：蓝方炮兵向 3 号高地转移，我方请求火力压制，"
                   f"各连队报告伤亡与阵地情况" for j in range(8, 16)])
        for strategy in ("truncate", "summarize"):
            wm = WorkingMemory("C1", capacity_tokens=300,
                               warning_ratio=0.7, flush_ratio=1.0,
                               llm=(MockLLM() if strategy == "summarize" else None))
            wm.set_goal("压缩研究任务", constraints=["禁止越境", "弹药基数减半"])
            peak = 0
            for m in msgs:
                wm.push_message(m)
                peak = max(peak, wm.used_tokens)
            before = peak
            get_strategy(strategy).apply(wm, int(300 * 0.7))
            after = wm.used_tokens
            ctx = wm.render()
            comp[strategy] = {
                "消息数": len(msgs), "峰值tokens": before, "压缩后tokens": after,
                "压缩率": round(1 - after / max(before, 1), 4),
                "归档次数(len(archived))": len(wm.archived),
                "约束保留": all(c in ctx for c in ("越境", "弹药基数减半")),
                "关键信息保留(标记事实)": marker[:8] in ctx or "XK-77" in ctx,
                "说明": ("truncate 驱逐最旧消息（标记事实在最旧端→应丢失）；"
                          "Mock 的 summarize 为截断式拼接（可能不缩反涨——"
                          "Mock 局限而非策略缺陷）；真模型后此项才度量"
                          "'摘要保真压缩'的真实质量")}
        report["C_compression_study"] = comp

        # ---------------- S：敏感性扫描 ----------------
        sens: Dict[str, object] = {}
        # θ 查重：近重复对 vs 不同内容对
        emb = MockEmbedding()
        dups = [("教训：夜战需前置电子压制，接敌后通信被干扰。",
                 "教训：夜间作战应先实施电子压制，接敌通信受扰。"),
                ("经验：预备队投入应提前10分钟。",
                 "经验：预备队使用时机要提前约10分钟。")]
        distinct = [("教训：渡河架桥超时导致梯队迟到。",
                     "经验：佯动可有效牵制敌直瞄火力。")]
        for theta in (0.6, 0.7, 0.8, 0.9):
            fs = FactualStore(":memory:", emb)
            es = ExperientialStore(emb)
            ev = MemoryEvolution(fs, es, MockLLM(), emb, merge_theta=theta)
            rejected_dup = 0
            for a, b in dups:
                ev.write(MemoryType.EXPERIENCE, a)
                if ev.write(MemoryType.EXPERIENCE, b) is None:
                    rejected_dup += 1
            rejected_new = 0
            for a, b in distinct:
                ev.write(MemoryType.EXPERIENCE, a)
                if ev.write(MemoryType.EXPERIENCE, b) is None:
                    rejected_new += 1
            sens[f"θ={theta}"] = {
                "近重复对拦截率(应高)": rejected_dup / len(dups),
                "不同内容误拦率(应0)": rejected_new / len(distinct)}
        # stage_bonus 扫描（判别指标=干扰压制：gold 排在干扰之前；
        # 同内容对 hit@5 恒 1 无判别力）
        for bonus in (0.0, 0.05, 0.15, 0.30):
            ctl = _fresh()
            ctl.retriever.stage_bonus = bonus
            r = run_retrieval(ctl, RETRIEVAL_CASES(ctl), categories=["G"])
            sens[f"stage_bonus={bonus}"] = {
                "G类干扰压制": summarize(r["per_case"]).get(
                    "gold_above_distractor", 0)}
        report["S_sensitivity"] = sens

    # 任务层引用率的 Mock 混杂说明（G2 citation 0.47 > G3 0.40 的成因）
    report["task_layer_note"] = (
        "MockLLM 为回显式输出（截取上下文前 300 字）：G2 装载记忆更少，"
        "固定 300 字回显覆盖其中更大比例 → 引用率反而更高。该指标在 Mock "
        "下的有效对照是 G0/G1(=0，无装载) vs G2/G3(>0，有装载)；"
        "'LLM 善用记忆'的比率须接真模型后度量（口径不变）。")

    report["_meta"] = {
        "testset": "50 cases (A–G 44 + H 6)",
        "embedding": "MockEmbedding(哈希词袋)",
        "llm": "MockLLM(回显式)",
        "elapsed_s": round(time.time() - t0, 1),
        "honesty": ("Mock 模式下：检索层指标可判别（测试集含干扰/负例/转述）；"
                    "任务层指标仅度量'上下文构造正确性'（MockLLM 为回显），"
                    "换真模型后同一脚本即测'LLM 是否善用记忆'——口径不变"),
    }
    return report


# ================================================================ 输出
def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".") or "0"
    return str(v)


def print_report(report: Dict[str, object]) -> None:
    w = sys.stdout
    print("=" * 78)
    print("G0–G6 消融跑批 v2（测试集 50 条 · MockEmbedding · 离线）")
    print("=" * 78)
    g = report["groups"]
    for name in ("G0", "G1", "G2", "G3"):
        row = g[name]
        print(f"\n【{name}】{row.get('note','')}")
        if "task" in row:
            print("  任务层:", {k: _fmt(v) for k, v in row["task"].items()})
        if "retrieval" in row:
            print("  检索层:", {k: _fmt(v) for k, v in row["retrieval"].items()
                                if not k.endswith("_ci")})
            print("  分类别 hit@5:", {c: _fmt(d.get("hit@5", 0))
                                     for c, d in row["by_category"].items()})
    print(f"\n【G3 vs G2 显著性】n={g['G3_vs_G2']['paired_n']} "
          f"Δhit@5={g['G3_vs_G2']['mean_diff_hit5']} "
          f"p(置换)={g['G3_vs_G2']['p_perm']}")
    print(f"\n【G4 +进化(跨场次)】{g['G4']['note']}")
    print("  summary:", {k: _fmt(v) for k, v in g["G4"]["summary"].items()
                         if not k.endswith("_ci")})
    print("  对照(无场次1):", {k: _fmt(v) for k, v in
                               g["G4_control(无场次1)"]["summary"].items()
                               if not k.endswith("_ci")})
    print(f"  显著性: p={g['G4_vs_control']['p_perm']} "
          f"({g['G4_vs_control']['note']})")
    print("\n【G5 检索策略对比】(A/B/C/D/F 用例)")
    for cfg, s in g["G5"].items():
        print(f"  {cfg:26s} hit@5={_fmt(s['hit@5'])} "
              f"recall@5={_fmt(s['recall@5'])} "
              f"mrr={_fmt(s['mrr'])} "
              f"干扰压制={_fmt(s.get('gold_above_distractor', 0))}")
    print(f"  hybrid vs vector 单路: p={g['G5_hybrid_vs_vector']['p_perm']}")
    print("\n【G6 阶段亲和】(G 类阶段决胜对)")
    for tag, s in g["G6"].items():
        print(f"  {tag:10s} hit@5={_fmt(s['hit@5'])} "
              f"干扰压制={_fmt(s.get('gold_above_distractor', 0))}")
    print(f"  显著性: {g['G6_significance']}")
    rb = report["random_baseline"]
    print("\n【随机基线】", rb["note"])
    for k, v in rb.items():
        if isinstance(v, dict):
            print(f"  {k}: {v}")
    for section, title in (("E_noise_study", "E 噪声研究（负例返回率）"),
                           ("F_forgetting_study", "F 遗忘研究"),
                           ("C_compression_study", "C 压缩研究"),
                           ("S_sensitivity", "S 敏感性扫描")):
        if section in report:
            print(f"\n【{title}】")
            for k, v in report[section].items():
                print(f"  {k}: {v}")
    if "task_layer_note" in report:
        print("\n【任务层说明】", report["task_layer_note"])
    print("\n【诚实边界】", report["_meta"]["honesty"])
    print("=" * 78)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="只跑 G0–G6 主线")
    ap.add_argument("--json", default="", help="报告落盘路径")
    args = ap.parse_args()
    rep = run_all(quick=args.quick)
    print_report(rep)
    out = args.json or os.path.join(os.path.dirname(__file__),
                                    "results", "ablation_report.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, default=str)
    print(f"[报告已落盘] {out}")
