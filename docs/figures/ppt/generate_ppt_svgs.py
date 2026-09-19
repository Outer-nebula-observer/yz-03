# -*- coding: utf-8 -*-
"""
生成 PPT 配图（SVG + PNG）
风格对齐 docs/figures/fig1_architecture.svg：
浅色分层带 + 白底子框、蓝/橙/绿/紫/黄配色、圆角、灰色箭头、字号层级。
输出：docs/figures/ppt/*.svg + *.png
"""
import os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BLACK = "#0B0B0B"; GREY = "#52514E"; LGREY = "#898781"
WHITE = "#FFFFFF"; BG = "#F9F9F7"; BORDER = "#DCDBD4"
BLUE = "#2A78D6"; BLUE_BG = "#EAF2FD"
ORANGE = "#EB6834"; ORANGE_BG = "#FDEEE7"
GREEN = "#1BAF7A"; GREEN_BG = "#E6F7F1"
PURPLE = "#4A3AA7"; PURPLE_BG = "#EDEBF7"
YELLOW = "#EDA100"; YELLOW_BG = "#FDF3E1"

def esc(t):
    return (t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))

def defs():
    return ('''<defs>
<marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#52514E"/></marker>
<marker id="arwb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#2A78D6"/></marker>
</defs>''')

def txt(x,y,s,size=20,color=GREY,weight=400,anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}px" font-weight="{weight}" fill="{color}" text-anchor="{anchor}" font-family="Microsoft YaHei, SimHei, sans-serif">{esc(s)}</text>'

def box(x,y,w,h,label="",sub="",stroke=BORDER,fill=WHITE,tsize=22,ssize=16,tcolor=BLACK):
    s=f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'
    cy = y+h/2 + (8 if sub else 0)
    if label:
        s += txt(x+w/2, cy if not sub else cy-12, label, tsize, tcolor, 600, "middle")
    if sub:
        s += txt(x+w/2, cy+18, sub, ssize, LGREY, 400, "middle")
    return s

def band(x,y,w,h,label="",fill=BG,stroke=BORDER,lsize=22):
    s=f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="2.0"/>'
    if label:
        s += txt(x+22, y+34, label, lsize, BLACK, 600)
    return s

def arrow(x1,y1,x2,y2,color="#52514E"):
    mk = "arw" if color=="#52514E" else "arwb"
    return f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="2.2" marker-end="url(#{mk})"/>'

def head(w,title,sub=""):
    s = txt(48, 70, title, 38, BLACK, 700)
    if sub:
        s += txt(48, 106, sub, 20, GREY, 400)
    return s

# ---------------- 各类版式 ----------------
def render_icon(title, sub, letter, color, bg, w=900, h=300):
    S = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">' + defs()
    S += f'<rect x="0" y="0" width="{w}" height="{h}" fill="{WHITE}"/>'
    S += f'<rect x="16" y="16" width="{w-32}" height="{h-32}" rx="18" fill="{bg}" stroke="{color}" stroke-width="3"/>'
    # 左侧大编号
    S += f'<rect x="32" y="32" width="{h-64}" height="{h-64}" rx="16" fill="{color}"/>'
    letter_size = 110 if len(letter) <= 2 else 76 if len(letter) == 3 else 60
    S += f'<rect x="32" y="32" width="{h-64}" height="{h-64}" rx="16" fill="{color}"/>'
    S += f'<text x="{32+(h-64)/2}" y="{h/2 + letter_size*0.24}" font-size="{letter_size}px" font-weight="700" fill="{WHITE}" text-anchor="middle" font-family="Microsoft YaHei, SimHei, sans-serif">{esc(letter)}</text>'

    # 右侧文字
    left_block_right = 32 + (h - 64)          # 左侧色块右边缘
    right_block_right = w - 32                 # 右侧剩余区域右边缘
    cx_text = (left_block_right + right_block_right) / 2
    if sub:
        # 有副标：标题在上、副标在下（RQ 图沿用）
        tx = h - 16
        S += f'<text x="{tx}" y="{h/2-14}" font-size="52px" font-weight="700" fill="{BLACK}" font-family="Microsoft YaHei, SimHei, sans-serif">{esc(title)}</text>'
        S += f'<text x="{tx}" y="{h/2+42}" font-size="30px" font-weight="400" fill="{GREY}" font-family="Microsoft YaHei, SimHei, sans-serif">{esc(sub)}</text>'
    else:
        # 无副标：只有大字标题，居中占据右侧色块中央
        S += f'<text x="{cx_text}" y="{h/2+24}" font-size="68px" font-weight="700" fill="{BLACK}" text-anchor="middle" font-family="Microsoft YaHei, SimHei, sans-serif">{esc(title)}</text>'
    S += '</svg>'
    return S


def render_cards(title, sub, items, cols=4, w=1000, h=560):
    S = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">' + defs()
    S += f'<rect x="0" y="0" width="{w}" height="{h}" fill="{WHITE}"/>' + head(w,title,sub)
    palette=[BLUE,ORANGE,GREEN,PURPLE,YELLOW,BLUE,ORANGE,GREEN]
    rows = (len(items)+cols-1)//cols
    cw = (w-96-(cols-1)*24)/cols; ch = (h-200-(rows-1)*24)/rows
    for i,it in enumerate(items):
        r,c = divmod(i,cols); x=48+c*(cw+24); y=150+r*(ch+24)
        col=palette[i%len(palette)]
        S += f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="12" fill="{WHITE}" stroke="{col}" stroke-width="2"/>'
        S += f'<rect x="{x}" y="{y}" width="{cw}" height="8" rx="4" fill="{col}"/>'
        S += txt(x+cw/2, y+ch/2-4, it, 22, BLACK, 600, "middle")
    S += '</svg>'
    return S

def render_layers(title, sub, layers, w=1000, h=560):
    S = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">' + defs()
    S += f'<rect x="0" y="0" width="{w}" height="{h}" fill="{WHITE}"/>' + head(w,title,sub)
    palette=[(BLUE,BLUE_BG),(ORANGE,ORANGE_BG),(GREEN,GREEN_BG),(PURPLE,PURPLE_BG),(YELLOW,YELLOW_BG)]
    y=150; bh=(h-190-(len(layers)-1)*16)/len(layers)
    for i,(name,detail) in enumerate(layers):
        col,bg=palette[i%len(palette)]
        S += band(48,y,w-96,bh,"",bg,col)
        S += txt(76, y+bh/2+8, name, 24, BLACK, 700)
        S += txt(300, y+bh/2+8, detail, 19, GREY, 400)
        y += bh+16
    S += '</svg>'
    return S

def render_flow(title, sub, items, w=1000, h=560, color=BLUE):
    S = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">' + defs()
    S += f'<rect x="0" y="0" width="{w}" height="{h}" fill="{WHITE}"/>' + head(w,title,sub)
    n=len(items); bw=(w-96-(n-1)*40)/n; y=210; bh=160
    for i,it in enumerate(items):
        x=48+i*(bw+40)
        S += box(x,y,bw,bh,it,"",color,WHITE,22)
        if i<n-1:
            S += arrow(x+bw+6,y+bh/2,x+bw+34,y+bh/2)
    S += '</svg>'
    return S

def render_bars(title, sub, items, w=1000, h=560):
    S = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">' + defs()
    S += f'<rect x="0" y="0" width="{w}" height="{h}" fill="{WHITE}"/>' + head(w,title,sub)
    base=470; maxh=280; n=len(items); bw=(w-140-(n-1)*60)/n
    palette=[BLUE,ORANGE,GREEN,PURPLE,YELLOW]
    for i,(lab,val) in enumerate(items):
        x=70+i*(bw+60); bh=maxh*val
        S += f'<rect x="{x}" y="{base-bh}" width="{bw}" height="{bh}" rx="8" fill="{palette[i%len(palette)]}"/>'
        S += txt(x+bw/2, base-bh-12, f"{val:.2f}", 22, BLACK, 700, "middle")
        S += txt(x+bw/2, base+30, lab, 18, GREY, 400, "middle")
    S += f'<path d="M50,{base} L{w-30},{base}" stroke="{LGREY}" stroke-width="2"/>'
    S += '</svg>'
    return S

def render_curve(title, sub, series, w=1000, h=560):
    S = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">' + defs()
    S += f'<rect x="0" y="0" width="{w}" height="{h}" fill="{WHITE}"/>' + head(w,title,sub)
    x0,y0,x1,y1=90,470,940,180
    S += f'<path d="M{x0},{y0} L{x0},{y1} M{x0},{y0} L{x1},{y0}" stroke="{LGREY}" stroke-width="2"/>'
    palette=[BLUE,ORANGE,GREEN]
    import math
    for si,(name,color) in enumerate(series):
        pts=[]
        for k in range(0,51):
            t=k/50.0; val=math.exp(-t*3.0)
            x=x0+(x1-x0)*t; y=y0-(y0-y1)*val
            pts.append(f"{x:.1f},{y:.1f}")
        S += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="3"/>'
        S += txt(x1-180, y1+30+si*28, name, 18, color, 600)
    S += '</svg>'
    return S

def render_cycle(title, sub, steps, w=900, h=1060):
    import math
    S = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">' + defs()
    S += f'<rect x="0" y="0" width="{w}" height="{h}" fill="{WHITE}"/>' + head(w,title,sub)
    cx,cy,r=450,630,295
    palette=[BLUE,ORANGE,GREEN,PURPLE,YELLOW,BLUE,ORANGE]
    palette_bg=[BLUE_BG,ORANGE_BG,GREEN_BG,PURPLE_BG,YELLOW_BG,BLUE_BG,ORANGE_BG]
    R=104   # 圆半径（放大）
    for i,st in enumerate(steps):
        ang=-math.pi/2+i*2*math.pi/len(steps)
        x=cx+r*math.cos(ang); y=cy+r*math.sin(ang)
        col=palette[i%len(palette)]; bg=palette_bg[i%len(palette_bg)]
        S += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{R}" fill="{bg}" stroke="{col}" stroke-width="5"/>'
        S += txt(x, y+14, st, 40, BLACK, 700, "middle")
    S += txt(cx, cy-18, "状态不跨场次", 40, BLACK, 700, "middle")
    S += txt(cx, cy+42, "同类错误反复出现", 26, GREY, 400, "middle")
    S += '</svg>'
    return S

# ---------------- 任务清单 ----------------
TASKS = [
 # 大图（右栏大图位 10.9x12.9cm）
 dict(f="ppt_session_cycle", kind="cycle", w=900,h=1060, title="场次制规划的困境", sub="七步闭环每场从零开始，经验不跨场传递",
      items=["建槽","查询","检索","装载","规划","反馈","复盘"]),
 dict(f="ppt_architecture", kind="layers", w=900,h=1060, title="系统总体架构", sub="四层解耦 · 可独立消融",
      items=[("编排层","控制器 / 管线 / 智戎适配"),("跨切面","边界三道门 · MDMP 阶段"),
             ("能力层","短期 · 长期 · 检索 · 进化"),("模型层","schema 数据对象 · 遗忘模型")]),
 dict(f="ppt_webui", kind="cards", w=900,h=1060, title="WebUI 可视化", sub="页签三栏 · 抽屉 · 遗忘曲线",
      items=["三栏页签","记忆抽屉","遗忘曲线","健康分布条","事件流","战役进度"]),
 dict(f="ppt_zhirong", kind="flow", w=900,h=1060, title="智戎事件驱动适配", sub="三挂接点 → P0 生命周期适配",
      items=["hook_plan","hook_feedback","hook_evolve","normalize_task"]),
 # 小图（失败模式 5 + RQ 5，3.2cm 宽）
 dict(f="ppt_p1", kind="icon", w=900,h=300, title="经验不积累", sub="", letter="P1", color=BLUE, bg=BLUE_BG),
 dict(f="ppt_p2", kind="icon", w=900,h=300, title="上下文超限", sub="", letter="P2", color=ORANGE, bg=ORANGE_BG),
 dict(f="ppt_p3", kind="icon", w=900,h=300, title="查询口径混杂", sub="", letter="P3", color=GREEN, bg=GREEN_BG),
 dict(f="ppt_p4", kind="icon", w=900,h=300, title="库噪声", sub="", letter="P4", color=PURPLE, bg=PURPLE_BG),
 dict(f="ppt_p5", kind="icon", w=900,h=300, title="目标检索弱", sub="", letter="P5", color=YELLOW, bg=YELLOW_BG),
 dict(f="ppt_rq1", kind="icon", w=900,h=300, title="双库贡献", sub="", letter="RQ1", color=BLUE, bg=BLUE_BG),
 dict(f="ppt_rq2", kind="icon", w=900,h=300, title="跨场次复用", sub="", letter="RQ2", color=ORANGE, bg=ORANGE_BG),
 dict(f="ppt_rq3", kind="icon", w=900,h=300, title="检索策略", sub="", letter="RQ3", color=GREEN, bg=GREEN_BG),
 dict(f="ppt_rq4", kind="icon", w=900,h=300, title="滤噪与遗忘", sub="", letter="RQ4", color=PURPLE, bg=PURPLE_BG),
 dict(f="ppt_rq5", kind="icon", w=900,h=300, title="真实模型", sub="", letter="RQ5", color=YELLOW, bg=YELLOW_BG),
 # 中图（无图位页面的备注建议图，1000x560）
 dict(f="ppt_four_principles", kind="cards", title="总体思路四原则", sub="外部系统 · 复盘晋升 · 建议执行分离 · 阶段感知",
      items=["外部系统","复盘晋升","建议-执行","阶段感知"]),
 dict(f="ppt_context_layers", kind="layers", title="上下文组织与工作记忆", sub="常驻关键区 + 滚动消息 + 递归摘要",
      items=[("约束/目标","永不压缩"),("装载记忆","检索正文进 prompt"),("滚动消息","超限后归档摘要")]),
 dict(f="ppt_dual_store", kind="cards", title="长期双库 + 三路读取", sub="事实精确 / 经验语义 / 属性绕过阈值",
      items=["事实库 SQLite","经验库 向量","vector","BM25","SQL 精确"]),
 dict(f="ppt_evolution_ops", kind="cards", title="进化四操作", sub="写入 · 合并 · 遗忘 · 抽象",
      items=["写入 θ 查重","合并相似项","遗忘 R=e^{-t/S}","抽象通用教训"]),
 dict(f="ppt_fifo_summary", kind="flow", title="短期记忆换页", sub="FIFO → 递归摘要 → 归档供复盘",
      items=["FIFO 队列","超阈值","递归摘要","归档"]),
 dict(f="ppt_hybrid_retrieval", kind="flow", title="三路混合检索", sub="归一化 → 加权融合 → 阶段亲和 → 命中强化",
      items=["vector","BM25","SQL","融合排序"]),
 dict(f="ppt_forgetting_curve", kind="curve", title="遗忘曲线 R=e^{-t/S}", sub="S 越大越平缓；命中 S+1 延寿",
      items=[]),
 dict(f="ppt_boundary_stages", kind="flow", title="边界门控与阶段感知", sub="复盘驱动 → 类别门 → 查重 θ；MDMP 阶段亲和",
      items=["复盘驱动","类别门","查重 θ","阶段亲和"]),
 dict(f="ppt_testset", kind="cards", title="测试集结构（50 条 8 类）", sub="A-H 类覆盖精确/语义/负例/干扰/阶段/跨场次",
      items=["A 属性 6","B 事实 6","C 转述 8","D 词法 4","E 负例 12","F 干扰 4","G 阶段 4","H 跨场次 6"]),
 dict(f="ppt_ablation", kind="bars", title="双库消融（hit@5）", sub="G2 仅事实库 vs G3 双库全开；随机基线 0.357",
      items=[("G2",0.341),("G3",0.636),("随机",0.357)]),
 dict(f="ppt_cross_session", kind="flow", title="跨场次复用", sub="第一场复盘写入 → 第二场查询召回",
      items=["场次1 复盘","写入经验库","场次2 查询","命中 0.833"]),
 dict(f="ppt_min_score", kind="curve", title="min_score 噪声-召回权衡", sub="0.16 首次归零；正例 hit@5=0.857",
      items=[]),
 dict(f="ppt_deepseek", kind="cards", title="DeepSeek 真实模型验证", sub="20/20 通过 · T6 引用率 1.00 · 约束 1.00",
      items=["抽取","抽象","摘要","进化","规划","引用"]),
 dict(f="ppt_roadmap", kind="flow", title="下一步路线", sub="真向量重跑 · 数据扩容 · 机制补全 · 智戎联调",
      items=["真向量重标定","H 类扩至20","知识锚定","智戎联调"]),
]

def render(task):
    kind = task["kind"]
    w = task.get("w", 1000)
    h = task.get("h", 560)
    if kind == "icon":
        return render_icon(task["title"], task["sub"], task["letter"], task["color"], task["bg"], w, h)
    if kind == "cards":
        return render_cards(task["title"], task["sub"], task["items"], w=w, h=h)
    if kind == "layers":
        return render_layers(task["title"], task["sub"], task["items"], w=w, h=h)
    if kind == "flow":
        return render_flow(task["title"], task["sub"], task["items"], w=w, h=h)
    if kind == "bars":
        return render_bars(task["title"], task["sub"], task["items"], w=w, h=h)
    if kind == "curve":
        return render_curve(task["title"], task["sub"], [("曲线",BLUE),("S+1",ORANGE)], w=w, h=h)
    if kind == "cycle":
        return render_cycle(task["title"], task["sub"], task["items"], w=w, h=h)
    raise ValueError(kind)

def main():
    for t in TASKS:
        svg = render(t)
        svg_path = os.path.join(HERE, t["f"] + ".svg")
        png_path = os.path.join(HERE, t["f"] + ".png")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg)
        subprocess.run(["rsvg-convert", "-z", "2", svg_path, "-o", png_path], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("OK", t["f"], "svg" if os.path.exists(svg_path) else "", "png" if os.path.exists(png_path) else "")

if __name__ == "__main__":
    main()