# -*- coding: utf-8 -*-
"""
打包交付脚本：生成「课题3_长短期记忆」干净交付 zip
====================================================
用途：
    给陈玉锋老师/智戎集成发送代码前，自动排除 .env、密钥、缓存、
    __pycache__、临时数据库、日志等不需要的东西。

用法：
    Windows PowerShell:
        python pack_delivery.py
    WSL / Linux:
        python3 pack_delivery.py

输出：
    dist/课题3_长短期记忆_交付.zip
    内含：
        ├── 课题3_长短期记忆/          # 完整可运行代码（核心包 + 智戎对接套装）
        ├── .env.example              # 真模型配置模板（无密钥，可放心发）
        └── 交付说明.md               # 给集成方看的快速说明

安全约定：
    - 任何 .env / .env.*（除 .env.example）都不会进包；
    - 任何 __pycache__、*.pyc、*.db、*.sqlite、*.log 等都不会进包；
    - 包内不包含 API Key。
"""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "code" / "课题3_长短期记忆"
DIST_DIR = REPO_ROOT / "dist"
OUT_ZIP = DIST_DIR / "课题3_长短期记忆_交付.zip"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

# 交付包内主目录名（保持原项目名，便于老师识别）
TOP_DIR = "课题3_长短期记忆"

# ---------------------------------------------------------------------------
# 排除规则
# ---------------------------------------------------------------------------
# 目录名（出现在任意层级即排除整个目录）
EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "node_modules",
}

# 文件名后缀（匹配即排除）
EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".tmp",
    ".bak",
    ".orig",
    ".rej",
}

# 文件名黑名单（匹配即排除；.env.example 属于白名单，会单独加入）
EXCLUDE_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
}


def _is_env_secret(rel_path: Path) -> bool:
    """排除 .env*，但保留 .env.example。"""
    name = rel_path.name
    if name == ".env.example":
        return False
    return name.startswith(".env") and (
        name == ".env" or name.startswith(".env.")
    )


def is_excluded(rel_path: Path) -> bool:
    """判断相对路径是否应排除。rel_path 相对于 SRC_DIR。"""
    parts = rel_path.parts

    # 目录名排除
    if any(part in EXCLUDE_DIR_NAMES for part in parts):
        return True

    # 隐藏 .git 等（保险）
    if any(part == ".git" for part in parts):
        return True

    # .env 密钥文件
    if _is_env_secret(rel_path):
        return True

    # 文件名黑名单
    if rel_path.name in EXCLUDE_FILE_NAMES:
        return True

    # 后缀排除
    if rel_path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True

    return False


# ---------------------------------------------------------------------------
# 打包
# ---------------------------------------------------------------------------
def main() -> int:
    if not SRC_DIR.is_dir():
        print(f"[错误] 找不到源码目录：{SRC_DIR}", file=sys.stderr)
        return 1

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()

    included_count = 0
    excluded_count = 0
    total_bytes = 0

    with zipfile.ZipFile(
        OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
    ) as zf:
        # 1) 主代码目录
        for root, dirs, files in os.walk(SRC_DIR):
            # 原地剪枝，避免进入排除目录
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_NAMES]

            for fname in files:
                full = Path(root) / fname
                rel = full.relative_to(SRC_DIR)

                if is_excluded(rel):
                    excluded_count += 1
                    continue

                arcname = f"{TOP_DIR}/{rel.as_posix()}"
                zf.write(full, arcname)
                included_count += 1
                total_bytes += full.stat().st_size

        # 2) .env.example（配置模板，无密钥；放在 zip 根目录，和项目文件夹平级）
        if ENV_EXAMPLE.is_file():
            zf.write(ENV_EXAMPLE, ".env.example")
            included_count += 1
            total_bytes += ENV_EXAMPLE.stat().st_size
        else:
            print("[警告] 未找到 .env.example，未加入配置模板", file=sys.stderr)

        # 3) 交付说明
        delivery_note = (
            "# 交付说明\n\n"
            "## 这是什么\n"
            f"- `{TOP_DIR}/` —— 课题③「异构多模态数据环境下大模型作战规划智能体记忆系统构建」"
            "（长短期记忆系统）完整可运行代码。\n"
            "- `.env.example` —— 真模型配置模板（不含密钥）；如需使用 DeepSeek/GLM，"
            "请把它复制为 `.env` 并填入密钥后再运行。\n\n"
            "## 智戎对接入口\n"
            f"代码已包含智戎适配：`{TOP_DIR}/integration/zhirong_kit/`。\n\n"
            "### 快速验证（零依赖，离线可跑）\n"
            "```bash\n"
            f"cd {TOP_DIR}\n"
            "python tests/test_smoke.py\n"
            "python integration/zhirong_kit/selfcheck.py\n"
            "python integration/zhirong_kit/p0_test.py\n"
            "```\n\n"
            "### 三种接入方式\n"
            "1. Python 内嵌：`from integration.zhirong_kit.adapter import create_adapter`\n"
            "2. HTTP 桥：`python integration/zhirong_kit/bridge_server.py --port 8390`\n"
            "3. 老师 SDK：将 `课题3_长短期记忆/` 放入 SDK `server/engines/`，"
            "引擎名为「长短期记忆」。\n\n"
            "详细对接手册见 `integration/zhirong_kit/README.md`。\n"
        )
        zf.writestr("交付说明.md", delivery_note.encode("utf-8"))
        included_count += 1
        total_bytes += len(delivery_note.encode("utf-8"))

    size_mb = OUT_ZIP.stat().st_size / 1024 / 1024
    print("打包完成：")
    print(f"  输出文件 : {OUT_ZIP}")
    print(f"  包含文件 : {included_count}")
    print(f"  排除文件 : {excluded_count}")
    print(f"  原始体积 : {total_bytes / 1024 / 1024:.2f} MB")
    print(f"  压缩体积 : {size_mb:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
