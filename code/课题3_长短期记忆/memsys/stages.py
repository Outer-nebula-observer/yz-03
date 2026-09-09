# -*- coding: utf-8 -*-
"""
memsys.stages — 规划阶段感知（Stage-Aware Memory，本轮升级）
=============================================================
背景（老师指导意见的落地）：
  此前"goal 文本 → 生成查询"的检索，任务陈述本身索引出的记忆意义有限——
  真正的记忆需求由**规划进行到哪个阶段**决定：
    任务分析时要情报事实，方案拟制时要相似战例，推演时要对抗教训……
  → 查询列表（创新点 C）从"开场一次性生成"升级为"**按规划阶段滚动生成**"。

七阶段口径（老师提的"制定战法七阶段"）：采用 **MDMP 七步**
（Military Decision-Making Process，ADP 5-0），我军作战筹划习惯表述对照见下表。

论文映射：
  - MIRIX 按查询类型路由 → 扩展为"按规划阶段路由"；
  - Synapse trajectory-as-exemplar → 方案拟制阶段注入相似战例（CBR）；
  - ExpeL/Reflexion 经验抽取 → 复盘教训带**阶段归因**（下场同阶段优先召回）；
  - 认知科学事件分段理论（Event Segmentation Theory, Zacks & Swallow 2007）：
    人天然把连续活动切成离散阶段来理解与记忆——阶段化记忆的理论根基。

实现约定（与 boundary.CONTENT_RULES 同款"表即文档"）：
  - 模板生成查询 = MVP 确定性实现（可测试可复现）；
    接真模型后换 LLM 按阶段提示词生成（接口不变，同 G2 门控的升级路径）。
"""

from __future__ import annotations

from typing import List, Optional

from .schema import QueryItem


# ---------------------------------------------------------------- 七阶段定义
MDMP_STAGES = [
    {"id": "mission_receipt",   "n": 1, "name": "受领任务",
     "en": "Receipt of Mission", "output": "任务理解 / 初步指示",
     "knows": "既往同型任务的教训（开场先看历史上吃过什么亏）"},
    {"id": "mission_analysis",  "n": 2, "name": "任务分析",
     "en": "Mission Analysis", "output": "敌情/地形/装备判断",
     "knows": "情报事实：目标区地形、敌我装备参数（IPB 式情报准备）"},
    {"id": "coa_development",   "n": 3, "name": "方案拟制",
     "en": "COA Development", "output": "2–3 个候选行动方案",
     "knows": "相似战例与可复用对策（CBR：跟着打赢过的仗学）"},
    {"id": "coa_analysis",      "n": 4, "name": "方案推演",
     "en": "COA Analysis (Wargaming)", "output": "各方案兵棋推演结论",
     "knows": "对抗/推演历史教训（伏击、暴露、通信干扰等）"},
    {"id": "coa_comparison",    "n": 5, "name": "方案比较",
     "en": "COA Comparison", "output": "方案优劣对比矩阵",
     "knows": "评估维度经验（代价/风险/战果怎么权衡）"},
    {"id": "coa_approval",      "n": 6, "name": "定下决心",
     "en": "COA Approval", "output": "选定最优方案报批",
     "knows": "决断类历史教训（犹豫误机、当机立断的先例）"},
    {"id": "orders_production", "n": 7, "name": "命令拟制",
     "en": "Orders Production", "output": "作战命令 / 计划文书",
     "knows": "条令条款与协同格式事实（命令要合规范）"},
]

STAGE_IDS = [s["id"] for s in MDMP_STAGES]
STAGE_NAMES = {s["id"]: f'{s["n"]} {s["name"]}' for s in MDMP_STAGES}


def get_stage(stage_id: str) -> Optional[dict]:
    return next((s for s in MDMP_STAGES if s["id"] == stage_id), None)


# ---------------------------------------------------------------- 阶段知识模板
# 每个阶段"需要什么记忆"→ 生成结构化查询（{goal} 占位，检索按 target/route 走）
STAGE_TEMPLATES = {
    "mission_receipt": [
        ("召回同型任务历史教训", "experience", "vector",
         "{goal} 同型任务 历史教训"),
    ],
    "mission_analysis": [
        ("查目标区域地形与通行", "fact", "vector",
         "{goal} 目标区域 地形 通行 道路"),
        # 【评审修复】原为 sql 路 + 纯文本查询——LIKE 子串永远无法命中
        # 多词查询（实测恒空）。装备参数的**精确**查询应走 attrs
        # （sql 路），但 attrs 需要意图解析（"T-90"→{"装备":"T-90"}，
        # 留待真模型）；模板层先用 vector 做语义召回，精确路由由
        # orders_production 的 attrs 查询与测试集 sql 用例覆盖。
        ("查敌我装备参数", "fact", "vector",
         "{goal} 装备 参数 速度 装甲 火力"),
    ],
    "coa_development": [
        ("召回相似战例与对策", "experience", "vector",
         "{goal} 相似战例 战法 对策"),
        ("查同类战法教训（字面）", "experience", "bm25",
         "{goal} 战法 突破 佯动 教训"),
    ],
    "coa_analysis": [
        ("召回对抗推演历史教训", "experience", "bm25",
         "{goal} 伏击 遭袭 干扰 暴露 教训"),
    ],
    "coa_comparison": [
        ("召回方案评估经验", "experience", "vector",
         "{goal} 方案评估 代价 风险 权衡"),
    ],
    "coa_approval": [
        ("召回决断类历史教训", "experience", "bm25",
         "{goal} 决心 决断 犹豫 误机 教训"),
    ],
    "orders_production": [
        # 【评审修复】sql 路现在支持 attrs 精确过滤——条令类事实按
        # {"类别": "条令"} 属性精确召回（参数级，ChatDB 符号查询落地）
        ("查条令与协同格式（精确）", "fact", "sql",
         "条令 协同 命令 格式", {"类别": "条令"}),
    ],
}


def queries_for_stage(stage_id: str, goal: str = "") -> List[QueryItem]:
    """按阶段模板生成查询列表（MVP：确定性模板；真模型后换 LLM 生成）。

    查询带 stage 字段——检索层据此做"阶段亲和加分"（hybrid.py）。
    """
    templates = STAGE_TEMPLATES.get(stage_id, [])
    items: List[QueryItem] = []
    for i, spec in enumerate(templates):
        intent, target, route, text = spec[0], spec[1], spec[2], spec[3]
        attrs = spec[4] if len(spec) > 4 else None  # 5 元组带属性过滤条件
        items.append(QueryItem(
            q_id=f"{stage_id}-q{i+1}", intent=intent, target=target,
            route=route, query_text=text.format(goal=goal),
            attrs=attrs, stage=stage_id))
    return items


# ---------------------------------------------------------------- 复盘教训阶段归因
# 教训文本关键词 → 所属规划阶段（MVP 关键词模板；真模型换 LLM 归因，接口不变）
# 归因后的 stage 标签写入 metadata.stage，下场**同阶段**检索时被亲和加分。
STAGE_ATTR_KEYWORDS = {
    "mission_analysis": ("情报", "侦察", "敌情", "地形", "漏判", "没有查",
                         "气象", "水文", "装备参数", "不明"),
    "coa_development": ("战法", "方案", "打法", "突破口", "主攻", "佯动",
                        "部署", "编成", "梯队", "炮火准备", "火力准备"),
    "coa_analysis": ("推演", "伏击", "交火", "遇袭", "对抗", "遭",
                     "暴露", "压制", "干扰", "迟到", "超时"),
    "coa_comparison": ("评估", "比较", "优选", "对比", "代价", "权衡"),
    "coa_approval": ("决心", "决断", "犹豫", "误机", "报批"),
    "orders_production": ("命令", "协同", "通报", "文书", "格式", "电台"),
}


def attr_stage(content: str) -> str:
    """把一条复盘教训归因到规划阶段（用于 metadata.stage 标签）。

    无命中 → 返回 "coa_analysis"（默认归到推演阶段——多数战场教训
    在推演/执行中暴露；宁可给默认值也不留空，保证下场阶段检索有亲和可用）。
    """
    for stage_id, kws in STAGE_ATTR_KEYWORDS.items():
        if any(k in content for k in kws):
            return stage_id
    return "coa_analysis"
