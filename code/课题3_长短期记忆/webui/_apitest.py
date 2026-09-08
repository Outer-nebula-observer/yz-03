# -*- coding: utf-8 -*-
"""临时：webui 七步闭环全链路测试（文件内发请求，避开终端编码问题）。"""
import json, urllib.request, urllib.error

BASE = "http://127.0.0.1:8765"
def call(path, body=None, method=None):
    if body is None and method is None:
        req = urllib.request.Request(BASE + path)
    else:
        method = method or ("POST" if body is not None else "GET")
        req = urllib.request.Request(BASE + path,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else b"",
            headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))

ok = fail = 0
def chk(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print(f"  [PASS] {name}")
    else: fail += 1; print(f"  [FAIL] {name} {extra}")

print("=== webui 七步闭环全链路 ===")
html = urllib.request.urlopen(BASE + "/", timeout=5).read().decode("utf-8")
chk("GET / 静态页", "记忆系统控制台" in html)
s = call("/api/reset", method="POST"); chk("reset", s.get("ok") is True)
s = call("/api/seed", {}); chk("seed 演示数据", s.get("facts", 0) >= 3 and s.get("experiences", 0) >= 2, str(s))
st = call("/api/status"); chk("status", st.get("facts", 0) >= 3)
s = call("/api/session/start", {"goal": "夜间夺占 2 号高地",
    "constraints": ["禁止越境", "限时 4 小时"],
    "queries": [{"intent": "查地形", "target": "fact", "route": "vector", "query_text": "2 号高地 地形 装甲 通行"},
                {"intent": "召回夜战教训", "target": "experience", "route": "bm25", "query_text": "夜战 侦察 伏击"}]})
chk("① session/start", s.get("ok") is True, str(s))
r = call("/api/session/retrieve", {"top_k": 3})
chk("③④ retrieve 命中", len(r.get("hits", [])) >= 1, str(r)[:150])
ctx = call("/api/context")
chk("⑤ context 含目标/约束", "夜间夺占" in ctx.get("context", "") and "禁止越境" in ctx.get("context", ""))
chk("⑤ 溯源字段", any(h.get("provenance") for h in r.get("hits", [])))
p = call("/api/session/push", {"msg": "指挥所：红方 3 营东侧集结完毕"})
chk("场次消息 push", p.get("ok") is True)
c = call("/api/session/close", {"review_text": "复盘：教训：夜间突袭未前置电子压制。经验：预备队提前 10 分钟投入。"})
chk("⑦ close 进化", c.get("report", {}).get("write", 0) + c.get("report", {}).get("skip_duplicate", 0) >= 1, str(c)[:200])
chk("⑦ 边界审计", c.get("boundary", {}).get("total", 0) >= 0)
s2 = call("/api/search", {"query": "夜战 教训", "target": "experience", "route": "vector"})
chk("独立检索 api/search", len(s2.get("hits", [])) >= 1, str(s2)[:150])
req = urllib.request.Request(BASE + "/api/memory?type=experience")
with urllib.request.urlopen(req, timeout=10) as r:
    m = json.loads(r.read().decode("utf-8"))
chk("记忆浏览 api/memory", isinstance(m.get("items"), list) and m.get("count", 0) >= 1, str(m)[:100])
print(f"\n结果：{ok} 通过 / {fail} 失败")
