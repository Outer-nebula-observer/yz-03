# -*- coding: utf-8 -*-
"""
eval.task_metrics — 任务层（规划输出质量）指标
================================================
为什么需要"任务层"指标？（评审 §1.4）

  赛题③的验收主张不是"检索召回了记忆"，而是"**检索增强作战规划**"。
  旧消融只有检索层指标（hit/recall/mrr/ndcg）——只能证明"记忆被
  找出"，证明不了"规划变好"。任务层指标回答后一个问题。

三个可自动判分的指标（中文适用、零依赖）：
  constraint_satisfaction  约束满足率：每条作战约束的判别性词是否出现在
                           规划输出里（G0 无记忆 vs G3 的核心对照之一）。
  memory_citation_rate     记忆引用率：装载进上下文的记忆，其核心内容
                           片段是否出现在规划输出里（记忆被 LLM"用上"
                           的比率）。依赖装载记忆真正进入上下文——
                           v0.3 的 render【装载记忆】修复使它可度量。
  noise_pollution_rate     噪声污染率：负例查询命中的无关记忆被装载后，
                           其内容片段出现在输出里的比率（越低越好）。

【诚实边界】MockLLM 是回显式输出：这些指标在 Mock 下度量的是
"上下文构造是否正确"（记忆确实进入了提示词），而非"LLM 是否善用
记忆"。换真模型（GLM）后同一脚本即测"LLM 善用记忆"——T6 验证已见
宽松引用率 1.00（规划输出真的引用了"仅东侧可装甲通行""先遣侦察教训"）。
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

from memsys import WorkingMemory


def _key_terms(constraint: str) -> List[str]:
    """从约束文本提取判别性词（去停用前缀，取 2 字以上核心片段）。

    例子：
      "禁止越境"        → ["越境"]
      "限时 4 小时"      → ["4小时", "限时 4 小时"]   # 数字单位优先
      "优先保存装甲力量" → ["保存装甲力量"]

    为什么剥离前缀？约束里的"禁止/必须/优先"等词对"是否遵守"没有
    判别力——"禁止越境"的输出如果含"禁止"但没谈越境，不算遵守。
    """
    c = constraint.strip()
    for prefix in ("禁止", "严禁", "不得", "必须", "优先", "应当", "需要"):
        if c.startswith(prefix):
            c = c[len(prefix):]
            break
    c = c.strip()
    # 数字+单位短语（如 "4 小时"、"50 米"）先作为强判别项
    m = re.search(r"\d+\s*[^\s，。；]{1,4}", c)
    terms = []
    if m:
        terms.append(re.sub(r"\s+", "", m.group(0)))
    if len(c) >= 2:
        terms.append(c)              # 完整剩余约束作为次判别项
    return terms or [constraint]


def constraint_satisfaction(output: str, constraints: Sequence[str]) -> float:
    """约束满足率 ∈ [0,1]：判别词命中的约束占比。

    例：output 含"越境"且含"4小时" → 满足 2/3 = 0.667。
    G0（无记忆）在 Mock 回显下若不含约束词则 0；G3 含约束则 1——
    用同一脚本可在真模型下度量"LLM 是否真的遵守约束"。
    """
    if not constraints:
        return 1.0                   # 无约束可答"全部满足"（空真）
    hit = 0
    for c in constraints:
        if any(t in output for t in _key_terms(c)):
            hit += 1
    return hit / len(constraints)


def _content_probe(content: str) -> str:
    """取记忆正文的核心探针片段（去'教训：/经验：'前缀后的前 6 字）。

    为什么用"前 6 字"：记忆内容最核心的信息通常在开头（如
    "夜间行军未派先遣侦察…" → 探针 "夜间行军未派"）。严格口径以此
    探针是否出现在输出中判断"这条记忆被引用"。
    注意：真模型可能改写（"应当先派"而非"未派"）→ 严格口径会漏报，
    因此真模型验证里还用了宽松口径（任意 2 字 CJK 片段匹配）。
    """
    body = re.sub(r"^(教训|经验|事实|条令)[:：]", "", content.strip())
    probe = re.sub(r"\s+", "", body)[:6]
    return probe


def memory_citation_rate(output: str,
                         loaded_briefs) -> float:
    """记忆引用率：装载记忆的核心片段出现在输出中的比例。

    loaded_briefs: dict(id→brief) 或 brief 文本列表（噪声污染等场景）。
    brief 格式来自 controller.retrieve_and_load：
      "[fact] 2 号高地海拔 320 米…（来源:seed）"
    本函数用正则抽 content 段（介于 [type] 与 （来源: 之间）再取探针。

    使用场景：
      - G0/G1（无装载）→ 0；
      - G2/G3（有装载）→ Mock 下 >0（上下文构造正确）；
      - 真模型 T6 → 度量"LLM 是否真的引用了记忆内容"。
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
    """噪声污染率：负例查询带入的无关记忆出现在输出中的比例（越低越好）。

    意义：检索层把无关记忆滤在 min_score 之外还不够——如果漏进一条并
    被 LLM 写进规划，就是**实际污染**。这个指标把"滤噪"从检索层
    下沉到任务层验证。
    """
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
    """一次规划输出的任务层指标汇总（消融/验证脚本的统一入口）。"""
    briefs = wm.slot.loaded_briefs if wm is not None else {}
    return {
        "constraint_sat": round(constraint_satisfaction(output, constraints), 4),
        "memory_citation": round(memory_citation_rate(output, briefs), 4),
    }
