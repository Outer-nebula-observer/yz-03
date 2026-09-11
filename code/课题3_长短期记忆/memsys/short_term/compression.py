# -*- coding: utf-8 -*-
"""
memsys.short_term.compression — 短期记忆压缩策略
================================================
三档策略（docs/04 2.1 节消融对照组）：
  1. truncate  长度截断（MVP 保底，零依赖）
  2. summarize 摘要压缩（MockLLM / 真模型）
  3. llmlingua LLMLingua 删 token 式压缩（预留适配器，仓库见
                paper_code/01_短期记忆/LLMLingua/llmlingua/prompt_compressor.py）

设计要点：compression 对 WorkingMemory 是**可插拔策略**，
消融实验（G1）用同一批场次分别跑三档，比较"压缩率 vs 关键约束保留率"。
"""

from __future__ import annotations

from typing import Optional, Protocol

from .working_memory import WorkingMemory


class CompressionStrategy(Protocol):
    """压缩策略协议：给工作记忆定一个预算，返回压缩后的上下文文本。"""

    def apply(self, wm: WorkingMemory, budget_tokens: int) -> str: ...


class TruncateStrategy:
    """截断策略：从 FIFO 最旧端删起，直到预算内（最简单、可解释）。

    适用：零模型依赖的保底；代价：旧消息直接丢失（虽有 archived
    归档但不在渲染上下文里）。压缩研究实测：约束必保留、标记事实
    可能因被归档而不再出现在新上下文中。
    """

    def apply(self, wm: WorkingMemory, budget_tokens: int) -> str:
        # 委托 wm.compress（内部只动 fifo_queue，绝不触碰约束/goal）
        return wm.compress(strategy="truncate", budget_tokens=budget_tokens)


class SummarizeStrategy:
    """摘要策略：历史消息整体摘要成一段（依赖 LLMClient）。

    与 truncate 的关键差异：旧信息以"摘要"形态保留在上下文中，
    而非直接丢弃——代价是细节损失（Mock 为截断式拼接，真模型
    后才体现摘要质量）。压缩研究实测 summarize 压缩率可达 89.9%
    （Mock 口径，阈值参数 300/210）。
    """

    def apply(self, wm: WorkingMemory, budget_tokens: int) -> str:
        # 委托 wm.compress（strategy=summarize 走 llm.summarize 有界截断）
        return wm.compress(strategy="summarize", budget_tokens=budget_tokens)


class LLMLinguaStrategy:
    """LLMLingua 适配器（预留）——接入真压缩器时实现此类。

    接入方式（装好 llmlingua 包后）：
        from llmlingua import PromptCompressor
        pc = PromptCompressor(model_name="microsoft/llmlingua-2-xsmall")
        result = pc.compress_prompt(context, rate=0.5)
    注意：约束字段要先摘出来不送压缩（我们只压历史消息）。
    """

    def __init__(self, model_name: str = "microsoft/llmlingua-2-xsmall",
                 rate: float = 0.5) -> None:
        self.model_name = model_name
        self.rate = rate
        self._pc = None  # 延迟初始化（未装包时此类不应 import 报错）

    def apply(self, wm: WorkingMemory, budget_tokens: int) -> str:
        # 延迟导入：未安装 llmlingua 包时，import 本文件不应报错
        if self._pc is None:
            from llmlingua import PromptCompressor  # 延迟导入
            self._pc = PromptCompressor(model_name=self.model_name)
        # 只压历史消息（fifo_queue），约束/goal 字段由 wm.compress 契约保护
        material = "\n".join(wm.slot.fifo_queue)
        if not material:
            return wm.render()
        out = self._pc.compress_prompt(context=material, rate=self.rate)
        # 压缩结果以"历史摘要"形态回写（与 summarize 策略同构），
        # 原消息入 archived 供复盘晋升使用（不丢）
        wm._recursive_summary = out.get("compressed_prompt", material)
        wm.archived.append({"evicted": list(wm.slot.fifo_queue),
                            "summary": wm._recursive_summary, "by": "llmlingua"})
        wm.slot.fifo_queue = []
        wm.slot.touch()
        return wm.render()


def get_strategy(name: str, **kwargs) -> CompressionStrategy:
    """策略工厂：truncate / summarize / llmlingua。"""
    if name == "truncate":
        return TruncateStrategy()
    if name == "summarize":
        return SummarizeStrategy()
    if name == "llmlingua":
        return LLMLinguaStrategy(**kwargs)
    raise ValueError(f"未知压缩策略: {name}")
