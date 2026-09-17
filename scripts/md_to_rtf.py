# -*- coding: utf-8 -*-
"""
md_to_rtf — 零依赖 Markdown → Word 可读 .doc（RTF 内容）转换
================================================================
参考《本科毕业论文撰写规范》（附件4）排版：
  - 页面：A4，边距上下左右 3cm；
  - 正文：小四(12pt) 宋体，约 1.5 倍行距，首行缩进 2 字符；
  - 文档/一级标题：三号(16pt) 黑体加粗居中，段前段后 1 行；
  - 二级标题（大章）：三号黑体加粗居中，另起一页；
  - 参考文献标题：四号黑体加粗居中，另起一页；
  - 三级标题：四号黑体加粗顶格；四级标题：小四黑体加粗顶格；
  - 表格：三线表（顶线粗、表头下细线、底线粗，无竖线）；
  - 代码：Courier New；引用：缩进灰体。
行内支持 `**加粗**`、`代码`、`[[序号]]` 上标引用（最后统一替换为上标）。
用法：python scripts/md_to_rtf.py <输入.md> <输出.doc>
"""
from __future__ import annotations

import os
import re
import sys
from typing import List


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
    """行内格式化：把 [[n]] 替成 ASCII 占位符，**加粗** 与 `代码` 保留。"""
    # 清理中文字符之间无意义的空格（软换行合并产生的半角空格等）
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    # 先保护上标占位符（纯 ASCII，不会被 escape 破坏）
    text = re.sub(r"\[\[([^\[\]]+)\]\]", r"@@S\1@@", text)
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


def make_para(text: str, style: str = "body") -> str:
    # 字号（half-point）：三号=32，四号=28，小四=24，五号=21
    if style == "h1":
        return (f"{{\\pard\\qc\\f3\\fs32\\sb240\\sa240\\b "
                f"{escape(text)}\\b0\\par}}")
    if style == "h2":
        return (f"{{\\pard\\page\\qc\\f3\\fs32\\sb240\\sa240\\b "
                f"{escape(text)}\\b0\\par}}")
    if style == "h_ref":
        return (f"{{\\pard\\page\\qc\\f3\\fs28\\sb240\\sa240\\b "
                f"{escape(text)}\\b0\\par}}")
    if style == "h3":
        return (f"{{\\pard\\ql\\f3\\fs28\\sb240\\sa240\\b "
                f"{escape(text)}\\b0\\par}}")
    if style == "h4":
        return (f"{{\\pard\\ql\\f3\\fs24\\sb120\\sa120\\b "
                f"{escape(text)}\\b0\\par}}")
    if style == "ref":
        return (f"{{\\pard\\ql\\fi-480\\li480\\f0\\fs21\\sl300\\slmult1 "
                f"{inline(text)}\\par}}")
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
    return (f"{{\\pard\\ql\\fi480\\f0\\fs24\\sl360\\slmult1 "
            f"{inline(text)}\\par}}")


def make_table(rows: List[List[str]]) -> str:
    """三线表：表头上下线（顶粗底细），末行底线粗，无竖线。"""
    if not rows:
        return ""
    n_cols = max(len(r) for r in rows)
    total = 9360
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
            brdr = ""
            if is_head:
                brdr = "\\clbrdrt\\brdrs\\brdrw20\\clbrdrb\\brdrs\\brdrw5"
            elif is_last:
                brdr = "\\clbrdrb\\brdrs\\brdrw20"
            cell_rtf.append(
                f"{brdr}\\cellx{cellx[ci]} \\intbl {make_para_cell(c, style)} \\cell")
        out.append(f"\\trowd\\trgaph108\\trleft0 " + "".join(cell_rtf) + "\\row")
    return "".join(out)


def make_para_cell(text: str, style: str) -> str:
    if style == "table_h":
        return f"\\pard\\intbl\\b {inline(text)}\\b0 "
    return f"\\pard\\intbl {inline(text)} "


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
            title = m.group(2).strip()
            if len(m.group(1)) == 2 and title == "参考文献":
                out.append(make_para(title, style="h_ref"))
            else:
                out.append(make_para(title, style="h" + str(len(m.group(1)))))
            i += 1
            continue

        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            out.append("{\\pard\\brdrb\\brdrs\\brdrw10\\brsp40\\par}")
            i += 1
            continue

        if stripped.startswith(">"):
            q_lines = []
            while i < n and lines[i].strip().startswith(">"):
                q_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(make_para(" ".join(q_lines), style="quote"))
            continue

        if re.match(r"^[-*]\s+", stripped):
            out.append(make_para(re.sub(r"^[-*]\s+", "", stripped), style="bullet"))
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        if re.match(r"^\[\d+\]\s+", stripped):
            out.append(make_para(stripped, style="ref"))
            i += 1
            continue

        # 合并连续普通行（同一段落内的软换行，不拆成多个 Word 段落）
        para_lines = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith("```") or nxt.startswith("|")
                    or re.match(r"^(#{1,4})\s+", nxt)
                    or re.fullmatch(r"-{3,}|\*{3,}|_{3,}", nxt)
                    or nxt.startswith(">")
                    or re.match(r"^[-*]\s+", nxt)
                    or re.match(r"^\[\d+\]\s+", nxt)):
                break
            para_lines.append(nxt)
            i += 1
        out.append(make_para(" ".join(para_lines), style="body"))
        continue

    body = make_cover() + "\n" + "\n".join(out)
    # 最后统一把上标占位符替换为 RTF 上标控制字
    body = re.sub(r"@@S([^@]+)@@", r"\\super [\1]\\nosupersub ", body)

    header = (
        "{\\rtf1\\ansi\\ansicpg936"
        "{\\fonttbl"
        "{\\f0\\fnil\\fcharset134 SimSun;}"
        "{\\f1\\fmodern\\fcharset0 Courier New;}"
        "{\\f2\\fswiss\\fcharset0 Times New Roman;}"
        "{\\f3\\fnil\\fcharset134 SimHei;}}"
        "{\\colortbl ;\\red0\\green0\\blue0;\\red80\\green80\\blue80;}"
        "\\paperw11906\\paperh16838"
        "\\margl1701\\margr1701\\margt1701\\margb1701"
        "\\deflang2052"
        "\\pard\\f0\\fs24\n"
    )
    footer = "\n}"
    rtf = header + body + footer
    # 兜底转义：封面等手写中文若未转义，统一转为 \uN（否则 Word 按本地代码页读到乱码）
    rtf = re.sub(r"[^\x00-\x7f]", lambda m: escape(m.group(0)), rtf)
    # 清理数字章节号前后的多余空格（连续 2+ 压缩为 1，保留正常中英间距）
    rtf = re.sub(r"(\s{2,})(?=\d+\.\d+)", " ", rtf)
    rtf = re.sub(r"(?<=\d+\.\d+)(\s{2,})", " ", rtf)
    return rtf


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
        base, ext = os.path.splitext(dst)
        final = base + "_new" + ext
        with open(final, "w", encoding="utf-8", errors="replace") as f:
            f.write(rtf)
        print(f"[警告] {dst} 被占用，已生成替代文件：{final}")
    size = len(rtf.encode("utf-8"))
    print(f"[完成] {final} 已生成（{size} 字节），采用《本科毕业论文撰写规范》排版")
    return 0




def make_cover() -> str:
    """生成封面（参考附件5版式）：编号/密级 + 大标题 + 课题信息 + 落款。

    占位信息（姓名/学号/日期）可在生成后于 Word 中直接填写。
    """
    C = []
    # 顶部编号/密级（小五宋体，左对齐）
    C.append("{\\pard\\ql\\f0\\fs21 "
             "编号：\\ul 　　　　　　　　\\ul0 "
             "密级：\\ul 　　　　　　　　\\ul0\\par}")
    C.append("\\par\\par\\par")
    # 大标题（一号黑体居中）
    C.append("{\\pard\\qc\\f3\\fs44\\b 实验报告\\b0\\par}")
    C.append("\\par\\par")
    # 课题名称（三号黑体居中）
    C.append("{\\pard\\qc\\f3\\fs32\\b "
             "面向作战规划智能体的可进化外部记忆系统\\b0\\par}")
    C.append("{\\pard\\qc\\f0\\fs24 设计、实现与验证\\par}")
    C.append("\\par\\par\\par\\par")
    # 信息栏（四号宋体居中）
    C.append("{\\pard\\qc\\f0\\fs28 "
             "课题名称：面向作战规划智能体的可进化外部记忆系统\\par}")
    C.append("\\par")
    C.append("{\\pard\\qc\\f0\\fs28 "
             "小组组员：\\ul 姓名一　　　　姓名二　　\\ul0\\par}")
    C.append("{\\pard\\qc\\f0\\fs28 "
             "学　　号：\\ul 　　　　　　　　　　　　　　\\ul0\\par}")
    C.append("{\\pard\\qc\\f0\\fs28 "
             "所属单位：国防科技大学\\par}")
    C.append("{\\pard\\qc\\f0\\fs28 "
             "指导教师：\\ul 　　　　　　　　　　　　　　\\ul0\\par}")
    C.append("\\par\\par\\par\\par")
    # 落款
    C.append("{\\pard\\qc\\f3\\fs28 国防科技大学\\par}")
    C.append("{\\pard\\qc\\f0\\fs24 二〇二五年　月　日\\par}")
    return "\\par\\par\n".join(C)

if __name__ == "__main__":
    sys.exit(main())
