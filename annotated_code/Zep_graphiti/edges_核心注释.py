# ============================================================================
# Zep/Graphiti: graphiti_core/edges.py 核心节选【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2501.13956 §2.2：
#   Zep 的时序知识图谱 G=(N,E,φ)，三层子图 episode/semantic entity/community。
#   本文件定义"边"的类层次——**边的类型 = 图的语义骨架**。
#
# 【为什么精读】赛题③"事实记忆进阶选型"（Zep 路线）的核心文件；
#   EntityEdge 的三个时间字段是**双时态模型**（bi-temporal）的落地，
#   也是 Zep 论文声称超越前作图 RAG 的实质创新的代码证据。
#
# 【我们的实现对照】
#   EpisodicEdge（episode↔entity 引用边） → 我们 MemoryEntry.source（单层溯源）
#   EntityEdge.valid_at/invalid_at        → 我们 timestamp 单字段（无有效期概念）
#   fact_embedding（事实向量挂在边上）    → 我们向量挂在条目上
#   → 升级方向：事实加 valid/invalid 双时间，支撑"当时 vs 现在"时序问答
# ============================================================================

from datetime import datetime
from pydantic import BaseModel, Field


class Edge(BaseModel, ABC):
    """边基类：源/目标节点 + 分组隔离。

    group_id：图分区键——多租户/多战役隔离（不同 group 的数据互不可见）。
    【可借鉴】我们长期库若要按"战役/演习"隔离，加一个 group 字段即可。
    """
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    group_id: str = Field(description='partition of the graph')
    source_node_uuid: str
    target_node_uuid: str
    created_at: datetime

    async def delete(self, driver: GraphDriver):
        """删除边——注意按 provider 分支写不同 Cypher（Kuzu vs Neo4j）。

        MENTIONS / RELATES_TO / HAS_MEMBER 三种关系标签对应：
          episode→entity 的"提及"、entity→entity 的"关系"、community→entity 的"成员"
        """
        if driver.provider == GraphProvider.KUZU:
            await driver.execute_query(
                "MATCH (n)-[e:MENTIONS|HAS_MEMBER {uuid: $uuid}]->(m) DELETE e",
                uuid=self.uuid)
            await driver.execute_query(
                "MATCH (e:RelatesToNode_ {uuid: $uuid}) DETACH DELETE e",
                uuid=self.uuid)
        else:  # Neo4j
            await driver.execute_query(
                "MATCH (n)-[e:MENTIONS|RELATES_TO|HAS_MEMBER {uuid: $uuid}]->(m) DELETE e",
                uuid=self.uuid)


class EpisodicEdge(Edge):
    """底层边：episode ↔ 它抽取出的 entity 的"提及"关系。

    【论文 §2】非损式设计的关键：原始 episode 永存，语义实体通过
    这类边回链到来源——"semantic artifact 可回溯到源 episode"。
    【对照我们】provenance() 是它的退化版（单字段 source 而非图回链）。
    """
    ...


class EntityEdge(Edge):
    """中层边：entity ↔ entity 的语义关系（Zep 的"事实"本体）。

    ★★★ 本文件最重要的类：五个字段构成 Zep 的全部时序魔法 ★★★
    """
    name: str = Field(description='name of the edge, relation name')
    fact: str = Field(description='fact representing the edge and nodes that it connects')
    fact_embedding: list[float] | None = Field(default=None,
        description='embedding of the fact')

    episodes: list[str] = Field(default=[],
        description='list of episode ids that reference these entity edges')
    # ↓ 这条边来自哪些 episode（反向索引：改写/失效时要知道动过谁）

    # ---- 双时态三时间（bi-temporal）——论文 §2.1 的核心创新 ----
    expired_at: datetime | None = Field(default=None,
        description='datetime of when the node was invalidated')
    #   系统时间维度：这条边**在图里**何时被判定过时（Zep 内部管理用）

    valid_at: datetime | None = Field(default=None,
        description='datetime of when the fact became true')
    #   现实时间维度：这个事实**在现实中**何时开始为真
    #   （"张三 2024-03 调任 2 营营长"——valid_at=2024-03）

    invalid_at: datetime | None = Field(default=None,
        description='datetime of when the fact stopped being true')
    #   现实时间维度：这个事实**在现实中**何时不再为真
    #   （"张三 2025-01 又调离"——上一条任职边的 invalid_at=2025-01）
    #
    # 【双时态的威力】查询"2024 年中张三在哪"：
    #   找 valid_at ≤ 2024-06 < invalid_at 的边 → 精确时序问答；
    #   普通向量库做不到（只有写入时间，无事实有效期）。
    # 【作战场景价值】"敌营长 3 月在 A 营 5 月调 B 营"——
    #   时序情报查询的关键结构。我们升级事实库时的首选设计。

    reference_time: datetime | None = Field(default=None,
        description='reference timestamp from the episode that produced this edge')
    #   产出该边的 episode 的参考时间（消息发送时刻）——归因用

    attributes: dict[str, Any] = Field(default={},
        description='Additional attributes of the edge. Dependent on edge name')
    #   扩展属性：不同关系名可挂不同字段（灵活 schema）

    async def generate_embedding(self, embedder: EmbedderClient):
        """事实文本向量化——**挂在边上而非节点上**！

        【设计精髓】检索粒度 = 事实（边），不是实体（节点）：
        "T-90 最大速度 60km/h"是一条边（T-90 --最大速度--> 60km/h），
        查"T-90 速度"直接命中最精确的事实单元。
        【对照我们】factual_store 的向量挂在条目（整行）上——
        若一条事实含多个三元组，检索粒度就粗了。
        """
        text = self.fact.replace('\n', ' ')
        self.fact_embedding = await embedder.create(input_data=[text])
        return self.fact_embedding


class CommunityEdge(Edge):
    """顶层边：community ↔ 成员 entity（"属于"关系）。

    对应论文 §2 的 community subgraph——GraphRAG 式的高层聚类视图。
    """
    ...

# ============================================================================
# 【给基础开发者的三条读懂线索】
# 1) Zep 时序 = 系统时间(expired_at) + 现实时间(valid_at/invalid_at) 双轴——
#    "数据何时入库"与"事实何时为真"是两回事，混用就无法做时序问答；
# 2) 向量挂边上（事实级检索）比挂节点上（实体级）粒度更细、命中更准；
# 3) episodes 反向索引（边→来源 episode 列表）：事实被后续消息**修正**时，
#    能找到"谁说的"做消解——冲突消解的数据基础。
# ============================================================================
