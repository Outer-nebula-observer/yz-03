# 论文精读：LLMLingua — Compressing Prompts for Accelerated Inference of Large Language Models

> - **作者 / 机构**：Huiqiang Jiang、Qianhui Wu、Chin-Yew Lin 等（Microsoft 研究院）
> - **发表**：EMNLP 2023（arXiv 2310.05736）
> - **对应模块**：`references/01_短期记忆/Jiang2023-LLMLingua.pdf`
> - **全文提取**：`references/01_短期记忆/Jiang2023-LLMLingua.md`
> - **官方代码**：https://aka.ms/LLMLingua（GitHub: `microsoft/LLMLingua`）

## 一句话总结

**面向 Prompt 的"由粗到细"压缩方法：用预算控制器在极高压缩率下保住语义完整性，用 token 级迭代压缩刻画被压缩内容之间的依赖，再用指令微调让压缩对齐目标语言模型的分布，最高可做到 20× 压缩而几乎不掉性能。**

## 摘要（归纳）

CoT 提示、上下文学习（ICL）等使送入 LLM 的 prompt 越来越长（可达上万 token），推理成本剧增。本文提出 LLMLingua：
- **预算控制器（budget controller）**：全局压缩率 → 各层级（word/token/perplexity）动态分配预算，保证语义完整性；
- **token 级迭代压缩算法**：基于 token 间互信息/困惑度，迭代式地决定删除哪些 token，建模被压缩内容之间的相互依赖；
- **指令微调对齐**（LLMLingua-2 思路的先导）：用少量数据让压缩后的提示分布与目标 LLM 对齐。
在 GSM8K / BBH / ShareGPT / Arxiv-March23 四个不同场景数据集上取得当时 SOTA，**20× 压缩下性能损失很小**。

## 技术路线

```
原始 prompt
   └─① 粗粒度压缩（按句/段重要性粗筛 + 预算分配）
        └─② 细粒度 token 级压缩（困惑度 + token 间依赖迭代删除）
             └─③ 指令微调对齐（压缩分布 → 目标 LLM 分布）
                  └─ 输入 LLM，加速推理
```

## 关键结果

| 场景 | 结果 |
|---|---|
| GSM8K | 高压缩比下仍保持高准确率（相对无压缩基线损失极小） |
| 长 prompt 场景 | 最多 20× 压缩、token 数大幅下降 |
| 推理开销 | 吞吐提升 / 延迟下降（Prefill 成本随 token 数线性下降） |

## 代码索引

- 官方仓库（开源）：https://github.com/microsoft/LLMLingua （含 LLMLingua / LongLLMLingua / LLMLingua-2 全家桶与评测脚本）
- 本仓库语境：压缩能力可复用于赛题③的"短期记忆压缩"，运行位 `paper_code/短期记忆/`（待复现）。

## 优点 / 局限

- **优点**：即插即用、无需改 LLM 结构；压缩率高且可控（预算控制器）；与模型无关，可配任意黑盒/白盒 LLM。
- **局限**：压缩以"删 token"为手段，可能删掉关键约束；对"必须保留的字段"无原生标记机制；主要面向单次 prompt，需扩展才能直接服务多轮长程记忆。

## 与赛题③的联系

| 借鉴点 | 说明 |
|---|---|
| 预算控制器 | 赛题短期记忆的"压缩率动态分配"可仿照：对约束字段高预算、对历史闲聊低预算 |
| 高压缩比基线 | 作为短期记忆"长度截断 vs 摘要 vs 压缩"消融实验的对比项 |
| 依赖建模 | 压缩时保留关键实体/约束之间的依赖，防止约束断裂（对应 `docs/04` 避坑点 6"约束不可压缩标记"） |

---
*姊妹篇 LongLLMLingua 见 `笔记_Jiang2024-LongLLMLingua.md`。*