#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
记忆引擎契约自检脚本（离线，无需启动服务端）。

用法:
    python scripts/validate_engine.py <引擎目录名>
    例: python scripts/validate_engine.py my_engine

作用:
    校验 server/engines/<引擎目录名>/ 下模块级 engine_plugin 是否满足
    MEMORY_ENGINE_CONTRACT_VERSION 契约（validate_plugin），并打印结果。

退出码: 0=通过, 1=违规或引擎不存在, 2=用法错误。
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

def _find_project_root() -> Path:
    """向上查找包含 server/engines/memory_plugin_api.py 的项目根目录。"""
    p = Path(__file__).resolve().parent
    for _ in range(10):
        if (p / "server" / "engines" / "memory_plugin_api.py").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    raise RuntimeError("未找到项目根目录（应包含 server/engines/memory_plugin_api.py）")


_PROJECT_ROOT = _find_project_root()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def main() -> int:
    if len(sys.argv) != 2:
        print("用法: python scripts/validate_engine.py <引擎目录名>")
        print("示例: python scripts/validate_engine.py my_engine")
        return 2

    name = sys.argv[1].strip()

    from server.engines.memory_plugin_api import validate_plugin

    try:
        mod = importlib.import_module(f"server.engines.{name}")
    except Exception as e:
        print(f"[X] 导入失败 server.engines.{name}: {e}")
        print("  （确认目录名正确、不以下划线开头、不命中保留名、依赖已安装）")
        return 1

    plugin = getattr(mod, "engine_plugin", None)
    if plugin is None:
        print(f"[X] server.engines.{name} 未导出模块级 engine_plugin")
        return 1

    violations = validate_plugin(plugin)
    if violations:
        print(f"[X] 契约自检未通过（{len(violations)} 项违规）：")
        for v in violations:
            print("   -", v)
        return 1

    caps = plugin.capabilities
    print("[OK] 契约自检通过")
    print(f"   name         = {plugin.name}")
    print(f"   engine_label = {plugin.engine_label}")
    print(f"   engine_color = {plugin.engine_color}")
    print(f"   version      = {plugin.version}")
    print(f"   contract     = {plugin.contract_version}")
    print(f"   能力: ingest={caps.supports_ingest} delete={caps.supports_delete} "
          f"generate={caps.supports_generate} stream={caps.supports_stream}")
    print(f"   suffixes={caps.supported_suffixes} granularity={caps.ingest_granularity} "
          f"backend={caps.storage_backend}")
    print("   （重启服务后 GET /api/v2/memory-engine/engines 应能看到该引擎）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
