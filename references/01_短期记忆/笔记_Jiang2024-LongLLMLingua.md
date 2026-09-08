# 论文精读（深化版）：LongLLMLingua — Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression

> - **作者 / 机构**：Huiqiang Jiang、Qianhui Wu、Xufang Luo 等（Microsoft 研究院）
> - **发表**：ACL 2024（arXiv 2310.06839）
> - **对应**：`references/01_短期记忆/Jiang2024-LongLLMLingua.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/microsoft/LLMLingua

## 一句话总结

LLMLingua 的长上下文升级版：针对长上下文三痛点（成本高、性能下降、位置偏置），用「**问题感知的粗粒度压缩（rk 指标）+ token 级压缩 + 子序列恢复**」提升 LLM 对关键信息的感知——NQ 上 +21.4% 性能且 token 少约 4×，LooGLE 成本降 94%，10k token 2×–6× 压缩端到端加速 1.4×–2.6×。

## 1. 问题与动机（三痛点）

长上下文场景 LLM 三大挑战：
1. **计算成本高**（注意力二次方）；
2. **性能下降**（冗长无关信息淹没关键信息）；
3. **位置偏置**（lost-in-the-middle：关键信息在中部时利用率低）。
已有研究指出 LLM 性能取决于关键信息的**密度与位置**。LongLLMLingua 据"问题感知"压缩同时解三痛点。

## 2. 技术路线

```
长上下文 prompt x + 问题 Q
  ├─① 问题感知粗粒度压缩（ranker 指标 rk）
  │    · 按"文档/片段与 Q 的关联"排序（替代纯信息熵打分）
  │    · 删低关联片段，保原文顺序
  ├─② token 级迭代压缩（ITPC，沿用 LLMLingua）
  │    · segment size=200，条件困惑度阈值保留
  ├─③ 子序列恢复（Algorithm 1，后处理保真）
  │    · 生成后把 compressed prompt 里的 token 还原为 original prompt 中最长公共子序列
  │    · 让最终回答尽可能用原文 token，避免压缩导致的语义漂移
  └─④ （可选）重排序：把高关联片段移到首/尾，避开"中部失效区"
       （论文引用 LangChain long_context_reorder）
```

**与 LLMLingua 的关键差异**：
- 粗粒度打分用**问题感知 rk**（文档-Q 关联）而非纯困惑度——解决"冗余信息多时纯熵压缩塞进噪声、甚至比 zero-shot 还差"；
- 新增**子序列恢复**——压缩改变了 token，后处理把它们还原回原文 token，保真。

## 3. 实验设置与结果

- **目标 LLM**：GPT-3.5-Turbo-0613（>4k 用 16k）、LongChat-13B-16k；小 LM 用 LLaMA-2-7B-Chat；greedy decoding，温度 0。
- **数据集**：NaturalQuestions（多文档 QA）、LongBench & ZeroSCROLLS（通用长上下文）、MuSiQue（多跳 QA）、LooGLE（长依赖 QA）。
- **基线**：检索式（BM25/Gzip/SentenceBERT/OpenAI Embedding/rk）+ 压缩式（Selective Context、LLMLingua）。

| 场景 | 结果 |
|---|---|
| NaturalQuestions（真值文档在第 10 位） | **+21.4%**，token 少约 4×（GPT-3.5-Turbo） |
| LooGLE | 成本降 **94.0%** |
| 端到端延迟（~10k token，2×–6× 压缩） | 加速 **1.4×–2.6×** |
| 鲁棒性 | 各任务、各压缩率下均优于基线；随压缩率↑，检索法因 recall 下降而退化，LongLLMLingua 仍稳 |

**关键发现**：纯熵压缩（Selective Context/LLMLingua）在冗余信息多的任务上表现差（甚至不如 zero-shot）；检索法在低压缩率好但高压缩率退化；问题感知压缩最鲁棒。

## 4. 代码索引

- 官方仓库：https://github.com/microsoft/LLMLingua（`LongLLMLingua` 目录，与 LLMLingua 同仓库）
- 本仓库语境：问题感知压缩 + 子序列恢复可用于短期记忆装载前的"查询列表→排序→压缩"；复现位 `paper_code/短期记忆/`。

## 5. 优点 / 局限（深化）

- **优点**：同时解成本/性能/位置偏置三问题；问题感知 rk 解决纯熵压缩"塞噪声"问题；子序列恢复保真；与 RAG/多轮 agent 天然适配。
- **局限**：需要"问题 Q"引导压缩，无显式 query 时效果打折；子序列恢复依赖原文 token 匹配，对改写型回答无效；仍是删 token 式，长程结构化记忆（图谱/SQL）不适用；重排改变原文顺序，位置敏感任务需谨慎。

## 6. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 问题感知 rk（按 q 关联排序压缩） | 赛题"查询列表→检索→装载"：检索结果按 q 相关性排序再压缩入上下文 |
| 子序列恢复 | 压缩后回答尽量引用原文 token → 可解释溯源（创新点 E） |
| 位置偏置缓解 | 长场次规划上下文：作战约束/目标放首尾，避免中部遗忘 |
| 成本账 | NQ +21.4%/4×、LooGLE -94%、延迟 1.4×–2.6× → 组会汇报量化论据 |
| 消融对照 | 截断/摘要/LLMLingua/LongLLMLingua 四路短期压缩消融 |

---
*基础版见 `笔记_Jiang2023-LLMLingua.md`；可学习压缩见 `笔记_Ge2024-ICAE.md`。*

## 论文核心代码（paper_code 索引）

- 与 LLMLingua 同仓库同包：`llmlingua/prompt_compressor.py` 的 `PromptCompressor`——LongLLMLingua 模式靠参数区分（`condition_in_question` 问题感知开关、文档级 ranker、`target_context`）；
- RAG 实战示例：`examples/RAG.ipynb`（检索后压缩的完整链路，对我们最有参考价值）。

## 我们的实现（memsys）

- **思路**：借两点——①"问题感知"：查询列表（`QueryItem.query_text`）作为压缩排序锚而非盲压；②"关键信息放首尾"：`render()` 头部放目标/约束、尾部放最新消息，规避 lost-in-the-middle；
- **代码索引**：`memsys/short_term/working_memory.py::render()`（首尾布局）、`memsys/retrieval/hybrid.py`（检索结果按 q 相关性排序后才装载——问题感知排序前置）。

## 代码详解（我们的 render 首尾布局）

```python
# memsys/short_term/working_memory.py::render()（节选）
parts = []
if self.slot.goal:        parts.append(f"【目标】{self.slot.goal}")          # 头部
if self.slot.constraints: parts.append("【约束】" + "；".join(...))          # 头部
if self._recursive_summary: parts.append(f"【历史摘要】{...}")               # 中部
if self.slot.working_context: parts.append(f"【关键信息】{...}")             # 中部
if self.slot.query_list:  parts.append(f"【查询列表】{...}")                  # 尾部
if self.slot.fifo_queue:  parts.append("【近期消息】" + ...)                 # 尾部（最新）
```
> 与 LongLLMLingua 的对应：首尾=高利用率区（放不可压缩的目标/约束与最新消息），中部=低利用率区（放可再压缩的摘要与工作上下文）。这个顺序就是"位置偏置缓解"的落地形态。