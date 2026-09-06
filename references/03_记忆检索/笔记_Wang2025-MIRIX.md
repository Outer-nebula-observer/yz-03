# 论文精读：MIRIX — Multi-Agent Memory System for LLM-Based Agents

> - **作者 / 机构**：Yu Wang（UC San Diego）、Xi Chen（NYU Stern）（MIRIX AI）
> - **发表**：arXiv 2025（2507.07957）
> - **对应模块**：`references/03_记忆检索/Wang2025-MIRIX.pdf`
> - **全文提取**：`references/03_记忆检索/Wang2025-MIRIX.md`
> - **官方代码**：https://github.com/Mirix-AI/MIRIX（`public_evaluation` 分支含评测）；官网 https://mirix.io

## 一句话总结

**模块化多智能体记忆系统：把记忆分成 6 类（Core / Episodic / Semantic / Procedural / Resource / Knowledge Vault），由多智能体框架动态协调"更新与检索"，文本之外还支持多模态（屏幕截图）——多模态 ScreenshotVQA 上比 RAG 高 35% 准确率且存储降 99.9%，LOCOMO 上 85.4% 达 SOTA。**

## 摘要（归纳）

现有记忆方案多为"扁平、窄范围"的单一组件，难以做个性化、抽象与可靠召回。MIRIX 提出**模块化多智能体记忆系统**：
- **六类结构化记忆**：核心记忆（Core）、情景记忆（Episodic）、语义记忆（Semantic）、程序性记忆（Procedural）、资源记忆（Resource Memory）、知识库（Knowledge Vault）——分层分工，覆盖个性化与抽象；
- **多智能体框架**：动态**控制与协调记忆的更新与检索**（不同 agent 分管不同类型记忆操作）；
- **超越文本**：支持**视觉/多模态记忆**（屏幕截图等真实场景）。
验证场景一：**ScreenshotVQA**（含近 2 万张高分辨率电脑截图/序列的多模态基准）——比 RAG 基线高 **35%** 准确率、存储需求降 **99.9%**；场景二：**LOCOMO**（长文档对话基准）——**85.4%**，超过现有基线（含 mem0 等，论文第 5 章对比）。

## 技术路线

```
多模态输入（文本/截图/…）
  ├─① 分类存储：六类记忆
  │    Core / Episodic / Semantic / Procedural / Resource / Knowledge Vault
  ├─② 多智能体协调：更新（写）与检索（读）由专用 agent 动态控制、协调
  ├─③ 检索：按查询类型路由到对应记忆类（embeddings / BM25 / string 等多策略）
  └─④ 供 LLM 决策 / 生成
```

## 关键结果

| 基准 | MIRIX | 对比 |
|---|---|---|
| ScreenshotVQA（多模态） | 高 35% 准确率、存储降 99.9% | RAG 基线（现有记忆系统无法应用） |
| LOCOMO（长对话） | 85.4%（SOTA） | 超过 mem0 等记忆增强基线 |

## 代码索引

- 官方仓库：https://github.com/Mirix-AI/MIRIX （public_evaluation 分支可复现指标）
- 相关生态（论文对比/引用）：mem0、Zep、LangMem、Memobase 等
- 本仓库语境：**"多类记忆 + 多智能体协调 + 多策略检索"的集大成方案**，赛题短期/长期/检索分层设计的参照；复现位 `paper_code/记忆检索/`。

## 优点 / 局限

- **优点**：记忆分类体系完整（6 类，覆盖声明/程序/资源/知识）；多智能体协调把"写、读、路由"显式化；原生支持多模态（对齐赛题②多模态命题）；SOTA 数据扎实。
- **局限**：六类记忆 + 多智能体的工程复杂度高；多智能体协调依赖额外 LLM 调用（成本）；以商业产品视角设计，学术可复现性依赖官方评测分支；多模态部分与赛题③（纯文本长短期记忆）关联较弱。

## 与赛题③的联系

| 借鉴点 | 说明 |
|---|---|
| 记忆分类体系 | 赛题可借鉴其分层：事实（Core/Knowledge Vault）、经验（Episodic/Semantic）、策略（Procedural） |
| 多策略检索路由 | 支撑赛题"混合检索 + 查询列表分路"（embedding/BM25/string 任选，`docs/04` 2.3 节） |
| 多智能体协调 | 对应赛题"记忆控制器"：何时写、何时读的显式调度（与 SCM 思路一致） |
| LOCOMO 基准 | 组会汇报评估小节可用：MIRIX 85.4% vs 其他基线 |

---
*检索路线全景：向量（ExpeL）、SQL（ChatDB）、图谱（Zep）、多策略多智能体（MIRIX，本笔记）。*