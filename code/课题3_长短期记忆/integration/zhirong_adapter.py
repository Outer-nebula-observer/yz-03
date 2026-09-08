# -*- coding: utf-8 -*-
"""
integration.zhirong_adapter — 智戎规划链路适配层（验收项"正式系统接入"）
==========================================================================
对应 docs/04 验收底线：
  「集成：在智戎规划链路（或 mock）中完成一处真实调用并记录时延」

设计：把 memsys 七步闭环包装成智戎管线可调用的**三个挂接点**——
  hook_plan()    规划前：①②③④（建槽位→查询列表→检索→装载）→ 返回增强上下文
  hook_feedback() 推演后：⑥（AFSIM 反馈文本化）
  hook_close()   场次末：⑦（复盘进化）→ 返回进化报告

真实接入：智戎管线在这三处各调一行；时延自动记录进 IntegrationLog。
Mock 模式：mock_zhirong_session() 完整模拟一场，供验收演示与回归测试。

时延口径（docs/04 5.1 节 Δt）：每个挂接点记录 wall-clock 毫秒；
IntegrationLog.to_dict() 直接作为验收记录（JSON 可归档）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import os as _os
import sys as _sys
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:          # 支持直接 python integration/zhirong_adapter.py
    _sys.path.insert(0, _ROOT)

from memsys import MemoryController, QueryItem
from memsys.evolution.memory_evolution import EvolutionReport


# ---------------------------------------------------------------- 时延记录
@dataclass
class CallRecord:
    """一次挂接点调用的记录（时延 + 结果摘要）。"""

    hook: str            # plan / feedback / close
    elapsed_ms: float    # 耗时（毫秒）
    ok: bool
    detail: str = ""
    at: float = field(default_factory=time.time)


class IntegrationLog:
    """集成验收日志：全部挂接点记录 + 汇总统计。"""

    def __init__(self) -> None:
        self.records: List[CallRecord] = []

    def add(self, rec: CallRecord) -> None:
        self.records.append(rec)

    def summary(self) -> Dict[str, Any]:
        """验收材料：各挂接点平均/最大时延 + 调用数。"""
        by_hook: Dict[str, List[float]] = {}
        for r in self.records:
            by_hook.setdefault(r.hook, []).append(r.elapsed_ms)
        return {
            "total_calls": len(self.records),
            "all_ok": all(r.ok for r in self.records),
            "per_hook": {
                h: {"calls": len(v),
                    "avg_ms": round(sum(v) / len(v), 2),
                    "max_ms": round(max(v), 2)}
                for h, v in by_hook.items()
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return {"summary": self.summary(),
                "records": [vars(r) for r in self.records]}


# ---------------------------------------------------------------- 适配层
class ZhirongAdapter:
    """智戎规划链路 ↔ memsys 的适配器（三个挂接点 + 时延自动记录）。

    用法（真实接入——智戎管线三处各一行）：
        adapter = ZhirongAdapter()                 # 初始化（可注入真模型）
        ctx = adapter.hook_plan(plan_id, goal, constraints)   # 规划前
        adapter.hook_feedback("推演：任务达成…")    # AFSIM 推演后
        report = adapter.hook_close()              # 场次结束（复盘进化）

    mock 演示/回归测试用 mock_zhirong_session()（本文件底部）。
    """

    def __init__(self, controller: Optional[MemoryController] = None,
                 queries_per_session: int = 2) -> None:
        self.ctl = controller or MemoryController()
        self.log = IntegrationLog()
        self.n_queries = queries_per_session
        self._feedback_text: str = ""

    # ------------------------------------------------ ①②③④ 规划前
    def hook_plan(self, plan_id: str, goal: str,
                  constraints: Optional[List[str]] = None,
                  queries: Optional[List[QueryItem]] = None) -> Dict[str, Any]:
        """规划前挂接：建槽位 → 查询列表 → 检索 → 装载 → 返回增强上下文。

        返回 {"context": str, "retrieved": int, "elapsed_ms": float}——
        context 即注入智戎规划 LLM 的记忆增强上下文（⑤ 的输入）。
        """
        t0 = time.perf_counter()
        ok = True
        detail = ""
        try:
            if queries is None:  # 默认查询计划：事实+经验各一（与 pipeline 一致）
                queries = [
                    QueryItem(q_id=f"{plan_id}-q1", intent="查相关事实",
                              target="fact", route="vector", query_text=goal),
                    QueryItem(q_id=f"{plan_id}-q2", intent="召回相似教训",
                              target="experience", route="vector", query_text=goal),
                ][:self.n_queries]
            self.ctl.start_session(plan_id, goal, constraints, queries)
            hits = self.ctl.retrieve_and_load(top_k=3)
            return_val = {
                "context": self.ctl.render_context(),
                "retrieved": len(hits),
            }
        except Exception as exc:  # 挂接点异常不阻断智戎管线（降级为无记忆）
            ok, detail, return_val = False, str(exc), {"context": "", "retrieved": 0}
        elapsed = (time.perf_counter() - t0) * 1000
        self.log.add(CallRecord("plan", elapsed, ok, detail))
        return_val["elapsed_ms"] = round(elapsed, 2)
        return return_val

    # ------------------------------------------------ ⑥ 推演后
    def hook_feedback(self, feedback_text: str) -> Dict[str, Any]:
        """AFSIM 推演后挂接：暂存反馈文本（close 时并入复盘材料）。"""
        t0 = time.perf_counter()
        self._feedback_text = feedback_text
        elapsed = (time.perf_counter() - t0) * 1000
        self.log.add(CallRecord("feedback", elapsed, True, len(feedback_text)))
        return {"ok": True, "elapsed_ms": round(elapsed, 2)}

    # ------------------------------------------------ ⑦ 场次末
    def hook_close(self, extra_review: str = "") -> Dict[str, Any]:
        """场次结束挂接：复盘进化（反馈文本 + 补充复盘 → 四操作）。

        返回 {"report": EvolutionReport.summary(), "elapsed_ms", "boundary"}。
        """
        t0 = time.perf_counter()
        ok, detail = True, ""
        report_summary: Dict[str, Any] = {}
        try:
            material = "\n".join(x for x in (self._feedback_text, extra_review) if x)
            report: EvolutionReport = self.ctl.close_session(material)
            report_summary = report.summary()
        except Exception as exc:
            ok, detail = False, str(exc)
        elapsed = (time.perf_counter() - t0) * 1000
        self.log.add(CallRecord("close", elapsed, ok, detail))
        report_summary["elapsed_ms"] = round(elapsed, 2)
        report_summary["boundary"] = self.ctl.evolution.boundary.stats()
        return report_summary


# ---------------------------------------------------------------- Mock 演示
def mock_zhirong_session(seed: bool = True) -> Dict[str, Any]:
    """模拟智戎一场完整调用（验收演示 + tests 回归用）。

    流程：预置记忆 → hook_plan（增强上下文）→ 模拟规划 →
          hook_feedback（AFSIM 结果）→ hook_close（进化）→ 汇总时延。
    返回 IntegrationLog.to_dict() + 各挂接点返回值。
    """
    from memsys import MemoryType, new_entry
    adapter = ZhirongAdapter()
    if seed:
        ctl = adapter.ctl
        ctl.factual.add(new_entry(
            MemoryType.FACT, "2 号高地海拔 320 米，仅东侧可装甲通行。",
            source="seed", attrs={"地点": "2号高地"}))
        ctl.experiential.add(new_entry(
            MemoryType.EXPERIENCE, "教训：夜间行军未派先遣侦察，先头遭伏击。",
            source="seed", importance=2.0))

    # ①②③④ 规划前（智戎管线调用点 1）
    plan = adapter.hook_plan(
        "ZR-001", "夜间夺占 2 号高地",
        constraints=["禁止越境", "限时 4 小时"])
    # ⑤ 规划执行（智戎自身管线，mock 略）
    # ⑥ 推演反馈（调用点 2）
    adapter.hook_feedback(
        "推演：任务部分达成。教训：夜间突袭未前置电子压制，通信被干扰。")
    # ⑦ 复盘进化（调用点 3）
    close = adapter.hook_close(extra_review="经验：预备队投入应提前 10 分钟。")

    return {"plan": plan, "close": close, "integration": adapter.log.to_dict()}


if __name__ == "__main__":
    import json
    result = mock_zhirong_session()
    print(json.dumps(result, ensure_ascii=False, indent=2))
