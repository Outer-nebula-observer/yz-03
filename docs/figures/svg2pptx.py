# -*- coding: utf-8 -*-
"""
通用 SVG -> PPTX 转换器（矢量重建，非位图描摹）

用法：
    python svg2pptx.py fig1_architecture.svg [fig2_campaign_trajectory.svg ...]

设计前提：源是 SVG 不是 PNG，所以每个元素的坐标/字号/颜色都是确定值，
直接翻译成 PowerPoint 原生对象，不做 OCR 或位图描摹。

  <rect>          -> 原生矩形（rx>0 时用圆角矩形，含圆角半径换算）
  <circle>        -> 原生椭圆
  <line>          -> 原生 Connector
  <path>（折线）  -> 原生 Freeform
  <text>          -> 一个独立文本框（位置/字号/颜色/对齐逐项搬运）
  marker-end      -> 原生箭头（a:tailEnd）

坐标换算：SVG 用户单位(px) -> EMU，1px = 9525 EMU（96dpi）
字号换算：px -> pt，×0.75
基准线换算：SVG 的文字 y 是基线，PowerPoint 文本框按顶边定位，
            故 top = y - ASCENT_EM × font-size（常数经 PowerPoint 渲染回测标定）

图层：按 SVG 文档顺序建 z 序 Background -> Shapes -> Text，
      对象名带层前缀 + 内容摘要，可在「选择窗格」里按前缀筛选。
      注：PPTX 没有 Photoshop 式的图层，等价物是 z 序 + 选择窗格；
      这里保持对象扁平（不进组合），换取每个对象都能直接点选编辑。
"""

import re
import sys
import xml.etree.ElementTree as ET

from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn

NS = "{http://www.w3.org/2000/svg}"
PX = 9525                 # 1 px @96dpi -> EMU
ASCENT_EM = 1.079         # Segoe UI hhea ascent（渲染回测确认）

LATIN_R = "Segoe UI"
LATIN_SB = "Segoe UI Semibold"
EA = "Microsoft YaHei"

INHERIT = ("fill", "stroke", "stroke-width", "font", "font-size", "font-weight",
           "text-anchor", "marker-end", "letter-spacing")


def E(v):
    return Emu(int(round(float(v) * PX)))


def pt(px):
    return Pt(float(px) * 0.75)


def hexcolor(v):
    v = (v or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        return v[1:].upper()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", v):
        return "".join(c * 2 for c in v[1:]).upper()
    return None


# ------------------------------------------------------------------ CSS

def parse_css(root):
    css = {}
    for st in root.iter(NS + "style"):
        for m in re.finditer(r"\.([\w-]+)\s*\{([^}]*)\}", st.text or ""):
            props = {}
            for decl in m.group(2).split(";"):
                if ":" in decl:
                    k, v = decl.split(":", 1)
                    props[k.strip()] = v.strip()
            css[m.group(1)] = props
    return css


def resolve(el, inherited, css):
    """属性优先级：元素自身 > class > 父级继承。"""
    props = dict(inherited)
    for cls in (el.get("class") or "").split():
        props.update(css.get(cls, {}))
    for k in INHERIT:
        if el.get(k) is not None:
            props[k] = el.get(k)
    return props


def font_of(props):
    """解析 font 简写 -> (size_px, weight)。"""
    size, weight = None, 400
    f = props.get("font", "")
    if f:
        m = re.search(r"(\d+(?:\.\d+)?)px", f)
        if m:
            size = float(m.group(1))
        m = re.match(r"\s*(\d{3})\s", f)
        if m:
            weight = int(m.group(1))
    if props.get("font-size"):
        m = re.search(r"(\d+(?:\.\d+)?)", props["font-size"])
        if m:
            size = float(m.group(1))
    if props.get("font-weight"):
        try:
            weight = int(props["font-weight"])
        except ValueError:
            pass
    return size, weight


def anchor_of(props):
    a = (props.get("text-anchor") or "start").strip()
    return {"middle": "middle", "end": "end"}.get(a, "start")


def stroke_px(props, default=1.0):
    v = props.get("stroke-width")
    if not v:
        return default
    m = re.search(r"(\d+(?:\.\d+)?)", v)
    return float(m.group(1)) if m else default


def parse_transform(t):
    """只处理 translate(x,y) rotate(a) 这种组合。"""
    dx = dy = rot = 0.0
    if not t:
        return dx, dy, rot
    m = re.search(r"translate\(\s*([-\d.]+)[ ,]+([-\d.]+)\s*\)", t)
    if m:
        dx, dy = float(m.group(1)), float(m.group(2))
    m = re.search(r"rotate\(\s*([-\d.]+)", t)
    if m:
        rot = float(m.group(1))
    return dx, dy, rot


# ------------------------------------------------------------------ 写入器

class Builder:
    def __init__(self, shapes):
        self.shapes = shapes
        self.arrows = 0

    def set_fonts(self, run, size_px, color, weight):
        f = run.font
        f.size = pt(size_px)
        f.bold = False
        f.color.rgb = RGBColor.from_string(color)
        f.name = LATIN_SB if weight >= 600 else LATIN_R
        rPr = run._r.get_or_add_rPr()
        for tag in ("a:ea", "a:cs"):
            for old in rPr.findall(qn(tag)):
                rPr.remove(old)
        ea = rPr.makeelement(qn("a:ea"), {"typeface": EA})
        latin = rPr.find(qn("a:latin"))
        if latin is not None:
            latin.addnext(ea)
        else:
            rPr.append(ea)

    def text(self, x, y, s, size_px, color, weight, anchor, dx, dy, rot, name):
        x += dx          # transform="translate(...)" 的位移必须叠加，
        y += dy          # 否则只带 transform 不带 x/y 的文字会落到画布原点
        line_h = size_px * 1.6
        box_w = max(240.0, len(s) * size_px * 1.05)
        if rot:
            left, top = x - box_w / 2.0, y - line_h / 2.0
        elif anchor == "middle":
            left, top = x - box_w / 2.0, y - ASCENT_EM * size_px
        elif anchor == "end":
            left, top = x - box_w, y - ASCENT_EM * size_px
        else:
            left, top = x, y - ASCENT_EM * size_px
        tb = self.shapes.add_textbox(E(left), E(top), E(box_w), E(line_h))
        tf = tb.text_frame
        tf.word_wrap = False
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.TOP
        p = tf.paragraphs[0]
        p.alignment = {"middle": PP_ALIGN.CENTER, "end": PP_ALIGN.RIGHT}.get(
            anchor if not rot else "middle", PP_ALIGN.LEFT)
        r = p.add_run()
        r.text = s
        self.set_fonts(r, size_px, color, weight)
        if rot:
            tb.rotation = rot
        tb.name = "Text / " + (s[:16] + ("…" if len(s) > 16 else ""))
        return tb

    def rect(self, x, y, w, h, rx, fill, line, lw, name):
        shp = MSO_SHAPE.ROUNDED_RECTANGLE if rx > 0 else MSO_SHAPE.RECTANGLE
        sp = self.shapes.add_shape(shp, E(x), E(y), E(w), E(h))
        if rx > 0:
            try:
                sp.adjustments[0] = max(0.0, min(0.5, rx / float(min(w, h))))
            except Exception:
                pass
        if fill:
            sp.fill.solid()
            sp.fill.fore_color.rgb = RGBColor.from_string(fill)
        else:
            sp.fill.background()
        if line:
            sp.line.color.rgb = RGBColor.from_string(line)
            sp.line.width = pt(lw)
        else:
            sp.line.fill.background()
        sp.shadow.inherit = False
        sp.text_frame.word_wrap = False
        sp.name = name
        return sp

    def _head(self, ln, color):
        for old in ln.findall(qn("a:tailEnd")):
            ln.remove(old)
        ln.append(ln.makeelement(qn("a:tailEnd"),
                                 {"type": "triangle", "w": "med", "len": "med"}))

    def line(self, x1, y1, x2, y2, color, lw, arrow, name):
        cn = self.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                       E(x1), E(y1), E(x2), E(y2))
        cn.line.color.rgb = RGBColor.from_string(color)
        cn.line.width = pt(lw)
        cn.shadow.inherit = False
        if arrow:
            self._head(cn.line._get_or_add_ln(), color)
        cn.name = name
        return cn

    def polyline(self, pts, color, lw, arrow, name, fill=None, close=False):
        if len(pts) == 2 and fill is None:
            return self.line(pts[0][0], pts[0][1], pts[1][0], pts[1][1],
                             color, lw, arrow, name)
        fb = self.shapes.build_freeform(E(pts[0][0]), E(pts[0][1]), scale=1.0)
        fb.add_line_segments([(E(x), E(y)) for x, y in pts[1:]], close=close)
        sp = fb.convert_to_shape()
        if fill:
            sp.fill.solid()
            sp.fill.fore_color.rgb = RGBColor.from_string(fill)
        else:
            sp.fill.background()
        if color:
            sp.line.color.rgb = RGBColor.from_string(color)
            sp.line.width = pt(lw)
        else:
            sp.line.fill.background()
        sp.shadow.inherit = False
        if arrow and color:
            self._head(sp.line._get_or_add_ln(), color)
        sp.name = name
        return sp

    def circle(self, cx, cy, r, fill, line, lw, name):
        sp = self.shapes.add_shape(MSO_SHAPE.OVAL,
                                   E(cx - r), E(cy - r), E(2 * r), E(2 * r))
        if fill:
            sp.fill.solid()
            sp.fill.fore_color.rgb = RGBColor.from_string(fill)
        else:
            sp.fill.background()
        if line:
            sp.line.color.rgb = RGBColor.from_string(line)
            sp.line.width = pt(lw)
        else:
            sp.line.fill.background()
        sp.shadow.inherit = False
        sp.name = name
        return sp


# ------------------------------------------------------------------ 主流程

PATH_RE = re.compile(r"([ML])\s*([-\d.]+)[ ,]+([-\d.]+)")
PATH_TOK = re.compile(r"([MLQZ])([^MLQZ]*)")
NUM_RE = re.compile(r"-?\d+\.?\d*")
Q_STEPS = 8          # Q 曲线折线逼近的段数（柱子圆角用，视觉上看不出差别）


def parse_path(d):
    """解析 M/L/Q/Z；返回 (点列, 是否闭合)。Q 按折线逼近，因为 PPTX 自由形状只吃直线段。"""
    pts, cur, closed = [], None, False
    for cmd, args in PATH_TOK.findall(d):
        n = [float(x) for x in NUM_RE.findall(args)]
        if cmd == "M" and len(n) >= 2:
            cur = (n[0], n[1])
            pts.append(cur)
        elif cmd == "L" and len(n) >= 2:
            cur = (n[0], n[1])
            pts.append(cur)
        elif cmd == "Q" and len(n) >= 4 and cur:
            x1, y1, x2, y2 = n[:4]
            for i in range(1, Q_STEPS + 1):
                t = i / float(Q_STEPS)
                u = 1.0 - t
                pts.append((u * u * cur[0] + 2 * u * t * x1 + t * t * x2,
                            u * u * cur[1] + 2 * u * t * y1 + t * t * y2))
            cur = (x2, y2)
        elif cmd == "Z":
            closed = True
    return pts, closed


def convert(svg_path, pptx_path):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    css = parse_css(root)

    W = float(root.get("width"))
    H = float(root.get("height"))

    prs = Presentation()
    prs.slide_width = E(W)
    prs.slide_height = E(H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    B = Builder(slide.shapes)

    counts = {"rect": 0, "line": 0, "path": 0, "circle": 0, "text": 0}

    def walk(el, inherited):
        props = resolve(el, inherited, css)
        tag = el.tag.replace(NS, "")
        dx, dy, rot = parse_transform(el.get("transform"))

        if tag == "rect":
            counts["rect"] += 1
            x = float(el.get("x", 0)) + dx
            y = float(el.get("y", 0)) + dy
            w, h = float(el.get("width", 0)), float(el.get("height", 0))
            rx = float(el.get("rx", 0) or 0)
            fill = hexcolor(props.get("fill"))
            line = hexcolor(props.get("stroke"))
            if w >= W and h >= H:
                name = "Background / 画布底色"
            else:
                name = "Shapes / rect %d" % counts["rect"]
            B.rect(x, y, w, h, rx, fill, line, stroke_px(props, 1.5), name)

        elif tag == "line":
            counts["line"] += 1
            B.line(float(el.get("x1")) + dx, float(el.get("y1")) + dy,
                   float(el.get("x2")) + dx, float(el.get("y2")) + dy,
                   hexcolor(props.get("stroke")) or "C3C2B7",
                   stroke_px(props, 1.0), bool(props.get("marker-end")),
                   "Shapes / 网格线 %d" % counts["line"])

        elif tag == "path":
            counts["path"] += 1
            raw, closed = parse_path(el.get("d", ""))
            pts = [(x + dx, y + dy) for x, y in raw]
            if len(pts) >= 2:
                fill = hexcolor(props.get("fill"))
                if fill and not closed:
                    # 有填充的开放路径（如柱子）当作实心块处理，不画描边
                    B.polyline(pts, None, 0, False,
                               "Shapes / 色块 %d" % counts["path"], fill=fill)
                elif fill:
                    B.polyline(pts, hexcolor(props.get("stroke")),
                               stroke_px(props, 1.0), False,
                               "Shapes / 色块 %d" % counts["path"],
                               fill=fill, close=True)
                else:
                    B.polyline(pts, hexcolor(props.get("stroke")) or "52514E",
                               stroke_px(props, 2.0), bool(props.get("marker-end")),
                               "Shapes / 箭头 %d" % counts["path"])

        elif tag == "circle":
            counts["circle"] += 1
            B.circle(float(el.get("cx")) + dx, float(el.get("cy")) + dy,
                     float(el.get("r")),
                     hexcolor(props.get("fill")),
                     hexcolor(props.get("stroke")),
                     stroke_px(props, 2.0),
                     "Shapes / 标记点 %d" % counts["circle"])

        elif tag == "text":
            counts["text"] += 1
            s = "".join(el.itertext())
            size, weight = font_of(props)
            if size is None:
                return
            B.text(float(el.get("x", 0)), float(el.get("y", 0)), s,
                   size, hexcolor(props.get("fill")) or "0B0B0B", weight,
                   anchor_of(props), dx, dy, rot, None)

        elif tag in ("g", "svg", "defs", "style", "marker"):
            if tag == "defs":
                return
            for child in el:
                walk(child, props)
            return

    # 顶层逐个子元素走（svg 本身作为继承根）
    root_props = resolve(root, {}, css)
    for child in root:
        if child.tag.replace(NS, "") in ("defs", "style", "metadata", "title", "desc"):
            continue
        walk(child, root_props)

    prs.save(pptx_path)
    total = sum(counts.values())
    print("%-32s -> %-32s  %d 个原生对象  %s"
          % (svg_path, pptx_path, total, counts))
    return counts


if __name__ == "__main__":
    args = sys.argv[1:] or ["fig1_architecture.svg",
                            "fig2_campaign_trajectory.svg"]
    for a in args:
        convert(a, a.rsplit(".", 1)[0] + ".pptx")
