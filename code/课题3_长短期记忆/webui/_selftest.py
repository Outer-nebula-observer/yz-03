# -*- coding: utf-8 -*-
"""webui API 全链路自测（七步闭环 + 过程可视化端点），跑完自动退出。

覆盖：
  A. 原七步闭环逐接口；
  B. 新增可视化端点：/api/events、/api/sessions、/api/context 的 wm 构成、
     /api/status 的 steps 进度；
  C. 跨场次复用（多轮长期性）：第一场复盘沉淀教训 → 第二场检索召回
     往场记忆（reused 字段）→ 场次历史记录 produced/reused；
  D. seed 幂等、场景库含 night_hill_2。
"""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"
PASS, FAIL = 0, 0


def call(path, body=None):
    if body is None:
        req = urllib.request.Request(BASE + path)
    else:
        req = urllib.request.Request(BASE + path,
                                     data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {extra}")


print("=== webui 全链路自测（七步闭环 + 过程可视化 + 跨场次复用） ===")

# 0) 静态页（含新组件：stepper / 事件流 / 工作记忆 / 场次历史）
import urllib.error
try:
    html = urllib.request.urlopen(BASE + "/", timeout=5).read().decode("utf-8")
    check("GET / 静态页", "记忆系统控制台" in html)
    for key in ("stepper", "events", "wm", "sessions", "reuse-banner", "demoTwoSessions"):
        check(f"静态页含组件 {key}", key in html)
except Exception as e:
    check("GET / 静态页", False, str(e))

# 1) 重置 + 状态 + 种子
call("/api/reset", {})
st = call("/api/status")
check("GET /api/status", "facts" in st and "boundary" in st)
check("status 含七步进度 steps", isinstance(st.get("steps"), dict)
      and st["steps"].get("s1") is False)
check("status 含场次计数", st.get("sessions_total") == 0)
s = call("/api/seed", {})
check("POST /api/seed", s.get("facts") >= 4 and s.get("experiences") >= 3, str(s))
s2 = call("/api/seed", {})
check("seed 幂等（重复调用跳过）", s2.get("skipped") is True, str(s2))

# 2) ①② 开场（goal+约束+两条查询）
r = call("/api/session/start", {
    "plan_id": "W001", "goal": "夜间夺占 2 号高地",
    "constraints": ["禁止越境", "限时 4 小时"],
    "queries": [
        {"intent": "查地形通行", "target": "fact", "route": "vector",
         "query_text": "2 号高地 地形 装甲 通行"},
        {"intent": "召回夜战教训", "target": "experience", "route": "bm25",
         "query_text": "夜战 侦察 伏击 教训"},
    ]})
check("POST /api/session/start", r.get("ok") and r.get("plan_id") == "W001", str(r))
st = call("/api/status")
check("开场后 steps.s1/s2=True", st["steps"].get("s1") and st["steps"].get("s2"), str(st["steps"]))
ev = call("/api/events")
check("GET /api/events（开场输入/产出事件）",
      any(e["kind"] == "input" and "规划任务" in e["title"] for e in ev["events"])
      and any(e["kind"] == "output" and "槽位" in e["title"] for e in ev["events"]),
      str(ev["events"][:3]))
ss = call("/api/sessions")
check("GET /api/sessions（本场已登记，进行中）",
      len(ss["sessions"]) == 1 and ss["sessions"][0]["plan_id"] == "W001"
      and ss["sessions"][0]["closed_at"] is None, str(ss))

# 3) ③④ 检索装载（命中地形事实 + 夜战教训，带溯源 + wm 构成）
r = call("/api/session/retrieve", {"top_k": 3})
check("POST /api/session/retrieve", r.get("ok") and len(r.get("hits", [])) > 0)
hit_types = {h["type"] for h in r.get("hits", [])}
check("检索命中双类型", "fact" in hit_types, str(hit_types))
check("命中带溯源", all("provenance" in h for h in r.get("hits", [])))
check("上下文含约束", "禁止越境" in r.get("context", ""))
check("retrieve 返回 wm 构成", isinstance(r.get("wm"), dict)
      and r["wm"].get("plan_id") == "W001" and r["wm"].get("loaded")
      and r["wm"].get("capacity") == 4000, str(r.get("wm", {}))[:120])
check("retrieve 返回 reused 字段", "reused" in r)
st = call("/api/status")
check("检索后 steps.s3/s4/s5=True", st["steps"].get("s3") and st["steps"].get("s4"))

# 4) 消息推入（FIFO）
r = call("/api/session/push", {"msg": "指挥所：红方 3 营东侧集结完毕"})
check("POST /api/session/push", r.get("ok") and "tokens" in r)

# 5) ⑤ 上下文（含 wm：FIFO 应包含刚推的消息）
r = call("/api/context")
check("GET /api/context", "目标" in r.get("context", ""))
check("context.wm.fifo 含已推消息",
      any("红方 3 营" in m for m in r["wm"]["fifo"]), str(r["wm"]["fifo"][:2]))

# 6) ⑥⑦ 复盘进化（写入新经验 + boundary 审计）
r = call("/api/session/close", {"review_text":
        "复盘：任务部分达成。教训：夜间突袭未前置电子压制。经验：预备队投入应提前 10 分钟。"})
rep = r.get("report", {})
check("POST /api/session/close", r.get("ok") and rep.get("write", 0) >= 1, str(rep))
check("进化四操作计数齐全",
      all(k in rep for k in ("write", "merge", "forget", "abstract")))
st = call("/api/status")
check("关闭后 session=null", st.get("session") is None)
check("关闭后 steps.s7=True", st["steps"].get("s7") is True)
ss = call("/api/sessions")
check("场次历史：W001 已收口并记录沉淀",
      ss["sessions"][0]["closed_at"] is not None
      and ss["sessions"][0]["report"]["write"] >= 1
      and len(ss["sessions"][0]["produced"]) >= 1, str(ss["sessions"][0])[:200])

# 7) 记忆浏览（进化后经验库 +1，条目带 session_id / timestamp）
r = call("/api/memory?type=experience")
check("GET /api/memory", r.get("count", 0) >= 4, str(r.get("count")))
has_new = any("电子压制" in m["content"] for m in r.get("items", []))
check("复盘新经验已入库", has_new)
# 【断言更新·评审修复】句子级抽取后：复盘含"教训/经验"两句 → 写入 2 条；
# 且 ≥2 条新经验触发抽象 → 抽象产物（内容含两句拼接）同样继承 session_id。
# 故"含电子压制且来自 W001"的条目应为【复盘写入 + 抽象产物】≥1 条。
wrote_sess = [m["session_id"] for m in r.get("items", []) if "电子压制" in m["content"]]
check("新经验带来源场次 session_id",
      len(wrote_sess) >= 1 and all(x == "W001" for x in wrote_sess),
      str(wrote_sess))

# 8) ★ 跨场次复用：第二场检索应召回 W001 沉淀的记忆（多轮长期性）
r = call("/api/session/start", {
    "plan_id": "W002", "goal": "第二夜再次夺占 2 号高地",
    "constraints": ["保持无线电静默"],
    "queries": [
        {"intent": "召回上一场夜间突袭教训", "target": "experience", "route": "bm25",
         "query_text": "夜间 突袭 电子压制 通信 干扰"},
    ]})
check("第二场开场", r.get("ok") and r.get("plan_id") == "W002", str(r))
r = call("/api/session/retrieve", {"top_k": 3})
check("第二场检索命中", len(r.get("hits", [])) > 0)
reused = r.get("reused", [])
check("第二场复用 W001 沉淀（reused）",
      any(x["plan_id"] == "W001" and x["count"] >= 1 for x in reused), str(reused))
ss = call("/api/sessions")
w002 = next(s for s in ss["sessions"] if s["plan_id"] == "W002")
check("场次历史记录 W002 复用往场",
      any(x["plan_id"] == "W001" for x in w002["reused"]), str(w002.get("reused")))
# 复盘收口第二场（保持库干净，供后续手动演示）
call("/api/session/close", {"review_text": "复盘：任务达成。经验：复用上场教训有效。"})

# 8b) ★ 阶段感知（MDMP）：查询按规划阶段生成 + 阶段亲和 + 事件流
st = call("/api/stages")
check("GET /api/stages（MDMP 七阶段）",
      len(st.get("stages", [])) == 7 and st["stages"][0]["id"] == "mission_receipt",
      str(st)[:100])
r = call("/api/session/start", {
    "plan_id": "W003", "goal": "夜间夺占 2 号高地", "constraints": ["禁止越境"],
    "queries": []})   # 不带手写查询——由阶段模板生成（老师意见的落地）
check("W003 开场（无手写查询）", r.get("ok") is True, str(r))
# 新默认：开场即装载"受领任务+任务分析"阶段查询（不再 goal 字面直查）
r = call("/api/context")
default_qs = [q for q in r.get("wm", {}).get("queries", []) if q.get("stage")]
check("开场默认查询为阶段模板（受领任务+任务分析）",
      any(q["stage"] == "mission_receipt" for q in default_qs)
      and any(q["stage"] == "mission_analysis" for q in default_qs),
      str([q.get("stage") for q in default_qs]))
r = call("/api/session/stage", {"stage_id": "mission_analysis", "top_k": 3})
check("POST /api/session/stage（任务分析）",
      r.get("ok") and r.get("stage", {}).get("name") == "任务分析", str(r)[:120])
check("阶段查询已生成（带 stage 字段）",
      any(q.get("stage") == "mission_analysis"
          for q in r.get("wm", {}).get("queries", [])),
      str(r.get("wm", {}).get("queries", []))[:120])
check("任务分析命中事实（阶段供给）",
      any(h["type"] == "fact" for h in r.get("hits", [])), str(r.get("hits", []))[:100])
check("命中带 stage 标签", any(h.get("stage") for h in r.get("hits", [])))
check("上下文带【规划阶段】", "【规划阶段】mission_analysis" in r.get("context", ""))
stt = call("/api/status")
check("status 带 current_stage",
      stt.get("session", {}).get("current_stage") == "mission_analysis")
r = call("/api/session/stage", {"stage_id": "coa_analysis", "top_k": 3})
check("进入推演阶段（查询追加不覆盖）",
      r.get("ok") and sum(1 for q in r.get("wm", {}).get("queries", [])
                          if q.get("stage")) >= 3,
      str(len(r.get("wm", {}).get("queries", []))))
check("推演阶段召回经验教训",
      any(h["type"] == "experience" for h in r.get("hits", [])))
# 补走"受领任务"阶段：开场默认查询在此执行并入缓存（供下方回归断言）
call("/api/session/stage", {"stage_id": "mission_receipt", "top_k": 3})
# 幂等：同阶段重复点击不虚涨 recall_count
mem_before = call("/api/memory?type=experience")["items"]
rc_before = {m["id"]: m["recall_count"] for m in mem_before}
r2 = call("/api/session/stage", {"stage_id": "coa_analysis", "top_k": 3})
check("同阶段重复推进返回缓存命中", r2.get("ok") and len(r2.get("hits", [])) > 0)
mem_after = call("/api/memory?type=experience")["items"]
rc_after = {m["id"]: m["recall_count"] for m in mem_after}
check("重复推进不虚涨 recall_count", rc_before == rc_after,
      str({k: (rc_before.get(k), rc_after.get(k)) for k in rc_after
           if rc_before.get(k) != rc_after.get(k)})[:120])
# steps 进度：走阶段后 ②③④⑤ 应点亮
stt2 = call("/api/status")
check("阶段推进点亮 stepper ③④⑤",
      stt2["steps"]["s3"] and stt2["steps"]["s4"] and stt2["steps"]["s5"],
      str(stt2["steps"]))
# 手动检索跳过已缓存阶段查询（recall 不虚涨）
rcb = {m["id"]: m["recall_count"] for m in call("/api/memory?type=experience")["items"]}
r3 = call("/api/session/retrieve", {"top_k": 3})
rca = {m["id"]: m["recall_count"] for m in call("/api/memory?type=experience")["items"]}
check("手动检索不重跑已缓存阶段查询（recall 不变）",
      rcb == rca and r3.get("hits") == [],
      str({k: (rcb.get(k), rca.get(k)) for k in rca if rcb.get(k) != rca.get(k)})[:120])
ev = call("/api/events")
check("阶段切换进事件流",
      any("规划阶段" in e["title"] for e in ev["events"]))
call("/api/session/close", {"review_text": "复盘：教训：夜间遭伏击通信被干扰。经验：佯动奏效。"})
r = call("/api/memory?type=experience")
staged = [m for m in r.get("items", []) if m.get("metadata", {}).get("stage")]
check("复盘教训已带阶段归因标签",
      any(m["session_id"] == "W003" and m["metadata"].get("stage")
          for m in staged), str([m["id"] for m in staged])[:100])
try:
    call("/api/session/stage", {"stage_id": "no_such"})
    check("未知阶段 400", False, "未抛错")
except urllib.error.HTTPError as e:
    check("未知阶段 400", e.code == 400)

# 9) 独立检索接口（无需场次）
r = call("/api/search", {"query": "T-90 速度", "target": "fact", "route": "bm25", "top_k": 3})
check("POST /api/search", len(r.get("hits", [])) > 0)
ev = call("/api/events")
check("独立检索也进事件流",
      any("独立检索" in e["title"] for e in ev["events"]))

# 10) 边界审计
r = call("/api/audit")
check("GET /api/audit", "stats" in r and "log" in r)

# 11) 业务错误返回 400（未开场就 retrieve）
call("/api/reset", {})
try:
    call("/api/session/retrieve", {"top_k": 3})
    check("业务错误 400", False, "未抛错")
except urllib.error.HTTPError as e:
    check("业务错误 400", e.code == 400)

# 12) 场景库（含跨场次复用场景 night_hill_2）
sc = call("/api/scenarios")
ids = [x["id"] for x in sc["scenarios"]]
check("GET /api/scenarios 含 night_hill_2", "night_hill_2" in ids, str(ids))
r = call("/api/scenario", {"id": "night_hill_2"})
check("POST /api/scenario", "第二夜" in r.get("goal", ""), str(r)[:100])

# 13) 静态 JS/CSS
for path, key in [("/app.js", "refreshAll"), ("/style.css", "--accent"),
                  ("/app.js", "demoTwoSessions"), ("/style.css", ".stepper")]:
    try:
        body = urllib.request.urlopen(BASE + path, timeout=5).read().decode("utf-8")
        check(f"GET {path} 含 {key}", key in body)
    except Exception as e:
        check(f"GET {path}", False, str(e))

print("=" * 40)
print(f"总计 {PASS + FAIL} 项，通过 {PASS}，失败 {FAIL}")
exit(1 if FAIL else 0)
