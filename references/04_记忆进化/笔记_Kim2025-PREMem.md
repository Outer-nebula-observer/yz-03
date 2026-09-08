# 论文精读（深化版）：PREMem — Pre-Storage Reasoning for Episodic Memory

> - **作者 / 机构**：Sangyeop Kim、Yohan Lee、Sungzoon Cho 等（首尔国立大学 / Coxwave / KAIST）
> - **发表**：arXiv 2025（2509.10852）
> - **对应**：`references/04_记忆进化/Kim2025-PREMem.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/sangyeop-kim/PREMem

## 一句话总结

"把推理负担从生成时刻搬到存储时刻"：写入时即抽取**事实/经验/主观**三类细粒度片段并建立**显式跨会话关系**（建模关系本质+时序演化，非简单聚类），捕捉扩展/转化/蕴含演化模式——全规模模型显著提升，小模型可媲美大基线，token 预算敏感度低。

## 1. 动机：推理负担压在生成时刻

会话式 AI 长期记忆需跨会话综合，但现有系统把过多推理负担压在**回答生成时**，性能强依赖模型大小。已有工作用元数据标注/概念链接知识图谱处理多会话推理，但常把跨会话关系定义为**简单聚类**，未建模**关系本质与时序演化**。PREMem 把推理**前移到存储（pre-storage）**。

## 2. 技术路线（预存储推理）

```
跨会话对话历史
  ├─① 片段抽取：factual / experiential / subjective 三类细粒度记忆
  │    （理论支撑的分类，非随意切分）
  ├─② 跨会话链接：建立显式关系（非简单聚类）
  │    · 建模关系本质：扩展 extension / 转化 transformation / 蕴含 implication
  │    · 建模时序演化
  │    · 聚类 → 链接对（相似度阈值 θ=0.6）→ 链接对推理
  └─③ 入库（enriched memory repository）
       生成时：轻量检索 + 生成（推理负担小，小模型也能胜任）
```

**核心**：写入贵、读取廉——把跨会话综合推理做在写入时，生成时只做轻量召回；三类片段 + 链接对提供可解释的进化轨迹；显式建模关系本质与时序演化（超越简单聚类）。

## 3. 关键结果

| 方面 | 效果 |
|---|---|
| 模型规模 | 各规模模型均显著提升；小模型 ≈ 大模型基线 |
| Token 预算 | 预算受限下仍有效（推理负担已前移） |
| 跨会话推理 | 尤其在跨会话推理任务上表现强 |

## 4. 代码索引

- 官方：https://github.com/sangyeop-kim/PREMem（含代码与数据集）
- 本仓库语境：**"写入时预存储推理"是赛题创新点 A（首选）核心参照**；复现位 `paper_code/记忆进化/`。

## 5. 优点 / 局限（深化）

- **优点**：把"何时做推理"显式化——写入贵、读取廉，性价比高；三类记忆片段 + 链接对提供可解释进化轨迹；显式建模关系本质+时序演化（超越简单聚类）；天然支持跨会话演化综合。
- **局限**：链接对阈值（θ=0.6）与关系类型需调参；片段抽取依赖 LLM 质量；面向对话场景，复杂任务结构化（图谱/程序）记忆未覆盖。

## 6. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 预存储推理 | **赛题创新点 A 直系依据**：写入时即做跨会话综合，生成时轻量召回（`docs/04` 6 节） |
| 事实/经验/主观三分类 | 对应赛题事实记忆+经验记忆双库（再加"主观/偏好"可选） |
| 链接对（θ=0.6） | "合并去重+冲突消解"量化手段，可进消融实验 |
| 显式建模关系本质+时序 | 超越简单聚类，与 StructMem/ Zep 的结构化进化呼应 |
| 减轻生成负担 | 论证记忆系统对模型规模敏感度的价值（低成本部署） |

---
*进化三路线之一；与 `笔记_Liu2023-TiM.md`（操作演化）、`笔记_Liang2023-SCM.md`（控制器）对照。*

## 论文核心代码（paper_code 索引）

- 仓库：`paper_code/04_记忆进化/PREMem/`
- `src/premem/`：四脚本流水线——`run_extract_episodic_memory.py`（片段抽取）→ `run_reasoning.py`（链接对推理）→ `save_episodic_embedding.py`（编码入库）→ `save_reasoning.py`；`src/memory/{segmentor,compressor}.py`（切分/压缩）；`prompts/`（事实/经验/主观抽取 + 推理 prompt 全文）。

## 我们的实现（memsys）

- **思路**："写入即推理"落为 write() 的**前置查重**——新内容先与全库比相似度（链接对的 MVP 形态），超 θ 判"已有此知识"跳过；跨会话关系暂不做（单场次闭环优先）；
- **代码索引**：`memsys/evolution/memory_evolution.py::write()`。

## 代码详解（链接对 θ 查重的完整逻辑）

```python
# memory_evolution.py::write()（节选）—— PREMem"写入前先想清楚"的落地
new_vec = self.vindex.model.embed(content)   # 新内容编码
dup, best_sim = None, -1.0
for cid in store.candidates():               # 全库逐条比对（万级内够快；FAISS 后走索引）
    existing = store.get(cid)
    sim = cosine(new_vec, self.vindex.model.embed(existing.content))
    if sim > best_sim: best_sim, dup = sim, existing   # 追踪最像的一条
if dup is not None and best_sim > self.merge_theta:    # θ=0.80（PREMem 用 0.6）
    return None    # 判定重复 → 跳过写入（调用方统计进 report.skipped）
# 不重复才真正落库（op_history 记 write，可回放）
entry = new_entry(type_, content, importance=..., op_history=[MemoryOp.WRITE.value])
```
> θ 差异说明：MockEmbedding 哈希词袋相似度偏高，0.6 会误杀正常写入；接真 embedding 后回调 0.6 对齐论文。

## 代码实证（结合 paper_code/）

- 仓库：`paper_code/04_记忆进化/PREMem/`
- 看 `src/`（预存储推理实现）、`prompts/`（事实/经验/主观抽取 + 链接对推理 prompt）、`script/`、`output/`、`requirements.txt`。
- 赛题用法：**创新点 A 依据**——写入时跨会话综合 + 链接对 θ=0.6 可直接仿。