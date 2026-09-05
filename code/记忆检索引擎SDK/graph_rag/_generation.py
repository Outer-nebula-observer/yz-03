"""
GraphRAG 答案生成模块 — local/global search 生成逻辑。
从 engine.py 拆出以减小文件体积（mixin 模式）。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from server.engines.graph_rag.context import DEFAULT_TOKEN_BUDGET, estimate_tokens
from server.engines.graph_rag.prompts import (
    MAP_COMMUNITY_PROMPT,
    build_global_empty_prompt,
    build_global_reduce_prompt as _build_global_reduce_prompt_template,
    build_local_prompt as _build_local_prompt_template,
)

logger = logging.getLogger("server.engines.graph_rag")

# -- Map phase --
MAX_MAP_CONCURRENCY = 5
MAP_COMMUNITY_MAX_CHARS = 800


class _GraphRAGGeneration:
    """Mixin — GraphRAG local/global search 答案生成。"""

    # ── Local search ──────────────────────────────────────

    def _build_local_prompt(
        self, query: str, entities: list, text_units: list,
        relations: list, communities: list,
    ) -> str:
        """Build local search mode LLM prompt (dynamic token budget allocation)."""
        n_entity = min(len(entities), 5)
        entity_ctx = "\n".join(
            f"[{i+1}] {e.get('content', '')}"
            for i, e in enumerate(entities[:5])
        ) or "(无)"

        text_offset = n_entity
        text_ctx = "\n".join(
            f"[{text_offset + i + 1}] {tu.get('content', '')[:300]}"
            for i, tu in enumerate(text_units[:5])
        ) or "(无)"

        rel_offset = text_offset + min(len(text_units), 5)
        relation_ctx = "\n".join(
            f"[{rel_offset + i + 1}] {r.get('content', '')}"
            for i, r in enumerate(relations[:5])
        ) or "(无)"

        return _build_local_prompt_template(query, entity_ctx, text_ctx, relation_ctx)

    async def _generate_local(
        self, query: str, entities: list, text_units: list,
        relations: list, communities: list
    ) -> dict | None:
        """Local Search: generate answer based on entity+text+relationship context."""
        prompt = self._build_local_prompt(query, entities, text_units, relations, communities)

        try:
            llm = self._get_llm()
            output = await asyncio.wait_for(
                asyncio.to_thread(llm.chat, prompt),
                timeout=10.0,
            )
            return {
                "chunk_id": "graphrag-generated",
                "source_file": "[GraphRAG:generated] Local search answer",
                "content": output,
                "score": 0.9,
                "engine": "graph_rag",
                "metadata": {"type": "generated", "mode": "local", "source_file": "[GraphRAG:generated]"},
            }
        except asyncio.TimeoutError:
            logger.warning("GraphRAG local generation timeout (10s)")
            return None
        except Exception as e:
            logger.warning(f"GraphRAG local generation failed: {e}")
            return None

    # ── Map phase (community → key points) ────────────────

    async def _map_community_batch(self, query: str, batch: list) -> list:
        """(Deprecated) Map: extract key info points from a batch of CommunityReports.

        Retained for backward compatibility; new code should use _map_community_with_score.
        """
        reports_text = ""
        for i, cr in enumerate(batch):
            title = cr.get("content", "").split("\n")[0] if cr.get("content") else f"Report {i}"
            summary = cr.get("content", "")[:500]
            reports_text += f"### [{title}]\n{summary}\n\n"

        prompt = (
            "You are an operational knowledge analyst. Extract key information points "
            "related to the user's question from the following community summaries.\n"
            "Each point should be one sentence, annotated with the community name.\n\n"
            f"## User Question\n{query}\n\n"
            f"## Community Summaries\n{reports_text}\n"
            "## Key Information Points"
        )

        try:
            llm = self._get_llm()
            output = await asyncio.wait_for(
                asyncio.to_thread(llm.chat, prompt),
                timeout=10.0,
            )
            return [line.strip("- ").strip() for line in output.split("\n") if line.strip().startswith("-")]
        except Exception as e:
            logger.warning(f"GraphRAG map batch failed: {e}")
            return []

    async def _map_community_with_score(
        self, query: str, report: dict, sem: asyncio.Semaphore | None = None,
    ) -> dict | None:
        """Map: extract key info points from a single CommunityReport with scoring (0-100).

        Replaces the old batch _map_community_batch. Each report calls LLM independently,
        returning {"report_id": str, "title": str, "points": [str], "score": int}.
        Returns None on failure.

        Uses sem for concurrency control to avoid overwhelming the LLM backend.
        """
        report_title = report.get("metadata", {}).get("community", "N/A")
        content = report.get("content", "")
        if isinstance(content, str) and len(content) > MAP_COMMUNITY_MAX_CHARS:
            content = content[:MAP_COMMUNITY_MAX_CHARS]

        prompt = MAP_COMMUNITY_PROMPT.format(
            query=query, title=report_title, content=content,
        )

        async def _do_map():
            try:
                llm = self._get_llm()
                output = await asyncio.wait_for(
                    asyncio.to_thread(llm.chat, prompt),
                    timeout=10.0,
                )
                score, points = self._parse_map_response(output)
                return {
                    "report_id": report.get("chunk_id", ""),
                    "title": report_title,
                    "points": points,
                    "score": score,
                    "raw_output": output,
                }
            except Exception as e:
                logger.warning(f"Map community '{report_title}' failed: {e}")
                return None

        if sem is not None:
            async with sem:
                return await _do_map()
        return await _do_map()

    @staticmethod
    def _parse_map_response(response: str) -> tuple[int, list[str]]:
        """Parse LLM map response: extract score (0-100) and key points list.

        Fault-tolerant design: compatible with multiple formats, returns (0, []) on parse failure.
        """
        import re

        score = 0
        points: list[str] = []

        # Extract score
        score_patterns = [
            r"评分\s*[:：]\s*(\d+)",
            r"score\s*[:：]\s*(\d+)",
            r"相关性[:：]\s*(\d+)",
            r"(\d+)\s*分",
        ]
        for pat in score_patterns:
            m = re.search(pat, response, re.IGNORECASE)
            if m:
                try:
                    score = int(m.group(1))
                    score = max(0, min(100, score))
                except ValueError:
                    pass
                break

        # Extract points
        points_section = response
        section_markers = ["要点:", "要点：", "关键信息点:", "关键信息点："]
        for marker in section_markers:
            idx = response.find(marker)
            if idx >= 0:
                points_section = response[idx + len(marker):]
                break

        for line in points_section.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                point = stripped[2:].strip()
                if point:
                    points.append(point)
            elif stripped.startswith(("•", "·")) and len(stripped) > 2:
                point = stripped[1:].strip()
                if point:
                    points.append(point)

        # If no "要点:" region found, globally search for "- " lines
        if not points:
            for line in response.split("\n"):
                stripped = line.strip()
                if stripped.startswith("- ") and len(stripped) > 2:
                    point = stripped[2:].strip()
                    if point and len(point) >= 5:  # filter overly short lines
                        points.append(point)

        return score, points

    # ── Global search ─────────────────────────────────────

    async def _build_global_prompt(
        self, query: str, community_reports: list, entities: list | None = None,
    ) -> tuple[str, list]:
        """Build global search mode LLM prompt (parallel map phase + reduce prompt).

        Parallel LLM calls per CommunityReport to extract info points with scoring (0-100),
        then filter low-score points, sort by score, truncate by token budget, build reduce prompt.

        Returns:
            (reduce_prompt_str, map_metadata_for_stream_events)
            map_metadata contains parallel map phase result metadata for generate_stream.
        """
        if not community_reports:
            return build_global_empty_prompt(query), []

        top_reports = community_reports[:10]

        # -- Map: parallel scoring --
        sem = asyncio.Semaphore(MAX_MAP_CONCURRENCY)
        tasks = [
            self._map_community_with_score(query, cr, sem=sem)
            for cr in top_reports
        ]
        map_results = await asyncio.gather(*tasks, return_exceptions=True)

        # -- Filter & Sort --
        valid_results: list[dict] = []
        for r in map_results:
            if isinstance(r, BaseException) or r is None:
                if isinstance(r, BaseException):
                    logger.warning(f"Map community exception: {r}")
                continue
            if r.get("score", 0) == 0:
                continue
            valid_results.append(r)

        valid_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(
            f"GraphRAG map: {len(top_reports)} reports -> "
            f"{len(valid_results)} valid (score>0)"
        )

        # -- Token-budget truncation --
        all_points: list[str] = []
        tokens_used = 0
        max_reduce_tokens = DEFAULT_TOKEN_BUDGET // 4
        for r in valid_results:
            for p in r.get("points", []):
                pt = estimate_tokens(p)
                if tokens_used + pt > max_reduce_tokens:
                    break
                all_points.append(
                    f"[{r.get('title', '?')}](score={r.get('score', 0)}) {p}"
                )
                tokens_used += pt

        prompt = self._build_global_reduce_prompt(query, all_points, entities)
        return prompt, valid_results

    @staticmethod
    def _build_global_reduce_prompt(
        query: str, points: list, entities: list | None = None
    ) -> str:
        """Build global mode reduce prompt (no LLM call)."""
        points_text = "\n".join(f"- {p}" for p in points) if points else "(无关键信息点)"

        entity_context = ""
        if entities:
            entity_names: list[str] = []
            for i, e in enumerate(entities[:5]):
                name = e.get("metadata", {}).get("name", "")
                etype = e.get("metadata", {}).get("type", "")
                if name:
                    label = f"{name} (type: {etype})" if etype else name
                    entity_names.append(f"[{i+1}] {label}")
            if entity_names:
                entity_context = (
                    "## Knowledge graph related entities\n"
                    + "\n".join(entity_names)
                    + "\n\n"
                )

        return _build_global_reduce_prompt_template(query, points_text, entity_context)

    async def _reduce_intermediate_points(
        self, query: str, points: list, entities: list | None = None
    ) -> str:
        """Reduce: summarize intermediate points into final answer.

        Incorporates entity name context to ensure answers can reference specific
        knowledge graph entities.
        """
        prompt = self._build_global_reduce_prompt(query, points, entities)

        try:
            llm = self._get_llm()
            output = await asyncio.wait_for(
                asyncio.to_thread(llm.chat, prompt),
                timeout=10.0,
            )
            return output
        except Exception as e:
            logger.warning(f"GraphRAG reduce failed: {e}")
            # fallback: return raw points
            return "\n".join(f"- {p}" for p in points) if points else "(无关键信息点)"

    async def _generate_global(
        self, query: str, community_reports: list, entities: list | None = None,
    ) -> dict | None:
        """Global Search: parallel map -> reduce CommunityReport to generate global answer.

        Also incorporates entity context to ensure even global path can reference specific entities.
        """
        if not community_reports:
            return None

        prompt, map_meta = await self._build_global_prompt(
            query, community_reports, entities,
        )
        report_count = len(map_meta) if map_meta else len(community_reports[:10])

        try:
            llm = self._get_llm()
            answer = await asyncio.wait_for(
                asyncio.to_thread(llm.chat, prompt),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.warning("GraphRAG global generation timeout (10s)")
            return None
        except Exception as e:
            logger.warning(f"GraphRAG global generation failed: {e}")
            return None

        return {
            "chunk_id": "graphrag-generated",
            "source_file": "[GraphRAG:generated] Global search answer",
            "content": answer,
            "score": 0.9,
            "engine": "graph_rag",
            "metadata": {
                "type": "generated",
                "mode": "global",
                "report_count": report_count,
            },
        }

    # ── Generation entry ──────────────────────────────────

    async def _generate_answer(self, query: str, results: list) -> dict | None:
        """GraphRAG generation entry: classify mode -> extract classified results -> call generation method."""
        if not results:
            return None

        # Classify search results by metadata.type
        entities = [r for r in results if r.get("metadata", {}).get("type") == "entity"]
        text_units = [r for r in results if r.get("metadata", {}).get("type") == "text_unit"]
        relations = [r for r in results if r.get("metadata", {}).get("type") == "relation"]
        communities = [r for r in results if r.get("metadata", {}).get("type") == "community"]
        community_reports = [r for r in results if r.get("metadata", {}).get("type") == "community_report"]

        # Community weight sorting (by entity coverage)
        if entities and community_reports:
            community_reports = await self._compute_community_weights(
                entities, community_reports,
            )

        # LLM determines mode
        mode = await self._classify_query_mode(query)
        logger.info(f"GraphRAG generation mode: {mode}")

        if mode == "global":
            generated = await self._generate_global(
                query, community_reports, entities,
            )
            if generated:
                return generated
            # Global generation failed, fallback to local
            return await self._generate_local(query, entities, text_units, relations, communities)
        else:
            return await self._generate_local(query, entities, text_units, relations, communities)
