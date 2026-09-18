# -*- coding: utf-8 -*-
"""
生成《最终汇报成果.pptx》——gorden-ppt-skill 模式 C 原创设计
============================================================
简约专业学术科技风：白底 + 深蓝主色 + 灰阶，16:9。
同时导出《PPT内容设计.md》供人工核对与配图。

运行：python 汇报PPT/generate_final_ppt.py
"""
from __future__ import annotations

import os
from pptx import Presentation
from pptx.util import Cm, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PPTX = os.path.join(OUT_DIR, "最终汇报成果.pptx")
MD = os.path.join(OUT_DIR, "PPT内容设计.md")

PRIMARY = RGBColor(0x1F, 0x3A, 0x68)   # 深蓝
ACCENT = RGBColor(0x2F, 0x6E, 0xBA)    # 亮蓝
GREY = RGBColor(0x55, 0x5F, 0x6E)
LIGHT = RGBColor(0xF2, 0xF4, 0xF8)
DARK = RGBColor(0x22, 0x28, 0x30)
LINE = RGBColor(0xC8, 0xD0, 0xDC)

SW, SH = Cm(33.87), Cm(19.05)

PAGES = [
 # ---------------- 封面 ----------------
 {"type":"cover","title":"面向作战规划智能体的可进化外部记忆系统","subtitle":"国防科技大学 · 课题3 · 长短期记忆系统\n小组：姓名一 / 姓名二\n2025年7月","note":"【配图】可放校徽（可选）。\n【讲稿】开场1分钟：课题目标、单位、小组分工。","image":""},
 # ---------------- 目录 ----------------
 {"type":"agenda","title":"目录 CONTENTS","items":["01 问题与思路","02 相关工作与启发","03 系统设计与实现","04 实验设计与验证","05 智戎接入与总结展望"],"note":"【配图】无。\n【讲稿】按五部分走，重点在系统设计与实验验证。","image":""},
 # ---------------- 01 问题与思路 ----------------
 {"type":"section","num":"01","title":"问题与思路","subtitle":"PROBLEM & APPROACH","image":"","note":"【配图】可放 docs/figures/fig2_campaign_trajectory.png 作背景。\n【讲稿】先讲‘为什么需要外部记忆’。","image2":""},
 {"type":"content","tag":"01 · 问题与思路","title":"课题背景","items":["作战规划智能体以场次接任务：目标→查询→检索→规划→推演→复盘→下一场","模型与上下文都不保留跨场次状态，同类错误会反复出现","长上下文只解决容量，RAG 只解决知识供给，均不解决经验沉淀/更新/淘汰","目标：在模型之外构建可读写、可演化、可审计的外部记忆系统"],"note":"【配图】无。\n【讲稿】用‘同一夜间进攻任务，第一场隘口遇伏，第二场大概率再吃亏’举例。","image":""},
 {"type":"content","tag":"01 · 问题与思路","title":"五个失败模式","items":["P1 经验不积累：场次间无状态传递，同样错误重复出现","P2 上下文超限：粗暴截断可能丢失硬约束，规划违反约束","P3 查询口径混杂：参数精确与经验语义同路，互相干扰","P4 库噪声：复盘无差别入库，长期库变成日志不可审计","P5 目标检索弱：直接用任务目标文本查询，语义信息量不足"],"note":"【配图】无。\n【讲稿】P1-P4 来自初始问题拆解，P5 来自导师反馈。","image":""},
 {"type":"content","tag":"01 · 问题与思路","title":"五个研究问题 RQ1-RQ5","items":["RQ1 双库贡献：事实/经验分库是否带来可测召回增益","RQ2 跨场次复用：第一场复盘能否被第二场召回","RQ3 检索策略：三路融合相对单路是否有增益","RQ4 滤噪与遗忘：阈值能否滤噪、遗忘是否不误删","RQ5 真实模型：DeepSeek 是否实际引用装载记忆"],"note":"【配图】无。\n【讲稿】实验章节会逐个回答。","image":""},
 {"type":"content","tag":"01 · 问题与思路","title":"总体思路","items":["外部系统：把记忆组织成可演化结构，不止检索增强","复盘晋升：短期→长期唯一写通道，三道门控","建议-执行分离：LLM 提候选，确定性代码执行写/合/忘/抽","阶段感知：MDMP 七阶段生成查询，对口记忆加分"],"note":"【配图】无。\n【讲稿】一句话：把跨场次知识做成可回放、可审计的外部系统。","image":""},
 # ---------------- 02 相关工作与启发 ----------------
 {"type":"section","num":"02","title":"相关工作与启发","subtitle":"RELATED WORK & INSPIRATION","image":"","note":"【配图】可放 docs/figures/fig1_architecture.png 作背景。\n【讲稿】说明借鉴什么、不采用什么。","image2":""},
 {"type":"content","tag":"02 · 相关工作与启发","title":"上下文组织与工作记忆","items":["综述框架（Zhang 2024）：记忆的‘形式-操作-应用’分层","MemGPT：主上下文+外部存档，本文改为确定性阈值换页","SCM：控制器显式决定读/写/归档，本文收敛为复盘晋升","LLMLingua/LongLLMLingua/ICAE：位置偏置与‘只压历史不压约束’"],"note":"【配图】无。\n【讲稿】每条都说明：借鉴什么、为什么不完整照搬。","image":""},
 {"type":"content","tag":"02 · 相关工作与启发","title":"长期存储与检索","items":["ChatDB：数据库即符号记忆 → 采用属性精确过滤","ExpeL：经验库+向量召回 → 补充重要性加权与持久化","Reflexion：语言反思 → 采用语言形式经验","MemoryBank：艾宾浩斯遗忘 → 加入 importance≥2 保护线","Zep：时间戳/溯源 → 采用溯源字段，不采用图存储","MIRIX / TiM：多路策略与显式检索计划 → 压缩为三路融合"],"note":"【配图】无。\n【讲稿】这一段说明检索与存储不是凭空设计。","image":""},
 {"type":"content","tag":"02 · 相关工作与启发","title":"记忆进化与设计依据","items":["PREMem：预存储推理/θ查重 → 采用相似度去重","StructMem：跨事件整合 → 演化为‘抽象’操作","MemSkill：INSERT/UPDATE/DELETE/SKIP → 采用操作类型化","Mem-α：建议-执行分离 → 本文核心架构","小结：组合层面+领域化（保护线/精确绕过阈值/阶段供给）"],"note":"【配图】无。\n【讲稿】强调：机制都有原型，差异在组合与军事场景限定。","image":""},
 # ---------------- 03 系统设计与实现 ----------------
 {"type":"section","num":"03","title":"系统设计与实现","subtitle":"DESIGN & IMPLEMENTATION","image":"","note":"【配图】可放 docs/figures/fig1_architecture.png 作背景。\n【讲稿】进入核心章节。","image2":""},
 {"type":"content","tag":"03 · 系统设计与实现","title":"总体架构","items":["四层：模型层/能力层/跨切面/编排层","能力层四模块互不依赖：短期、长期、检索、进化","两层之间唯一写通道：复盘晋升 + 三道边界门","可独立消融：依赖注入实现 G0-G6","","配图占位：系统架构图（建议 docs/figures/fig1_architecture.png）"],"note":"【配图】本页右侧预留图位：放 docs/figures/fig1_architecture.png（系统架构图）。\n【讲稿】讲清分层与‘可独立消融’。","image":"架构图（docs/figures/fig1_architecture.png）"},
 {"type":"code","tag":"03 · 系统设计与实现","title":"短期工作记忆","items":["槽位保存目标/约束/查询/消息；约束永不压缩","FIFO 超阈值触发压缩，被驱逐消息进入归档","伪代码如下（memsys/short_term/working_memory.py）："],"code":"def render(slot):\n    parts = [阶段, 目标, 约束]          # 头部：不可压缩\n    if slot.loaded_briefs:\n        parts.append('【装载记忆】' + 逐条brief)\n    parts.append(查询列表)               # 审计\n    parts.append(最新消息[-20:])\n    return '\\n'.join(parts)\n\ndef flush(slot, llm):\n    evicted = slot.fifo.pop(前半)\n    slot.summary = llm.summarize(old + evicted)\n    slot.archived.append(evicted)        # 归档不丢","note":"【配图】无。\n【讲稿】讲清‘首尾关键、约束不压缩、归档可复盘’。","image":""},
 {"type":"code","tag":"03 · 系统设计与实现","title":"长期双库","items":["事实库：SQLite + 属性精确；经验库：向量语义召回","attrs 精确命中绕过 min_score（构造性相关）","接口示例："],"code":"# 事实精确：属性过滤\nhits_exact = factual.search_attrs({'装备': 'T-90'})\n# 经验语义：向量召回\nhits_sem = experiential.search('夜战侦察教训')\n# 融合时：attrs 命中即相关，不参与相似度阈值","note":"【配图】无。\n【讲稿】用 T-90 vs M1A2 的例子说明为什么必须分库。","image":""},
 {"type":"code","tag":"03 · 系统设计与实现","title":"混合检索：三路融合 + 单路","items":["vector/BM25/SQL 三路；hybrid 加权累加，single 便于消融","归一化：向量余弦、BM25 查询自匹配上界、SQL 恒 1","公式：s_hybrid = Σ w_r·n_r(id)"],"code":"def retrieve(q, mode='hybrid', top_k=5):\n    pool = [route(q, q.route)]\n    if mode == 'hybrid':\n        pool += [route(q, alt) for alt in routes\n                 if alt != q.route]\n    pool = [normalize(r) for r in pool]\n    fused = aggregate_by_id(pool, weights)  # 多路累加\n    if q.stage: fused = add_stage_bonus(fused, q.stage)\n    ranked = [x for x in sorted(fused, reverse=True)\n              if x.score >= min_score][:top_k]\n    for r in ranked: r.entry.mark_recalled()\n    return ranked","note":"【配图】无。\n【讲稿】重点讲归一化与‘命中强化只做一次’。","image":""},
 {"type":"code","tag":"03 · 系统设计与实现","title":"记忆进化：写/合/忘/抽","items":["建议-执行分离：LLM 提候选，确定性代码执行","遗忘：R=e^{-t/S}，命中 S+1；importance≥2 保护","抽象：≥2 条新经验 → 一条通用教训"],"code":"def evolve_from_review(review, session_id):\n    ops = llm.extract_memory_ops(review)\n    for op in ops:\n        if not boundary.promote(op.content): continue\n        if write(op) is None: skipped += 1\n    merge_new_entries()\n    forget()\n    if len(new_experiences) >= 2: abstract()\n\n# 遗忘核心\nR = math.exp(-t / max(S, 1e-6))\n# 命中强化：S += 1, t 重置","note":"【配图】无。\n【讲稿】讲清‘为什么建议与执行分离’——可审计。","image":""},
 {"type":"content","tag":"03 · 系统设计与实现","title":"边界门控与阶段感知","items":["复盘晋升经三道门：复盘驱动、类别判定、语义查重","每次判定写入审计日志（boundary）","查询按 MDMP 七阶段生成，阶段匹配记忆加亲和分","复盘教训归因到阶段，供同阶段检索优先召回"],"note":"【配图】无。\n【讲稿】澄清‘什么能进长期库、什么时候检索什么’。","image":""},
 {"type":"content","tag":"03 · 系统设计与实现","title":"WebUI 可视化","items":["后台 /api 与前端三栏；左右栏页签化，避免过长","记忆详情抽屉：总览/单条历史/遗忘日志","遗忘曲线：R=e^{-t/S} 与‘立即召回 S+1’对比","战役进度条、库健康度分布条、事件流点击展开","配图占位：WebUI 截图（抽屉/遗忘曲线/事件流）"],"note":"【配图】本页右侧预留图位：放 WebUI 截图（运行 python webui/server.py 后截取记忆详情抽屉、遗忘曲线、事件流）。\n【讲稿】展示可视化如何帮助理解系统。","image":"WebUI 截图（记忆详情抽屉/遗忘曲线/事件流）"},
 # ---------------- 04 实验设计与验证 ----------------
 {"type":"section","num":"04","title":"实验设计与验证","subtitle":"EXPERIMENTS","image":"","note":"【配图】可放消融图（docs/17 配图脚本生成）作背景。\n【讲稿】进入数据章节，先声明词袋环境。","image2":""},
 {"type":"content","tag":"04 · 实验设计与验证","title":"数据集与评估协议","items":["自建 50 条 8 类测试集（A-H），避免关键词共现","固定用例集，依赖注入开关能力（G0-G6）","检索指标：hit@3/5、MRR、NDCG；任务层：引用/约束/噪声","统计：随机基线、bootstrap CI、配对置换检验"],"note":"【配图】无。\n【讲稿】强调‘对照是开关能力而不是删用例’。","image":""},
 {"type":"content","tag":"04 · 实验设计与验证","title":"双库贡献（RQ1）","items":["G2 仅事实库 hit@5=0.341；G3 双库全开 0.636","Δ=0.295，配对置换 p=0.0001","增益全部来自经验类（C/D/G），事实类不降","随机基线 0.357，G3 显著高于随机","残余失分在转述类（C=0.625）：词袋局限"],"note":"【配图】建议放消融柱状图（docs/17 配图脚本：G2 vs G3 分类别 hit@5）。\n【讲稿】这是最硬的一条证据。","image":"消融柱状图（docs/17 §8.2 脚本生成）"},
 {"type":"content","tag":"04 · 实验设计与验证","title":"跨场次与检索策略（RQ2/RQ3）","items":["跨场次：处理组 0.833 vs 对照 0，负控 0","p=0.059，样本有限 → 方向性证据","检索：hybrid 0.857 vs vector 0.929（词袋）","但干扰压制 hybrid 1.0 > 单路 ≤0.875","结论：混合价值在排序，真向量再定召回"],"note":"【配图】可放跨场次 WebUI 截图（第二场命中带‘往场沉淀’）或表格。\n【讲稿】对负结果要诚实：词袋下混合召回无增益。","image":"跨场次复用示意（WebUI 截图/表格）"},
 {"type":"content","tag":"04 · 实验设计与验证","title":"滤噪、遗忘与真实模型（RQ4/RQ5）","items":["min_score=0.16：负例返回率 0%，正例 hit@5=0.857","遗忘：未保护删 10/10，保护 0，新写 0，误删 0","S×时间：命中强化 S+1 显著延长寿命","DeepSeek：20/20，T6 引用率 1.00、约束 1.00","限定：MockEmbedding 之上单次运行，示范性证据"],"note":"【配图】可放遗忘曲线（WebUI 截图）或 DeepSeek 输出截图。\n【讲稿】强调限定词，避免被当成最终结论。","image":"遗忘曲线（WebUI 截图）/ DeepSeek T6 输出截图"},
 # ---------------- 05 智戎接入与总结展望 ----------------
 {"type":"section","num":"05","title":"智戎接入与总结展望","subtitle":"INTEGRATION & OUTLOOK","image":"","note":"【配图】可放 docs/figures/fig2_campaign_trajectory.png 作背景。\n【讲稿】从‘能不能用’讲到‘怎么接’。","image2":""},
 {"type":"content","tag":"05 · 智戎接入与总结展望","title":"智戎事件驱动适配（P0 落地）","items":["hook_evolve：不依赖‘场次结束’，可随时触发进化","结构化反馈：AFSIM 数值/事件 → 复盘文本","normalize_task：结构化任务 → goal/constraints/queries","domain_check：领域巡检 + min_score 建议","配图占位：智戎接入架构/事件流图"],"note":"【配图】本页右侧预留图位：放 docs/figures/fig2_campaign_trajectory.png 或智戎桥接架构示意图。\n【讲稿】强调 P1（无结束信号）已有适配方案。","image":"智戎接入/事件流图（可复用 docs/figures/fig2_campaign_trajectory.png）"},
 {"type":"content","tag":"05 · 智戎接入与总结展望","title":"总结与展望","items":["结论：分层与进化机制在词袋固定设置下有效（p=0.0001）","真实模型验证了检索-生成链路可用（引用率 1.00）","下一步：真向量重跑与重标定 min_score/θ","下一步：H 类扩至 20 条、知识锚定、冲突仲裁","下一步：智戎真实链路联调与领域巡检"],"note":"【配图】无。\n【讲稿】把‘方向性/示范性’讲清楚，再列行动项。","image":""},
 {"type":"thanks","title":"感谢聆听 · 欢迎交流","subtitle":"国防科技大学 · 课题3 · 长短期记忆系统","note":"【配图】可放校徽（可选）。\n【讲稿】感谢，进入提问。","image":""},
]

# ================================================================ 绘图
prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]
TOTAL = len(PAGES)

def _set_font(run, size, bold=False, color=DARK, mono=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Consolas" if mono else "Microsoft YaHei"

def add_text(slide, text, left, top, width, height, size=18, bold=False,
             color=DARK, align=PP_ALIGN.LEFT, mono=False):
    tb = slide.shapes.add_textbox(Cm(left), Cm(top), Cm(width), Cm(height))
    tf = tb.text_frame
    tf.word_wrap = True
    lines = str(text).split("\n")
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = ln
        _set_font(r, size, bold, color, mono)
    return tb

def add_rect(slide, left, top, width, height, fill=None, line=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Cm(left), Cm(top), Cm(width), Cm(height))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    shp.shadow.inherit = False
    return shp

def add_header(slide, tag, title):
    if tag:
        add_text(slide, tag, 1.8, 0.9, 12, 1.0, size=13, color=ACCENT, bold=True)
        add_rect(slide, 1.8, 1.6, 2.0, 0.12, fill=ACCENT)
    add_text(slide, title, 1.8, 1.8, 30, 1.8, size=30, bold=True, color=PRIMARY)

def add_footer(slide, idx):
    add_rect(slide, 0, 18.35, 33.87, 0.03, fill=LINE)
    add_text(slide, "国防科技大学 · 长短期记忆系统", 1.8, 18.5, 17, 0.5, size=10, color=GREY)
    add_text(slide, f"{idx} / {TOTAL}", 28.5, 18.5, 4.0, 0.5, size=10, color=GREY,
             align=PP_ALIGN.RIGHT)

def add_bullets(slide, items, left=2.2, top=4.2, width=29, height=11.5, size=17, gap=0.9):
    for i, item in enumerate(items):
        if not item:
            continue
        add_text(slide, "•", left, top + i * gap, 0.7, 1.0, size=size, color=ACCENT, bold=True)
        add_text(slide, item, left + 0.9, top + i * gap, width - 0.9, 1.3, size=size, color=DARK)

def add_code(slide, code, left=2.2, top=7.2, width=29, height=9.0):
    add_rect(slide, left, top, width, height, fill=LIGHT, line=LINE)
    add_text(slide, code, left + 0.6, top + 0.4, width - 1.2, height - 0.8,
             size=13, color=PRIMARY, mono=True)

def add_image_box(slide, left, top, width, height):
    add_rect(slide, left, top, width, height, fill=LIGHT, line=ACCENT)
    # 留空，不写字；由备注说明配图

def set_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text

def build():
    for idx, p in enumerate(PAGES, 1):
        slide = prs.slides.add_slide(BLANK)
        t = p["type"]
        if t == "cover":
            add_rect(slide, 0, 0, 33.87, 19.05, fill=PRIMARY)
            add_text(slide, p["title"], 3.0, 6.0, 27.8, 4.0, size=40, bold=True,
                     color=RGBColor(0xFF,0xFF,0xFF), align=PP_ALIGN.CENTER)
            for i, ln in enumerate(p["subtitle"].split("\n")):
                add_text(slide, ln, 3.0, 11.1 + i*0.9, 27.8, 1.0, size=16,
                         color=RGBColor(0xC7,0xD3,0xE8), align=PP_ALIGN.CENTER)
        elif t == "agenda":
            add_header(slide, "", p["title"])
            for i, item in enumerate(p["items"]):
                y = 4.2 + i * 2.2
                add_text(slide, f"{i+1:02d}", 3.2, y, 1.5, 1.4, size=26, bold=True, color=ACCENT)
                add_text(slide, item, 5.4, y + 0.15, 20, 1.4, size=22, color=DARK)
                add_rect(slide, 3.2, y + 1.35, 25, 0.05, fill=LINE)
        elif t == "section":
            add_rect(slide, 0, 0, 33.87, 19.05, fill=PRIMARY)
            add_text(slide, p["num"], 6.0, 4.0, 22, 5.0, size=80, bold=True,
                     color=RGBColor(0x4C,0x68,0x9B), align=PP_ALIGN.CENTER)
            add_text(slide, p["title"], 6.0, 10.0, 22, 2.5, size=38, bold=True,
                     color=RGBColor(0xFF,0xFF,0xFF), align=PP_ALIGN.CENTER)
            add_text(slide, p["subtitle"], 6.0, 12.7, 22, 1.2, size=14,
                     color=RGBColor(0xC7,0xD3,0xE8), align=PP_ALIGN.CENTER)
        elif t == "content":
            add_header(slide, p.get("tag"), p["title"])
            has_img = bool(p.get("image"))
            if has_img:
                add_bullets(slide, p["items"][:-1], left=2.2, top=4.4, width=17.5, height=11.5, size=16, gap=1.05)
                add_image_box(slide, 21.2, 4.4, 10.5, 11.5)
            else:
                add_bullets(slide, p["items"], left=2.2, top=4.2, width=29, height=11.5, size=17, gap=1.0)
        elif t == "code":
            add_header(slide, p.get("tag"), p["title"])
            body = p["items"]
            # 前几行为说明，转成 bullet
            add_bullets(slide, body[:3], left=2.2, top=4.0, width=29, height=3.2, size=15, gap=0.7)
            add_code(slide, p["code"], left=2.2, top=7.6, width=29, height=9.0)
        elif t == "thanks":
            add_rect(slide, 0, 0, 33.87, 19.05, fill=PRIMARY)
            add_text(slide, p["title"], 3.0, 7.0, 27.8, 2.5, size=44, bold=True,
                     color=RGBColor(0xFF,0xFF,0xFF), align=PP_ALIGN.CENTER)
            add_text(slide, p["subtitle"], 3.0, 10.8, 27.8, 1.5, size=18,
                     color=RGBColor(0xC7,0xD3,0xE8), align=PP_ALIGN.CENTER)
        if t not in ("cover","section","thanks"):
            add_footer(slide, idx)
        set_notes(slide, p.get("note",""))

    prs.save(PPTX)
    print(f"[OK] {PPTX} 已生成，共 {TOTAL} 页")

def export_md():
    lines = ["# 最终汇报 PPT 内容设计\n",
             "> 由 `汇报PPT/generate_final_ppt.py` 导出，供人工核对与配图。\n"]
    for idx, p in enumerate(PAGES, 1):
        lines.append(f"\n## 第 {idx} 页｜{'封面' if p['type']=='cover' else '目录' if p['type']=='agenda' else '章节扉页' if p['type']=='section' else '代码页' if p['type']=='code' else '感谢页' if p['type']=='thanks' else '内容页'}")
        lines.append(f"- 标题：**{p.get('title','')}**")
        if p.get("subtitle"): lines.append(f"- 副标题/说明：{p['subtitle']}")
        if p.get("items"):
            lines.append("- 内容：")
            for it in p["items"]:
                if it: lines.append(f"  - {it}")
        if p.get("code"): lines.append(f"- 代码/伪代码：\n```\n{p['code']}\n```")
        if p.get("image"):
            lines.append(f"- **配图建议**：{p['image']}")
        else:
            lines.append("- 配图：无")
        lines.append(f"- **备注/讲稿**：{p.get('note','')}")
    with open(MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[OK] {MD} 已导出")

if __name__ == "__main__":
    build()
    export_md()
