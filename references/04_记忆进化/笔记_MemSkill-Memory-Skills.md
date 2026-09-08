# 论文精读（深化版）：MemSkill — Learning and Evolving Memory Skills for Self-Evolving Agents

> - **作者 / 机构**：Haozhen Zhang、Quanyu Long、Wenya Wang（南洋理工大学）等
> - **发表**：arXiv 2025（按标题检索；Preprint）
> - **对应**：`references/04_记忆进化/MemSkill-Memory-Skills.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/ViktorAxelsen/MemSkill

## 一句话总结

把"记忆操作"从固定手工流程升级为"可学习、可进化的记忆技能"：**控制器**学选一组相关技能、**LLM 执行器**按技能生成记忆、**设计师**定期复盘难例进化技能集——形成"技能选择策略 + 技能集本身"双闭环进化，LoCoMo/LongMemEval/HotpotQA/ALFWorld 全面超基线。

## 1. 动机：手工操作僵硬

大多数 LLM agent 记忆系统依赖**少量静态手工设计操作**（抽取/修订），把"存什么、怎么改"的人类先验硬编码，面对多样交互模式僵硬、长历史低效。MemSkill 把记忆操作**重构为可学习、可进化的记忆技能**（structured behaviors specifying when & how to extract/consolidate/prune）。

## 2. 技术路线（三角色闭环）

```
交互轨迹
  ├─① 控制器（Controller）：学习选择一小组合适技能（skill-selection policy）
  ├─② 执行器（Executor，LLM）：按所选技能 → 生成/整合/修剪记忆
  ├─③ 设计师（Designer）：周期性复盘难例（所选技能产出错误/不完整记忆）
  │    → 提出技能改进 + 新技能，进化技能集
  └─ 闭环：既优化"选技能"策略，也优化"技能集"本身
```

**核心**：记忆操作 = 可学习可进化技能（INSERT/UPDATE/DELETE/SKIP 等结构化行为）；三角色分工清晰可解释；双闭环——选择策略 + 技能集共同进化。

## 3. 关键结果

| 基准 | 效果 |
|---|---|
| LoCoMo / LongMemEval | 长对话记忆任务优于强基线 |
| HotpotQA | 知识与多跳问答任务提升 |
| ALFWorld | 具身决策任务提升、跨设定泛化 |
| 技能演化分析 | 揭示技能如何进化，指向自适应自进化记忆管理 |

## 4. 代码索引

- 官方：https://github.com/ViktorAxelsen/MemSkill
- 本仓库语境：**"可学习记忆操作（INSERT/UPDATE/DELETE/SKIP）"落地实现**，赛题创新点 A 进阶参照；复现位 `paper_code/记忆进化/`。

## 5. 优点 / 局限（深化）

- **优点**：记忆操作从"固定规则"变为"可进化技能集"——对应认知"学会怎么记"；控制器/执行器/设计师三段职责清晰可解释；多基准验证（对话/问答/具身）泛化性好；技能演化可分析。
- **局限**：设计师定期复盘依赖额外 LLM 调用（成本）；技能集演化质量依赖难例筛选；仍是文本记忆为主，多模态/程序性记忆未覆盖。

## 6. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 可学习记忆操作 | **赛题创新点 A 最直接文献支撑**：INSERT/UPDATE/DELETE/SKIP 做成可进化技能（`docs/04` 6 节 A 首选） |
| 控制器→选操作 | 对应赛题进化模块"何时写/合并/遗忘/抽象"决策器 |
| 设计师→复盘进化 | 作战复盘驱动记忆操作改进的闭环设想 |
| LoCoMo/LongMemEval 评测 | 记忆进化效果标准评测口径（`docs/04` 5.2 节） |
| 双闭环（策略+技能集） | 启示赛题"操作策略+操作集合"两层都可消融量化 |

---
*进化三路线补全：TiM（操作集）→ SCM/PREMem（控制器/预存储）→ Mem-α/MemSkill（可学习操作）。*

## 论文核心代码（paper_code 索引 · 带注释）

- 仓库：`paper_code/04_记忆进化/MemSkill/`

```python
# src/operation_bank.py::Operation（论文核心：可进化记忆操作，加注释讲解）
class Operation:
    """Single memory operation —— 一条'怎么记'的技能（元记忆）"""
    def __init__(self, name, description, instruction_template, update_type, meta_info=None):
        self.name = name                  # 操作名（如 insert_factual）
        self.description = description    # 什么时候该用它（控制器据此选择）
        self.instruction_template = instruction_template  # 执行器 prompt 模板（技能本体）
        self.update_type = update_type    # insert / update / delete / noop —— 四操作！
        self.meta_info = meta_info or {
            "usage_count": 0,        # 被用过几次（流行度）
            "avg_reward": 0.0,       # 平均回报（设计师复盘难例后更新——进化信号）
            "recent_rewards": [],    # 近期回报序列（淘汰退化技能的依据）
            "recent_usage_ema": 0.0, # 使用率滑动平均（热度衰减）
        }
```
> 精髓：**操作本身带使用统计与回报**——设计师复盘"这技能最近干得怎么样"，据此改模板/生新技能/淘汰差技能，操作集自我进化（区别于 Mem-α 的 RL 训练路线）。

## 我们的实现（memsys）

- **思路**：MVP 的四操作是**固定方法**（write/merge/forget/abstract），未做成可进化技能；但 `op_history` 字段已记录每条记忆经历的操作——为"操作效果统计"留了数据基础；
- **代码索引**：`memsys/evolution/memory_evolution.py`（四操作方法）+ `memsys/schema.py::MemoryEntry.op_history`。

## 代码详解（操作统计的数据基础已埋好）

```python
# schema.py（节选）—— 每条记忆自带操作履历
op_history: List[str] = field(default_factory=list)  # 如 ["write", "merge", "abstract"]

# evolution.py::abstract()（节选）—— 抽象产物 importance+0.5 且记来源
abstract_entry = new_entry(MemoryType.EXPERIENCE, abstract_text,
                           importance=max(...) + 0.5,          # 抽象经验更值钱
                           merged_from=[e.id for e in entries], # 来源可回放
                           op_history=[MemoryOp.ABSTRACT.value])
```
> 升级路径（对齐 MemSkill）：统计 `op_history` 频次与该操作产物的召回率 → 周期复盘"哪些操作模板好用"→ 进化 prompt 模板——`EvolutionReport` 就是现成的统计输入。

## 代码实证（结合 paper_code/）

- 仓库：`paper_code/04_记忆进化/MemSkill/`
- ⭐ `main.py`：入口；依赖 `src/trainer`、`src/memory_bank`、`src/executor`、`src/data_processing/alfworld`。
- `rag_utils.py`（embedding）、`eval_utils.py`（llm_judge）、`prompts/prompt_pool.py`（技能池 prompt）。
- 评测脚本：`eval_locomo.sh`、`eval_longmemeval.sh`、`eval_hp.sh`、`eval_alfworld.sh`——**LoCoMo/LongMemEval 评测可复用**。
- 赛题用法：**创新点 A 依据**——可学习记忆操作 + 评测口径。