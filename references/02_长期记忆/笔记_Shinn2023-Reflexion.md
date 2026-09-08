# 论文精读（深化版）：Reflexion — Language Agents with Verbal Reinforcement Learning

> - **作者 / 机构**：Noah Shinn、Edward Berman、Karthik Narasimhan、Shunyu Yao 等（Northeastern / Princeton / MIT）
> - **发表**：NeurIPS 2023（arXiv 2303.11366）
> - **对应**：`references/02_长期记忆/Shinn2023-Reflexion.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/noahshinn/reflexion（作者 GitHub 由 noahshinn024 改名为 noahshinn）

## 一句话总结

"口头强化学习"：不更新权重，而用 **Actor → Evaluator → Self-Reflection** 三角把失败原因写成语言反思存入**情景记忆缓冲**，下一轮先读反思再行动——HumanEval pass@1 达 91%，超当时 GPT-4 的 80%。

## 1. 核心思想：Verbal RL

传统 RL 对语言 agent 太贵（大量样本 + 微调）。Reflexion 用**语言反馈取代梯度**：把"失败教训"自然语言化、存进记忆、下轮注入——以语言为"权重"的强化学习。

## 2. 技术路线（三角架构）

```
for trial in attempts:
  ① Actor（LLM agent）：根据 任务 + 上一轮反思 生成动作/代码
  ② Evaluator：给反馈信号（标量分数 / 测试用例 / 语言评判；外部或内部模拟）
  ③ Self-Reflection（LLM）：把"为何失败、下次怎么做"写成反思文本
  ④ 反思写入 episodic memory 缓冲（按任务存，下轮注入 prompt）
```

**三角色分工**：Actor 执行；Evaluator 评判（可融合多源反馈）；Self-Reflection 把反馈抽象为可复用语言经验。

## 3. 与同类方法对比（论文表）

| 方法 | Self-refine | Hidden constraints | Decision making | Binary reward | Memory |
|---|---|---|---|---|---|
| Self-refine | ✓ | ✗ | ✗ | ✗ | ✗ |
| Beam search | ✓ | ✓ | ✓ | ✓ | ✗ |
| **Reflexion** | ✓ | ✓ | ✓ | ✓ | **✓** |

> Reflexion 区别点：**有记忆**（情景记忆缓冲），能跨 trial 累积教训；能处理隐藏约束、决策任务、二元奖励。

## 4. 关键结果

| 环境 | 结果 |
|---|---|
| HumanEval（代码） | pass@1 **91%**（超当时 GPT-4 80%） |
| AlfWorld（序列决策） | 显著超 ReAct 等基线 |
| HotpotQA / 常识推理 | 推理任务提升 |
| 消融 | 自由形式反馈与自生成反思均有效；反思质量↑→提升↑ |

## 5. 代码索引

- 官方：https://github.com/noahshinn/reflexion（HumanEval/ALFWorld/问答全套实验）
- 本仓库语境：**经验记忆（经验→教训文本）代表作**；复现位 `paper_code/长期记忆/`。

## 6. 优点 / 局限（深化）

- **优点**：免微调即可"学习"；反思可读、可审计、可跨任务迁移；思想朴素、实现简单、效果强；三角架构职责清晰。
- **局限**：反思质量依赖 LLM 本身（"反思却不改行为"=空转）；记忆只是"全塞进上下文"的简单缓冲，无检索/优先级/遗忘管理；单轮反思粒度粗，跨长程任务需扩展；无结构化抽象。

## 7. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 语言形式经验 | 经验记忆层：推演失败后沉淀"作战教训"文本（`docs/04` 2.2 节） |
| 反思→行为改变 | "经验要能改变规划输出"的验证：比较加入反思前后规划是否变化（`docs/04` 避坑点 5） |
| 简单缓冲 vs 检索式经验库 | 消融 G3 对照：Reflexion 全塞 vs ExpeL 检索召回 |
| 三角架构 | 启示作战复盘流水线：执行→评估（AFSIM 推演）→反思沉淀 |

---
*经验记忆三件套：Reflexion（语言反思，本笔记）、Voyager（可执行技能库）、Memp（程序性记忆）。*