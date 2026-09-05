# 论文精读：Reflexion — Language Agents with Verbal Reinforcement Learning

> - **作者 / 机构**：Noah Shinn、Edward Berman、Karthik Narasimhan 等（Northeastern / Princeton / MIT）
> - **发表**：NeurIPS 2023（arXiv 2303.11366）
> - **对应模块**：`references/02_长期记忆/Shinn2023-Reflexion.pdf`
> - **全文提取**：`references/02_长期记忆/Shinn2023-Reflexion.md`
> - **官方代码**：https://github.com/noahshinn024/reflexion

## 一句话总结

**"口头强化学习"：不更新权重，而是让 agent 在任务失败后把失败原因写成语言反思（self-reflection），存入情景记忆缓存，下一轮尝试前先读反思再行动——HumanEval 上 pass@1 达 91%，超过当时 GPT-4 的 80%。**

## 摘要（归纳）

语言 agent 与外部环境（游戏/编译器/API）交互时，传统 RL 需要大量样本与昂贵的微调。Reflexion 提出全新范式：**用语言反馈取代梯度更新**。
- agent 对任务反馈信号（标量分数或自由文本，外部给定或内部模拟）进行**语言层面的反思**；
- 把反思文本保存到**情景记忆缓冲（episodic memory buffer）**；
- 下一轮 trial 中把高质量反思注入 prompt，诱导更优决策。
该框架可兼容多种反馈类型与来源，覆盖**序列决策、代码生成、语言推理**三类任务，均显著超过基线；并对反馈信号类型、反馈融合方式、agent 类型做了系统消融。

## 技术路线

```
for trial in attempts:
    ① Actor（LLM agent）根据 任务描述 + 上一轮反思 生成动作/回答
    ② Evaluator 给出反馈（分数 / 测试用例 / 语言评判）
    ③ Self-Reflection（LLM）把"为什么失败、下次怎么做"写成反思文本
    ④ 反思写入 episodic memory 缓存（按任务存储，加入下一轮上下文）
```

## 关键结果

| 环境 | 效果 |
|---|---|
| HumanEval（代码） | pass@1 **91%**（超当时 GPT-4 的 80%） |
| AlfWorld（序列决策） | 成功率大幅超过 ReAct 等基线 |
| HotpotQA / 常识问答（语言推理） | 推理任务显著提升 |
| 消融 | 免费形式反馈与"自生成反思"均有效；反思质量越高提升越大 |

## 代码索引

- 官方仓库：https://github.com/noahshinn024/reflexion（含 HumanEval/ALFWorld/问答等全部实验代码与数据）
- 本仓库语境：**经验记忆（经验→教训文本）的代表作**；复现位 `paper_code/长期记忆/`。

## 优点 / 局限

- **优点**：无需权重更新即可"学习"；反思是可读、可审计、可跨任务迁移的语言知识；思想朴素、实现简单、效果强。
- **局限**：反思质量依赖 LLM 本身（会反思却不改行为=空转）；记忆只是"全部塞进上下文"的简单缓冲，无检索/优先级/遗忘管理；单轮反思粒度粗，跨长程任务需扩展。

## 与赛题③的联系

| 借鉴点 | 说明 |
|---|---|
| 语言形式经验 | 直接支撑"经验记忆"层：推演失败后沉淀"作战教训"文本（`docs/04` 2.2 节） |
| 反思→行为改变 | "经验要能改变规划输出"的验证思路：比较加入反思前后规划是否变化（`docs/04` 避坑点 5） |
| 记忆缓冲 | 可对比其简单缓冲 vs 赛题的检索式经验库，作为消融 G3 的依据 |

---
*经验记忆三件套：Reflexion（语言反思）、Voyager（可执行技能库）、Memp（程序性记忆，见 `笔记_Fang2025-Memp.md`）。*