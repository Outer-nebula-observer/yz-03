# 论文精读（深化版）：Zep — A Temporal Knowledge Graph Architecture for Agent Memory

> - **作者 / 机构**：Preston Rasmussen、Pavlo Paliychuk 等（Zep AI）
> - **发表**：arXiv 2025（2501.13956）
> - **对应**：`references/02_长期记忆/Rasmussen2025-Zep.pdf` → 同名 `.md`
> - **官方代码**：核心引擎 Graphiti 开源 https://github.com/getzep/graphiti；服务端 https://github.com/getzep/zep

## 一句话总结

把 agent 记忆做成"时序知识图谱"：Graphiti 引擎把非结构化对话 + 结构化业务数据动态合成为带时间属性的三层图谱（episode/semantic entity/community），非损式维护历史关系——DMR 94.8% 超 MemGPT 93.4%，LongMemEval 准确率最高 +18.5%、延迟降 90%。

## 1. Graphiti 知识图谱 G=(N, E, φ)

三层子图（hierarchical tiers）：

```
┌─ Community Subgraph Gc（最高层）───────────────────┐
│  community 节点 = 强连通实体簇，含高层摘要            │
│  community edges 连 community↔其成员实体            │
│  （借鉴 GraphRAG，给全局/领域级理解）                │
└────────────────────────┬──────────────────────────┘
                         ▼
┌─ Semantic Entity Subgraph Gs（中层）──────────────┐
│  entity 节点 = 从 episode 抽取 + 与已有图实体消解的实体  │
│  semantic edges = 实体间关系                         │
└────────────────────────┬──────────────────────────┘
                         ▼
┌─ Episode Subgraph Ge（底层，非损）─────────────────┐
│  episode 节点 = 原始输入（message/text/JSON），含 tref 时间戳│
│  episodic edges 连 episode↔其引用的语义实体           │
│  双向索引：语义 artifact 可回溯到源 episode（引用/引用）；episode 快速取其相关实体与事实 │
└──────────────────────────────────────────────────────┘
```

## 2. 关键机制（深化）

- **双时态模型（bi-temporal）**：T = 事件 chronological 顺序；T' = Zep 数据摄入 transactional 顺序（审计）。T 给记忆"动态性"维度，是 Zep 相对前作图 RAG 的核心新颖性。
- **实体抽取与消解**：处理当前消息 + 最近 n=4 条（两完整轮）做上下文 NER；说话者自动为实体；用**受 Reflexion 启发的反思**减幻觉、提覆盖；实体名嵌入 1024 维向量 + 全文检索找候选 → LLM 实体消解 prompt → 重复实体生成更新名/摘要。
- **时间信息**：消息带 tref，可识别"下周四""两周后""去年夏天"等相对/部分日期。
- **非损式 + 双向索引**：原始 episode 永存，语义 artifact 可溯源回原文（引用/引用），episode 可快速取相关实体/事实。
- **认知类比**：episode（情景记忆）+ semantic entity（语义记忆）双存储，对齐人脑情景/语义记忆区分。

## 3. 关键结果

| 基准 | Zep | 对比 |
|---|---|---|
| DMR（MemGPT 提出） | **94.8%** | MemGPT 93.4% |
| LongMemEval（企业时序推理） | 准确率最高 +18.5%、延迟 -90% | 优于基线 RAG 实现 |

## 4. 代码索引

- Graphiti 开源：https://github.com/getzep/graphiti
- Zep 服务：https://github.com/getzep/zep（含 DMR/LongMemEval 评测复现）
- 本仓库语境：**结构化/时序长期记忆代表方案**，可作赛题"图谱式事实记忆"进阶选型；复现位 `paper_code/长期记忆/`。

## 5. 优点 / 局限（深化）

- **优点**：图谱天然支持多跳/跨会话/时序推理；结构化事实可精确召回（对齐"事实记忆精确召回"验证点）；非损+双向索引可溯源；有开源引擎可二次开发；双时态模型是相对图 RAG 的实质进步。
- **局限**：图谱构建依赖 LLM 抽取质量（错抽/漏抽污染关系）；增量图更新与版本管理复杂；纯文本/简单场景下比向量库方案重；评测集中在对话记忆（message 类型）。

## 6. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 时序知识图谱 | 赛题"事实记忆"结构化进阶：装备参数/条令/战例以图存储支持多跳查询（`docs/04` 2.2 节选型） |
| 双时态模型 T/T' | 作战记忆"事件发生时间"与"录入时间"分离，支撑时序问答 |
| 非损+双向索引（可溯源） | 每条注入规划的记忆可回溯到源 episode（创新点 E 可解释溯源） |
| 跨会话综合 | 对应"跨场次经验/事实复用"，LongMemEval 类指标可作评估基准 |
| DMR 基准 | 组会汇报评估小节：Zep(94.8%) > MemGPT(93.4%) |

---
*事实记忆路线：MemoryBank（摘要式，见 `笔记_Zhong2023-MemoryBank.md`）；Zep（图谱式，本笔记）。*

## 论文核心代码（paper_code 索引）

- 仓库：`paper_code/02_长期记忆/graphiti/`
- `graphiti_core/`：三层图引擎核心——`edges.py`（episode/semantic/community 三类边）、`nodes.py`、`graph_queries.py`（Cypher 查询）、`driver/`（Neo4j 适配）；`docker-compose.yml` 一键起服务。

## 我们的实现（memsys）

- **思路**：MVP 不上图谱（构建贵），但保留其两个精髓——①**可溯源**：每条检索结果带 provenance（对应 Zep 的 episode↔semantic 双向索引）；②**事实走结构化**：SQLite 属性过滤对应其精确召回；
- **代码索引**：`memsys/schema.py::provenance()` + `memsys/long_term/factual_store.py::search_attrs()`。

## 代码详解（溯源如何随检索结果流动）

```python
# schema.py::provenance() —— 条目自带溯源包
def provenance(self):
    return {"id": self.id, "type": self.type.value, "source": self.source,
            "session_id": self.session_id, "timestamp": self.timestamp,
            "recall_count": self.recall_count}

# pipeline.py（节选）—— 溯源随每条检索结果输出（创新点 E）
result.retrieved = [{"id": h.entry.id, "score": round(h.score, 4),
                     "route": h.route, "content": h.entry.content[:80],
                     "provenance": h.entry.provenance()}  # ← 注入规划的记忆可回查来历
                    for h in hits]
```
> 对应 Zep 的"semantic artifact 可回溯到源 episode"——我们的轻量版：`source='复盘:P001'` 即能回答"这条教训哪来的"。进阶接 graphiti 时把 provenance 升级为图节点回链。

## 代码实证（结合 paper_code/）

- 仓库：`paper_code/02_长期记忆/graphiti/`（Graphiti 引擎）
- **可起服务**：`docker-compose up` 本地跑时序知识图谱；看 `graphiti/` 源码（三层图 episode/semantic/community + 双时态）、`AGENTS.md`。
- 赛题用法：进阶事实记忆图谱后端候选（装备/条令/战例多跳查询）。