# -*- coding: utf-8 -*-
"""
zhirong_kit.adapter — 智戎对接适配器工厂（统一入口）
=====================================================
在现有 `integration/zhirong_adapter.py` 的基础上，提供一个**一键装配**工厂：

  create_adapter(real=False, fact_db=None, exp_db=None, embed_glm=False, ...)

它会自动完成：
  1. 选择 LLM：real=True 时用 DeepSeek（.env 的 DEEPSEEK_API_KEY），否则 Mock；
  2. 选择 embedding：embed_glm=True 且 GLM Key 可用时用 GLM embedding-2，
     否则 Mock（DeepSeek 无 embedding 接口）；
  3. 持久化：事实库 SQLite + 经验库 SQLite（如果给路径）；
  4. 返回可用的 ZhirongAdapter（三挂接点 + 集成时延日志）。

使用场景：
  - 智戎侧嵌入 Python：  from zhirong_kit.adapter import create_adapter
  - HTTP 桥：            from zhirong_kit.bridge_server import create_bridge
  - 自检：                python -m zhirong_kit.selfcheck

本文件可单独拷贝（连同 memsys 包一起部署到智戎环境），零第三方依赖。
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

# ---- 路径装配：让本套装可从上到下找到 memsys / 兄弟 adapter ----
_KIT = os.path.dirname(os.path.abspath(__file__))
_INT = os.path.dirname(_KIT)          # integration/
_ROOT = os.path.dirname(_INT)         # 课题3_长短期记忆/
for _p in (_ROOT, _INT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from memsys import (  # noqa: E402
    MemoryController, FactualStore, ExperientialStore, MockEmbedding,
    get_llm, get_embedding,
)
from zhirong_adapter import ZhirongAdapter  # noqa: E402


def create_adapter(real: bool = False,
                   fact_db: Optional[str] = None,
                   exp_db: Optional[str] = None,
                   embed_glm: bool = False,
                   model: Optional[str] = None,
                   queries_per_session: int = 2) -> ZhirongAdapter:
    """创建可直接对接智戎的适配器。

    参数：
      real             True → 用 DeepSeek 真 LLM（.env 需要 DEEPSEEK_API_KEY）；
                        False → MockLLM（离线稳定）。
      fact_db/exp_db   SQLite 持久化路径（None = 内存态，重启即失）。
      embed_glm        True 且 GLM Key 有效 → 用 GLM embedding-2；
                       否则 MockEmbedding（DeepSeek/离线场景推荐 Mock）。
      model            DeepSeek 模型名覆盖（默认 .env 的 DEEPSEEK_MODEL）。
      queries_per_session  默认每次规划并发查询数（hook_plan 用）。

    返回：ZhirongAdapter（plan/feedback/close 三个方法 + .log 时延日志）。
    """
    # ---- LLM：DeepSeek 或 Mock（失败自动降级不阻断对接） ----
    llm = None
    if real:
        try:
            llm = get_llm("deepseek", **({"model": model} if model else {}))
        except Exception as exc:  # 密钥缺失/无效 → 降级 Mock 并提示
            print(f"[zhirong_kit] 警告：DeepSeek 不可用（{exc}），回退 MockLLM")
    # ---- Embedding：GLM（可选）或 Mock ----
    emb = MockEmbedding()
    if embed_glm:
        try:
            emb = get_embedding("glm")
            emb.embed("连通性校验")   # 构造成功不代表 Key 有效，必须实际试一次
        except Exception as exc:
            print(f"[zhirong_kit] 警告：GLM embedding 不可用（{exc}），回退 MockEmbedding")
            emb = MockEmbedding()
    # ---- 持久化存储 ----
    factual = FactualStore(fact_db or ":memory:", emb)
    experiential = ExperientialStore(emb, db_path=exp_db)
    ctl = MemoryController(llm=llm, embedding=emb,
                           factual=factual, experiential=experiential)
    return ZhirongAdapter(controller=ctl,
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
