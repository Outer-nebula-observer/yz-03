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
        """摘要（工作记忆 flush 递归摘要用）。"""
        ...

    def abstract(self, material: str, theme: str = "") -> str:
        """抽象（进化模块'抽象'操作专用：多条经验 → 一条通用教训）。

        【评审修复】此前 abstract 复用 summarize 且把带指令前缀的
        prompt 整段传入——Mock 的抽取式摘要会把"以下为多条作战复盘
        经验…请抽象出…"这类**指令文本本身**写进记忆并永久入库。
        现单列协议方法：调用方只传材料本体，指令留在实现侧。
        """
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
        # 回显用户输入前 300 字，模拟"基于（含装载记忆的）上下文生成规划"。
        # 【评审修复】原 60 字回显只能覆盖 goal/约束——装载记忆排在
        # 上下文中后部，回显太短使 task 级"记忆引用率"无法度量。
        head = re.sub(r"\s+", " ", user)[:300]
        return f"[MockLLM] 基于 {len(system)} 字系统指令与装载记忆，针对「{head}」生成规划草案。"

    def summarize(self, text: str, max_words: int = 100) -> str:
        """抽取式摘要：首句 + 截断正文（中文按字符计）。

        【Bug 修复】原实现 `text.split()` 按空白切"词"——中文整段无空格
        → 全文成为 1 个"词" → max_words 完全失效，摘要=首句+全文。
        连锁后果：工作记忆递归摘要每次 flush 都把旧摘要+驱逐消息**全文**
        拼进新摘要 → 摘要无界膨胀（压缩研究实测峰值 29531 tokens，
        "压缩"变成"放大"）。现按字符数截断（中文 1 字≈1 词）。
        """
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""
        first_sent = re.split(r"[。！？.!?]", text)[0] or text[:50]
        body = text[:max_words]
        return f"{first_sent}（摘要：{body}）"

    def abstract(self, material: str, theme: str = "") -> str:
        """抽取式'抽象'：每条经验取首个分句拼接（Mock 保底）。

        真模型版由 LLM 归纳通用教训；Mock 保证**不含指令文本**
        （评审修复：此前 prompt 指令残留被写进记忆）。
        """
        clauses = []
        for line in material.splitlines():
            line = line.strip().lstrip("-").strip()
            if not line:
                continue
            head = re.split(r"[。！？;；,，]", line)[0] or line[:30]
            if head:
                clauses.append(head[:60])
        if not clauses:
            return ""
        prefix = f"通用教训（{theme}）：" if theme else "通用教训："
        return prefix + "；".join(clauses)

    def extract_memory_ops(self, dialogue: str) -> List[Dict[str, Any]]:
        """规则式记忆操作抽取（句子粒度）——演示进化闭环的兜底实现。

        【评审修复·两处】
        1. 粒度：原按"行"抽取——"复盘：任务部分达成。教训：A。经验：B。"
           整行成为**一条**记忆（结果陈述+两类教训混在一条，且整行
           '复盘：'前缀入库）。现按句（。！？）切分后逐句分类。
        2. importance 交互：原"含'教训'即 2.0"，而遗忘保护线恰为
           importance>=2.0 → **所有教训永久免遗忘**（遗忘机制系统性
           失效、经验库无界增长——实测复盘 30 天后只删正向经验）。
           现自动抽取教训给 1.5（**不越保护线**）：保护线保留给显式
           高价值标记（种子/人工复盘标注 importance=2.0、抽象产物
           max+0.5），未被复用的复盘教训仍会被遗忘淘汰。
        """
        ops: List[Dict[str, Any]] = []
        for line in dialogue.splitlines():
            for sent in re.split(r"(?<=[。！？!?])", line):
                sent = sent.strip()
                # 【评审修复】剥离"复盘：/总结："等段落标记前缀——
                # "复盘：教训：xxx。"整句抽取时前缀会污染记忆内容
                # （实测使向量分数下降 ~0.01-0.02，阈值边缘翻转）。
                sent = re.sub(r"^(复盘|总结|复盘总结|行动回顾)[:：]", "", sent).strip()
                if not sent:
                    continue
                if any(k in sent for k in ("教训", "经验", "失败", "成功",
                                           "战例", "参数", "条令")):
                    mtype = ("fact" if any(k in sent for k in ("参数", "条令"))
                             else "experience")
                    ops.append({
                        "op": "write",
                        "type": mtype,
                        "content": sent[:200],
                        "importance": (1.5 if any(k in sent for k in ("失败", "教训"))
                                       else 1.0),
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

    def abstract(self, material: str, theme: str = "") -> str:
        """真模型版抽象：多条经验 → 1 条跨场次可复用的通用教训。"""
        sys_prompt = ("你是作战复盘参谋。把多条经验归纳为 1 条可跨场次复用的"
                      f"通用教训（主题：{theme or '综合'}），只输出教训本身，"
                      "不要复述指令。")
        return self.chat(sys_prompt, material)

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
