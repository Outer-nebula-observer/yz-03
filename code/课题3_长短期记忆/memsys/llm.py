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

import io
import json
import os
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


# ---------------------------------------------------------------- 本地配置加载
def load_env(dotenv_path: Optional[str] = None) -> Dict[str, str]:
    """零依赖 .env 加载器：读 KEY=VALUE 行，不覆盖已存在的环境变量。

    查找顺序（首个命中的 .env）：显式路径 → cwd → memsys 包各级父目录
    （课题3_长短期记忆/ → code/ → 仓库根）。密钥只放 .env（已 gitignore），
    严禁硬编码进仓库。
    """
    loaded: Dict[str, str] = {}
    candidates: List[str] = []
    if dotenv_path:
        candidates.append(dotenv_path)
    candidates.append(os.path.join(os.getcwd(), ".env"))
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):  # memsys/ → 课题3/ → code/ → 仓库根
        here = os.path.dirname(here)
        candidates.append(os.path.join(here, ".env"))
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            for line in io.open(path, encoding="utf-8").read().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("\"'")
                if v and k not in os.environ and k not in loaded:
                    os.environ[k] = v
                    loaded[k] = v
        except OSError:
            continue
        if loaded:
            break
    return loaded


# ---------------------------------------------------------------- JSON 容错解析
def parse_llm_json(raw: str) -> List[Dict[str, Any]]:
    """解析 LLM 输出的 JSON 数组（真模型验证发现的三类噪声全容忍）：

      1. ```json 围栏（GLM/gpt 系默认习惯）；
      2. 前后解释文本包裹；
      3. 单对象（漏写外层 []）。
    """
    if not raw or not raw.strip():
        return []
    text = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    # 直接解析
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, list) else ([obj] if isinstance(obj, dict) else [])
    except json.JSONDecodeError:
        pass
    # 括号平衡截取首个 [...]（容忍尾部解释文本）
    start = text.find("[")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        if isinstance(obj, list):
                            return obj
                    except json.JSONDecodeError:
                        break
    # 单对象兜底
    a, b = text.find("{"), text.rfind("}")
    if a >= 0 and b > a:
        try:
            obj = json.loads(text[a:b + 1])
            if isinstance(obj, dict):
                return [obj]
        except json.JSONDecodeError:
            pass
    return []


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


# ---------------------------------------------------------------- 真实客户端
class OpenAICompatibleClient:
    """OpenAI 兼容接口客户端（智戎平台 / DeepSeek / vLLM / GLM 均兼容此协议）。

    【v0.4 改造】HTTP 层从 requests 换成 stdlib urllib.request——
    真模型路径也保持**零第三方依赖**（与 Mock 路径同一哲学，部署环境
    无需 pip install）。

    使用方法：
        client = OpenAICompatibleClient(
            base_url="http://<智戎或本地网关>/v1",
            api_key=os.environ["LLM_KEY"],   # 从环境变量/.env 读，严禁硬编码
            model="deepseek-chat",
        )
    """

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: float = 60.0,
                 extra_body: Optional[Dict[str, Any]] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        # 附加请求体（如 GLM 的 {"thinking": {"type": "disabled"}}）
        self.extra_body: Dict[str, Any] = extra_body or {}

    def _post(self, payload: Dict[str, Any]) -> str:
        """POST /chat/completions（stdlib urllib，指数退避重试 3 次）。

        重试动机：GLM 网关实测偶发 SSL 握手瞬断（embedding 端点同款问题，
        见 OpenAIEmbedding.embed）——进化/规划在挂接点上被单次瞬断打断
        不可接受（智戎链路要求"记忆系统故障不阻断规划"）。
        """
        import time as _time
        import urllib.request  # stdlib——零依赖
        body = json.dumps({**payload, "model": self.model, **self.extra_body},
                          ensure_ascii=False).encode("utf-8")
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/chat/completions", data=body,
                    method="POST",
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {self.api_key}"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                # 思考型模型：reasoning_content 与 content 分离——只取 content
                msg = (data.get("choices") or [{}])[0].get("message", {})
                return msg.get("content") or ""
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    _time.sleep(0.8 * (2 ** attempt))
        raise RuntimeError(f"LLM 调用连续 3 次失败: {last_exc}")

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
                      f"通用教训（主题：{theme or '综合'}），只输出教训本身（一句话），"
                      "不要复述指令、不要罗列原文。")
        return self.chat(sys_prompt, material)

    def extract_memory_ops(self, dialogue: str) -> List[Dict[str, Any]]:
        """真模型版记忆抽取（JSON 数组，容错解析见 parse_llm_json）。

        prompt 约定（v0.4 强化，两处防缺陷设计）：
          1. importance 语义分级——2.0 在遗忘模型里是"保护线"（永不遗忘），
             必须显式告知 LLM 慎用，否则它会习惯性给教训打 2.0、
             重现 v0.2 修复过的"遗忘机制系统性失效"；
          2. content 保留"教训：/经验："标记前缀——G2 晋升门控与阶段归因
             （attr_stage）依赖内容关键词判别，裸句会被误拒/漏归因。
        """
        sys_prompt = (
            "你是作战复盘的记忆管理器。从复盘中抽取值得长期保留的记忆，"
            "输出 JSON 数组，每项形如："
            '{"op":"write","type":"fact|experience","content":"...","importance":1.0}。'
            "约定：type=experience 用于教训/经验/对策（content 以'教训：'或'经验：'"
            "开头）；type=fact 用于装备参数/条令/地形等跨场次稳定的客观事实；"
            "importance 分级：1.0=一般经验，1.5=重要教训，2.0=仅限人命关天、"
            "绝不能忘的保命教训（2.0 永不遗忘，慎用）；"
            "场次过程叙述（如'某部于某时机动'）不要抽取。"
            "只输出 JSON 数组，不要解释。"
        )
        raw = self.chat(sys_prompt, dialogue)
        ops: List[Dict[str, Any]] = []
        for op in parse_llm_json(raw):
            if not isinstance(op, dict):
                continue
            content = str(op.get("content", "")).strip()
            if not content:
                continue
            mtype = op.get("type", "experience")
            if mtype not in ("fact", "experience"):
                mtype = "experience"
            try:
                imp = float(op.get("importance", 1.0))
            except (TypeError, ValueError):
                imp = 1.0
            ops.append({"op": str(op.get("op", "write")),
                        "type": mtype, "content": content,
                        "importance": min(max(imp, 0.5), 2.0)})
        return ops


class GLMClient(OpenAICompatibleClient):
    """智谱 GLM 客户端（bigmodel.cn OpenAI 兼容协议，stdlib 零依赖）。

    配置来源（优先级）：显式参数 > 环境变量 > .env（load_env 自动加载）：
        GLM_API_KEY     密钥（.env，严禁入库）
        GLM_MODEL       对话模型（默认 glm-4.5-air：实测 2.4s/次、抽取质量优）
        GLM_EMBED_MODEL 向量模型（默认 embedding-2，见 embeddings.py）

    模型选择实测（2026-09，同一抽取任务）：
        glm-4.5-air   2.4s  质量优（默认——速度/质量/成本平衡点）
        glm-4.5       5.7s  质量最优（旗舰，重要消融可用）
        glm-4-flash   1.8s  质量可用（最省）
        glm-4.5-flash 20s+  稳态过慢（免费档限速，不推荐）
    """

    BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    # 思考型模型（glm-4.5 系）默认开思考——抽取/摘要类任务要快答案，
    # 默认禁用；enable_thinking=True 可开（复杂规划生成时建议开）。
    THINKING_MODELS = ("glm-4.5", "glm-4.6")

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 timeout: float = 90.0, enable_thinking: bool = False) -> None:
        load_env()  # 零依赖 .env 加载（幂等，不覆盖已有环境变量）
        api_key = api_key or os.environ.get("GLM_API_KEY", "")
        model = model or os.environ.get("GLM_MODEL", "glm-4.5-air")
        if not api_key:
            raise ValueError("缺少 GLM_API_KEY：请在 .env 或环境变量设置"
                             "（.env 模板见仓库根 README）")
        extra: Dict[str, Any] = {}
        if not enable_thinking and any(model.startswith(p)
                                       for p in self.THINKING_MODELS):
            extra["thinking"] = {"type": "disabled"}
        super().__init__(base_url=self.BASE_URL, api_key=api_key, model=model,
                         timeout=timeout, extra_body=extra)
        self.enable_thinking = enable_thinking


def get_llm(kind: str = "mock", **kwargs: Any) -> LLMClient:
    """LLM 工厂：mock（离线默认）/ glm（智谱）/ openai（任意兼容网关）。

    用法：
        llm = get_llm("mock")                          # 离线
        llm = get_llm("glm")                           # 读 .env 的 GLM_API_KEY/GLM_MODEL
        llm = get_llm("glm", model="glm-4.5")          # 旗舰
        llm = get_llm("openai", base_url=..., api_key=..., model=...)
    """
    if kind == "mock":
        return MockLLM()
    if kind == "glm":
        return GLMClient(**kwargs)
    if kind == "openai":
        return OpenAICompatibleClient(**kwargs)
    raise ValueError(f"未知 LLM 类型: {kind}（可选 mock/glm/openai）")
