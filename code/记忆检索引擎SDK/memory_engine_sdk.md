# 记忆引擎开发 SDK（v1.0.0）

> 面向第三方记忆引擎开发者。按本文档实现契约后，把引擎包放进 server/engines/ 目录，重启服务即自动注册，前端和后端都能直接使用。
> 契约版本：MEMORY_ENGINE_CONTRACT_VERSION = "1.0.0"（与 server/engines/memory_plugin_api.py 保持一致）。

---

## 1. 概述

记忆引擎是「检索引擎层」的可插拔单元，统一实现 MemoryEnginePlugin 契约。系统已内置 5 个引擎（standard_rag / graph_rag / light_rag / struct_rag / plan_rag），第三方引擎与它们平级、同契约、同注册方式。

**引擎职责边界（重要）**：

- 引擎只管「检索数据 → 引擎存储」的**索引**，以及「引擎存储 → 结果」的**检索/生成**。
- 引擎**不负责**「源数据 → 检索数据」的构建（PDF/AFSIM 解析、三元组抽取等属构建层）。
- 因此 ingest_file 的输入一定是**已构建好的检索数据文件**（.txt/.md/.json/.parquet/.db），绝不是 .pdf/.docx 等源数据。

---

## 2. 快速开始（5 分钟）

### 2.1 目录结构

```text
server/engines/
├── standard_rag/          # 内建引擎（示例参考）
├── _template/             # 模板（复制它开始开发）
└── my_engine/             # 你的引擎（复制 _template 改名）
    ├── __init__.py        # 导出 engine_plugin
    ├── engine.py          # 实现 MemoryEnginePlugin
    └── README.md          # 说明
```

### 2.2 三步接入

1. 复制 server/engines/_template/ 为 server/engines/你的引擎名/；
2. 在 engine.py 实现 search()（必选）及可选的 ingest/generate；
3. 重启服务。`GET /api/v2/memory-engine/engines` 出现你的引擎，前端自动出现勾选框和结果卡片。

> 目录名建议与 name 一致；目录名不能以下划线开头（_template 会被跳过），也不能命中保留名清单（见 §6.3）。
>
> **最小实现提示**：只想做检索、不做生成时，务必在 capabilities 里显式设 `supports_generate=False`、`supports_stream=False`，否则 validate_plugin 会因「未实现 generate/generate_stream」报错。骨架见附录 A。

---

## 3. 契约详解

### 3.1 MemoryEnginePlugin 基类

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

MEMORY_ENGINE_CONTRACT_VERSION = "1.0.0"

@dataclass
class EngineCapabilities:
    supports_ingest: bool = False       # 检索数据→引擎存储的索引能力
    supports_delete: bool = False       # 数据删除能力
    supports_generate: bool = True      # 非流式生成
    supports_stream: bool = True        # 流式生成
    supports_browse: bool = False       # 数据浏览/预览
    supported_suffixes: list[str] = field(default_factory=list)  # 认领的检索数据后缀
    ingest_granularity: str = "file"    # "file"(文本) | "directory"(图数据KG) | "both"
    storage_backend: str = ""           # 描述性字段："qdrant"/"neo4j"/"in-memory" 等

class MemoryEnginePlugin(ABC):
    # ── 元数据（类属性，必填）──
    name: str              # 唯一 id，小写下划线，如 "standard_rag"
    engine_label: str      # 前端展示名
    engine_color: str      # 前端颜色（#rrggbb）
    version: str           # 插件版本
    description: str       # 一句话描述
    contract_version: str = MEMORY_ENGINE_CONTRACT_VERSION

    @property
    @abstractmethod
    def capabilities(self) -> EngineCapabilities: ...

    # ── 检索面（必选）──
    @abstractmethod
    async def check_availability(self) -> bool: ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 10,
                     timeout: float = 30.0) -> list[dict]: ...

    # ── 数据面（可选，按 capabilities 声明）──
    async def ingest_file(self, rel_path: str) -> dict:
        raise NotImplementedError

    async def ingest_directory(self, rel_dir: str) -> dict:
        raise NotImplementedError

    async def remove_file(self, rel_path: str) -> dict:
        raise NotImplementedError

    async def list_data(self) -> dict:
        raise NotImplementedError

    # ── 生成面（可选，按 capabilities 声明）──
    async def generate(self, query: str, top_k: int = 10,
                       timeout: float = 30.0) -> dict:
        raise NotImplementedError

    async def generate_stream(self, query: str, top_k: int = 10,
                              timeout: float = 30.0) -> AsyncGenerator:
        raise NotImplementedError
```

### 3.2 search 返回字段契约（每条结果）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| content | str | 是 | 检索内容片段 |
| score | float | 是 | 相关度，归一化 0~1（越高越相关） |
| source_file | str | 是 | 来源文件相对路径；无法解析时用可辨识标记（如 [KG:xxx]） |
| chunk_id | str | 是 | 去重键组成之一 |
| engine | str | 是 | 引擎自报名；降级路径可用 xxx_fallback |
| metadata | dict | 否 | 引擎私有字段，融合时平铺进 RetrievalResult.metadata |

> 注意：score 必须归一化 0~1。位置伪分（如 1.0 - i*0.02）属于已知偏差，会降低融合排序质量，建议用真实语义相似度。

### 3.3 数据面语义

- ingest_file(rel_path)：索引单个检索数据文件，幂等（重复调用覆盖），返回 {"indexed": n}。
- ingest_directory(rel_dir)：索引一个目录（用于图数据 KG 等目录级数据），返回 {"indexed": n} 或 {"pending": true, ...}。
- remove_file(rel_path)：从引擎移除某文件的数据，返回 {"removed": n}。
- list_data()：列出引擎已索引数据，复用 {"directories": [...], "files": [...]} 结构。

**rel_path / rel_dir 语义**：相对「检索数据根」（data/检索数据/）的正斜杠路径，如 "半结构化数据/doctrine/foo.md"、"知识图谱数据/JP3_60"。解析绝对路径用：

```python
from server.config import knowledge_base_dir
abs_path = knowledge_base_dir() / rel_path
```

> **supported_suffixes 的用途**：它用于「自动索引路由」——检索数据文件变更时（notify_data_changed），系统按扩展名认领声明了该后缀且 supports_ingest=True 的插件，自动调 ingest_file/ingest_directory。注意：**内建引擎优先**——若某后缀已被内建引擎认领（如 `.txt` 被 standard_rag 认领），同名后缀的第三方引擎会被忽略并打 WARNING；后缀匹配大小写不敏感、自动去前导点。接某后缀前先确认没有内建引擎占用。

### 3.4 生成面语义

- generate() 返回 {"generated_text", "citations", "sources", "retrieval_count", "elapsed_ms"}。
- 不支持生成时，capabilities.supports_generate=False；路由器/SSE 层会自动发 engine_done(status="unsupported")，插件无需实现 generate。

---

## 4. 流式事件契约（generate_stream 必守）

generate_stream 产出 (event_type, data) 元组序列，事件顺序：

```text
engine_start → [engine_status…] → [engine_token…] → engine_done
```

**铁律：每次生成恰好发射一个 engine_done**（服务端 done 计数与 SSE 流终止依赖此语义，多发/漏发都会导致前端卡片挂起或提前结束）。

各事件 payload（参考 server/engines/base.py 的 `_emit_start/_emit_status/_emit_token/_emit_done`，字段对齐即可，不强制继承）：

**engine_start**

| 字段 | 说明 |
|---|---|
| engine / engine_label / engine_color | 引擎元数据 |

**engine_status**

| 字段 | 说明 |
|---|---|
| engine | 引擎 name |
| phase | 阶段名（自定义，如 searching / generating） |
| … | 其他自定义字段（可选，透传） |

**engine_token**

| 字段 | 说明 |
|---|---|
| engine | 引擎 name |
| delta | 文本增量 |
| zone | 可选：`"thinking"`（思考区）或缺省（正文区） |

**engine_done** payload 必含：

| 字段 | 说明 |
|---|---|
| engine / engine_label / engine_color | 元数据 |
| status | "ok" \| "degraded" \| "error" \| "unavailable" \| "unsupported" |
| generated_text | 生成文本 |
| citations | 引用列表 |
| sources | 来源列表 |
| elapsed_ms | 耗时 |
| retrieval_count | 检索条数 |

payload JSON 序列化后必须单行（客户端 rag_stream 仅支持单行 data）；服务端统一 json.dumps(..., ensure_ascii=False) 已保证。

### 4.1 生成面实现参考（LLM + 引用工具）

实现 generate/generate_stream 时，直接复用系统内置的 LLM 调用与引用工具，不必自己写：

**LLM 调用**（`src.agent.llm_interface.LLMInterface`）：

```python
from src.agent.llm_interface import LLMInterface

llm = LLMInterface()  # 自动读取 config.json 的模型/provider 配置

# 流式：async generator，逐 chunk yield
async for chunk in llm.achat_stream(prompt, temperature=0.3, max_tokens=1024):
    ...

# 非流式：同步方法，须用 asyncio.to_thread 包裹避免阻塞事件循环
answer = await asyncio.to_thread(llm.chat, prompt)
```

**引用溯源工具**（`server.engines.citation_utils`）：

```python
from server.engines.citation_utils import CITATION_PROMPT, parse_citations, build_numbered_context

context = build_numbered_context(items, max_content_len=500)  # 【来源N】编号上下文
citations = parse_citations(generated_text, len(items))       # 解析生成文本里的【来源N】
```

**事件发射器**：可多继承 `server.engines.base.BaseEngine` 复用 `_emit_start/_emit_status/_emit_thinking/_emit_token/_emit_done/_build_sources/_enforce_citations`（`class MyEngine(MemoryEnginePlugin, BaseEngine)`），或按 §4 手工构造字段。

**完整 generate_stream 示例**：

```python
async def generate_stream(self, query, top_k=10, timeout=30.0):
    import time as _t
    from server.engines.citation_utils import CITATION_PROMPT, parse_citations, build_numbered_context
    from src.agent.llm_interface import LLMInterface

    t0 = _t.perf_counter()
    yield ("engine_start", {"engine": self.name, "engine_label": self.engine_label, "engine_color": self.engine_color})
    yield ("engine_status", {"engine": self.name, "phase": "searching"})

    items = await self.search(query, top_k=top_k, timeout=timeout * 0.8)
    context = build_numbered_context(items, max_content_len=500)
    prompt = f"""{CITATION_PROMPT}

## 用户问题
{query}

## 检索到的文档
{context}

## 回答"""

    llm = LLMInterface()
    buf = []
    async for chunk in llm.achat_stream(prompt, temperature=0.3, max_tokens=1024):
        buf.append(chunk)
        yield ("engine_token", {"engine": self.name, "delta": chunk})

    generated_text = "".join(buf)
    citations = parse_citations(generated_text, len(items))
    sources = [
        {"source_file": i.get("source_file", ""), "excerpt": (i.get("content", "") or "")[:40]}
        for i in items
    ]

    yield ("engine_done", {
        "engine": self.name, "engine_label": self.engine_label, "engine_color": self.engine_color,
        "status": "ok", "generated_text": generated_text,
        "citations": citations, "sources": sources,
        "elapsed_ms": int((_t.perf_counter() - t0) * 1000), "retrieval_count": len(items),
    })
```

> 只发射 §4 列出的四种事件；插件自定义事件类型会被服务端原样转发给前端，而前端只认 engine_start/engine_status/engine_token/engine_done（engine_confidence 由服务端自动追加，插件无需发）。

---

## 5. 异步要求与异常约定

- **禁止同步 IO / CPU 密集计算阻塞事件循环**：文件读取、网络请求、重计算必须用 asyncio.to_thread 包裹。
- **异常由路由器熔断器接管**：search/generate 抛出异常会被路由器捕获并记 trace，连续失败 3 次进入 30s 冷却；不要自行吞掉异常返回空结果（那会掩盖故障）。
- **超时由外层兜底**：路由器用 wait_for(timeout+0.5) 包裹，无需插件自行实现超时，但 search 的 timeout 参数应按约执行（超时任务及时取消）。

---

## 6. 接入方式

### 6.1 零配置（推荐）

把引擎包放进 server/engines/ 下，__init__.py 导出 engine_plugin，重启即自动注册：

```python
# server/engines/my_engine/__init__.py
from .engine import MyEngine, engine_plugin
__all__ = ["MyEngine", "engine_plugin"]
```

discover_plugins() 会扫描 server/engines/ 下每个含 __init__.py 的子包，查找模块级 engine_plugin 实例并按其 name 自动注册。

### 6.2 高级：目录外模块

config.json 的 engines.modules 可注册 server/engines/ 之外的模块：

```json
{ "engines": { "modules": ["my_pkg.my_engine"], "allow_override": false } }
```

### 6.3 保留名黑名单（命中即拒绝加载）

插件目录名/name 不得与以下顶层模块重名（目录包会遮蔽同名 .py 模块，击穿内建引擎）：

```text
base, citation_utils, qdrant_client, reasoning_bus, retrieval_router,
memory_plugin_api, memory_plugin_adapters, memory_plugin_registry
```

另：目录名以下划线开头（_template、__pycache__ 等）会被跳过；内建引擎目录名（standard_rag/graph_rag/light_rag/struct_rag/plan_rag）已由适配器接管。

---

## 7. 配置（权重 / 超时 / 覆盖）

- 权重/超时只从 config.json 的 `retrieval.engine_weights` / `retrieval.engine_timeouts` 读取；未配置时回落 `engine_weights.get(name, 0.5)` 与 `engine_timeouts.get(name, 30.0)`。第三方插件无需、也无法在插件内部自报权重（注册时不携带）。
- config.json retrieval 段可配置：

```json
{ "retrieval": { "engine_weights": {"my_engine": 0.6}, "engine_timeouts": {"my_engine": 10.0} } }
```

- allow_override=True 时，同名第三方插件可覆盖内建引擎（覆盖记 WARNING 日志）。默认 False（仅并存不覆盖）。

---

## 8. 自检（validate_plugin）

接入前可调用契约自检，返回违规清单（空列表 = 通过）：

```python
from server.engines.memory_plugin_api import validate_plugin
from server.engines.my_engine import engine_plugin
violations = validate_plugin(engine_plugin)
assert violations == [], violations   # 无违规才能接入
```

自检项：是否 `MemoryEnginePlugin` 实例、name 命名规范、engine_label 非空、engine_color 为 `#rrggbb`、contract_version 匹配、ingest_granularity 合法、capabilities 与已实现方法一致。

> 注意：validate_plugin **不会调用 search()、也不校验 search 返回字段**。返回字段是否符合 §3.2，请用 `scripts/smoke_test_engine.py`（HTTP 冒烟）或直接调 `/api/v2/memory-engine/search` 做端到端验证。

---

## 9. 常见陷阱

1. **同步 IO 阻塞事件循环**：read_text/requests.post 直接写 async 方法里 → 卡死整个检索。用 asyncio.to_thread。
2. **漏发/多发 engine_done**：SSE 流终止靠 done 计数，多发导致提前结束、漏发导致前端卡片永挂。
3. **check_availability 永久缓存**：后端恢复后仍返回 False。建议带 TTL（如 60s）缓存探测结果。
4. **score 不归一化**：返回 0~100 或负分会被融合排序错置。统一 0~1。
5. **source_file 用系统绝对路径**：应与 payload 口径一致（检索数据根相对路径），否则删除/去重对不上。
6. **吞异常返回空列表**：会掩盖故障、绕过熔断器。让异常抛出，由路由器接管。

---

## 10. 共享底座访问（复用已有向量/图数据）

系统提供**共享底座**，引擎可不自建存储，直接复用已有的向量与图数据：

| 底座 | 访问入口 | 内容 |
|---|---|---|
| 向量底座 | server.engines.qdrant_client.get_qdrant_client() | knowledge_chunks(文本) / entity_embeddings(实体) / relation_embeddings(关系) |
| 图底座 | server.neo4j_client.get_async_driver() / get_sync_driver() | Entity / Community / CommunityReport / TextUnit + 关系边 |
| 向量化 | server.embedding_model.encode(texts) | BGE-large-zh，query→向量 |
| LLM 调用 | src.agent.llm_interface.LLMInterface | achat_stream()（流式）/ chat()（非流式），自动读 config.json 模型配置 |
| 引用工具 | server.engines.citation_utils | CITATION_PROMPT / parse_citations / build_numbered_context |

三种接入模式（由 capabilities 声明）：

1. **复用共享底座**（supports_ingest=False）：不实现 ingest，直接读已有向量/图，做自己的检索/分析。示例：

```python
from server.engines.qdrant_client import get_qdrant_client
from server.embedding_model import encode

async def search(self, query, top_k=10, timeout=30.0):
    client = get_qdrant_client()
    vec = encode([query])[0].tolist()
    points = client.query_points(
        collection_name="knowledge_chunks", query=vec, limit=top_k, with_payload=True)
    # ... 转成契约结果
```

2. **自有存储**（supports_ingest=True）：实现 ingest_file/ingest_directory，构建自己的向量/图（可复用共享底座的新集合，或独立存储）。

3. **混合**：复用共享底座 + 自有增量。

> 要点：复用共享底座时，source_file 应与底座 payload 口径一致（检索数据根相对路径），否则融合去重/删除会失配。

---

## 附录 A：最小实现骨架（完整可运行模板见 _template/）

> 完整可运行示例以 `server/engines/_template/engine.py` 为准（交付包内为 `template/engine.py`）。下面只给「最小可用」骨架，用于对照契约结构，别照抄这里的实现细节。

### engine.py（最小：只实现检索，不支持生成/索引）

```python
from __future__ import annotations

from server.engines.memory_plugin_api import EngineCapabilities, MemoryEnginePlugin


class MyEngine(MemoryEnginePlugin):
    name = "my_engine"          # 唯一 id，小写下划线
    engine_label = "我的引擎"     # 前端展示名
    engine_color = "#16a085"     # #rrggbb
    version = "1.0.0"
    description = "一句话描述"
    contract_version = "1.0.0"

    @property
    def capabilities(self) -> EngineCapabilities:
        # 只做检索：把 generate/stream 显式关掉，否则 validate_plugin 报未实现
        return EngineCapabilities(
            supports_ingest=False,
            supports_delete=False,
            supports_generate=False,
            supports_stream=False,
            supported_suffixes=[],
            ingest_granularity="file",
            storage_backend="",
        )

    async def check_availability(self) -> bool:
        return True

    async def search(self, query: str, top_k: int = 10, timeout: float = 30.0) -> list[dict]:
        # 返回 content / score / source_file / chunk_id / engine（见 §3.2）
        return []


engine_plugin = MyEngine()
```

### __init__.py

```python
from .engine import MyEngine, engine_plugin

__all__ = ["MyEngine", "engine_plugin"]
```

## 附录 B：接入自检清单

- [ ] engine_plugin 是 MemoryEnginePlugin 实例，name 唯一
- [ ] contract_version == "1.0.0"
- [ ] search 返回 content/score/source_file/chunk_id/engine 五字段
- [ ] score 归一化 0~1
- [ ] 无同步 IO 阻塞事件循环
- [ ] generate_stream 恰好一个 engine_done
- [ ] capabilities 与已实现方法一致
- [ ] validate_plugin 返回空列表
