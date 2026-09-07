# 论文精读（深化版）：MIRIX — Multi-Agent Memory System for LLM-Based Agents

> - **作者 / 机构**：Yu Wang（UC San Diego）、Xi Chen（NYU Stern）（MIRIX AI）
> - **发表**：arXiv 2025（2507.07957）
> - **对应**：`references/03_记忆检索/Wang2025-MIRIX.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/Mirix-AI/MIRIX（`public_evaluation` 分支）；官网 https://mirix.io

## 一句话总结

模块化多智能体记忆系统：**六类结构化记忆**（Core/Episodic/Semantic/Procedural/Resource/Knowledge Vault）+ **多智能体框架动态协调更新与检索** + **超越文本支持多模态**——ScreenshotVQA 比 RAG 高 35% 准确率且存储降 99.9%，LOCOMO 85.4% 达 SOTA。

## 1. 六类记忆（分层分工）

| 记忆类 | 内容 |
|---|---|
| **Core** | 核心稳定信息（用户身份/偏好/关键事实） |
| **Episodic** | 情景/事件经历 |
| **Semantic** | 概念/知识关联 |
| **Procedural** | 程序/技能（怎么做） |
| **Resource** | 资源记忆（文件/外部资源引用） |
| **Knowledge Vault** | 知识库（综合知识存储） |

## 2. 技术路线

```
多模态输入（文本/截图/…）
  ├─① 分类存储：六类记忆，分层分工
  ├─② 多智能体协调：更新（写）与检索（读）由专用 agent 动态控制、协调
  ├─③ 检索：按查询类型路由到对应记忆类（embedding / BM25 / string 多策略）
  └─④ 供 LLM 决策/生成
```

**核心**：超越扁平单一记忆，六类覆盖个性化与抽象；多智能体把"写、读、路由"显式化协调；原生支持视觉/多模态。

## 3. 关键结果

| 基准 | MIRIX | 对比 |
|---|---|---|
| ScreenshotVQA（多模态，~2 万高分辨率截图/序列） | 高 35% 准确率、存储降 99.9% | RAG 基线（现有记忆系统无法应用） |
| LOCOMO（长对话） | 85.4%（SOTA） | 超过 mem0 等记忆增强基线 |

## 4. 代码索引

- 官方：https://github.com/Mirix-AI/MIRIX（public_evaluation 分支可复现指标）
- 相关生态（论文对比/引用）：mem0、Zep、LangMem、Memobase
- 本仓库语境：**"多类记忆+多智能体协调+多策略检索"集大成方案**；复现位 `paper_code/记忆检索/`。

## 5. 优点 / 局限（深化）

- **优点**：记忆分类体系完整（6 类覆盖声明/程序/资源/知识）；多智能体协调把"写、读、路由"显式化；原生多模态（对齐赛题②多模态命题）；SOTA 数据扎实。
- **局限**：六类记忆+多智能体工程复杂度高；多智能体协调依赖额外 LLM 调用（成本）；以商业产品视角设计，学术可复现性依赖官方评测分支；多模态部分与赛题③（纯文本长短期记忆）关联较弱。

## 6. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 记忆分类体系 | 赛题可借鉴分层：事实（Core/Knowledge Vault）、经验（Episodic/Semantic）、策略（Procedural） |
| 多策略检索路由 | 支撑赛题"混合检索+查询列表分路"（embedding/BM25/string 任选，`docs/04` 2.3 节） |
| 多智能体协调 | 对应赛题"记忆控制器"：何时写、何时读的显式调度（与 SCM 思路一致） |
| LOCOMO 基准 | 组会汇报评估小节：MIRIX 85.4% vs 其他基线 |
| 多模态 | 为赛题②（多模态记忆）预留接口 |

---
*检索路线全景：向量（ExpeL）、SQL（ChatDB）、图谱（Zep）、多策略多智能体（MIRIX，本笔记）。*