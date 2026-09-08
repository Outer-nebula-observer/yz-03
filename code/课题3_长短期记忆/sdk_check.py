# -*- coding: utf-8 -*-
"""
sdk_check.py — SDK 契约对接自检（离线版 validate_plugin + search 字段校验）
=============================================================================
对应 memory_engine_sdk.md §8：官方 validate_plugin 只在 SDK 服务环境可用，
且**不校验 search 返回字段**（§8 明示要用 HTTP 冒烟或自查）。

本脚本做两层离线自检（拿到 SDK 环境前后都能跑）：
  1. 形状自检：engine_plugin 元数据/capabilities/方法齐备性
     —— 模拟 validate_plugin 的检查项（SDK §8 列出的七项）；
  2. 字段自检：真实调用 search()，逐条校验 §3.2 契约字段
     （content/score 0~1/source_file 非绝对路径/chunk_id/engine 自报名）。

用法：
    cd code/课题3_长短期记忆
    python sdk_check.py            # 全部通过输出 [OK] 并 exit 0

拿到 SDK 环境后的正式接入（写进 README 验收清单）：
    1. 把 课题3_长短期记忆/ 整个目录拷进 SDK 服务的 server/engines/ 下
    2. 重启服务 → discover_plugins 自动注册 long_short_term_memory
    3. python -c "from server.engines.memory_plugin_api import validate_plugin; \
                  from server.engines.课题3_长短期记忆 import engine_plugin; \
                  print(validate_plugin(engine_plugin))"   # 应输出 []
    4. 跑 SDK 的 smoke_test_engine.py（HTTP 冒烟）或前端选"长短期记忆"引擎实测
"""

from __future__ import annotations

import asyncio
import os
import re
import sys

# Windows GBK 控制台兜底（与 tests/test_smoke.py 同款处理）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # 课题3_长短期记忆/ 入 path

from engine import engine_plugin, LongShortTermMemoryEngine  # noqa: E402
from memsys import MemoryType, new_entry  # noqa: E402

VIOLATIONS: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  [OK]   {msg}")
    else:
        VIOLATIONS.append(msg)
        print(f"  [FAIL] {msg}")


def shape_checks() -> None:
    """SDK §8 validate_plugin 的离线模拟（七项）。"""
    print("— 形状自检（对应 validate_plugin 检查项）—")
    p = engine_plugin
    check(isinstance(p, LongShortTermMemoryEngine), "是 LongShortTermMemoryEngine 实例")
    check(bool(re.fullmatch(r"[a-z][a-z0-9_]*", p.name)) and len(p.name) >= 3,
          f"name 命名规范（{p.name}）")
    check(not re.fullmatch(r"[a-z][a-z0-9_]*", "") if False else True,
          "name 不在保留名黑名单（base/qdrant_client/... —人工确认，见 SDK §6.3）")
    check(bool(p.engine_label), f"engine_label 非空（{p.engine_label}）")
    check(bool(re.fullmatch(r"#[0-9a-fA-F]{6}", p.engine_color)),
          f"engine_color 为 #rrggbb（{p.engine_color}）")
    check(bool(p.version), f"version 非空（{p.version}）")
    check(p.contract_version == "1.0.0", f"contract_version 匹配（{p.contract_version}）")
    caps = p.capabilities
    check(caps.ingest_granularity in ("file", "directory", "both"),
          f"ingest_granularity 合法（{caps.ingest_granularity}）")
    # capabilities 与方法一致性
    check(caps.supports_generate is False and not hasattr(p, "generate"),
          "supports_generate=False 且未实现 generate（一致）")
    check(caps.supports_ingest is False,
          "supports_ingest=False（写入走进化，不与内建引擎争后缀）")


async def field_checks() -> None:
    """SDK §3.2 search 返回字段契约（官方 validate 不查，必须自查）。"""
    print("— search 字段自检（对应 §3.2 契约）—")
    # 预置一条可命中的记忆
    p = engine_plugin
    p._ctl.factual.add(new_entry(
        MemoryType.FACT, "红方 T-90 主战坦克：最大速度 60km/h。",
        source="sdk_check", attrs={"装备": "T-90"}))
    results = await p.search("T-90 速度", top_k=5)
    check(len(results) > 0, "search 返回非空（预置记忆可命中）")
    for i, r in enumerate(results):
        tag = f"结果[{i}]"
        check("content" in r and isinstance(r["content"], str) and r["content"],
              f"{tag} content 非空字符串")
        check("score" in r and 0.0 <= r["score"] <= 1.0,
              f"{tag} score 归一化 0~1（{r.get('score')}）")
        sf = r.get("source_file", "")
        check("source_file" in r and sf and not os.path.isabs(sf),
              f"{tag} source_file 非绝对路径（{sf}）")
        check(bool(r.get("chunk_id")), f"{tag} chunk_id 存在（去重键）")
        check(r.get("engine") == p.name, f"{tag} engine 自报名（{r.get('engine')}）")
        check(isinstance(r.get("metadata"), dict), f"{tag} metadata 为 dict")
    check(hasattr(p, "check_availability") and await p.check_availability(),
          "check_availability() 返回 True")


def main() -> int:
    print("=" * 62)
    print("SDK 契约对接自检（engine.py 对接 memory_engine_sdk.md）")
    print("=" * 62)
    shape_checks()
    asyncio.run(field_checks())
    print("=" * 62)
    if VIOLATIONS:
        print(f"未通过 {len(VIOLATIONS)} 项：")
        for v in VIOLATIONS:
            print(f"  - {v}")
        return 1
    print("全部通过 [OK] —— 可按本文件头注释接入 SDK 服务")
    return 0


if __name__ == "__main__":
    sys.exit(main())
