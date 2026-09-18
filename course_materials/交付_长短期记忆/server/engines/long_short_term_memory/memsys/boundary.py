# -*- coding: utf-8 -*-
"""
memsys.boundary — 长短期记忆的边界与内容限定
================================================
对应 `docs/04` 避坑点 2（"短期与长期边界要清晰：来源+时间尺度两把尺子"）
与 `docs/05` 技术路线汇报 §2.1/2.2 的边界表述——本模块把"口头约定"
变成**代码强制**。

一、两把尺子（判定基准，来自 docs/03 第 18.1 节）：
  尺子A 来源（SOURCE）：任务内产生 vs 跨任务产生
  尺子B 时间尺度（TIME）：当前场次生命周期 vs 持久沉淀

二、边界矩阵（什么内容能进哪个记忆层）：
  ┌─────────────────────────────────────────────────────┐
  │ 内容类别          │ 归属层    │ 依据                   │
  ├───────────────────┼──────────┼────────────────────────┤
  │ 本场次目标/约束    │ 短期 only │ 任务内 + 场次生命周期    │
  │ 本场次消息/中间结果│ 短期 only │ 任务内 + 场次生命周期    │
  │ 装备参数/条令/地形 │ 长期·事实 │ 跨任务 + 持久           │
  │ 战例客观经过       │ 长期·事实 │ 跨任务 + 持久           │
  │ 成败教训/可复用对策│ 长期·经验 │ 跨任务 + 持久           │
  └─────────────────────────────────────────────────────┘

三、双向禁止（这是"限定"的强制力）：
  ① 短期 → 长期：工作记忆里的内容**不能直接**变成长期记忆——必须经过
     `promote()` 门控（复盘驱动 + 满足晋升条件），否则场次闲聊会污染
     长期库（docs/04 避坑点 6"知识锚定约束长期记忆"的落地）。
  ② 长期 → 短期：长期记忆**只能以检索结果形态**进入工作记忆
     （retrieve → load_memory 登记），禁止把长期库整段拷进 FIFO——
     保证"检索只读、进化只写"的解耦不被绕过。

四、晋升门控（promotion gate）——短期内容升级为长期的唯一通道：
  条件（全部满足才放行）：
    G1 复盘驱动：只在场次结束（close_session）的复盘材料中出现（非场中随时写）；
    G2 内容类型合法：命中"事实/经验"关键词模板（参数/条令/教训/对策…）；
    G3 重复检查：通过 evolution.write 的 PREMem θ 查重（不重复入库）。
  每次晋升/拒绝都记录 reason——**边界决策可解释、可审计**。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .schema import MemoryType, QueryItem


# ---------------------------------------------------------------- 边界判定基准
class Scope(str, Enum):
    """两把尺子的取值。"""

    WITHIN_TASK = "within_task"    # 任务内（尺子A：来源）
    CROSS_TASK = "cross_task"      # 跨任务（尺子A：来源）
    SESSION_LIFETIME = "session"   # 场次生命周期（尺子B：时间）
    PERSISTENT = "persistent"      # 持久沉淀（尺子B：时间）


# 内容类别 → (归属记忆层, 尺子A, 尺子B) 的判定表
# 【为什么用表而不用 if-else】表即文档：新增内容类别加一行，
# 边界规则一目了然，答辩可直接展示这张表。
CONTENT_RULES = {
    "goal":        ("short_term", Scope.WITHIN_TASK, Scope.SESSION_LIFETIME,
                    "本场规划目标"),
    "constraint":  ("short_term", Scope.WITHIN_TASK, Scope.SESSION_LIFETIME,
                    "本场作战约束"),
    "message":     ("short_term", Scope.WITHIN_TASK, Scope.SESSION_LIFETIME,
                    "场次消息/中间结果"),
    "fact_param":  ("long_term.fact", Scope.CROSS_TASK, Scope.PERSISTENT,
                    "装备参数/条令条款（跨场次稳定）"),
    "fact_event":  ("long_term.fact", Scope.CROSS_TASK, Scope.PERSISTENT,
                    "战例客观经过"),
    "experience":  ("long_term.experience", Scope.CROSS_TASK, Scope.PERSISTENT,
                    "成败教训/可复用对策"),
}


@dataclass
class BoundaryDecision:
    """一次边界判定的结论（可解释、可审计）。"""

    allowed: bool                       # 是否放行
    layer: str                          # 目标层：short_term / long_term.fact / long_term.experience
    reason: str                         # 判定理由（日志/答辩展示用）
    content_kind: str = ""              # 命中的内容类别
    scope_source: str = ""              # 尺子A 判定
    scope_time: str = ""                # 尺子B 判定
    at: float = field(default_factory=time.time)


class MemoryBoundary:
    """长短期记忆边界管理器。

    用法（controller/evolution 在关键写入点调用）：
        boundary = MemoryBoundary()

        # ① 场中写入短期（消息/中间结果）——总是放行（短期就是任务内的）
        d = boundary.check_write("message", to="short_term")
        # → allowed=True, reason="任务内+场次生命周期 → 短期"

        # ② 场中有人想把工作记忆内容直接写长期 —— 拒绝（必须走复盘晋升）
        d = boundary.check_write("message", to="long_term.fact")
        # → allowed=False, reason="场中直写长期被禁止：须走 promote() 复盘晋升"

        # ③ 复盘晋升（close_session 时唯一合法通道）
        d = boundary.promote("教训：夜战需前置电子压制")
        # → allowed=True, layer="long_term.experience"
    """

    # 晋升门控 G2：内容类型关键词模板（Mock 版；真模型换 LLM 分类，接口不变）
    PROMOTION_PATTERNS = {
        MemoryType.FACT: ("参数", "条令", "海拔", "编制", "性能", "射程", "速度",
                          "态势", "部署"),
        MemoryType.EXPERIENCE: ("教训", "经验", "对策", "失败", "成功",
                                "复盘", "下次", "应当", "避免"),
    }

    def __init__(self) -> None:
        self.decisions: List[BoundaryDecision] = []   # 决策日志（审计/答辩）

    # ------------------------------------------------------------ 判定入口
    def classify(self, content: str) -> tuple:
        """判定一段内容的类别（尺子A/B 由类别表带出）。

        Mock 版：关键词模板匹配；接真模型后换 LLM 分类（接口不变）。
        """
        for mtype, kws in self.PROMOTION_PATTERNS.items():
            if any(k in content for k in kws):
                kind = ("fact_param" if "参数" in content or "条令" in content
                        or "海拔" in content or "射程" in content or "速度" in content
                        else "fact_event") if mtype == MemoryType.FACT else "experience"
                return kind, mtype
        return "message", None     # 无命中 → 场次内容（留在短期）

    def check_write(self, content_kind: str, to: str) -> BoundaryDecision:
        """写入前的边界检查（双向禁止的执行点）。"""
        rule = CONTENT_RULES.get(content_kind)
        if rule is None:
            d = BoundaryDecision(False, to, f"未知内容类别: {content_kind}")
            self.decisions.append(d)
            return d
        layer, src_scope, time_scope, desc = rule

        if to == layer:
            d = BoundaryDecision(True, to,
                                 f"{desc}：{src_scope.value}+{time_scope.value} → {to}",
                                 content_kind, src_scope.value, time_scope.value)
        elif to.startswith("long_term"):
            # 双向禁止①：场中内容直写长期
            d = BoundaryDecision(
                False, to,
                f"边界拒绝：{desc} 属 {layer}，场中直写 {to} 被禁止"
                f"（须走 promote() 复盘晋升通道）",
                content_kind, src_scope.value, time_scope.value)
        else:
            d = BoundaryDecision(False, to,
                                 f"边界拒绝：{desc} 应写入 {layer} 而非 {to}",
                                 content_kind, src_scope.value, time_scope.value)
        self.decisions.append(d)
        return d

    # ------------------------------------------------------------ 晋升门控
    def promote(self, content: str) -> BoundaryDecision:
        """短期 → 长期 的唯一合法通道（复盘驱动，G1-G3 门控）。

        调用时机：仅 close_session 的复盘材料经 evolution 抽取后，
        每条候选写入长期库之前（evolve_from_review 内部调用）。
        """
        # G2 内容类型门控：先分类，非法类别（纯场次内容）拒绝
        kind, mtype = self.classify(content)
        if mtype is None:
            d = BoundaryDecision(False, "long_term",
                                 f"晋升拒绝（G2）：内容未命中事实/经验模板，"
                                 f"判为场次内容留在短期（含归档，不丢失）",
                                 content_kind="message")
            self.decisions.append(d)
            return d

        # 通过门控 → 返回目标层（G3 θ 查重由 evolution.write 负责，此处不管）
        layer = "long_term.fact" if mtype == MemoryType.FACT else "long_term.experience"
        rule = CONTENT_RULES[kind]
        d = BoundaryDecision(
            True, layer,
            f"晋升放行（G1 复盘驱动 + G2 类别[{rule[3]}]）："
            f"{rule[1].value}+{rule[2].value} → {layer}",
            content_kind=kind, scope_source=rule[1].value, scope_time=rule[2].value)
        self.decisions.append(d)
        return d

    # ------------------------------------------------------------ 审计
    def audit_log(self) -> List[dict]:
        """决策日志（答辩展示"边界如何被强制执行"）。"""
        return [{"allowed": d.allowed, "layer": d.layer, "reason": d.reason,
                 "kind": d.content_kind, "at": d.at} for d in self.decisions]

    def stats(self) -> dict:
        """放行/拒绝计数（评估口径：边界模块的工作量证明）。"""
        allowed = sum(1 for d in self.decisions if d.allowed)
        return {"allowed": allowed, "rejected": len(self.decisions) - allowed,
                "total": len(self.decisions)}


# ---------------------------------------------------------------- 长期→短期 的装载约束
def validate_load(retrieved_ids: List[str], loaded_via: str = "retrieve") -> bool:
    """双向禁止②：长期记忆进短期的形态校验。

    合法形态：检索结果逐条 load_memory 登记（via="retrieve"）；
    非法形态：把长期库内容整段塞 FIFO（via="fifo"）——绕过检索层。
    """
    if via_legal := (loaded_via == "retrieve"):
        return True
    return False
