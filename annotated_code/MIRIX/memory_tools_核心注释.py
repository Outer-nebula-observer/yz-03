# ============================================================================
# MIRIX: mirix/functions/function_sets/memory_tools.py 核心节选
# 【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2507.07957 §3-4：
#   六类记忆（core/episodic/semantic/procedural/resource/knowledge_vault）
#   + 多 agent 协调更新。本文件 = 六类记忆的**操作工具集**——
#   每个函数都是一个 LLM 可调用的 tool（docstring 即工具说明书）。
#
# 【为什么精读】赛题③"记忆操作 API"的最完整工业级参照——
#   Mem-α 的 ToolFunction 思想 + MIRIX 的六库落地。
#   trigger_memory_update 的"记忆类型→专属 agent"分发是
#   多智能体协调的精髓。
#
# 【我们的实现对照】
#   六类 *_memory_insert/update     → evolution.write/merge（两类简化）
#   core_memory_append/rewrite      → working_memory（常驻区编辑）
#   trigger_memory_update 分发      → controller（单体内联，无子 agent）
#   六库 schema（*ForLLM/*Base）    → schema.py 两类（fact/experience）
# ============================================================================

from typing import List, Optional


# ------------------------------------------------------------------
# 【工具组 1】core memory —— 常驻 system prompt 的记忆（不可检索）
# ------------------------------------------------------------------
def core_memory_append(self: "Agent", agent_state: "AgentState",
                       label: str, content: str) -> Optional[str]:
    """向 core memory 追加内容。

    core = 用户身份/偏好等"永远在场"的信息（我们 working_context 同位）。
    带 label 分区（如 label="user_preferences"）——core 内部再分块，
    rewrite/replace 按 label/行号定位编辑。
    【对照我们】working_context 是单字符串——若 core 需要分区管理，
    加 label→content 的 dict 即可，接口先留好。
    """
    ...

def core_memory_rewrite(self: "Agent", agent_state: "AgentState",
                        label: str, content: str) -> Optional[str]:
    """整体重写某 label 的 core 块（append 的对照面：覆盖 vs 追加）。"""
    ...

def core_memory_replace(self: "Agent", agent_state: "AgentState", label: str,
                        old_line_number: str, new_content: str) -> Optional[str]:
    """按**行号**替换 core 内容——精确到行的编辑！

    为什么行号而非文本匹配？core 是 LLM 可见的，行号引用无歧义；
    文本匹配在内容重复时会错位。这个设计让 LLM 能做精细编辑。
    """
    ...


# ------------------------------------------------------------------
# 【工具组 2-5】五类可检索记忆的 insert/update（结构同构）
# ------------------------------------------------------------------
def episodic_memory_insert(self: "Agent", items: List[EpisodicEventForLLM]):
    """批量插入情景记忆。

    ★ 参数是 **List + 专用 ForLLM 类型**（非裸字符串）：
    episodic 条目带结构化字段（时间/参与者/地点）——LLM 按类型填参，
    强约束输出格式（比"输出 JSON 再解析"更稳，借 OpenAI 结构化输出）。
    【值得学】我们的 extract_memory_ops 输出 Dict——升级方向：
    定义 ForLLM 类型让 LLM 直接产结构化对象。
    """
    ...

def episodic_memory_merge(self: "Agent", event_id: str,
                          combined_summary: str = None,
                          combined_details: str = None):
    """★ merge 是显式工具：LLM 指定"合并成什么"（summary+details 都给）。

    与我们 merge() 的差异：我们是"传入 ids → 代码摘要融合"；
    MIRIX 是"LLM 自己想好融合结果 → 代码只落库"——
    融合的智能在工具调用方（LLM），执行在工具内。建议-执行分离的更彻底版。
    """
    ...

def resource_memory_insert(self: "Agent", items: List[ResourceMemoryItemBase]):
    """resource 记忆：文件/外部资源引用（六类中我们未建的一类）。

    【作战场景启发】作战规划有"情报文档/态势图/条令文件"引用需求——
    resource 库存"指向外部资源的记忆"（记忆里放引用而非全文），
    我们的 factual 库未来可分出这一类。
    """
    ...

def procedural_memory_insert(self: "Agent", items: List[ProceduralMemoryItemBase]):
    """procedural 记忆：程序/技能（对应 Memp 的程序性记忆）。"""
    ...

def knowledge_vault_insert(self: "Agent", items: List[KnowledgeVaultItemBase]):
    """knowledge vault：长期知识沉淀（低频访问、高容量）。"""
    ...


# ------------------------------------------------------------------
# 【核心】trigger_memory_update —— 多智能体分发的入口
# ------------------------------------------------------------------
def trigger_memory_update(self: "Agent", user_message: object,
                          memory_types: List[str]) -> Optional[str]:
    """主 agent 判断"哪些记忆类型需要更新"→ 分发给对应记忆 agent。

    ★ 六类记忆 = 六个专属 agent（memory_type_to_agent_type 映射）：
        core            → core_memory_agent
        episodic        → episodic_memory_agent
        resource        → resource_memory_agent
        procedural      → procedural_memory_agent
        knowledge_vault → knowledge_vault_agent
        semantic        → semantic_memory_agent

    【论文 §4 的多智能体协调】主 agent（对话/推理）不做记忆操作——
    它只**决定**该更新哪些类型（本函数），具体"怎么更新"由各记忆
    agent 独立完成（各自调本文件的工具）。

    【对照我们】controller 是"单体内联"版：一个类直接调 evolution；
    MIRIX 是"进程分发"版：ThreadPoolExecutor 并行发给子 agent。
    我们的选择：MVP 无需多进程开销；MIRIX 的价值在**隔离**——
    记忆 agent 各自维护各自的库，主 agent 上下文不被记忆操作污染
    （六类操作的 prompt 很长，塞主 agent 会挤爆窗口）。

    message_queue 批处理：一次消息触发多类型更新时排队并行
    （as_completed 收集结果）——吞吐设计。
    """
    from mirix import create_client
    client = create_client()
    agents = client.list_agents()

    memory_type_to_agent_type = {
        "core": "core_memory_agent",
        "episodic": "episodic_memory_agent",
        "resource": "resource_memory_agent",
        "procedural": "procedural_memory_agent",
        "knowledge_vault": "knowledge_vault_agent",
        "semantic": "semantic_memory_agent",
    }
    # 过滤合法类型 → 逐类分发到对应 agent（并行线程池）
    valid_agent_types = []
    for memory_type in memory_types:
        if memory_type in memory_type_to_agent_type:
            valid_agent_types.append(memory_type_to_agent_type[memory_type])
        else:
            raise ValueError(f"Memory type '{memory_type}' is not supported.")
    ...


def trigger_memory_update_with_instruction(self: "Agent", user_message: object,
                                           instruction: str, memory_type: str):
    """带指令的分发版：主 agent 可指定"这次更新要特别注意什么"。

    instruction 会传给记忆 agent 作为额外上下文——
    主→记忆 agent 的**意图传递通道**（不止"更新什么"，还有"为什么"）。
    """
    ...

def finish_memory_update(self: "Agent"):
    """收尾信号：本轮记忆更新完成（多 agent 同步的屏障）。"""
    ...

# ============================================================================
# 【给基础开发者的三条读懂线索】
# 1) 六类记忆不是六个库那么简单——是"六组工具 + 六个 agent"：
#    类型即职责边界，每类的 insert/update/check 三件套同构；
# 2) LLM 工具的参数用**类型化对象**（ForLLM/Base 系列）而非裸字符串：
#    结构化输出从"提示词求它"变成"类型系统逼它"；
# 3) "谁决定更新"与"谁执行更新"分离：主 agent 只选类型（trigger_*），
#    记忆 agent 执行——与我们"LLM 建议、代码执行"是同一哲学的
#    两种粒度（我们分离到函数级，MIRIX 分离到进程级）。
# ============================================================================
