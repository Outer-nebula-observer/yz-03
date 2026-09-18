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
 {"type":"cover","title":"面向作战规划智能体的\n可进化外部记忆系统","subtitle":"国防科技大学 · 课题3 · 长短期记忆系统\n小组：姓名一 / 姓名二\n2025年7月","note":"【配图】可放校徽（可选）。\n【讲稿】开场1分钟：课题目标、单位、小组分工。","image":""},
 # ---------------- 目录 ----------------
 {"type":"agenda","title":"目录 CONTENTS","items":["01 问题与思路","02 相关工作与启发","03 系统设计与实现","04 实验设计与验证","05 智戎接入与总结展望"],"note":"【配图】无。\n【讲稿】按五部分走，重点在系统设计与实验验证。","image":""},
 # ---------------- 01 问题与思路 ----------------
 {"type":"section","num":"01","title":"问题与思路","subtitle":"PROBLEM & APPROACH","image":"","note":"【配图】可放 docs/figures/fig2_campaign_trajectory.png 作背景。\n【讲稿】先讲‘为什么需要外部记忆’。","image2":""},
 {"type":"content","tag":"01 · 问题与思路","title":"课题背景","items":["作战规划智能体以场次接任务：目标→查询→检索→规划→推演→复盘→下一场","模型与上下文都不保留跨场次状态，同类错误会反复出现","长上下文只解决容量，RAG 只解决知识供给，均不解决经验沉淀/更新/淘汰","目标：在模型之外构建可读写、可演化、可审计的外部记忆系统","配图占位：七步闭环示意图"],"note":"【配图】本页右侧图位：放 docs/figures/fig2_campaign_trajectory.png（多轮战役轨迹/七步闭环示意图）。\n【讲稿】用‘同一夜间进攻任务，第一场隘口遇伏，第二场大概率再吃亏’举例。","image":"七步闭环示意图（docs/figures/fig2_campaign_trajectory.png 或手绘）"},
 {"type":"content","tag":"01 · 问题与思路","title":"五个失败模式","layout":"numbered_list","items":["P1 经验不积累：场次间无状态传递，同样错误重复出现","P2 上下文超限：粗暴截断可能丢失硬约束，规划违反约束","P3 查询口径混杂：参数精确与经验语义同路，互相干扰","P4 库噪声：复盘无差别入库，长期库变成日志不可审计","P5 目标检索弱：直接用任务目标文本查询，语义信息量不足"],"note":"【配图】无。\n【讲稿】P1-P4 来自初始问题拆解，P5 来自导师反馈。","image":""},
 {"type":"content","tag":"01 · 问题与思路","title":"五个研究问题 RQ1-RQ5","layout":"numbered_list","items":["RQ1 双库贡献：事实/经验分库是否带来可测召回增益","RQ2 跨场次复用：第一场复盘能否被第二场召回","RQ3 检索策略：三路融合相对单路是否有增益","RQ4 滤噪与遗忘：阈值能否滤噪、遗忘是否不误删","RQ5 真实模型：DeepSeek 是否实际引用装载记忆"],"note":"【配图】无。\n【讲稿】实验章节会逐个回答。","image":""},
 {"type":"content","tag":"01 · 问题与思路","title":"总体思路","layout":"grid2x2","items":["外部系统：把记忆组织成可演化结构，不止检索增强","复盘晋升：短期→长期唯一写通道，三道门控","建议-执行分离：LLM 提候选，确定性代码执行写/合/忘/抽","阶段感知：MDMP 七阶段生成查询，对口记忆加分"],"note":"【配图】无。\n【讲稿】一句话：把跨场次知识做成可回放、可审计的外部系统。","image":""},
 # ---------------- 02 相关工作与启发 ----------------
 {"type":"section","num":"02","title":"相关工作与启发","subtitle":"RELATED WORK & INSPIRATION","image":"","note":"【配图】可放 docs/figures/fig1_architecture.png 作背景。\n【讲稿】说明借鉴什么、不采用什么。","image2":""},
 {"type":"content","tag":"02 · 相关工作与启发","title":"上下文组织与工作记忆","items":["综述框架（Zhang 2024）：记忆的‘形式-操作-应用’分层","MemGPT：主上下文+外部存档，本文改为确定性阈值换页","SCM：控制器显式决定读/写/归档，本文收敛为复盘晋升","LLMLingua/LongLLMLingua/ICAE：位置偏置与‘只压历史不压约束’"],"note":"【配图】无。\n【讲稿】每条都说明：借鉴什么、为什么不完整照搬。","image":""},
 {"type":"content","tag":"02 · 相关工作与启发","title":"长期存储与检索","items":["ChatDB：数据库即符号记忆 → 采用属性精确过滤","ExpeL：经验库+向量召回 → 补充重要性加权与持久化","Reflexion：语言反思 → 采用语言形式经验","MemoryBank：艾宾浩斯遗忘 → 加入 importance≥2 保护线","Zep：时间戳/溯源 → 采用溯源字段，不采用图存储","MIRIX / TiM：多路策略与显式检索计划 → 压缩为三路融合"],"note":"【配图】无。\n【讲稿】这一段说明检索与存储不是凭空设计。","image":""},
 {"type":"content","tag":"02 · 相关工作与启发","title":"记忆进化与设计依据","layout":"two_col","items":["PREMem：预存储推理/θ查重 → 采用相似度去重","StructMem：跨事件整合 → 演化为‘抽象’操作","MemSkill：INSERT/UPDATE/DELETE/SKIP → 采用操作类型化","Mem-α：建议-执行分离 → 本文核心架构","小结：组合层面+领域化（保护线/精确绕过阈值/阶段供给）"],"note":"【配图】无。\n【讲稿】强调：机制都有原型，差异在组合与军事场景限定。","image":""},
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
 {"type":"content","tag":"04 · 实验设计与验证","title":"数据集与评估协议","layout":"numbered_list","items":["自建 50 条 8 类测试集（A-H），避免关键词共现","固定用例集，依赖注入开关能力（G0-G6）","检索指标：hit@3/5、MRR、NDCG；任务层：引用/约束/噪声","统计：随机基线、bootstrap CI、配对置换检验"],"note":"【配图】无。\n【讲稿】强调‘对照是开关能力而不是删用例’。","image":""},
 {"type":"content","tag":"04 · 实验设计与验证","title":"双库贡献（RQ1）","layout":"stats","items":["0.636：G3 双库全开 hit@5（G2 为 0.341）","p=0.0001：配对置换检验，n=44","0.357：随机基线","0.625：C 类残余失分（词袋局限）",""],"note":"【配图】建议放消融柱状图（docs/17 配图脚本：G2 vs G3 分类别 hit@5）。\n【讲稿】这是最硬的一条证据。","image":"消融柱状图（docs/17 §8.2 脚本生成）"},
 {"type":"content","tag":"04 · 实验设计与验证","title":"跨场次与检索策略（RQ2/RQ3）","layout":"numbered_list","items":["跨场次：处理组 0.833 vs 对照 0，负控 0","p=0.059，样本有限 → 方向性证据","检索：hybrid 0.857 vs vector 0.929（词袋）","但干扰压制 hybrid 1.0 > 单路 ≤0.875","结论：混合价值在排序，真向量再定召回"],"note":"【配图】可放跨场次 WebUI 截图（第二场命中带‘往场沉淀’）或表格。\n【讲稿】对负结果要诚实：词袋下混合召回无增益。","image":"跨场次复用示意（WebUI 截图/表格）"},
 {"type":"content","tag":"04 · 实验设计与验证","title":"滤噪、遗忘与真实模型（RQ4/RQ5）","layout":"stats","items":["0%：负例返回率（min_score=0.16）","0：遗忘误删，保护线有效","1.00：DeepSeek 引用率（20/20）","0.857：正例 hit@5 保持",""],"note":"【配图】可放遗忘曲线（WebUI 截图）或 DeepSeek 输出截图。\n【讲稿】强调限定词，避免被当成最终结论。","image":"遗忘曲线（WebUI 截图）/ DeepSeek T6 输出截图"},
 # ---------------- 05 智戎接入与总结展望 ----------------
 {"type":"section","num":"05","title":"智戎接入与总结展望","subtitle":"INTEGRATION & OUTLOOK","image":"","note":"【配图】可放 docs/figures/fig2_campaign_trajectory.png 作背景。\n【讲稿】从‘能不能用’讲到‘怎么接’。","image2":""},
 {"type":"content","tag":"05 · 智戎接入与总结展望","title":"智戎事件驱动适配（P0 落地）","items":["hook_evolve：不依赖‘场次结束’，可随时触发进化","结构化反馈：AFSIM 数值/事件 → 复盘文本","normalize_task：结构化任务 → goal/constraints/queries","domain_check：领域巡检 + min_score 建议","配图占位：智戎接入架构/事件流图"],"note":"【配图】本页右侧预留图位：放 docs/figures/fig2_campaign_trajectory.png 或智戎桥接架构示意图。\n【讲稿】强调 P1（无结束信号）已有适配方案。","image":"智戎接入/事件流图（可复用 docs/figures/fig2_campaign_trajectory.png）"},
 {"type":"content","tag":"05 · 智戎接入与总结展望","title":"总结与展望","items":["结论：分层与进化机制在词袋固定设置下有效（p=0.0001）","真实模型验证了检索-生成链路可用（引用率 1.00）","下一步：真向量重跑与重标定 min_score/θ","下一步：H 类扩至 20 条、知识锚定、冲突仲裁","下一步：智戎真实链路联调与领域巡检"],"note":"【配图】无。\n【讲稿】把‘方向性/示范性’讲清楚，再列行动项。","image":""},
 {"type":"thanks","title":"感谢聆听 · 欢迎交流","subtitle":"国防科技大学 · 课题3 · 长短期记忆系统","note":"【配图】可放校徽（可选）。\n【讲稿】感谢，进入提问。","image":""},
]

# ================================================================ 绘图（增强版）
prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]
TOTAL = len(PAGES)

def _font(run, size, bold=False, color=DARK, mono=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Consolas" if mono else "Microsoft YaHei"

def add_text(slide, text, left, top, width, height, size=18, bold=False,
             color=DARK, align=PP_ALIGN.LEFT, mono=False, wrap=True):
    tb = slide.shapes.add_textbox(Cm(left), Cm(top), Cm(width), Cm(height))
    tf = tb.text_frame
    tf.word_wrap = wrap
    for i, ln in enumerate(str(text).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = ln
        _font(r, size, bold, color, mono)
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
        shp.line.width = Pt(1.2)
    shp.shadow.inherit = False
    return shp

def add_round(slide, left, top, width, height, fill=LIGHT):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                 Cm(left), Cm(top), Cm(width), Cm(height))
    shp.adjustments[0] = 0.08
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    shp.line.color.rgb = LINE; shp.line.width = Pt(1)
    shp.shadow.inherit = False
    return shp

def add_header(slide, tag, title):
    if tag:
        add_text(slide, tag, 2.35, 0.85, 14, 0.8, size=13, color=ACCENT, bold=True)
    add_rect(slide, 1.8, 1.5, 0.4, 2.5, fill=ACCENT)
    ts = 40 if len(title) <= 10 else 34 if len(title) <= 16 else 30
    add_text(slide, title, 2.5, 1.72, 29, 2.0, size=ts, bold=True, color=PRIMARY)
    add_rect(slide, 1.8, 4.05, 30.0, 0.04, fill=LINE)

def add_footer(slide, idx):
    add_rect(slide, 0, 18.35, 33.87, 0.03, fill=LINE)
    add_text(slide, "国防科技大学 · 长短期记忆系统", 1.8, 18.5, 17, 0.5, size=10, color=GREY)
    add_text(slide, f"{idx} / {TOTAL}", 28.5, 18.5, 4.0, 0.5, size=10, color=GREY,
             align=PP_ALIGN.RIGHT)

def add_corner_decor(slide, color=ACCENT):
    for x0, y0, dx, dy in [(1.8,1.6,1.6,0.06),(1.8,17.3,1.6,0.06),
                           (30.4,1.6,1.6,0.06),(30.4,17.3,1.6,0.06)]:
        add_rect(slide, x0, y0, dx, dy, fill=color)
    for x0, y0, dx, dy in [(1.8,1.6,0.06,1.2),(1.8,16.76,0.06,1.2),
                           (31.94,1.6,0.06,1.2),(31.94,16.76,0.06,1.2)]:
        add_rect(slide, x0, y0, dx, dy, fill=color)

def add_image_box(slide, left, top, width, height):
    shp = add_rect(slide, left, top, width, height, fill=LIGHT, line=ACCENT)
    # 留空，由备注说明配图

def split_head_body(item):
    for sep in ("：", ":"):
        if sep in item:
            head, body = item.split(sep, 1)
            return head.strip(), body.strip()
    return "", item.strip()

def render_cards(slide, items, left=2.0, top=4.5, width=29.8, gap=0.22, height=1.72, number=True):
    # 条目较多时自动压缩卡片高度，避免超出页面
    n = len([x for x in items if x])
    if n >= 6:
        height = 1.62
        gap = 0.16
        head_size, body_size = 12.5, 11.5
    else:
        head_size, body_size = 15, 13
    y = top
    for i, item in enumerate(items):
        if not item:
            continue
        head, body = split_head_body(item)
        card_h = height
        add_round(slide, left, y, width, card_h)
        add_rect(slide, left, y, 0.22, card_h, fill=ACCENT)
        if number:
            add_text(slide, f"{i+1:02d}", left+0.45, y+0.18, 1.5, 1.0, size=18,
                     bold=True, color=ACCENT, wrap=False)
            tx = left + 1.6
        else:
            tx = left + 0.5
        if head:
            add_text(slide, head, tx, y+0.15, width-2.2, 0.55, size=head_size, bold=True, color=PRIMARY)
            add_text(slide, body, tx, y+0.72, width-2.2, 0.85, size=body_size, color=GREY)
        else:
            add_text(slide, body, tx, y+0.42, width-2.2, 0.95, size=body_size+1, color=DARK)
        y += card_h + gap
    return y

def render_grid2x2(slide, items, left=2.0, top=4.6, width=29.8, height=5.6, gap=0.8):
    for i, item in enumerate(items[:4]):
        if not item:
            continue
        col = i % 2
        row = i // 2
        x = left + col * (width/2 + gap/2)
        y = top + row * (height + 0.6)
        w = width/2 - gap/2
        head, body = split_head_body(item)
        add_round(slide, x, y, w, height)
        add_rect(slide, x, y, 0.22, height, fill=ACCENT)
        add_text(slide, f"0{i+1}", x+0.6, y+0.4, 1.6, 1.2, size=28, bold=True, color=ACCENT)
        if head:
            add_text(slide, head, x+0.7, y+1.25, w-1.4, 1.0, size=20, bold=True, color=PRIMARY)
            add_text(slide, body, x+0.7, y+2.35, w-1.4, height-2.6, size=15, color=GREY)
        else:
            add_text(slide, body, x+0.7, y+1.7, w-1.4, height-2.0, size=16, color=DARK)

def render_numbered_list(slide, items, left=2.2, top=4.7, width=29.5, gap=1.55):
    """轻量编号列表：不用圆角卡，避免版式疲劳。"""
    y = top
    for i, item in enumerate(items):
        if not item:
            continue
        head, body = split_head_body(item)
        add_text(slide, f"{i+1:02d}", left, y, 1.8, 1.2, size=22, bold=True,
                 color=ACCENT, wrap=False)
        tx = left + 2.0
        if head:
            add_text(slide, head, tx, y+0.06, width-2.2, 0.6, size=16, bold=True, color=PRIMARY)
            add_text(slide, body, tx, y+0.72, width-2.2, 0.85, size=12.5, color=GREY)
        else:
            add_text(slide, body, tx, y+0.22, width-2.2, 1.0, size=14, color=DARK)
        add_rect(slide, left, y + 1.35, width, 0.03, fill=LINE)
        y += gap


def render_stats(slide, items, left=2.0, top=4.8, width=29.8, height=4.6, gap=0.9):
    """大数字统计：适合实验数据页，视觉区别于圆角卡。"""
    cols = min(len([x for x in items if x]), 4)
    if cols == 0:
        return
    w = (width - (cols-1)*gap) / cols
    for i, item in enumerate(items[:cols]):
        if not item:
            continue
        head, body = split_head_body(item)
        x = left + i * (w + gap)
        add_rect(slide, x, top, w, 0.55, fill=ACCENT)
        add_text(slide, head, x, top+0.95, w, 1.5, size=26, bold=True, color=PRIMARY, align=PP_ALIGN.CENTER, wrap=True)
        add_text(slide, body, x+0.3, top+2.55, w-0.6, height-2.55, size=12.5, color=GREY, align=PP_ALIGN.CENTER)


def render_two_col(slide, items, left=2.2, top=4.7, width=29.5, gap=1.5):
    """两栏对照：平分条目成左右两列，无圆角框。"""
    valid = [x for x in items if x]
    half = (len(valid) + 1) // 2
    labels = ("借鉴 / 启发", "注意 / 边界") if len(valid) >= 6 else ("要点", "补充")
    for col, start in enumerate((0, half)):
        if start >= len(valid):
            continue
        x = left + col * (width/2 + 1.6)
        w = width/2
        add_rect(slide, x, top, 1.8, 0.08, fill=ACCENT)
        add_text(slide, labels[col], x, top+0.25, w, 0.7, size=15, bold=True, color=PRIMARY)
        y = top + 1.3
        for item in valid[start:start+half]:
            head, body = split_head_body(item)
            add_text(slide, "•", x, y+0.02, 0.7, 0.7, size=14, color=ACCENT, bold=True, wrap=False)
            if head:
                add_text(slide, head, x+0.8, y+0.02, w-1.2, 0.6, size=12.5, bold=True, color=PRIMARY)
                add_text(slide, body, x+0.8, y+0.6, w-1.2, 0.8, size=11.5, color=GREY)
            else:
                add_text(slide, body, x+0.8, y+0.08, w-1.2, 0.9, size=12.5, color=DARK)
            y += gap + 0.25
        add_rect(slide, x, y+0.1, w, 0.02, fill=LINE)


def add_code_block(slide, code, left=2.0, top=8.4, width=29.8, height=8.4):
    add_rect(slide, left, top, width, 0.7, fill=PRIMARY)
    add_text(slide, "代码 / 伪代码", left+0.5, top+0.08, 8, 0.55, size=13, bold=True,
             color=RGBColor(0xFF,0xFF,0xFF))
    add_rect(slide, left, top+0.7, width, height-0.7, fill=LIGHT, line=LINE)
    add_text(slide, code, left+0.6, top+0.95, width-1.2, height-1.4,
             size=12, color=PRIMARY, mono=True)

def set_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text

# ================================================================ 生成
def build():
    for idx, p in enumerate(PAGES, 1):
        slide = prs.slides.add_slide(BLANK)
        t = p["type"]
        if t == "cover":
            add_rect(slide, 0, 0, 33.87, 19.05, fill=PRIMARY)
            add_corner_decor(slide, RGBColor(0xFF,0xFF,0xFF))
            add_rect(slide, 14.5, 5.4, 4.9, 0.06, fill=RGBColor(0x9A,0xB0,0xD0))
            add_text(slide, "GRADUATE PROJECT · FINAL REPORT", 4.0, 2.6, 26, 1.0,
                     size=14, color=RGBColor(0xC7,0xD3,0xE8), align=PP_ALIGN.CENTER)
            add_text(slide, p["title"], 3.0, 6.2, 27.8, 4.2, size=50, bold=True,
                     color=RGBColor(0xFF,0xFF,0xFF), align=PP_ALIGN.CENTER)
            sub_lines = p["subtitle"].split("\n")
            for i, ln in enumerate(sub_lines):
                add_text(slide, ln, 4.0, 11.4 + i*1.0, 26, 0.9, size=17,
                         color=RGBColor(0xC7,0xD3,0xE8), align=PP_ALIGN.CENTER)
        elif t == "agenda":
            add_header(slide, "CONTENTS", p["title"])
            for i, item in enumerate(p["items"]):
                y = 4.6 + i * 2.35
                add_round(slide, 3.0, y, 27.5, 1.9, fill=RGBColor(0xF7,0xF9,0xFC))
                add_rect(slide, 3.22, y+0.25, 1.4, 1.4, fill=ACCENT)
                add_text(slide, f"{i+1:02d}", 3.22, y+0.32, 1.4, 1.2, size=22,
                         bold=True, color=RGBColor(0xFF,0xFF,0xFF), align=PP_ALIGN.CENTER)
                add_text(slide, item, 5.2, y+0.5, 23, 1.2, size=24, bold=True, color=PRIMARY)
        elif t == "section":
            add_rect(slide, 0, 0, 33.87, 19.05, fill=PRIMARY)
            # 右上装饰圆
            c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Cm(25.5), Cm(3.5), Cm(8), Cm(8))
            c.fill.solid(); c.fill.fore_color.rgb = RGBColor(0x2C,0x4A,0x7C)
            c.line.fill.background(); c.shadow.inherit = False
            add_text(slide, p["num"], 5.0, 3.6, 14, 6.0, size=120, bold=True,
                     color=RGBColor(0x4C,0x68,0x9B), align=PP_ALIGN.LEFT)
            add_rect(slide, 5.2, 10.2, 6.0, 0.1, fill=RGBColor(0x9A,0xB0,0xD0))
            add_text(slide, p["title"], 5.0, 10.8, 22, 2.8, size=50, bold=True,
                     color=RGBColor(0xFF,0xFF,0xFF), align=PP_ALIGN.LEFT)
            add_text(slide, p["subtitle"], 5.2, 13.6, 22, 1.2, size=16,
                     color=RGBColor(0xC7,0xD3,0xE8), align=PP_ALIGN.LEFT)
        elif t == "content":
            add_header(slide, p.get("tag"), p["title"])
            items = p["items"]
            layout = p.get("layout", "cards")
            if layout == "grid2x2":
                render_grid2x2(slide, items)
            elif layout == "numbered_list":
                render_numbered_list(slide, items)
            elif layout == "two_col":
                render_two_col(slide, items)
            elif layout == "stats":
                render_stats(slide, items)
            elif p.get("image"):
                render_cards(slide, items[:-1], left=2.0, top=4.6, width=17.8, height=2.1, gap=0.22)
                add_image_box(slide, 21.4, 4.6, 10.5, 11.4)
            else:
                render_cards(slide, items, left=2.0, top=4.6, width=29.8, height=2.1, gap=0.22)
        elif t == "code":
            add_header(slide, p.get("tag"), p["title"])
            render_cards(slide, p["items"][:3], left=2.0, top=4.4, width=29.8, height=1.5, gap=0.2, number=False)
            add_code_block(slide, p["code"], left=2.0, top=8.6, width=29.8, height=8.6)
        elif t == "thanks":
            add_rect(slide, 0, 0, 33.87, 19.05, fill=PRIMARY)
            add_corner_decor(slide, RGBColor(0xFF,0xFF,0xFF))
            add_text(slide, p["title"], 3.0, 7.2, 27.8, 3.0, size=54, bold=True,
                     color=RGBColor(0xFF,0xFF,0xFF), align=PP_ALIGN.CENTER)
            add_text(slide, p["subtitle"], 3.0, 11.4, 27.8, 1.5, size=18,
                     color=RGBColor(0xC7,0xD3,0xE8), align=PP_ALIGN.CENTER)
        if t not in ("cover", "section", "thanks"):
            add_footer(slide, idx)
        set_notes(slide, p.get("note", ""))

    prs.save(PPTX)
    print(f"[OK] {PPTX} 已生成，共 {TOTAL} 页")

def export_md():
    lines = ["# 最终汇报 PPT 内容设计\n",
             "> 由 `汇报PPT/generate_final_ppt.py` 导出，供人工核对与配图。\n"]
    for idx, p in enumerate(PAGES, 1):
        kind = {"cover":"封面","agenda":"目录","section":"章节扉页","code":"代码页","thanks":"感谢页"}.get(p["type"],"内容页")
        lines.append(f"\n## 第 {idx} 页｜{kind}")
        lines.append(f"- 标题：**{p.get('title','')}**")
        if p.get("subtitle"): lines.append(f"- 副标题/说明：{p['subtitle'].replace(chr(10),' / ')}")
        if p.get("items"):
            lines.append("- 内容：")
            for it in p["items"]:
                if it: lines.append(f"  - {it}")
        if p.get("code"): lines.append(f"- 代码/伪代码：\n```\n{p['code']}\n```")
        if p.get("image"):
            lines.append(f"- **配图建议**：{p['image']}")
        else:
            lines.append("- 配图：无")
        lines.append(f"- **备注/讲稿**：{p.get('note','').replace(chr(10),' | ')}")
    with open(MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[OK] {MD} 已导出")

if __name__ == "__main__":
    build()
    export_md()
