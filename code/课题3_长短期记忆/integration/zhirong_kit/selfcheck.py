# -*- coding: utf-8 -*-
"""
zhirong_kit.selfcheck — 对接前自检脚本
=======================================
一键确认：代码路径、三挂接点、时延日志、真模型/embedding 可用性，
并把报告写入 reports/selfcheck.json（验收材料）。

用法：
    python -m zhirong_kit.selfcheck            # Mock 离线自检（推荐先跑）
    python -m zhirong_kit.selfcheck --real      # 同时探测 DeepSeek 真 LLM
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_KIT = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_KIT))
_REPORTS = os.path.join(_KIT, "reports")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from memsys import MemoryType, new_entry
from adapter import create_adapter, adapter_info
from bridge_server import ADAPTER  # noqa: F401  (验证桥模块可加载)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="探测 DeepSeek 真 LLM")
    args = ap.parse_args()

    report = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": []}

    def check(name: str, ok: bool, detail: str = ""):
        report["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" —— {detail}" if detail else ""))

    print("=" * 64)
    print("智戎对接自检（zhirong_kit）")
    print("=" * 64)

    # 1) 创建适配器（Mock 离线）
    try:
        adapter = create_adapter(real=False)
        check("create_adapter（Mock）", True,
              f"LLM={getattr(adapter.ctl.llm,'model','mock')} "
              f"embed={getattr(adapter.ctl.embedding,'model','mock')}")
    except Exception as e:
        check("create_adapter（Mock）", False, str(e))
        report["ok"] = False
        _save(report)
        return 1

    # 2) 三挂接点全链路（mock 一场）
    try:
        adapter.ctl.factual.add(new_entry(
            MemoryType.FACT, "2 号高地海拔 320 米，仅东侧可装甲通行。",
            source="selfcheck", attrs={"地点": "2号高地"}))
        adapter.ctl.experiential.add(new_entry(
            MemoryType.EXPERIENCE, "教训：夜间行军未派先遣侦察。",
            source="selfcheck", importance=2.0))
        t0 = time.time()
        plan = adapter.hook_plan("SC-01", "夜间夺占 2 号高地", ["禁止越境"])
        fb = adapter.hook_feedback("推演：任务部分达成。教训：电子压制不足。")
        close = adapter.hook_close(extra_review="经验：预备队投入应提前 10 分钟。")
        ms = round((time.time() - t0) * 1000, 1)
        check("三挂接点全链路", plan["retrieved"] >= 1 and fb["ok"]
              and close.get("write", 0) >= 1,
              f"retrieved={plan['retrieved']} write={close.get('write')} "
              f"总耗时≈{ms}ms")
        summary = adapter.log.summary()
        check("时延日志齐全", summary["total_calls"] == 3 and summary["all_ok"],
              str(summary["per_hook"]))
        report["integration"] = {"plan": plan, "feedback": fb,
                                 "close": close, "log": summary}
    except Exception as e:
        check("三挂接点全链路", False, str(e))

    # 3) 真模型探测（可选）
    if args.real:
        try:
            r_adapter = create_adapter(real=True)
            r = r_adapter.ctl.llm.chat("你是连通性测试助手。", "只回复 OK")
            check("DeepSeek 真 LLM 可用", "OK" in r or "ok" in r.lower(),
                  f"model={getattr(r_adapter.ctl.llm,'model','?')} reply={r[:20]!r}")
        except Exception as e:
            check("DeepSeek 真 LLM 可用", False, str(e)[:120])

    report["ok"] = all(c["ok"] for c in report["checks"])
    _save(report)
    print("=" * 64)
    print(f"自检结果：{sum(1 for c in report['checks'] if c['ok'])}/"
          f"{len(report['checks'])} 通过"
          + ("（全部通过 ✅）" if report["ok"] else "（存在失败项）"))
    return 0 if report["ok"] else 1


def _save(report: dict) -> None:
    os.makedirs(_REPORTS, exist_ok=True)
    path = os.path.join(_REPORTS, "selfcheck.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"[报告已落盘] {path}")


if __name__ == "__main__":
    sys.exit(main())
