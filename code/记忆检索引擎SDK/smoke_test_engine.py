#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
记忆引擎 HTTP 冒烟测试（需服务端已启动）。

用法:
    python scripts/smoke_test_engine.py <引擎名> [base_url]
    例: python scripts/smoke_test_engine.py my_engine
        python scripts/smoke_test_engine.py my_engine http://127.0.0.1:8000

作用:
    1. GET  /api/v2/memory-engine/engines  -> 确认引擎已注册、available
    2. POST /api/v2/memory-engine/search   -> 用该引擎检索并打印返回字段

curl 等价:
    curl http://127.0.0.1:8000/api/v2/memory-engine/engines
    curl -X POST http://127.0.0.1:8000/api/v2/memory-engine/search -H "Content-Type: application/json" -d '{"query":"测试","engines":["my_engine"],"top_k":5}'

PowerShell 等价:
    Invoke-RestMethod http://127.0.0.1:8000/api/v2/memory-engine/engines
    Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v2/memory-engine/search -ContentType 'application/json' -Body '{"query":"测试","engines":["my_engine"],"top_k":5}'
"""
from __future__ import annotations

import json
import sys
import urllib.request

_DEFAULT_BASE = "http://127.0.0.1:8000"


def _request(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python scripts/smoke_test_engine.py <引擎名> [base_url]")
        return 2
    name = sys.argv[1]
    base = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else _DEFAULT_BASE

    # 1) 引擎列表
    engines = _request("GET", f"{base}/api/v2/memory-engine/engines")
    names = [e.get("name") for e in engines]
    if name not in names:
        print(f"[X] 引擎 {name!r} 未注册。当前已注册: {names}")
        return 1
    meta = next(e for e in engines if e.get("name") == name)
    print(f"[OK] 引擎已注册: label={meta.get('engine_label')} available={meta.get('available')}")

    # 2) 检索
    resp = _request("POST", f"{base}/api/v2/memory-engine/search", {
        "query": "测试查询",
        "engines": [name],
        "top_k": 5,
    })
    results = resp.get("results", [])
    print(f"[OK] 检索返回 {len(results)} 条:")
    for r in results:
        print(f"   - [{r.get('engine')}] score={r.get('score')} source={r.get('source_file')}")
        print(f"     {str(r.get('content'))[:80]}")
    if not results:
        print("   （0 条：确认该引擎已摄入检索数据，或换一个查询词）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
