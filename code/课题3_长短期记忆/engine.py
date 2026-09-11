# -*- coding: utf-8 -*-
"""
engine — 老师平台「记忆检索引擎 SDK」插件适配器
=================================================
作用：把 memsys 的混合检索能力包装成 MemoryEnginePlugin，
挂进老师的记忆检索引擎服务（SDK 契约见
`code/记忆检索引擎SDK/memory_engine_sdk.md` 与 `template/engine.py`）。

挂接方式（三步）：
  1. 把本目录（课题3_长短期记忆）整个放进 SDK 服务的 engines 目录
     （或在其 PYTHONPATH 内）；
  2. 服务启动时自动发现 `engine_plugin`（见下方导出）；
  3. 前端选引擎"长短期记忆"即走本适配器。

设计说明：
  - SDK 基类 `server.engines.memory_plugin_api.MemoryEnginePlugin` 只在
    SDK 服务环境存在——因此这里用 **try/except 条件导入**：
    独立运行（无 SDK）时退化为"占位基类"，import 本文件不报错，
    冒烟测试/演示不受影响；
  - 检索语义：把 query 交给 HybridRetriever（三路融合），
    事实/经验双库都查，返回 SDK 约定的结果结构。
"""

from __future__ import annotations

from typing import Any, Dict, List

# ---- 条件导入 SDK 契约（无 SDK 环境下退化为占位基类，保证可独立 import） ----
try:  # pragma: no cover - 仅在 SDK 服务环境内走到
    from server.engines.memory_plugin_api import EngineCapabilities, MemoryEnginePlugin
    _HAS_SDK = True
except ImportError:  # 独立运行：定义最小占位，保持接口形状一致
    _HAS_SDK = False

    class MemoryEnginePlugin:  # type: ignore[no-redef]
        """占位基类（形状与 SDK 契约一致，便于 IDE 提示）。"""

        name = engine_label = engine_color = version = description = contract_version = ""

        def capabilities(self): ...
        async def check_availability(self) -> bool: return True
        async def search(self, query, top_k=10, timeout=30.0): return []
        async def ingest_file(self, rel_path) -> Dict[str, Any]: return {}
        async def remove_file(self, rel_path) -> Dict[str, Any]: return {}
        async def list_data(self) -> Dict[str, Any]: return {}

    class EngineCapabilities:  # type: ignore[no-redef]
        """占位能力声明（字段与 SDK 契约一一对应，支持属性访问）。

        SDK 环境用的是 dataclass；占位版用显式字段，保证 sdk_check
        的属性检查在无 SDK 环境同样可跑（此前 **kw 版无属性会崩）。
        """

        def __init__(self, supports_ingest: bool = False, supports_delete: bool = False,
                     supports_generate: bool = True, supports_stream: bool = True,
                     supports_browse: bool = False,
                     supported_suffixes: "list | None" = None,
                     ingest_granularity: str = "file",
                     storage_backend: str = "") -> None:
            self.supports_ingest = supports_ingest
            self.supports_delete = supports_delete
            self.supports_generate = supports_generate
            self.supports_stream = supports_stream
            self.supports_browse = supports_browse
            self.supported_suffixes = supported_suffixes or []
            self.ingest_granularity = ingest_granularity
            self.storage_backend = storage_backend


# 【契约合规】score 归一化上限（SDK §3.2：score 必须 0~1）。
# 我们的融合分 = alpha*cos + beta*bm25 + gamma*sql，理论上限 = 三权重和
# （多路命中同一条时累加）。检索器构造时权重和≈1.0，此处除以实际权重和
# 归一，保证不同权重配置下 score 始终落在 [0,1]。
_SCORE_MAX = 1.0


class LongShortTermMemoryEngine(MemoryEnginePlugin):
    """长短期记忆引擎插件（memsys 包装层）——老师平台 SDK 的适配器。

    检索行为：
      - 一次 query 同时打事实库（参数级精确）与经验库（语义召回）；
      - 自动构造 QueryItem（默认 vector 路由），走 HybridRetriever 融合；
      - 返回 SDK 约定的 dict 列表（content/score/source_file/...）。

    与 memsys 内部的关系：
      - 本类只做"平台协议 → memsys 方法"的翻译，不含业务逻辑；
      - 内部持有一个 MemoryController（默认全 Mock，接真模型时注入
        GLM/智戎网关；多实例部署时每个引擎实例一个独立记忆库）；
      - 写入（记忆进化）不是通过 ingest_file——走场次复盘的
        ZhirongAdapter/controller.close_session，因此 supports_ingest=False。

    契约合规要点（SDK §3.2/§9）：score 0~1、source_file 非绝对路径、
    supported_suffixes=[] 不与内建引擎争后缀、异常上抛由路由器熔断、
    同步 IO 放线程（asyncio.to_thread）。
    """

    name = "long_short_term_memory"
    engine_label = "长短期记忆"
    engine_color = "#2E86AB"
    version = "0.1.0"
    description = "赛题③：事实/经验双库 + 混合检索 + 记忆进化（memsys）"
    contract_version = "1.0.0"

    def __init__(self) -> None:
        # 延迟导入 memsys（避免无 SDK 环境下的导入顺序问题）
        from memsys import MemoryController, QueryItem
        self._ctl = MemoryController()          # 全 Mock 起步；接真模型时注入
        self._QueryItem = QueryItem

    @property
    def capabilities(self):  # type: ignore[override]
        """能力声明（SDK 前端据此决定如何展示/调用本引擎）。

        每一项都对应一个平台契约决策：
          - supports_ingest=False：记忆写入不通过"上传文件"完成，
            而是复盘时由进化模块写入（见 ZhirongAdapter.hook_close）；
          - supports_generate=False：平台负责规划生成，本引擎只做检索
            （避免与智戎规划管线职责重叠）；
          - supports_stream=False：检索结果一次性返回即可，无流式；
          - supported_suffixes=[]：不认领 .txt 等后缀，避免与内建
            standard_rag 冲突（契约 §3.3）；
          - storage_backend 描述性字符串，供平台 UI 展示存储类型。
        """
        return EngineCapabilities(
            supports_ingest=False,   # 写入走进化模块（场次复盘），不做文件级 ingest
            supports_delete=False,
            supports_generate=False, # 生成由智戎规划管线负责，本引擎只管检索
            supports_stream=False,   # 同上：检索面插件，SSE 层发 engine_done(unsupported)
            supported_suffixes=[],   # 不认领文件后缀（避免与内建 standard_rag 争 .txt）
            ingest_granularity="file",  # 契约值仅为 file/directory/both；无 ingest 时声明 file
            storage_backend="memsys(sqlite+vector)",
        )

    async def check_availability(self) -> bool:
        return True

    async def search(self, query: str, top_k: int = 10,
                     timeout: float = 30.0) -> List[dict]:
        """SDK 检索入口：query → 双库混合检索 → SDK 结果结构。

        【契约合规要点（SDK §3.2/§9）】
        - score 归一化 0~1：融合分除以三权重和（多路累加的上限）后截断；
        - 异常不吞：检索异常向上抛（SDK 路由器有熔断接管），不返回空列表；
        - source_file：用条目 source（复盘场次/seed 等可辨识标记），
          绝不放系统绝对路径；
        - chunk_id：条目唯一 id（去重键）。
        """
        # 同步检索放到线程里跑——SDK §9 陷阱 1：同步 IO 阻塞事件循环
        import asyncio
        return await asyncio.to_thread(self._search_sync, query, top_k)

    def _search_sync(self, query: str, top_k: int) -> List[dict]:
        """实际检索逻辑（同步实现，被 asyncio.to_thread 包裹避免阻塞事件循环）。

        对同一查询分别打事实库与经验库：
          - target="fact"       → 走 FactualStore 向量/精确路径；
          - target="experience" → 走 ExperientialStore 语义/重要性路径。
        SDK 的查询文本没有 target 概念，所以两条路都跑再按融合分合并
        排序——这样一次平台查询既覆盖"参数事实"也覆盖"历史教训"。
        """
        q = self._QueryItem(q_id="sdk", intent="平台检索", target="fact",
                            route="vector", query_text=query)
        fact_hits = self._ctl.retriever.retrieve(q, top_k=top_k)
        q2 = self._QueryItem(q_id="sdk-e", intent="平台检索", target="experience",
                             route="vector", query_text=query)
        exp_hits = self._ctl.retriever.retrieve(q2, top_k=top_k)
        # 【score 归一化】融合分理论上限 = alpha+beta+gamma（多路命中累加）；
        # 除以实际权重和，保证任意权重配置下 score ∈ [0,1]
        wsum = (self._ctl.retriever.alpha + self._ctl.retriever.beta
                + self._ctl.retriever.gamma) or 1.0
        out: List[dict] = []
        for h in fact_hits + exp_hits:
            p = h.entry.provenance()
            out.append({
                "content": h.entry.content[:500],
                "score": round(min(h.score / wsum, 1.0), 4),
                "source_file": h.entry.source or "memsys",
                "chunk_id": h.entry.id,
                "engine": self.name,
                "metadata": {**h.entry.metadata,
                             "memory_type": h.entry.type.value,
                             "route": h.route,
                             "session_id": p["session_id"],
                             "timestamp": p["timestamp"]},
            })
        out.sort(key=lambda x: x["score"], reverse=True)
        return out[:top_k]

    async def ingest_file(self, rel_path: str) -> Dict[str, Any]:
        # 【设计说明】事实/经验的写入由"场次复盘进化"完成（ZhirongAdapter
        # → controller.close_session → evolution），不接收平台文件 ingest。
        # 返回 0 并附说明，是为了让平台前端明确知道"这个引擎不是文件库"。
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
