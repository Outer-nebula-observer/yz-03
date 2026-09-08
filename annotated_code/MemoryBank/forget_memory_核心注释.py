# ============================================================================
# MemoryBank: memory_retrieval/forget_memory.py 核心节选【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2305.10250 (AAAI'24) §2.3：
#   艾宾浩斯遗忘曲线 R=e^(-t/S)：时间衰减 + 命中强化（S+1, t 重置）。
#   本文件是该机制的**真实工程实现**——比论文公式多了三个落地细节。
#
# 【为什么精读】赛题③遗忘模块（schema.retention + evolution.forget）
#   的直系原型。读它才发现：论文公式 → 代码之间有"概率遗忘"这座桥。
#
# 【我们的实现对照】
#   forgetting_curve(t, S)        → schema.retention()（我们 math.exp(-t/S)）
#   update_memory_when_searched   → schema.mark_recalled()（S+1 + t 重置）
#   概率丢弃 random() > R         → 我们阈值判断（R < 0.3 确定删）
#   memory_strength 存在 JSON     → 我们存 MemoryEntry.decay_strength
# ============================================================================

import json, datetime, random, copy, math
from langchain.vectorstores import FAISS
from langchain.docstore.document import Document


def forgetting_curve(t, S):
    """艾宾浩斯留存率。⚠ 注意实现细节：exp(-t / (5*S))

    论文写 R = e^(-t/S)，代码里 S 乘了系数 5——**衰减速率压慢 5 倍**。
    为什么？t 单位是"天"，S 初始=1：无系数时一天后 R=e^(-1)≈0.37，
    几乎全忘——对话记忆不该忘这么快。5 倍系数是工程校准：
    让"没被召回的普通记忆"约一周才衰减过半。
    【教训】论文公式到落地之间必有参数校准——我们 retention()
    直接照抄公式没校准，README 不足清单第 6 条（参数未调优）的根源。
    """
    return math.exp(-t / 5 * S)   # 原文如此（等价 -t/(5/S) 见下）：注意原代码的
    # 运算优先级写法有歧义，作者意图是 exp(-t/(5*S))——慢衰减版本


class MemoryForgetterLoader:
    """遗忘器：加载记忆 → 逐条算留存率 → 概率丢弃 → 回写 JSON。"""

    def __init__(self, filepath, language, mode="elements"):
        self.memory_level = 3      # 记忆等级（论文的多级强度概念）
        self.total_date = 30       # 保留总时长上限（天）
        self.memory_bank = {}      # {user: {history: {date: [对话]}, summary: {date: 摘要}}}

    def _get_date_difference(self, date1, date2) -> int:
        """两个日期字符串 → 相差天数（t 的来源）。"""
        d1 = datetime.datetime.strptime(date1, "%Y-%m-%d")
        d2 = datetime.datetime.strptime(date2, "%Y-%m-%d")
        return (d2 - d1).days

    def update_memory_when_searched(self, recalled_memos, user, cur_date):
        """★ 命中强化（间隔效应的实现）——检索回调，不是进化操作！

        位置很关键：这个方法由 search_memory 在**每次检索后**调用——
        强化发生在"读取路径"，而非"进化路径"。
        【对照我们】mark_recalled() 在 hybrid/experiential 检索内部调用，
        同一设计——读取即强化，无需等进化周期。
        """
        for recalled in recalled_memos:
            recalled_id = recalled.metadata['memory_id']
            recalled_date = recalled_id.split('_')[1]
            for i, memory in enumerate(self.memory_bank[user]['history'][recalled_date]):
                if memory['memory_id'] == recalled_id:
                    # 两条更新，正对应论文"R=e^(-t/S)"的两个自变量：
                    self.memory_bank[user]['history'][recalled_date][i]['memory_strength'] += 1  # S+1
                    self.memory_bank[user]['history'][recalled_date][i]['last_recall_date'] = cur_date  # t 重置
                    break

    def initial_load_forget_and_save(self, name, now_date):
        """★ 遗忘主流程：加载 → 逐条概率丢弃 → 幸存者进 FAISS → 回写。

        【与我们的关键差异】MemoryBank 用**概率遗忘**：
            if random.random() > retention_probability: 丢弃
        留存率 R=0.3 的记忆有 30% 概率活下来——不是确定删！
        为什么？艾宾浩斯本身是统计规律（人类记忆也是概率性遗忘），
        概率版更贴认知模型，且带来自然的"随机性多样性"。
        【我们选了确定版】R < threshold 删——为了消融可复现
        （同样输入同样输出）。这是"认知拟真 vs 实验可控"的取舍，
        答辩可作为设计决策讲。
        """
        docs = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            memories = json.load(f)
            for user_name, user_memory in memories.items():
                if 'history' not in user_memory.keys():
                    continue
                self.memory_bank[user_name] = copy.deepcopy(user_memory)
                for date, content in user_memory['history'].items():
                    forget_ids = []
                    for i, dialog in enumerate(content):
                        # ---- 每条记忆带四元组元数据（我们的 MemoryEntry 同构）----
                        query = dialog['query']
                        response = dialog['response']
                        memory_strength = dialog.get('memory_strength', 1)   # S，默认 1
                        last_recall_date = dialog.get('last_recall_date', date)  # t 起点
                        memory_id = dialog.get('memory_id', f'{user_name}_{date}_{i}')

                        metadata = {'memory_strength': memory_strength,
                                    'memory_id': memory_id,
                                    'last_recall_date': last_recall_date,
                                    "source": memory_id}   # source=memory_id → 可溯源

                        # ---- 遗忘判定：R = f(距上次召回天数, 强度) ----
                        days_diff = self._get_date_difference(last_recall_date, now_date)
                        retention_probability = forgetting_curve(days_diff, memory_strength)

                        # ★ 概率丢弃：随机数 > 留存率 → 忘（详见上方注释）
                        if random.random() > retention_probability:
                            forget_ids.append(i)
                        else:
                            # 幸存者包装成 LangChain Document（进 FAISS 的原料）
                            docs.append(Document(page_content=..., metadata=metadata))

                    # ---- 倒序 pop（正序删会移位导致错删——经典坑）----
                    if len(forget_ids) > 0:
                        forget_ids.sort(reverse=True)
                        for idd in forget_ids:
                            self.memory_bank[user_name]['history'][date].pop(idd)

                    # ---- 整日记忆清空 → 连摘要一起删（层级联删）----
                    if len(self.memory_bank[user_name]['history'][date]) == 0:
                        self.memory_bank[user_name]['history'].pop(date)
                        self.memory_bank[user_name]['summary'].pop(date)
                    # 摘要（summary）也走同样的 强度/衰减 流程（同函数下半段，略）
        self.write_memories(self.filepath)   # 遗忘后回写 JSON——真删，非软删
        return docs


class LocalMemoryRetrieval:
    """检索器：FAISS 向量召回 + 邻块拼接 + 触发命中强化。"""

    def search_memory(self, query, vector_store, cur_date=''):
        """检索主流程（节选关键三步）。"""
        # ① 向量召回 top-6（VECTOR_SEARCH_TOP_K）
        related_docs_with_score = vector_store.similarity_search_with_score(query,
                                                                            k=self.top_k)
        related_docs = get_docs_with_score(related_docs_with_score)
        # ② 按日期 source 排序 → 同日多块拼回一段（检索结果的时序整理）
        related_docs = sorted(related_docs, key=lambda x: x.metadata["source"])
        ...
        # ③ ★ 检索后立即强化（遗忘模型与检索的联动点）
        self.memory_loader.update_memory_when_searched(related_docs,
                                                       user=self.user, cur_date=cur_date)
        self.save_updated_memory()   # 强化结果立刻持久化
        return date_docs, ', '.join(dates)

# ============================================================================
# 【给基础开发者的三条读懂线索】
# 1) 论文公式 ≠ 可直接运行：系数校准（×5）、默认值（S=1）、
#    判定方式（概率 vs 阈值）三处工程决策，每处都值得在答辩讲清取舍；
# 2) 遗忘触发在**加载时**（load 阶段逐条判定），强化触发在**检索后**——
#    一读一写两条路径都要碰记忆模型，缺一条遗忘曲线就不闭环；
# 3) 倒序 pop 防移位、整日清空连摘要级联删——数据结构层面的细节，
#    我们 forget() 用 store.remove(id) 天然规避，但要意识到这份"被保护"。
# ============================================================================
