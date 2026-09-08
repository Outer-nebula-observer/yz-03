# ============================================================================
# MemSkill: src/operation_bank.py【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2602.02474
#   README 原话：skills 是 meta-memory——"记什么、怎么记、保什么、忘什么"
#   的**方法**而非记忆内容。本文件定义"操作"（一条技能）与"操作库"
#   （技能池 + 淘汰机制）。
#
# 【为什么精读】赛题③创新点 A（可学习记忆操作）的两个依据之一；
#   update_type 四值（insert/update/delete/noop）就是我们进化四操作的
#   直系映射；"操作带统计 + 末位淘汰"是我们 op_history 统计的目标形态。
#
# 【我们的实现对照】
#   Operation.update_type     → memsys MemoryOp（write/merge/forget/abstract）
#   meta_info 统计            → 我们的 EvolutionReport（计数版，无 reward）
#   add_operation 末位淘汰    → 我们暂无（技能集固定）——升级方向
# ============================================================================

import numpy as np
from typing import List, Dict, Optional
import copy
from prompts.operation_templates import get_initial_operations


class Operation:
    """单条记忆操作 = 一条可进化的"怎么记"技能。

    三要素：
      - instruction_template：技能本体（执行器的 prompt 模板，含占位符）
      - update_type：落到记忆库的动作类型 insert/update/delete/noop
      - meta_info：使用统计——进化的数据依据（不是拍脑袋改技能）
    """

    def __init__(self, name: str, description: str,
                 instruction_template: str, update_type: str,
                 meta_info: Optional[Dict] = None):
        self.name = name                  # 操作名（日志/检索用）
        self.description = description    # "什么时候该用它"——controller 选择的依据
        self.instruction_template = instruction_template  # 技能本体：{session_text}等占位符
        self.update_type = update_type    # insert / update / delete / noop ← 四操作！
        self.meta_info = meta_info or {
            "usage_count": 0,        # 被选次数（流行度）
            "avg_reward": 0.0,       # 平均回报——末位淘汰的依据
            "recent_rewards": [],    # 近 20 次回报（看趋势，防"躺功劳簿"）
            "recent_usage_ema": 0.0, # 使用率滑动平均（长期不被选→衰减→淘汰信号）
        }
        # 向后兼容：旧 checkpoint 可能没有 ema 字段
        if "recent_usage_ema" not in self.meta_info:
            self.meta_info["recent_usage_ema"] = 0.0
        self.embedding = None  # 描述的向量（由 OperationBank 统一编码）

    def get_description_text(self) -> str:
        """给 embedding 用的纯文本描述。"""
        return self.description

    def format_instruction(self, session_text: str, retrieved_memories: str) -> str:
        """把模板的占位符填上当前上下文，生成执行器的具体指令。

        {session_text}        → 当前要处理的交互片段
        {retrieved_memories}  → 已召回的相关记忆（技能可参考旧记忆做合并/更新）
        format 失败则原样返回（模板无占位符的静态技能）。
        """
        template = self.instruction_template
        if '{session_text}' in template or '{retrieved_memories}' in template:
            try:
                return template.format(session_text=session_text,
                                       retrieved_memories=retrieved_memories)
            except Exception:
                return template
        return template

    def update_stats(self, reward: float):
        """被选中并执行后更新统计（进化的原料）。

        avg_reward 用增量公式（Welford 变体）：new = old + (r-old)/n
        —— 不用存全部历史，O(1) 更新。
        recent_rewards 只留最近 20 次：近期表现 > 历史总平均
        （一个技能可能"曾经好用后来退化"——看趋势才能淘汰它）。
        """
        self.meta_info["usage_count"] += 1
        n = self.meta_info["usage_count"]
        old_avg = self.meta_info["avg_reward"]
        self.meta_info["avg_reward"] = old_avg + (reward - old_avg) / n

        self.meta_info["recent_rewards"].append(reward)
        if len(self.meta_info["recent_rewards"]) > 20:
            self.meta_info["recent_rewards"] = self.meta_info["recent_rewards"][-20:]

    def decay_ema(self, ema_alpha: float = 0.1):
        """**未被选中**时调用（每步对所有落选技能）。

        EMA = (1-alpha) * old_ema → 不被选就指数衰减向 0。
        【设计精髓】与 usage_count（只增不减）互补：
        usage_count 回答"总共用了多少次"，EMA 回答"最近还在用吗"——
        老技能躺功劳簿（count 高但 EMA 衰减）应让位给新技能。
        """
        old_ema = self.meta_info.get("recent_usage_ema", 0.0)
        self.meta_info["recent_usage_ema"] = (1.0 - ema_alpha) * old_ema

    def to_dict(self):
        """序列化（embedding 转 list 才能 JSON 化）——checkpoint 用。"""
        return {'name': self.name, 'description': self.description,
                'instruction_template': self.instruction_template,
                'update_type': self.update_type, 'meta_info': self.meta_info,
                'embedding': self.embedding.tolist() if self.embedding is not None else None}

    @classmethod
    def from_dict(cls, data):
        """反序列化（embedding 转回 np.array）。"""
        op = cls(name=data['name'], description=data['description'],
                 instruction_template=data['instruction_template'],
                 update_type=data['update_type'],
                 meta_info=data.get('meta_info', {}))
        if data.get('embedding') is not None:
            op.embedding = np.array(data['embedding'])
        return op


class OperationBank:
    """操作库：存所有技能 + 支持动态进化（designer 加新、末位淘汰旧的）。"""

    def __init__(self, encoder=None, max_ops: int = 20, skip_noop: bool = False):
        self.operations: Dict[str, Operation] = {}
        self.encoder = encoder     # 描述编码器（技能也是文本→向量，供 controller 打分）
        self.max_ops = max_ops     # 库容上限——技能池不能无限膨胀（上下文放不下）
        self.new_operation_names = set()  # designer 新加的技能名（PPO 探索奖励用）
        self.skip_noop = skip_noop
        self._initialize_with_seeds()     # 种子技能起步（人工先验）

    def _initialize_with_seeds(self):
        """用 prompts/operation_templates.py 的种子操作初始化。

        【对照我们】我们的"种子"= docs/04 的四操作（固定方法）；
        MemSkill 的种子是 prompt 模板（可被 designer 改写进化）——差在这一层。
        """
        initial_ops = get_initial_operations(include_noop=not self.skip_noop)
        for op_name, op_data in initial_ops.items():
            self.operations[op_name] = Operation(
                name=op_data['name'], description=op_data['description'],
                instruction_template=op_data['instruction_template'],
                update_type=op_data['update_type'],
                meta_info=op_data['meta_info'])
        if self.encoder is not None:
            self._recompute_embeddings()

    def _recompute_embeddings(self):
        """所有技能描述统一编码（加/删技能后必须重算——向量要和库同步）。"""
        texts = [op.get_description_text() for op in self.operations.values()]
        embeddings = self.encoder.encode(texts)
        for i, op_name in enumerate(self.operations.keys()):
            self.operations[op_name].embedding = embeddings[i]

    def get_new_action_indices(self, candidate_ops=None):
        """新技能在候选列表中的下标——PPO 的 new_op_mask 数据源：
        新技能无历史统计，不给探索奖励就永远不会被选中（冷启动问题）。"""
        candidate_ops = candidate_ops or self.get_candidate_operations()
        return [i for i, op in enumerate(candidate_ops)
                if op.name in self.new_operation_names]

    def get_candidate_operations(self) -> List[Operation]:
        """给 controller 的候选全集——**按名字排序保证确定性**。

        【工程细节，值得学】PPO 的 action_idx 必须跨调用稳定：
        designer 在 episode 间增删技能，若顺序抖动，存好的
        log_prob/action 对不上号——sorted() 是最便宜的确定性保证。
        """
        names = sorted(self.operations.keys())
        return [self.operations[name] for name in names]

    def add_operation(self, operation: Operation) -> bool:
        """加新技能；库满则**末位淘汰**（进化闭环的出口）。

        淘汰规则（两级兜底）：
          1) 在"用过至少一次"的技能里，淘汰 avg_reward 最低者
             （有数据按数据——回报差的先走）；
          2) 若全都没用过（早期阶段），淘汰 usage_count 最低者
             （没数据按使用频率——没人选的自然让位）。
        【对照我们】我们的技能集固定不淘汰；若做进化版，
        EvolutionReport 的 skipped/wrote 就是这里的 reward 数据源。
        """
        if operation.name in self.operations:      # 同名=更新而非新增
            self.operations[operation.name] = operation
            if self.encoder is not None:
                self._recompute_embeddings()
            return True

        if len(self.operations) >= self.max_ops:
            worst_op_name, worst_reward = None, float('inf')
            for name, op in self.operations.items():
                if op.meta_info.get('usage_count', 0) > 0:
                    avg_reward = op.meta_info.get('avg_reward', 0.0)
                    if avg_reward < worst_reward:
                        worst_reward, worst_op_name = avg_reward, name
            if worst_op_name is None:              # 全是新技能→按使用次数淘汰
                min_usage = float('inf')
                for name, op in self.operations.items():
                    if op.meta_info.get('usage_count', 0) < min_usage:
                        min_usage, worst_op_name = \
                            op.meta_info.get('usage_count', 0), name
            if worst_op_name is not None:
                del self.operations[worst_op_name]
        # ...（后续：真正插入 + 重算向量 + 记入 new_operation_names）

# ============================================================================
# 【给基础开发者的三条读懂线索】
# 1) "可进化"的完整含义 = 新技能能进（designer 加）+ 差技能能出
#    （末位淘汰）+ 有数据依据（usage/reward/EMA 三统计）；
# 2) EMA 与 usage_count 的分工：总量 vs 近期热度——缺一就会被
#    "历史功臣"占坑；
# 3) sorted() 保序不是洁癖，是 PPO action_idx 一致性的硬需求——
#    任何"动作空间可变"的学习系统都要过这一关。
# ============================================================================
