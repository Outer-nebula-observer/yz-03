# -*- coding: utf-8 -*-
"""
zhirong_kit.bridge_server — 智戎 HTTP 桥服务（REST 三挂接点）
==============================================================
当智戎平台不便内嵌 Python（或跨机部署）时，用本服务把记忆系统变成
一个 HTTP 服务，智戎侧只需发 3 个 POST 请求。

端点：
  GET  /healthz            → 服务/模型/库状态
  POST /hook/plan          body: {"plan_id","goal","constraints":[],"queries":[]?}
                           或 {"task": {...}} 结构化任务（自动 normalize）
                           → {"context","retrieved","elapsed_ms"}
  POST /hook/feedback      body: {"text":""?, "structured":{...}?}
                           → {"ok","elapsed_ms"}（结构化会转写成复盘文本）
  POST /hook/append_feedback body: {"text":""?, "structured":{...}?}  → 累积缓冲
  POST /hook/evolve        body: {"reason":"manual|periodic|...", "extra_review":""?}
                           → 事件驱动进化（不要求有 open session）
  POST /hook/normalize     body: {"task": {...}}
                           → 规范化后的 goal/constraints/queries
  POST /hook/close         body: {"extra_review":""?}
                           → {"write","merge","forget","abstract","boundary","elapsed_ms"}

启动：
  python bridge_server.py --host 0.0.0.0 --port 8390
环境变量（可选）：
  ZR_REAL=1       启用 DeepSeek 真 LLM（默认 0=Mock，离线稳定）
  ZR_EMBED_GLM=1  启用 GLM embedding（需有效 GLM_API_KEY；失败回退 Mock）
  ZR_FACT_DB=...  事实库 SQLite 路径（默认内存）
  ZR_EXP_DB=...   经验库 SQLite 路径（默认内存）
零第三方依赖（stdlib http.server）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# 让本文件可直接运行：先加载 adapter（自动装配 sys.path）
from adapter import create_adapter, adapter_info, normalize_task


# ---------------------------------------------------------------- 全局配置
def load_bridge() -> object:
    """根据环境变量创建全局适配器（模块加载时执行一次）。"""
    real = os.environ.get("ZR_REAL", "0") == "1"
    embed = os.environ.get("ZR_EMBED_GLM", "0") == "1"
    fact_db = os.environ.get("ZR_FACT_DB") or None
    exp_db = os.environ.get("ZR_EXP_DB") or None
    adapter = create_adapter(real=real, embed_glm=embed,
                             fact_db=fact_db, exp_db=exp_db)
    print(f"[bridge] LLM={getattr(adapter.ctl.llm,'model','mock')} "
          f"embed={getattr(adapter.ctl.embedding,'model','mock')} "
          f"(ZR_REAL={real}, ZR_EMBED_GLM={embed})")
    return adapter


ADAPTER = load_bridge()


def _read_json(handler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


class Handler(BaseHTTPRequestHandler):
    # ---- CORS（允许智戎前端跨域调试）----
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if urlparse(self.path).path == "/healthz":
            info = adapter_info(ADAPTER)
            self._json(200, {"ok": True, "service": "zhirong_kit", **info})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = _read_json(self)
        try:
            if path == "/hook/plan":
                # 支持直接传结构化 task（智戎侧一条请求就规范化）
                if "task" in body:
                    nt = normalize_task(body["task"])
                    plan_id = nt["plan_id"]
                    goal = nt["goal"]
                    constraints = nt["constraints"]
                    queries = [q.to_dict() for q in nt["queries"]]
                else:
                    plan_id = body.get("plan_id", "ZR-" + str(hash(json.dumps(body)) % 100000))
                    goal = body.get("goal", "")
                    constraints = body.get("constraints", [])
                    queries = body.get("queries")
                r = ADAPTER.hook_plan(plan_id=plan_id, goal=goal,
                                      constraints=constraints, queries=queries)
                self._json(200, r)
            elif path == "/hook/feedback":
                self._json(200, ADAPTER.hook_feedback(
                    body.get("text", ""), structured=body.get("structured")))
            elif path == "/hook/append_feedback":
                self._json(200, ADAPTER.hook_append_feedback(
                    body.get("text", ""), structured=body.get("structured")))
            elif path == "/hook/evolve":
                self._json(200, ADAPTER.hook_evolve(
                    reason=body.get("reason", "manual"),
                    extra_review=body.get("extra_review", "")))
            elif path == "/hook/normalize":
                nt = normalize_task(body.get("task", {}))
                self._json(200, {"plan_id": nt["plan_id"], "goal": nt["goal"],
                                 "constraints": nt["constraints"],
                                 "queries": [q.to_dict() for q in nt["queries"]]})
            elif path == "/hook/close":
                self._json(200, ADAPTER.hook_close(body.get("extra_review", "")))
            else:
                self._json(404, {"error": f"unknown hook: {path}"})
        except Exception as exc:  # 桥接层兜底：不因记忆系统故障让智戎挂掉
            self._json(500, {"error": str(exc), "ok": False})


def main() -> int:
    ap = argparse.ArgumentParser(description="智戎记忆系统 HTTP 桥")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8390)
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"智戎 HTTP 桥已启动：http://{args.host}:{args.port} "
          f"（/healthz · /hook/plan · /hook/feedback · /hook/close）")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
