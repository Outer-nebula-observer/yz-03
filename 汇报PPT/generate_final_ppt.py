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
 {"type":"cover","title":"面向作战规划智能体的\n可进化外部记忆系统","subtitle":"国防科技大学 · 课题3 · 长短期记忆系统\n小组：姓名一 / 姓名二\n2025年7月","note":"【配图】封面可放校徽（可选）；无需其他图。\n【讲稿】各位老师好，我们小组汇报的课题是《面向作战规划智能体的可进化外部记忆系统》。系统面向场次制规划任务，目标是在模型之外建立可读写、可演化、可审计的记忆。汇报分五个部分：问题与思路、相关工作与启发、系统设计与实现、实验设计与验证、智戎接入与总结展望。","image":""},
 # ---------------- 目录 ----------------
 {"type":"agenda","title":"目录 CONTENTS","items":["问题与思路","相关工作与启发","系统设计与实现","实验设计与验证","智戎接入与总结展望"],"note":"【配图】无。\n【讲稿】汇报主线是五步：先讲清问题，再说明我们从已有工作里借鉴了什么，然后给出系统设计与代码实现，接着用消融和真模型验证，最后讲智戎接入与下一步。重点在第 3、4 部分。","image":""},
 # ---------------- 01 问题与思路 ----------------
 {"type":"section","num":"01","title":"问题与思路","subtitle":"PROBLEM & APPROACH","image":"","note":"【配图】章首主视觉可用 docs/figures/ppt/ppt_session_cycle.svg（竖版 900×1060）。\n【讲稿】第一章先界定问题：为什么场次制规划需要外部记忆。","image2":""},
 {"type":"content","tag":"01 · 问题与思路","title":"课题背景","items":["从零开始的问题：作战规划智能体以场次接任务，目标→查询→检索→规划→推演→复盘→下一场；模型与上下文都不保留跨场次状态，同类错误会反复出现。","长上下文不够：扩展窗口只解决“当前提示词放得下”，窗口关闭后信息即失效；RAG 只解决外部知识供给，不解决经验如何沉淀、更新与淘汰。","模型内记忆代价高：通过微调或状态注入改变模型本身，成本高且无法审计；军事场景需要可回放、可解释的记忆操作。","目标定位：在模型之外构建可读写、可演化、可审计的外部记忆系统，以“写入-检索-更新-淘汰”为生命周期。"],"note":"【配图】右侧大图位 10.9×12.9cm，放 docs/figures/ppt/ppt_session_cycle.svg（PPT 已插入同名 PNG）：场次循环 + 状态不跨场次。\n【讲稿】作战规划智能体按场次接任务：目标→查询→检索→规划→推演→复盘→下一场。模型权重与上下文都不保留跨场次状态，所以同类错误会反复出现。长上下文只解决容量，RAG 只解决知识供给，都不解决经验沉淀、更新与淘汰。因此我们要在模型之外构建可读写、可演化、可审计的外部记忆系统。","image":"docs/figures/ppt/ppt_session_cycle.png"},
 {"type":"content","tag":"01 · 问题与思路","title":"五个失败模式","layout":"icon_rows","icons":["docs/figures/ppt/ppt_p1.png","docs/figures/ppt/ppt_p2.png","docs/figures/ppt/ppt_p3.png","docs/figures/ppt/ppt_p4.png","docs/figures/ppt/ppt_p5.png"],"items":["P1 经验不积累：场次间无状态传递；第一场在隘口遇伏，第二场可能仍未派先遣侦察，失败教训没有载体。","P2 上下文超限：场内战报与硬约束同时涌入，粗暴截断可能把“禁止越境”等约束切掉，规划易合规出错。","P3 查询口径混杂：装备参数需要精确，经验教训需要语义泛化；同一路无法同时满足精确与召回。","P4 库噪声：复盘无差别入库让长期库积累流水账，信号被噪声淹没，且无法回答“这条为什么在库中”。","P5 目标检索弱：直接用任务目标一句话查询信息量太薄，规划不同阶段需要的记忆类型不同。"],"note":"【配图】每行右侧小图位 3.2×2.0cm，依次放 docs/figures/ppt/ppt_p1.svg ~ ppt_p5.svg（PPT 已插入同名 PNG）。\n【讲稿】我们把问题拆成五个失败模式：P1 经验不积累；P2 上下文超限导致硬约束丢失；P3 参数精确查询与经验语义查询混用单路；P4 复盘无差别入库让库变日志；P5 直接用目标文本查询信息量太薄。这五个问题分别对应后面的设计取舍。","image":""},
 {"type":"content","tag":"01 · 问题与思路","title":"五个研究问题 RQ1-RQ5","layout":"mapping_rows","icons":["docs/figures/ppt/ppt_rq1.png","docs/figures/ppt/ppt_rq2.png","docs/figures/ppt/ppt_rq3.png","docs/figures/ppt/ppt_rq4.png","docs/figures/ppt/ppt_rq5.png"],"items":["P1/P5 → RQ1 双库贡献：事实/经验分库是否在固定用例集上带来可测召回增益？对应 G2 vs G3 消融。","P1 → RQ2 跨场次复用：第一场复盘写入能否被第二场召回？处理组 0.833 vs 对照 0。","P3 → RQ3 检索策略：三路融合相对单路是否有增益？词袋下召回未胜出，排序/干扰压制更好。","P2/P4 → RQ4 滤噪与遗忘：阈值能否滤除负例、遗忘是否不误删保护记忆？","P4 → RQ5 真实模型：DeepSeek 是否实际引用装载记忆？T6 引用率 1.00。"],"note":"【配图】每行右侧小图位，依次放 docs/figures/ppt/ppt_rq1.svg ~ ppt_rq5.svg（PPT 已插入同名 PNG），体现 P→RQ 映射。\n【讲稿】由五个失败模式引申出五个研究问题：RQ1 双库贡献、RQ2 跨场次复用、RQ3 检索策略、RQ4 滤噪与遗忘、RQ5 真实模型。每个 RQ 都对应可量化的实验，后面实验章节会逐一回答。","image":""},
 {"type":"content","tag":"01 · 问题与思路","title":"总体思路","layout":"grid2x2","items":["外部系统：把记忆从上下文窗口搬到独立系统，可写、可检索、可更新、可淘汰；短期管当前场次，长期管跨场次知识。","复盘晋升：短期→长期只留一条写通道，即场次结束后的复盘；三道门控：复盘驱动、类别判定、语义查重，每次操作进审计日志。","建议-执行分离：LLM/规则只负责提候选，写入、合并、遗忘、抽象由确定性代码执行；保证“为什么删、从哪来”可审计。","阶段感知：查询按 MDMP 七阶段生成，阶段匹配记忆加亲和分；复盘教训归因到阶段，让“方案拟制”优先看到历史战例。"],"note":"【配图】建议把 docs/figures/ppt/ppt_four_principles.svg（1000×560）放在 2×2 卡片旁或做成半页图。\n【讲稿】总体思路四句话：把记忆做成可演化的外部系统；短期到长期只留复盘晋升一条写通道；LLM 只提候选、确定性代码执行写合忘抽；查询按 MDMP 阶段生成并给对口记忆加分。这四点分别回应前面的失败模式。","image":""},
 # ---------------- 02 相关工作与启发 ----------------
 {"type":"section","num":"02","title":"相关工作与启发","subtitle":"RELATED WORK & INSPIRATION","image":"","note":"【配图】章首主视觉可用 docs/figures/ppt/ppt_architecture.svg。\n【讲稿】第二章梳理相关工作，说明我们借鉴了什么、不采用什么。","image2":""},
 {"type":"content","tag":"02 · 相关工作与启发","title":"上下文组织与工作记忆","layout":"vert_fill","items":["综述框架（Zhang 2024）：把记忆工作归纳为“形式-操作-应用”三层；本文补齐“写、更新、遗忘”闭环并把每步做成可审计事件。","MemGPT 分层：主上下文+外部存档；本文采用分层，但改成确定性阈值换页（0.7预警/1.0压缩），保证可复现可消融。","SCM 控制器：显式决定何时读/写/归档；本文沿用“控制器唯一调度”，但把写长期库收窄为复盘晋升一条通道。","LLMLingua/ICAE 压缩：借用位置偏置与“只压历史不压约束”，压缩器本身留作后续扩展。"],"note":"【配图】建议插入 docs/figures/ppt/ppt_context_layers.svg（常驻关键区/装载记忆/滚动消息三层）。\n【讲稿】上下文管理上，综述给出“形式-操作-应用”框架；MemGPT 提出主上下文+外部存档，我们采用分层但把换页改成确定性阈值，保证可复现；SCM 强调控制器决定读写归档，我们沿用但把写长期库收窄为复盘晋升；LLMLingua/ICAE 的压缩我们只借用位置偏置和“只压历史不压约束”。","image":""},
 {"type":"content","tag":"02 · 相关工作与启发","title":"长期存储与检索","layout":"numbered_list","items":["ChatDB：数据库即符号记忆 → 只保留属性精确过滤，不实现全量 NL→SQL。","ExpeL：经验库+向量召回 → 补齐重要性加权与 SQLite 持久化。","Reflexion：语言反思 → 采用语言形式经验，不采用在线强化。","MemoryBank：艾宾浩斯遗忘+召唤强化 → 增加 importance≥2 保护线。","Zep：时序知识图谱+溯源 → 采用溯源字段，不采用图存储。","MIRIX/TiM：多路策略与显式检索计划 → 压缩为三路融合。"],"note":"【配图】建议插入 docs/figures/ppt/ppt_dual_store.svg（事实库/经验库 + 三路读取）。\n【讲稿】长期存储与检索上，ChatDB 的数据库即符号记忆让我们保留属性精确过滤；ExpeL 的经验库+向量召回让我们保留经验语义；Reflexion 的语言反思、MemoryBank 的遗忘曲线、Zep 的溯源字段、MIRIX/TiM 的多路检索分别对应我们的经验表示、遗忘保护线、溯源和路由设计。","image":""},
 {"type":"content","tag":"02 · 相关工作与启发","title":"记忆进化与设计依据","layout":"two_col","items":["PREMem：θ 相似度去重 → 写入前查重","StructMem：跨事件整合 → “抽象”操作","MemSkill：操作类型化 → MemoryOp 枚举","Mem-α：建议-执行分离 → 核心架构","不采用完整聚类：50 条量级收益不明显","不采用在线强化：战场奖励信号不稳定","不采用图存储：构建纠错成本高","领域化：保护线、精确绕过阈值、阶段供给"],"note":"【配图】建议插入 docs/figures/ppt/ppt_evolution_ops.svg（写入/合并/遗忘/抽象四操作）。\n【讲稿】记忆进化上，PREMem 的相似度去重、StructMem 的跨事件整合、MemSkill 的操作类型化、Mem-α 的建议-执行分离，分别启发了我们的写入查重、抽象、MemoryOp 枚举和整体架构。差异在组合方式与军事场景限定：保护线、精确命中绕过阈值、阶段化供给。","image":""},
 # ---------------- 03 系统设计与实现 ----------------
 {"type":"section","num":"03","title":"系统设计与实现","subtitle":"DESIGN & IMPLEMENTATION","image":"","note":"【配图】章首主视觉可用 docs/figures/ppt/ppt_architecture.svg。\n【讲稿】第三章进入系统设计与实现，先看总体架构，再看短期、长期、检索、进化的具体代码。","image2":""},
 {"type":"content","tag":"03 · 系统设计与实现","title":"总体架构","items":["四层架构：模型层统一数据对象，能力层分短期/长期/检索/进化，跨切面处理边界与阶段，编排层由控制器与管线调度。","模块解耦：四个能力层互不 import，只通过 schema 对象通信，为独立消融提供物理基础。","唯一写通道：短期→长期只经复盘晋升，经三道边界门，每次判定写入审计日志。","可独立消融：通过依赖注入开关能力，G0-G6 固定用例集验证。","配图占位：系统架构图"],"note":"【配图】右侧大图位 10.9×12.9cm，放 docs/figures/ppt/ppt_architecture.svg（PPT 已插入同名 PNG）。\n【讲稿】系统分四层：模型层统一数据对象，能力层分短期/长期/检索/进化，跨切面负责边界与阶段，编排层由控制器和管线调度。四能力层互不 import，只通过 schema 对象通信，因此可以独立开关做消融。短期到长期只经复盘晋升，并有三道边界门和审计日志。","image":"docs/figures/ppt/ppt_architecture.png"},
 {"type":"code","tag":"03 · 系统设计与实现","title":"短期工作记忆","items":["槽位保存目标/约束/查询/消息；约束永不压缩，保证规划合规","FIFO 超阈值触发递归摘要，被驱逐消息进入归档区供复盘晋升","渲染顺序刻意使用首尾位置偏置：关键信息放头部，近期消息放尾部"],"code":"def render(slot):\n    parts = [阶段, 目标, 约束]\n    if slot.loaded_briefs:\n        parts.append('【装载记忆】' + briefs)\n    parts.append(查询列表)\n    parts.append(最新消息[-20:])\n    return '\\n'.join(parts)\n\ndef flush(slot, llm):\n    evicted = slot.fifo.pop(前半)\n    slot.summary = llm.summarize(旧摘要 + evicted)\n    slot.archived.append(evicted)","note":"【配图】建议插入 docs/figures/ppt/ppt_fifo_summary.svg（FIFO→递归摘要→归档）。\n【讲稿】短期工作记忆用槽位保存目标、约束、查询和消息，约束永不压缩。FIFO 超阈值时把最旧消息移出，递归生成摘要，原文进入归档供复盘。渲染顺序刻意使用首尾位置偏置：关键信息放头部、近期消息放尾部。","image":""},
 {"type":"code","tag":"03 · 系统设计与实现","title":"长期双库","items":["事实库：SQLite+属性精确；经验库：向量语义召回","attrs 精确命中绕过 min_score——查询方显式指定条件即构造性相关","接口示例与融合策略如下"],"code":"hits_exact = factual.search_attrs({'装备': 'T-90'})\nhits_sem = experiential.search('夜战侦察教训')\n# 融合时：attrs 命中即相关，不参与相似度阈值","note":"【配图】建议插入 docs/figures/ppt/ppt_dual_store.svg（双库接口与三路读取）。\n【讲稿】长期记忆分事实库和经验库：事实库用 SQLite 和属性精确过滤，经验库用向量语义召回。属性精确命中绕过 min_score，因为查询方显式指定条件时命中即相关。这样参数查询不会被相似度阈值卡住，经验查询也能跨措辞召回。","image":""},
 {"type":"code","tag":"03 · 系统设计与实现","title":"混合检索：三路融合 + 单路","items":["vector/BM25/SQL 三路；hybrid 加权累加，single 供消融","归一化：向量余弦、BM25 查询自匹配上界、SQL 恒 1","公式：s_hybrid = Σ w_r·n_r(id)"],"code":"def retrieve(q, mode='hybrid', top_k=5):\n    pool = [route(q, q.route)]\n    if mode == 'hybrid':\n        pool += [route(q, alt) for alt in routes\n                 if alt != q.route]\n    pool = [normalize(r) for r in pool]\n    fused = aggregate_by_id(pool, weights)\n    if q.stage:\n        fused = add_stage_bonus(fused, q.stage)\n    ranked = [x for x in sorted(fused, reverse=True)\n              if x.score >= min_score][:top_k]\n    for r in ranked:\n        r.entry.mark_recalled()\n    return ranked","note":"【配图】建议插入 docs/figures/ppt/ppt_hybrid_retrieval.svg（三路融合/归一/阶段亲和）。\n【讲稿】检索层把 vector、BM25、SQL 三路放在一起：hybrid 模式三路加权累加，single 模式只走一路供消融。归一化时向量取余弦、BM25 用查询自匹配作上界、SQL 恒为 1；然后叠加阶段亲和、过滤 min_score，对最终结果只做一次命中强化，避免同一记忆被强化多次。","image":""},
 {"type":"code","tag":"03 · 系统设计与实现","title":"记忆进化：写/合/忘/抽","items":["建议-执行分离：LLM 提候选，确定性代码执行写/合/忘/抽","遗忘：R=e^{-t/S}，命中 S+1；importance≥2 保护","同场新经验≥2 条触发抽象"],"code":"def evolve_from_review(review, session_id):\n    ops = llm.extract_memory_ops(review)\n    for op in ops:\n        if not boundary.promote(op.content):\n            continue\n        if write(op) is None:\n            skipped += 1\n    merge_new_entries()\n    forget()\n    if len(new_experiences) >= 2:\n        abstract()\n\n# 遗忘核心\nR = exp(-t / max(S, 1e-6))\n# 命中强化\nS += 1; t 重置","note":"【配图】建议插入 docs/figures/ppt/ppt_forgetting_curve.svg（R=e^{-t/S} 与 S+1）。\n【讲稿】进化采用建议-执行分离：LLM 从复盘中提候选，确定性代码执行写入、合并、遗忘、抽象。遗忘用艾宾浩斯公式 R=e^{-t/S}，命中一次 S 加一并重置时间；importance≥2 的记忆受保护。这样既保证记忆会淘汰，也保证失败教训不会被误删。","image":""},
 {"type":"content","tag":"03 · 系统设计与实现","title":"边界门控与阶段感知","layout":"vert_fill","items":["复盘驱动：只有场次复盘文本才能触发晋升，流水账被挡在门外","类别判定：事实/经验分别进入对应存储，避免类型混乱","语义查重：写入前 θ 余弦去重，重复经验不重复入库；每次判定写审计日志","阶段感知：查询按 MDMP 七阶段生成，阶段匹配记忆加亲和分，复盘教训归因到阶段"],"note":"【配图】建议插入 docs/figures/ppt/ppt_boundary_stages.svg（复盘驱动→类别门→查重→阶段）。\n【讲稿】短期内容进入长期库必须过三道门：复盘驱动、类别判定、语义查重，每次判定写入审计日志。阶段感知则把查询按 MDMP 七阶段生成，阶段匹配的记忆加亲和分，复盘教训按阶段归因，让后续同阶段优先召回。","image":""},
 {"type":"content","tag":"03 · 系统设计与实现","title":"WebUI 可视化","items":["三栏页签化布局：左输入/中运行/右产出，长内容折叠为页签","记忆详情抽屉：总览/单条历史/遗忘日志，支持点击展开","遗忘曲线：R=e^{-t/S} 与‘立即召回 S+1’对比","战役进度条、库健康度分布条、事件流点击展开详情","配图占位：WebUI 截图"],"note":"【配图】右侧大图位 10.9×12.9cm，放 docs/figures/ppt/ppt_webui.svg（PPT 已插入同名 PNG）：三栏/抽屉/遗忘曲线。\n【讲稿】WebUI 用三栏页签化布局：左输入、中运行、右产出，长内容折叠为页签。记忆详情抽屉展示总览、单条历史和遗忘日志；遗忘曲线把 R=e^{-t/S} 和“立即召回 S+1”放在一起对比；还有战役进度条、库健康度分布条和可展开的事件流。","image":"docs/figures/ppt/ppt_webui.png"},
 # ---------------- 04 实验设计与验证 ----------------
 {"type":"section","num":"04","title":"实验设计与验证","subtitle":"EXPERIMENTS","image":"","note":"【配图】章首主视觉可用 docs/figures/ppt/ppt_ablation.svg。\n【讲稿】第四章是实验设计与验证，先讲数据集和协议，再按 RQ 给结果。","image2":""},
 {"type":"content","tag":"04 · 实验设计与验证","title":"数据集与评估协议","layout":"vert_fill","items":["实验目标与 RQ 对应：围绕 RQ1-RQ5 设计五组实验；每组独立 controller，避免跨组污染；固定 44 条检索用例，H 类 6 条单独跑跨场次流程。","测试集构建：自建 50 条 8 类（A-H），覆盖属性/事实/经验/词法/负例/干扰/阶段/跨场次；查询与答案刻意避免关键词共现，负例只测噪声。","对照与开关：G0-G6 通过依赖注入开关能力（空经验库/空检索器），不删减用例；跨场次 gold 在运行期解析，避免种子记忆被误当沉淀。","指标与统计：检索层 hit@3/5、MRR、NDCG；任务层 引用率/约束满足/噪声污染；统计用随机基线、bootstrap CI、配对置换检验，种子固定 42。"],"note":"【配图】建议插入 docs/figures/ppt/ppt_testset.svg（50 条 8 类结构）。\n【讲稿】实验用的测试集是自建 50 条 8 类，查询与答案刻意避免关键词共现。所有组在固定用例集上跑，通过依赖注入开关能力，而不是删减用例；跨场次 gold 在运行期解析。指标分检索层和任务层，统计用随机基线、bootstrap 置信区间和配对置换检验，种子固定 42。","image":""},
 {"type":"content","tag":"04 · 实验设计与验证","title":"双库贡献（RQ1）","layout":"stats_plus","items":["0.636：G3 双库全开 hit@5（G2 为 0.341）","p=0.0001：配对置换检验（n=44）","0.357：随机基线","0.625：C 类转述命中（词袋局限）","实验设计：G2 仅事实库 vs G3 双库全开，44 条固定检索用例，依赖注入开关经验库","置信区间与分类别：G3 CI=[0.500,0.773] 与 G2 CI=[0.205,0.477] 不重叠；增益来自经验类，事实类不降","解读：分层不是冗余，经验库是经验查询的必要条件"],"note":"【配图】建议插入 docs/figures/ppt/ppt_ablation.svg（G2/G3 柱状 + 随机基线）。\n【讲稿】RQ1 实验是 G2 仅事实库对 G3 双库全开，同为 44 条固定用例。结果 G2 hit@5=0.341，G3=0.636，Δ=0.295，配对置换 p=0.0001，两组置信区间不重叠。分类别看，增益全部来自经验类，事实类没有下降，说明双库分层不是冗余，经验库是经验查询的必要条件。","image":"消融柱状图（docs/17 §8.2 脚本生成）"},
 {"type":"content","tag":"04 · 实验设计与验证","title":"跨场次与检索策略（RQ2/RQ3）","layout":"vert_fill","items":["RQ2 实验设计：第一场先跑复盘，把‘教训/经验’写入经验库；第二场用相关查询检索，gold 为运行期写入条目；对照不写第一场；另设负控（渡河教训 vs 巷战查询）。","RQ2 结果与解释：处理组 hit@5=0.833、对照 0、负控 0；p=0.059 但 n=6 样本有限，只能算方向性证据——机制路径完整，需要扩容到 20 条再下结论。","RQ3 实验设计：同一批检索用例分别跑 hybrid 与 vector/bm25/sql 单路；权重变体（α.7 等）做敏感性；指标含 hit@5、MRR、干扰压制。","RQ3 结果与解释：词袋下 hybrid 0.857 未超 vector 0.929；但干扰压制 1.0 优于单路 ≤0.875；结论：混合的价值在排序，召回增益需真向量复测。"],"note":"【配图】建议插入 docs/figures/ppt/ppt_cross_session.svg（第一场复盘→第二场召回）。\n【讲稿】RQ2 的做法是第一场先跑复盘写入经验，第二场用相关查询检索，gold 为运行期写入条目，对照不写第一场，另设负控。处理组 hit@5=0.833、对照 0、负控 0，机制路径完整；但样本只有 6 条，p=0.059，只能算方向性证据。RQ3 比较 hybrid 与单路：词袋下 hybrid 召回未胜出，但干扰压制更好，说明混合价值在排序，需真向量复测。","image":"跨场次复用示意（WebUI 截图/表格）"},
 {"type":"content","tag":"04 · 实验设计与验证","title":"滤噪、遗忘与真实模型（RQ4/RQ5）","layout":"stats_plus","items":["0%：负例返回率（min_score=0.16）","0：遗忘误删（保护线有效）","1.00：DeepSeek 引用率（20/20）","0.857：正例 hit@5 保持","滤噪实验：E 扫描 0.05/0.10/0.16/0.25，0.16 为当前网格拐点","遗忘实验：合成老化 30 天 forget，未保护删 10/10，保护/新写 0；S+1 显著延长寿命","真模型：20/20 通过，T6 引用 1.00、约束 1.00；限定词袋/单次，示范性证据"],"note":"【配图】建议组合插入 docs/figures/ppt/ppt_min_score.svg、ppt_forgetting_curve.svg、ppt_deepseek.svg（三选一或上下组合）。\n【讲稿】RQ4 包含两个实验：滤噪扫描 min_score 的四个取值，0.16 时负例返回率归零、正例 hit@5=0.857；遗忘实验把时间戳回拨 30 天后运行 forget，未保护删 10/10，保护和新写入删 0，误删为 0。RQ5 用 DeepSeek 验证 20 项全过，T6 规划引用率 1.00、约束满足 1.00。需要强调这些都在 MockEmbedding 之上且为单次运行，属于示范性证据。","image":"遗忘曲线（WebUI 截图）/ DeepSeek T6 输出截图"},
 # ---------------- 05 智戎接入与总结展望 ----------------
 {"type":"section","num":"05","title":"智戎接入与总结展望","subtitle":"INTEGRATION & OUTLOOK","image":"","note":"【配图】章首主视觉可用 docs/figures/ppt/ppt_zhirong.svg。\n【讲稿】第五章讲智戎接入与总结展望。","image2":""},
 {"type":"content","tag":"05 · 智戎接入与总结展望","title":"智戎事件驱动适配（P0 落地）","items":["hook_evolve：不依赖‘场次结束’，可随时触发进化","结构化反馈：AFSIM 数值/事件转复盘文本，失败补‘教训’","normalize_task：结构化任务 → goal/constraints/queries","domain_check：领域巡检 + min_score 建议，等待真实数据","配图占位：智戎接入/事件流图"],"note":"【配图】右侧大图位 10.9×12.9cm，放 docs/figures/ppt/ppt_zhirong.svg（PPT 已插入同名 PNG）：三挂接点→事件驱动。\n【讲稿】智戎平台可能没有“场次结束”和“复盘文本”，所以我们做了 P0 适配：hook_evolve 不依赖场次结束，可以随时触发进化；结构化反馈把 AFSIM 的数值和事件转成复盘文本；normalize_task 把结构化任务转成 goal/constraints/queries；domain_check 用于真实数据的领域巡检和阈值建议。","image":"docs/figures/ppt/ppt_zhirong.png"},
 {"type":"content","tag":"05 · 智戎接入与总结展望","title":"总结与展望","layout":"summary_split","left_count":2,"items":["分层有效：结构层结论在词袋固定设置下稳定，双库 p=0.0001","真模型可用：DeepSeek 引用率 1.00，检索-生成链路打通","真向量复测：重跑消融并重标定 min_score/θ","数据扩容：H 类扩至 20 条，让 p 值有意义","机制补全：知识锚定、冲突仲裁、软删除","智戎联调：真实链路与领域巡检"],"note":"【配图】建议插入 docs/figures/ppt/ppt_roadmap.svg（下一步四步路线）。\n【讲稿】总结两条结论：分层与进化机制在词袋固定设置下有效，双库 p=0.0001；真模型验证了检索-生成链路可用，引用率 1.00。下一步四件事：真向量重跑并重标定、H 类扩到 20 条、补知识锚定和冲突仲裁、接入智戎真实链路。","image":""},
 {"type":"thanks","title":"感谢聆听 · 欢迎交流","subtitle":"国防科技大学 · 课题3 · 长短期记忆系统","note":"【配图】感谢页可放校徽（可选）。\n【讲稿】我的汇报到此结束，感谢各位老师，欢迎提问。","image":""},
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

def add_image_box(slide, left, top, width, height, img_path=None):
    """图位：若提供存在的图片则按 contain 缩放居中插入，否则画空白框。"""
    if img_path:
        full = img_path if os.path.isabs(img_path) else os.path.join(os.path.dirname(OUT_DIR), img_path)
        if os.path.exists(full):
            try:
                pic = slide.shapes.add_picture(full, Cm(left), Cm(top))
                w_cm = pic.width / 360000.0
                h_cm = pic.height / 360000.0
                ratio = min(width / w_cm, height / h_cm)
                pic.width = Cm(w_cm * ratio)
                pic.height = Cm(h_cm * ratio)
                pic.left = Cm(left + (width - w_cm * ratio) / 2)
                pic.top = Cm(top + (height - h_cm * ratio) / 2)
                add_rect(slide, left, top, width, height, fill=None, line=ACCENT)
                return
            except Exception as e:
                print("[warn] 插图失败:", full, e)
    add_rect(slide, left, top, width, height, fill=LIGHT, line=ACCENT)

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
    if len([x for x in items if x]) >= 6:
        gap = 1.2
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


def render_vert_fill(slide, items, left=2.2, top=4.8, width=29.5, bottom=17.4):
    """竖向四段/五段铺满：编号 + 内容标题 + 文字说明，适用于课题背景等。"""
    valid = [x for x in items if x]
    n = len(valid)
    if n == 0:
        return
    step = (bottom - top) / n
    for i, item in enumerate(valid):
        y = top + i * step
        head, body = split_head_body(item)
        add_text(slide, f"{i+1:02d}", left, y+0.28, 1.8, 1.2, size=26, bold=True,
                 color=ACCENT, wrap=False)
        tx = left + 2.0
        add_text(slide, head, tx, y+0.2, width-2.2, 0.9, size=20, bold=True, color=PRIMARY)
        add_text(slide, body, tx, y+1.05, width-2.2, step-1.5, size=14, color=GREY)
        add_rect(slide, left, y + step - 0.28, width, 0.03, fill=LINE)


def render_icon_rows(slide, items, left=2.2, top=4.8, width=29.5, bottom=17.4, icon_w=6.0, icons=None):
    """五段横向行：编号+标题+正文，右侧预留小图框。"""
    valid = [x for x in items if x]
    n = len(valid)
    if n == 0:
        return
    step = (bottom - top) / n
    for i, item in enumerate(valid):
        y = top + i * step
        head, body = split_head_body(item)
        add_text(slide, f"{i+1:02d}", left, y+0.28, 1.8, 1.2, size=24, bold=True,
                 color=ACCENT, wrap=False)
        tx = left + 2.0
        text_w = left + width - tx - icon_w - 0.5
        add_text(slide, head, tx, y+0.18, text_w, 0.8, size=18, bold=True, color=PRIMARY)
        add_text(slide, body, tx, y+0.95, text_w, step-1.4, size=13, color=GREY)
        img = icons[i] if icons and i < len(icons) else None
        add_image_box(slide, left + width - icon_w, y + step*0.18, icon_w, step*0.62, img)
        add_rect(slide, left, y + step - 0.25, width, 0.025, fill=LINE)


def render_mapping_rows(slide, items, left=2.2, top=4.8, width=29.5, bottom=17.4, icon_w=6.0, icons=None):
    """P→RQ 映射行：左侧来源标签 + 箭头 + RQ 标题/正文 + 右侧图位。"""
    valid = [x for x in items if x]
    n = len(valid)
    if n == 0:
        return
    step = (bottom - top) / n
    for i, item in enumerate(valid):
        y = top + i * step
        head, body = split_head_body(item)
        if "→" in head:
            src, name = head.split("→", 1)
        else:
            src, name = f"P{i+1}", head
        add_round(slide, left, y+0.24, 3.6, 1.9, fill=RGBColor(0xE7, 0xEF, 0xF9))
        add_text(slide, src.strip(), left+0.2, y+0.58, 3.2, 1.2, size=18, bold=True,
                 color=ACCENT, align=PP_ALIGN.CENTER, wrap=False)
        ax = left + 4.0
        add_text(slide, "→", ax, y+0.35, 1.0, 1.4, size=28, bold=True, color=ACCENT, wrap=False)
        tx = ax + 1.2
        text_w = left + width - tx - icon_w - 0.4
        add_text(slide, name.strip(), tx, y+0.15, text_w, 0.9, size=19, bold=True, color=PRIMARY)
        add_text(slide, body, tx, y+1.02, text_w, step-1.5, size=13.5, color=GREY)
        img = icons[i] if icons and i < len(icons) else None
        add_image_box(slide, left + width - icon_w, y+0.4, icon_w, step*0.6, img)
        add_rect(slide, left, y + step - 0.22, width, 0.025, fill=LINE)


# 简易 Python 伪代码高亮
KEYWORDS = {"def","return","if","else","elif","for","while","in","not","and","or",
            "import","None","True","False","continue","break","from","with","try",
            "except","raise","pass","lambda","as"}
C_KW = RGBColor(0x1F, 0x3A, 0x68)
C_FUNC = RGBColor(0x2F, 0x6E, 0xBA)
C_STR = RGBColor(0xC0, 0x50, 0x4D)
C_COMMENT = RGBColor(0x6A, 0x8B, 0x3B)
C_NUM = RGBColor(0x7B, 0x4F, 0xA6)
C_DEF = RGBColor(0x30, 0x30, 0x30)

def tokenize_line(line):
    """返回 [(token, kind)]，kind ∈ kw/func/str/comment/num/def/space/op。"""
    out = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "#":
            out.append((line[i:], "comment")); break
        if ch == "'" or ch == '"':
            quote = ch
            j = i + 1
            while j < n and line[j] != quote:
                j += 1
            j = min(j + 1, n)
            out.append((line[i:j], "str")); i = j; continue
        if ch.isspace():
            j = i
            while j < n and line[j].isspace(): j += 1
            out.append((line[i:j], "space")); i = j; continue
        if ch.isdigit():
            j = i
            while j < n and (line[j].isdigit() or line[j] in "._"): j += 1
            out.append((line[i:j], "num")); i = j; continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (line[j].isalnum() or line[j] == "_"): j += 1
            word = line[i:j]
            if word in KEYWORDS:
                out.append((word, "kw"))
            elif j < n and line[j] == "(":
                out.append((word, "func"))
            else:
                out.append((word, "def"))
            i = j; continue
        out.append((ch, "op")); i += 1
    return out

def render_stats_plus(slide, items, left=2.2, top=4.8, width=29.5, bottom=17.7):
    """大数字 + 详细说明：保留大字冲击力，下方再给实验细节。"""
    stats = items[:4]
    details = items[4:]
    gap = 0.6
    n = len([x for x in stats if x])
    if n == 0:
        n = 1
    card_w = (width - gap * (n - 1)) / n
    for i, item in enumerate(stats[:4]):
        if not item:
            continue
        head, body = split_head_body(item)
        x = left + i * (card_w + gap)
        add_rect(slide, x, top, card_w, 0.55, fill=ACCENT)
        add_text(slide, head, x, top+0.85, card_w, 1.5, size=30, bold=True,
                 color=PRIMARY, align=PP_ALIGN.CENTER, wrap=True)
        add_text(slide, body, x+0.25, top+2.5, card_w-0.5, 1.6, size=12.5,
                 color=GREY, align=PP_ALIGN.CENTER)
    detail_top = top + 4.9
    render_vert_fill(slide, details, left=left, top=detail_top, width=width, bottom=bottom)


def render_summary_split(slide, items, left_count=2, left=2.2, top=4.8, width=29.5, bottom=17.7):
    """总结与展望两栏：左结论、右下一步，用色条/编号区分。"""
    left_items = items[:left_count]
    right_items = items[left_count:]
    col_w = (width - 2.2) / 2
    # 左栏
    lx = left
    add_rect(slide, lx, top, col_w, 0.55, fill=ACCENT)
    add_text(slide, "结  论", lx+0.3, top+0.02, 6, 0.5, size=15, bold=True,
             color=RGBColor(0xFF,0xFF,0xFF))
    ly = top + 1.0
    for i, item in enumerate(left_items):
        head, body = split_head_body(item)
        add_text(slide, f"0{i+1}", lx, ly, 1.6, 1.0, size=18, bold=True, color=ACCENT, wrap=False)
        tx = lx + 1.4
        add_text(slide, head, tx, ly+0.02, col_w-1.6, 0.6, size=16, bold=True, color=PRIMARY)
        add_text(slide, body, tx, ly+0.62, col_w-1.6, 4.4, size=13, color=GREY)
        ly += 5.6
    # 右栏
    rx = left + col_w + 1.2
    add_rect(slide, rx, top, col_w, 0.55, fill=PRIMARY)
    add_text(slide, "下一步", rx+0.3, top+0.02, 6, 0.5, size=15, bold=True,
             color=RGBColor(0xFF,0xFF,0xFF))
    ry = top + 1.0
    for i, item in enumerate(right_items):
        head, body = split_head_body(item)
        add_text(slide, f"0{i+1}", rx, ry, 1.6, 1.0, size=18, bold=True, color=PRIMARY, wrap=False)
        tx = rx + 1.4
        add_text(slide, head, tx, ry+0.02, col_w-1.6, 0.6, size=15, bold=True, color=ACCENT)
        add_text(slide, body, tx, ry+0.62, col_w-1.6, 3.4, size=12.5, color=GREY)
        ry += 3.2
    # 中间箭头装饰
    add_text(slide, "→", left + col_w + 1.0, top + 0.12, 1.0, 0.8, size=18,
             bold=True, color=ACCENT, wrap=False)


def add_code_rich(slide, code, left, top, width, height, size=11):
    """彩色伪代码块（右侧区域）。"""
    add_rect(slide, left, top, width, 0.7, fill=PRIMARY)
    add_text(slide, "代码 / 伪代码", left+0.5, top+0.08, 10, 0.55, size=13, bold=True,
             color=RGBColor(0xFF,0xFF,0xFF))
    add_rect(slide, left, top+0.7, width, height-0.7, fill=LIGHT, line=LINE)
    tb = slide.shapes.add_textbox(Cm(left+0.5), Cm(top+0.95), Cm(width-1.0), Cm(height-1.2))
    tf = tb.text_frame
    tf.word_wrap = False
    first = True
    for line in code.split("\n"):
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(2)
        for tok, kind in tokenize_line(line):
            r = p.add_run(); r.text = tok
            r.font.name = "Consolas"; r.font.size = Pt(size)
            if kind == "comment":
                r.font.color.rgb = C_COMMENT
            elif kind == "str":
                r.font.color.rgb = C_STR
            elif kind == "kw":
                r.font.color.rgb = C_KW; r.font.bold = True
            elif kind == "func":
                r.font.color.rgb = C_FUNC; r.font.bold = True
            elif kind == "num":
                r.font.color.rgb = C_NUM
            else:
                r.font.color.rgb = C_DEF

def render_code_split(slide, p):
    """代码页左右分栏：左说明占竖向，右彩色伪代码占竖向。"""
    items = p["items"][:4]
    render_vert_fill(slide, items, left=2.2, top=4.6, width=12.2, bottom=17.6)
    add_code_rich(slide, p["code"], left=15.4, top=4.6, width=16.7, height=13.0, size=11)


def add_code_block(slide, code, left=2.0, top=8.4, width=29.8, height=8.4):
    add_rect(slide, left, top, width, 0.7, fill=PRIMARY)
    add_text(slide, "代码 / 伪代码", left+0.5, top+0.08, 8, 0.55, size=13, bold=True,
             color=RGBColor(0xFF,0xFF,0xFF))
    add_rect(slide, left, top+0.7, width, height-0.7, fill=LIGHT, line=LINE)
    add_text(slide, code, left+0.6, top+0.95, width-1.2, height-1.4,
             size=11, color=PRIMARY, mono=True)

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
            elif layout == "vert_fill":
                render_vert_fill(slide, items)
            elif layout == "icon_rows":
                render_icon_rows(slide, items, icons=p.get("icons"))
            elif layout == "mapping_rows":
                render_mapping_rows(slide, items, icons=p.get("icons"))
            elif layout == "stats_plus":
                render_stats_plus(slide, items)
            elif layout == "summary_split":
                render_summary_split(slide, items, left_count=p.get("left_count", 2))
            elif p.get("image"):
                content_items = [x for x in items if x and not x.startswith("配图占位")]
                render_vert_fill(slide, content_items, left=2.2, top=4.6, width=16.8, bottom=17.6)
                add_image_box(slide, 21.2, 4.6, 10.9, 12.9, p.get("image"))
            else:
                render_cards(slide, items, left=2.0, top=4.6, width=29.8, height=2.1, gap=0.22)
        elif t == "code":
            add_header(slide, p.get("tag"), p["title"])
            render_code_split(slide, p)
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

    try:
        prs.save(PPTX)
        saved = PPTX
    except PermissionError:
        saved = os.path.join(OUT_DIR, "最终汇报成果_new.pptx")
        prs.save(saved)
        print(f"[警告] {PPTX} 被占用，已生成替代文件：{saved}")
    print(f"[OK] {saved} 已生成，共 {TOTAL} 页")

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