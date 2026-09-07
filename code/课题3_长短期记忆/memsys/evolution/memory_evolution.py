# -*- coding: utf-8 -*-
"""
memsys.evolution.memory_evolution — 记忆进化（创新重点，模块 A）
=================================================================
四操作实现（docs/04 2.4 节），全部"只写"（检索层只读——避坑点 3）：

  ① write   写入：从复盘对话抽取候选 → 去重（相似度阈值 θ，PREMem 链接对
            思路：cosine > θ 判定重复）→ 落库（事实→SQLite，经验→向量库）
  ② merge   合并：找相似簇 → LLM/规则融合为一条 → merged_from 记录来源（可回放）
  ③ forget  遗忘：艾宾浩斯 R=e^(-t/S)（MemoryBank）——
            R < forget_threshold 且 importance 不高的条目删除；
            "重要"标准可配（如 importance >= 2.0 永不删——失败教训保命）
  ④ abstract 抽象：多条同主题经验 → LLM 摘要成一条高阶"作战教训"
            （TiM Post-thinking / StructMem 周期整合思路）

每一步都写入 op_history，支撑 G4 消融的"进化可回放、可解释"。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..schema import MemoryEntry, MemoryType, MemoryOp, new_entry
from ..llm import LLMClient
from ..embeddings import MemoryVectorIndex, MockEmbedding, cosine
from ..long_term.factual_store import FactualStore
from ..long_term.experiential_store import ExperientialStore


@dataclass
class EvolutionReport:
    """一次进化调用的报告（消融实验直接统计此对象）。"""

    wrote: List[str] = field(default_factory=list)      # 写入的条目 id
    merged: List[Tuple[str, List[str]]] = field(default_factory=list)  # (新id, 来源ids)
    forgot: List[str] = field(default_factory=list)     # 遗忘的条目 id
    abstracted: List[str] = field(default_factory=list) # 抽象产出的条目 id
    skipped: List[str] = field(default_factory=list)    # 去重跳过的候选

    def summary(self) -> Dict[str, int]:
        return {"write": len(self.wrote), "merge": len(self.merged),
                "forget": len(self.forgot), "abstract": len(self.abstracted),
                "skip_duplicate": len(self.skipped)}


class MemoryEvolution:
    """记忆进化器：只被 controller 在'场次结束/复盘后'调用。

    参数：
        merge_theta:    相似度阈值 θ（PREMem 用 0.6；MockEmbedding 分布不同，
                        默认 0.80——消融时可扫描）
        forget_threshold: 等效'天数'——R 衰减到该值以下且不重要则遗忘
        protected_importance: importance ≥ 该值的条目永不遗忘（失败教训保护线）
    """

    def __init__(self, factual: FactualStore, experiential: ExperientialStore,
                 llm: LLMClient, embedding: MockEmbedding,
                 merge_theta: float = 0.80, forget_threshold: float = 0.30,
                 protected_importance: float = 2.0) -> None:
        self.factual = factual
        self.experiential = experiential
        self.llm = llm
        self.vindex = MemoryVectorIndex(embedding)  # 进化专用临时索引（查重/聚类）
        self.merge_theta = merge_theta
        self.forget_threshold = forget_threshold
        self.protected_importance = protected_importance

    # ---------------------------------------------------------------- ① 写入
    def write(self, type_: MemoryType, content: str, source: str = "",
              session_id: str = "", importance: float = 1.0,
              attrs: Dict | None = None) -> str | None:
        """写入一条记忆（带查重：与同库现有条目 cosine > θ 判重复，跳过）。

        返回新条目 id；重复则返回 None 并由调用方统计 skip。
        """
        store = self.factual if type_ == MemoryType.FACT else self.experiential
        # --- 查重（PREMem 链接对：相似度阈值判定"是否已有此知识"） ---
        # 直接逐条比对（库规模万级内足够快；换 FAISS 后可走索引检索）
        new_vec = self.vindex.model.embed(content)
        dup = None
        best_sim = -1.0
        for cid in store.candidates():
            existing = store.get(cid)
            if existing is None:
                continue
            sim = cosine(new_vec, self.vindex.model.embed(existing.content))
            if sim > best_sim:
                best_sim, dup = sim, existing
        if dup is not None and best_sim > self.merge_theta:
            return None  # 重复：跳过写入

        entry = new_entry(type_, content, source=source, session_id=session_id,
                          importance=importance,
                          metadata=attrs or {}, op_history=[MemoryOp.WRITE.value])
        store.add(entry)
        return entry.id

    # ---------------------------------------------------------------- ② 合并
    def merge(self, entry_ids: List[str]) -> str | None:
        """把多条相似记忆合并为一条（内容融合 + merged_from 溯源）。

        真模型：LLM 融合改写；Mock：拼接去重行（保底）。
        """
        if len(entry_ids) < 2:
            return None
        entries: List[MemoryEntry] = []
        for eid in entry_ids:
            e = self.factual.get(eid) or self.experiential.get(eid)
            if e:
                entries.append(e)
        if len(entries) < 2:
            return None
        merged_content = self.llm.summarize(
            "\n".join(sorted({e.content for e in entries})), max_words=150)
        base = entries[0]
        merged = new_entry(
            base.type, merged_content, source="merge", session_id=base.session_id,
            importance=max(e.importance for e in entries),
            merged_from=[e.id for e in entries],
            op_history=[MemoryOp.MERGE.value],
        )
        store = self.factual if merged.type == MemoryType.FACT else self.experiential
        store.add(merged)
        for e in entries:  # 删除被合并者（内容已进 merged）
            store.remove(e.id)
        return merged.id

    # ---------------------------------------------------------------- ③ 遗忘
    def forget(self, now: float | None = None) -> List[str]:
        """按艾宾浩斯衰减淘汰低价值记忆，返回被遗忘的 id 列表。

        规则（MemoryBank + 保护线）：
          R = e^(-t/S) < forget_threshold 且 importance < protected_importance → 删
        注意：本方法只做"硬删除"；检索侧的 mark_recalled() 已实现'命中强化'，
        使常用记忆 S 增大、更难被遗忘——两机制共同构成完整遗忘模型。
        """
        now = now if now is not None else time.time()
        forgot: List[str] = []
        for store in (self.factual, self.experiential):
            for cid in list(store.candidates()):
                e = store.get(cid)
                if e is None:
                    continue
                if e.importance >= self.protected_importance:
                    continue  # 失败教训等重要条目保护
                if e.retention(now) < self.forget_threshold:
                    store.remove(cid)
                    forgot.append(cid)
        return forgot

    # ---------------------------------------------------------------- ④ 抽象
    def abstract(self, entry_ids: List[str], theme: str = "") -> str | None:
        """把多条同主题经验抽象为一条高阶教训（TiM Post-thinking）。

        与 merge 的区别：merge 是"去重式合并"（内容基本相同）；
        abstract 是"升华式抽象"（多条具体经验 → 一条通用原则）。
        """
        entries = []
        for eid in entry_ids:
            e = self.factual.get(eid) or self.experiential.get(eid)
            if e:
                entries.append(e)
        if len(entries) < 2:
            return None
        material = "\n".join(f"- {e.content}" for e in entries)
        prompt = (f"以下为多条作战复盘经验（主题：{theme or '综合'}），"
                  f"请抽象出 1 条可跨场次复用的通用教训：\n{material}")
        abstract_text = self.llm.summarize(prompt, max_words=120)
        abstract_entry = new_entry(
            MemoryType.EXPERIENCE, abstract_text, source="abstract",
            session_id=entries[0].session_id,
            importance=max(e.importance for e in entries) + 0.5,  # 抽象经验更重要
            merged_from=[e.id for e in entries],
            op_history=[MemoryOp.ABSTRACT.value],
            metadata={"theme": theme},
        )
        self.experiential.add(abstract_entry)
        return abstract_entry.id

    # ---------------------------------------------------------------- 复盘驱动入口
    def evolve_from_review(self, review_dialogue: str, session_id: str = "") -> EvolutionReport:
        """场次复盘驱动的进化入口（pipeline ⑦ 直接调它）。

        流程（LLM 抽取 → 写入（查重）→ 合并 → 遗忘 → 抽象）：
          1. llm.extract_memory_ops() 从复盘文本抽取操作建议（真模型时是 LLM，
             Mock 时是关键词规则——接口不变）；
          2. 逐条 write（重复自动跳过）；
          3. 对同类型条目做一次相似簇 merge（θ 阈值成对判重）；
          4. forget() 淘汰衰减记忆；
          5. 对"失败教训簇"做 abstract（演示抽象操作）。
        """
        report = EvolutionReport()
        ops = self.llm.extract_memory_ops(review_dialogue)
        new_ids_by_type: Dict[str, List[str]] = {"fact": [], "experience": []}

        # 1) 写入（含查重）
        for op in ops:
            if op.get("op") != "write":
                continue  # MVP：只处理 write 建议；merge/forget 由周期任务触发
            mtype = MemoryType.FACT if op.get("type") == "fact" else MemoryType.EXPERIENCE
            new_id = self.write(mtype, op.get("content", ""),
                                source=f"复盘:{session_id}", session_id=session_id,
                                importance=float(op.get("importance", 1.0)))
            if new_id:
                report.wrote.append(new_id)
                new_ids_by_type[mtype.value].append(new_id)
            else:
                report.skipped.append(op.get("content", "")[:50])

        # 2) 合并（新写入条目两两查重，超阈值则 merge）
        for mtype_value, ids in new_ids_by_type.items():
            i = 0
            while i < len(ids) - 1:
                e1 = self.factual.get(ids[i]) or self.experiential.get(ids[i])
                e2 = self.factual.get(ids[i + 1]) or self.experiential.get(ids[i + 1])
                if e1 and e2:
                    v1 = self.vindex.model.embed(e1.content)
                    v2 = self.vindex.model.embed(e2.content)
                    if cosine(v1, v2) > self.merge_theta:
                        mid = self.merge([e1.id, e2.id])
                        if mid:
                            report.merged.append((mid, [e1.id, e2.id]))
                            ids[i] = mid  # 合并产物继续参与后续比对
                            ids.pop(i + 1)
                            continue
                i += 1

        # 3) 遗忘（周期性；此处每场复盘触发一次）
        report.forgot = self.forget()

        # 4) 抽象（失败教训 ≥2 条时升华一条通用教训）
        exp_ids = [eid for eid in new_ids_by_type["experience"]]
        if len(exp_ids) >= 2:
            aid = self.abstract(exp_ids, theme="本场复盘教训")
            if aid:
                report.abstracted.append(aid)

        return report
