# -*- coding: utf-8 -*-
"""生成实验报告 图7–图9（示意/终端/界面），风格与 fig1/fig3 一致。
输出：docs/figures/report_fig{7,8,9}_*.svg + .png
"""
import io, os, subprocess

FIG="docs/figures"
FONT="'Microsoft YaHei','PingFang SC','Noto Sans CJK SC',sans-serif"
INK,SUB,DIM="#0B0B0B","#52514E","#898781"
BLUE,ORANGE,GREEN,PURPLE,YELLOW,GREY="#2A78D6","#EB6834","#1BAF7A","#4A3AA7","#EDA100","#DCDBD4"
FB,FO,FG,FP,FY,FGrey="#EAF2FD","#FDEEE7","#E6F7F1","#EDEBF7","#FDF3E1","#F9F9F7"

def esc(t): return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def rect(x,y,w,h,fill,stroke="none",sw=0,rx=8,op=None):
    o=f' fill-opacity="{op}"' if op else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{o}/>'
def text(x,y,t,size=20,color=INK,weight=400,anchor="start"):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{esc(t)}</text>'
def path(d,stroke=SUB,sw=2,dash=None,marker=False):
    dd=f' stroke-dasharray="{dash}"' if dash else ""
    mm=' marker-end="url(#arw)"' if marker else ""
    return f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}"{dd}{mm}/>'
def write(name,W,H,parts):
    svg="\n".join(parts) + "\n</svg>"
    io.open(f"{FIG}/{name}.svg","w",encoding="utf-8",newline="\n").write(svg)
    subprocess.run(["rsvg-convert","-w",str(W),"-h",str(H),f"{FIG}/{name}.svg","-o",f"{FIG}/{name}.png"],check=True)
def header(title,sub,W,H):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
            '<defs><marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#52514E"/></marker></defs>',
            text(80,76,title,36,INK,600),text(80,112,sub,21,SUB,400)]

# ---------------- 图7 跨场次复用 ----------------
def fig7():
    W,H=1300,660; p=header("跨场次复用：第一场沉淀 → 第二场命中","H 类 6 条用例：先跑第一场复盘写入经验，再用第二场相关查询检索",W,H)
    cards=[(80,"第一场 P1","夜间夺占 2 号高地",["复盘进化：教训 / 经验写入长期库","来源标记 复盘:P1"],FO,ORANGE),
           (490,"长期经验库","向量语义召回 + SQLite",["跨场次唯一沉淀通道","按 session_id 记录来源"],FG,GREEN),
           (900,"第二场 P2","相关任务查询",["检索命中往场沉淀","命中结果带 ⏪ 往场徽标"],FB,BLUE)]
    for x,title,sub2,lines,fill,stroke in cards:
        p.append(rect(x,170,310,190,fill,stroke,2.2,12))
        p.append(text(x+24,208,title,23,INK,600)); p.append(text(x+24,238,sub2,18,SUB,600))
        for i,ln in enumerate(lines): p.append(text(x+24,274+i*28,ln,16,DIM))
    p.append(path("M390,265 L486,265",SUB,2.2,marker=True))
    p.append(path("M800,265 L896,265",SUB,2.2,marker=True))
    p.append(text(650,250,"写入",16,DIM,400,"middle")); p.append(text(650,286,"召回",16,DIM,400,"middle"))
    # 结果卡
    p.append(text(80,420,"实验结果",24,INK,600))
    bars=[("处理组 hit@5",0.833,GREEN),("对照组 hit@5",0.0,GREY),("负控 false cross recall",0.0,GREY)]
    base=600; x=120
    for label,val,color in bars:
        h=max(val*180,3)
        p.append(rect(x,base-h,120,h,color,rx=6))
        p.append(text(x+60,base-h-12,f"{val:.3f}",18,INK,600,"middle"))
        p.append(text(x+60,base+30,label,16,SUB,400,"middle"))
        x+=260
    p.append(path(f"M100,{base} L920,{base}","#898781",1.5))
    p.append(rect(960,430,300,170,FG,GREEN,2.0,12))
    p.append(text(984,466,"结论",20,GREEN,600))
    p.append(text(984,502,"命中 5/6，对照组不可达",16,SUB))
    p.append(text(984,532,"负控为 0：无跨主题假阳性",16,SUB))
    p.append(text(984,562,"p=0.059（方向性证据）",16,ORANGE,600))
    p.append(text(80,H-24,"数据来源：eval/results/ablation_report.json · G4",16,DIM))
    write("report_fig7_cross_session",W,H,p)

# ---------------- 图8 DeepSeek 规划输出引用记忆 ----------------
def fig8():
    W,H=1240,800; p=header("DeepSeek 规划输出引用装载记忆","T6 任务层验证：宽松引用率 1.00；高亮句分别对应地形事实与历史教训",W,H)
    # 终端窗口
    p.append(rect(80,150,1080,450,"#1E1E24","#3A3A44",2,14))
    p.append(rect(80,150,1080,48,"#2A2A32",rx=14)); p.append(rect(80,185,1080,13,"#2A2A32"))
    for cx,col in [(112,"#FF5F56"),(136,"#FFBD2E"),(160,"#27C93F")]:
        p.append(f'<circle cx="{cx}" cy="174" r="7" fill="{col}"/>')
    p.append(text(190,180,"DeepSeek deepseek-flash · T6 规划输出",16,"#C9C9CE",600))
    lines=[
        ("夜间夺占 2 号高地规划方案（要点式）",False),
        ("一、任务判断与先期查询",False),
        ("已知地形：海拔 320 米；北坡缓、南坡陡；仅东侧可装甲通行。",True),
        ("硬约束：禁止越境，边界线为“红线”。",False),
        ("先遣侦察队：侦察排 + 工兵 + 无人机，前出查隘口、伏击区、雷场。",True),
        ("T0—T+20min：情报确认，边界标定，先遣侦察出发；灯火管制，静默通信。",False),
    ]
    y=240
    for ln,hl in lines:
        if hl:
            p.append(rect(108,y-24,1010,34,"#F2C94C","none",0,6,op=0.18))
        p.append(text(118,y,ln,17,("#FFE58F" if hl else "#E8E8E8"),600 if hl else 400))
        y+=36
    # 指标卡
    cards=[(80,"宽松引用率","1.00",GREEN),(440,"严格引用率","0.50",BLUE),(800,"检索命中","2 条",PURPLE)]
    for x,label,val,color in cards:
        p.append(rect(x,630,320,100,"#FFFFFF",color,2.0,12))
        p.append(text(x+22,666,label,17,SUB,600)); p.append(text(x+22,710,val,30,color,700))
    p.append(text(80,H-24,"数据来源：eval/results/llm_verification.json · t6_pipeline",16,DIM))
    write("report_fig8_deepseek_output",W,H,p)

# ---------------- 图9 WebUI 界面示意 ----------------
def fig9():
    W,H=1320,760; p=header("WebUI：事件流 · 记忆详情抽屉 · 库健康度","界面示意（布局与真实 WebUI 一致）：左侧事件流可展开，右侧抽屉含总览/单条历史/遗忘日志",W,H)
    # 浏览器
    p.append(rect(60,150,1200,560,"#FFFFFF","#DCDBD4",2,14))
    p.append(rect(60,150,1200,46,"#F2F3F5",rx=14)); p.append(rect(60,186,1200,10,"#F2F3F5"))
    for cx,col in [(92,"#FF5F56"),(116,"#FFBD2E"),(140,"#27C93F")]:
        p.append(f'<circle cx="{cx}" cy="173" r="7" fill="{col}"/>')
    p.append(rect(200,162,520,24,"#FFFFFF","#DCDBD4",1.2,6)); p.append(text(214,180,"127.0.0.1:8765",14,DIM))
    # 左：事件流
    p.append(rect(80,216,600,470,FGrey,"#E1E0D9",1.5,10))
    p.append(text(100,252,"运行事件流",22,INK,600))
    events=[("① 场次 P1 开启","夜间夺占 2 号高地",BLUE),
            ("③④ 检索装载完成","命中 4 条（事实 2 / 经验 2）",GREEN),
            ("⑤ 规划输出","装载记忆已注入上下文",PURPLE),
            ("⑦ 复盘进化","write=2 · abstract=1",ORANGE),
            ("⏩ 模拟时间推进 15 天","遗忘 11 条（低价值未召回）",YELLOW)]
    y=278
    for tag,detail,color in events:
        p.append(rect(100,y,560,66,"#FFFFFF","#E1E0D9",1.2,8))
        p.append(rect(100,y,6,66,color,rx=3))
        p.append(text(120,y+26,tag,16,INK,600)); p.append(text(120,y+50,detail,14,DIM))
        y+=72
    # 右：抽屉
    p.append(rect(700,216,540,470,"#FFFFFF",BLUE,2.2,10))
    p.append(text(722,252,"记忆详情",22,INK,600))
    for i,(tab,active) in enumerate([("总览",True),("单条历史",False),("遗忘日志",False)]):
        x=722+i*130
        p.append(text(x,286,tab,17,BLUE if active else SUB,600 if active else 400))
        if active: p.append(rect(x,294,60,3,BLUE,rx=2))
    p.append(rect(700,300,540,1,"#E1E0D9"))
    p.append(text(722,336,"记忆 42 · 受保护 12 · 已低于遗忘线 3 · 已遗忘 7",16,SUB,600))
    # 健康度三色条
    bar_x,bar_y,bar_w=722,356,500
    p.append(rect(bar_x,bar_y,bar_w,16,"#E9EDF2",rx=8))
    w1=int(bar_w*27/42); w2=int(bar_w*12/42); w3=bar_w-w1-w2
    p.append(rect(bar_x,bar_y,w1,16,GREEN,rx=8)); p.append(rect(bar_x+w1,bar_y,w2,16,ORANGE))
    p.append(rect(bar_x+w1+w2,bar_y,w3,16,"#C0392B",rx=8))
    p.append(text(722,398,"健康 27 · 受保护 12 · 已低于遗忘线 3",14,DIM))
    # 记忆卡片
    mems=[("experience-seed-204b9","教训：夜间突袭必须前置电子压制。","S=3.0 · 召回 2 · 留存 92%",GREEN),
          ("fact-320m-east","2 号高地海拔 320 米，仅东侧可装甲通行。","S=1.0 · 召回 1 · 留存 61%",BLUE)]
    y=424
    for mid,content,meta,color in mems:
        p.append(rect(720,y,500,80,"#FBFCFD","#E1E0D9",1.2,8))
        p.append(text(736,y+26,mid,14,color,600)); p.append(text(736,y+50,content,15,INK))
        p.append(text(736,y+70,meta,13,DIM)); y+=92
    p.append(text(80,H-24,"界面示意（基于真实 WebUI 布局）：抽屉支持总览/单条历史/遗忘日志；健康度条显示 健康/受保护/低于遗忘线。",16,DIM))
    write("report_fig9_webui_ui",W,H,p)

if __name__=="__main__":
    fig7(); print("图7 完成")
    fig8(); print("图8 完成")
    fig9(); print("图9 完成")
