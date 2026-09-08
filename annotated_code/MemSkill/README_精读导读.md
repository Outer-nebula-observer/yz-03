# 源码精读注释 ②：MemSkill（`04_记忆进化/MemSkill/`）

> **论文**：arXiv 2602.02474；笔记：`references/04_记忆进化/笔记_MemSkill-Memory-Skills.md`。
> **为什么精读它**：赛题**创新点 A**（可学习记忆操作）的两个依据之一；其"元记忆"思想直接塑造了我们 `EvolutionReport` 的统计设计。

---

## 0. 三角色架构总览

```
controller.py（选技能） → executor.py（按技能生成记忆） → memory_bank.py（存）
        ↑                        ↓ 失败案例
        └──── designer.py（复盘难例 → 进化技能集 operation_bank.py）←──┘
```

---

## 1. `src/operation_bank.py::Operation` —— 技能即"带统计的操作模板"

```python
class Operation:
    """Single memory operation —— 一条'怎么记'的技能（元记忆）"""
    def __init__(self, name, description, instruction_template, update_type, meta_info=None):
        self.name = name                  # 操作名（检索/日志用）
        self.description = description    # 什么时候该用它——controller 选择时的"说明书"
        self.instruction_template = instruction_template  # 技能本体：执行器的 prompt 模板
        self.update_type = update_type    # insert / update / delete / noop —— 四操作落地！
        self.meta_info = meta_info or {
            "usage_count": 0,        # 被选过几次（流行度）
            "avg_reward": 0.0,       # 平均回报——designer 复盘后更新，是进化的信号源
            "recent_rewards": [],    # 近期回报序列（看趋势，淘汰退化技能）
            "recent_usage_ema": 0.0, # 使用率滑动平均（防止老技能躺功劳簿）
        }
```

**【论文对应】** README 原话："skills 是 **meta-memory**——关注**记什么、怎么记、保什么、忘什么**的方法，而非记忆内容本身"。`update_type` 四值 = 论文的 INSERT/UPDATE/DELETE/SKIP。

**【我们的实现】** `memsys/schema.py::MemoryEntry.op_history` 记录每条记忆经历的操作——就是为将来统计"哪种操作模板好用"埋的数据基础（docs/09 决策 2 的升级路径）。

---

## 2. `src/controller.py` —— PPO 训练的技能选择器（最重的部分）

```python
"""
Controller: Trainable agent that selects operations
Uses PPO with dynamic action space        ← 动作空间=技能库，技能随时增删！
- Dual-encoder: state_net + op_net with interaction layer
- Actor-Critic: policy head + value head
- On-policy + GAE + clipped surrogate    ← 标准 PPO 三件套
"""
class PPOBuffer:
    """存 episode 轨迹：states/actions/log_probs/values/rewards"""
    def push(self, state_emb, op_embs, action, log_prob, value, reward=0.0,
             new_op_mask=None):
        # new_op_mask：标记"哪些技能是 designer 新加的"——
        # 新技能无历史统计，训练时给探索奖励（exploration bonus），否则永远选不到
        ...
    def merge(self, other):   # 并行收集多条 episode 后合并——典型 on-policy 多进程结构
        ...

# 状态编码（双塔）：
#   state_net：编码"当前交互片段"（要处理的历史文本）
#   op_net：   编码"每个技能的 description+template"（技能也是文本！）
#   interaction layer：状态与每个技能嵌入交互 → 打分 → top-K 选择
```

**【论文对应】** §Method 的 controller：**动态动作空间**是本文相对 Mem-α 的关键差异——技能集会变（designer 加新技能），PPO 策略必须适应"动作数不固定"，所以用交互层打分而非固定输出头。

**【我们的实现】** 我们没有 controller 的学习版——`evolve_from_review()` 里"选什么操作"是规则定的（write 建议→查重→写）。**对照价值**：把我们的"规则路由"换成"训练的策略"就是创新点 A 的完整形态；`new_op_mask` 的"新技能探索奖励"是个精妙设计，值得抄进我们的进化实验。

---

## 3. `src/designer.py` —— 难例驱动的技能进化

```python
@dataclass
class DesignerCase:
    """一次失败案例的完整档案（designer 的分析原料）"""
    query_id: str; question: str; ground_truth: str
    evidence: Optional[str]        # 应该召回但没召回/召回错的证据
    category: Optional[int]        # 错误类别（LoCoMo 的题型分类）
    # + 记忆侧属性：当时用了哪些技能、生成了什么记忆、检索返回了什么

# 工作流（三个 prompt：designer_prompts.py）：
#   DESIGNER_ANALYSIS_PROMPT    → LLM 分析"这个 case 为什么错"
#   DESIGNER_REFLECTION_PROMPT  → 归因到技能："哪个模板的输出导致了错误"
#   DESIGNER_REFINEMENT_PROMPT  → 产出：改旧模板 / 提新技能 / 标记淘汰
# json_repair 库容错 LLM 输出的 JSON——工程细节，值得学
```

**【论文对应】** §Method 的 designer：**周期性**（不是每步）复盘 hard cases——论文强调"选错技能≠技能差，可能只是状态罕见"，所以只拿"反复失败"的案例做进化依据，避免过拟合噪声。

**【我们的实现】** 我们的 `EvolutionReport.skipped`（查重跳过清单）+ `op_history` 就是"难例档案"的雏形；升级路径：按 docs/09 决策 2 的接口分离——执行侧不动，加一个"复盘器"消费 report 生成操作模板改进。

---

## 4. `main.py` + `eval_*.sh` —— 实验入口与评测

```python
# main.py 顶部：多进程收集 episode（mp + ProcessPoolExecutor），
#   alfworld 轨迹按 token 切块（chunk_trajectories_by_tokens）——长轨迹分块进 PPO
# eval_*.sh：LoCoMo / LongMemEval / HotpotQA / ALFWorld 四套评测一键跑
#   —— 我们的消融脚本 eval/ablation.py 直接仿的这组 sh 的结构
```

**【我们的实现】** `eval/ablation.py` 的 G0–G5 结构 = MemSkill 多 benchmark 评测的赛题化改造；`rag_utils.py::get_embeddings` 与我们 `embeddings.py` 同构（它用 sentence-transformers，我们留了 OpenAI 兼容位）。

---

## 5. 可直接搬走的三件事

1. **操作带统计元数据**（usage_count/avg_reward/EMA）——进化不是拍脑袋，是数据驱动；
2. **new_op_mask 探索奖励**——任何"可扩充动作空间"的学习系统都需要；
3. **json_repair 容错**——LLM 输出 JSON 的必备工具（我们 `OpenAICompatibleClient.extract_memory_ops` 的正则截取是丐版，可换此库）。
