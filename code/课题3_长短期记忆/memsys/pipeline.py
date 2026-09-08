# -*- coding: utf-8 -*-
"""
memsys.pipeline — 七步闭环编排（赛题③主流程演示）
==================================================
对应 docs/04 第 3 节"编排闭环"：
  ①规划 → ②查询列表 → ③检索 → ④长期/短期装载 → ⑤规划输出
  → ⑥AFSIM 反馈 → ⑦记忆进化

本文件把 controller 的原子操作串成**可演示的端到端流程**，
并用 MockLLM 模拟"规划输出"与"AFSIM 推演反馈"——离线跑通全链路。

接智戎链路时：把 ⑤⑥ 两步换成真实管线调用（见 examples/demo_pipeline.py
里的注释标记 TODO-INTEGRATION）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .schema import QueryItem, RetrievedMemory
from .llm import LLMClient
from .controller import MemoryController
from .evolution.memory_evolution import EvolutionReport


@dataclass
class SessionResult:
    """一场完整七步闭环的产物（评估/日志/消融统计的输入）。"""

    plan_id: str
    context_tokens: int = 0                     # ⑤ 注入 LLM 的上下文规模
    retrieved: List[Dict[str, Any]] = field(default_factory=list)  # ③ 检索命中
    plan_output: str = ""                       # ⑤ 规划输出
    feedback: str = ""                          # ⑥ AFSIM 反馈
    evolution: Optional[EvolutionReport] = None # ⑦ 进化报告
    session_stats: Dict[str, int] = field(default_factory=dict)


class MemoryPipeline:
    """七步闭环编排器。内部持有一个 controller；每次 run_session 跑一场。"""

    def __init__(self, controller: Optional[MemoryController] = None,
                 llm: Optional[LLMClient] = None) -> None:
        self.controller = controller or MemoryController(llm=llm)
        self.llm = llm or self.controller.llm

    # ---------------------------------------------------------------- 单场闭环
    def run_session(self, plan_id: str, goal: str,
                    constraints: Optional[List[str]] = None,
                    queries: Optional[List[QueryItem]] = None,
                    messages: Optional[List[str]] = None,
                    review_text: str = "",
                    top_k: int = 3) -> SessionResult:
        """跑完整七步闭环（离线演示用；接智戎后 ⑤⑥ 换真调用）。

        参数：
            plan_id:     场次 id
            goal:        规划目标
            constraints: 作战约束（不可压缩）
            queries:     查询列表（②；None 则由 goal 自动生成两条示例查询）
            messages:    场次中的消息流（模拟规划管线各步的输入输出）
            review_text: 复盘文本（⑦ 进化的原材料）
        """
        result = SessionResult(plan_id=plan_id)

        # ① 规划：开场（建槽位、设目标约束）
        # ② 查询列表：无外部提供时，按 goal 生成默认两问（事实+经验各一）
        if not queries:
            queries = [
                QueryItem(q_id=f"{plan_id}-q1", intent="查相关装备/环境事实",
                          target="fact", route="vector", query_text=goal),
                QueryItem(q_id=f"{plan_id}-q2", intent="召回相似历史经验教训",
                          target="experience", route="vector", query_text=goal),
            ]
        self.controller.start_session(plan_id, goal, constraints, queries)

        # ③ 检索 + ④ 装载（controller 内部处理 memory_pressure 压缩）
        hits: List[RetrievedMemory] = self.controller.retrieve_and_load(top_k=top_k)
        result.retrieved = [
            {"id": h.entry.id, "type": h.entry.type.value, "score": round(h.score, 4),
             "route": h.route, "content": h.entry.content[:80],
             "provenance": h.entry.provenance()}  # 创新点 E：溯源随行
            for h in hits
        ]

        # 场次消息流（模拟管线运行过程中的信息进出）
        for msg in (messages or []):
            self.controller.push(msg)
        self.controller.record("检索装载", {"n": len(hits)})

        # ⑤ 规划输出（TODO-INTEGRATION: 换智戎规划管线真实调用）
        context = self.controller.render_context()
        result.context_tokens = count_tokens(context)
        result.plan_output = self.llm.chat(
            "你是作战规划智能体。基于以下记忆上下文生成规划方案（要点式）。",
            context)

        # ⑥ AFSIM 反馈（TODO-INTEGRATION: 换 AFSIM 推演结果 + 评估）
        # Mock：模拟一场"部分成功"的推演，产出带教训的复盘文本
        result.feedback = (
            "推演结果：任务部分达成。\n"
            "教训：先遣侦察不足导致遭遇伏击。\n"
            "经验：炮火准备阶段前置 20 分钟可显著压制敌方火力点。"
            if not review_text else review_text
        )

        # ⑦ 记忆进化（复盘驱动：写入/合并/遗忘/抽象）
        result.evolution = self.controller.close_session(result.feedback)
        result.session_stats = dict(self.controller.session_stats)
        return result


def count_tokens(text: str) -> int:
    """简化 token 计数（与 WorkingMemory._count_tokens 口径一致）。"""
    cn = sum(1 for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF)
    words = len([w for w in text.split() if w.isascii()])
    return cn + words
