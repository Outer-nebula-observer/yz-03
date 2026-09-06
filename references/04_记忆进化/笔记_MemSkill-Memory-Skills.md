# 论文精读：MemSkill — Learning and Evolving Memory Skills for Self-Evolving Agents

> - **作者 / 机构**：Haozhen Zhang、Quanyu Long、Wenya Wang（南洋理工大学）等
> - **发表**：arXiv 2025（按标题检索；ACL 2026 投稿，Preprint）
> - **对应模块**：`references/04_记忆进化/MemSkill-Memory-Skills.pdf`
> - **全文提取**：`references/04_记忆进化/MemSkill-Memory-Skills.md`
> - **官方代码**：https://github.com/ViktorAxelsen/MemSkill

## 一句话总结

**把"记忆操作"从固定手工流程升级为"可学习、可进化的记忆技能"：控制器学会选一组相关技能、LLM 执行器按技能生成记忆、设计师定期复盘难例并提出改进/新技能——形成"技能选择策略 + 技能集本身"双闭环进化，在 LoCoMo / LongMemEval / HotpotQA / ALFWorld 上全面超过强基线。**

## 摘要（归纳）

大多数 LLM agent 记忆系统依赖**少量静态手工设计的操作**（抽取/修订），把"存什么、怎么改"的人类先验硬编码，面对多样交互模式僵硬、长历史低效。MemSkill 将记忆操作**重构为可学习、可进化的记忆技能**（结构化的可复用例程，用于从交互轨迹中抽取、整合、修剪信息）：
1. **控制器（Controller）**：学习**选择一小组合适的技能**（技能选择策略）；
2. **执行器（Executor）**：基于所选技能、由 LLM 生成技能引导的记忆；
3. **设计师（Designer）**：周期性**复盘难例**（所选技能产出错误/不完整记忆），**提出技能改进与新技能**，进化技能集。
三者构成**闭环**：既优化"选技能"的策略，也优化"技能集"本身。LoCoMo / LongMemEval / HotpotQA / ALFWorld 上优于强基线且跨设定泛化良好；分析揭示了技能如何演化，指向更自适应、自进化的记忆管理。

## 技术路线

```
交互轨迹
  ├─① 控制器：学习选择相关技能子集（skill selection policy）
  ├─② 执行器（LLM）：按所选技能 → 生成/整合/修剪记忆
  ├─③ 设计师：周期性复盘难例 → 改进旧技能 / 提出新技能
  └─ 闭环：策略与技能集共同进化
```

## 关键结果

| 基准 | 效果 |
|---|---|
| LoCoMo / LongMemEval | 长对话记忆任务优于强基线 |
| HotpotQA | 知识与多跳问答任务提升 |
| ALFWorld | 具身决策任务提升、跨设定泛化 |

## 代码索引

- 官方仓库：https://github.com/ViktorAxelsen/MemSkill
- 本仓库语境：**"可学习记忆操作（INSERT/UPDATE/DELETE/SKIP）"落地实现**，赛题创新点 A 的进阶参照；复现位 `paper_code/记忆进化/`。

## 优点 / 局限

- **优点**：记忆操作从"固定规则"变为"可进化技能集"——对应认知层面"学会怎么记"；控制器/执行器/设计师三段职责清晰、可解释；多基准验证（对话/问答/具身）泛化性好。
- **局限**：设计师定期复盘依赖额外 LLM 调用（成本）；技能集演化质量依赖难例筛选；仍是文本记忆为主，多模态/程序性记忆未覆盖。

## 与赛题③的联系

| 借鉴点 | 说明 |
|---|---|
| 可学习记忆操作 | **赛题创新点 A 的最直接文献支撑**：INSERT/UPDATE/DELETE/SKIP 做成可进化技能（`docs/04` 6 节 A 首选） |
| 控制器→选操作 | 对应赛题进化模块"何时写/合并/遗忘/抽象"的决策器 |
| 设计师→复盘进化 | 作战复盘驱动记忆操作改进的闭环设想 |
| LoCoMo/LongMemEval 评测 | 记忆进化效果的标准评测口径（`docs/04` 5.2 节） |

---
*进化三路线补全：TiM（操作集）→ SCM/PREMem（控制器/预存储）→ Mem-α/MemSkill（可学习操作）。*