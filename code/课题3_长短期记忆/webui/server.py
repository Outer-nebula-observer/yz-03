# -*- coding: utf-8 -*-
"""
webui/server.py — 赛题③ 记忆系统 Web 控制台（零依赖，纯 Python 标准库）
==========================================================================
用法（在 课题3_长短期记忆/ 目录下）：
    python webui/server.py            # 默认 http://127.0.0.1:8765
    python webui/server.py --port 9000

功能（单页控制台，全部映射到 memsys 七步闭环）：
  ① 规划开场   POST /api/session/start   （goal/constraints/查询列表）
  ③④ 检索装载  POST /api/session/retrieve（混合检索 + 装载 + 上下文渲染）
  场次消息     POST /api/session/push
  ⑤ 上下文     GET  /api/context         （当前注入 LLM 的完整上下文）
  ⑦ 复盘进化   POST /api/session/close   （四操作报告 + 边界审计）
  记忆浏览/检索 GET/POST /api/memory, /api/search
  演示数据     POST /api/seed  /api/reset

实现说明：
  - http.server.ThreadingHTTPServer + json：不引入任何第三方依赖（与 memsys 哲学一致）；
  - 全局单例 MemoryController（会话态在服务进程内存中）；
  - 静态文件从 webui/static/ 读取；API 全部 JSON。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# 让 webui 能 import 上一级的 memsys 包
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 课题3_长短期记忆/
sys.path.insert(0, ROOT)

from memsys import (  # noqa: E402
    MemoryController, MemoryType, QueryItem, new_entry, MockLLM, MockEmbedding,
    FactualStore, ExperientialStore,
)

STATIC_DIR = os.path.join(HERE, "static")

# ---------------------------------------------------------------- 全局状态
class AppState:
    """服务进程内的全局状态：一个 controller + 演示种子。"""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        emb = MockEmbedding()
        self.ctl = MemoryController(
            factual=FactualStore(":memory:", emb),
            experiential=ExperientialStore(emb),
            llm=MockLLM(),
            embedding=emb,
        )
        self.last_hits = []          # 最近一次检索结果（含溯源）
        self.last_report = None      # 最近一次进化报告

    def seed(self) -> dict:
        """预置演示记忆（战例事实 + 历史教训），返回写入数量。"""
        facts = [
            ("红方 T-90 主战坦克：最大速度 60km/h，主炮 125mm。",
             {"装备": "T-90", "阵营": "红方"}),
            ("蓝方 M1A2 主战坦克：最大速度 67km/h，主炮 120mm。",
             {"装备": "M1A2", "阵营": "蓝方"}),
            ("2 号高地海拔 320 米，北坡缓南坡陡，仅东侧可装甲通行。",
             {"地点": "2号高地"}),
            ("3 号高地海拔 210 米，地形开阔，两条机械化通路。",
             {"地点": "3号高地"}),
        ]
        exps = [
            ("教训：夜间行军未派先遣侦察，先头连在东侧隘口遭遇伏击。", 2.0),
            ("经验：炮火准备前置 20 分钟，可显著压制敌方反坦克火力点。", 1.5),
            ("教训：渡河架桥耗时超预估 40%，导致主攻梯队迟到。", 2.0),
        ]
        for content, attrs in facts:
            self.ctl.factual.add(new_entry(MemoryType.FACT, content,
                                           source="seed", attrs=attrs))
        for content, imp in exps:
            self.ctl.experiential.add(new_entry(
                MemoryType.EXPERIENCE, content, source="seed", importance=imp))
        return {"facts": len(facts), "experiences": len(exps)}


STATE = AppState()


# ---------------------------------------------------------------- API 实现
def api_status() -> dict:
    ctl = STATE.ctl
    wm = ctl.working_memory
    return {
        "facts": ctl.factual.stats()["count"],
        "experiences": ctl.experiential.stats()["count"],
        "session": {
            "open": wm is not None and wm.slot.status == "open",
            "plan_id": wm.slot.plan_id if wm else None,
            "goal": wm.slot.goal if wm else None,
            "constraints": wm.slot.constraints if wm else [],
            "pressure": wm.memory_pressure if wm else False,
            "used_ratio": round(wm.used_ratio, 3) if wm else 0,
        } if wm else None,
        "boundary": ctl.evolution.boundary.stats(),
        "min_score": ctl.retriever.min_score,
        "weights": {"alpha": ctl.retriever.alpha, "beta": ctl.retriever.beta,
                    "gamma": ctl.retriever.gamma},
    }


def api_session_start(body: dict) -> dict:
    if STATE.ctl.working_memory and STATE.ctl.working_memory.slot.status == "open":
        raise ValueError("已有未关闭场次，请先 close（复盘进化）再开新场次")
    queries_raw = body.get("queries") or []
    queries = [
        QueryItem(q_id=f"q{i+1}", intent=q.get("intent", "查询"),
                  target=q.get("target", "fact"), route=q.get("route", "vector"),
                  query_text=q.get("query_text", ""))
        for i, q in enumerate(queries_raw)
    ]
    if not queries:  # 无外部查询时按 goal 自动生成两条（与 pipeline 默认一致）
        goal = body.get("goal", "")
        queries = [
            QueryItem(q_id="q1", intent="查相关装备/环境事实", target="fact",
                      route="vector", query_text=goal),
            QueryItem(q_id="q2", intent="召回相似历史经验教训", target="experience",
                      route="vector", query_text=goal),
        ]
    wm = STATE.ctl.start_session(
        body.get("plan_id") or f"P{int(time.time())%100000}",
        body.get("goal", ""), body.get("constraints"), queries)
    return {"ok": True, "plan_id": wm.slot.plan_id}


def api_session_retrieve(body: dict) -> dict:
    wm = STATE.ctl.working_memory
    if wm is None or wm.slot.status != "open":
        raise ValueError("没有活动场次，请先 start")
    hits = STATE.ctl.retrieve_and_load(top_k=int(body.get("top_k", 3)))
    STATE.last_hits = hits
    return {"ok": True, "hits": [hit_dict(h) for h in hits],
            "context": STATE.ctl.render_context(),
            "tokens": wm.used_tokens, "ratio": round(wm.used_ratio, 3),
            "pressure": wm.memory_pressure, "stats": STATE.ctl.session_stats}


def api_session_push(body: dict) -> dict:
    wm = STATE.ctl.working_memory
    if wm is None or wm.slot.status != "open":
        raise ValueError("没有活动场次")
    STATE.ctl.push(body.get("msg", ""))
    return {"ok": True, "tokens": wm.used_tokens, "ratio": round(wm.used_ratio, 3),
            "pressure": wm.memory_pressure,
            "archived": len(wm.archived)}


def api_context() -> dict:
    wm = STATE.ctl.working_memory
    if wm is None:
        return {"context": "", "tokens": 0, "ratio": 0, "pressure": False}
    return {"context": STATE.ctl.render_context(), "tokens": wm.used_tokens,
            "ratio": round(wm.used_ratio, 3), "pressure": wm.memory_pressure}


def api_session_close(body: dict) -> dict:
    wm = STATE.ctl.working_memory
    if wm is None or wm.slot.status != "open":
        raise ValueError("没有活动场次")
    report = STATE.ctl.close_session(body.get("review_text", ""))
    STATE.last_report = report
    return {"ok": True, "report": report_dict(report),
            "boundary": STATE.ctl.evolution.boundary.stats(),
            "audit": STATE.ctl.evolution.boundary.audit_log()[-20:]}


def api_memory(params: dict) -> dict:
    mtype = params.get("type", "fact")
    store = STATE.ctl.factual if mtype == "fact" else STATE.ctl.experiential
    items = []
    for mid in store.candidates():
        e = store.get(mid)
        if e is None:
            continue
        items.append({
            "id": e.id, "content": e.content, "importance": e.importance,
            "recall_count": e.recall_count,
            "retention": round(e.retention(), 4),
            "source": e.source, "session_id": e.session_id,
            "metadata": e.metadata, "merged_from": e.merged_from,
            "op_history": e.op_history,
        })
    items.sort(key=lambda x: x["importance"], reverse=True)
    return {"type": mtype, "items": items, "count": len(items)}


def api_search(body: dict) -> dict:
    q = QueryItem(q_id="web", intent=body.get("intent", "web 检索"),
                  target=body.get("target", "fact"),
                  route=body.get("route", "vector"),
                  query_text=body.get("query", ""))
    hits = STATE.ctl.retriever.retrieve(q, top_k=int(body.get("top_k", 5)))
    return {"hits": [hit_dict(h) for h in hits],
            "answer_memory_ids": q.answer_memory_ids}


def hit_dict(h) -> dict:
    """检索结果 → JSON（含溯源，创新点 E 的可视化）。"""
    p = h.entry.provenance()
    return {"id": h.entry.id, "type": h.entry.type.value,
            "content": h.entry.content, "score": round(h.score, 4),
            "route": h.route, "rank": h.rank,
            "provenance": p}


def report_dict(r) -> dict:
    return {
        "write": len(r.wrote), "merge": len(r.merged),
        "forget": len(r.forgot), "abstract": len(r.abstracted),
        "skip_duplicate": len(r.skipped),
        "wrote_ids": r.wrote, "forgot_ids": r.forgot,
        "abstracted_ids": r.abstracted,
        "merged_pairs": [[new, srcs] for new, srcs in r.merged],
    }


def api_audit() -> dict:
    b = STATE.ctl.evolution.boundary
    return {"stats": b.stats(), "log": b.audit_log()[-50:]}


# ---------------------------------------------------------------- HTTP 服务
class Handler(BaseHTTPRequestHandler):
    """极简路由：/api/* 走 JSON，其余走静态文件。"""

    # ----- 路由表 -----
    API = {
        ("GET", "/api/status"): lambda params, body: api_status(),
        ("POST", "/api/reset"): lambda params, body: (STATE.reset(), {"ok": True})[1],
        ("POST", "/api/seed"): lambda params, body: STATE.seed(),
        ("POST", "/api/session/start"): lambda params, body: api_session_start(body),
        ("POST", "/api/session/retrieve"): lambda params, body: api_session_retrieve(body),
        ("POST", "/api/session/push"): lambda params, body: api_session_push(body),
        ("GET", "/api/context"): lambda params, body: api_context(),
        ("POST", "/api/session/close"): lambda params, body: api_session_close(body),
        ("GET", "/api/memory"): lambda params, body: api_memory(params),
        ("POST", "/api/search"): lambda params, body: api_search(body),
        ("GET", "/api/audit"): lambda params, body: api_audit(),
    }

    def log_message(self, fmt, *args):  # 安静模式：不刷屏
        pass

    def _send_json(self, obj, code=200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        fname = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
        if not fname.startswith(STATIC_DIR) or not os.path.isfile(fname):
            self._send_json({"error": "not found"}, 404)
            return
        ctype = {"html": "text/html; charset=utf-8", "js": "text/javascript; charset=utf-8",
                 "css": "text/css; charset=utf-8", "svg": "image/svg+xml"}.get(
                    fname.rsplit(".", 1)[-1], "application/octet-stream")
        with open(fname, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method: str) -> None:
        parsed = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        body = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                try:
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                except json.JSONDecodeError:
                    self._send_json({"error": "请求体不是合法 JSON"}, 400)
                    return
        fn = self.API.get((method, parsed.path))
        if fn is not None:
            try:
                self._send_json(fn(params, body))
            except ValueError as exc:      # 业务错误（场次状态等）
                self._send_json({"error": str(exc)}, 400)
            except Exception as exc:       # 兜底：不让线程崩
                self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        else:
            if method == "GET":
                self._send_static(parsed.path)
            else:
                self._send_json({"error": "not found"}, 404)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


def main() -> None:
    parser = argparse.ArgumentParser(description="赛题③ 记忆系统 Web 控制台")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print("=" * 60)
    print(f"赛题③ 记忆系统 Web 控制台已启动")
    print(f"    地址: http://{args.host}:{args.port}")
    print(f"    静态目录: {STATIC_DIR}")
    print(f"    停止: Ctrl+C")
    print("=" * 60)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
