# -*- coding: utf-8 -*-
"""
zhirong_kit.adapter — 智戎对接适配器工厂（统一入口 + P0 事件驱动扩展）
========================================================================
在 `integration/zhirong_adapter.py` 的基础上扩展：
  1. 事件驱动进化（不依赖"一次结束"）：hook_evolve / hook_append_feedback
  2. 结构化反馈：hook_feedback(text, structured)——AFSIM 数值/事件也能入库
  3. 任务规范化：normalize_task(task_json)——智戎结构化任务 → 内部输入
  4. 一键装配工厂：create_adapter(real, fact_db, exp_db, embed_glm, ...)

设计：`ZhirongEventAdapter` 继承原始 `ZhirongAdapter`，保持 hook_plan /
hook_feedback / hook_close 向后兼容，同时新增事件驱动能力。

对应 docs/20 P0 方案：
  S1 事件驱动进化、S3 输入规范化、S4 反馈多模态化（结构化转复盘文本）。
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional

# ---- 路径装配：让本套装可从上到下找到 memsys / 兄弟 adapter ----
_KIT = os.path.dirname(os.path.abspath(__file__))
_INT = os.path.dirname(_KIT)          # integration/
_ROOT = os.path.dirname(_INT)         # 课题3_长短期记忆/
for _p in (_ROOT, _INT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from memsys import (  # noqa: E402
    MemoryController, FactualStore, ExperientialStore, MockEmbedding,
    QueryItem, get_llm, get_embedding,
)
from memsys.stages import queries_for_stage  # noqa: E402
from zhirong_adapter import ZhirongAdapter   # noqa: E402


# ================================================================ 工具函数
def structured_to_review(payload: Dict[str, Any]) -> str:
    """把 AFSIM/系统的结构化结果转成一条可被记忆抽取的复盘文本。

    支持字段（按常见情况做别名兼容）：
      result/outcome     成功与否（success/fail/达成/失败/partially...）
      metrics             数值指标 {name: value}
      events              关键事件列表（字符串或 dict）
    启发式：失败→补"教训：…"；成功→补"经验：…"。这样即使平台只给
    数值/事件，也能让 extract_memory_ops 有机会抽取；真模型接入后
    可换 LLM 版 review_builder。

    注意：这是"保底转写"，真正的复盘质量仍建议由智戎提供复盘文本，
    或后续用 LLM 把结构化结果写成结构化复盘。
    """
    result = payload.get("result") or payload.get("outcome") or ""
    metrics = payload.get("metrics") or {}
    events = payload.get("events") or []
    lines = [f"复盘：任务结果——{result}。"]
    for k, v in metrics.items():
        lines.append(f"指标 {k}={v}。")
    if events:
        ev_text = []
        for e in events[:10]:
            ev_text.append(str(e.get("desc", e)) if isinstance(e, dict) else str(e))
        lines.append("关键事件：" + "；".join(ev_text))
    if isinstance(result, str):
        r = result.lower()
        if any(k in r for k in ("fail", "败", "损失", "未达成")):
            lines.append("教训：任务未达成，需复盘失败环节并调整方案。")
        elif any(k in r for k in ("success", "达成", "成功", "完成")):
            lines.append("经验：本类任务当前方案有效，可作为后续参考。")
    return "\n".join(lines)


def normalize_task(task_json: Dict[str, Any]) -> Dict[str, Any]:
    """把智戎结构化任务 JSON 规范化为内部输入。

    接受多种字段别名：
      plan_id/task_id/id
      goal/objective/objective_text/任务目标
      constraints/约束/rule/rules
      queries/query_list/查询

    返回：
      {"plan_id","goal","constraints","queries": [QueryItem, ...]}
    - 若任务自带查询，逐个转 QueryItem；
    - 否则用「受领任务 + 任务分析」阶段模板生成查询（P5 口径，与内部一致）。
    """
    def pick(*keys: str, default=""):
        for k in keys:
            if k in task_json:
                return task_json[k]
        return default

    plan_id = str(pick("plan_id", "task_id", "id", default=f"T-{int(time.time() % 100000)}"))
    goal = str(pick("goal", "objective", "objective_text", "任务目标", "目标", default=""))
    raw_c = pick("constraints", "约束", "rules", "rule", default=[])
    constraints = [str(c) for c in raw_c] if isinstance(raw_c, list) else [str(raw_c)] if raw_c else []
    queries: list = []
    raw_q = pick("queries", "query_list", "查询", default=None)
    if raw_q:
        for q in raw_q:
            if isinstance(q, QueryItem):
                queries.append(q)
            elif isinstance(q, dict):
                queries.append(QueryItem(
                    str(q.get("q_id") or q.get("id") or f"q{len(queries)+1}"),
                    str(q.get("intent", "查询")),
                    str(q.get("target", "fact")),
                    str(q.get("route", "vector")),
                    str(q.get("query_text", q.get("query", ""))),
                    attrs=q.get("attrs") or None,
                    stage=str(q.get("stage", "")),
                ))
    if not queries:
        # 兜底：按阶段模板生成查询（受领任务→历史教训，任务分析→情报事实）
        queries = (queries_for_stage("mission_receipt", goal)
                   + queries_for_stage("mission_analysis", goal))
    return {"plan_id": plan_id, "goal": goal,
            "constraints": constraints, "queries": queries}


# ================================================================ 事件驱动适配器
class ZhirongEventAdapter(ZhirongAdapter):
    """事件驱动版智戎适配器（兼容原三挂接点，新增 evolve/结构化反馈）。

    与原 ZhirongAdapter 的差异：
      - hook_feedback 支持 structured 结构化结果；
      - 新增 hook_evolve：**不依赖"必须有 open session"也能进化**——
        实现"事件驱动记忆进化"（docs/20 S1）；
      - 新增 hook_append_feedback：把多段反馈累积成材料。
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._structured_feedback: List[Dict[str, Any]] = []
        self._last_structured_text: str = ""

    def hook_feedback(self, feedback_text: str = "",
                      structured: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """接收反馈。text 沿用原逻辑；structured 会把结构化结果转写为
        复盘文本并追加到待消费材料（hook_evolve/close 时使用）。"""
        if structured:
            self._structured_feedback.append(structured)
            text = structured_to_review(structured)
            self._last_structured_text = text
            if not feedback_text:
                feedback_text = text
        return super().hook_feedback(feedback_text)

    def hook_append_feedback(self, fragment_text: str = "",
                             structured: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """把一段反馈追加（累积）进待消费材料，不立即消费。"""
        if structured:
            self._structured_feedback.append(structured)
            fragment_text = (fragment_text + "\n" + structured_to_review(structured)).strip()
        if fragment_text:
            self._feedback_text = (self._feedback_text + "\n" + fragment_text).strip()
        return {"ok": True, "buffered": len(self._feedback_text)}

    def hook_evolve(self, reason: str = "manual",
                    extra_review: str = "") -> Dict[str, Any]:
        """事件驱动进化：不要求当前必须有 open session。

        行为：
          - 若当前有 open session（之前 hook_plan 未 close）→ 走正常收场进化；
          - 否则直接从累积反馈 + extra 生成复盘材料并独立进化（核心）；
        返回：{summary, boundary, elapsed_ms, reason}
        """
        t0 = time.perf_counter()
        material = "\n".join(x for x in (self._feedback_text, extra_review) if x)
        try:
            if self.ctl.working_memory is not None:
                report = self.ctl.close_session(material)
            else:
                # 事件驱动核心：即使没有"规划会话"也能沉淀经验
                session_id = f"auto-{reason}-{int(time.time())}"
                report = self.ctl.evolution.evolve_from_review(
                    material, session_id=session_id)
            self._feedback_text = ""
            self._structured_feedback = []
            ok = True
        except Exception as exc:
            ok, detail = False, str(exc)
            report = None
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        if not ok:
            self.log.add(_CallRecordShim("evolve", elapsed, False, detail))
            return {"ok": False, "error": detail, "reason": reason,
                    "elapsed_ms": elapsed}
        summary = report.summary() if report else {}
        self.log.add(_CallRecordShim("evolve", elapsed, True, str(summary)))
        return {"ok": True, "reason": reason, "elapsed_ms": elapsed,
                "summary": summary,
                "boundary": self.ctl.evolution.boundary.stats()}


class _CallRecordShim:
    """轻量记录占位（与 IntegrationLog.CallRecord 字段兼容）。"""
    def __init__(self, hook: str, elapsed_ms: float, ok: bool, detail: str = ""):
        self.hook, self.elapsed_ms, self.ok, self.detail, self.at = \
            hook, elapsed_ms, ok, detail, time.time()


# ================================================================ 工厂
def create_adapter(real: bool = False,
                   fact_db: Optional[str] = None,
                   exp_db: Optional[str] = None,
                   embed_glm: bool = False,
                   model: Optional[str] = None,
                   queries_per_session: int = 2) -> ZhirongEventAdapter:
    """创建可直接对接智戎的**事件驱动适配器**（兼容原三挂接点）。

    参数：
      real             True → 用 DeepSeek 真 LLM（.env 需要 DEEPSEEK_API_KEY）；
                        False → MockLLM（离线稳定）。
      fact_db/exp_db   SQLite 持久化路径（None = 内存态）。
      embed_glm        True 且 GLM Key 有效 → 用 GLM embedding-2；否则 Mock。
      model            DeepSeek 模型名覆盖。
      queries_per_session  默认每次规划并发查询数。

    返回：ZhirongEventAdapter（plan/feedback/evolve/close + .log）。
    """
    llm = None
    if real:
        try:
            llm = get_llm("deepseek", **({"model": model} if model else {}))
        except Exception as exc:
            print(f"[zhirong_kit] 警告：DeepSeek 不可用（{exc}），回退 MockLLM")
    emb = MockEmbedding()
    if embed_glm:
        try:
            emb = get_embedding("glm")
            emb.embed("连通性校验")
        except Exception as exc:
            print(f"[zhirong_kit] 警告：GLM embedding 不可用（{exc}），回退 MockEmbedding")
            emb = MockEmbedding()
    factual = FactualStore(fact_db or ":memory:", emb)
    experiential = ExperientialStore(emb, db_path=exp_db)
    ctl = MemoryController(llm=llm, embedding=emb,
                           factual=factual, experiential=experiential)
    return ZhirongEventAdapter(controller=ctl,
                               queries_per_session=queries_per_session)


def adapter_info(adapter: ZhirongAdapter) -> Dict[str, Any]:
    """返回适配器运行时信息（用于 healthz/自检/验收）。"""
    ctl = adapter.ctl
    return {
        "model": getattr(ctl.llm, "model", "mock"),
        "embedding": getattr(ctl.embedding, "model", "mock"),
        "stores": {
            "facts": ctl.factual.stats()["count"],
            "experiences": ctl.experiential.stats()["count"],
        },
        "log": adapter.log.summary(),
    }
