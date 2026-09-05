"""GraphRAG engine prompt templates."""

from server.engines.citation_utils import CITATION_PROMPT

MODE_CLASSIFICATION_PROMPT = """判断以下问题需要哪种搜索模式：
- local（局部搜索）：问题涉及具体实体名称、特定清单内容、参数细节、单一任务。绝大多数问题属于此类。只要问题中提到了具体事物名称，就应选择 local。
- global（全局搜索）：仅当问题明确要求跨领域的整体概览、不指定任何具体名称的分类统计、或体系级总结时才选择。
只输出一个词：global 或 local。

问题：{query}"""

MAP_COMMUNITY_PROMPT = """你是一个作战知识分析师。评估以下社区摘要与用户问题的相关性。
- 从摘要中提取与问题相关的关键信息点（每条一句话）
- 给出相关性评分（0-100，0=完全不相关，100=高度相关）

## 用户问题
{query}

## 社区摘要
标题: {title}
{content}

## 输出格式（严格遵守）
评分: <数字>
要点:
- <要点1>
- <要点2>"""


def build_local_prompt(query: str, entity_ctx: str, text_ctx: str, relation_ctx: str) -> str:
    return (
        "你是一个作战规划知识助手。基于以下知识图谱信息回答用户问题。\n"
        + CITATION_PROMPT + "\n\n"
        f"## 相关实体\n{entity_ctx}\n\n"
        f"## 相关文本\n{text_ctx}\n\n"
        f"## 相关关系\n{relation_ctx}\n\n"
        f"## 用户问题\n{query}\n\n"
        "请直接回答："
    )


def build_global_empty_prompt(query: str) -> str:
    return (
        "你是一个作战规划知识助手。基于以下关键信息点回答用户问题。\n"
        "综合所有相关信息，给出全面、详细的回答。\n\n"
        "## 关键信息点\n(无关键信息点)\n\n"
        f"## 用户问题\n{query}\n\n"
        "## 回答"
    )


def build_global_reduce_prompt(query: str, points_text: str, entity_context: str = "") -> str:
    return (
        "你是一个作战规划知识助手。基于以下关键信息点回答用户问题。\n"
        "综合所有相关信息，给出全面、详细的回答。\n"
        "如果知识图谱实体中有相关信息，请务必引用实体名称。\n"
        + CITATION_PROMPT + "\n\n"
        f"{entity_context}"
        f"## 关键信息点\n{points_text}\n\n"
        f"## 用户问题\n{query}\n\n"
        "请直接回答："
    )
