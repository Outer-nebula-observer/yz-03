# -*- coding: utf-8 -*-
"""
eval.task_metrics — 任务层（规划输出质量）指标
================================================
评审 §1.4 的落地：旧消融只有检索层指标（hit/recall/mrr/ndcg），而赛题③
的验收主张是"检索内容**增强作战规划**"——这条主张必须有任务层证据。

三个可自动判分的指标（零依赖、中文适用）：
  constraint_satisfaction  约束满足率：每条作战约束的判别性词是否出现在
                           规划输出里（"禁止越境"→查"越境"；"限时 4 小时"
                           →查"4 小时"）。G0 无记忆基线 vs G3 的核心对照。
  memory_citation_rate     记忆引用率：装载进上下文的记忆，其核心内容
                           片段是否出现在规划输出里（被 LLM"用上"的比率）。
                           依赖"装载记忆真正进入上下文"——评审修复的关键
                           缺陷（此前 render 不含记忆正文，此指标恒 0）。
  noise_pollution_rate     噪声污染率：负例查询命中的无关记忆被装载后，
                           其内容片段出现在输出里的比率（越低越好）。

【诚实边界】MockLLM 是回显式输出：这些指标在 Mock 下度量的是"上下文
构造是否正确"（记忆确实进入了提示词），而非"LLM 是否善用记忆"。
换真模型后同一脚本即测后者——口径不变，含义升级。
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

from memsys import WorkingMemory


def _key_terms(constraint: str) -> List[str]:
    """从约束文本提取判别性词（去停用前缀，取 2 字以上核心片段）。

    "禁止越境" → ["越境"]；"限时 4 小时" → ["4 小时"]；
    "优先保存装甲力量" → ["保存装甲力量"]。
    """
    c = constraint.strip()
    for prefix in ("禁止", "严禁", "不得", "必须", "优先", "应当", "需要"):
        if c.startswith(prefix):
            c = c[len(prefix):]
            break
    c = c.strip()
    # 抽出数字+单位短语（如 "4 小时"、"50 米"）优先
    m = re.search(r"\d+\s*[^\s，。；]{1,4}", c)
    terms = []
    if m:
        terms.append(re.sub(r"\s+", "", m.group(0)))
    if len(c) >= 2:
        terms.append(c)
    return terms or [constraint]


def constraint_satisfaction(output: str, constraints: Sequence[str]) -> float:
    """约束满足率 ∈ [0,1]：判别词命中的约束占比。"""
    if not constraints:
        return 1.0
    hit = 0
    for c in constraints:
        if any(t in output for t in _key_terms(c)):
            hit += 1
    return hit / len(constraints)


def _content_probe(content: str) -> str:
    """取记忆正文的核心探针片段（去掉"教训：/经验："前缀后的前 6 字），
    用于判断该记忆内容是否出现在规划输出中。"""
    body = re.sub(r"^(教训|经验|事实|条令)[:：]", "", content.strip())
    probe = re.sub(r"\s+", "", body)[:6]
    return probe


def memory_citation_rate(output: str,
                         loaded_briefs) -> float:
    """记忆引用率：装载记忆的核心片段出现在输出中的比例。

    loaded_briefs: dict(id→brief) 或 brief 文本列表（噪声污染等场景）。
    """
    if not loaded_briefs:
        return 0.0
    if isinstance(loaded_briefs, dict):
        briefs = list(loaded_briefs.values())
    else:
        briefs = list(loaded_briefs)
    # briefs 存的是 "[type] content（来源:xx）"，取 content 段做探针
    cited = 0
    for brief in briefs:
        m = re.match(r"\[(fact|experience)\]\s*(.*?)（来源:", brief)
        content = m.group(2) if m else brief
        if _content_probe(content) and _content_probe(content) in output:
            cited += 1
    return cited / len(loaded_briefs)


def noise_pollution_rate(output: str,
                         noise_briefs: Sequence[str]) -> float:
    """噪声污染率：负例查询带入的无关记忆出现在输出中的比例（越低越好）。"""
    if not noise_briefs:
        return 0.0
    polluted = 0
    for brief in noise_briefs:
        m = re.match(r"\[(fact|experience)\]\s*(.*?)（来源:", brief)
        content = m.group(2) if m else brief
        if _content_probe(content) and _content_probe(content) in output:
            polluted += 1
    return polluted / len(noise_briefs)


def evaluate_task(output: str, constraints: Sequence[str],
                  wm: "WorkingMemory | None") -> Dict[str, float]:
    """一次规划输出的任务层指标汇总。"""
    briefs = wm.slot.loaded_briefs if wm is not None else {}
    return {
        "constraint_sat": round(constraint_satisfaction(output, constraints), 4),
        "memory_citation": round(memory_citation_rate(output, briefs), 4),
    }
