# -*- coding: utf-8 -*-
"""
md_to_rtf — 零依赖 Markdown → Word 可读 .doc（RTF 内容）转换
================================================================
用途：在无 pandoc / python-docx / LibreOffice 的环境下，把 Markdown
报告排版为 Word 可直接打开的 .doc（内部为 RTF，Word 不报格式不匹配）。

支持：标题 1-4、段落、无序列表、表格、代码块、引用、分隔线、
行内加粗 `**`、行内代码 `` ` ``、Unicode/emoji（RTF \\u 编码）。

用法：
    python scripts/md_to_rtf.py 输入.md 输出.doc
示例：
    python scripts/md_to_rtf.py docs/17_实验报告.md docs/实验报告.doc
"""
from __future__ import annotations

import re
import sys
from typing import List, Optional, Tuple


def escape(text: str) -> str:
    """转义 RTF 特殊字符，并把非 ASCII 转为 \\uN? 编码（含 emoji 代理对）。"""
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
            # 按 UTF-16 code units 输出，每单位一个 \uN?
            for b in ch.encode("utf-16-le"):
                # 每两个字节一组（低字节在前）
                pass
            enc = ch.encode("utf-16-le")
            units = [enc[i] | (enc[i + 1] << 8) for i in range(0, len(enc), 2)]
            for u in units:
                out.append(f"\\u{u}?")
    return "".join(out)


def inline(text: str) -> str:
    """把行内 **加粗** 与 `代码` 转成 RTF 片段。"""
    # 用 token 扫描：识别 **...** 与 `...`
    parts: List[str] = []
    i = 0
    buf: List[str] = []
    n = len(text)

    def flush_buf(plain: bool = True):
        if buf:
            raw = "".join(buf)
            parts.append(escape(raw))
            buf.clear()

    while i < n:
        if text.startswith("**", i):
            # 找结束
            j = text.find("**", i + 2)
            if j != -1:
                flush_buf()
                parts.append("\\b " + escape(text[i + 2:j]) + " \\b0 ")
                i = j + 2
                continue
        if text[i] == "`":
            j = text.find("`", i + 1)
            if j != -1:
                flush_buf()
                parts.append("\\f1 " + escape(text[i + 1:j]) + " \\f0 ")
                i = j + 1
                continue
        buf.append(text[i])
        i += 1
    flush_buf()
    return "".join(parts)


def make_para(text: str, style: str = "body") -> str:
    """生成一个段落。style: body / h1 / h2 / h3 / h4 / quote / code / bullet / table_h / table_b"""
    if style.startswith("h"):
        sizes = {"h1": 36, "h2": 30, "h3": 26, "h4": 24}
        fs = sizes.get(style, 24)
        align = "\\qc" if style == "h1" else "\\ql"
        return f"{{\\pard {align} \\b\\fs{fs} {escape(text)}\\b0\\fs22\\par}}"
    if style == "quote":
        return f"{{\\pard\\ql\\li480\\i\\cf2 {inline(text)}\\i0\\par}}"
    if style == "code":
        return f"{{\\pard\\ql\\li360\\f1\\fs20 {escape(text)}\\f0\\fs22\\par}}"
    if style == "bullet":
        return f"{{\\pard\\ql\\li480\\bullet\\tab {inline(text)}\\par}}"
    if style == "table_h":
        return f"{{\\pard\\intbl\\b {inline(text)}\\b0 \\par}}"
    if style == "table_b":
        return f"{{\\pard\\intbl {inline(text)}\\par}}"
    return f"{{\\pard\\ql\\sl360\\slmult1 {inline(text)}\\par}}"


def make_table(rows: List[List[str]], widths_pct: Optional[List[int]] = None) -> str:
    """RTF 表格：首行表头加粗，所有行加边框。"""
    if not rows:
        return ""
    n_cols = max(len(r) for r in rows)
    widths = widths_pct or [100 // n_cols] * n_cols
    # 页面可用宽度约 9360 twips（A4 减边距后）
    total = 9360
    cellx = []
    acc = 0
    for w in widths:
        acc += int(total * w / 100)
        cellx.append(acc)
    rows_rtf = []
    for ri, row in enumerate(rows):
        cells = [c if c else "" for c in row]
        cells = cells + [""] * (n_cols - len(cells))
        style = "table_h" if ri == 0 else "table_b"
        cells_rtf = []
        for ci, c in enumerate(cells):
            cells_rtf.append(
                f"\\clbrdrt\\brdrs\\brdrw10\\clbrdrl\\brdrs\\brdrw10"
                f"\\clbrdrb\\brdrs\\brdrw10\\clbrdrr\\brdrs\\brdrw10"
                f"\\cellx{cellx[ci]} \\intbl {make_para_cell(c, style)} \\cell")
        rows_rtf.append(f"\\trowd\\trgaph108\\trleft0 " + "".join(cells_rtf) + "\\row")
    return "".join(rows_rtf)


def make_para_cell(text: str, style: str) -> str:
    """表格单元格内的段落（RTF 单元格由 \\cell 收尾）。"""
    if style == "table_h":
        return f"\\pard\\intbl\\b {inline(text)}\\b0 "
    return f"\\pard\\intbl {inline(text)} "


def convert(md_text: str) -> str:
    lines = md_text.splitlines()
    out: List[str] = []
    i = 0
    n = len(lines)

    def flush_code_block(tokens: List[str]):
        for ln in tokens:
            out.append(make_para(ln, style="code"))

    while i < n:
        line = lines[i]
        stripped = line.strip()
        # 代码块
        if stripped.startswith("```"):
            j = i + 1
            code: List[str] = []
            while j < n and not lines[j].strip().startswith("```"):
                code.append(lines[j])
                j += 1
            flush_code_block(code)
            i = j + 1
            continue
        # 表格块
        if stripped.startswith("|") and stripped.endswith("|"):
            rows: List[List[str]] = []
            while i < n and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                # 跳过 |---|---| 分隔行
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                out.append(make_table(rows))
            continue
        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            out.append(make_para(m.group(2).strip(), style="h" + str(len(m.group(1)))))
            i += 1
            continue
        # 水平分隔线
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            out.append("{\\pard\\brdrb\\brdrs\\brdrw10\\brsp40\\par}")
            i += 1
            continue
        # 引用
        if stripped.startswith(">"):
            out.append(make_para(stripped.lstrip(">").strip(), style="quote"))
            i += 1
            continue
        # 无序列表
        if re.match(r"^[-*]\s+", stripped):
            out.append(make_para(re.sub(r"^[-*]\s+", "", stripped), style="bullet"))
            i += 1
            continue
        # 空行
        if not stripped:
            i += 1
            continue
        # 普通段落
        out.append(make_para(stripped, style="body"))
        i += 1

    header = (
        "{\\rtf1\\ansi\\ansicpg936"
        "{\\fonttbl{\\f0\\fnil\\fcharset134 SimSun;}"
        "{\\f1\\fmodern\\fcharset0 Courier New;}"
        "{\\f2\\fswiss\\fcharset0 Calibri;}}"
        "{\\colortbl ;\\red0\\green0\\blue0;\\red70\\green70\\blue70;}"
        "\\paperw11906\\paperh16838\\margl1440\\margr1440\\margt1200\\margb1200"
        "\\deflang2052"
        "\\pard\\f0\\fs22\n"
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
    with open(dst, "w", encoding="utf-8", errors="replace") as f:
        f.write(rtf)
    print(f"[完成] 已生成 Word 可打开的 .doc：{dst}（{len(rtf.encode('utf-8'))} 字节）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
