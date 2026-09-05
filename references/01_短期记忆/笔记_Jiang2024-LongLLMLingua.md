# 论文精读：LongLLMLingua — Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression

> - **作者 / 机构**：Huiqiang Jiang、Qianhui Wu、Xufang Luo 等（Microsoft 研究院）
> - **发表**：ACL 2024（arXiv 2310.06839）
> - **对应模块**：`references/01_短期记忆/Jiang2024-LongLLMLingua.pdf`
> - **全文提取**：`references/01_短期记忆/Jiang2024-LongLLMLingua.md`
> - **官方代码**：https://aka.ms/LongLLMLingua（GitHub: `microsoft/LLMLingua`）

## 一句话总结

**LLMLingua 的长上下文升级版：针对长上下文三痛点（成本高、性能下降、位置偏置），通过「关键信息感知的 token 重排序 + 问题感知压缩 + 动态压缩率」提升 LLM 对关键信息的感知，同时降本增效——NQ 上最多 +21.4% 性能且 token 少约 4×。**

## 摘要（归纳）

长上下文场景下 LLM 面临三大挑战：**计算成本高、性能下降、位置偏置**（middle/lost-in-the-middle 现象）。已有研究指出 LLM 性能取决于关键信息在输入中的**密度与位置**。LongLLMLingua 据此设计：
1. **关键信息感知重排序（reordering）**：把文档中与问题最相关的内容移到 prompt 前/后（远离中部失效区）；
2. **问题感知压缩**：以问题的 token 为锚点，计算各文档片段与问题的相关性再压缩；
3. **动态压缩率**：按任务/上下文自动调节压缩力度。
评测显示：NaturalQuestions 上性能最高提升 21.4%、token 减少约 4×；LooGLE 上成本降低 94.0%；对约 10k token 的 prompt 做 2×–6× 压缩时端到端延迟加速 **1.4×–2.6×**。

## 技术路线

```
长上下文 + 问题(Q)
 ├─① 检索/docs 排序：按与 Q 的相关性粗排
 ├─② 课程式压缩（coarse→fine）：粗筛 → token 级迭代删除
 ├─③ 关键信息重排：相关片段移到首/尾，避开"中部信息遗忘区"
 └─④ 输入 LLM（长上下文问答 / RAG / 多轮对话）
```

## 关键结果

| 基准 | 效果 |
|---|---|
| NaturalQuestions | 相比 GPT-3.5-Turbo 基线最高 +21.4%，token 减少 ~4× |
| LooGLE | 成本降低 94.0% |
| 端到端延迟 | 10k tokens、2×–6× 压缩 → 加速 1.4×–2.6× |
| TriviaQA / HotpotQA / LongBench 系列 | 压缩后性能持平或提升（位置偏置缓解） |

## 代码索引

- 官方仓库：https://github.com/microsoft/LLMLingua （与 LLMLingua 同仓库，`LongLLMLingua` 目录）
- 本仓库语境：压缩 + 重排的"关键信息感知"思路可用于短期记忆装载前的排序与截断；独立复现位 `paper_code/短期记忆/`。

## 优点 / 局限

- **优点**：同时解决成本 / 性能 / 位置偏置三问题；对 RAG 与多轮对话天然适配；无需微调。
- **局限**：需要"问题"来引导压缩，无显式问题时效果打折；重排改变了原文顺序，对强位置敏感的任务需谨慎；仍是删 token 式压缩，长程结构化记忆（图谱/SQL）不适用。

## 与赛题③的联系

| 借鉴点 | 说明 |
|---|---|
| 问题感知 + 关键信息重排 | 赛题"查询列表 → 检索 → 装载"链路中，检索结果可按 q 相关性重排再入上下文 |
| 位置偏置缓解 | 长场次规划上下文装载时，把作战约束/目标放在首尾，避免中部遗忘 |
| 动态压缩率 | 短期记忆压缩的消融对照组（截断 / 摘要 / LLMLingua / LongLLMLingua） |
| 成本账 | 组会汇报可引用"NQ +21.4%、token 少 4×"证明短期压缩的收益数量级 |

---
*基础版见 `笔记_Jiang2023-LLMLingua.md`。*