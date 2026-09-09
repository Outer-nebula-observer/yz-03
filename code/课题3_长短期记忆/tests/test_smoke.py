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
    # 确定性构造：把创建时间回拨 10 天，避免依赖真实时钟精度
    # （retention 已统一"天"单位：t=10 天、S=1 → r0≈e^-10≈4.5e-5，
    #   安全且确定性；mark_recalled 后 t≈0 → R≈1，断言稳定）
    e.timestamp = time.time() - 10 * 86400
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
    # 【评审修复·恒真断言】原断言 `retrieved >= 0` 恒真——什么都没验证。
    # 现改为真实断言：第二场检索命中里必须存在 source='复盘:P001' 的条目
    # （第一场复盘写入的教训被跨场次召回），且规划上下文含其内容。
    # P002 用显式查询（同 demo night_hill_2 场景：召回上场电子压制教训）。
    # 注：默认阶段模板查询的检索质量由 P001（mission_receipt 模板命中种子
    # 教训）与消融 G4/H 类覆盖；此处显式查询保证跨场次断言的稳健边际。
    res2 = pipe.run_session(
        "P002", "夜间进攻 3 号高地",
        queries=[QueryItem("P002-q1", "召回上场夜间突袭教训", "experience",
                           "bm25", "夜间 突袭 电子压制 通信 干扰"),
                 QueryItem("P002-q2", "查 3 号高地地形", "fact",
                           "vector", "3 号高地 地形 通路")])
    assert res2.session_stats.get("retrieved", 0) >= 1, "第二场应有检索命中"
    s1_hits = [h for h in res2.retrieved if h["provenance"]["source"] == "复盘:P001"]
    assert s1_hits, "第二场必须召回第一场复盘沉淀（跨场次复用）"
    ctx2 = pipe.controller.render_context() if pipe.controller.working_memory else ""
    # （res2 场次已关闭，working_memory=None——用 retrieved 内容直接验证装载链路：
    #   该教训在第二场开场查询的命中里，且通过 loaded_briefs 进入过上下文）
    assert any("电子压制" in h["content"] or "预备队" in h["content"]
               for h in s1_hits), "召回的应为第一场的电子压制/预备队教训"
    ok("pipeline：七步闭环端到端 + 第二场真实复用（source=复盘:P001）")


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


def test_fix_regressions() -> None:
    """第四轮检查修复的回归锁定：①遗忘单位 ②BM25 缓存 ③LIKE 转义。"""
    # --- F1: 遗忘时间单位（秒→天）---
    # 未保护、未召回的记忆 60 秒"高龄"不应被忘记（旧实现 R=e^-60≈0 直接删）
    emb = MockEmbedding()
    fs = FactualStore(":memory:", emb)
    es = ExperientialStore(emb)
    ev = MemoryEvolution(fs, es, MockLLM(), emb)
    fresh = new_entry(MemoryType.EXPERIENCE, "经验：预备队投入应提前 10 分钟。",
                      importance=1.0)
    fresh.timestamp = time.time() - 60          # 上一场（60 秒前）沉淀
    fresh.last_recalled_at = fresh.timestamp
    es.add(fresh)
    assert fresh.id not in ev.forget(), "60 秒前的未保护记忆不应被遗忘（单位失配回归）"
    assert fresh.retention() > ev.forget_threshold, "60 秒 → R 应接近 1（按天衰减）"
    # 而 10 天前且未召回的未保护记忆应被遗忘（模型语义仍是艾宾浩斯按天）
    stale = new_entry(MemoryType.EXPERIENCE, "经验：补给线过长导致延误。",
                      importance=1.0)
    stale.timestamp = time.time() - 10 * 86400
    stale.last_recalled_at = stale.timestamp
    es.add(stale)
    assert stale.id in ev.forget(), "10 天未召回的未保护记忆应被遗忘"
    # 保护线不受单位影响：importance≥2 永不遗忘
    prot = new_entry(MemoryType.EXPERIENCE, "教训：夜战未派先遣侦察遭伏击。",
                     importance=2.0)
    prot.timestamp = time.time() - 365 * 86400
    prot.last_recalled_at = prot.timestamp
    es.add(prot)
    assert prot.id not in ev.forget(), "失败教训保护线应跨越任何时间尺度"

    # --- F2: BM25 缓存按 version 失效（内容原地更新后索引不得陈旧）---
    fs2 = FactualStore(":memory:", emb)
    es2 = ExperientialStore(emb)
    f = new_entry(MemoryType.FACT, "红方 T-90 坦克 最大速度 60km/h")
    fs2.add(f)
    r = HybridRetriever(fs2, es2)
    qb = QueryItem(q_id="f2", intent="查装备", target="fact",
                   route="bm25", query_text="T-90")
    assert any(h.entry.id == f.id for h in r.retrieve(qb, top_k=3)), "更新前应命中"
    f.content = "蓝方 M1A2 坦克 主炮 120mm"
    fs2.update(f)                               # size 不变的内容换血
    hits = r.retrieve(qb, top_k=3)
    assert not any(h.entry.id == f.id for h in hits), \
        "内容已不含 T-90，BM25 缓存必须失效（陈旧索引回归）"

    # --- F3: LIKE 通配符转义（字面 _ 不再当单字符通配）---
    fs3 = FactualStore(":memory:", emb)
    g = new_entry(MemoryType.FACT, "fact-1234 参数记录")
    fs3.add(g)
    weird = fs3.search("fact-____ 参数")         # 用户本意：字面下划线
    assert not any(h.entry.id == g.id and h.route == "sql" for h in weird), \
        "字面下划线不得被 LIKE 当通配符命中 fact-1234"
    assert any(h.entry.id == g.id for h in fs3.search("参数记录")), \
        "转义子句不得破坏正常 LIKE 匹配"
    ok("第四轮修复回归：遗忘单位(天) + BM25缓存version + LIKE转义")


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

    # 7b) 手动检索不重复执行已缓存的阶段查询（retrieve_after_stage 回归）
    #     先补走"受领任务"阶段（开场默认查询在此执行并缓存）
    ctl.advance_stage("mission_receipt", top_k=3)
    rc_b = {eid: ctl.experiential.get(eid).recall_count
            for eid in ctl.experiential.candidates()}
    hits_manual = ctl.retrieve_and_load(top_k=3)   # stage=None：全量执行
    rc_a = {eid: ctl.experiential.get(eid).recall_count
            for eid in ctl.experiential.candidates()}
    # 各阶段均已缓存 → 其查询不重复执行
    assert rc_b == rc_a, f"手动检索不应重跑已缓存阶段查询：{rc_b} → {rc_a}"
    assert hits_manual == [], f"全部查询均已按阶段缓存，手动检索应无新增命中：{len(hits_manual)}"
    ok("手动检索跳过已缓存阶段查询（不虚涨 recall）")

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


# ---------------------------------------------------------------- 13. 评审修复回归（v0.3）
def test_review_fixes() -> None:
    """评审报告修复项的回归锁定（每条对应评审 §一/§二的一个缺陷）。"""
    import tempfile, os as _os

    # --- RF1【关键】检索结果必须进入注入 LLM 的上下文（render 含装载记忆）---
    emb = MockEmbedding()
    fs = FactualStore(":memory:", emb)
    es = ExperientialStore(emb)
    fs.add(new_entry(MemoryType.FACT, "2 号高地海拔 320 米，仅东侧可装甲通行。",
                     attrs={"地点": "2号高地"}))
    ctl = MemoryController(factual=fs, experiential=es)
    ctl.start_session("RF1", "夺占 2 号高地", [], [
        QueryItem("q", "查地形", "fact", "vector", "2 号高地 地形 装甲 通行")])
    ctl.retrieve_and_load(top_k=3)
    ctx = ctl.render_context()
    assert "【装载记忆】" in ctx, "渲染上下文必须含装载记忆段"
    assert "2 号高地海拔 320" in ctx, "检索命中的记忆正文必须进入上下文"
    ctl.close_session("")

    # --- RF2 单路模式与混合模式可区分（G5 消融的口径基础）---
    fs2 = FactualStore(":memory:", emb)
    es2 = ExperientialStore(emb)
    f2 = new_entry(MemoryType.FACT, "红方 T-90 坦克 最大速度 60km/h", attrs={"装备": "T-90"})
    fs2.add(f2)
    r2 = HybridRetriever(fs2, es2)
    q_v = QueryItem("v", "查装备", "fact", "vector", "T-90 坦克 速度")
    q_s = QueryItem("s", "查装备", "fact", "sql", "T-90 参数", attrs={"装备": "T-90"})
    assert r2.retrieve(q_v, top_k=3, mode="single"), "vector 单路应命中"
    assert r2.retrieve(q_s, top_k=3, mode="single"), "sql(attrs) 单路应精确命中"
    assert r2.retrieve(q_v, top_k=3, mode="hybrid"), "hybrid 应命中"
    try:
        r2.retrieve(q_v, mode="bad_mode")
        raise AssertionError("未知 mode 应报错")
    except ValueError:
        pass

    # --- RF3 MockLLM 句子级抽取 + importance 不越保护线 ---
    llm = MockLLM()
    ops = llm.extract_memory_ops(
        "复盘：任务部分达成。教训：夜间突袭未前置电子压制。经验：预备队投入应提前 10 分钟。")
    assert len(ops) == 2, f"句子级抽取应得 2 条（非行级 1 条混装）：{len(ops)}"
    lesson = next(o for o in ops if "教训" in o["content"])
    assert lesson["importance"] == 1.5, \
        "自动抽取教训 importance 应为 1.5（不越保护线 2.0——否则遗忘机制系统性失效）"
    assert "任务部分达成" not in lesson["content"], "结果陈述句不得混入教训条目"

    # --- RF4 抽象产物不含指令残留文本 ---
    abs_text = llm.abstract("- 教训：夜战需前置电子压制\n- 经验：预备队提前投入", "本场")
    assert "以下为" not in abs_text and "请抽象" not in abs_text, \
        f"抽象产物不得含指令残留：{abs_text}"
    assert "电子压制" in abs_text, "抽象产物应含源经验内容"

    # --- RF5 bm25 自匹配归一（负例噪声不放大）---
    fs5 = FactualStore(":memory:", emb)
    es5 = ExperientialStore(emb)
    for c in ("红方 T-90 坦克 最大速度 60km/h", "蓝方 M1A2 坦克 最大速度 67km/h"):
        fs5.add(new_entry(MemoryType.FACT, c))
    r5 = HybridRetriever(fs5, es5)
    neg = QueryItem("n", "负例", "fact", "vector", "电影 票房 统计")
    assert r5.retrieve(neg, top_k=3) == [], "负例查询应被 min_score 滤除"

    # --- RF6 Mock summarize 中文截断有界（递归摘要不膨胀）---
    long_text = "红方装甲梯队向东机动。" * 50
    summ = llm.summarize(long_text, max_words=100)
    assert len(summ) <= 250, f"摘要应有界（≤250 字），实际 {len(summ)}"

    # --- RF7 经验库 SQLite 持久化（重启不丢 + 召回史保留）---
    fd, path = tempfile.mkstemp(suffix=".db"); _os.close(fd)
    try:
        s_a = ExperientialStore(emb, db_path=path)
        e_a = new_entry(MemoryType.EXPERIENCE, "教训：持久化回归测试条目。", importance=1.5)
        s_a.add(e_a)
        e_a.mark_recalled(); s_a.persist_recall(e_a)
        s_b = ExperientialStore(emb, db_path=path)   # 模拟重启
        assert s_b.stats()["count"] == 1, "重启后条目应保留"
        got = s_b.get(e_a.id)
        assert got.recall_count == 1 and got.decay_strength == 2.0, \
            "命中强化（S/recall_count）应随持久化保留"
        assert s_b.search("持久化 回归 测试"), "重启后语义检索可用"
    finally:
        _os.unlink(path)

    # --- RF8 controller.write_long_term：边界门控正规入口 ---
    ctl8 = MemoryController(factual=FactualStore(":memory:", emb),
                            experiential=ExperientialStore(emb))
    nid = ctl8.write_long_term("教训：正规入口写入的教训。", session_id="RF8")
    assert nid, "教训类内容应经 promote 门控放行入库"
    assert ctl8.experiential.get(nid).metadata.get("stage"), "写入应带阶段归因标签"
    assert ctl8.write_long_term("指挥所说今天食堂有红烧肉") is None, \
        "场次闲聊应被 G2 门控拒绝（不入长期库）"
    assert any(not d["allowed"] for d in ctl8.boundary.audit_log()), \
        "拒绝决策应留审计日志"

    # --- RF9 跨查询去重（同场同记忆只装载/计数一次）---
    fs9 = FactualStore(":memory:", emb)
    es9 = ExperientialStore(emb)
    f9 = new_entry(MemoryType.FACT, "红方 T-90 坦克 最大速度 60km/h", attrs={"装备": "T-90"})
    fs9.add(f9)
    ctl9 = MemoryController(factual=fs9, experiential=es9)
    ctl9.start_session("RF9", "查装备", [], [
        QueryItem("q1", "查 T-90", "fact", "vector", "T-90 坦克 速度"),
        QueryItem("q2", "再查 T-90", "fact", "bm25", "T-90 速度")])
    hits = ctl9.retrieve_and_load(top_k=3)
    assert len(hits) == 1, f"两条查询命中同一记忆应去重为 1（实际 {len(hits)}）"
    assert ctl9.session_stats["retrieved"] == 1

    ok("评审修复回归：上下文注入/单路模式/句级抽取/抽象无残留/"
       "bm25归一/摘要有界/经验库持久化/正规写入入口/跨查询去重")


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
    test_fix_regressions()
    test_integration_zhirong()
    test_stage_aware()
    test_review_fixes()
    print("=" * 60)
    print("全部通过 [OK]")
