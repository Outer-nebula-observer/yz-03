# 论文精读（深化版）：LLMLingua — Compressing Prompts for Accelerated Inference of Large Language Models

> - **作者 / 机构**：Huiqiang Jiang、Qianhui Wu、Chin-Yew Lin、Yuqing Yang、Lili Qiu（Microsoft 研究院）
> - **发表**：EMNLP 2023（arXiv 2310.05736）
> - **对应**：`references/01_短期记忆/Jiang2023-LLMLingua.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/microsoft/LLMLingua（含 LLMLingua / LongLLMLingua / LLMLingua-2）

## 一句话总结

面向 Prompt 的"由粗到细"压缩：**预算控制器**按困惑度在 instruction/demonstrations/question 间分配预算保语义完整，**token 级迭代压缩（ITPC）**建模被压缩内容间依赖，**指令微调对齐**让压缩分布贴合目标 LLM——最高 20× 压缩、性能几乎不掉，端到端 1.7×–5.7× 加速。

## 1. 问题与方法动机

CoT、ICL、RAG、多轮 agent 让 prompt 越来越长（上万 token），推理成本与延迟剧增。已有压缩分两类：**生成式**（LLM 改写摘要，慢且可能失真）与**选择式**（按打分删片段，如 Selective-Context 删 token）。LLMLingua 走**选择式 + 由粗到细**路线，用一个小 LM（如 7B LLaMA）做困惑度打分来决定删什么。

## 2. 技术路线（三组件）

```
原始 prompt x = (x_ins 指令, x_dems 示例, x_que 问题)
  ├─① 预算控制器（Algorithm 1，粗粒度）
  │    · 按 target 压缩率 τ 算 demonstrations 压缩率 τ_dems
  │    · 用小 LM M_s 算每个 demo 的困惑度，降序排
  │    · 顺序追加 demo 到 D，直到 token 数超 k·τ_dems·L_dems 停
  │    · 剩余预算 Δτ 分配给 instruction 与 question
  ├─② 迭代 token 级压缩 ITPC（Algorithm 2，细粒度）
  │    · 把剩余 prompt 切段 S
  │    · 迭代 m 次：条件概率 p(s_i) → 阈值 γ_i → 保留高于阈值的 token 拼到 T
  │    · 用 KV cache 复用前文，建模被压缩内容之间的相互依赖
  └─③ 指令微调对齐
       · 让压缩后 prompt 的分布与目标 LLM 对齐（先导思路，LLMLingua-2 系统化）
```

**核心设计点**：
- **粗→细**：先 demo 级（保语言完整性，避免高压缩时 token dropout 让 prompt 太琐碎丢关键信息），再 token 级；
- **预算控制器**对 instruction/question 给更小压缩率（保护关键约束），对 demonstrations 给更大压缩率（冗余多）；
- **条件困惑度**而非独立打分：第 i 段的保留取决于已保留前文，建模依赖。

## 3. 关键实验结果

| 场景 | 结果 |
|---|---|
| 数据集 | GSM8K / BBH / ShareGPT / Arxiv-March23（覆盖推理/对话/摘要/代码） |
| 压缩率 | 最高 20×，性能损失很小；优于 Selective-Context 与随机/尾部截断基线 |
| 生成质量 | 压缩 prompt 仍能引导多步推理；Selective-Context 压缩会破坏推理逻辑 |
| 计算开销公式 | c = (L + kL/τ + L/τ)·c_small + (L/τ)·c_LLM；小 LM 成本 c_small ≈ (7/175)·c_LLM = 1/25·c_LLM |
| τ=5 时 | c ≈ 0.264·L·c_LLM ≈ **1/4 原成本**（约 4× 节省） |
| 端到端延迟（V100-32G，GSM8K） | 1×→8.6s 基线；2×→4.9s(1.7×)；5×→2.3s(3.3×)；10×→1.3s(5.7×)；LLMLingua 自身开销 0.8/0.3/0.2s |

> 关键洞察：压缩不只省输入成本，生成阶段也省（压缩率↑→生成 token 长度↓）。

## 4. 代码索引

- 官方仓库：https://github.com/microsoft/LLMLingua（全家桶 + 评测脚本）
- 本仓库语境：压缩能力可复用于赛题③短期记忆压缩；运行位 `paper_code/短期记忆/`。

## 5. 优点 / 局限（深化）

- **优点**：即插即用、无需改 LLM 结构、模型无关；预算控制器让"关键约束少压、冗余多压"；条件困惑度建模依赖，保真优于独立打分。
- **局限**：删 token 式压缩可能误删关键约束字段（赛题作战约束需"不可压缩"标记）；需一个小 LM 做打分（额外组件）；主要面向单次 prompt，多轮长程记忆需扩展；高压缩时 demo 级 dropout 会牺牲示例完整性。

## 6. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 预算控制器（按重要性分配压缩率） | 赛题短期记忆压缩：约束/目标字段高预算、历史闲聊低预算 |
| 条件困惑度（建模依赖） | 压缩时保留关键实体/约束间依赖，防约束断裂（`docs/04` 避坑点 6） |
| 计算开销公式 + 4×/5.7× 数据 | 组会汇报"短期压缩收益"量化论据 |
| 消融对照组 | "截断 vs 摘要 vs LLMLingua vs LongLLMLingua"四路消融 |

---
*姊妹篇 LongLLMLingua 见 `笔记_Jiang2024-LongLLMLingua.md`；可学习压缩见 `笔记_Ge2024-ICAE.md`。*

## 代码实证（结合 paper_code/）

- 仓库：`paper_code/01_短期记忆/LLMLingua/`
- **可直接用**：`llmlingua/prompt_compressor.py` 的 `PromptCompressor` 类——`from llmlingua import PromptCompressor; pc = PromptCompressor(); pc.compress_prompt(...)`，已入 LangChain/LlamaIndex。
- 学由粗到细压缩：`examples/RAG.ipynb`、`examples/CoT.ipynb`、`examples/Code.ipynb`。
- 赛题用法：短期记忆压缩消融对照组（截断/摘要/LLMLingua 四路对比）。