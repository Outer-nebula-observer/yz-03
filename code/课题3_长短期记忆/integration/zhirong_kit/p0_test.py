# -*- coding: utf-8 -*-
"""
zhirong_kit.p0_test — P0 场景适配功能测试（可复现）
====================================================
覆盖 docs/20 P0 的四个落地能力：
  T1 normalize_task           中文/英文别名、自带查询、无查询兜底
  T2 structured_to_review     成功/失败/部分/空 的转写
  T3 事件驱动进化（无 session） 多次反馈累积 → hook_evolve 沉淀
  T4 事件驱动进化（有 session） hook_plan 后 evolve 正常收场
  T5 重复触发幂等            连续 evolve 不会重复写入（θ 查重）
  T6 domain_check 示例        命令行巡检可运行并生成 min_score 建议

用法：
    python integration/zhirong_kit/p0_test.py
输出：控制台 PASS/FAIL + reports/p0_test.json（可验收）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

_KIT = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_KIT))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from adapter import (create_adapter, normalize_task, structured_to_review,
                     ZhirongEventAdapter)
from memsys import MemoryType, new_entry

RESULTS = []
_PASS = _TOTAL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _PASS, _TOTAL
    _PASS += 1 if ok else 0
    _TOTAL += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" —— {detail}" if detail else ""))
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    print("=" * 66)
    print("P0 场景适配功能测试（zhirong_kit）")
    print("=" * 66)

    # ---------- T1 normalize_task ----------
    print("\n== T1 任务规范化 ==")
    t_cn = normalize_task({"task_id": "CN-1", "目标": "夜间夺占 2 号高地", "约束": ["禁止越境"]})
    check("中文别名（目标/约束）", t_cn["goal"] == "夜间夺占 2 号高地"
          and t_cn["constraints"] == ["禁止越境"], str(t_cn["queries"][:1])[:60])
    t_en = normalize_task({"id": "EN-1", "objective": "Test Objective", "constraints": ["A"]})
    check("英文别名（id/objective/constraints）",
          t_en["plan_id"] == "EN-1" and t_en["goal"] == "Test Objective"
          and t_en["constraints"] == ["A"])
    t_q = normalize_task({"goal": "任务", "queries": [
        {"q_id": "q1", "intent": "查", "target": "fact", "route": "vector",
         "query_text": "地形"}]})
    check("自带查询→QueryItem", len(t_q["queries"]) == 1
          and t_q["queries"][0].query_text == "地形")
    t_no = normalize_task({"goal": "夜间夺占 2 号高地"})
    check("无查询→阶段模板兜底", len(t_no["queries"]) >= 2, f"{len(t_no['queries'])} 条")

    # ---------- T2 structured_to_review ----------
    print("\n== T2 结构化反馈转写 ==")
    r_fail = structured_to_review({"result": "fail", "metrics": {"伤亡": 3},
                                   "events": [{"desc": "伏击"}]})
    check("fail → 含‘教训’", "教训" in r_fail, r_fail[:40])
    r_ok = structured_to_review({"result": "success", "metrics": {"时间": 2}})
    check("success → 含‘经验’", "经验" in r_ok, r_ok[:40])
    r_part = structured_to_review({"result": "partially"})
    check("partially → 不误加教训/经验",
          "教训" not in r_part and "经验" not in r_part, r_part[:40])
    r_empty = structured_to_review({})
    check("空 payload → 不崩且无教训/经验",
          isinstance(r_empty, str) and "教训" not in r_empty)

    # ---------- T3 事件驱动（无 session） ----------
    print("\n== T3 事件驱动：无 open session ==")
    a = create_adapter(real=False)
    a.hook_append_feedback("复盘：第一段反馈。")
    a.hook_append_feedback("", structured={"result": "fail",
                                           "metrics": {"伤亡": 2},
                                           "events": [{"desc": "通信被干扰"}]})
    before = a.ctl.experiential.stats()["count"]
    r3 = a.hook_evolve(reason="periodic", extra_review="复盘：教训：电子压制不足。")
    after = a.ctl.experiential.stats()["count"]
    check("多次反馈累积→事件驱动进化写入",
          r3.get("ok") and r3.get("summary", {}).get("write", 0) >= 1
          and after > before,
          f"write={r3.get('summary',{}).get('write')} 库 {before}→{after}")
    check("无 session 也能进化（不依赖 hook_plan）", r3.get("ok") is True)
    check("缓冲已清空（不重复消费）", a._feedback_text == "",
          f"buffered={len(a._feedback_text)}")

    # ---------- T4 事件驱动（有 session） ----------
    print("\n== T4 事件驱动：有 open session（正常收场） ==")
    b = create_adapter(real=False)
    b.hook_plan("S1", "夜间夺占 2 号高地", ["禁止越境"])
    b.hook_append_feedback("复盘：推演结果。", structured={"result": "fail"})
    r4 = b.hook_evolve(reason="session_end", extra_review="")
    check("有 session 时 evolve 走正常收场且写入",
          r4.get("ok") and b.ctl.working_memory is None
          and r4.get("summary", {}).get("write", 0) >= 1,
          f"write={r4.get('summary',{}).get('write')}")

    # ---------- T5 重复触发幂等 ----------
    print("\n== T5 重复触发幂等（θ 查重） ==")
    c = create_adapter(real=False)
    c.hook_append_feedback("复盘：教训：夜间突袭未前置电子压制。")
    n1 = c.hook_evolve(reason="manual", extra_review="")["summary"]["write"]
    c.hook_append_feedback("复盘：教训：夜间突袭未前置电子压制。")   # 相同教训再触发
    n2 = c.hook_evolve(reason="manual", extra_review="")["summary"]["write"]
    check("重复教训不会重复写入（幂等）", n1 >= 1 and n2 == 0, f"第一次write={n1} 第二次write={n2}")

    # ---------- T6 domain_check 示例 ----------
    print("\n== T6 domain_check 示例 ==")
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(_KIT, "domain_check.py"),
             "--seed-campaign", "heights_battle",
             "--samples", os.path.join(_KIT, "reports", "_demo_samples.json")],
            capture_output=True, text=True, timeout=60)
        out = proc.stdout
        check("domain_check 可运行且 exit=0", proc.returncode == 0,
              f"tail={out.strip().splitlines()[-2:]}")
        report_path = os.path.join(_KIT, "reports", "domain_check.json")
        check("domain_check 报告落盘", os.path.exists(report_path),
              report_path)
    except Exception as e:
        check("domain_check 可运行且 exit=0", False, str(e))
        check("domain_check 报告落盘", False, str(e))

    # ---------- 汇总 ----------
    print("\n" + "=" * 66)
    print(f"P0 功能测试：{_PASS}/{_TOTAL} 通过"
          + ("（全部通过 ✅）" if _PASS == _TOTAL else "（存在失败项）"))
    os.makedirs(os.path.join(_KIT, "reports"), exist_ok=True)
    with open(os.path.join(_KIT, "reports", "p0_test.json"), "w",
              encoding="utf-8") as f:
        json.dump({"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "pass": _PASS, "total": _TOTAL, "checks": RESULTS},
                  f, ensure_ascii=False, indent=2)
    print(f"[报告已落盘] {os.path.join(_KIT, 'reports', 'p0_test.json')}")
    return 0 if _PASS == _TOTAL else 1


if __name__ == "__main__":
    sys.exit(main())
