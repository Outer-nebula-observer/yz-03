# -*- coding: utf-8 -*-
"""
examples.campaign_demo — 多轮作战案例《高地群攻防战役》CLI 演示
================================================================
用法：
    python examples/campaign_demo.py              # Mock（离线，推荐演示）
    python examples/campaign_demo.py --real       # 用 DeepSeek 真模型（需 .env 有效 Key）
    python examples/campaign_demo.py --json out.json  # 结果落盘

过程：连续跑 5 场，逐场打印：
  ① 目标/约束 → ③ 检索命中（含来源溯源）→ 复用检测（命中往场复盘沉淀）
  → ⑤ 规划输出摘要 → ⑦ 进化报告（write/merge/forget/abstract/skip）
  → 库规模。最后输出"战役记忆轨迹"统计表。

与 WebUI 的对应：本脚本做的是 https://webui 的"一键导入 + 逐步进行"
同一套数据（campaign/campaign_data.py）的离线命令行版。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memsys import (MemoryController, MemoryType, QueryItem, new_entry,
                    FactualStore, ExperientialStore, MockEmbedding,
                    get_llm, get_embedding)
from campaign.campaign_data import CAMPAIGNS, SEED_FACTS, SEED_EXPS


def _safe_embedding(enable_glm: bool = False):
    """可靠的 embedding 选择：默认 Mock；enable_glm 且 GLM Key 可用才用真向量。

    注意：get_embedding('glm') 构造成功不代表 Key 有效——必须实际 embed 一次
    验证（GLM Key 失效时 embed 才报 401，若不试就回退会污染后续检索）。
    """
    if enable_glm:
        try:
            emb = get_embedding("glm")
            emb.embed("连通性校验")
            return emb
        except Exception:
            print("[提示] GLM embedding 不可用（Key 失效或网络异常），回退 MockEmbedding")
    return MockEmbedding()


def build_controller(real: bool = False, enable_glm_embed: bool = False) -> MemoryController:
    """Mock 或 DeepSeek 真模型的 controller（embedding 默认 Mock，可选 GLM）。"""
    if real:
        try:
            llm = get_llm("deepseek")
        except Exception:
            print("[提示] DeepSeek Key 不可用，回退 MockLLM")
            llm = None
    else:
        llm = None
    emb = _safe_embedding(enable_glm_embed)
    ctl = MemoryController(factual=FactualStore(":memory:", emb),
                           experiential=ExperientialStore(emb),
                           llm=llm, embedding=emb)
    return ctl


def seed_campaign(ctl: MemoryController) -> None:
    """注入战役种子记忆（sha1 确定性 id，跨进程可复现）。"""
    import hashlib as _h
    for content, attrs in SEED_FACTS:
        e = new_entry(MemoryType.FACT, content, source="campaign-seed", attrs=attrs)
        e.id = "seed-f-" + _h.sha1(content.encode("utf-8")).hexdigest()[:10]
        ctl.factual.add(e)
    for content, imp, stage in SEED_EXPS:
        e = new_entry(MemoryType.EXPERIENCE, content, source="campaign-seed",
                      importance=imp, attrs={"stage": stage})
        e.id = "seed-e-" + _h.sha1(content.encode("utf-8")).hexdigest()[:10]
        ctl.experiential.add(e)


def run_one_round(ctl: MemoryController, rd: dict, top_k: int = 3) -> dict:
    """跑一场完整闭环，返回该场结果（检索/规划/进化/复用/库规模）。"""
    queries = [QueryItem(q["intent"], q["intent"], q["target"], q["route"],
                         q.get("query_text", ""), attrs=q.get("attrs"))
               for q in rd["queries"]]
    ctl.start_session(rd["plan_id"], rd["goal"], rd["constraints"], queries)
    hits = ctl.retrieve_and_load(top_k=top_k)
    context = ctl.render_context()
    plan = ctl.llm.chat("你是作战规划智能体。基于以下记忆上下文生成规划方案（要点式）。",
                        context)
    for msg in rd.get("messages", []):
        ctl.push(msg)
    report = ctl.close_session(rd["review"])

    # 复用检测：命中里来自往场复盘（source 以 复盘: 开头，且 session != 本场）
    reused = []
    for h in hits:
        if h.entry.source.startswith("复盘:") and h.entry.session_id != rd["plan_id"]:
            reused.append({"source": h.entry.source,
                           "session_id": h.entry.session_id,
                           "content": h.entry.content[:60]})
    return {
        "plan_id": rd["plan_id"],
        "title": rd["title"],
        "retrieved": [{"id": h.entry.id[:12], "type": h.entry.type.value,
                       "route": h.route, "score": round(h.score, 3),
                       "source": h.entry.source, "session": h.entry.session_id,
                       "content": h.entry.content[:70]}
                      for h in hits],
        "reused": reused,
        "plan_output": plan[:180],
        "report": report.summary(),
        "store": {"facts": ctl.factual.stats()["count"],
                  "exps": ctl.experiential.stats()["count"]},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="用 DeepSeek 真模型生成规划/抽取")
    ap.add_argument("--embed-glm", action="store_true",
                    help="尝试用 GLM embedding（Key 失效则自动回退 Mock）")
    ap.add_argument("--json", default="", help="结果落盘路径（.json）")
    args = ap.parse_args()

    camp = CAMPAIGNS["heights_battle"]
    print("=" * 76)
    print(f"多轮作战案例：{camp['title']}")
    print("=" * 76)
    ctl = build_controller(args.real, args.embed_glm)
    seed_campaign(ctl)
    mode = "DeepSeek(real)" if args.real else "Mock"
    print(f"[LLM={mode}] 预置战役种子：事实 {len(SEED_FACTS)} 条 / 经验 {len(SEED_EXPS)} 条\n")

    results = []
    for i, rd in enumerate(camp["rounds"], start=1):
        t0 = time.time()
        r = run_one_round(ctl, rd)
        r["elapsed_s"] = round(time.time() - t0, 1)
        results.append(r)
        print("-" * 76)
        print(f"① {r['plan_id']}｜{r['title']}")
        print(f"   目标：{rd['goal']}")
        print(f"   ️③ 检索命中 {len(r['retrieved'])} 条：")
        for h in r["retrieved"]:
            mark = "🔄" if h["source"].startswith("复盘:") else "  "
            print(f"    {mark} [{h['type']}/{h['route']}] {h['content']} "
                  f"(src={h['source'] or 'seed'}/{h['session'] or '-'})")
        if r["reused"]:
            print(f"   ♻️ 跨场次复用 {len(r['reused'])} 条：")
            for u in r["reused"]:
                print(f"      ← {u['source']}｜{u['content']}")
        else:
            print("   ♻️ 无往场复用（本场" + ("应无" if not rd.get("expect_reuse") else "有预期但未命中——请检查检索阈值/查询") + ")")
        print(f"   ⑤ 规划输出：{r['plan_output']}…")
        print(f"   ⑦ 进化报告：{r['report']}")
        print(f"   库规模：事实 {r['store']['facts']} / 经验 {r['store']['exps']} "
              f"（本轮耗时 {r['elapsed_s']}s）")

    print("\n" + "=" * 76)
    print("📊 战役记忆轨迹（每场复用/沉淀汇总）")
    print("-" * 76)
    print(f"{'场次':<6}{'检索':<5}{'复用数':<7}{'写入':<5}{'合并':<5}{'遗忘':<5}{'抽象':<5}{'去重跳过':<7}{'经验库'}")
    for r in results:
        rep = r["report"]
        print(f"{r['plan_id']:<6}{len(r['retrieved']):<5}{len(r['reused']):<7}"
              f"{rep['write']:<5}{rep['merge']:<5}{rep['forget']:<5}"
              f"{rep['abstract']:<5}{rep['skip_duplicate']:<7}{r['store']['exps']}")
    total_reuse = sum(len(r["reused"]) for r in results)
    print(f"\n五场累计跨场次复用 {total_reuse} 次；经验库由 {len(SEED_EXPS)} 条增长到 "
          f"{results[-1]['store']['exps']} 条。")
    print("演示完成：前场教训被后场召回、重复复盘被查重、经验抽象为通用教训——"
          "记忆系统在连续作战中的价值全链路可见。")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"campaign": camp["title"], "mode": mode, "rounds": results},
                      f, ensure_ascii=False, indent=2, default=str)
        print(f"[结果已落盘] {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
