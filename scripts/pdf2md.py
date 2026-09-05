# -*- coding: utf-8 -*-
"""
PDF 转 Markdown 脚本（使用 pymupdf4llm）—— 已在本仓库"固化"，供论文提取复用。

来源：本脚本沿用《调研工作区》的 pdf2md.py 方法（pymupdf4llm.to_markdown），
并扩展为"单文件 + 批量目录"两种用法，统一输出到 PDF 同目录下的同名 .md。

用法（在仓库根目录运行）：
    # 1) 单篇
    python scripts/pdf2md.py "references/02_长期记忆/Shinn2023-Reflexion.pdf"

    # 2) 批量提取 references 下所有 PDF（每篇输出 <同名>.md，已存在则跳过）
    python scripts/pdf2md.py --all

    # 3) 指定目录（递归扫描其中所有 .pdf）
    python scripts/pdf2md.py --dir references/04_记忆进化

    # 4) 强制覆盖已生成的 .md
    python scripts/pdf2md.py --all --force

环境说明：
    - 依赖 pymupdf4llm。若当前 python 未安装，可复用《调研工作区》的虚拟环境：
        "C:/Users/20784/Desktop/调研工作区/.venv/Scripts/python.exe" scripts/pdf2md.py --all
    - 更稳妥：在仓库内自建 .venv 并 `pip install pymupdf4llm`，见本文件末尾注释。

输出：
    - 在 PDF 同目录下生成同名 .md（纯 Markdown 全文，供精读与总结使用）。
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TARGET_DIRS = [
    "00_综述",
    "01_短期记忆",
    "02_长期记忆",
    "03_记忆检索",
    "04_记忆进化",
    "05_记忆评估",
]


def pdf_to_markdown(pdf_path: str, force: bool = False) -> str:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"文件不存在: {pdf_path}")
    if not pdf_path.lower().endswith(".pdf"):
        raise ValueError(f"不是 PDF 文件: {pdf_path}")

    md_path = pdf_path[:-4] + ".md"
    if os.path.exists(md_path) and not force:
        size_kb = os.path.getsize(md_path) / 1024
        print(f"[跳过] 已存在: {md_path} ({size_kb:.1f} KB)，用 --force 覆盖")
        return md_path

    print(f"[转换] {pdf_path} -> {md_path}")
    import pymupdf4llm

    md_text = pymupdf4llm.to_markdown(pdf_path)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    size_kb = os.path.getsize(md_path) / 1024
    print(f"[完成] {md_path} ({size_kb:.1f} KB)")
    return md_path


def collect_pdfs(target) -> list:
    """给定一个文件/目录，返回需要处理的 PDF 列表。"""
    if os.path.isfile(target):
        return [target] if target.lower().endswith(".pdf") else []
    pdfs = []
    for root, _dirs, files in os.walk(target):
        for fn in sorted(files):
            if fn.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, fn))
    return pdfs


def main():
    parser = argparse.ArgumentParser(description="PDF 转 Markdown（pymupdf4llm）")
    parser.add_argument("paths", nargs="*", help="一个或多个 PDF 文件路径")
    parser.add_argument("--all", action="store_true", help="批量提取 references 下所有 PDF")
    parser.add_argument("--dir", help="递归提取指定目录下的所有 PDF")
    parser.add_argument("--force", action="store_true", help="覆盖已生成的 .md")
    args = parser.parse_args()

    targets = list(args.paths)
    if args.dir:
        targets.append(args.dir)
    if args.all:
        targets.extend(os.path.join(ROOT, "references", d) for d in DEFAULT_TARGET_DIRS)

    if not targets:
        print(__doc__)
        sys.exit(1)

    pdfs = []
    for t in targets:
        pdfs.extend(collect_pdfs(t))
    # 去重保序
    seen, uniq = set(), []
    for p in pdfs:
        if p not in seen:
            seen.add(p)
            uniq.append(p)

    if not uniq:
        print("未找到任何 PDF 文件。")
        sys.exit(0)

    print(f"共 {len(uniq)} 个 PDF 待处理：")
    ok, fail = 0, 0
    for p in uniq:
        try:
            pdf_to_markdown(p, args.force)
            ok += 1
        except Exception as exc:
            print(f"[错误] {p} -> {exc}", file=sys.stderr)
            fail += 1

    print(f"\n===== 汇总：成功 {ok}，失败 {fail} =====")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()

# 自建虚拟环境（可选，若不想依赖调研工作区的 venv）：
#   python -m venv .venv
#   .venv/Scripts/python.exe -m pip install pymupdf4llm
#   .venv/Scripts/python.exe scripts/pdf2md.py --all
