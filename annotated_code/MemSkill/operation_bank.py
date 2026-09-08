# ============================================================================
# MemSkill: src/operation_bank.py —— 可进化记忆操作库【赛题③逐行注释版】
# ============================================================================
# 【论文定位】arXiv 2602.02474 §Method：
#   MemSkill 把"记忆操作"从固定规则重构为【可学习、可进化】的技能（skill）。
#   本文件 = 技能库本体：每个技能 = 一段带统计元数据的 prompt 模板。
#
# 【为什么精读】赛题③创新点 A（可学习记忆操作）的两个依据之一（另一个 PREMem）。
#   README 原话："skills 是 meta-memory——关注【记什么、怎么记、保什么、忘什么】
#   的方法，而非记忆内容本身。"
#
# 【我们的实现对照】
#   Operation（技能=模板+统计）   → memsys/schema.py::MemoryEntry.op_history
#                                  （我们记"记忆经历了什么操作"，为操作统计埋数据）
#   OperationBank（淘汰最差技能） → 我们的 EvolutionReport（消融 G4 的统计输入）
#   update_type 四值              → memsys/evolution 四方法 write/merge/forget/abstract
# 完整原文件：paper_code/04_记忆进化/MemSkill/src/operation_bank.py（本地 clone）
# ============================================================================

"""
Operation Bank: Stores and evolves memory operations
"""
import numpy as np
from typing import List, Dict, Optional
import copy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts.operation_templates import get_initial_operations


class Operation:
    """Single memory operation —— 一条"怎么记"的技能（元记忆单元）

    【设计精髓】一个技能由三部分组成：
      ① 静态定义（name/description/template）——人写或 Designer 进化产出
      ② 执行语义（update_type）——落到记忆库的动作类型
      ③ 动态统计（meta_info）——进化的依据：用得怎么样，决定去留
    """
    def __init__(self, name: str, description: str,
                 instruction_template: str, update_type: str,
                 meta_info: Optional[Dict] = None):
        self.name = name                  # 技能名（日志/去重键）
        self.description = description    # "什么时候用我"——controller 选择时的说明书，
                                          # 也是被 encoder 编码成向量的文本（见 get_description_text）
        self.instruction_template = instruction_template  # 技能本体：执行器 executor 的 prompt 模板，
                                                          # 占位符 {session_text}/{retrieved_memories}
        # 四操作落地：insert（写新）/ update（改旧）/ delete（删）/ noop（跳过）
        # 【我们的对照】memsys/evolution 的 write/merge/forget + 我们的 abstract（四操作）
        self.update_type = update_type  # insert, update, delete, noop
        # ---- 动态统计：进化的数据基础（没有这些就只是静态模板） ----
        self.meta_info = meta_info or {
            "usage_count": 0,        # 被选中次数（流行度）
            "avg_reward": 0.0,       # 平均回报——Designer 复盘难例后更新的核心信号
            "recent_rewards": [],    # 近 20 次回报（看趋势：技能可能退化）
            "recent_usage_ema": 0.0, # 使用率滑动平均（防老技能"躺功劳簿"）
            "created_at": "unknown",
            "last_modified": "unknown"
        }
        # 向后兼容：旧存档可能没有 EMA 字段（ evolutionary 过程中的 schema 演进处理）
        if "recent_usage_ema" not in self.meta_info:
            self.meta_info["recent_usage_ema"] = 0.0
        self.embedding = None  # description 的向量——由 OperationBank 统一编码
                               # （controller 的 op_net 消费它做"状态×技能"交互打分）

    def get_description_text(self) -> str:
        """供编码的纯文本（去掉指导字符等噪声）——embedding 只看 description"""
        return self.description

    def format_instruction(self, session_text: str, retrieved_memories: str) -> str:
        """把当前上下文填进模板占位符 → executor 可直接执行的完整 prompt
        【我们的对照】我们 evolution 的 prompt 是代码里拼的；
        MemSkill 把 prompt 变成"数据"（模板可被 Designer 进化修改）——
        这正是"可进化操作"与"硬编码操作"的本质区别。"""
        template = self.instruction_template
        if '{session_text}' in template or '{retrieved_memories}' in template:
            try:
                return template.format(
                    session_text=session_text,          # 当前交互片段
                    retrieved_memories=retrieved_memories  # 已召回的相关记忆
                )
            except Exception:
                return template   # 占位符不匹配时兜底返回原文（防崩）
        return template

    def update_stats(self, reward: float):
        """被选中并执行后更新统计——增量均值，O(1) 不存全历史
        【值得学】均值用 online update：new = old + (x - old)/n，
        避免存全部 reward 再算平均（内存友好且可流式）。"""
        self.meta_info["usage_count"] += 1
        n = self.meta_info["usage_count"]
        old_avg = self.meta_info["avg_reward"]
        new_avg = old_avg + (reward - old_avg) / n     # 增量均值
        self.meta_info["avg_reward"] = new_avg
        self.meta_info["recent_rewards"].append(reward)
        if len(self.meta_info["recent_rewards"]) > 20:  # 滑窗 20——只看近期表现
            self.meta_info["recent_rewards"] = self.meta_info["recent_rewards"][-20:]

    def decay_ema(self, ema_alpha: float = 0.1):
        """未被选中时衰减 EMA（每步对所有落选技能调用）
        EMA = (1-α)·old —— 衰减向 0：久不用的技能热度下降，
        防止"早期立功、后期躺平"的技能永远占位。"""
        old_ema = self.meta_info.get("recent_usage_ema", 0.0)
        self.meta_info["recent_usage_ema"] = (1.0 - ema_alpha) * old_ema

    def to_dict(self):
        """序列化（embedding 转 list 才能 JSON 化）——技能库落盘/迁移"""
        return {
            'name': self.name, 'description': self.description,
            'instruction_template': self.instruction_template,
            'update_type': self.update_type, 'meta_info': self.meta_info,
            'embedding': self.embedding.tolist() if self.embedding is not None else None
        }

    @classmethod
    def from_dict(cls, data):
        """反序列化（embedding list → np.array）——技能库加载"""
        op = cls(name=data['name'], description=data['description'],
                 instruction_template=data['instruction_template'],
                 update_type=data['update_type'],
                 meta_info=data.get('meta_info', {}))
        if data.get('embedding') is not None:
            op.embedding = np.array(data['embedding'])
        return op


class OperationBank:
    """技能库：存储全部 Operation 并支撑动态进化（增/删/替换/探索偏置）

    【我们的对照】我们没有这个库（四操作是固定方法）——这是创新点 A 的
    完整形态差距：操作从"代码"变成"数据"后才能被进化（Designer 改模板、
    淘汰最差、探索新技能）。
    """
    def __init__(self, encoder=None, max_ops: int = 20,
                 skip_noop: bool = False):
        self.operations: Dict[str, Operation] = {}
        self.encoder = encoder   # 文本编码器（给 description 编码，供 PPO op_net 用）
        self.max_ops = max_ops   # 库容上限（20）——防技能无限膨胀，超了淘汰最差
        self.new_operation_names = set()  # Designer 新加的技能名——享受探索偏置
        self.skip_noop = skip_noop
        self._initialize_with_seeds()

    def _initialize_with_seeds(self):
        """种子技能初始化（prompts/operation_templates.py 里人工定义）——
        【进化不是从零开始】先有好的种子，Designer 再在其上进化。
        【我们的对照】我们的"种子"= 四个固定方法；MemSkill 的种子=可改的模板。"""
        initial_ops = get_initial_operations(include_noop=not self.skip_noop)
        for op_name, op_data in initial_ops.items():
            operation = Operation(
                name=op_data['name'],
                description=op_data['description'],
                instruction_template=op_data['instruction_template'],
                update_type=op_data['update_type'],
                meta_info=op_data['meta_info'])
            self.operations[op_name] = operation
        if self.encoder is not None:
            self._recompute_embeddings()

    def _recompute_embeddings(self):
        """全库重新编码——注意：Designer 每次改模板都要重算（描述变了向量就变）"""
        if self.encoder is None:
            return
        texts = [op.get_description_text() for op in self.operations.values()]
        if len(texts) == 0:
            return
        embeddings = self.encoder.encode(texts)
        for i, op_name in enumerate(self.operations.keys()):
            self.operations[op_name].embedding = embeddings[i]

    def set_new_operation_names(self, names: List[str]):
        """登记新技能名单——训练时对这些动作加探索奖励，
        否则新技能无历史统计，PPO 永远选不到它（冷启动死锁）。
        【值得学】任何"可扩充动作空间"的学习系统都需要这个机制。"""
        self.new_operation_names = set(names)

    def get_new_action_indices(self, candidate_ops=None) -> List[int]:
        """新技能在候选列表中的下标——controller 据此加 exploration bonus"""
        if candidate_ops is None:
            candidate_ops = self.get_candidate_operations()
        return [i for i, op in enumerate(candidate_ops)
                if op.name in self.new_operation_names]

    def get_candidate_operations(self) -> List[Operation]:
        """按名字排序返回全部技能——排序是为了【下标稳定】：
        PPO 的 action_idx 必须跨调用一致，Designer 中途增删技能时
        不排序会导致动作索引错位（注释里明确写了这个坑）。
        【值得学】动态动作空间 + 索引一致性 = 必须规范排序。"""
        names = sorted(self.operations.keys())
        return [self.operations[name] for name in names]

    def add_operation(self, operation: Operation) -> bool:
        """新增技能；库满时替换"表现最差"的——进化的淘汰机制
        规则（两段兜底）：
          ① 在"用过至少一次"的技能里找 avg_reward 最低的替换
          ② 若全都没用过 → 找 usage_count 最低的（最少被选的让位）"""
        if operation.name in self.operations:   # 同名 = 更新而非新增
            self.operations[operation.name] = operation
            if self.encoder is not None:
                self._recompute_embeddings()
            return True
        if len(self.operations) >= self.max_ops:
            # ① 找用过且 avg_reward 最低的
            worst_op_name = None
            worst_reward = float('inf')
            for name, op in self.operations.items():
                if op.meta_info.get('usage_count', 0) > 0:
                    avg_reward = op.meta_info.get('avg_reward', 0.0)
                    if avg_reward < worst_reward:
                        worst_reward = avg_reward
                        worst_op_name = name
            # ② 兜底：全没用过 → 找 usage_count 最低的
            if worst_op_name is None:
                min_usage = float('inf')
                for name, op in self.operations.items():
                    usage = op.meta_info.get('usage_count', 0)
                    if usage < min_usage:
                        min_usage = usage
                        worst_op_name = name
            # 替换（被淘汰者直接删除——与记忆库的 forget 同构）
            if worst_op_name is not None:
                del self.operations[worst_op_name]
                # （原文后续：加入新操作并重算 embedding + 登记 new_operation_names）
