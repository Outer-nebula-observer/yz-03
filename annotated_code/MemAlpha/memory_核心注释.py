# ============================================================================
# Mem-α: memory.py 核心节选【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2509.25911 §3：
#   core/episodic/semantic 三组件记忆 + 多工具操作 + RL 训练。
#   本文件是 Memory 类：三库的增删查与检索（BM25/向量双路）。
#
# 【为什么精读】赛题③记忆操作 API 的接口参照（docs/09 决策 2 的
#   "建议-执行分离"，其执行侧原型就在这里）；双路检索（bm25 默认）
#   与我们 hybrid 三路同构。
#
# 【我们的实现对照】
#   Memory 三库（core/semantic/episodic） → 我们双库（fact/experience）
#   memory_search 双方法                 → hybrid 三路（+sql）
#   new_memory_insert/memory_update/delete → evolution.write/merge/forget
#   嵌入矩阵批量相似度                    → 我们逐条 cosine（小库可接受）
# ============================================================================

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi


class Memory:
    """core/semantic/episodic 三库，全内存（RAM）。

    设计要点：
      - core 是**纯字符串**（非列表）——它整体进 system prompt，永不检索；
      - semantic/episodic 是 List[Dict[id→content]] + 配套嵌入矩阵——
        矩阵与列表**平行存储**（ids 列表记录矩阵行↔记忆的映射），
        批量检索时一次 cosine_similarity 打全库（比逐条快百倍）。
    """

    MAX_MEMORY_ITEMS = 20          # system prompt 里最多展示的记忆条数（上下文预算）
    MEMORY_CONSOLIDATE_STEP = 5    # 每次合并操作处理的记忆数（防一次动太多）
    MODEL = "gpt-4.1-mini"         # 与 agent.py 同模型（一致性）
    TOPK = 20

    def __init__(self, including_core: bool = False,
                 disabled_memory_types: list = None):
        # disabled_memory_types：消融开关！可关掉 semantic/episodic 任一库——
        # RL 训练时用它做"记忆架构消融"（我们 G2/G3 的同款思路）
        disabled_memory_types = disabled_memory_types or []
        normalized_disabled = {t.lower() for t in disabled_memory_types}
        invalid = normalized_disabled - {"core", "semantic", "episodic"}
        if invalid:
            raise ValueError(f"Invalid memory types: {', '.join(sorted(invalid))}")

        if including_core:
            self.core: str = ""    # core=整段文本常驻 system prompt
        else:
            self.core = None       # None=禁用（消融用）
        self.semantic: List[Dict[str, str]] = []
        self.episodic: List[Dict[str, str]] = []
        # 嵌入矩阵（1536 维 = text-embedding-3-small）——行与库条目平行
        self.semantic_embedding_matrix: np.ndarray = np.empty((0, 1536))
        self.episodic_embedding_matrix: np.ndarray = np.empty((0, 1536))
        self.semantic_embedding_ids: List[str] = []
        self.episodic_embedding_ids: List[str] = []

    # ------------------------------------------------------------------
    # 【检索】memory_search —— 双方法路由（BM25 默认 / 向量可选）
    # ------------------------------------------------------------------
    def memory_search(self, memory_type: str, query: str, top_k: int = None,
                      min_score: float = 0.0,
                      search_method: str = "bm25") -> List[Tuple[Dict, float]]:
        """BM25 或向量余弦检索。**默认 bm25**——便宜、快、无嵌入成本。

        【与我们对照】hybrid.py 默认 vector；Mem-α 默认 bm25——
        各有道理：它面向 RL 高频训练（打分次数巨多，bm25 省钱）；
        我们面向低频检索（质量优先）。启示：**默认检索路应按调用频率选**。

        core 不可检索（ValueError）：core 永远在 system prompt 里，
        检索它没有意义——"常驻记忆不检索"是条硬规则。
        """
        if memory_type == 'core':
            raise ValueError("Core memory doesn't support searching. "
                             "Core memory is always included in the system prompt.")
        if memory_type not in ['semantic', 'episodic']:
            raise ValueError(f"Invalid memory_type: {memory_type}.")

        mem_list = getattr(self, memory_type)   # 动态取库（semantic/episodic 同构）
        if not mem_list or not query.strip():
            return []

        if search_method == "bm25":
            return self._search_bm25(memory_type, query, top_k, min_score)
        elif search_method == "text-embedding":
            return self._search_embedding(memory_type, query, top_k, min_score)

    def _search_bm25(self, memory_type, query, top_k=None, min_score=0.0):
        """rank_bm25 库做词法检索（与我们 eval 版 BM25 同算法不同实现）。

        min_score 阈值过滤：低于分的直接不返回——
        【值得搬】我们 hybrid 缺这个：低分垃圾混进 top_k 会浪费上下文。
        """
        mem_list = getattr(self, memory_type)
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 展平：[{id: content}, ...] → [(id, content), ...]
        documents, doc_contents = [], []
        for mem in mem_list:
            for memory_id, content in mem.items():
                documents.append((memory_id, content))
                doc_contents.append(content)

        tokenized_corpus = [self._tokenize(c) for c in doc_contents]
        bm25 = BM25Okapi(tokenized_corpus)          # 每次检索重建索引（小库可接受）
        doc_scores = bm25.get_scores(query_tokens)  # 全库打分一次出

        results = []
        for i, (memory_id, content) in enumerate(documents):
            score = doc_scores[i]
            if score >= min_score:                  # 阈值过滤（防低分垃圾）
                results.append(({memory_id: content}, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k] if top_k else results

    def _search_embedding(self, memory_type, query, top_k=None, min_score=0.0):
        """向量检索：**矩阵批量**余弦（与逐条循环的关键差异）。

        query(1×1536) @ 库矩阵(N×1536)ᵀ → 一次算完全库相似度。
        库到几千条时，这比 Python 循环快两个数量级——
        我们 MemoryVectorIndex 是逐条 cosine，万条内够用，
        再大就要学这个"矩阵平行存储 + 批量打分"结构。
        """
        mem_list = getattr(self, memory_type)
        embedding_matrix = getattr(self, f"{memory_type}_embedding_matrix")
        embedding_ids = getattr(self, f"{memory_type}_embedding_ids")

        if not mem_list or embedding_matrix.shape[0] == 0:
            return []

        query_embedding = self._get_embedding(query)
        if np.allclose(query_embedding, 0):   # 嵌入失败防御（API 挂了返回零向量）
            return []

        # 批量余弦：一次矩阵运算打全库
        similarities = cosine_similarity(
            query_embedding.reshape(1, -1),
            embedding_matrix)                 # → shape (1, N)
        ...

    # ------------------------------------------------------------------
    # 【三操作】insert / update / delete（evolution 四操作的原型）
    # ------------------------------------------------------------------
    def new_memory_insert(self, memory_type: str, content: str):
        """插入前查重（_content_exists）——与我们 write() 的 PREMem θ 查重同位。
        插入 = 追加列表 + 追加嵌入矩阵行（两处必须同步，否则检索错位）。"""
        ...

    def memory_update(self, memory_type: str, new_content: str, memory_id=None):
        """更新：按 id 找到旧条目 → 换内容 → **重算该行嵌入**。
        MEMORY_CONSOLIDATE_STEP=5：一次最多合并 5 条（防 prompt 爆炸 +
        小步快跑便于 RL 奖励归因）。"""
        ...

    def memory_delete(self, memory_type: str, memory_id: str = None):
        """删除：列表删 + 矩阵行删（np.delete 后 ids 列表同步）。
        注意：物理删除（我们 forget 也物理删，Zep 用 invalid_at 软删——
        三种策略各有适用：硬删省空间/软删保历史/归档可回放）。"""
        ...

# ============================================================================
# 【给基础开发者的三条读懂线索】
# 1) "列表 + 嵌入矩阵平行存储"是向量库的最简自实现——行号对齐是命门，
#    增删改必须双写（漏一处就检索错位，且极难排查）；
# 2) 默认检索路按**调用频率**选：RL 训练高频→BM25（零嵌入成本），
#    在线服务低频→向量（质量优先）——我们 hybrid 的 route 字段
#    就是把"这个选择"交给调用方；
# 3) min_score 阈值过滤是廉价的质量保险：top_k 只保证数量不保证质量，
#    低分命中不如不命中（省上下文就是省钱）。
# ============================================================================
