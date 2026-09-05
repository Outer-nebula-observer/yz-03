"""GraphRAG context building -- token budget management and context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

# -- Token budget defaults --
DEFAULT_TOKEN_BUDGET = 8000
COMMUNITY_PROP = 0.25
TEXT_UNIT_PROP = 0.50
LOCAL_PROP = 0.25


@dataclass
class TokenBudget:
    """Token budget allocation for context building."""
    community_prop: float = COMMUNITY_PROP
    text_unit_prop: float = TEXT_UNIT_PROP
    local_prop: float = LOCAL_PROP
    total_budget: int = DEFAULT_TOKEN_BUDGET


def estimate_tokens(text: str) -> int:
    """Token count heuristic (~2 chars per token for Chinese)."""
    return max(len(text) // 2, 1)


def compute_token_budget(query: str, prompt_overhead: int = 0,
                         budget_config: TokenBudget | None = None) -> dict:
    """Allocate token budget across context sections proportionally."""
    cfg = budget_config or TokenBudget()
    reserved = estimate_tokens(query) + prompt_overhead
    available = max(cfg.total_budget - reserved, 200)
    return {
        "communities": max(int(available * cfg.community_prop), 100),
        "text_units": max(int(available * cfg.text_unit_prop), 100),
        "local": max(int(available * cfg.local_prop), 100),
    }


def fill_section(items: list, budget: int, content_key: str = "content") -> Tuple[str, list]:
    """Greedily fill items into a text section until token budget is exhausted."""
    parts: list[str] = []
    consumed: list = []
    tokens_used = 0
    for item in items:
        content = item.get(content_key, "") or ""
        item_tokens = estimate_tokens(content)
        if tokens_used + item_tokens > budget:
            break
        parts.append(content)
        consumed.append(item)
        tokens_used += item_tokens
    return "\n".join(parts), consumed


def build_context_sections(query: str, entities: list, text_units: list,
                           relations: list, community_reports: list,
                           budget_config: TokenBudget | None = None) -> Tuple[str, list]:
    """Build proportionally-allocated numbered context for local search."""
    budgets = compute_token_budget(query, budget_config=budget_config)
    context_items: list = []
    sections: list[str] = []

    if community_reports and budgets["communities"] > 0:
        comm_text, comm_items = fill_section(community_reports, budgets["communities"])
        if comm_text.strip():
            sections.append(f"## 相关社区摘要\n{comm_text}")
            context_items.extend(comm_items)

    if entities and budgets["local"] > 0:
        local_budget = budgets["local"]
        entity_budget = int(local_budget * 0.6)
        rel_budget = int(local_budget * 0.4)
        entity_text, entity_items = fill_section(entities, entity_budget)
        if entity_text.strip():
            sections.append(f"## 相关实体\n{entity_text}")
            context_items.extend(entity_items)
        if relations and rel_budget > 0:
            rel_text, rel_items = fill_section(relations, rel_budget)
            if rel_text.strip():
                sections.append(f"## 相关关系\n{rel_text}")
                context_items.extend(rel_items)

    if text_units and budgets["text_units"] > 0:
        tu_text, tu_items = fill_section(text_units, budgets["text_units"])
        if tu_text.strip():
            sections.append(f"## 相关文本\n{tu_text}")
            context_items.extend(tu_items)

    context_str = "\n\n".join(sections) if sections else "(无相关上下文)"
    return context_str, context_items
