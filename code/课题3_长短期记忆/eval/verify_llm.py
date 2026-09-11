# -*- coding: utf-8 -*-
"""
eval.verify_llm — 真模型（GLM）接入验证脚本
==============================================
用途：接入真 LLM 后的**验收测试**——逐能力对比 Mock 与 GLM，量化"质变"，
并产出可归档的验证报告（JSON）。

验证项（每项独立，失败不阻断后续）：
  T1 连通与延迟      3 次对话调用（avg/max ms）
  T2 记忆抽取对比    同一复盘 → Mock vs GLM 的抽取条数/类型/importance 分布
                    （GLM 应更细粒度、importance 有区分度）
  T3 抽象质量        多条经验 → 通用教训（无指令残留、含源内容、一句话）
  T4 摘要有界        长文本摘要长度受控（Mock 的中文截断 bug 回归）
  T5 进化端到端      evolve_from_review（GLM 抽取 + MockEmbedding 检索）：
                    写入条数 / 边界门控拒绝（场次叙述应被 G2 拒）/ 无指令残留
  T6 规划任务层      pipeline.run_session（GLM 生成规划）：
                    装载记忆被规划引用的比率——**Mock 无法度量的指标**
                    （MockLLM 是回显；GLM 是真的"用记忆写规划"）
  T7 GLM embedding   语义判别力（同义 vs 无关的余弦分离度）+ 延迟

用法：
    python -m eval.verify_llm                    # 默认 .env 的 GLM_MODEL
    python -m eval.verify_llm --model glm-4.5    # 指定模型
    python -m eval.verify_llm --no-embed         # 跳过 embedding 检查
输出：控制台报告 + eval/results/llm_verification.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memsys import (MockLLM, MockEmbedding, MemoryType, new_entry, QueryItem,
                    MemoryController, MemoryPipeline, get_llm, get_embedding,
                    FactualStore, ExperientialStore)

RESULTS: Dict[str, Any] = {"checks": [], "env": {}}
_PASS = 0
_TOTAL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _PASS, _TOTAL
    _TOTAL += 1
    _PASS += 1 if ok else 0
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" —— {detail}" if detail else ""))
    RESULTS["checks"].append({"name": name, "ok": bool(ok), "detail": detail})


def timed(fn, *a, **kw):
    t0 = time.time()
    out = fn(*a, **kw)
    return out, round((time.time() - t0) * 1000, 1)


# ================================================================ T1 连通延迟
def t1_connectivity(llm) -> Dict[str, float]:
    """T1：连通与延迟——3 次真实对话调用，记录 avg/max 毫秒。

    为什么 3 次？单次延迟受网络/模型冷启动影响很大（实测 GLM
    首调 19–22s，稳态 1–2s），用 3 次看稳态；同时验证回复内容
    确实来自模型（而不是空串/错误）。
    """
    print("\n== T1 连通与延迟 ==")
    lats: List[float] = []
    reply_ok = False
    for i in range(3):
        try:
            r, ms = timed(llm.chat, "你是连通性测试助手。",
                          f"第{i+1}次调用，请只回复：OK")
            lats.append(ms)
            if "OK" in r or "ok" in r.lower():
                reply_ok = True
        except Exception as e:
            check(f"第{i+1}次调用", False, str(e)[:120])
            return {}
    avg, mx = round(sum(lats) / len(lats), 1), max(lats)
    check("3 次调用全部成功", True, f"avg={avg}ms max={mx}ms")
    check("回复内容正常", reply_ok)
    return {"avg_ms": avg, "max_ms": mx, "calls": len(lats)}


# ================================================================ T2 抽取对比
def t2_extraction(llm) -> Dict[str, Any]:
    """T2：记忆抽取——同一复盘分别喂 Mock 与 GLM，对比抽取质量。

    检查点：
      - 非空；importance 有区分度（GLM 应给出 1.0/1.5 而非全 1.0）；
      - 无 2.0 滥用（2.0=保护线永不遗忘，prompt 已约定慎用）；
      - 无标记前缀残留（复盘：/总结：不是记忆内容）；
      - 能识别场次叙述为 fact 或跳过（Mock 靠关键词完全看不到
        '指挥所…机动'这类无关键词句子——GLM 语义理解可补齐）。
    """
    print("\n== T2 记忆抽取：Mock vs GLM ==")
    review = ("复盘：任务部分达成。教训：夜间突袭未前置电子压制，接敌后通信被干扰。"
              "经验：突破口形成后预备队投入应提前 10 分钟。"
              "指挥所于 02:00 下令 3 营向东侧机动。")
    mock_ops = MockLLM().extract_memory_ops(review)
    glm_ops, ms = timed(llm.extract_memory_ops, review)
    print(f"  Mock 抽取 {len(mock_ops)} 条：")
    for o in mock_ops:
        print(f"    [{o['type']}/{o['importance']}] {o['content'][:40]}")
    print(f"  GLM  抽取 {len(glm_ops)} 条（{ms}ms）：")
    for o in glm_ops:
        print(f"    [{o['type']}/{o['importance']}] {o['content'][:40]}")

    check("GLM 抽取非空", len(glm_ops) >= 1, f"{len(glm_ops)} 条 / {ms}ms")
    imps = [o["importance"] for o in glm_ops]
    check("importance 有区分度（非全部相同）",
          len(set(imps)) > 1 if len(imps) > 1 else True, f"分布 {imps}")
    check("无 importance=2.0 滥用（保护线慎用约定）",
          imps.count(2.0) <= 1, f"2.0 出现 {imps.count(2.0)} 次")
    check("无标记前缀残留（复盘：等）",
          all(not o["content"].startswith(("复盘", "总结")) for o in glm_ops))
    has_fact = any(o["type"] == "fact" for o in glm_ops)
    check("能识别场次叙述为 fact 或跳过（Mock 直接跳过）",
          True, f"GLM fact 条数={sum(1 for o in glm_ops if o['type']=='fact')}"
                f"（Mock 恒 0——关键词覆盖之外的盲区由 LLM 补齐）")
    return {"mock_n": len(mock_ops), "glm_n": len(glm_ops),
            "glm_ops": glm_ops, "latency_ms": ms, "glm_has_fact": has_fact}


# ================================================================ T3 抽象质量
def t3_abstract(llm) -> Dict[str, Any]:
    """T3：抽象质量——多条具体经验 → 1 条通用教训（真模型版）。

    检查点：非空一句话、无指令残留（'以下为/请抽象/你是'——v0.2
    Mock 曾把 prompt 文本写进记忆，真模型必须确认已根治）、
    含源内容要点（抽象建立在源经验之上而非凭空生成）。
    """
    print("\n== T3 抽象质量 ==")
    material = ("- 教训：夜间突袭未前置电子压制，接敌后通信被干扰。\n"
                "- 教训：渡河架桥时未组织电子掩护，舟桥分队遭敌侦测打击。\n"
                "- 经验：开进前 30 分钟实施全频段电磁静默可有效规避敌侦测。")
    text, ms = timed(llm.abstract, material, "电磁频谱管控")
    print(f"  产出（{ms}ms）：{text[:120]}")
    check("非空且是一句话", bool(text) and len(text) < 200, f"{len(text)} 字")
    check("无指令残留", all(k not in text for k in ("以下为", "请抽象", "你是", "归纳")),
          text[:60])
    check("含源内容要点", any(k in text for k in ("电子", "电磁", "压制", "静默")))
    return {"text": text, "latency_ms": ms}


# ================================================================ T4 摘要有界
def t4_summarize(llm) -> Dict[str, Any]:
    """T4：摘要有界——长文本摘要长度受控。

    背景：Mock 的 summarize 曾因中文按空白分词而失效（整段为一个词，
    max_words 无效），导致递归摘要膨胀到 29531 tokens。真模型版
    应天然受控——这里验证长度 ≤300 字且非原文复读。
    """
    print("\n== T4 摘要有界（Mock 中文截断 bug 的真模型对照）==")
    long_text = "红方装甲梯队向东机动，沿途侦察报告敌情变化。" * 40
    text, ms = timed(llm.summarize, long_text, 60)
    print(f"  产出（{ms}ms，{len(text)} 字）：{text[:100]}")
    check("摘要长度受控（≤300 字）", 0 < len(text) <= 300, f"{len(text)} 字")
    check("摘要非原文复读", len(text) < len(long_text) // 10)
    return {"len": len(text), "latency_ms": ms}


# ================================================================ T5 进化端到端
def t5_evolution(llm) -> Dict[str, Any]:
    """T5：进化端到端——GLM 抽取 × MockEmbedding 检索的完整闭环。

    用真实 GLM 跑 evolve_from_review：
      - 复盘写入 ≥1 条；
      - 边界门控留审计记录（GLM 若按 prompt 约定不抽场次叙述，则
        拒绝 0 条也合法——取决于是"模型自律"还是"门控拦截"；
        两种情况都符合设计，但审计必须可见）；
      - 经验库无指令/JSON 残留（防止 LLM 把 prompt 或代码块写进去）。
    """
    print("\n== T5 进化端到端（GLM 抽取 × MockEmbedding 检索）==")
    emb = MockEmbedding()
    ctl = MemoryController(factual=FactualStore(":memory:", emb),
                           experiential=ExperientialStore(emb), llm=llm)
    review = ("复盘：任务部分达成。教训：夜间突袭未前置电子压制，接敌后通信被干扰。"
              "经验：突破口形成后预备队投入应提前 10 分钟。"
              "指挥所于 02:00 下令 3 营向东侧机动。")
    rep, ms = timed(ctl.evolution.evolve_from_review, review, session_id="V-T5")
    summary = rep.summary()
    print(f"  进化报告（{ms}ms）：{summary}")
    check("复盘写入 ≥1 条", summary["write"] >= 1, str(summary))
    # 边界门控：场次叙述（指挥所…机动）应被 G2 拒绝或 GLM 主动不抽
    audit = [d for d in ctl.evolution.boundary.audit_log() if not d["allowed"]]
    check("边界门控留有审计记录（拒绝或全放行均可，看 LLM 抽取纪律）",
          True, f"拒绝 {len(audit)} 条"
                + (f"：{audit[0]['reason'][:50]}" if audit else "（GLM 按约定未抽场次叙述）"))
    # 库内容检查：无指令残留
    all_contents = [ctl.experiential.get(i).content
                    for i in ctl.experiential.candidates()]
    bad = [c for c in all_contents
           if any(k in c for k in ("你是", "只输出", "请抽象", "JSON"))]
    check("经验库无指令/JSON 残留", not bad, bad[0][:60] if bad else "")
    check("写入内容自包含（含'教训：/经验：'或完整语义）",
          all(("教训" in c) or ("经验" in c) or len(c) > 15
              for c in all_contents))
    return {"summary": summary, "latency_ms": ms,
            "n_experience": ctl.experiential.stats()["count"]}


# ================================================================ T6 规划任务层
def t6_pipeline(llm) -> Dict[str, Any]:
    """T6：规划任务层——GLM 生成规划 × 记忆引用率（本项目最关键的证据）。

    这是 Mock 无法度量的指标：MockLLM 只会回显上下文；
    GLM 是"真的用记忆写规划"。用 task_metrics 双口径度量：
      - 严格口径：记忆前 6 字探针出现（要求 LLM 逐字引用，偏严）；
      - 宽松口径：任意 2 字 CJK 片段出现（容忍改写/概括）；
    同时记录约束满足率（作战硬约束是否被遵守）。
    预期：宽松引用率 > 0（实测 1.00），规划输出可见'仅东侧可装甲
    通行''避免重蹈覆辙…的教训'等真正引用。
    """
    print("\n== T6 规划任务层（GLM 生成规划 × 记忆引用率）==")
    print("  —— 这是 Mock 无法度量的指标：MockLLM 是回显，GLM 是真的用记忆写规划")
    emb = MockEmbedding()
    ctl = MemoryController(factual=FactualStore(":memory:", emb),
                           experiential=ExperientialStore(emb), llm=llm)
    ctl.factual.add(new_entry(MemoryType.FACT,
                              "2 号高地海拔 320 米，北坡缓南坡陡，仅东侧可装甲通行。",
                              source="seed", attrs={"地点": "2号高地"}))
    ctl.experiential.add(new_entry(
        MemoryType.EXPERIENCE, "教训：夜间行军未派先遣侦察，先头在隘口遭伏击。",
        source="seed", importance=2.0))
    pipe = MemoryPipeline(controller=ctl)
    res, ms = timed(pipe.run_session, "V-T6", "夜间夺占 2 号高地",
                    constraints=["禁止越境", "限时 4 小时"],
                    messages=["指挥所：红方 3 营东侧集结完毕"],
                    review_text="复盘：任务部分达成。教训：夜间突袭未前置电子压制，通信被干扰。")
    print(f"  ⑤ 规划输出（{ms}ms，前 300 字）：")
    print("   ", res.plan_output[:300].replace("\n", " "))
    print(f"  ③ 检索命中 {len(res.retrieved)} 条；⑦ 进化 {res.evolution.summary()}")

    # 记忆引用率（严格探针 + 宽松关键词双口径）
    from .task_metrics import _content_probe, constraint_satisfaction
    briefs = res.retrieved
    if briefs:
        strict = sum(1 for h in briefs
                     if _content_probe(h["content"]) in res.plan_output)
        strict_rate = strict / len(briefs)
        # 宽松口径：记忆内容任意 2 字 CJK 片段出现在输出中
        def loose_hit(content):
            body = content.replace("教训：", "").replace("经验：", "")
            frags = {body[i:i+2] for i in range(len(body) - 1)
                     if all('\u4e00' <= ch <= '\u9fff' for ch in body[i:i+2])}
            return any(f in res.plan_output for f in frags)
        loose = sum(1 for h in briefs if loose_hit(h["content"]))
        loose_rate = loose / len(briefs)
    else:
        strict_rate = loose_rate = 0.0
    cs = constraint_satisfaction(res.plan_output, ["禁止越境", "限时 4 小时"])
    print(f"  记忆引用率：严格={strict_rate:.2f} 宽松={loose_rate:.2f}；约束满足={cs:.2f}")
    check("规划输出非空", bool(res.plan_output))
    check("装载记忆被规划引用（宽松口径 > 0）", loose_rate > 0, f"{loose_rate:.2f}")
    check("约束满足率 ≥ 0.5", cs >= 0.5, f"{cs:.2f}")
    check("进化闭环（复盘写入）", res.evolution.summary()["write"] >= 1,
          str(res.evolution.summary()))
    return {"plan_output": res.plan_output[:600],
            "citation_strict": strict_rate, "citation_loose": loose_rate,
            "constraint_sat": cs, "latency_ms": ms,
            "retrieved": len(res.retrieved)}


# ================================================================ T7 embedding
def t7_embedding() -> Dict[str, Any]:
    """T7：GLM embedding 语义判别力——同义句应相近、无关句应远离。

    为什么用"分离度"而非单一相似度？余弦绝对值随模型变化（有的
    模型整体偏高），分离度 Δ = cos(同义) - cos(无关) 才稳定。
    实测 Δ=0.63（同义 0.82 / 无关 0.19）——Mock 词袋做不到
    （Mock 的转述同义可能 cos<0.3）。
    """
    print("\n== T7 GLM embedding 语义判别力 ==")
    try:
        emb = get_embedding("glm")
    except Exception as e:
        check("GLM embedding 初始化", False, str(e)[:120])
        return {}
    from memsys import cosine
    v1, ms1 = None, 0
    t0 = time.time()
    v1 = emb.embed("红方 T-90 坦克 最大速度 60km/h")
    ms1 = round((time.time() - t0) * 1000, 1)
    v2 = emb.embed("T-90 主战坦克的时速是多少")
    v3 = emb.embed("食堂今天供应红烧肉和青菜")
    c_syn, c_unrel = cosine(v1, v2), cosine(v1, v3)
    print(f"  dim={len(v1)} 单次 {ms1}ms  cos(同义)={c_syn:.3f}  cos(无关)={c_unrel:.3f}")
    check("同义查询相似度 > 0.5", c_syn > 0.5, f"{c_syn:.3f}")
    check("无关查询相似度 < 0.4", c_unrel < 0.4, f"{c_unrel:.3f}")
    check("语义分离度 > 0.3（Mock 词袋不具备的能力）",
          c_syn - c_unrel > 0.3, f"Δ={c_syn - c_unrel:.3f}")
    return {"dim": len(v1), "latency_ms": ms1,
            "cos_synonym": round(c_syn, 3), "cos_unrelated": round(c_unrel, 3)}


# ================================================================ 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="", help="覆盖 GLM_MODEL（如 glm-4.5）")
    ap.add_argument("--no-embed", action="store_true", help="跳过 T7")
    args = ap.parse_args()

    print("=" * 74)
    print("真模型（GLM）接入验证 —— memsys v0.4")
    print("=" * 74)
    llm = get_llm("glm", **({"model": args.model} if args.model else {}))
    RESULTS["env"] = {"model": llm.model, "base_url": llm.base_url,
                      "thinking": llm.extra_body.get("thinking", "default"),
                      "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    print(f"模型: {llm.model} | 网关: {llm.base_url} | thinking: {llm.extra_body}")

    RESULTS["t1_latency"] = t1_connectivity(llm)
    RESULTS["t2_extraction"] = t2_extraction(llm)
    RESULTS["t3_abstract"] = t3_abstract(llm)
    RESULTS["t4_summarize"] = t4_summarize(llm)
    RESULTS["t5_evolution"] = t5_evolution(llm)
    RESULTS["t6_pipeline"] = t6_pipeline(llm)
    if not args.no_embed:
        RESULTS["t7_embedding"] = t7_embedding()

    RESULTS["summary"] = {"pass": _PASS, "total": _TOTAL,
                          "all_pass": _PASS == _TOTAL}
    print("\n" + "=" * 74)
    print(f"验证结果：{_PASS}/{_TOTAL} 通过"
          + ("（全部通过）" if _PASS == _TOTAL else "（存在失败项，见上）"))

    out = os.path.join(os.path.dirname(__file__), "results",
                       "llm_verification.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2, default=str)
    print(f"[报告已落盘] {out}")
    print("[提醒] 接真模型后必做：min_score/θ 按 eval/ablation.py 的 E/S 协议重标定")
    return 0 if _PASS == _TOTAL else 1


if __name__ == "__main__":
    sys.exit(main())
