# 指挥决策图谱检索引擎（command_graph）

子课题-1 交付引擎：在 GraphRAG 知识图谱产物之上做**多跳关联检索**，并输出**可解释的推理路径**。

## 是什么

- 输入：问题文本；输出：带推理链路与逐跳依据的检索结果，供上层规划 / 生成系统消费。
- 契约：`memory_engine_sdk.md` v1.0.0；目录名 = `name` = `command_graph`
  （小写下划线、不以下划线开头、不命中保留名与内建引擎名）。
- **只做检索**：`supports_generate=False`、`supports_stream=False`、`supports_ingest=False`、
  `supports_delete=False`、`supports_browse=False`、`supported_suffixes=[]`
  —— 因此不会与内建引擎抢占后缀自动索引路由；生成由服务端统一编排。

## 交付物与落位

| 本目录内容 | 放到目标系统 |
|---|---|
| `command_graph/`（整个目录） | `server/engines/command_graph/` |
| 配套图数据 `<KG名>/`（随交付包） | `data/检索数据/知识图谱数据/<KG名>/` |

`__init__.py` 已导出模块级 `engine_plugin`，重启服务即自动注册，无需改动服务端任何代码。

## 依赖

| 依赖 | 用途 | 实测版本 |
|---|---|---|
| Python | 运行时 | 3.12.6 |
| pandas | 读 parquet | 2.3.3 |
| pyarrow | parquet 引擎 | 22.0.0 |

**不依赖** `neo4j` / `qdrant-client` / `graphrag` —— 本引擎不直连图库与向量库，只读 parquet。

## 数据来源（自动选择；两种模式都直接读 parquet）

1. **shared（服务端）**：`server.config.knowledge_base_dir()/知识图谱数据/<KG名>/output/*.parquet`
   （即 `data/检索数据/知识图谱数据/...`）。能 `import server.neo4j_client` 即判定为服务端环境。
2. **local（离线 / 沙箱）**：引擎所在仓库内的 `kg_out/<KG名>/output/*.parquet`，
   或交付包内布局 `data/检索数据/知识图谱数据/<KG名>/output/*.parquet`（都按目录层级自动定位）；
   也可用环境变量 `COMMAND_GRAPH_KG_ROOT` 显式指定数据根。

识别规则：`<KG名>/output/` 下存在 `entities.parquet`（或 `create_final_entities.parquet`）
即视为一个可用图谱。数据根不存在时 `check_availability()` 返回 False，
`search()` 记一条 WARNING（日志里会打印实际查找的路径）并返回空列表。

## 契约合规（要点）

- `name`=`command_graph`、`engine_label`=`指挥决策图谱`、`engine_color`=`#2f6fd0`
- `contract_version`=`1.0.0`，插件 `version`=`1.3.3`
- `search()` 每条结果含 `content / score / source_file / chunk_id / engine`（外加 `metadata`）
- `score` 归一到 0~1；`source_file` = `知识图谱数据/<KG名>`（检索数据根相对路径、正斜杠，
  绝不出现系统绝对路径）；`chunk_id` = `<KG名>:<实体名>`（融合去重键）
- 无同步 IO：文件读取全部走 `asyncio.to_thread`
- 不吞异常：检索异常向上抛，交由服务端路由器熔断器接管
- `check_availability()` 带 60 秒 TTL 缓存

## 结果里有什么（`metadata`）

| 字段 | 说明 |
|---|---|
| `reasoning_path` | 有序推理链路，如 `战斧巡航导弹 -[打击]-> 沙伊拉特空军基地` |
| `hops_detail` | 逐跳明细（from / to / 关系 / 证据 text_unit） |
| `evidence` | 逐跳原文依据（doc + text_unit + 文本片段），可核对可引用 |
| `seed` / `entity` / `entity_type` / `hops` | 命中的种子实体与跳数 |
| `kg_source` / `kgs` / `docs` | 该结果出自哪个图谱、涉及哪些文档 |
| `cross_kg_hops` / `cross_doc_hops` | 跨库 / 跨文档跳数（本课题的核心能力） |
| `search_mode` | `local` / `global` / `list`（整体规律类问题走社区摘要，罗列类问题走成员收口） |

## 可调参数（类属性）

| 参数 | 默认 | 含义 |
|---|---|---|
| `max_hops` | 2 | 从种子实体向外扩展的最大跳数 |
| `max_paths_per_seed` | 12 | 每个种子最多保留的路径条数 |
| `min_seed_ratio` | 0.2 | 种子实体的最少词元重叠比例 |

权重与超时不在插件内自报，只从服务端 `config.json` 的 `retrieval.engine_weights` /
`retrieval.engine_timeouts` 读取；建议 `"command_graph": 0.6` 与 `10.0`。

## 验证

```
python scripts/validate_engine.py command_graph     # 契约自检（离线，退出码 0 = 通过）
python scripts/smoke_test_engine.py command_graph   # HTTP 冒烟（需服务端已启动）
```

不启服务端也能做数据侧自检（需本机有图谱数据）：

```
python -c "import asyncio,sys;sys.path.insert(0,'.');from server.engines.command_graph import engine_plugin as e;print(asyncio.run(e.check_availability()))"
```

## 单机演示（可选，不属于 SDK 契约）

`sandbox/` 内放了最小契约实现（`server/engines/memory_plugin_api.py`），
配合 `tools/18_webui.py` + `webui/index.html`（WebUI：概览 / 图谱 / 检索 / 社区 / 指标）
可以在不依赖智戎服务端的情况下完整验收本引擎。
