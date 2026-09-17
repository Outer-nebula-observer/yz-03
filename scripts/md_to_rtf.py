# -*- coding: utf-8 -*-
"""
md_to_rtf — 零依赖 Markdown → Word 可读 .doc（RTF 内容）转换
================================================================
参考《本科毕业论文撰写规范》（附件4）排版：
  - 页面：A4，边距上下左右 3cm；
  - 正文：小四(12pt) 宋体，约 1.5 倍行距，首行缩进 2 字符；
  - 一级/文档标题：三号(16pt) 黑体居中，段前段后 1 行；
  - 二级标题：三号黑体居中（同第一层次）；三级标题：四号(14pt) 黑体顶格；
  - 四级标题：小四黑体顶格；
  - 表格：三线表（顶线粗、表头下细线、底线粗，无竖线）；
  - 代码：Courier New；引用：缩进灰体。
用法：python scripts/md_to_rtf.py <输入.md> <输出.doc>
"""
from __future__ import annotations

import os
import re
import sys
from typing import List, Optional


# ================================================================ 工具
def escape(text: str) -> str:
    """转义 RTF 特殊字符，并把非 ASCII 转为 \\uN?（含 emoji 代理对）。"""
    out: List[str] = []
    for ch in text:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == "{":
            out.append("\\{")
        elif ch == "}":
            out.append("\\}")
        elif ch == "\n":
            out.append("\\line ")
        elif o < 128:
            out.append(ch)
        else:
            enc = ch.encode("utf-16-le")
            units = [enc[i] | (enc[i + 1] << 8) for i in range(0, len(enc), 2)]
            for u in units:
                out.append(f"\\u{u}?")
    return "".join(out)


def inline(text: str) -> str:
    """把行内 **加粗** 与 `代码` 转成 RTF 片段。"""
    parts: List[str] = []
    buf: List[str] = []
    i, n = 0, len(text)

    def flush():
        if buf:
            parts.append(escape("".join(buf)))
            buf.clear()

    while i < n:
        if text.startswith("**", i):
            j = text.find("**", i + 2)
            if j != -1:
                flush()
                parts.append("\\b " + escape(text[i + 2:j]) + " \\b0 ")
                i = j + 2
                continue
        if text[i] == "`":
            j = text.find("`", i + 1)
            if j != -1:
                flush()
                parts.append("\\f1 " + escape(text[i + 1:j]) + " \\f0 ")
                i = j + 1
                continue
        buf.append(text[i])
        i += 1
    flush()
    return "".join(parts)


# ================================================================ 段落
def make_para(text: str, style: str = "body") -> str:
    # 字号（half-point）：三号=32，四号=28，小四=24，五号=21
    if style == "h1" or style == "h2":
        # 一级/文档标题：三号黑体居中，段前段后约 1 行
        return (f"{{\\pard\\qc\\f3\\fs32\\sb240\\sa240 "
                f"{escape(text)}\\par}}")
    if style == "h3":
        # 第二层次：四号黑体顶格
        return (f"{{\\pard\\ql\\f3\\fs28\\sb240\\sa240 "
                f"{escape(text)}\\par}}")
    if style == "h4":
        # 其余层次：小四黑体顶格
        return (f"{{\\pard\\ql\\f3\\fs24\\sb120\\sa120 "
                f"{escape(text)}\\par}}")
    if style == "quote":
        return f"{{\\pard\\ql\\li480\\fi-480\\f0\\fs24\\cf2 {inline(text)}\\par}}"
    if style == "code":
        return f"{{\\pard\\ql\\li360\\f1\\fs20 {escape(text)}\\f0\\par}}"
    if style == "bullet":
        return (f"{{\\pard\\ql\\fi-240\\li480\\f0\\fs24 "
                f"\\bullet\\tab {inline(text)}\\par}}")
    if style == "table_h":
        return f"{{\\pard\\intbl\\b {inline(text)}\\b0 \\par}}"
    if style == "table_b":
        return f"{{\\pard\\intbl {inline(text)}\\par}}"
    # 正文：小四宋体、1.5 倍行距、首行缩进 2 字符
    return (f"{{\\pard\\ql\\fi480\\f0\\fs24\\sl360\\slmult1 "
            f"{inline(text)}\\par}}")


def make_table(rows: List[List[str]]) -> str:
    """三线表：表头上下线（顶粗底细），末行底线粗，无竖线。"""
    if not rows:
        return ""
    n_cols = max(len(r) for r in rows)
    total = 9360          # A4 - 3cm*2 边距 ≈ 9360 twips
    widths = [total // n_cols] * n_cols
    widths[-1] += total - sum(widths)
    cellx = []
    acc = 0
    for w in widths:
        acc += w
        cellx.append(acc)

    out = []
    for ri, row in enumerate(rows):
        cells = [c if c else "" for c in row] + [""] * (n_cols - len(row))
        is_head = ri == 0
        is_last = ri == len(rows) - 1
        style = "table_h" if is_head else "table_b"
        cell_rtf = []
        for ci, c in enumerate(cells):
            # 边框：顶线（表头粗），底线（表头细/末行粗），左右无
            brdr = ""
            if is_head:
                brdr = "\\clbrdrt\\brdrs\\brdrw20\\clbrdrb\\brdrs\\brdrw5"
            elif is_last:
                brdr = "\\clbrdrb\\brdrs\\brdrw20"
            cell_rtf.append(
                f"{brdr}\\cellx{cellx[ci]} "
                f"\\intbl {make_para_cell(c, style)} \\cell")
        out.append(f"\\trowd\\trgaph108\\trleft0 " + "".join(cell_rtf) + "\\row")
    return "".join(out)


def make_para_cell(text: str, style: str) -> str:
    if style == "table_h":
        return f"\\pard\\intbl\\b {inline(text)}\\b0 "
    return f"\\pard\\intbl {inline(text)} "


# ================================================================ 主转换
def convert(md_text: str) -> str:
    lines = md_text.splitlines()
    out: List[str] = []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            j = i + 1
            code: List[str] = []
            while j < n and not lines[j].strip().startswith("```"):
                code.append(lines[j])
                j += 1
            for ln in code:
                out.append(make_para(ln, style="code"))
            i = j + 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            rows: List[List[str]] = []
            while i < n and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                out.append(make_table(rows))
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            out.append(make_para(m.group(2).strip(),
                                 style="h" + str(len(m.group(1)))))
            i += 1
            continue

        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            out.append("{\\pard\\brdrb\\brdrs\\brdrw10\\brsp40\\par}")
            i += 1
            continue

        if stripped.startswith(">"):
            out.append(make_para(stripped.lstrip(">").strip(), style="quote"))
            i += 1
            continue

        if re.match(r"^[-*]\s+", stripped):
            out.append(make_para(re.sub(r"^[-*]\s+", "", stripped),
                                 style="bullet"))
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        if re.match(r"^\[\d+\]\s+", stripped):
            out.append(make_para(stripped, style="ref"))
            i += 1
            continue
        out.append(make_para(stripped, style="body"))
        i += 1

    header = (
        "{\\rtf1\\ansi\\ansicpg936"
        "{\\fonttbl"
        "{\\f0\\fnil\\fcharset134 SimSun;}"          # 宋体（中文正文）
        "{\\f1\\fmodern\\fcharset0 Courier New;}"     # 代码
        "{\\f2\\fswiss\\fcharset0 Times New Roman;}"  # 西文（规范要求）
        "{\\f3\\fnil\\fcharset134 SimHei;}}"          # 黑体（标题）
        "{\\colortbl ;\\red0\\green0\\blue0;\\red80\\green80\\blue80;}"
        # A4：宽 11906 / 高 16838 twips；边距上下左右 3cm≈1701 twips
        "\\paperw11906\\paperh16838"
        "\\margl1701\\margr1701\\margt1701\\margb1701"
        "\\deflang2052"
        "\\pard\\f0\\fs24\n"
    )
    footer = "\n}"
    return header + "\n".join(out) + footer


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: python scripts/md_to_rtf.py <输入.md> <输出.doc>")
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        md = f.read()
    rtf = convert(md)
    try:
        with open(dst, "w", encoding="utf-8", errors="replace") as f:
            f.write(rtf)
        final = dst
    except PermissionError:
        # Windows 下目标可能被 Word 打开，自动写到 _new.doc
        base, ext = os.path.splitext(dst)
        final = base + "_new" + ext
        with open(final, "w", encoding="utf-8", errors="replace") as f:
            f.write(rtf)
        print(f"[警告] {dst} 被占用，已生成替代文件：{final}")
    size = len(rtf.encode("utf-8"))
    print(f"[完成] {final} 已生成（{size} 字节），采用《本科毕业论文撰写规范》排版")
    return 0


if __name__ == "__main__":
    sys.exit(main())
