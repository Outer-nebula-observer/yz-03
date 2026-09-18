# -*- coding: utf-8 -*-
"""
engine — 老师平台「记忆检索引擎 SDK」插件适配器（交付版）
=========================================================
作用：把 memsys 的混合检索能力包装成 MemoryEnginePlugin，
挂进老师的记忆检索引擎服务（SDK 契约见 memory_engine_sdk.md）。

交付版与开发版差异（对照返工清单 §3）：
  - 直接 import SDK 真实基类，不再提供 fallback 占位类；
  - memsys 改为相对导入（.memsys），目录名 = name = long_short_term_memory；
  - check_availability 带 TTL 缓存；
  - 支持通过环境变量注入真实 LLM / embedding，无密钥时自动降级 Mock。
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List

# SDK 服务环境真实契约（交付版不做 fallback：拖进 server/engines/ 后必定存在）
from server.engines.memory_plugin_api import EngineCapabilities, MemoryEnginePlugin


class LongShortTermMemoryEngine(MemoryEnginePlugin):
    """长短期记忆引擎插件（memsys 包装层）——老师平台 SDK 的适配器。

    检索行为：
      - 一次 query 同时打事实库（参数级精确）与经验库（语义召回）；
      - 自动构造 QueryItem（默认 vector 路由），走 HybridRetriever 融合；
      - 返回 SDK 约定的 dict 列表（content/score/source_file/chunk_id/engine）。

    与 memsys 内部的关系：
      - 本类只做"平台协议 → memsys 方法"的翻译，不含业务逻辑；
      - 记忆写入不通过 ingest_file，而是由场次复盘/智戎适配器调用
        controller.close_session 完成，因此 supports_ingest=False。
    """

    name = "long_short_term_memory"
    engine_label = "长短期记忆"
    engine_color = "#2E86AB"
    version = "1.0.0"
    description = "赛题③：事实/经验双库 + 混合检索 + 记忆进化（memsys）"
    contract_version = "1.0.0"

    # check_availability 的 TTL：60 秒内不重复探测，避免永久缓存故障状态
    AVAILABILITY_TTL = 60.0

    def __init__(self) -> None:
        # 延迟相对导入，确保包内 memsys 作为子包被加载
        from .memsys import MemoryController, QueryItem

        self._ctl = self._build_controller()
        self._QueryItem = QueryItem

        # 可用性探测缓存
        self._availability_ts = 0.0
        self._availability_cache = False

    # ------------------------------------------------------------------ 真模型注入
    @staticmethod
    def _build_controller():
        """构造 MemoryController；有真实模型配置时注入，否则回退 Mock。

        环境变量（与 .env 同效）：
          LSTM_LLM        = mock | deepseek | glm
          LSTM_EMBEDDING  = mock | glm

        说明：Mock 是零依赖离线兜底；接入智戎正式环境时建议配置真实
        DeepSeek/GLM（B4：避免默认全 Mock 无语义质量）。
        """
        from .memsys import MemoryController
        from .memsys.embeddings import get_embedding
        from .memsys.llm import get_llm, load_env

        load_env()

        llm = None
        llm_kind = os.environ.get("LSTM_LLM", "mock").lower()
        if llm_kind in ("deepseek", "glm"):
            try:
                llm = get_llm(llm_kind)
            except Exception:
                # 密钥缺失/失效时不阻断启动，回退 Mock（军规级可用性）
                llm = None

        emb = None
        emb_kind = os.environ.get("LSTM_EMBEDDING", "mock").lower()
        if emb_kind == "glm":
            try:
                emb = get_embedding("glm")
            except Exception:
                emb = None

        return MemoryController(llm=llm, embedding=emb)

    @property
    def capabilities(self) -> EngineCapabilities:
        """能力声明（SDK 前端据此决定如何展示/调用本引擎）。

        只做检索：ingest/generate/stream/delete/browse 全部关闭，
        避免与内建 standard_rag 争文件后缀。
        """
        return EngineCapabilities(
            supports_ingest=False,   # 写入走进化模块（场次复盘），不做文件级 ingest
            supports_delete=False,
            supports_generate=False, # 生成由智戎规划管线负责，本引擎只管检索
            supports_stream=False,   # 同上：检索面插件，SSE 层发 engine_done(unsupported)
            supports_browse=False,
            supported_suffixes=[],   # 不认领文件后缀（避免与内建 standard_rag 争 .txt）
            ingest_granularity="file",  # 契约值仅为 file/directory/both；无 ingest 时声明 file
            storage_backend="memsys(sqlite+vector)",
        )

    async def check_availability(self) -> bool:
        """带 TTL 的可用性探测（SDK §9 陷阱 3：避免永久缓存）。

        60 秒内重复调用直接返回缓存结果；到期后重新探测。
        """
        now = time.monotonic()
        if now - self._availability_ts < self.AVAILABILITY_TTL:
            return self._availability_cache
        self._availability_cache = await asyncio.to_thread(self._check_availability_sync)
        self._availability_ts = now
        return self._availability_cache

    def _check_availability_sync(self) -> bool:
        """同步探测：双库能否返回统计信息，任一异常视为不可用。"""
        try:
            self._ctl.factual.stats()
            self._ctl.experiential.stats()
            return True
        except Exception:
            return False

    async def search(self, query: str, top_k: int = 10,
                     timeout: float = 30.0) -> List[dict]:
        """SDK 检索入口：query → 双库混合检索 → SDK 结果结构。

        契约要点：
          - 同步检索放入 asyncio.to_thread，避免阻塞事件循环；
          - 异常不吞：检索异常向上抛（SDK 路由器有熔断接管）；
          - source_file 用条目来源的可辨识标记，绝不放系统绝对路径；
          - score 归一化 0~1。
        """
        return await asyncio.to_thread(self._search_sync, query, top_k)

    def _search_sync(self, query: str, top_k: int) -> List[dict]:
        """实际检索逻辑（同步实现，被 asyncio.to_thread 包裹）。"""
        q = self._QueryItem(
            q_id="sdk", intent="平台检索", target="fact",
            route="vector", query_text=query,
        )
        fact_hits = self._ctl.retriever.retrieve(q, top_k=top_k)

        q2 = self._QueryItem(
            q_id="sdk-e", intent="平台检索", target="experience",
            route="vector", query_text=query,
        )
        exp_hits = self._ctl.retriever.retrieve(q2, top_k=top_k)

        wsum = (self._ctl.retriever.alpha + self._ctl.retriever.beta
                + self._ctl.retriever.gamma) or 1.0

        out: List[dict] = []
        for h in fact_hits + exp_hits:
            p = h.entry.provenance()
            source = h.entry.source or f"[memsys:{h.entry.type.value}]"
            # 契约硬约束：source_file 绝不含系统绝对路径（SDK §3.2/§9）
            if os.path.isabs(source) or source.startswith(("D:\\", "C:\\", "/home/", "/Users/", "/tmp/")):
                source = f"[memsys:{h.entry.type.value}]"
            out.append({
                "content": h.entry.content[:500],
                "score": round(min(h.score / wsum, 1.0), 4),
                "source_file": source,
                "chunk_id": h.entry.id,
                "engine": self.name,
                "metadata": {
                    **h.entry.metadata,
                    "memory_type": h.entry.type.value,
                    "route": h.route,
                    "session_id": p["session_id"],
                    "timestamp": p["timestamp"],
                },
            })
        out.sort(key=lambda x: x["score"], reverse=True)
        return out[:top_k]

    # ------------------------------------------------------------------ 数据面
    # 记忆写入由"场次复盘进化"完成（ZhirongAdapter → close_session → evolution），
    # 不接收平台文件 ingest；以下方法显式返回 0，避免平台误以为有文件写入。
    async def ingest_file(self, rel_path: str) -> Dict[str, Any]:
        return {"indexed": 0, "note": "memsys 写入走记忆进化模块（复盘驱动）"}

    async def remove_file(self, rel_path: str) -> Dict[str, Any]:
        return {"removed": 0}

    async def list_data(self) -> Dict[str, Any]:
        return {
            "directories": [],
            "files": [],
            "memsys": {
                "facts": self._ctl.factual.stats()["count"],
                "experiences": self._ctl.experiential.stats()["count"],
            },
        }


# SDK 服务发现点：引擎目录被扫描时读取本变量完成注册
engine_plugin = LongShortTermMemoryEngine()
