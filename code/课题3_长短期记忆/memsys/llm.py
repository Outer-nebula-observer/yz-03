# -*- coding: utf-8 -*-
"""
memsys.llm — LLM 调用统一抽象
=============================
目标：让框架**离线可跑**（MockLLM），同时随时可切真模型（智戎平台/DeepSeek/OpenAI）。

设计（参考 Mem-α functions.py 的"工具化"思想，见 笔记_Wang2025-MemAlpha）：
  - LLMClient 只暴露三个能力：chat / summarize / extract_memory_ops；
  - MockLLM 用**规则**模拟三能力（零依赖、确定性，方便冒烟测试与消融回放）；
  - OpenAICompatibleClient 提供 HTTP 调用骨架（默认不启用，避免测试联网）；
  - 所有 LLM 依赖都集中在 evolution（抽象）/controller（调度）——
    检索与存储层**不依赖 LLM**，保证可独立评测（docs/04 避坑点 3）。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Protocol


# ---------------------------------------------------------------- 协议定义
class LLMClient(Protocol):
    """LLM 客户端协议（结构化鸭子类型，便于团队各自实现）。"""

    def chat(self, system: str, user: str) -> str:
        """通用对话。"""
        ...

    def summarize(self, text: str, max_words: int = 100) -> str:
        """摘要（进化模块'抽象'操作用）。"""
        ...

    def extract_memory_ops(self, dialogue: str) -> List[Dict[str, Any]]:
        """从对话/复盘中抽取记忆操作建议 [{op, type, content, importance}]。"""
        ...


# ---------------------------------------------------------------- Mock 实现
class MockLLM:
    """离线确定性 LLM——冒烟测试 / 消融回放 / 无网演示用。

    行为约定（保证测试可断言）：
      - chat:       返回包含用户关键词的固定模板（演示"规划输出"）；
      - summarize:  抽取式摘要——取前 max_words 个词 + 首句（确定性）；
      - extract_memory_ops: 规则抽取——按行扫描 "教训/经验/事实/失败/成功"
                            关键词生成建议操作（无真模型时的进化兜底）。
    """

    name = "mock"

    def chat(self, system: str, user: str) -> str:
        # 取用户输入前 60 字做回显，模拟"基于记忆生成规划"
        head = re.sub(r"\s+", " ", user)[:60]
        return f"[MockLLM] 基于 {len(system)} 字系统指令与装载记忆，针对「{head}…」生成规划草案。"

    def summarize(self, text: str, max_words: int = 100) -> str:
        """抽取式摘要：首句 + 截断到 max_words 词。"""
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""
        first_sent = re.split(r"[。！？.!?]", text)[0] or text[:50]
        words = text.split()
        body = " ".join(words[:max_words])
        return f"{first_sent}（摘要：{body}）"

    def extract_memory_ops(self, dialogue: str) -> List[Dict[str, Any]]:
        """规则式记忆操作抽取——演示进化闭环的兜底实现。

        真实系统应换成提示词工程让 LLM 输出 JSON（接口不变，实现可换）。
        """
        ops: List[Dict[str, Any]] = []
        for line in dialogue.splitlines():
            line = line.strip()
            if not line:
                continue
            # 关键词规则：命中即建议一条写入操作（演示用，足够跑通闭环）
            if any(k in line for k in ("教训", "经验", "失败", "成功", "战例", "参数", "条令")):
                mtype = "fact" if any(k in line for k in ("参数", "条令")) else "experience"
                ops.append({
                    "op": "write",
                    "type": mtype,
                    "content": line[:200],
                    "importance": 2.0 if any(k in line for k in ("失败", "教训")) else 1.0,
                })
        return ops


# ---------------------------------------------------------------- 真实客户端骨架
class OpenAICompatibleClient:
    """OpenAI 兼容接口客户端骨架（智戎平台 / DeepSeek / vLLM 均兼容此协议）。

    使用方法（接入真模型时）：
        client = OpenAICompatibleClient(
            base_url="http://<智戎或本地网关>/v1",
            api_key="<KEY>",           # 从环境变量读，不要硬编码进仓库！
            model="deepseek-chat",
        )
    注意：
      - 依赖 requests（未装时 import 报错，属预期——MVP 不需要它）；
      - 严禁把 api_key 提交进 git（.gitignore 已挡 .env）。
    """

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _post(self, payload: Dict[str, Any]) -> str:
        import requests  # 延迟导入：MVP 不装 requests 也能跑其它部分
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={**payload, "model": self.model},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def chat(self, system: str, user: str) -> str:
        return self._post({
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,  # 规划场景低温，保稳定
        })

    def summarize(self, text: str, max_words: int = 100) -> str:
        sys_prompt = "你是军事规划复盘助手。输出不超过 {n} 词的中文摘要，只保留关键事实与结论。"
        return self.chat(sys_prompt.format(n=max_words), text)

    def extract_memory_ops(self, dialogue: str) -> List[Dict[str, Any]]:
        """让 LLM 按 JSON Schema 输出记忆操作建议（真模型版）。"""
        sys_prompt = (
            "你是记忆管理器。阅读对话/复盘，输出 JSON 数组，每项形如："
            '{"op":"write|merge|forget|abstract","type":"fact|experience",'
            '"content":"...","importance":1.0}。只输出 JSON，不要解释。'
        )
        raw = self.chat(sys_prompt, dialogue)
        try:
            # 容错：截取首个 [ 到末尾 ] 之间的内容再解析
            m = re.search(r"\[.*\]", raw, re.S)
            return json.loads(m.group(0)) if m else []
        except json.JSONDecodeError:
            return []


def get_llm(kind: str = "mock", **kwargs: Any) -> LLMClient:
    """LLM 工厂：按配置返回 Mock 或真实客户端。

    用法：llm = get_llm("mock") / get_llm("openai", base_url=..., api_key=..., model=...)
    """
    if kind == "mock":
        return MockLLM()
    if kind == "openai":
        return OpenAICompatibleClient(**kwargs)
    raise ValueError(f"未知 LLM 类型: {kind}（可选 mock/openai）")
