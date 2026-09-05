"""
GraphRAG engine -- Neo4j knowledge graph retrieval with Map-Reduce generation.

Data source: 知识图谱数据/ -> Neo4j graph database.
Provides entity query, relationship traversal, path reasoning capabilities.

Node labels: Entity, Community, CommunityReport, TextUnit
Relationship types: RELATED_TO, BELONGS_TO, CHILD_OF, HAS_REPORT
Note: GraphRAG auto-extracted relationships have no discrete types, all use RELATED_TO,
      relationship semantics stored in description field. Mission/Location reserved for future data.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from server.engines.base import BaseEngine
from server.engines.citation_utils import (
    CITATION_PROMPT, parse_citations,
)

import numpy as np

from server.config import settings

from server.engines.graph_rag._generation import _GraphRAGGeneration
from server.engines.graph_rag.context import (
    TokenBudget, estimate_tokens, compute_token_budget,
    fill_section, build_context_sections,
    DEFAULT_TOKEN_BUDGET, COMMUNITY_PROP, TEXT_UNIT_PROP, LOCAL_PROP,
)
from server.engines.graph_rag.prompts import (
    MODE_CLASSIFICATION_PROMPT,
)
from server.engines.reasoning_bus import reasoning_bus

logger = logging.getLogger("server.engines.graph_rag")

# Suppress Neo4j driver schema warnings (empty db / missing labels are expected)
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)
logging.getLogger("neo4j.io").setLevel(logging.ERROR)

# -- Vector search --
VECTOR_SEARCH_NPROBE = 16
VECTOR_SEARCH_OVERSEARCH = 3  # search top_k * N for dedup margin


class GraphRAGEngine(_GraphRAGGeneration, BaseEngine):
    """GraphRAG engine -- knowledge graph relational reasoning."""

    def __init__(self) -> None:
        super().__init__()
        self._driver = None
        self._available: bool | None = None
        self._available_check_time: float = 0.0
        self._AVAILABLE_TTL: float = 60.0  # availability cache TTL (seconds)
        self._neo4j_has_data: bool | None = None
        self._has_data_check_time: float = 0.0
        self._HAS_DATA_TTL: float = 60.0  # cache TTL (seconds)
        self._qdrant_client = None  # QdrantClient deferred init (vector search)

    @property
    def name(self) -> str:
        return "graph_rag"

    @property
    def engine_label(self) -> str:
        return "GraphRAG"

    @property
    def engine_color(self) -> str:
        return "#2980b9"

    async def check_availability(self) -> bool:
        """Probe Neo4j connection state（带 TTL 缓存，允许后端恢复后自动重连）。"""
        import time
        now = time.time()
        if self._available is not None and (now - self._available_check_time) < self._AVAILABLE_TTL:
            return self._available
        try:
            driver = self._get_driver()
            with driver.session() as session:
                session.run("RETURN 1", timeout=5)
            self._available = True
        except Exception as e:
            logger.warning(f"Neo4j unavailable: {e}, GraphRAG engine disabled")
            self._available = False
        self._available_check_time = now
        return self._available

    def _get_driver(self):
        """Get shared Neo4j sync driver (connection pool singleton)."""
        if self._driver is None:
            from server.neo4j_client import get_sync_driver
            self._driver = get_sync_driver()
        return self._driver

    def _get_qdrant_client(self):
        """Get shared QdrantClient (deferred init) for entity_embeddings vector search."""
        from server.engines.qdrant_client import get_qdrant_client
        return get_qdrant_client()

    async def _vector_search_entities(
        self, query: str, top_k: int = 15,
    ) -> List[Dict[str, Any]]:
        """Semantic similarity search on entity_embeddings vector store, returning matching entities.

        Uses rag_engine's embedding model to encode query, performs COSINE similarity
        search in Qdrant entity_embeddings collection.

        Returns:
            Standard search result list (metadata.type='entity').
            Returns empty list when embedding model unavailable or collection missing.
        """
        from server.engines.standard_rag import rag_engine
        from server.embedding_model import is_available as _embed_available

        try:
            import asyncio as _asyncio_vs

            # to_thread 包裹：首次调用可能触发模型冷加载，避免阻塞事件循环
            if not await _asyncio_vs.to_thread(_embed_available):
                logger.debug("Embedding model unavailable, skipping vector entity search")
                return []

            client = self._get_qdrant_client()
            # qdrant-client 1.18 无 has_collection，使用 collection_exists
            has_coll = await _asyncio_vs.to_thread(
                client.collection_exists, "entity_embeddings",
            )
            if not has_coll:
                logger.debug("entity_embeddings collection does not exist, skipping vector entity search")
                return []
        except Exception as e:
            logger.debug(f"Qdrant connection check failed, skipping vector search: {e}")
            return []

        try:
            import asyncio as _asyncio_vs

            embedding = await rag_engine._embed_query(query)
            if embedding is None or all(v == 0.0 for v in embedding):
                return []
        except Exception as e:
            logger.warning(f"Query embedding failed: {e}")
            return []

        # Search entity_embeddings (Qdrant loads collection on demand)
        try:
            import asyncio as _asyncio_vs

            results = await _asyncio_vs.to_thread(
                lambda: client.query_points(
                    collection_name="entity_embeddings",
                    query=embedding,
                    limit=top_k,
                    with_payload=True,
                ).points
            )
        except Exception as e:
            logger.warning(f"Qdrant vector search failed: {e}")
            return []

        # Convert to standard search result format
        entity_results: List[Dict[str, Any]] = []
        for hit in (results or []):
            payload = hit.payload or {}
            # 兼容扁平（compute_embeddings 写入）与嵌套（旧版）两种 payload 结构
            if isinstance(payload, dict) and isinstance(payload.get("entity"), dict):
                entity_data = payload["entity"]
            else:
                entity_data = payload if isinstance(payload, dict) else {}
            entity_name = entity_data.get("entity_name", "")
            entity_content = entity_data.get("content", "")
            raw_file_path = entity_data.get("file_path", "")
            # file_path may be kg_source (short directory name) or resolved source_file
            if raw_file_path and "/" in raw_file_path:
                source_file = raw_file_path  # resolved 半结构化数据 relative path
            elif raw_file_path:
                # 去掉可能已存在的 KG: 前缀，避免 [KG:[KG:xxx]] 双前缀
                kg_name = raw_file_path[3:] if raw_file_path.upper().startswith("KG:") else raw_file_path
                source_file = f"[KG:{kg_name}] Entity:{entity_name}"
            else:
                source_file = f"[GraphRAG] Entity:{entity_name}"

            if not entity_name:
                continue

            entity_results.append({
                "chunk_id": f"entity-vec-{entity_name}",
                "source_file": source_file,
                "content": entity_content or f"Entity: {entity_name}",
                "score": round(float(hit.score), 4),
                "engine": "graph_rag",
                "metadata": {"type": "entity", "name": entity_name},
            })

        logger.debug(
            f"Vector entity search: query='{query[:50]}...' -> {len(entity_results)} entities"
        )
        return entity_results

    async def _classify_query_mode(self, query: str) -> str:
        """LLM determines whether to use global or local search mode.

        Returns: "global" | "local"
        """
        import asyncio

        prompt = MODE_CLASSIFICATION_PROMPT.format(query=query)

        try:
            llm = self._get_llm()
            output = await asyncio.to_thread(llm.chat, prompt)
            return "global" if "global" in output.lower() else "local"
        except Exception as e:
            logger.warning(f"GraphRAG mode classification failed ({e}), defaulting to local")
            return "local"

    # -- Backward-compatible wrappers delegating to context.py --

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Token count heuristic for Chinese text (~2 chars per token).

        Consistent with the project-wide ``len(text) // 2`` pattern used in
        retrieval_router.py. This is approximate but sufficient for budget
        management.
        """
        return estimate_tokens(text)

    def _compute_token_budget(
        self, query: str, prompt_overhead: int = 0,
        budget_config: TokenBudget | None = None,
    ) -> dict:
        """Allocate token budget across context sections proportionally.

        Returns:
            {"communities": int, "text_units": int, "local": int}
            where "local" covers entities + relationships.
        """
        return compute_token_budget(query, prompt_overhead, budget_config)

    @staticmethod
    def _fill_section(
        items: list, budget: int, content_key: str = "content",
    ) -> tuple[str, list]:
        """Greedily fill items into a text section until token budget is exhausted.

        Returns:
            (section_text, consumed_items) -- consumed_items are the items that
            fit within the budget.
        """
        return fill_section(items, budget, content_key)

    def _build_context_sections(
        self, query: str, entities: list, text_units: list,
        relations: list, community_reports: list,
        budget_config: TokenBudget | None = None,
    ) -> tuple[str, list]:
        """Build a proportionally-allocated numbered context for local search.

        Returns:
            (context_str, context_items) -- context_items are consumed items
            for citation indexing (order matches sourceN in the prompt).
        """
        return build_context_sections(query, entities, text_units, relations, community_reports, budget_config)

    async def _compute_community_weights(
        self, matched_entities: list, community_reports: list,
    ) -> list:
        """Compute community weights by entity coverage and sort descending.

        Weight = matched entities belonging to community / total community entities (approximate).
        Used only for optimizing community_reports sort order, does not modify raw data.
        """
        if not community_reports or not matched_entities:
            return community_reports

        driver = self._get_driver()
        if not driver:
            return community_reports

        import asyncio

        matched_names: set[str] = set()
        for ent in matched_entities:
            name = ent.get("metadata", {}).get("name", "")
            if name:
                matched_names.add(name)

        if not matched_names:
            return community_reports

        try:
            def _get_community_sizes(tx, **kwargs):
                return list(tx.run(
                    "MATCH (c:Community)<-[:BELONGS_TO]-(e:Entity) "
                    "RETURN c.title AS community, count(e) AS total_entities"
                ))

            with driver.session() as session:
                sizes = await asyncio.to_thread(
                    session.execute_read, _get_community_sizes,
                )

            comm_total_map: dict[str, int] = {}
            for row in sizes:
                comm_total_map[row["community"]] = row["total_entities"]

            comm_match_map: dict[str, int] = {}
            for cr in community_reports:
                comm_name = cr.get("metadata", {}).get("community", "")
                if comm_name and comm_name in comm_total_map:
                    comm_match_map[comm_name] = 0

            # Count matched entity distribution across communities (single batch query)
            with driver.session() as session:
                def _count_matches_batch(tx, **kwargs):
                    return list(tx.run(
                        "MATCH (e:Entity)-[:BELONGS_TO]->(c:Community) "
                        "WHERE e.name IN $names "
                        "RETURN c.title AS community",
                        {"names": list(matched_names)[:20]},
                    ))
                rows = await asyncio.to_thread(
                    session.execute_read, _count_matches_batch,
                )
                for row in rows:
                    comm = row["community"]
                    if comm in comm_match_map:
                        comm_match_map[comm] += 1

            # Compute weights (without mutating input items)
            import math
            for cr in community_reports:
                comm_name = cr.get("metadata", {}).get("community", "")
                if comm_name and comm_name in comm_total_map:
                    total = comm_total_map.get(comm_name, 1)
                    matched = comm_match_map.get(comm_name, 0)
                    overlap = matched / max(total, 1)
                    weight = overlap * math.log(total + 1)
                    cr["_weight"] = weight

            # Sort by weight descending (sort copy to avoid mutating input order)
            return sorted(
                community_reports,
                key=lambda x: x.get("_weight", 0.0),
                reverse=True,
            )
        except Exception as e:
            logger.debug(f"Community weight computation failed, keeping original order: {e}")
            return community_reports

    def _extract_keywords(self, query: str) -> List[str]:
        """jieba segmentation -> filter stopwords/punctuation/single chars -> return keywords (max 10).

        Used to decompose natural language questions into Neo4j CONTAINS search terms.
        """
        import jieba

        # Common Chinese stopwords (pronouns/conjunctions/particles/question words)
        _STOP_WORDS = {
            "那些", "这些", "哪些", "那个", "这个", "哪个", "什么", "怎么",
            "如何", "怎样", "是否", "可以", "应该", "需要", "可能", "已经",
            "还有", "以及", "或者", "而且", "但是", "因为", "所以", "如果",
            "都", "是", "的", "了", "在", "和", "与", "或", "有", "没",
            "吗", "呢", "吧", "啊", "么", "不", "也", "就", "要", "会",
            "能", "可", "对", "从", "向", "把", "被", "让", "给", "为",
        }

        words = jieba.cut(query)
        keywords = []
        for w in words:
            w = w.strip()
            if len(w) >= 2 and w not in _STOP_WORDS:
                keywords.append(w)
        if not keywords:
            keywords = [query]
        return keywords[:10]

    async def search(
        self, query: str, top_k: int = 10, timeout: float = 8.0
    ) -> List[Dict[str, Any]]:
        """Execute graph search in Neo4j.

        Args:
            query: search query text
            top_k: number of results to return
            timeout: timeout in seconds

        Returns:
            Search result list (pure retrieval, no LLM generation)
        """
        import asyncio

        try:
            available = await self.check_availability()
            if not available:
                return []

            try:
                results = await asyncio.wait_for(
                    self._do_graph_search(query, top_k),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"GraphRAG graph search timeout ({timeout}s)")
                return []

            return results

        except asyncio.TimeoutError:
            logger.warning(f"GraphRAG search timeout ({timeout}s)")
            return []
        except Exception as e:
            logger.error(f"GraphRAG search exception: {e}")
            return []

    async def generate(
        self, query: str, top_k: int = 10, timeout: float = 8.0
    ) -> dict:
        """Complete GraphRAG search->generation pipeline."""
        import asyncio, time
        t0 = time.perf_counter()

        # 1. Search
        try:
            items = await asyncio.wait_for(
                self.search(query, top_k=top_k, timeout=timeout * 0.8),
                timeout=timeout * 0.8,
            )
        except (asyncio.TimeoutError, Exception):
            items = []

        retrieval_count = len(items)

        # 2. Build sources
        sources = []
        for i, item in enumerate(items):
            sources.append({
                "index": i + 1,
                "source_file": item.get("source_file", "unknown"),
                "engine": "graph_rag",
                "excerpt": (lambda s: s[:40] + "..." if len(s) > 40 else s)((item.get("content", "") or "").replace("\n", " ").replace("\r", " ")),
                "relevance_score": round(float(item.get("score", 0.0) or 0.0), 4),
            })

        # 3. LLM generation
        generated = await self._generate_answer(query, items)
        generated_text = generated["content"] if isinstance(generated, dict) else (generated if generated else "[GraphRAG] LLM generation failed.")
        citations = parse_citations(generated_text, len(sources))
        generated_text, citations = self._enforce_citations(generated_text, citations)

        return {
            "generated_text": generated_text,
            "citations": citations,
            "sources": sources,
            "retrieval_count": retrieval_count,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        }

    async def generate_stream(self, query: str, top_k: int = 10, timeout: float = 8.0):
        """Streaming GraphRAG search->generation pipeline."""
        import asyncio, time
        t0 = time.perf_counter()
        yield ("engine_start", dict(self._meta))

        # -- searching --
        yield ("engine_status", {"engine": "graph_rag", "phase": "searching"})
        try:
            items = await asyncio.wait_for(
                self.search(query, top_k=top_k, timeout=timeout * 0.8),
                timeout=timeout * 0.8,
            )
        except (asyncio.TimeoutError, Exception):
            items = []

        retrieval_count = len(items)

        # -- sources --
        sources = []
        for i, item in enumerate(items):
            sources.append({
                "index": i + 1,
                "source_file": item.get("source_file", "unknown"),
                "engine": "graph_rag",
                "excerpt": (lambda s: s[:40] + "..." if len(s) > 40 else s)((item.get("content", "") or "").replace("\n", " ").replace("\r", " ")),
                "relevance_score": round(float(item.get("score", 0.0) or 0.0), 4),
            })

        # -- generating --
        yield ("engine_status", {
            "engine": "graph_rag", "phase": "generating",
            "retrieval_count": retrieval_count,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        })

        # Classify results and build prompt
        entities = [r for r in items if r.get("metadata", {}).get("type") == "entity"]
        text_units = [r for r in items if r.get("metadata", {}).get("type") == "text_unit"]
        relations = [r for r in items if r.get("metadata", {}).get("type") == "relation"]
        communities = [r for r in items if r.get("metadata", {}).get("type") == "community"]
        community_reports = [r for r in items if r.get("metadata", {}).get("type") == "community_report"]

        # Community weight sorting (by entity coverage)
        if entities and community_reports:
            community_reports = await self._compute_community_weights(
                entities, community_reports,
            )

        mode = await self._classify_query_mode(query)

        # ── thinking: retrieval summary ──
        thinking_parts = [
            f"图谱检索完成，命中 {retrieval_count} 条结果",
            f"  实体: {len(entities)} | 文本单元: {len(text_units)} | 关系: {len(relations)} | 社区: {len(communities)}",
            f"  查询模式: {'全局分析 (map-reduce)' if mode == 'global' else '局部检索'}",
        ]
        # Show top matched entities
        if entities:
            thinking_parts.append("  Top 匹配实体:")
            for e in entities[:5]:
                name = e.get("metadata", {}).get("name", "?")
                score = e.get("score", 0)
                thinking_parts.append(f"    - {name} (score={score:.3f})")
        yield ("engine_token", {
            "engine": "graph_rag", "zone": "thinking",
            "delta": "\n".join(thinking_parts),
        })

        if mode == "global":
            # Announce map phase (parallel scoring per CommunityReport)
            yield ("engine_status", {
                "engine": "graph_rag", "phase": "mapping",
                "retrieval_count": retrieval_count,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            })
            prompt, map_meta = await self._build_global_prompt(
                query, community_reports, entities,
            )
            # ── thinking: mapping complete ──
            map_valid = len(map_meta) if map_meta else 0
            map_total = len(community_reports) if community_reports else 0
            thinking_parts = [
                f"社区报告并行映射完成: {map_valid}/{map_total} 份有效 (score>0)",
            ]
            if map_meta:
                for i, mr in enumerate(map_meta[:3]):
                    thinking_parts.append(
                        f"  [{i+1}] {mr.get('title', '?')} (评分={mr.get('score', 0)})"
                    )
            yield ("engine_token", {
                "engine": "graph_rag", "zone": "thinking",
                "delta": "\n".join(thinking_parts),
            })
            # Announce reduce (generation) phase start
            yield ("engine_status", {
                "engine": "graph_rag", "phase": "generating",
                "retrieval_count": retrieval_count,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            })
        else:
            prompt = self._build_local_prompt(query, entities, text_units, relations, communities)

        full_parts: list[str] = []
        try:
            llm = self._get_llm()
            async for chunk in llm.achat_stream(prompt):
                full_parts.append(chunk)
                yield ("engine_token", {"engine": "graph_rag", "delta": chunk})
            generated_text = "".join(full_parts)
        except Exception as e:
            generated_text = f"[GraphRAG] LLM call exception: {e}"
            yield ("engine_token", {"engine": "graph_rag", "delta": generated_text})

        citations = parse_citations(generated_text, len(sources))
        generated_text, citations = self._enforce_citations(generated_text, citations)

        yield ("engine_done", {
            **self._meta, "status": "ok",
            "generated_text": generated_text,
            "citations": citations, "sources": sources,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "retrieval_count": retrieval_count,
        })

    async def _do_graph_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Execute graph search (entity matching + relationship traversal + community context)."""
        import asyncio

        driver = self._get_driver()
        if not driver:
            return []

        # Quick check: if Neo4j has no Entity nodes, return empty (with TTL cache)
        now = time.time()
        if self._neo4j_has_data is None or (now - self._has_data_check_time) > self._HAS_DATA_TTL:
            def _check_has_data(tx, **kwargs):
                result = tx.run("MATCH (e:Entity) RETURN count(e) > 0 AS has_data LIMIT 1")
                record = result.single()
                return record and record["has_data"]

            try:
                with driver.session() as check_session:
                    has_data = await asyncio.to_thread(check_session.execute_read, _check_has_data)
                    self._neo4j_has_data = bool(has_data)
                    self._has_data_check_time = now
            except Exception as e:
                logger.debug(f"Neo4j data check failed: {e}")
                self._neo4j_has_data = False
                self._has_data_check_time = now

        if not self._neo4j_has_data:
            return []

        keywords = self._extract_keywords(query)

        results = []

        def _run_cypher(tx, cypher: str, params: dict) -> list:
            return list(tx.run(cypher, params))

        # Extract search keywords from natural language query
        keywords = self._extract_keywords(query)
        if not keywords:
            keywords = [query]  # fallback: use raw query directly

        logger.debug(f"GraphRAG keyword extraction: \"{query}\" -> {keywords}")
        reasoning_bus.emit_simple(
            engine="graph_rag", phase="searching",
            content=f"关键词提取: {', '.join(keywords[:8])}",
            extra={"keywords": keywords[:8]},
        )

        # -- Step 0: Vector semantic entity search (priority, fallback to keyword match on failure) --
        vector_entities = await self._vector_search_entities(
            query, top_k=top_k * VECTOR_SEARCH_OVERSEARCH,
        )
        vector_entity_names: set[str] = set()
        if vector_entities:
            # Mark vector-retrieved entity names, skip keyword entity search later
            vector_entity_names = {
                e.get("metadata", {}).get("name", "") for e in vector_entities
            }
            vector_entity_names.discard("")
            results.extend(vector_entities)
            logger.info(
                f"GraphRAG vector entity search hit: {len(vector_entity_names)} entities"
            )
            reasoning_bus.emit_simple(
                engine="graph_rag", phase="searching",
                content=f"向量语义搜索命中 {len(vector_entity_names)} 个实体",
                extra={"vector_entities": len(vector_entity_names)},
            )

        with driver.session() as session:
            # Step 1a: Entity search -- match related entities (multi-keyword OR, sort by match count)
            # When vector search succeeds, use as supplement (fewer keyword results); otherwise primary
            keyword_entity_limit = (
                top_k  # keyword supplement (fewer results when vector succeeded)
                if vector_entities else top_k * 3
            )
            kw_clauses = " OR ".join(
                f"(e.name CONTAINS $kw{i} OR e.description CONTAINS $kw{i} OR e.type CONTAINS $kw{i})"
                for i in range(len(keywords))
            )
            score_terms = " + ".join(
                f"(CASE WHEN e.name CONTAINS $kw{i} THEN 2 "
                f"WHEN e.description CONTAINS $kw{i} THEN 1 "
                f"ELSE 0 END)"
                for i in range(len(keywords))
            )
            entity_cypher = f"""
                MATCH (e:Entity)
                WHERE {kw_clauses}
                WITH e, ({score_terms}) AS match_score
                OPTIONAL MATCH (e)-[:MENTIONED_IN]->(tu:TextUnit)
                WITH e, match_score, collect(DISTINCT tu.source_file)[0] AS source_file
                RETURN e.id AS entity_id, e.name AS name,
                       e.type AS type, e.description AS description,
                       e.kg_source AS kg_source,
                       match_score, source_file
                ORDER BY match_score DESC
                LIMIT $limit
            """
            params = {f"kw{i}": kw for i, kw in enumerate(keywords)}
            params["limit"] = keyword_entity_limit
            keyword_entities = await asyncio.to_thread(
                _run_cypher, session, entity_cypher, params,
            )

            # Filter out vector-matched entities to avoid duplicates
            for ent in keyword_entities:
                ent_name = ent.get("name", "")
                if ent_name in vector_entity_names:
                    continue  # vector already hit, skip keyword result
                match_count = ent.get("match_score", 0) or 0
                # Resolve source_file: prefer TextUnit's resolved source_file,
                # fall back to [KG:kg_source] marker with entity name
                tu_source = ent.get("source_file", "")
                kg_source = ent.get("kg_source", "")
                if tu_source:
                    source_file = tu_source
                elif kg_source:
                    source_file = f"[KG:{kg_source}] Entity:{ent['name']}"
                else:
                    source_file = f"[GraphRAG] Entity:{ent['name']}"
                results.append({
                    "chunk_id": f"entity-{ent['entity_id']}",
                    "source_file": source_file,
                    "content": f"Entity: {ent['name']} (type: {ent['type']})\n{ent.get('description', '')}",
                    "score": 0.5 + 0.075 * min(match_count or 0, 6),
                    "engine": "graph_rag",
                    "metadata": {"type": "entity", "name": ent["name"]},
                })

            # Build unified entity list for subsequent graph traversal (vector + keyword)
            # First look up Neo4j entity_ids for vector entity names, then merge keyword results
            all_neo4j_entities: list = list(keyword_entities)  # keyword entities already have full fields
            if vector_entity_names:
                # Look up Neo4j entity_ids for vector entities (for relationship traversal)
                lookup_names = list(vector_entity_names)[:top_k * 2]
                name_placeholders = ", ".join(
                    f"$vn{i}" for i in range(len(lookup_names))
                )
                lookup_params = {
                    f"vn{i}": name for i, name in enumerate(lookup_names)
                }
                vec_lookup_cypher = f"""
                    MATCH (e:Entity)
                    WHERE e.name IN [{name_placeholders}]
                    RETURN e.id AS entity_id, e.name AS name,
                           e.type AS type, e.description AS description
                """
                vec_neo4j_entities = await asyncio.to_thread(
                    _run_cypher, session, vec_lookup_cypher, lookup_params,
                )
                # Insert vector-found entities before keyword entities, prioritize graph traversal
                existing_ids = {e["entity_id"] for e in all_neo4j_entities}
                for ent in vec_neo4j_entities:
                    if ent["entity_id"] not in existing_ids:
                        all_neo4j_entities.insert(0, ent)
                        existing_ids.add(ent["entity_id"])

            # Step 1b: TextUnit search -- match document source text content
            text_kw_clauses = " OR ".join(
                f"tu.text CONTAINS $kw{i}" for i in range(len(keywords))
            )
            text_unit_cypher = f"""
                MATCH (tu:TextUnit)
                WHERE {text_kw_clauses}
                RETURN tu.id AS id, tu.text AS text, tu.n_tokens AS n_tokens,
                       tu.source_file AS source_file, tu.kg_source AS kg_source
                LIMIT $limit
            """
            text_units = await asyncio.to_thread(
                _run_cypher, session, text_unit_cypher, params,
            )

            for tu in text_units:
                tu_source = tu.get("source_file", "") or ""
                kg_source = tu.get("kg_source", "")
                if tu_source:
                    source_file = tu_source
                elif kg_source:
                    source_file = f"[KG:{kg_source}]"
                else:
                    source_file = "[GraphRAG] TextUnit"
                results.append({
                    "chunk_id": f"textunit-{tu['id']}",
                    "source_file": source_file,
                    "content": f"Text fragment (tokens: {tu.get('n_tokens', 0)})\n{tu.get('text', '')[:500]}",
                    "score": 0.65,
                    "engine": "graph_rag",
                    "metadata": {"type": "text_unit", "text_unit_id": tu["id"]},
                })

            # Step 1c: CommunityReport search -- match community summaries
            cr_kw_clauses_summary = " OR ".join(
                f"cr.summary CONTAINS $kw{i}" for i in range(len(keywords))
            )
            cr_kw_clauses_full = " OR ".join(
                f"cr.full_content CONTAINS $kw{i}" for i in range(len(keywords))
            )
            cr_cypher = f"""
                MATCH (cr:CommunityReport)
                WHERE {cr_kw_clauses_summary}
                   OR {cr_kw_clauses_full}
                RETURN cr.id AS id, cr.title AS title, cr.summary AS summary
                LIMIT $limit
            """
            community_reports = await asyncio.to_thread(
                _run_cypher, session, cr_cypher, params,
            )

            for cr in community_reports:
                results.append({
                    "chunk_id": f"cr-{cr['id']}",
                    "source_file": f"[GraphRAG] CommunityReport:{cr.get('title', cr['id'])}",
                    "content": f"Community summary: {cr.get('title', 'N/A')}\n{cr.get('summary', '')[:500]}",
                    "score": 0.55,
                    "engine": "graph_rag",
                    "metadata": {"type": "community_report", "report_id": cr["id"]},
                })

            # Step 2: Relationship expansion -- find relationships related to matched entities (sorted by weight)
            if all_neo4j_entities:
                entity_ids = [e["entity_id"] for e in all_neo4j_entities[:3]]
                relation_cypher = """
                    MATCH (e1:Entity)-[r]->(e2:Entity)
                    WHERE e1.id IN $entity_ids
                    RETURN e1.name AS source, type(r) AS relation,
                           e2.name AS target, r AS props
                    ORDER BY r.weight DESC
                    LIMIT $limit
                """
                relations = await asyncio.to_thread(
                    _run_cypher, session, relation_cypher,
                    {"entity_ids": entity_ids, "limit": top_k},
                )

                for rel in relations:
                    results.append({
                        "chunk_id": f"rel-{rel['source']}-{rel['relation']}",
                        "source_file": f"[GraphRAG] Relation:{rel['source']}-{rel['relation']}->{rel['target']}",
                        "content": f"Relation: {rel['source']} -[{rel['relation']}]-> {rel['target']}",
                        "score": 0.65,
                        "engine": "graph_rag",
                        "metadata": {
                            "type": "relation",
                            "source": rel["source"],
                            "relation": rel["relation"],
                            "target": rel["target"],
                        },
                    })

            # Step 3: Community context enhancement -- query community summaries for entity communities
            if all_neo4j_entities:
                entity_ids = [e["entity_id"] for e in all_neo4j_entities[:5]]
                community_cypher = """
                    MATCH (e:Entity)-[:BELONGS_TO]->(c:Community)
                    WHERE e.id IN $entity_ids
                    OPTIONAL MATCH (c)-[:HAS_REPORT]->(cr:CommunityReport)
                    RETURN c.title AS community, cr.summary AS community_summary,
                           cr.full_content AS community_full_content, c.level AS level
                    ORDER BY c.level ASC
                    LIMIT $limit
                """
                communities = await asyncio.to_thread(
                    _run_cypher, session, community_cypher,
                    {"entity_ids": entity_ids, "limit": top_k},
                )

                for comm in communities:
                    summary = comm.get("community_summary") or ""
                    full_content = comm.get("community_full_content") or ""
                    community_title = comm.get("community") or ""
                    if community_title:
                        content_parts = [f"Community: {community_title} (level: {comm.get('level', 'N/A')})"]
                        if summary:
                            content_parts.append(f"Summary: {summary}")
                        if full_content and full_content != summary:
                            content_parts.append(f"Details: {full_content[:500]}")
                        results.append({
                            "chunk_id": f"community-{community_title}",
                            "source_file": f"[GraphRAG] Community:{community_title}",
                            "content": "\n".join(content_parts),
                            "score": 0.55,
                            "engine": "graph_rag",
                            "metadata": {
                                "type": "community",
                                "community": community_title,
                                "level": comm.get("level"),
                            },
                        })

            # Step 4a: Mission query -- match related combat missions (multi-keyword OR)
            mission_kw_clauses = " OR ".join(
                f"(m.name CONTAINS $kw{i} OR m.type CONTAINS $kw{i})"
                for i in range(len(keywords))
            )
            mission_cypher = f"""
                MATCH (m:Mission)
                WHERE {mission_kw_clauses}
                RETURN m.id AS mission_id, m.name AS name,
                       m.type AS type, m.phase AS phase
                LIMIT $limit
            """
            missions = await asyncio.to_thread(
                _run_cypher, session, mission_cypher, params,
            )

            for m in missions:
                results.append({
                    "chunk_id": f"mission-{m['mission_id']}",
                    "source_file": f"[GraphRAG] Mission:{m.get('name', m['mission_id'])}",
                    "content": f"Combat mission: {m.get('name', 'N/A')} (type: {m.get('type', 'N/A')}, phase: {m.get('phase', 'N/A')})",
                    "score": 0.65,
                    "engine": "graph_rag",
                    "metadata": {
                        "type": "mission",
                        "mission_id": m["mission_id"],
                        "phase": m.get("phase"),
                    },
                })

            # Step 4b: TextUnit full-text search -- match original document fragments containing keywords
            if keywords:
                text_unit_cypher = (
                    "MATCH (tu:TextUnit) WHERE "
                    + " OR ".join(
                        [f"tu.text CONTAINS $kw{i}" for i in range(len(keywords))]
                    )
                    + " RETURN tu.id AS tu_id, tu.text AS text, tu.n_tokens AS n_tokens,"
                    + " tu.source_file AS source_file, tu.kg_source AS kg_source"
                    + " LIMIT $limit"
                )
                text_units = await asyncio.to_thread(
                    _run_cypher, session, text_unit_cypher,
                    {**params, "limit": top_k},
                )

                for tu in text_units:
                    tu_text = tu.get("text", "")
                    if tu_text.strip():
                        tu_source = tu.get("source_file", "") or ""
                        kg_source = tu.get("kg_source", "")
                        if tu_source:
                            source_file = tu_source
                        elif kg_source:
                            source_file = f"[KG:{kg_source}]"
                        else:
                            source_file = "[GraphRAG] TextUnit"
                        results.append({
                            "chunk_id": f"textunit-{tu['tu_id']}",
                            "source_file": source_file,
                            "content": tu_text[:800],
                            "score": 0.75,
                            "engine": "graph_rag",
                            "metadata": {
                                "type": "text_unit",
                                "tu_id": tu["tu_id"],
                                "n_tokens": tu.get("n_tokens", 0),
                            },
                        })

        # Dedup: multiple entry points may return same content
        seen = set()
        deduped = []
        for item in results:
            cid = item["chunk_id"]
            if cid not in seen:
                seen.add(cid)
                deduped.append(item)
        results = deduped

        # 统计各类结果数
        entity_count = sum(1 for r in results if r.get("metadata", {}).get("type") == "entity")
        tu_count = sum(1 for r in results if r.get("metadata", {}).get("type") == "text_unit")
        rel_count = sum(1 for r in results if r.get("metadata", {}).get("type") == "relation")
        com_count = sum(1 for r in results if r.get("metadata", {}).get("type") in ("community", "community_report"))
        reasoning_bus.emit_simple(
            engine="graph_rag", phase="searching",
            content=f"图谱检索完成: 实体{entity_count} | 文本单元{tu_count} | 关系{rel_count} | 社区{com_count} | 去重后共{len(results)}条",
            extra={"entities": entity_count, "text_units": tu_count,
                   "relations": rel_count, "communities": com_count,
                   "total": len(results)},
        )

        return results

    async def import_from_kg(self, kg_path: str, batch_size: int | None = None) -> Dict[str, Any]:
        """Parse GraphRAG knowledge graph from 知识图谱数据/ and import into Neo4j.

        Data source is parquet files from GraphRAG index output (output/ per subdirectory):
          - create_final_entities.parquet: id, title, type, description
          - create_final_relationships.parquet: source(title), target(title),
            description, weight
          - create_final_communities.parquet: id, community, parent, level, title, entity_ids, size
          - create_final_community_reports.parquet: id, community, title, summary, full_content, rank
          - create_final_text_units.parquet: id, text, n_tokens, entity_ids
          - create_final_nodes.parquet: id, title, community, level, degree

        Mapping strategy (per design doc Neo4j model):
          - Entities -> :Entity {id, name, type, description, kg_source}
          - Relations -> :RELATED_TO {description, weight, kg_source}
            (GraphRAG relations have no discrete types, all use RELATED_TO with description)
          - Communities -> :Community {id, community_id, level, title, size, kg_source}
          - Community summaries -> :CommunityReport {id, title, summary, full_content, rank, kg_source}
          - Text units -> :TextUnit {id, text, n_tokens, kg_source}

        Features: MERGE idempotent import, batched (default 500), unique constraints
        before import, graceful degradation when Neo4j unavailable.

        Args:
            kg_path: 知识图谱数据 directory path
            batch_size: batch size (default from settings.neo4j.import_batch_size)

        Returns:
            Import statistics dict
        """
        import asyncio
        from pathlib import Path

        if batch_size is None:
            batch_size = getattr(settings.neo4j, "import_batch_size", 500)

        stats: Dict[str, Any] = {
            "kgs": [],
            "entities": 0,
            "relationships": 0,
            "skipped_relationships": 0,
            "communities": 0,
            "community_reports": 0,
            "text_units": 0,
        }

        available = await self.check_availability()
        if not available:
            logger.warning("Neo4j unavailable, skipping KG import")
            return stats

        kg_dir = Path(kg_path)
        if not kg_dir.exists():
            logger.warning(f"KG directory does not exist: {kg_path}")
            return stats

        kg_outputs = self._discover_kg_outputs(kg_dir)
        if not kg_outputs:
            logger.warning(f"No GraphRAG output directories found under {kg_path} (output/*.parquet)")
            return stats

        try:
            driver = self._get_driver()
        except Exception as e:
            logger.warning(f"Neo4j driver init failed, skipping KG import: {e}")
            return stats

        # Establish unique constraint indexes before import
        await asyncio.to_thread(self._ensure_constraints, driver)

        logger.info(f"Starting KG import: found {len(kg_outputs)} graphs -> {list(kg_outputs)}")

        for name, out_dir in kg_outputs.items():
            try:
                kg_stats = await asyncio.to_thread(
                    self._import_single_kg, driver, name, out_dir, batch_size
                )
                stats["kgs"].append(name)
                stats["entities"] += kg_stats["entities"]
                stats["relationships"] += kg_stats["relationships"]
                stats["skipped_relationships"] += kg_stats["skipped_relationships"]
                stats["communities"] += kg_stats.get("communities", 0)
                stats["community_reports"] += kg_stats.get("community_reports", 0)
                stats["text_units"] += kg_stats.get("text_units", 0)
                logger.info(
                    f"KG[{name}] import complete: {kg_stats['entities']} entities, "
                    f"{kg_stats['relationships']} relations (skipped {kg_stats['skipped_relationships']} unmatchable), "
                    f"{kg_stats.get('communities', 0)} communities, "
                    f"{kg_stats.get('community_reports', 0)} community reports, "
                    f"{kg_stats.get('text_units', 0)} text units"
                )
            except Exception as e:
                logger.error(f"KG[{name}] import failed: {e}")

        logger.info(
            f"Neo4j KG import total: {stats['entities']} entities, "
            f"{stats['relationships']} relations, {stats['communities']} communities, "
            f"{stats['community_reports']} community reports, {stats['text_units']} text units, "
            f"from {len(stats['kgs'])} graphs"
        )

        # Update cache flag after successful import
        if stats["entities"] > 0:
            self._neo4j_has_data = True
            self._has_data_check_time = time.time()

        return stats

    async def compute_embeddings(self) -> Dict[str, int]:
        """Compute embeddings from Neo4j Entity + RELATED_TO and write to Qdrant shared collections.

        Two new data foundation members:
          - entity_embeddings: entity name+description vectors, source_id linked to TextUnit
          - relation_embeddings: relation triple vectors, source_id linked to both entity TextUnits

        Idempotent: uses md5 hash as primary key, repeated calls won't duplicate writes.
        """
        import hashlib
        import asyncio as _asyncio

        from server.config import settings
        from server.engines.standard_rag import rag_engine
        GRAPH_FIELD_SEP = "<SEP>"  # LightRAG chunk ID separator

        stats = {"entities": 0, "relations": 0}

        available = await self.check_availability()
        if not available:
            logger.warning("Neo4j unavailable, skipping embedding computation")
            return stats

        from server.embedding_model import is_available as _embed_available
        # to_thread 包裹：模型冷加载不进事件循环，与其它检索路径一致
        if not await _asyncio.to_thread(_embed_available):
            logger.warning("Embedding model unavailable, skipping embedding computation")
            return stats

        from qdrant_client import QdrantClient
        from qdrant_client.models import VectorParams, Distance, PointStruct

        qdrant_url = f"http://{settings.qdrant.host}:{settings.qdrant.port}"
        client = QdrantClient(url=qdrant_url, timeout=settings.qdrant.timeout)

        # Wrap synchronous Qdrant operations
        async def _qdrant_create_collection(name: str) -> None:
            await _asyncio.to_thread(
                client.create_collection,
                collection_name=name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

        async def _qdrant_upsert(name: str, points_data: list) -> None:
            pts = []
            for d in points_data:
                payload = {k: v for k, v in d.items() if k not in ("id", "vector")}
                pts.append(PointStruct(id=d["id"], vector=d["vector"], payload=payload))
            await _asyncio.to_thread(client.upsert, collection_name=name, points=pts)

        dim = settings.qdrant.dimension
        now_ts = int(time.time())

        # ── 快速检查：Qdrant 已有足够 embedding 则跳过 ──
        driver = self._get_driver()

        async def _qdrant_point_count(coll_name: str) -> int:
            """获取 Qdrant collection 的 points 数量。"""
            info = await _asyncio.to_thread(client.get_collection, coll_name)
            return info.points_count or 0

        # Neo4j 实体数 vs Qdrant entity_embeddings 行数
        # 使用 DISTINCT 实体名：不同 KG 来源的同名实体共享同一 PK（md5("ent:{name}")），
        # 因此 Qdrant 行数 == Neo4j 唯一实体名数，而非总实体数
        entity_coll = "entity_embeddings"
        neo4j_entity_count = 0

        def _count_entities(tx, **kwargs):
            return tx.run("MATCH (e:Entity) RETURN count(DISTINCT e.name) AS cnt").single()["cnt"]

        with driver.session(database="neo4j") as session:
            neo4j_entity_count = await _asyncio.to_thread(
                session.execute_read, _count_entities
            )

        rel_coll = "relation_embeddings"
        qdrant_entity_count = 0
        if await _asyncio.to_thread(client.collection_exists, entity_coll):
            qdrant_entity_count = await _qdrant_point_count(entity_coll)

        if qdrant_entity_count > 0 and qdrant_entity_count == neo4j_entity_count:
            qdrant_rel_count = 0
            if await _asyncio.to_thread(client.collection_exists, rel_coll):
                qdrant_rel_count = await _qdrant_point_count(rel_coll)
            logger.info(
                f"Embeddings up to date "
                f"(entities: {neo4j_entity_count}, relations: {qdrant_rel_count}), "
                f"skip recompute"
            )
            # 确保 collection 存在（Qdrant 重启后数据持久）
            return {"entities": qdrant_entity_count, "relations": qdrant_rel_count}

        # -- entity_embeddings collection --
        if not await _asyncio.to_thread(client.collection_exists, entity_coll):
            await _qdrant_create_collection(entity_coll)
            logger.info(f"Created Qdrant collection: {entity_coll}")

        # -- relation_embeddings collection --
        rel_coll = "relation_embeddings"
        if not await _asyncio.to_thread(client.collection_exists, rel_coll):
            await _qdrant_create_collection(rel_coll)
            logger.info(f"Created Qdrant collection: {rel_coll}")

        driver = self._get_driver()

        # -- 0. Resolve TextUnit → 半结构化数据 source_file (content matching) --
        logger.info("Resolving TextUnit source files...")
        tu_source_map = await self._resolve_textunit_source_files()
        logger.info(
            f"TextUnit source resolution: {len(tu_source_map)} TextUnits resolved"
        )

        # -- 0.5 Preload entity -> TextUnit mapping --
        logger.info("Building entity->TextUnit mapping...")
        entity_tu_map: dict[str, list[str]] = {}

        def _read_entity_textunits(tx, **kwargs):
            result = tx.run(
                "MATCH (e:Entity)-[:MENTIONED_IN]->(tu:TextUnit) "
                "RETURN e.name AS entity_name, tu.id AS tu_id"
            )
            return list(result)

        with driver.session(database="neo4j") as session:
            tu_rows = await _asyncio.to_thread(
                session.execute_read, _read_entity_textunits
            )

        for row in tu_rows:
            ename = row.get("entity_name", "")
            tuid = row.get("tu_id", "")
            if ename and tuid:
                if ename not in entity_tu_map:
                    entity_tu_map[ename] = []
                entity_tu_map[ename].append(tuid)

        logger.info(
            f"Entity->TextUnit mapping: {len(entity_tu_map)} entities, "
            f"{sum(len(v) for v in entity_tu_map.values())} total links"
        )

        # -- 0.3: Build entity -> source_file mapping from TextUnit nodes --
        entity_source_map: dict[str, str] = {}
        if tu_source_map:
            def _read_entity_sources(tx, **kwargs):
                result = tx.run(
                    "MATCH (e:Entity)-[:MENTIONED_IN]->(tu:TextUnit) "
                    "WHERE tu.source_file IS NOT NULL AND tu.source_file <> '' "
                    "WITH e.name AS name, tu.source_file AS sf "
                    "WITH name, collect(DISTINCT sf) AS sfs "
                    "RETURN name, sfs[0] AS source_file"
                )
                return {r["name"]: r.get("source_file", "") or "" for r in result}

            with driver.session(database="neo4j") as session:
                entity_source_map = await _asyncio.to_thread(
                    session.execute_read, _read_entity_sources
                )
            logger.info(
                f"Entity->source_file mapping: {len(entity_source_map)} entities resolved"
            )
        else:
            logger.info("No TextUnit source_file data, entity_source_map will be empty")

        # -- 0.5: Write source_id to Neo4j Entity nodes --
        # LightRAG's _get_node_data merge expects source_id from graph node properties.
        # Entity embedding source_id is discarded during merge, so must write to Neo4j.
        logger.info("Writing entity source_id to Neo4j...")
        if entity_tu_map:
            batch_rows = [
                {"name": ename, "source_id": GRAPH_FIELD_SEP.join(tuids)}
                for ename, tuids in entity_tu_map.items() if tuids
            ]

            def _write_source_ids(tx, rows, **kwargs):
                tx.run(
                    """
                    UNWIND $rows AS row
                    MATCH (e:Entity {name: row.name})
                    SET e.source_id = row.source_id
                    """,
                    rows=rows,
                ).consume()

            with driver.session(database="neo4j") as session:
                for i in range(0, len(batch_rows), 200):
                    batch = batch_rows[i : i + 200]
                    await _asyncio.to_thread(
                        session.execute_write, _write_source_ids, batch
                    )
            logger.info(f"Source_id written for {len(batch_rows)} entities")

        # -- 1. Entity embeddings (batch encoding) --
        logger.info("Computing entity embeddings (batch mode)...")
        entity_total = 0

        def _read_entities(tx, **kwargs):
            result = tx.run(
                "MATCH (e:Entity) RETURN e.name AS name, e.type AS type, "
                "e.description AS description, e.kg_source AS kg_source"
            )
            return list(result)

        with driver.session(database="neo4j") as session:
            entities = await _asyncio.to_thread(session.execute_read, _read_entities)

        # Collect all entity texts and metadata, batch encode
        entity_texts: list[str] = []
        entity_metas: list[dict] = []
        for ent in entities:
            name = ent.get("name", "")
            if not name:
                continue
            etype = ent.get("type", "")
            description = ent.get("description", "")
            kg_source = ent.get("kg_source", "")
            tu_ids = entity_tu_map.get(name, [])
            source_id = GRAPH_FIELD_SEP.join(tu_ids) if tu_ids else ""

            text = f"{name} (type: {etype}): {description}"
            entity_texts.append(text)
            entity_metas.append({
                "name": name, "text": text, "source_id": source_id,
                "kg_source": kg_source,
            })

        if entity_texts:
            total_entities = len(entity_texts)
            logger.info(f"  Batch-encoding {total_entities} entities (batch_size=64)...")
            entity_embeddings = await rag_engine._embed_batch(
                entity_texts, batch_size=64,
                progress_label=f"Entity embeddings",
            )
            logger.info(f"  Writing {total_entities} entity embeddings to Qdrant...")
            entity_batch = []
            for i, (meta, embedding) in enumerate(zip(entity_metas, entity_embeddings)):
                record_id = hashlib.md5(f"ent:{meta['name']}".encode()).hexdigest()[:32]
                entity_batch.append({
                    "id": record_id,
                    "vector": embedding,
                    "entity_name": meta["name"],
                    "content": meta["text"],
                    "source_id": meta["source_id"],
                    "file_path": entity_source_map.get(meta["name"], meta["kg_source"] or ""),
                    "created_at": now_ts,
                })
                entity_total += 1
                if len(entity_batch) >= 100:
                    await _qdrant_upsert(entity_coll, entity_batch)
                    logger.info(
                        f"  Entity upsert progress: {entity_total}/{total_entities} "
                        f"({entity_total * 100 // total_entities}%)"
                    )
                    entity_batch = []
            if entity_batch:
                await _qdrant_upsert(entity_coll, entity_batch)

        stats["entities"] = entity_total
        logger.info(
            f"Entity embeddings completed: {entity_total} "
            f"(with TextUnit links: {sum(1 for v in entity_tu_map.values() if v)})"
        )

        # -- 2. Relation embeddings (batch encoding) --
        logger.info("Computing relation embeddings (batch mode)...")
        rel_total = 0

        def _read_relations(tx, **kwargs):
            result = tx.run(
                "MATCH (s:Entity)-[r:RELATED_TO]->(t:Entity) "
                "RETURN s.name AS src_name, t.name AS tgt_name, "
                "r.description AS description, r.weight AS weight, "
                "s.kg_source AS kg_source"
            )
            return list(result)

        with driver.session(database="neo4j") as session:
            relations = await _asyncio.to_thread(session.execute_read, _read_relations)

        # Collect all relation texts and metadata, batch encode
        rel_texts: list[str] = []
        rel_metas: list[dict] = []
        for rel in relations:
            src_name = rel.get("src_name", "")
            tgt_name = rel.get("tgt_name", "")
            description = rel.get("description", "")
            kg_source = rel.get("kg_source", "")
            if not src_name or not tgt_name:
                continue

            src_tus = entity_tu_map.get(src_name, [])
            tgt_tus = entity_tu_map.get(tgt_name, [])
            all_tus = list(dict.fromkeys(src_tus + tgt_tus))
            source_id = GRAPH_FIELD_SEP.join(all_tus) if all_tus else ""

            text = f"{src_name} -> {tgt_name}: {description}"
            rel_texts.append(text)
            rel_metas.append({
                "src_name": src_name, "tgt_name": tgt_name,
                "text": text, "source_id": source_id,
                "kg_source": kg_source,
            })

        if rel_texts:
            total_relations = len(rel_texts)
            logger.info(f"  Batch-encoding {total_relations} relations (batch_size=64)...")
            rel_embeddings = await rag_engine._embed_batch(
                rel_texts, batch_size=64,
                progress_label=f"Relation embeddings",
            )
            logger.info(f"  Writing {total_relations} relation embeddings to Qdrant...")
            rel_batch = []
            for i, (meta, embedding) in enumerate(zip(rel_metas, rel_embeddings)):
                record_id = hashlib.md5(
                    f"rel:{meta['src_name']}:{meta['tgt_name']}".encode()
                ).hexdigest()[:32]
                rel_batch.append({
                    "id": record_id,
                    "vector": embedding,
                    "src_id": meta["src_name"],
                    "tgt_id": meta["tgt_name"],
                    "content": meta["text"],
                    "source_id": meta["source_id"],
                    "file_path": entity_source_map.get(
                        meta["src_name"],
                        entity_source_map.get(meta["tgt_name"], meta["kg_source"] or ""),
                    ),
                    "created_at": now_ts,
                })
                rel_total += 1
                if len(rel_batch) >= 100:
                    await _qdrant_upsert(rel_coll, rel_batch)
                    logger.info(
                        f"  Relation upsert progress: {rel_total}/{total_relations} "
                        f"({rel_total * 100 // total_relations}%)"
                    )
                    rel_batch = []
            if rel_batch:
                await _qdrant_upsert(rel_coll, rel_batch)

        stats["relations"] = rel_total
        logger.info(f"Relation embeddings completed: {rel_total}")

        return stats

    def _discover_kg_outputs(self, kg_dir) -> Dict[str, str]:
        """Scan 知识图谱数据 subdirectories, return {graph_name: output_path} for completed GraphRAG indexes."""
        results: Dict[str, str] = {}
        for sub in sorted(kg_dir.iterdir()):
            if not sub.is_dir():
                continue
            out = sub / "output"
            if out.is_dir() and (out / "create_final_entities.parquet").exists():
                results[sub.name] = str(out)
        return results

    # ── Content-based source_file resolution ─────────────────

    @staticmethod
    def _build_kb_content_index(kb_root: str | None = None) -> dict:
        """Build a content-fingerprint index of 半结构化数据 files.

        For each file under kb_root, extracts paragraph-level signatures
        (first 150 chars per paragraph) and stores them as MD5 → rel_path.

        Used by _resolve_textunit_source_files() to match TextUnit content
        back to original 半结构化数据 files.

        Returns:
            {md5_hash: rel_path} — fingerprint → 半结构化数据 relative path
        """
        import hashlib
        from pathlib import Path

        if kb_root is None:
            from server.config import knowledge_base_dir

            kb_root = str(knowledge_base_dir("半结构化数据"))

        kb_path = Path(kb_root)
        if not kb_path.exists():
            logger.warning(f"半结构化数据 not found: {kb_root}")
            return {}

        index: dict = {}
        for file_path in kb_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix not in (".txt", ".md", ".json"):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            try:
                rel_path = str(file_path.resolve().relative_to(kb_path.resolve()))
            except ValueError:
                rel_path = file_path.name

            # Extract paragraph-level signatures
            for para in content.split("\n"):
                para = para.strip()
                if len(para) < 20:  # skip short / empty lines
                    continue
                sig = para[:150]
                sig_hash = hashlib.md5(sig.encode("utf-8")).hexdigest()
                # First writer wins (earlier paragraph in file)
                if sig_hash not in index:
                    index[sig_hash] = rel_path

        logger.info(
            f"Built KB content index: {len(index)} signatures from "
            f"{kb_root}"
        )
        return index

    async def _resolve_textunit_source_files(self) -> dict:
        """Match Neo4j TextUnit nodes back to 半结构化数据 files.

        Uses content fingerprint matching: extracts the first meaningful
        sentence from each TextUnit, hashes it, and looks it up in the
        半结构化数据 content index.

        Writes ``source_file`` property on matched TextUnit nodes.
        Unmatched TextUnits get ``[KG:{kg_source}]`` as a fallback marker.

        Must be called after KG import and before compute_embeddings().

        Returns:
            {tu_id: source_file} resolution result dict for downstream use.
        """
        import asyncio as _asyncio
        import hashlib

        driver = self._get_driver()
        if not driver:
            logger.warning("Neo4j unavailable, skipping source_file resolution")
            return {}

        # 1. Build KB content index
        index = self._build_kb_content_index()
        if not index:
            logger.warning("KB content index empty, all TextUnits will use fallback")
            # Continue anyway — fallback markers are still better than internal IDs

        # 2. Query all TextUnits that need resolution (no source_file yet)
        def _read_textunits(tx, **kwargs):
            return list(tx.run(
                "MATCH (tu:TextUnit) "
                "WHERE tu.source_file IS NULL OR tu.source_file = '' "
                "RETURN tu.id AS tu_id, tu.text AS text, tu.kg_source AS kg_source"
            ))

        with driver.session(database="neo4j") as session:
            text_units = await _asyncio.to_thread(
                session.execute_read, _read_textunits
            )

        if not text_units:
            logger.info("All TextUnits already have source_file — skipping resolution")
            # Still need to return existing mapping for compute_embeddings
            def _read_all_tus(tx, **kwargs):
                return list(tx.run(
                    "MATCH (tu:TextUnit) "
                    "RETURN tu.id AS tu_id, tu.source_file AS source_file"
                ))
            with driver.session(database="neo4j") as session:
                all_tus = await _asyncio.to_thread(
                    session.execute_read, _read_all_tus
                )
            return {tu["tu_id"]: tu.get("source_file", "") for tu in all_tus}

        logger.info(
            f"Resolving source_file for {len(text_units)} TextUnits "
            f"(KB index: {len(index)} signatures)..."
        )

        # 3. Match each TextUnit
        resolved: dict = {}
        match_count = 0
        fallback_count = 0

        for tu in text_units:
            tu_id = tu["tu_id"]
            text = tu.get("text", "") or ""
            kg_source = tu.get("kg_source", "") or "unknown"

            source_file = ""

            # Try fingerprint match: first meaningful line
            for line in text.split("\n"):
                line = line.strip()
                if len(line) >= 20:
                    sig = line[:150]
                    sig_hash = hashlib.md5(sig.encode("utf-8")).hexdigest()
                    if sig_hash in index:
                        source_file = index[sig_hash]
                        match_count += 1
                        break

            # Fallback: full-text substring search across index values
            if not source_file and len(text) >= 20:
                search_key = text[:100].strip()
                for sig_hash, rel_path in index.items():
                    if search_key[:40] in sig_hash or sig_hash in hashlib.md5(
                        search_key.encode("utf-8")
                    ).hexdigest():
                        pass  # can't reverse hash — skip this fallback path
                # Alternative: iterate through unique rel_paths and string-search
                unique_paths = list(dict.fromkeys(index.values()))
                for rel_path in unique_paths:
                    try:
                        from server.config import knowledge_base_dir
                        kb_root = knowledge_base_dir("半结构化数据")
                        full_path = kb_root / rel_path
                        if full_path.exists():
                            file_content = full_path.read_text(encoding="utf-8", errors="ignore")
                            if search_key[:60] in file_content:
                                source_file = rel_path
                                match_count += 1
                                break
                    except Exception:
                        continue

            # Final fallback
            if not source_file:
                source_file = f"[KG:{kg_source}]"
                fallback_count += 1

            resolved[tu_id] = source_file

        # 4. Batch write source_file to Neo4j TextUnit nodes
        batch_rows = [
            {"tu_id": tu_id, "source_file": sf}
            for tu_id, sf in resolved.items()
        ]

        def _write_source_files(tx, batch, **kwargs):
            tx.run(
                """
                UNWIND $batch AS row
                MATCH (tu:TextUnit {id: row.tu_id})
                SET tu.source_file = row.source_file
                """,
                batch=batch,
            ).consume()

        with driver.session(database="neo4j") as session:
            for i in range(0, len(batch_rows), 200):
                batch = batch_rows[i : i + 200]
                await _asyncio.to_thread(
                    session.execute_write, _write_source_files, batch
                )

        logger.info(
            f"TextUnit source_file resolution complete: "
            f"{match_count} matched to KB files, "
            f"{fallback_count} using [KG:xxx] fallback"
        )
        return resolved

    def _ensure_constraints(self, driver) -> None:
        """Establish node unique constraints (idempotent, skip if already exists)."""
        constraints = [
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT mission_id IF NOT EXISTS FOR (m:Mission) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT location_id IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE",
            "CREATE CONSTRAINT community_id IF NOT EXISTS FOR (c:Community) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT text_unit_id IF NOT EXISTS FOR (tu:TextUnit) REQUIRE tu.id IS UNIQUE",
            "CREATE CONSTRAINT community_report_id IF NOT EXISTS FOR (cr:CommunityReport) REQUIRE cr.id IS UNIQUE",
        ]
        with driver.session() as session:
            for c in constraints:
                try:
                    session.run(c).consume()
                except Exception as e:
                    logger.debug(f"Constraint creation skipped: {e}")

    def _import_single_kg(self, driver, kg_name: str, out_dir: str, batch_size: int) -> Dict[str, Any]:
        """Import a single GraphRAG graph directory, return import statistics dict."""
        import math
        from pathlib import Path

        import pandas as pd

        def _clean_str(v) -> str:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return ""
            return str(v)

        out = Path(out_dir)
        kg_stats: Dict[str, Any] = {
            "entities": 0,
            "relationships": 0,
            "skipped_relationships": 0,
            "communities": 0,
            "community_reports": 0,
            "text_units": 0,
        }

        # --- Layer 1: Entities ---
        ent_df = pd.read_parquet(out / "create_final_entities.parquet")

        # Build title->id mapping (GraphRAG relations reference entities by title)
        title_to_id: Dict[str, str] = {}
        entity_rows: List[Dict[str, Any]] = []
        for _, r in ent_df.iterrows():
            eid = _clean_str(r.get("id")).strip()
            title = _clean_str(r.get("title")).strip()
            if not eid or not title:
                continue
            entity_rows.append({
                "id": eid,
                "name": title,
                "type": _clean_str(r.get("type")),
                "description": _clean_str(r.get("description")),
                "kg_source": kg_name,
            })
            title_to_id[title] = eid

        kg_stats["entities"] = self._batch_merge_entities(driver, entity_rows, batch_size, kg_name)

        # --- Layer 1: Relations ---
        skipped = 0
        rel_file = out / "create_final_relationships.parquet"
        if rel_file.exists():
            rel_df = pd.read_parquet(rel_file)
            rel_rows: List[Dict[str, Any]] = []
            for _, r in rel_df.iterrows():
                src = _clean_str(r.get("source")).strip()
                tgt = _clean_str(r.get("target")).strip()
                sid = title_to_id.get(src)
                tid = title_to_id.get(tgt)
                if not sid or not tid:
                    skipped += 1
                    continue
                weight = r.get("weight")
                try:
                    weight = (
                        None
                        if weight is None or (isinstance(weight, float) and math.isnan(weight))
                        else float(weight)
                    )
                except (TypeError, ValueError):
                    weight = None
                rel_rows.append({
                    "source_id": sid,
                    "target_id": tid,
                    "description": _clean_str(r.get("description")),
                    "weight": weight,
                    "kg_source": kg_name,
                })
            kg_stats["relationships"] = self._batch_merge_relationships(driver, rel_rows, batch_size, kg_name)
        kg_stats["skipped_relationships"] = skipped

        # --- Layer 2: Communities ---
        communities_path = out / "create_final_communities.parquet"
        nodes_path = out / "create_final_nodes.parquet"
        communities_df = None
        if communities_path.exists() and nodes_path.exists():
            communities_df = pd.read_parquet(communities_path)
            nodes_df = pd.read_parquet(nodes_path)
            community_stats = self._import_communities(driver, kg_name, communities_df, nodes_df, batch_size)
            kg_stats["communities"] = community_stats.get("communities", 0)
        else:
            if not communities_path.exists():
                logger.warning(f"KG[{kg_name}] community file not found, skipping: {communities_path}")
            if not nodes_path.exists():
                logger.warning(f"KG[{kg_name}] nodes file not found, skipping: {nodes_path}")

        # --- Layer 2: Community Reports ---
        reports_path = out / "create_final_community_reports.parquet"
        if reports_path.exists() and communities_df is not None:
            reports_df = pd.read_parquet(reports_path)
            kg_stats["community_reports"] = self._import_community_reports(
                driver, kg_name, reports_df, communities_df, batch_size
            )
        else:
            if not reports_path.exists():
                logger.warning(f"KG[{kg_name}] community reports file not found, skipping: {reports_path}")

        # --- Layer 3: Text Units ---
        text_units_path = out / "create_final_text_units.parquet"
        if text_units_path.exists():
            text_units_df = pd.read_parquet(text_units_path)
            kg_stats["text_units"] = self._import_text_units(
                driver, kg_name, text_units_df, title_to_id, batch_size
            )
        else:
            logger.warning(f"KG[{kg_name}] text units file not found, skipping: {text_units_path}")

        return kg_stats

    def _import_communities(
        self, driver, kg_name: str, communities_df, nodes_df, batch_size: int
    ) -> Dict[str, int]:
        """Import community nodes and hierarchical relationships.

        Steps:
        1. Extract community info from communities_df, batch MERGE Community nodes
        2. Build community parent-child hierarchy (CHILD_OF when parent field non-empty)
        3. From nodes_df get entity-community mapping (level=0 nodes),
           link Entity to Community via BELONGS_TO through community field

        Args:
            driver: Neo4j driver
            kg_name: graph name
            communities_df: communities DataFrame
            nodes_df: nodes DataFrame
            batch_size: batch size

        Returns:
            Import statistics dict
        """
        import math

        import pandas as pd

        stats = {"communities": 0, "hierarchy_links": 0, "entity_community_links": 0}

        # Step 1: Build community_number -> UUID mapping and prepare community node data
        community_num_to_id: Dict[Any, str] = {}
        community_rows: List[Dict[str, Any]] = []

        for _, r in communities_df.iterrows():
            cid = str(r.get("id", "")).strip()
            community_num = r.get("community")
            if not cid:
                continue
            community_num_to_id[community_num] = cid
            level = r.get("level")
            try:
                level = int(level) if level is not None and not (isinstance(level, float) and math.isnan(level)) else 0
            except (TypeError, ValueError):
                level = 0
            size = r.get("size")
            try:
                size = int(size) if size is not None and not (isinstance(size, float) and math.isnan(size)) else 0
            except (TypeError, ValueError):
                size = 0
            title = str(r.get("title", "")).strip() if r.get("title") is not None else ""
            community_rows.append({
                "id": cid,
                "community_id": int(community_num) if community_num is not None else 0,
                "level": level,
                "title": title,
                "size": size,
                "kg_source": kg_name,
            })

        # Batch MERGE community nodes
        community_cypher = """
            UNWIND $batch AS row
            MERGE (c:Community {id: row.id})
            SET c.community_id = row.community_id,
                c.level = row.level,
                c.title = row.title,
                c.size = row.size,
                c.kg_source = row.kg_source
        """

        def _merge_communities(tx, batch, **kwargs):
            tx.run(community_cypher, {"batch": batch}).consume()

        with driver.session() as session:
            for i in range(0, len(community_rows), batch_size):
                batch = community_rows[i:i + batch_size]
                session.execute_write(_merge_communities, batch)
                stats["communities"] += len(batch)
            logger.info(f"KG[{kg_name}] community nodes import: {stats['communities']}")

        # Step 2: Build community parent-child hierarchy
        hierarchy_rows: List[Dict[str, str]] = []
        for _, r in communities_df.iterrows():
            child_id = str(r.get("id", "")).strip()
            parent_num = r.get("parent")
            if not child_id:
                continue
            # parent is NaN or empty means no parent
            if parent_num is None:
                continue
            if isinstance(parent_num, float) and math.isnan(parent_num):
                continue
            parent_id = community_num_to_id.get(parent_num)
            if parent_id:
                hierarchy_rows.append({"child_id": child_id, "parent_id": parent_id})

        if hierarchy_rows:
            hierarchy_cypher = """
                UNWIND $batch AS row
                MATCH (child:Community {id: row.child_id})
                MATCH (parent:Community {id: row.parent_id})
                MERGE (child)-[:CHILD_OF]->(parent)
            """

            def _merge_hierarchy(tx, batch, **kwargs):
                tx.run(hierarchy_cypher, {"batch": batch}).consume()

            with driver.session() as session:
                for i in range(0, len(hierarchy_rows), batch_size):
                    batch = hierarchy_rows[i:i + batch_size]
                    session.execute_write(_merge_hierarchy, batch)
                    stats["hierarchy_links"] += len(batch)
            logger.info(f"KG[{kg_name}] community hierarchy: {stats['hierarchy_links']}")

        # Step 3: Entity-community association (via nodes_df level=0 rows)
        # nodes_df level=0 corresponds to leaf nodes, community field is community number (int)
        leaf_nodes = nodes_df[nodes_df["level"] == 0].copy()
        entity_community_rows: List[Dict[str, str]] = []

        for _, r in leaf_nodes.iterrows():
            entity_title = str(r.get("title", "")).strip()
            community_num = r.get("community")
            if not entity_title:
                continue
            if community_num is None:
                continue
            if isinstance(community_num, float) and math.isnan(community_num):
                continue
            # Map community number to UUID
            community_id = community_num_to_id.get(community_num)
            if not community_id:
                # Try int conversion
                try:
                    community_id = community_num_to_id.get(int(community_num))
                except (TypeError, ValueError):
                    continue
            if not community_id:
                continue
            # Find entity id by entity title (from nodes_df title field)
            entity_id = str(r.get("id", "")).strip()
            if not entity_id:
                continue
            entity_community_rows.append({
                "entity_id": entity_id,
                "community_id": community_id,
            })

        if entity_community_rows:
            belongs_cypher = """
                UNWIND $batch AS row
                MATCH (e:Entity {id: row.entity_id})
                MATCH (c:Community {id: row.community_id})
                MERGE (e)-[:BELONGS_TO]->(c)
            """

            def _merge_belongs(tx, batch, **kwargs):
                tx.run(belongs_cypher, {"batch": batch}).consume()

            with driver.session() as session:
                for i in range(0, len(entity_community_rows), batch_size):
                    batch = entity_community_rows[i:i + batch_size]
                    session.execute_write(_merge_belongs, batch)
                    stats["entity_community_links"] += len(batch)
            logger.info(f"KG[{kg_name}] entity-community associations: {stats['entity_community_links']}")

        return stats

    def _import_community_reports(
        self, driver, kg_name: str, reports_df, communities_df, batch_size: int
    ) -> int:
        """Import community reports and link to community nodes.

        Args:
            driver: Neo4j driver
            kg_name: graph name
            reports_df: community reports DataFrame
            communities_df: communities DataFrame (for number->UUID mapping)
            batch_size: batch size

        Returns:
            Number of community reports imported
        """
        import math

        # Build community_number -> UUID mapping
        community_num_to_id: Dict[Any, str] = {}
        for _, r in communities_df.iterrows():
            cid = str(r.get("id", "")).strip()
            community_num = r.get("community")
            if cid:
                community_num_to_id[community_num] = cid

        # Prepare community report data
        report_rows: List[Dict[str, Any]] = []
        link_rows: List[Dict[str, str]] = []

        for _, r in reports_df.iterrows():
            report_id = str(r.get("id", "")).strip()
            if not report_id:
                continue
            community_num = r.get("community")
            title = str(r.get("title", "")).strip() if r.get("title") is not None else ""
            summary = str(r.get("summary", "")).strip() if r.get("summary") is not None else ""
            full_content = str(r.get("full_content", "")).strip() if r.get("full_content") is not None else ""
            rank = r.get("rank")
            try:
                rank = float(rank) if rank is not None and not (isinstance(rank, float) and math.isnan(rank)) else None
            except (TypeError, ValueError):
                rank = None

            report_rows.append({
                "id": report_id,
                "title": title,
                "summary": summary,
                "full_content": full_content,
                "rank": rank,
                "kg_source": kg_name,
            })

            # Map community number to UUID
            community_id = community_num_to_id.get(community_num)
            if not community_id and community_num is not None:
                try:
                    community_id = community_num_to_id.get(int(community_num))
                except (TypeError, ValueError):
                    pass
            if community_id:
                link_rows.append({"community_id": community_id, "report_id": report_id})

        # Batch MERGE community report nodes
        report_cypher = """
            UNWIND $batch AS row
            MERGE (cr:CommunityReport {id: row.id})
            SET cr.title = row.title,
                cr.summary = row.summary,
                cr.full_content = row.full_content,
                cr.rank = row.rank,
                cr.kg_source = row.kg_source
        """

        def _merge_reports(tx, batch, **kwargs):
            tx.run(report_cypher, {"batch": batch}).consume()

        total = 0
        with driver.session() as session:
            for i in range(0, len(report_rows), batch_size):
                batch = report_rows[i:i + batch_size]
                session.execute_write(_merge_reports, batch)
                total += len(batch)
            logger.info(f"KG[{kg_name}] community report nodes import: {total}")

        # Build Community -> CommunityReport association
        if link_rows:
            link_cypher = """
                UNWIND $batch AS row
                MATCH (c:Community {id: row.community_id})
                MATCH (cr:CommunityReport {id: row.report_id})
                MERGE (c)-[:HAS_REPORT]->(cr)
            """

            def _merge_report_links(tx, batch, **kwargs):
                tx.run(link_cypher, {"batch": batch}).consume()

            with driver.session() as session:
                for i in range(0, len(link_rows), batch_size):
                    batch = link_rows[i:i + batch_size]
                    session.execute_write(_merge_report_links, batch)
            logger.info(f"KG[{kg_name}] community-report associations: {len(link_rows)}")

        return total

    def _import_text_units(
        self, driver, kg_name: str, text_units_df, entity_title_to_id: Dict[str, str], batch_size: int
    ) -> int:
        """Import text unit nodes and build entity associations.

        Args:
            driver: Neo4j driver
            kg_name: graph name
            text_units_df: text units DataFrame
            entity_title_to_id: entity title->id mapping
            batch_size: batch size

        Returns:
            Number of text units imported
        """
        import math

        import pandas as pd

        # Prepare text unit data
        tu_rows: List[Dict[str, Any]] = []
        link_rows: List[Dict[str, str]] = []

        for _, r in text_units_df.iterrows():
            tu_id = str(r.get("id", "")).strip()
            if not tu_id:
                continue
            text = str(r.get("text", "")).strip() if r.get("text") is not None else ""
            n_tokens = r.get("n_tokens")
            try:
                n_tokens = int(n_tokens) if n_tokens is not None and not (isinstance(n_tokens, float) and math.isnan(n_tokens)) else 0
            except (TypeError, ValueError):
                n_tokens = 0

            tu_rows.append({
                "id": tu_id,
                "text": text,
                "n_tokens": n_tokens,
                "kg_source": kg_name,
            })

            # Parse entity_ids field, build Entity-TextUnit associations
            entity_ids_raw = r.get("entity_ids")
            if entity_ids_raw is not None:
                if isinstance(entity_ids_raw, str):
                    # Try JSON parse, fallback to comma-separated
                    try:
                        entity_ids_list = json.loads(entity_ids_raw)
                    except (json.JSONDecodeError, TypeError):
                        entity_ids_list = [
                            x.strip().strip('"').strip("'")
                            for x in entity_ids_raw.strip("[]").split(",")
                            if x.strip()
                        ]
                elif isinstance(entity_ids_raw, (list, pd.Series, np.ndarray)):
                    entity_ids_list = list(entity_ids_raw)
                else:
                    entity_ids_list = []

                for eid in entity_ids_list:
                    eid_str = str(eid).strip()
                    if eid_str:
                        link_rows.append({"entity_id": eid_str, "text_unit_id": tu_id})

        # Batch MERGE text unit nodes
        tu_cypher = """
            UNWIND $batch AS row
            MERGE (tu:TextUnit {id: row.id})
            SET tu.text = row.text,
                tu.n_tokens = row.n_tokens,
                tu.kg_source = row.kg_source
        """

        def _merge_text_units(tx, batch, **kwargs):
            tx.run(tu_cypher, {"batch": batch}).consume()

        total = 0
        with driver.session() as session:
            for i in range(0, len(tu_rows), batch_size):
                batch = tu_rows[i:i + batch_size]
                session.execute_write(_merge_text_units, batch)
                total += len(batch)
            logger.info(f"KG[{kg_name}] text unit nodes import: {total}")

        # Build Entity-TextUnit associations
        if link_rows:
            link_cypher = """
                UNWIND $batch AS row
                MATCH (e:Entity {id: row.entity_id})
                MATCH (tu:TextUnit {id: row.text_unit_id})
                MERGE (e)-[:MENTIONED_IN]->(tu)
            """

            def _merge_tu_links(tx, batch, **kwargs):
                tx.run(link_cypher, {"batch": batch}).consume()

            with driver.session() as session:
                for i in range(0, len(link_rows), batch_size):
                    batch = link_rows[i:i + batch_size]
                    session.execute_write(_merge_tu_links, batch)
            logger.info(f"KG[{kg_name}] entity-text unit associations: {len(link_rows)}")
        else:
            logger.warning(
                f"KG[{kg_name}] no MENTIONED_IN relationships created: "
                f"entity_ids parse failed or entity IDs don't match"
            )

        return total

    def _batch_merge_entities(self, driver, rows: List[Dict[str, Any]], batch_size: int, kg_name: str) -> int:
        """Batch MERGE entity nodes (UNWIND for efficient writes, idempotent)."""
        cypher = """
            UNWIND $batch AS row
            MERGE (e:Entity {id: row.id})
            SET e.name = row.name,
                e.type = row.type,
                e.description = row.description,
                e.kg_source = row.kg_source
        """

        def _work(tx, batch, **kwargs):
            tx.run(cypher, {"batch": batch}).consume()

        total = 0
        with driver.session() as session:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                session.execute_write(_work, batch)
                total += len(batch)
                logger.info(f"KG[{kg_name}] entity import progress: {total}/{len(rows)}")
        return total

    def _batch_merge_relationships(self, driver, rows: List[Dict[str, Any]], batch_size: int, kg_name: str) -> int:
        """Batch MERGE relationships (connect by entity id, idempotent)."""
        cypher = """
            UNWIND $batch AS row
            MATCH (s:Entity {id: row.source_id})
            MATCH (t:Entity {id: row.target_id})
            MERGE (s)-[rel:RELATED_TO]->(t)
            SET rel.description = row.description,
                rel.weight = row.weight,
                rel.kg_source = row.kg_source
        """

        def _work(tx, batch, **kwargs):
            tx.run(cypher, {"batch": batch}).consume()

        total = 0
        with driver.session() as session:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                session.execute_write(_work, batch)
                total += len(batch)
                logger.info(f"KG[{kg_name}] relationship import progress: {total}/{len(rows)}")
        return total


# Module-level singleton
graph_rag_engine = GraphRAGEngine()
