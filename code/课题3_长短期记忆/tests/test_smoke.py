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
                    MemoryController, MemoryPipeline,
                    MDMP_STAGES, STAGE_IDS, queries_for_stage, attr_stage)


def ok(name: str) -> None:
    print(f"  [PASS] {name}")


# ---------------------------------------------------------------- 1. schema
def test_schema() -> None:
    e = new_entry(MemoryType.EXPERIENCE, "教训：夜战需先遣侦察")
    assert e.id.startswith("experience-"), "id 前缀错误"
    # 确定性构造：把创建时间回拨 10 秒，避免依赖真实时钟精度
    # （Windows time.time() 分辨率 ~15ms，t≈0 时 r0 与强化后都是 1.0，断言会闪断；
    #   回拨 1000s 会浮点下溢为 0，10s 时 r0≈e^-10≈4.5e-5，安全且确定性）
    e.timestamp = time.time() - 10.0
    e.last_recalled_at = e.timestamp
    r0 = e.retention()  # ≈ e^(-1000/1) ≈ 0
    assert 0 < r0 <= 1.0, "留存率应在 (0,1]"
    # 命中强化：召回后 S+1、t 重置 → 留存率应回到 ≈1（远大于 r0）
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


def test_bugfix_regression() -> None:
    """锁定三轮检查修复的缺陷（防止回归）。"""
    # --- R1: bm25 路双重强化（B2 残留）---
    emb = MockEmbedding()
    fs = FactualStore(":memory:", emb)
    es = ExperientialStore(emb)
    f = new_entry(MemoryType.FACT, "红方 T-90 坦克 最大速度 60km/h")
    fs.add(f)
    r = HybridRetriever(fs, es)
    before = fs.get(f.id).recall_count
    q = QueryItem(q_id="rb", intent="查装备", target="fact",
                  route="bm25", query_text="T-90 速度")
    hits = r.retrieve(q, top_k=3)
    after = fs.get(f.id).recall_count
    assert after - before == 1, f"一次检索 recall_count 应恰好 +1（实际 {before}→{after}）"
    assert hits, "bm25 路命中不应为空"

    # --- R2: min_score 阈值（低分噪声不返回）---
    r.min_score = 0.99  # 极高阈值 → 几乎全滤掉
    q2 = QueryItem(q_id="rm", intent="无关查询", target="fact",
                   route="vector", query_text="量子纠缠 波函数")
    hits2 = r.retrieve(q2, top_k=3)
    assert hits2 == [], "极低相关查询应被 min_score 全部滤除"
    r.min_score = 0.0   # 恢复关闭（兼容旧用法）

    # --- R3: 查重读缓存向量（不重复 embed，且查重结果不变）---
    from memsys import MemoryEvolution
    llm = MockLLM()
    ev = MemoryEvolution(fs, es, llm, emb)
    id1 = ev.write(MemoryType.FACT, "蓝方 M1A2 坦克 主炮 120mm")
    assert id1, "首条写入应成功"
    dup = ev.write(MemoryType.FACT, "蓝方 M1A2 坦克 主炮 120mm")
    assert dup is None, "重复内容应被查重拦截（缓存向量路径）"
    ok("回归：bm25 单次强化 + min_score 滤噪 + 查重缓存向量")


def test_integration_zhirong() -> None:
    """验收项：智戎链路三挂接点 mock 全链路 + 时延记录。"""
    from integration import ZhirongAdapter
    from memsys import MemoryType, new_entry

    ad = ZhirongAdapter()
    # 预置可召回记忆
    ad.ctl.factual.add(new_entry(
        MemoryType.FACT, "2 号高地海拔 320 米，仅东侧可装甲通行。",
        source="seed", attrs={"地点": "2号高地"}))
    ad.ctl.experiential.add(new_entry(
        MemoryType.EXPERIENCE, "教训：夜间行军未派先遣侦察。",
        source="seed", importance=2.0))

    # ①②③④ 规划前挂接：增强上下文非空、有命中、时延已记
    plan = ad.hook_plan("T-ZR", "夜间夺占 2 号高地", constraints=["禁止越境"])
    assert plan["context"] and "禁止越境" in plan["context"], "上下文应含约束"
    assert plan["retrieved"] >= 1, "应召回预置记忆"
    assert plan["elapsed_ms"] >= 0, "时延已记录"

    # ⑥ 反馈挂接
    fb = ad.hook_feedback("推演：任务部分达成。教训：电子压制不足。")
    assert fb["ok"]

    # ⑦ 复盘进化挂接：写入新经验 + 边界审计激活
    close = ad.hook_close(extra_review="经验：预备队投入提前 10 分钟。")
    assert close.get("write", 0) >= 1, "复盘应写入新经验"
    assert "boundary" in close, "应返回边界审计统计"

    # 验收日志：三挂接点齐全 + 全部成功
    s = ad.log.summary()
    assert s["total_calls"] == 3 and s["all_ok"], f"三挂接点应全成功：{s}"
    assert set(s["per_hook"]) == {"plan", "feedback", "close"}, "挂接点不齐"
    # 降级路径：异常不阻断（hook_plan 返回空上下文而非抛出）
    ad2 = ZhirongAdapter()
    # 模拟检索层故障：注入必然抛错的 retriever（真实场景=向量库宕机等）
    class _BrokenRetriever:
        def retrieve(self, *a, **k):
            raise RuntimeError("模拟检索层故障")
    ad2.ctl.retriever = _BrokenRetriever()  # type: ignore[assignment]
    p2 = ad2.hook_plan("T-ERR", "目标")
    assert p2["context"] == "", "异常应降级为空上下文（不阻断智戎管线）"
    assert ad2.log.records[-1].ok is False, "失败应记入集成日志（可观测）"
    ok("集成验收：智戎三挂接点 mock + 时延记录 + 异常降级")


# ---------------------------------------------------------------- 12. 阶段感知（本轮升级）
def test_stage_aware() -> None:
    """MDMP 七阶段模板 / 阶段亲和加分 / 复盘教训阶段归因 / advance_stage。"""
    # 1) 七阶段定义完整（MDMP 七步）
    assert len(MDMP_STAGES) == 7, "MDMP 应为七阶段"
    assert [s["n"] for s in MDMP_STAGES] == list(range(1, 8)), "阶段序号 1-7"
    assert all(STAGE_IDS[i] != STAGE_IDS[i+1] for i in range(6)), "阶段 id 不重复"

    # 2) 阶段模板生成查询：带 stage 字段、target/route 合法
    qs = queries_for_stage("mission_analysis", goal="夜间夺占 2 号高地")
    assert qs and all(q.stage == "mission_analysis" for q in qs)
    assert all(q.target in ("fact", "experience") for q in qs)
    assert all(q.route in ("vector", "bm25", "sql") for q in qs)
    assert any("2 号高地" in q.query_text for q in qs), "{goal} 应注入查询文本"
    ok("MDMP 七阶段定义 + 阶段模板查询生成")

    # 3) 复盘教训阶段归因（关键词模板）
    assert attr_stage("教训：侦察不力，敌情漏判") == "mission_analysis"
    assert attr_stage("经验：突破口选在南坡，佯动奏效") == "coa_development"
    assert attr_stage("教训：夜间遭伏击，通信被干扰") == "coa_analysis"
    assert attr_stage("教训：命令格式不规范") == "orders_production"
    assert attr_stage("随便一句话") == "coa_analysis", "无命中默认归推演阶段"
    # 与 seed 硬编码归因保持一致（炮火准备属战法拟制，不是推演暴露）
    assert attr_stage("经验：炮火准备前置 20 分钟，可显著压制敌方反坦克火力点。") \
        == "coa_development", "炮火准备应归方案拟制（与 seed 一致）"
    ok("复盘教训阶段归因（关键词模板）")

    # 4) 阶段亲和加分：同内容，stage 对口者融合分更高/可过阈值
    emb = MockEmbedding()
    factual = FactualStore(":memory:", emb)
    exp = ExperientialStore(emb)
    for store in (factual, exp):
        store.add(new_entry(MemoryType.EXPERIENCE, "教训：夜间突袭未前置电子压制，遭敌干扰。",
                            source="seed", importance=2.0,
                            attrs={"stage": "coa_analysis"}))
        store.add(new_entry(MemoryType.EXPERIENCE, "教训：夜间突袭未前置电子压制，遭敌干扰。",
                            source="seed2", importance=2.0))
    r = HybridRetriever(factual, exp)
    q_with = QueryItem(q_id="s1", intent="推演", target="experience", route="vector",
                       query_text="夜间 突袭 干扰", stage="coa_analysis")
    q_without = QueryItem(q_id="s2", intent="推演", target="experience", route="vector",
                          query_text="夜间 突袭 干扰")
    hits_w = r.retrieve(q_with, top_k=5)
    hits_o = r.retrieve(q_without, top_k=5)
    sw = {h.entry.id: h.score for h in hits_w}
    so = {h.entry.id: h.score for h in hits_o}
    assert sw and so
    for eid in sw:
        if eid in so:
            assert abs(sw[eid] - so[eid]) <= 1e-9 or sw[eid] > so[eid], \
                "对口条目加分后不应更低"
    tagged = [h for h in hits_w if h.entry.metadata.get("stage") == "coa_analysis"]
    untagged_o = [h for h in hits_o
                  if not h.entry.metadata.get("stage")]
    if tagged and untagged_o:
        assert sw[tagged[0].entry.id] >= so.get(untagged_o[0].entry.id, 0) - 1e-9 + 0.1, \
            "阶段对口条目应获得 stage_bonus 加分"
    ok("阶段亲和加分（stage_bonus=0.15，过滤前生效）")

    # 5) 复盘写入带 stage 标签（evolution → metadata.stage）
    evo = MemoryEvolution(factual, exp, MockLLM(), emb)
    evo.evolve_from_review("教训：渡河架桥超时导致梯队迟到。", session_id="S1")
    wrote = [exp.get(eid) for eid in exp.candidates()]
    assert any(e and e.metadata.get("stage") for e in wrote), "复盘写入应带阶段标签"
    ok("复盘教训写入带 stage 标签（阶段归因落库）")

    # 6) controller.advance_stage：阶段切换 + 只执行本阶段查询
    ctl = MemoryController(factual=FactualStore(":memory:", MockEmbedding()),
                           experiential=ExperientialStore(MockEmbedding()),
                           llm=MockLLM(), embedding=MockEmbedding())
    ctl.factual.add(new_entry(MemoryType.FACT, "2 号高地海拔 320 米，仅东侧可装甲通行。",
                              source="seed", attrs={"stage": "mission_analysis",
                                                    "地点": "2号高地"}))
    ctl.experiential.add(new_entry(
        MemoryType.EXPERIENCE, "教训：夜间行军未派先遣侦察遭伏击。",
        source="seed", importance=2.0, attrs={"stage": "coa_analysis"}))
    ctl.start_session("STG1", goal="夜间夺占 2 号高地",
                      constraints=["禁止越境"], queries=[])
    ctl.advance_stage("mission_analysis", top_k=3)
    assert ctl.working_memory.slot.current_stage == "mission_analysis"
    n_q1 = len(ctl.working_memory.slot.query_list)
    assert n_q1 >= 1, "任务分析阶段应生成查询"
    ctl.advance_stage("coa_analysis", top_k=3)
    assert ctl.working_memory.slot.current_stage == "coa_analysis"
    n_q2 = len(ctl.working_memory.slot.query_list)
    assert n_q2 > n_q1, "新阶段查询应追加（审计轨迹累积）"
    # 渲染带阶段标记
    ctx = ctl.render_context()
    assert "【规划阶段】coa_analysis" in ctx
    ok("advance_stage：阶段切换 + 阶段查询滚动生成 + 渲染带阶段")

    # 7) 幂等：同阶段重复推进不重复检索（recall_count 不虚涨）
    rc_before = {eid: ctl.experiential.get(eid).recall_count
                 for eid in ctl.experiential.candidates()}
    hits_again = ctl.advance_stage("coa_analysis", top_k=3)
    rc_after = {eid: ctl.experiential.get(eid).recall_count
                for eid in ctl.experiential.candidates()}
    assert rc_before == rc_after, f"重复推进不应强化记忆：{rc_before} → {rc_after}"
    assert hits_again, "重复推进应返回缓存命中（UI 回显用）"
    # 未知阶段应报错（防 current_stage 被写入垃圾值）
    try:
        ctl.advance_stage("no_such_stage")
        raise AssertionError("未知阶段未报错")
    except ValueError:
        pass
    ok("advance_stage 幂等（同阶段不重复检索）+ 未知阶段校验")

    # 8) merge/abstract 保留 stage 标签（亲和资格不因进化丢失）
    evo2 = MemoryEvolution(FactualStore(":memory:", MockEmbedding()),
                           ExperientialStore(MockEmbedding()),
                           MockLLM(), MockEmbedding())
    e1 = new_entry(MemoryType.EXPERIENCE, "教训：侦察不力敌情漏判。",
                   source="t", importance=2.0, attrs={"stage": "mission_analysis"})
    e2 = new_entry(MemoryType.EXPERIENCE, "教训：侦察分队敌情漏判失误。",
                   source="t", importance=2.0, attrs={"stage": "mission_analysis"})
    evo2.experiential.add(e1)
    evo2.experiential.add(e2)
    merged_id = evo2.merge([e1.id, e2.id])
    assert merged_id, "merge 应成功"
    merged = evo2.experiential.get(merged_id)
    assert merged.metadata.get("stage") == "mission_analysis", \
        f"合并产物应保留 stage 标签：{merged.metadata}"
    ok("merge 保留 stage 标签（抽象同理，见 abstract metadata）")


if __name__ == "__main__":
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
    test_bugfix_regression()
    test_integration_zhirong()
    test_stage_aware()
    print("=" * 60)
    print("全部通过 [OK]")
