# ============================================================================
# PREMem: src/memory/segmentor.py 核心节选【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2509.10852 §Method：
#   预存储推理第一步 = 会话切分（segmentation）——把长会话切成
#   "语义连贯段"，后续的事实/经验/主观抽取以段为单位。
#
# 【为什么精读】赛题③进化模块的"抽取前处理"参照——我们的
#   evolve_from_review() 直接吃整段复盘文本（按行规则切），
#   PREMem 用 LLM 语义切分 + **规则兜底**的双保险设计值得学。
#
# 【我们的实现对照】
#   ConversationSegmentor（LLM 切分） → 我们 MockLLM 按行扫（教训/经验关键词）
#   SegmentContent（段+摘要+原文）   → 我们 archived（驱逐消息+递归摘要）
#   fallback 每 3 轮切               → 我们无兜底（切分失败=整段处理）
# ============================================================================

from dataclasses import dataclass, asdict
from typing import List, Optional
from src.model.llm import LLMAgent, LLMResponse
from src.data.schema import Session, Message


@dataclass
class SegmentContent:
    """一个切分段：编号 + 起止轮次 + 摘要 + **原始消息全文**。

    原始消息保留（conversation 字段）= 非损式设计——
    摘要供快速浏览/检索，原文供需要时回查（Zep 的 episode 思想同源）。
    【对照我们】archived 同样"驱逐消息+摘要"并存，可回放。
    """
    segment_id: int
    start_exchange_number: int     # 起始轮次（exchange=一轮问答）
    end_exchange_number: int
    num_exchanges: int
    summary: str                   # LLM 生成段摘要
    conversation: List[Message]    # 原始消息（保真）


@dataclass
class SegmentResult:
    """一次切分的完整结果：原会话 + LLM 响应 + 段列表（可序列化落盘）。"""
    original_session: Session
    agent_response: LLMResponse
    result: List[SegmentContent]


class ConversationSegmentor:
    """LLM 语义切分器：把会话切成"话题连贯段"。

    双保险设计（docstring 明说）：
      ① LLM 切分（prompt 在 prompts/secom_segment.yaml）——质量高但可能失败；
      ② **规则兜底**：LLM 失败或覆盖不全 → 每 3 轮硬切——
         保证"所有轮次都被覆盖，不漏不重"（no missing or duplicated turns）。
    【工程价值】LLM 参与的任何环节都要想好"它挂了怎么办"——
    我们 MockLLM 的规则抽取本质上就是"真模型的兜底层"（接口不变可互换）。

    增量切分（incremental_prompt）：新消息来了不重切全会话，
    只在已有段基础上追加——长会话的成本控制。
    """
    def __init__(self, segment_model_name: str = "gpt-4.1-nano",
                 prompt_path: str = "prompts/secom_segment.yaml",
                 incremental_prompt_path: str = "prompts/secom_incremental_segment.yaml"):
        # 切分用 nano 小模型——"写入时贵"的例外：切分是廉价任务，
        # 后续的"链接对推理"才用大模型（成本分配的精细化）
        self.segment_model_name = segment_model_name
        self.agent = LLMAgent(segment_model_name)
        self.segment_prompt = prompt_path
        self.incremental_segment_prompt = incremental_prompt_path

    def _convert_messages_to_string(self, conversation: List[Message],
                                    session_date: Optional[str] = None):
        """消息列表 → LLM 输入格式。

        细节：session_date 有则前置为第一行 "[2024-03-15]"——
        把**会话日期**喂给切分 LLM：时间跳变常是话题边界信号
        （"周一聊工作 → 周三聊旅行"大概率不同段）。
        【作战场景对应】复盘文本带"场次时间"同理：
        推演阶段切换（准备/交战/复盘）是天然分段边界。
        """
        if session_date is not None:
            return_texts = [f"[{session_date}]"] + \
                [f"[{turn['role']}]: {turn['content']}" for turn in conversation]
        else:
            return_texts = [f"[{turn['role']}]: {turn['content']}" for turn in conversation]
        return return_texts

# ============================================================================
# 【给基础开发者的三条读懂线索】
# 1) "LLM 干活 + 规则兜底"双保险：LLM 输出不可信是常态，
#    兜底保证功能不挂（质量降级但可用）——比单押 LLM 稳得多；
# 2) 切分用小模型、推理用大模型——任务难度决定模型档位，
#    "写入时贵"贵的应该是**推理**（链接对），不是切分；
# 3) 段内保留原文（非损）+ 摘要（快速浏览）双形态——
#    与"删掉原文只留摘要"的差异：冲突消解时要回看原文。
# ============================================================================
