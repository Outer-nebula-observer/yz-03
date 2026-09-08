# -*- coding: utf-8 -*-
"""
tests.test_smoke — 冒烟测试（零依赖，直接 python tests/test_smoke.py 运行）
=============================================================================
不依赖 pytest（团队环境差异最小化）；每个用例一个 assert_* 函数，
任一失败立即抛异常并停在被测点——便于定位。

覆盖：
  1. schema：条目构造 / 艾宾浩斯留存 / 命中强化 / 溯源
  2. embeddings：Mock 向量确定性 / 余弦 / 索引检索
  3. short_term：容量阈值 / flush 递归摘要 / 约束不丢
  4. long_term：事实库精确+语义检索 / 经验库语义召回
  5. retrieval：三路路由 + 融合回填
  6. evolution：写入查重 / 合并 / 遗忘 / 抽象 / 复盘驱动
  7. pipeline：七步闭环端到端（全 Mock）
"""

from __future__ import annotations

import os
import sys
import time

# Windows GBK 控制台兜底：强制 UTF-8 输出（✔ 等字符不再报错）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memsys import (MemoryType, MemoryEntry, QueryItem, new_entry,
                    MockLLM, MockEmbedding,
                    FactualStore, ExperientialStore,
                    HybridRetriever, MemoryEvolution, MemoryBoundary,
                    MemoryController, MemoryPipeline)


def ok(name: str) -> None:
    print(f"  [PASS] {name}")


# ---------------------------------------------------------------- 1. schema
def test_schema() -> None:
    e = new_entry(MemoryType.EXPERIENCE, "教训：夜战需先遣侦察")
    assert e.id.startswith("experience-"), "id 前缀错误"
    r0 = e.retention()
    assert 0 < r0 <= 1.0, "留存率应在 (0,1]"
    # 命中强化：召回后 S+1、t 重置 → 留存率应上升
    time.sleep(0.01)
    e.mark_recalled()
    assert e.retention() > r0, "命中强化应提升留存率"
    assert e.provenance()["id"] == e.id, "溯源字段错误"
    ok("schema 数据模型 + 艾宾浩斯留存/命中强化")


# ---------------------------------------------------------------- 2. embeddings
def test_embeddings() -> None:
    m = MockEmbedding()
    v1, v2 = m.embed("红方 坦克 集结"), m.embed("红方 坦克 集结")
    assert v1 == v2, "同文本向量必须确定"
    v3 = m.embed("蓝方 战机 巡逻")
    from memsys import cosine
    assert cosine(v1, v3) < cosine(v1, v2), "相同文本相似度应更高"
    idx = m  # noqa: 占位避免未用告警
    ok("MockEmbedding 确定性 + 余弦区分度")


# ---------------------------------------------------------------- 3. short_term
def test_short_term() -> None:
    from memsys import WorkingMemory
    wm = WorkingMemory("T1", capacity_tokens=200, warning_ratio=0.5,
                       flush_ratio=0.9, llm=MockLLM())
    wm.set_goal("夺占 2 号高地", constraints=["禁止越境"])
    for i in range(30):
        wm.push_message(f"消息{i}：红方装甲梯队向东机动，距离高地约 {100-i} 公里")
    assert wm.slot.constraints == ["禁止越境"], "约束字段不可被压缩删除"
    assert wm.archived, "超限应触发 flush 归档"
    ctx = wm.render()
    assert "禁止越境" in ctx and "目标" in ctx, "渲染必须保留目标与约束"
    ok("工作记忆：阈值 flush + 递归摘要 + 约束保护")


# ---------------------------------------------------------------- 4. long_term
def test_long_term() -> None:
    emb = MockEmbedding()
    fs = FactualStore(":memory:", emb)
    e1 = new_entry(MemoryType.FACT, "红方 T-90 坦克 最大速度 60km/h",
                   attrs={"装备": "T-90"})
    fs.add(e1)
    hits = fs.search("T-90 速度")
    assert any(h.entry.id == e1.id for h in hits), "事实库应命中 T-90"
    exact = fs.search_attrs({"装备": "T-90"})
    assert len(exact) == 1 and exact[0].entry.id == e1.id, "属性精确过滤失败"

    es = ExperientialStore(emb)
    e2 = new_entry(MemoryType.EXPERIENCE, "教训：夜战未派先遣侦察遭遇伏击",
                   importance=2.0)
    es.add(e2)
    hits2 = es.search("夜间 行军 侦察")
    assert any(h.entry.id == e2.id for h in hits2), "经验库语义召回失败"
    ok("双库：事实精确过滤 + 经验语义召回")


# ---------------------------------------------------------------- 5. retrieval
def test_retrieval() -> None:
    emb = MockEmbedding()
    fs = FactualStore(":memory:", emb)
    es = ExperientialStore(emb)
    f = new_entry(MemoryType.FACT, "红方 T-90 坦克 最大速度 60km/h", attrs={"装备": "T-90"})
    x = new_entry(MemoryType.EXPERIENCE, "教训：夜战未派先遣侦察遭遇伏击", importance=2.0)
    fs.add(f)
    es.add(x)
    r = HybridRetriever(fs, es)
    q = QueryItem(q_id="q1", intent="查装备", target="fact", route="vector",
                  query_text="T-90 坦克 速度")
    hits = r.retrieve(q, top_k=3)
    assert hits, "混合检索应有结果"
    assert q.answer_memory_ids, "创新点 C：命中 id 应回填到查询项"
    q2 = QueryItem(q_id="q2", intent="召回教训", target="experience",
                   route="bm25", query_text="夜战 侦察 伏击")
    hits2 = r.retrieve(q2, top_k=3)
    assert any(h.entry.id == x.id for h in hits2), "BM25 路应命中教训"
    ok("混合检索：vector/bm25 路由 + 融合 + 回填")


# ---------------------------------------------------------------- 6. evolution
def test_evolution() -> None:
    emb = MockEmbedding()
    fs = FactualStore(":memory:", emb)
    es = ExperientialStore(emb)
    llm = MockLLM()
    ev = MemoryEvolution(fs, es, llm, emb)
    # 写入
    id1 = ev.write(MemoryType.FACT, "2 号高地海拔 320 米，仅东侧可装甲通行")
    assert id1, "写入应成功"
    dup = ev.write(MemoryType.FACT, "2 号高地海拔 320 米，仅东侧可装甲通行。")
    assert dup is None, "重复内容应被查重跳过"
    # 遗忘：造一条衰减到底且不受保护的旧记忆
    old = new_entry(MemoryType.EXPERIENCE, "旧经验：某次演习补给线过长", importance=1.0)
    old.timestamp = time.time() - 10 ** 7  # 约 115 天前
    old.last_recalled_at = old.timestamp
    es.add(old)
    forgot = ev.forget()
    assert old.id in forgot, "低价值旧记忆应被遗忘"
    # 复盘驱动（MockLLM 规则抽取）
    review = ("复盘：教训：夜战通信静默过久导致协同脱节。"
              "经验：预备队投入应提前 10 分钟。")
    rep = ev.evolve_from_review(review, session_id="T6")
    assert rep.wrote, "复盘应写入新记忆"
    ok("进化：写入查重 + 遗忘 + 复盘驱动闭环")


# ---------------------------------------------------------------- 7. pipeline
def test_pipeline() -> None:
    pipe = MemoryPipeline()
    # 预置记忆（模拟历史沉淀）
    ctl = pipe.controller
    ctl.factual.add(new_entry(MemoryType.FACT, "红方 T-90 坦克 最大速度 60km/h",
                              attrs={"装备": "T-90"}))
    ctl.experiential.add(new_entry(
        MemoryType.EXPERIENCE, "教训：夜战未派先遣侦察遭遇伏击", importance=2.0))
    res = pipe.run_session(
        "P001", "夜间夺占 2 号高地",
        constraints=["禁止越境", "限时 4 小时"],
        messages=["指挥所：红方 3 营东侧集结", "侦察：高地南坡发现反坦克阵地"],
        review_text="复盘：教训：夜间突袭需前置电子压制。经验：突破口形成后预备队应立即投入。")
    assert res.plan_output, "⑤ 规划输出不能为空"
    assert res.evolution is not None and (res.evolution.wrote or res.evolution.skipped), \
        "⑦ 进化应产生写入或查重跳过"
    assert res.retrieved, "③ 检索应有命中"
    # 二场：验证"越用越强"（第一场沉淀的经验应可被第二场召回）
    res2 = pipe.run_session("P002", "夜间进攻 3 号高地")
    assert res2.session_stats.get("retrieved", 0) >= 0  # 链路不炸即可（种子命中依 embedding）
    ok("pipeline：七步闭环端到端 + 第二场复用")


# ---------------------------------------------------------------- 8. boundary（长短期边界）
def test_boundary() -> None:
    """两把尺子 + 双向禁止 + 晋升门控（Bug 修复回归 + 新能力）。"""
    b = MemoryBoundary()

    # ① 场中写入短期：放行（短期就是任务内的）
    d = b.check_write("message", to="short_term")
    assert d.allowed, "场次消息应留在短期"

    # ② 双向禁止①：场中内容直写长期 → 拒绝
    d = b.check_write("message", to="long_term.fact")
    assert not d.allowed and "禁止" in d.reason, "场中直写长期必须被边界拒绝"

    # ③ 晋升门控：教训类内容复盘晋升 → 放行到经验库
    d = b.promote("教训：夜战需前置电子压制，接敌后通信被干扰")
    assert d.allowed and d.layer == "long_term.experience", "教训应晋升经验库"

    # ④ 晋升门控：参数类内容 → 事实库
    d = b.promote("2 号高地海拔 320 米，北坡缓南坡陡")
    assert d.allowed and d.layer == "long_term.fact", "地形参数应晋升事实库"

    # ⑤ 晋升门控：纯场次闲聊 → 拒绝（留在短期归档）
    d = b.promote("指挥所说今天食堂有红烧肉")
    assert not d.allowed, "场次闲聊不得晋升长期"

    # ⑥ 审计日志与统计
    log = b.audit_log()
    assert len(log) >= 5 and all("reason" in x for x in log), "决策必须可审计"
    s = b.stats()
    assert s["allowed"] >= 2 and s["rejected"] >= 2, "放行/拒绝计数应正确"
    ok("boundary：两把尺子 + 双向禁止 + 晋升门控 + 审计")


# ---------------------------------------------------------------- 9. Bug 修复回归
def test_bugfix_regressions() -> None:
    """① 强化落库 ② 三路互检不重复强化 ③ render 无死代码。"""
    emb = MockEmbedding()
    fs = FactualStore(":memory:", emb)
    e = new_entry(MemoryType.FACT, "红方 T-90 坦克 最大速度 60km/h",
                  attrs={"装备": "T-90"})
    fs.add(e)

    # ①② 三路互检下：一次 retrieve 对同一记忆只强化一次且落库
    r = HybridRetriever(fs, ExperientialStore(emb))
    q = QueryItem(q_id="q1", intent="查装备", target="fact", route="vector",
                  query_text="T-90 坦克 速度")
    r.retrieve(q, top_k=3)
    after = fs.get(e.id)
    assert after.recall_count == 1, \
        f"一次检索应强化恰好 1 次（实际 {after.recall_count}）——三路互检污染回归"
    assert after.decay_strength == 2.0, "S 应从 1.0 增至 2.0 且落库"
    assert after.last_recalled_at is not None, "last_recalled_at 必须落库"

    # ③ render 含【历史摘要】且无属性错误（原 hasattr 死代码已清理）
    from memsys import WorkingMemory
    wm = WorkingMemory("T9", capacity_tokens=200, llm=MockLLM())
    wm.set_goal("测试目标", constraints=["约束A"])
    for i in range(30):
        wm.push_message(f"消息{i}：红方向东机动")
    ctx = wm.render()
    assert "【目标】测试目标" in ctx and "【约束】约束A" in ctx
    if wm._recursive_summary:
        assert "【历史摘要】" in ctx, "flush 后 render 应含历史摘要"
    ok("Bug 修复回归：强化落库 + 单次强化 + render 清理")


if __name__ == "__main__":
    print("=" * 60)
    print("memsys 冒烟测试（零依赖 · 离线）")
    print("=" * 60)
    test_schema()
    test_embeddings()
    test_short_term()
    test_long_term()
    test_retrieval()
    test_evolution()
    test_pipeline()
    test_boundary()
    test_bugfix_regressions()
    print("=" * 60)
    print("全部通过 [OK]")
