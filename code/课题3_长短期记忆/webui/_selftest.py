# -*- coding: utf-8 -*-
"""webui API 全链路自测（七步闭环逐接口验证），跑完自动退出。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8765"
PASS, FAIL = 0, 0


def call(path, body=None):
    if body is None:
        req = urllib.request.Request(BASE + path)
    else:
        req = urllib.request.Request(BASE + path,
                                     data=json.dumps(body).encode("utf-8"),
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


print("=== webui 全链路自测（七步闭环） ===")

# 0) 静态页
import urllib.error
try:
    html = urllib.request.urlopen(BASE + "/", timeout=5).read().decode("utf-8")
    check("GET / 静态页", "记忆系统控制台" in html)
except Exception as e:
    check("GET / 静态页", False, str(e))

# 1) 状态 + 种子（DOMContentLoaded 已自动 seed，手动再 seed 幂等）
st = call("/api/status")
check("GET /api/status", "facts" in st and "boundary" in st)
s = call("/api/seed", {})
check("POST /api/seed", s.get("facts") >= 4 and s.get("experiences") >= 3, str(s))

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

# 3) ③④ 检索装载（命中地形事实 + 夜战教训，带溯源）
r = call("/api/session/retrieve", {"top_k": 3})
check("POST /api/session/retrieve", r.get("ok") and len(r.get("hits", [])) > 0)
hit_types = {h["type"] for h in r.get("hits", [])}
check("检索命中双类型", "fact" in hit_types, str(hit_types))
check("命中带溯源", all("provenance" in h for h in r.get("hits", [])))
check("上下文含约束", "禁止越境" in r.get("context", ""))

# 4) 消息推入（FIFO）
r = call("/api/session/push", {"msg": "指挥所：红方 3 营东侧集结完毕"})
check("POST /api/session/push", r.get("ok") and "tokens" in r)

# 5) ⑤ 上下文
r = call("/api/context")
check("GET /api/context", "目标" in r.get("context", ""))

# 6) ⑥⑦ 复盘进化（写入新经验 + boundary 审计）
r = call("/api/session/close", {"review_text":
        "复盘：任务部分达成。教训：夜间突袭未前置电子压制。经验：预备队投入应提前 10 分钟。"})
rep = r.get("report", {})
check("POST /api/session/close", r.get("ok") and rep.get("write", 0) >= 1, str(rep))
check("进化四操作计数齐全",
      all(k in rep for k in ("write", "merge", "forget", "abstract")))

# 7) 关闭后状态：无场次
st = call("/api/status")
check("关闭后 session=null", st.get("session") is None)

# 8) 记忆浏览（进化后经验库 +1）
r = call("/api/memory?type=experience")
check("GET /api/memory", r.get("count", 0) >= 4, str(r.get("count")))
has_new = any("电子压制" in m["content"] for m in r.get("items", []))
check("复盘新经验已入库", has_new)

# 9) 独立检索接口（无需场次）
r = call("/api/search", {"query": "T-90 速度", "target": "fact", "route": "bm25", "top_k": 3})
check("POST /api/search", len(r.get("hits", [])) > 0)

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

# 12) 静态 JS/CSS
for path, key in [("/app.js", "refreshAll"), ("/style.css", "--accent")]:
    try:
        body = urllib.request.urlopen(BASE + path, timeout=5).read().decode("utf-8")
        check(f"GET {path}", key in body)
    except Exception as e:
        check(f"GET {path}", False, str(e))

print("=" * 40)
print(f"总计 {PASS + FAIL} 项，通过 {PASS}，失败 {FAIL}")
exit(1 if FAIL else 0)
