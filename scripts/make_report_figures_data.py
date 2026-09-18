# -*- coding: utf-8 -*-
"""生成实验报告 图3–图6（数据图），风格与 fig1/fig3 一致。
输出：docs/figures/report_fig{3,4,5,6}_*.svg + .png
"""
import io, json, math, os, subprocess

FIG = "docs/figures"
FONT = "'Microsoft YaHei','PingFang SC','Noto Sans CJK SC',sans-serif"
INK, SUB, DIM = "#0B0B0B", "#52514E", "#898781"
BLUE, ORANGE, GREEN, PURPLE, YELLOW, GREY = "#2A78D6", "#EB6834", "#1BAF7A", "#4A3AA7", "#EDA100", "#DCDBD4"
FILL = {"blue":"#EAF2FD","orange":"#FDEEE7","green":"#E6F7F1","purple":"#EDEBF7","yellow":"#FDF3E1","grey":"#F9F9F7"}

def esc(t): return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def rect(x,y,w,h,fill,stroke="none",sw=0,rx=8,opacity=None):
    o = f' fill-opacity="{opacity}"' if opacity else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{o}/>'
def text(x,y,t,size=20,color=INK,weight=400,anchor="start"):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{esc(t)}</text>'
def path(d,stroke=SUB,sw=2,dash=None,marker=False):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mm = ' marker-end="url(#arw)"' if marker else ""
    return f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}"{dd}{mm}/>'
def header(title, subtitle, W):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="680" viewBox="0 0 {W} 680" font-family="{FONT}">',
            '<defs><marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#52514E"/></marker></defs>',
            text(90, 76, title, 36, INK, 600),
            text(90, 112, subtitle, 21, SUB, 400)]
def footer(note, W, H=680):
    return [text(90, H-26, note, 16, DIM, 400), "</svg>"]

def write(name, parts):
    svg = "\n".join(parts)
    io.open(f"{FIG}/{name}.svg","w",encoding="utf-8",newline="\n").write(svg)
    subprocess.run(["rsvg-convert","-w","1200","-h","680",f"{FIG}/{name}.svg","-o",f"{FIG}/{name}.png"],check=True)

# ---------------- 图3 测试集 8 类结构 ----------------
def fig3():
    W=1200; parts=header("测试集 8 类结构", "共 50 条用例；查询与答案刻意错开措辞，含 12 条负例与参数干扰项", W)
    data=[("A","属性精确",6,BLUE),("B","事实语义",6,GREEN),("C","经验转述",8,ORANGE),
          ("D","词法",4,YELLOW),("E","负例",12,"#898781"),("F","参数干扰",4,PURPLE),
          ("G","阶段决胜",4,BLUE),("H","跨场次",6,GREEN)]
    x0,y0,x1,y1=120,150,1140,560; ymax=14
    for v in (0,4,8,12):
        yy=y1-v/ymax*(y1-y0)
        parts.append(path(f"M{x0},{yy:.1f} L{x1},{yy:.1f}", "#E1E0D9",1))
        parts.append(text(x0-14,yy+6,v,16,DIM,400,"end"))
    n=len(data); slot=(x1-x0)/n; bw=66
    for i,(code,label,val,color) in enumerate(data):
        cx=x0+slot*(i+0.5); xl=cx-bw/2; yh=y1-val/ymax*(y1-y0)
        parts.append(rect(xl,yh,bw,y1-yh,color,rx=6))
        parts.append(text(cx,yh-10,val,20,INK,600,"middle"))
        parts.append(text(cx,y1+28,code,18,INK,600,"middle"))
        parts.append(text(cx,y1+50,label,14,DIM,400,"middle"))
    parts.append(path(f"M{x0},{y1} L{x1},{y1}", "#898781",1.5))
    parts+=footer("数据来源：eval/testset.py（A–H 八类，共 50 条）",W)
    write("report_fig3_testset_structure",parts)

# ---------------- 图4 G2 vs G3 分类别 hit@5 ----------------
def fig4():
    rep=json.load(open("code/课题3_长短期记忆/eval/results/ablation_report.json",encoding="utf-8"))
    g2=rep["groups"]["G2"]["by_category"]; g3=rep["groups"]["G3"]["by_category"]
    cats=[("A","属性精确"),("B","事实语义"),("C","经验转述"),("D","词法"),
          ("E","负例"),("F","参数干扰"),("G","阶段决胜")]
    random_base=rep["random_baseline"]["fact库(n=14)"]["hit@5_单gold"]
    W=1200; parts=header("G2 vs G3：分类别 hit@5", "双库贡献消融（固定 44 条检索用例）；Δhit@5=0.2955，配对置换 p=0.0001（n=44）", W)
    x0,y0,x1,y1=120,160,1140,560; ymax=1.1
    for v in (0,0.25,0.5,0.75,1.0):
        yy=y1-v/ymax*(y1-y0)
        parts.append(path(f"M{x0},{yy:.1f} L{x1},{yy:.1f}", "#E1E0D9",1))
        parts.append(text(x0-14,yy+6,f"{v:.2f}",16,DIM,400,"end"))
    n=len(cats); slot=(x1-x0)/n; bw=40
    for i,(code,label) in enumerate(cats):
        cx=x0+slot*(i+0.5)
        for j,(key,color,off) in enumerate([("G2",GREY,-44),("G3",BLUE,4)]):
            val=(g2 if key=="G2" else g3)[code]["hit@5"]
            yh=y1-val/ymax*(y1-y0)
            parts.append(rect(cx+off,yh,bw,y1-yh,color,rx=5))
            parts.append(text(cx+off+bw/2,yh-8,f"{val:.3f}".rstrip("0").rstrip("."),14,INK,600,"middle"))
        parts.append(text(cx,y1+30,code,18,INK,600,"middle"))
        parts.append(text(cx,y1+52,label,14,DIM,400,"middle"))
    yy=y1-random_base/ymax*(y1-y0)
    parts.append(path(f"M{x0},{yy:.1f} L{x1},{yy:.1f}", ORANGE,2,dash="8 5"))
    parts.append(text(x1-6,yy-8,f"随机基线 {random_base:.3f}",16,ORANGE,600,"end"))
    parts.append(rect(x0,y0-40,26,16,FILL["grey"],GREY,1.2,rx=4)); parts.append(text(x0+36,y0-26,"G2 仅事实库",16,SUB))
    parts.append(rect(x0+190,y0-40,26,16,FILL["blue"],BLUE,1.2,rx=4)); parts.append(text(x0+226,y0-26,"G3 双库全开",16,SUB))
    parts.append(path(f"M{x0},{y1} L{x1},{y1}","#898781",1.5))
    parts+=footer("数据来源：eval/results/ablation_report.json",W)
    write("report_fig4_ablation_category",parts)

# ---------------- 图5 min_score 噪声-召回 ----------------
def fig5():
    rep=json.load(open("code/课题3_长短期记忆/eval/results/ablation_report.json",encoding="utf-8"))
    e=rep["E_noise_study"]; keys=["min_score=0.05","min_score=0.1","min_score=0.16","min_score=0.25"]
    xs=[0.05,0.10,0.16,0.25]
    neg=[e[k]["负例返回率"] for k in keys]; pos=[e[k]["正例hit@5"] for k in keys]
    W=1100; parts=header("min_score：噪声与召回的取舍", "E 噪声研究：阈值 0.16 处负例返回率首次归零，正例 hit@5 仍保持 0.857", W)
    x0,y0,x1,y1=130,160,1040,560; ymax=1.0
    def X(v): return x0+(v-0.05)/(0.25-0.05)*(x1-x0)
    def Y(v): return y1-v/ymax*(y1-y0)
    for v in (0,0.25,0.5,0.75,1.0):
        parts.append(path(f"M{x0},{Y(v):.1f} L{x1},{Y(v):.1f}", "#E1E0D9",1))
        parts.append(text(x0-14,Y(v)+6,f"{v:.2f}",16,DIM,400,"end"))
    for v in xs:
        parts.append(path(f"M{X(v):.1f},{y0} L{X(v):.1f},{y1}", "#EFEFEF",1))
        parts.append(text(X(v),y1+30,f"{v:.2f}",16,DIM,400,"middle"))
    parts.append(text(x0+ (x1-x0)/2, y1+64,"min_score",18,SUB,600,"middle"))
    # 竖线 0.16
    parts.append(path(f"M{X(0.16):.1f},{y0} L{X(0.16):.1f},{y1}", ORANGE,2,dash="7 5"))
    parts.append(text(X(0.16)+8,y0+22,"默认阈值 0.16",16,ORANGE,600))
    for series,color,label in [(neg,"#C0392B","负例返回率"),(pos,BLUE,"正例 hit@5")]:
        d="M"+" L".join(f"{X(x):.1f},{Y(v):.1f}" for x,v in zip(xs,series))
        parts.append(path(d,color,2.6))
        for x,v in zip(xs,series):
            parts.append(f'<circle cx="{X(x):.1f}" cy="{Y(v):.1f}" r="5" fill="{color}"/>')
    parts.append(rect(x0,y0-42,26,16,FILL["orange"],"#C0392B",1.2,rx=4)); parts.append(text(x0+36,y0-28,"负例返回率",16,SUB))
    parts.append(rect(x0+180,y0-42,26,16,FILL["blue"],BLUE,1.2,rx=4)); parts.append(text(x0+216,y0-28,"正例 hit@5",16,SUB))
    parts+=footer("数据来源：eval/results/ablation_report.json · E_noise_study",W,H=680)
    write("report_fig5_min_score_curve",parts)

# ---------------- 图6 遗忘曲线 ----------------
def fig6():
    W=1100; parts=header("遗忘曲线 R = e^(−t/S)", "艾宾浩斯留存模型：S 越大衰减越慢；每次召回 S+1、t 重置；R<0.3 且 importance<2 时淘汰", W)
    x0,y0,x1,y1=130,160,1040,560
    def X(t): return x0+t/30*(x1-x0)
    def Y(r): return y1-r*(y1-y0)
    for v in (0,0.25,0.5,0.75,1.0):
        parts.append(path(f"M{x0},{Y(v):.1f} L{x1},{Y(v):.1f}", "#E1E0D9",1))
        parts.append(text(x0-14,Y(v)+6,f"{v:.2f}",16,DIM,400,"end"))
    for t in (0,10,20,30):
        parts.append(text(X(t),y1+30,str(t),16,DIM,400,"middle"))
        parts.append(path(f"M{X(t):.1f},{y0} L{X(t):.1f},{y1}", "#EFEFEF",1))
    parts.append(text((x0+x1)/2,y1+64,"距上次召回 / 天",18,SUB,600,"middle"))
    # R=0.3
    parts.append(path(f"M{x0},{Y(0.3):.1f} L{x1},{Y(0.3):.1f}", "#C0392B",2,dash="8 5"))
    parts.append(text(x1-6,Y(0.3)-10,"遗忘阈值 R=0.3",16,"#C0392B",600,"end"))
    for S,color in [(1,ORANGE),(3,BLUE),(7,GREEN)]:
        pts=[(t,math.exp(-t/S)) for t in range(0,31)]
        d="M"+" L".join(f"{X(t):.1f},{Y(r):.1f}" for t,r in pts)
        parts.append(path(d,color,2.8))
        parts.append(text(X(29)+6,Y(math.exp(-30/S))+5,f"S={S}",17,color,600))
    parts+=footer("R = e^(−t/S)；命中强化：S←S+1，t←0；保护线 importance≥2 不参与淘汰",W,H=680)
    write("report_fig6_forgetting_curve",parts)

if __name__ == "__main__":
    os.makedirs(FIG,exist_ok=True)
    fig3(); print("图3 完成")
    fig4(); print("图4 完成")
    fig5(); print("图5 完成")
    fig6(); print("图6 完成")
