# -*- coding: utf-8 -*-
"""指挥决策图谱检索引擎（子课题-1 交付引擎）。

在 GraphRAG 索引产物之上提供两类能力：
  1. 多跳关联检索：从问题命中的种子实体出发，沿关系边扩展 1~2 跳；
  2. 推理路径输出：每条结果附带 entities -> relationships -> entities 的显式链路，
     供上层规划系统引用、展示与审计。

数据来源有两种模式，自动选择（两种模式都直接读 parquet，不直连 Neo4j/Qdrant）：
  - shared：服务端环境（能 import server.neo4j_client 即判定为服务端），
     读检索数据根 data/检索数据/知识图谱数据/<KG名>/output/*.parquet；
  - local ：离线/沙箱环境，读本地索引产物 kg_out/<KG名>/output/*.parquet。

契约：memory_engine_sdk.md v1.0.0。本引擎只做检索，不声明生成与摄入能力。
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from server.engines.memory_plugin_api import EngineCapabilities, MemoryEnginePlugin

logger = logging.getLogger(__name__)

# 检索数据根相对路径前缀（契约要求 source_file 用相对路径，正斜杠）
KG_REL_PREFIX = "知识图谱数据"

#: 本地索引产物目录名（相对仓库根 / 引擎包目录，不写死机器路径）
KG_LOCAL_DIRNAME = "kg_out"


def _local_kg_candidates() -> List[Path]:
    """本地数据根候选：``kg_out`` 与包内 ``data/检索数据/知识图谱数据`` 两种布局，
    都按所在仓库逐级向上找，兼容「引擎被单独拷走」与「整包解压到任意目录」。
    """
    pkg = Path(__file__).resolve()
    cands: List[Path] = []
    for up in (4, 3, 2):                      # <仓库根> / sandbox / server
        if len(pkg.parents) > up:
            base = pkg.parents[up]
            cands.append(base / KG_LOCAL_DIRNAME)
            cands.append(base / "data" / "检索数据" / KG_REL_PREFIX)
    cands.append(pkg.parent / KG_LOCAL_DIRNAME)   # 引擎目录内自带一份
    return cands


def _resolve_kg_root() -> Path:
    """解析图谱数据根目录，优先级：

    1. 环境变量 ``COMMAND_GRAPH_KG_ROOT``
    2. 智戎检索数据根 ``server.config.knowledge_base_dir()/知识图谱数据``
       （即 ``data/检索数据/知识图谱数据``，接入后走这条）
    3. 本地数据根（按仓库布局自动定位 ``kg_out``，或包内 ``data/检索数据/知识图谱数据``；
       也可用环境变量覆盖）

    2、3 都取第一个**真实存在**的目录；都不存在时返回第 3 项的首个候选，
    由 check_availability 判否（日志里能看到实际找的路径）。
    """
    env = os.environ.get("COMMAND_GRAPH_KG_ROOT")
    if env:
        return Path(env)
    try:
        from server.config import knowledge_base_dir  # 只在智戎服务端存在
        cand = Path(knowledge_base_dir()) / KG_REL_PREFIX
        if cand.is_dir():
            return cand
    except Exception:  # noqa: BLE001
        pass
    cands = _local_kg_candidates()
    for cand in cands:
        if cand.is_dir():
            return cand
    return cands[0]

AVAILABILITY_TTL = 60.0  # check_availability 结果缓存秒数

#: 每跨越一次图谱（条令库 <-> 案例库）给多少加分
CROSS_KG_BONUS = 0.06
#: 每跨越一次文档（同一图谱内不同案例之间）给多少加分。
#: 比跨库小：案例之间的关联不如"条令规则依据"那样强。
#: 但要大到能让「含跨文档跳的 2 跳链路」压过「普通 1 跳邻居」：
#: 图一变密（2026-09 新语料）后 1 跳邻居拿 0.917，跨文档 2 跳只有 0.875，
#: 会被整批挤出 top_k，跨文档命中率实测从 0.75 掉到 0.50。
CROSS_DOC_BONUS = 0.05
#: 跨库/跨文档加分上限，避免长链路仅靠跨边界刷分
CROSS_KG_BONUS_CAP = 0.18

# ── 全局检索（论文 §Global Search：社区摘要 map-reduce）──────────
#: 判定「整体规律类问题」的标志词。这类问题的答案散在多个社区里，
#: 从实体种子出发扩展覆盖不到全部文档（实测种子"美军"只覆盖 4 篇），
#: 必须改走社区摘要；具体到单个实体的提问则不启用，以免挤掉精确命中。
HOLISTIC_MARKERS = (
    "哪些", "共同", "规律", "整体", "总体", "流程", "因素", "措施", "举措",
    "历次", "这些", "各案例", "案例中", "系列",
)
#: 全局结果在 top_k 里预留的名额。不预留的话，它们会被同分的实体路径挤光
#: （实体路径每个种子能产出十几条，8 个名额根本轮不到社区摘要）。
GLOBAL_RESERVE = 3
#: 社区报告的词面重叠达到该值即视为"完全相关"
GLOBAL_REL_FULL = 0.45
#: 全局结果的分数区间 0.50~0.85：低于"精确命中实体"的 0.895，
#: 高于 2 跳噪声，正好插在两者中间
GLOBAL_SCORE_BASE = 0.50
GLOBAL_SCORE_SPAN = 0.35
#: 社区报告的"覆盖广度"按几篇文档算满分。问"历次行动的共同规律"时，
#: 覆盖 4 篇案例的社区显然比只覆盖 1 篇的更该被选中，
#: 但纯词面排序会把这种社区压到十几名开外（实测 rel 只有 0.103）。
GLOBAL_BREADTH_FULL = 4.0
#: 覆盖广度在排序里的加分上限（只影响选谁，不影响最终分数）
GLOBAL_BREADTH_WEIGHT = 0.25

# ── 罗列型问题收口（"有哪些 / 清单 / 型号"类提问）──────────────────
#: 罗列型问题的标志词。
#: 问"这些行动中美军使用了哪些型号的精确制导弹药"时，答案散落在多条
#: 「X 属于 精确制导弹药」这种**清单关系边**上，而清单边权天生为 1
#: （strength 只给 0.774），低于 0 跳种子的 0.895；再叠加枢纽种子
#: 「美军」（度=38）的 6 条同分 1 跳先占满 top_k，"精确制导弹药"的
#: 1 跳邻居（战斧巡航导弹、AGM-114地狱火…）整批被挤出，答案退化成
#: 条令库的泛化条文。命中标志词、且种子里有装备/物资时才启用收口。
LIST_MARKERS = ("哪些", "都有哪些", "有什么", "列出", "清单", "型号")
#: 罗列型问题要收口的实体类型：武器装备与物资资源
LIST_TYPES = ("EQUIPMENT", "RESOURCE")
#: 罗列结果在 top_k 里预留的名额。问"有哪些"时，答案本身就是一**串**成员，
#: 必须给足名额：实测 Q11 只留 4 个时，另外 4 个还是被"美军"枢纽种子的
#: 条令库 2 跳（目标选择 / 动态目标打击 / 平台选择 / 空中作战计划）占着，
#: 与"哪些型号的弹药"毫不相干。留 2 个给常规路径兜底即可。
LIST_RESERVE = 6
#: 罗列结果的定档分（1 跳），每多一跳递减 LIST_SCORE_STEP
LIST_SCORE_BASE = 0.86
LIST_SCORE_STEP = 0.06
#: 罗列型展开时每个种子的名额上限（要装下一整类实体，比常规 12 大）
LIST_MAX_PATHS = 16
#: "成员类实体名"的领域词表。本体只有粗粒度 EQUIPMENT——轰炸机、驱逐舰
#: 这类**平台**和导弹、炸弹这类**弹药**同型，结构上分不开；问"哪些型号
#: 的弹药/武器"时只能靠名表把平台排到后面。只做排序键，不做硬过滤：
#: 宁可多带一条相关项，也不要把真正的答案卡掉。
LIST_ITEM_HINTS = ("导弹", "弹药", "炸弹", "火箭弹", "鱼雷", "炮弹",
                   "JDAM", "GBU", "SDB")

#: 每一跳随附的原文依据最大字符数（防止上下文爆炸）
#: 规划步骤实体类型（老师第 2 步「案例步骤分解」在图谱里的载体）
PHASE_TYPE = "PHASE"

EVIDENCE_MAX_CHARS = 400
# 案例原文里的元数据行（``来源:`` ``日期:`` ``行动:`` …）只做导航用，
# 不适合当"原文依据"，命中则降权。
META_LINE_RE = re.compile(
    r"^(来源|日期|时间|地点|行动|平台|发射平台|武器|武器类型|类型|数量|规模|目标|参战方)[:：]"
)


class CommandGraphEngine(MemoryEnginePlugin):
    """基于指挥决策知识图谱的多跳检索与推理路径输出引擎。"""

    name = "command_graph"
    engine_label = "指挥决策图谱"
    engine_color = "#2f6fd0"
    version = "1.3.3"  # 交付加固：路径可移植 + 并发安全
    #: 1.3.1：给每种子加 1 跳配额 + 提高跨文档加分，修新语料下 2 跳不生成的问题
    #: 1.3.2：罗列型提问按实体类型收口，避免清单成员被枢纽种子挤掉
    #: 1.3.3：交付加固——去掉写死的本机数据路径（改多布局自动定位）、
    #:        跨边界加分改按调用参数传递（并发检索不再互相串味）、
    #:        storage_backend 据实描述为「直接读 parquet」
    description = ("基于 GraphRAG 指挥决策知识图谱的多跳检索引擎；"
                   "每一跳附带来源文档，支持跨文档链路的显式输出与审计")
    contract_version = "1.0.0"

    #: 从种子实体向外扩展的最大跳数
    max_hops = 2
    #: 每个种子实体最多保留的路径条数
    max_paths_per_seed = 12
    #: 单个种子里 1 跳路径最多占几个名额。BFS 会先把 1 跳邻居铺满——
    #: 枢纽种子（实测「目标选择」度=121）12 个名额被 1 跳全占，2 跳根本
    #: 不生成，而 2 跳是唯一能承载跨文档跳的深度。超额的 1 跳只跳过
    #: 「计价」、仍继续入队，免得经过它的 2 跳路径一并丢失。
    max_hop1_per_seed = 6
    #: 命中种子的最少词元重叠比例（local 模式）
    min_seed_ratio = 0.2
    #: 强词元一个都没命中时，退化为单字匹配的阈值（更高，防常见字误命中）
    min_seed_ratio_fallback = 0.6

    def __init__(self, kg_root: str | None = None) -> None:
        self._kg_root = Path(kg_root) if kg_root else _resolve_kg_root()
        self._cache: Dict[str, Any] = {}          # 本地 parquet 缓存 {kg: {...}}
        self._avail: Tuple[float, bool] | None = None
        self._mode: str | None = None

    # ───────────────────────── 契约：能力与可用性 ─────────────────────────

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            supports_ingest=False,      # 数据由构建层(build_kg / 离线索引)负责
            supports_delete=False,
            supports_generate=False,    # 只做检索；生成由服务端统一编排
            supports_stream=False,
            supports_browse=False,
            supported_suffixes=[],      # 不认领后缀，避免与内建引擎抢占
            ingest_granularity="file",
            storage_backend="parquet(检索数据根) | parquet(本地 kg_out)",
        )

    async def check_availability(self) -> bool:
        """探测后端可用性，结果缓存 AVAILABILITY_TTL 秒。"""
        now = time.monotonic()
        if self._avail and now - self._avail[0] < AVAILABILITY_TTL:
            return self._avail[1]
        ok = await asyncio.to_thread(self._probe)
        self._avail = (now, ok)
        return ok

    def _probe(self) -> bool:
        if self._shared_available():
            self._mode = "shared"
            return True
        if self._local_available():
            self._mode = "local"
            return True
        self._mode = None
        return False

    # ───────────────────────── 后端探测 ─────────────────────────

    @staticmethod
    def _shared_available() -> bool:
        """共享底座是否可用（服务端环境）。"""
        try:
            import server.neo4j_client  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return True

    def _kg_dirs(self) -> List[Path]:
        if not self._kg_root.is_dir():
            return []
        out = []
        for sub in sorted(self._kg_root.iterdir()):
            if (sub / "output" / "entities.parquet").is_file() or \
               (sub / "output" / "create_final_entities.parquet").is_file():
                out.append(sub)
        return out

    def _local_available(self) -> bool:
        return bool(self._kg_dirs())

    # ───────────────────────── 契约：检索 ─────────────────────────

    async def search(self, query: str, top_k: int = 10,
                     timeout: float = 30.0) -> List[Dict[str, Any]]:
        """多跳检索入口。异常按契约向上抛，由路由器熔断器接管。"""
        if not await self.check_availability():
            logger.warning("command_graph: 无可用数据源（%s 下没有 <KG>/output/*.parquet）",
                           self._kg_root)
            return []

        return await asyncio.wait_for(self._search_impl(query, top_k), timeout=timeout)

    async def _search_impl(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        graph = await asyncio.to_thread(self._load_graph)
        if not graph["entities"]:
            return []

        seeds = self._find_seeds(query, graph)
        holistic = self._is_holistic(query)
        # 跨边界加分只在「整体规律类」问题上生效：那类问题本来就要跨案例，
        # 提升跨文档/跨库链路正是要点；单实体提问要的是精确命中，
        # 提升跨边界只会把金标文档往下压（实测 MRR 0.477 -> 0.352）。
        # 注意：它按调用参数往下传，不挂在 self 上——服务端可能并发调用 search()，
        # 实例属性会被另一个请求改写，导致这次检索的排序串味。
        if not seeds and not holistic:
            return []

        # ① 局部检索：从种子实体多跳扩展（论文的 Local Search）
        results: List[Dict[str, Any]] = []
        for seed, seed_score in seeds:
            for path in self._expand(seed, graph):
                results.append(self._to_result(seed, seed_score, path, graph,
                                               promote_cross=holistic))
        results.sort(key=lambda r: r["score"], reverse=True)

        # ② 全局检索：只有"整体规律类问题"才启用（论文的 Global Search）
        reserve = min(GLOBAL_RESERVE, top_k // 3) if holistic else 0
        if reserve:
            # 门控输入 = 局部检索本来会返回的那批结果覆盖了哪些文档
            covered: List[str] = []
            for r in results[:top_k]:
                for d in r["metadata"].get("docs") or []:
                    if d not in covered:
                        covered.append(d)
            glob = self._global_results(query, graph, reserve, covered)
        else:
            glob = []

        # ③ 罗列型收口：问"有哪些/清单/型号"时，把装备/物资这一类成员收齐
        lists = self._list_results(query, seeds, graph, promote_cross=holistic)
        lists = lists[: min(LIST_RESERVE, max(0, top_k - 2))]

        if not glob and not lists:
            return self._dedup(results, top_k)

        # 给全局结果与罗列结果预留名额后再合并排序：实体路径一个种子就能产出
        # 十几条，不预留的话社区摘要/清单成员永远进不了 top_k。
        merged = (results[: max(0, top_k - len(glob) - len(lists))]
                  + glob + lists)
        if len(merged) < top_k:
            # 去重还会再吃掉一些名额（同一实体可能被两条路径命中），
            # 用后面的实体路径补齐，免得 top_k 出现空位
            have = {r["chunk_id"] for r in merged}
            for r in results:
                if len(merged) >= top_k:
                    break
                if r["chunk_id"] not in have:
                    have.add(r["chunk_id"])
                    merged.append(r)
        merged.sort(key=lambda r: r["score"], reverse=True)
        return self._dedup(merged, top_k)

    # ───────────────────────── 图加载 ─────────────────────────

    def _load_graph(self) -> Dict[str, Any]:
        """加载本地索引产物（带 mtime 缓存）。

        关键：同名实体可能同时存在于多个图谱（如"美军"同时在条令库与案例库），
        因此这里用 entity_kgs / entity_docs 保留**全部**出处，而不是让后加载的库覆盖前者。
        这正是跨文档多跳链路得以成立的前提。
        """
        merged: Dict[str, Any] = {
            "entities": {},        # name -> 实体属性（多库时取度数最高者作为展示）
            "relationships": [],
            "communities": {},
            "reports": [],         # 社区报告（全局检索的检索单元），带 kg 标记
            "kg_of": {},           # name -> 代表库（展示用）
            "entity_kgs": {},      # name -> [库名, ...]  跨库桥接点
            "entity_docs": {},     # name -> [文档标题, ...]
            "tu2doc": {},          # text_unit -> 文档标题
            "tu2text": {},         # text_unit -> 原文片段（推理依据）
        }
        for kg_dir in self._kg_dirs():
            kg = kg_dir.name
            cached = self._cache.get(kg)
            key = self._mtime_key(kg_dir)
            if cached and cached["key"] == key:
                ents = cached["entities"]
                rels = cached["relationships"]
                comms = cached["communities"]
                reports = cached["reports"]
                tu2doc = cached["tu2doc"]
                tu2text = cached["tu2text"]
            else:
                ents, rels, comms, reports, tu2doc, tu2text = self._read_parquet(kg_dir)
                self._cache[kg] = {"key": key, "entities": ents, "relationships": rels,
                                   "communities": comms, "reports": reports,
                                   "tu2doc": tu2doc, "tu2text": tu2text}

            for name, ent in ents.items():
                prev = merged["entities"].get(name)
                if prev is None or ent["degree"] > prev["degree"]:
                    merged["entities"][name] = ent
                    merged["kg_of"][name] = kg
                merged.setdefault("entity_kgs", {}).setdefault(name, []).append(kg)
                docs = merged["entity_docs"].setdefault(name, [])
                for tu in ent.get("text_units", []):
                    doc = tu2doc.get(tu)
                    if doc and doc not in docs:
                        docs.append(doc)

            for rel in rels:
                rel["kg"] = kg          # 每条边记下所属库，供跨库判定
                merged["relationships"].append(rel)
            for rep in reports:
                rep["kg"] = kg          # 同理，全局结果要能说出自己出自哪个库
                merged["reports"].append(rep)
            merged["communities"].update(comms)
            merged["tu2doc"].update(tu2doc)
            merged["tu2text"].update(tu2text)
        return merged

    @staticmethod
    def _mtime_key(kg_dir: Path) -> float:
        stamps = [p.stat().st_mtime for p in (kg_dir / "output").glob("*.parquet")]
        meta = kg_dir / "meta"
        if meta.is_dir():
            stamps.extend(p.stat().st_mtime for p in meta.glob("*.json"))
        return max(stamps, default=0.0)

    @staticmethod
    def _as_list(value: Any) -> List[str]:
        """把 parquet 的 list 列（ndarray / str / NaN）统一成 [str]。"""
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(x) for x in value]
        try:
            if value != value:      # NaN
                return []
        except Exception:           # noqa: BLE001
            pass
        if hasattr(value, "tolist"):
            out = value.tolist()
            return [str(x) for x in out] if isinstance(out, list) else [str(out)]
        text = str(value).strip()
        if not text or text in ("nan", "None", "[]"):
            return []
        if text.startswith("[") and text.endswith("]"):
            return [t.strip().strip("'\"") for t in text[1:-1].split(",") if t.strip()]
        return [text]

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        """容忍 NaN / 空串的 float 转换（parquet 里 rank、size 常见 None）。"""
        try:
            out = float(value)
        except (TypeError, ValueError):
            return default
        return default if out != out else out      # NaN

    @staticmethod
    def _read_parquet(kg_dir: Path):
        """读取一个图谱目录的产物。

        返回 (entities, relationships, communities, reports, tu2doc, tu2text)，
        其中 tu2doc 是 text_unit -> 文档标题 的映射，用于把每一跳回溯到原文；
        reports 是社区报告（Global Search 的检索单元），自带覆盖文档与代表实体。
        来源链：实体/关系 --text_unit_ids--> text_units --document_id--> documents.title
        """
        import pandas as pd

        out = kg_dir / "output"

        def pick(*names: str) -> Path | None:
            for n in names:
                p = out / n
                if p.is_file():
                    return p
            return None

        ent: Dict[str, Any] = {}
        id2title: Dict[str, str] = {}
        p = pick("entities.parquet", "create_final_entities.parquet")
        if p:
            df = pd.read_parquet(p)
            for row in df.itertuples(index=False):
                d = row._asdict()
                title = str(d.get("title") or d.get("name") or "").strip()
                if not title:
                    continue
                id2title[str(d.get("id") or "")] = title
                ent[title] = {
                    "title": title,
                    "type": str(d.get("type") or ""),
                    "description": str(d.get("description") or ""),
                    "degree": int(d.get("degree") or 0),
                    "text_units": CommandGraphEngine._as_list(d.get("text_unit_ids")),
                }

        rels: List[Dict[str, Any]] = []
        p = pick("relationships.parquet", "create_final_relationships.parquet")
        if p:
            df = pd.read_parquet(p)
            for row in df.itertuples(index=False):
                d = row._asdict()
                src = str(d.get("source") or "").strip()
                tgt = str(d.get("target") or "").strip()
                if not src or not tgt:
                    continue
                rels.append({
                    "source": src,
                    "target": tgt,
                    "description": str(d.get("description") or ""),
                    "weight": float(d.get("weight") or 0.0),
                    "text_units": CommandGraphEngine._as_list(d.get("text_unit_ids")),
                })

        comms: Dict[str, Any] = {}
        reports: List[Dict[str, Any]] = []
        p = pick("community_reports.parquet", "create_final_community_reports.parquet")
        if p:
            df = pd.read_parquet(p)
            for row in df.itertuples(index=False):
                d = row._asdict()
                cid = str(d.get("community") or "")
                reports.append({
                    "id": cid,
                    "title": str(d.get("title") or ""),
                    "summary": str(d.get("summary") or ""),
                    "level": int(CommandGraphEngine._to_float(d.get("level"))),
                    "rank": CommandGraphEngine._to_float(d.get("rank")),
                    "size": int(CommandGraphEngine._to_float(d.get("size"))),
                    "findings": CommandGraphEngine._as_list(d.get("findings")),
                    "text_units": [],
                    "entity_ids": [],
                })
                comms[cid] = {
                    "title": str(d.get("title") or ""),
                    "summary": str(d.get("summary") or ""),
                    "level": int(CommandGraphEngine._to_float(d.get("level"))),
                }

        # 社区 -> text_unit / entity（后面折算成"这个社区摘要覆盖了哪些文档、哪些实体"）
        comm_text_units: Dict[str, List[str]] = {}
        p = pick("communities.parquet", "create_final_communities.parquet")
        if p:
            for row in pd.read_parquet(p).itertuples(index=False):
                d = row._asdict()
                cid = str(d.get("community") or "")
                if not cid:
                    continue
                comm_text_units[cid] = CommandGraphEngine._as_list(d.get("text_unit_ids"))
                for rep in reports:
                    if rep["id"] == cid:
                        rep["entity_ids"] = CommandGraphEngine._as_list(d.get("entity_ids"))
                        break
        for rep in reports:
            rep["text_units"] = comm_text_units.get(rep["id"], [])
        # text_unit -> 文档标题（关系跳溯源用）
        doc_title: Dict[str, str] = {}
        p = pick("documents.parquet", "create_final_documents.parquet")
        if p:
            for row in pd.read_parquet(p).itertuples(index=False):
                d = row._asdict()
                doc_title[str(d.get("id") or "")] = str(d.get("title") or d.get("id") or "")

        tu2doc: Dict[str, str] = {}
        tu2text: Dict[str, str] = {}
        p = pick("text_units.parquet", "create_final_text_units.parquet")
        if p:
            for row in pd.read_parquet(p).itertuples(index=False):
                d = row._asdict()
                # graphrag 3.1.0 的外键是单数 document_id
                refs = (CommandGraphEngine._as_list(d.get("document_id"))
                        or CommandGraphEngine._as_list(d.get("document_ids")))
                if refs:
                    tu_id = str(d.get("id") or "")
                    tu2doc[tu_id] = doc_title.get(refs[0], refs[0])
                    tu2text[tu_id] = str(d.get("text") or "").strip()  # 保留换行，供 _sentences 定位

        # 社区报告落到"覆盖哪些文档、代表哪些实体"，全局检索要靠它把
        # 摘要结果挂回具体文档上（否则没法溯源，也没法算召回）
        for rep in reports:
            docs: List[str] = []
            for tu in rep.get("text_units") or []:
                doc = tu2doc.get(str(tu))
                if doc and doc not in docs:
                    docs.append(doc)
            rep["docs"] = docs
            titles: List[str] = []
            for eid in rep.get("entity_ids") or []:
                name = id2title.get(str(eid))
                if name and name not in titles:
                    titles.append(name)
            titles.sort(key=lambda n: -(ent.get(n, {}).get("degree") or 0))
            rep["entities"] = titles[:8]

        return ent, rels, comms, reports, tu2doc, tu2text

    # ───────────────────────── 种子定位 ─────────────────────────

    def _find_seeds(self, query: str, graph: Dict[str, Any]) -> List[Tuple[str, float]]:
        """按词元重合比例定位种子实体，取 top 5。

        两轮：先用强词元（二字滑窗）精确定位；一个都定位不到时，
        才退化成单字匹配兜底——阈值更高，避免常见字把不相关的实体拉进来。
        """
        seeds = self._match_seeds(query, self._tokenize(query), graph,
                                  self.min_seed_ratio, chars=False)
        if seeds:
            return seeds
        return self._match_seeds(query, self._tokenize_chars(query), graph,
                                 self.min_seed_ratio_fallback, chars=True)

    def _match_seeds(self, query: str, q_tokens: set, graph: Dict[str, Any],
                     threshold: float, chars: bool) -> List[Tuple[str, float]]:
        if not q_tokens:
            return []
        tokenize = self._tokenize_chars if chars else self._tokenize
        scored: List[Tuple[float, str]] = []
        for name, ent in graph["entities"].items():
            if chars and len(name) < 2:      # 单字实体必为抽取噪音
                continue
            name_tokens = tokenize(name)
            if not name_tokens:
                continue
            hit = len(q_tokens & name_tokens) / len(name_tokens)
            if hit < threshold:
                continue
            # 度数越高说明在体系中越关键，作为轻微加权；名字长度作次键，
            # 同样的命中率下优先取更具体的那个名字
            scored.append((hit + min(ent["degree"], 50) / 500.0, len(name), name))
        scored.sort(reverse=True)

        # 消歧：存在「更长、且分数不低于它」的命中名字把它包含在内时，丢弃短名。
        # 例：问"沙伊拉特空军基地为什么被打击"，条令库实体"空军"整词命中同样满分，
        # 但它是"沙伊拉特空军基地"的子串，属噪声种子，会挤掉真正的种子名额。
        # 反过来，若长名只是勉强过阈值（如"美国海军"被
        # "RCT 救援协调组（美国海军）"包含），则短名才是更准的种子，必须保留。
        picked: List[Tuple[float, str]] = []
        for score, _, name in scored:
            if any(other_score >= score and len(other) > len(name) and name in other
                   for other_score, _, other in scored):
                continue
            picked.append((score, name))
        return [(name, min(score, 1.0)) for score, name in picked[:5]]

    # ─────────────────── 全局检索（论文 §Global Search）───────────────────

    @staticmethod
    def _is_holistic(query: str) -> bool:
        """判断是不是「整体规律类」提问。

        这类问题的答案散在多个社区里（"历次行动有哪些共同规律"），从种子实体
        往外扩永远覆盖不全——实测种子"美军"只覆盖 4 篇文档，而答案要 5 篇。
        具体到单个实体的提问（"沙伊拉特空军基地为什么被打击"）不启用，
        免得全局结果把精确命中挤下去。
        """
        return any(m in query for m in HOLISTIC_MARKERS)

    @staticmethod
    def _bigrams(text: str) -> set:
        """词面重叠用的词元：ASCII 词 + 中文二字滑窗（只在连续汉字段内取）。"""
        s = re.sub(r"\s+", "", str(text or "").lower())
        out = set(re.findall(r"[a-z0-9][a-z0-9\-\.]{2,}", s))
        run = ""
        for ch in s:
            if "\u4e00" <= ch <= "\u9fff":
                run += ch
            else:
                for i in range(len(run) - 1):
                    out.add(run[i:i + 2])
                run = ""
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
        return out

    def _match_reports(self, query: str, reports: List[Dict[str, Any]],
                       k: int | None = None,
                       breadth: bool = False) -> List[Tuple[float, Dict[str, Any]]]:
        """给社区报告排序：词面重叠为主，``breadth=True`` 时并入覆盖广度。

        广度权重只给"整体规律类"问题用——那类问题要的是"跨了多少篇"，
        而不是"某个词重合多少"。返回的 rel 一律是**纯词面重叠**，
        广度只影响排序，不污染结果分数。
        """
        q = self._bigrams(query)
        if not q:
            return []
        scored: List[Tuple[float, float, Dict[str, Any]]] = []
        for rep in reports:
            # 词元集缓存到报告对象上（图谱本身有 mtime 缓存，一份报告只算一次）：
            # 335 条报告每次查询都重算的话，单问要多花 ~600ms
            grams = rep.get("_body_grams")
            if grams is None:
                body = str(rep.get("title") or "") + str(rep.get("summary") or "")
                for f in rep.get("findings") or []:
                    if isinstance(f, dict):
                        body += str(f.get("summary") or "") + str(f.get("explanation") or "")
                grams = self._bigrams(body)
                rep["_body_grams"] = grams
            rel = len(q & grams) / max(len(q), 1)
            if rel <= 0:
                continue
            rank = rel
            if breadth:
                # 只当温和的加分项，不让"覆盖广"盖过"讲的是同一件事"；
                # 真正把跨文档社区捞上来的是 _global_results 里的覆盖门控。
                rank = rel + GLOBAL_BREADTH_WEIGHT * min(
                    len(rep.get("docs") or []) / GLOBAL_BREADTH_FULL, 1.0)
            scored.append((rank, rel, rep))
        scored.sort(key=lambda t: -t[0])
        return [(rel, rep) for _, rel, rep in (scored if k is None else scored[:k])]

    def _global_results(self, query: str, graph: Dict[str, Any],
                        k: int, covered: List[str]) -> List[Dict[str, Any]]:
        """全局检索：检索单元是社区摘要，而不是实体链路。

        ``covered`` 是局部检索已经覆盖到的文档。只收"能带来新文档"的社区摘要——
        这个门控保证全局检索**只补覆盖、不抢名额**：若它拿不出新东西，
        结果与启用前完全一致（实测 Q08 就是靠它避免倒退的）。
        """
        reports = graph.get("reports") or []
        if not reports or k <= 0:
            return []
        picked: List[Dict[str, Any]] = []
        seen = set(covered)
        for rel, rep in self._match_reports(query, reports, None, breadth=True):
            fresh = [d for d in (rep.get("docs") or []) if d not in seen]
            if not fresh:
                continue
            picked.append(self._to_global_result(rep, rel, graph))
            seen.update(fresh)
            if len(picked) >= k:
                break
        return picked

    def _to_global_result(self, rep: Dict[str, Any], rel: float,
                          graph: Dict[str, Any]) -> Dict[str, Any]:
        """把一条社区报告整理成与实体结果同构的契约结果。"""
        raw = min(rel / GLOBAL_REL_FULL, 1.0)
        score = round(GLOBAL_SCORE_BASE + GLOBAL_SCORE_SPAN * raw, 4)
        docs = list(rep.get("docs") or [])
        kg = rep.get("kg") or ""
        title = str(rep.get("title") or "")
        level = int(rep.get("level") or 0)

        # 原文依据取该社区名下前两个 text_unit，供上层核查摘要是否忠于原文
        facts: List[Dict[str, str]] = []
        for tu in (rep.get("text_units") or [])[:2]:
            text = (graph.get("tu2text") or {}).get(str(tu), "")
            if not text:
                continue
            facts.append({"doc": (graph.get("tu2doc") or {}).get(str(tu), ""),
                          "text_unit": str(tu), "text": text[:EVIDENCE_MAX_CHARS]})

        bullets: List[str] = []
        for f in rep.get("findings") or []:
            if isinstance(f, dict) and str(f.get("summary") or "").strip():
                bullets.append(str(f["summary"]).strip())
            if len(bullets) >= 3:
                break

        content = f"[社区摘要 L{level}] {title}：{rep.get('summary', '')}"
        for i, b in enumerate(bullets, 1):
            content += f"\n要点{i}：{b}"
        if docs:
            content += f"\n覆盖文档：{'、'.join(docs)}"
        if facts:
            content += f"\n依据（{facts[0]['doc'] or '未知来源'}）：{facts[0]['text'][:300]}"

        steps = [f"社区摘要 L{level}：{title}"]
        if len(docs) > 1:
            steps.append(f"覆盖 {len(docs)} 篇文档")

        return {
            "content": content.strip(),
            "score": score,
            "source_file": f"{KG_REL_PREFIX}/{kg}" if kg else KG_REL_PREFIX,
            "chunk_id": f"{kg}:community:{rep.get('id', '')}",
            "engine": self.name,
            "metadata": {
                "seed": "",
                "entity": title,
                "entity_type": "COMMUNITY",
                "hops": 0,
                "kg_source": kg,
                "kgs": [kg] if kg else [],
                "docs": docs,
                # 社区摘要是"汇总视图"不是多跳链路：跨库/跨文档跳数一律记 0，
                # 否则"跨文档命中率""路径可溯源率"这些创新点指标会被灌水。
                "cross_kg_hops": 0,
                "cross_doc_hops": 0,
                "reasoning_path": steps,
                "hops_detail": [],
                "evidence": facts,
                "source_label": f"[KG:{kg or 'unknown'}][COMMUNITY:{rep.get('id', '')}]",
                "path_text": f"社区摘要 · {title}",
                "planning_steps": [],
                "citation_graph": self._community_citation_graph(rep, docs),
                "search_mode": "global",
                "match_ratio": round(rel, 4),
                "community_level": level,
                "community_size": int(rep.get("size") or 0),
                "community_entities": list(rep.get("entities") or []),
            },
        }

    @staticmethod
    def _community_citation_graph(rep: Dict[str, Any],
                                  docs: List[str]) -> Dict[str, Any]:
        """社区级文档引用图：代表实体 → 社区 → 来源文档。"""
        ckey = f"C:{rep.get('id', '')}"
        nodes: Dict[str, Dict[str, Any]] = {
            ckey: {"id": ckey, "label": str(rep.get("title") or ""),
                   "kind": "community", "type": "COMMUNITY",
                   "level": int(rep.get("level") or 0)}
        }
        edges: List[Dict[str, Any]] = []
        for name in rep.get("entities") or []:
            ekey = f"E:{name}"
            nodes[ekey] = {"id": ekey, "label": name, "kind": "entity", "type": ""}
            edges.append({"from": ekey, "to": ckey, "kind": "belongs", "rel": "属于该社区"})
        for name in docs:
            dkey = f"D:{name}"
            nodes[dkey] = {"id": dkey, "label": name, "kind": "doc", "type": "DOC"}
            edges.append({"from": ckey, "to": dkey, "kind": "citation", "rel": "摘要依据"})
        return {"nodes": list(nodes.values()), "edges": edges}

    # ────────────── 罗列型收口（论文 Local Search 的清单特化）──────────────

    @staticmethod
    def _type_of(graph: Dict[str, Any], name: str) -> str:
        return str((graph["entities"].get(name) or {}).get("type") or "")

    def _list_seeds(self, query: str, seeds: List[Tuple[str, float]],
                    graph: Dict[str, Any]) -> List[Tuple[str, float]]:
        """罗列型收口的闸门：问「有哪些 / 清单 / 型号」，且种子里有装备/物资。

        只认结构（实体类型），不认关系描述文本——描述是 LLM 现写的，措辞
        不稳定；类型来自图谱本体，稳定可靠。两个条件同时满足才启用，
        避免把"沙伊拉特空军基地为什么被打击"这类精确提问也拐到清单上。
        """
        if not any(m in query for m in LIST_MARKERS):
            return []
        return [(name, score) for name, score in seeds
                if self._type_of(graph, name) in LIST_TYPES]

    def _list_results(self, query: str, seeds: List[Tuple[str, float]],
                      graph: Dict[str, Any],
                      promote_cross: bool = False) -> List[Dict[str, Any]]:
        """把「装备 / 物资」这一类的成员收齐，而不是按全局分数排。

        常规局部检索按分数排序时，清单关系边（"战斧巡航导弹 属于
        精确制导弹药"）的边权天生为 1，strength 只有 0.774，压不过 0 跳
        种子（0.895），再被枢纽种子的同分 1 跳一挤就整批落榜，答案就
        退化成条令库的泛化条文。这里改成"从装备/物资种子出发、只收同类
        成员"，分数定档（1 跳 0.86 / 每多一跳减 0.06），稳定进 top_k。

        排序只用排序键、不做硬过滤：① 名字像弹药/武器的排前面（本体只有
        粗粒度类型，平台与弹药同型，只能靠名表区分）；② 度数高的排前面
        （在体系里越关键）；③ 跨边界证据多的排前面。种子自身不入清单——
        种子是提问命中的"类别/主体"，不是它的成员。
        """
        list_seeds = self._list_seeds(query, seeds, graph)
        if not list_seeds:
            return []
        seed_names = {name for name, _ in seeds}

        def keep(nxt: str) -> bool:
            # 同类型才计入结果；不符的仍会被 _expand 入队，供 2 跳穿过
            return self._type_of(graph, nxt) in LIST_TYPES

        cands: List[Dict[str, Any]] = []
        for seed, seed_score in list_seeds:
            for path in self._expand(seed, graph, keep=keep,
                                     max_paths=LIST_MAX_PATHS):
                name = path["entity"]
                if name in seed_names \
                        or self._type_of(graph, name) not in LIST_TYPES:
                    continue
                res = self._to_result(seed, max(seed_score, 0.9), path, graph,
                                      promote_cross=promote_cross)
                res["score"] = round(min(
                    LIST_SCORE_BASE - LIST_SCORE_STEP * max(0, path["hops"] - 1),
                    1.0), 4)
                meta = res["metadata"]
                meta["search_mode"] = "list"
                meta["list_seed"] = seed
                cands.append(res)
        cands.sort(key=lambda r: self._list_rank(r, graph))
        # 同一实体可能由多条路径命中（种子不同 / 跳数不同），只留排序最优
        # 的那条，免得一个实体把好几个预留名额占掉
        out: List[Dict[str, Any]] = []
        seen: set = set()
        for r in cands:
            name = r["metadata"]["entity"]
            if name in seen:
                continue
            seen.add(name)
            out.append(r)
        return out

    @staticmethod
    def _list_rank(res: Dict[str, Any], graph: Dict[str, Any]) -> tuple:
        """罗列结果的排序键（升序越小越前）。"""
        meta = res["metadata"]
        name = meta["entity"]
        # 名字不像弹药/武器的（平台、装备库…）退一位；同类再按度数、跨边界
        not_item = 0 if any(w in name for w in LIST_ITEM_HINTS) else 1
        degree = int((graph["entities"].get(name) or {}).get("degree") or 0)
        cross = int(meta["cross_kg_hops"]) + int(meta["cross_doc_hops"])
        return (not_item, -degree, -cross, int(meta["hops"]))

    @staticmethod
    def _tokenize(text: str) -> set:
        """强词元：ASCII 词元 + 中文二字滑窗。

        刻意**不**收录单个汉字：像"伊""军"这类高频字，会让实体
        "伊军"（海湾战争）误命中"沙伊拉特空军基地为什么被打击"这种提问。
        二字滑窗只在连续汉字段内生成——否则"卡西姆·苏莱曼尼"里的间隔号
        会拼出"姆苏"这种并不存在的词，拉低真实匹配率。
        """
        tokens: set = set()
        buf = ""
        run: List[str] = []

        def flush_run() -> None:
            for i in range(len(run) - 1):
                tokens.add(run[i] + run[i + 1])
            run.clear()

        for ch in text.lower():
            if "\u4e00" <= ch <= "\u9fff":
                if buf:
                    tokens.add(buf)
                    buf = ""
                run.append(ch)
                continue
            flush_run()
            if ch.isascii() and (ch.isalnum() or ch == "_"):
                buf += ch
            elif buf:
                tokens.add(buf)
                buf = ""
        if buf:
            tokens.add(buf)
        flush_run()
        return tokens

    @staticmethod
    def _tokenize_chars(text: str) -> set:
        """弱词元：单个汉字。仅在强词元召回为空时兜底使用。"""
        return {c for c in text if "\u4e00" <= c <= "\u9fff"}

    # ───────────────────────── 多跳扩展 ─────────────────────────

    def _adjacency(self, graph: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        adj: Dict[str, List[Dict[str, Any]]] = {}
        for r in graph["relationships"]:
            adj.setdefault(r["source"], []).append({"other": r["target"], "rel": r, "dir": "out"})
            adj.setdefault(r["target"], []).append({"other": r["source"], "rel": r, "dir": "in"})
        return adj

    def _hop_doc(self, graph: Dict[str, Any], rel: Dict[str, Any]) -> Tuple[str, str]:
        """把一条边回溯到原文：取该边第一个 text_unit 及其所属文档。"""
        tu2doc = graph.get("tu2doc") or {}
        for tu in rel.get("text_units", []):
            doc = tu2doc.get(tu)
            if doc:
                return tu, doc
        return "", ""

    @staticmethod
    def _clean_md(text: str) -> str:
        """剥掉 markdown 结构符号，只留可读正文。"""
        s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text or "")
        s = re.sub(r"^\s*#{1,6}\s*", "", s)
        s = re.sub(r"^\s*[-*+>]+\s*", "", s)
        s = re.sub(r"^\s*\d+[.)]\s*", "", s)
        s = re.sub(r"\*{1,3}|`{1,3}|_{2,}", "", s)
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip(" \t-\u2014=\u00b7")

    @classmethod
    def _flat(cls, text: str) -> str:
        """清洗 markdown 并把换行/连续空白压成单空格，得到可读的单行文本。"""
        return " ".join(cls._clean_md(text).split())

    @classmethod
    def _sentences(cls, text: str) -> List[str]:
        """按 markdown 结构切分并清洗，得到可作原文依据的句子单元。

        案例原文是 markdown（标题、``---``、``**来源**: [链接]``），几乎不含
        句末标点；只按标点切会把整篇切成一个巨型“句子”，依据于是退回文档开头。
        因此改为「先按行切、再按标点切」，并丢弃纯结构行。
        """
        units: List[str] = []
        for line in re.split(r"\n+", text or ""):
            line = cls._clean_md(line)
            if len(line) < 8 or set(line) <= set("-=\u2014*_\u00b7. \t"):
                continue
            for piece in re.split(r"(?<=[。！？；!?;])\s*", line):
                piece = piece.strip(" \t-\u2014=\u00b7")
                if len(piece) >= 8:
                    units.append(piece)
        return units

    def _hop_evidence(self, graph: Dict[str, Any], rel: Dict[str, Any],
                      node: str, nxt: str) -> str:
        """定位这一跳的原文依据。

        直接取 text_unit 全文会拿到文档开头（对短文档尤甚）。这里把正文切成
        候选句后打分取优：「同时出现两端实体」>「与关系描述字面重合」>
        「出现目标实体」，并轻微偏好中等长度句子。
        """
        tu2text = graph.get("tu2text") or {}
        full = ""
        for tu in rel.get("text_units", []):
            if tu2text.get(tu):
                full = tu2text[tu]
                break
        if not full:
            return ""

        units = self._sentences(full)
        if not units:
            return self._flat(full)[:EVIDENCE_MAX_CHARS]

        desc = rel.get("description") or ""
        grams = {desc[k:k + 2] for k in range(len(desc) - 1)}

        best, best_score = "", 0.0
        for u in units:
            score = 0.0
            if node and nxt and node in u and nxt in u:
                score += 3.0
            else:
                if nxt and nxt in u:
                    score += 1.0
                if node and node in u:
                    score += 1.0
            if grams:
                score += 2.0 * sum(1 for g in grams if g in u) / len(grams)
            if 20 <= len(u) <= 200:
                score += 0.5
            # 偏好真正的整句；短而无句末标点的多为标题/字段行，降权
            if u.endswith(("。", "！", "？", "!", "?", "…")):
                score += 0.6
            elif len(u) < 40:
                score -= 0.3
            if META_LINE_RE.match(u):
                score -= 1.0
            if score > best_score:
                best, best_score = u, score
        if not best:
            return self._flat(full)[:EVIDENCE_MAX_CHARS]
        return best[:EVIDENCE_MAX_CHARS]

    @staticmethod
    def _citation_graph(graph: Dict[str, Any], path: Dict[str, Any],
                        docs: List[str]) -> Dict[str, Any]:
        """构造「文档引用图」：实体节点 + 关系边 + 实体→来源文档的引用边。

        老师第 6 步 Q4 明确要求「构建文档引用图并说明」，这里把数据整理成
        前端可直接渲染的 nodes/edges 结构（也便于导出 Mermaid / SVG）。
        """
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        seen_edge: set = set()

        def entity_key(name: str) -> str:
            key = f"E:{name}"
            if key not in nodes:
                nodes[key] = {
                    "id": key, "label": name, "kind": "entity",
                    "type": (graph["entities"].get(name) or {}).get("type", ""),
                }
            return key

        def doc_key(name: str) -> str:
            key = f"D:{name}"
            if key not in nodes:
                nodes[key] = {"id": key, "label": name, "kind": "doc", "type": "DOC"}
            return key

        def add_edge(a: str, b: str, kind: str, rel: str, **extra: Any) -> None:
            sig = (a, b, kind, rel)
            if sig in seen_edge:
                return
            seen_edge.add(sig)
            edges.append({"from": a, "to": b, "kind": kind, "rel": rel, **extra})

        entity_key(path["entity"])
        for h in path.get("detail", []) or []:
            a, b = entity_key(h.get("from", "")), entity_key(h.get("to", ""))
            add_edge(a, b, "relation", h.get("rel", ""), dir=h.get("dir", "out"),
                     cross_doc=bool(h.get("cross_doc")), cross_kg=bool(h.get("cross_kg")),
                     kg=h.get("kg", ""), doc=h.get("doc", ""))
            if h.get("doc"):
                dk = doc_key(h["doc"])
                add_edge(a, dk, "citation", "来源")
                add_edge(b, dk, "citation", "来源")
        for d in docs or []:
            if d:
                add_edge(entity_key(path["entity"]), doc_key(d), "citation", "来源")
        return {"nodes": list(nodes.values()), "edges": edges}

    def _make_hop(self, graph: Dict[str, Any], node: str, nxt: str,
                  rel: Dict[str, Any], direction: str,
                  prev_doc: str = "") -> Dict[str, Any]:
        """构造一跳的结构化记录，供上层渲染与审计。

        cross_doc 比较的是"上一跳的边所属文档"与"本跳的边所属文档"——
        相邻两跳落在不同文档，即认为这条链路跨了文档。
        """
        tu, doc = self._hop_doc(graph, rel)
        evidence = self._hop_evidence(graph, rel, node, nxt)
        kg_from = graph["kg_of"].get(node, "")
        kg_to = graph["kg_of"].get(nxt, "")
        return {
            "from": node,
            "to": nxt,
            "from_type": (graph["entities"].get(node) or {}).get("type", ""),
            "to_type": (graph["entities"].get(nxt) or {}).get("type", ""),
            "rel": rel.get("description", ""),
            "dir": direction,
            "kg": kg_to or rel.get("kg", ""),
            "kg_from": kg_from,
            "kg_to": kg_to,
            "doc": doc,
            "text_unit": tu,
            "evidence": evidence,
            "cross_kg": bool(kg_from and kg_to and kg_from != kg_to),
            "cross_doc": bool(prev_doc and doc and prev_doc != doc),
        }

    def _expand(self, seed: str, graph: Dict[str, Any], keep=None,
                max_paths: int | None = None) -> List[Dict[str, Any]]:
        """BFS 扩展至 max_hops 跳，返回种子自身及若干条带显式链路的路径。"""
        adj = graph.get("_adj")
        if adj is None:
            adj = self._adjacency(graph)
            graph["_adj"] = adj

        # 种子实体本身作为 0 跳结果，保证针对具体实体的提问也有召回
        paths: List[Dict[str, Any]] = [
            {"entity": seed, "chain": [], "detail": [], "weight": 0.0,
             "hops": 0, "cross_kg": 0, "cross_doc": 0}
        ]
        queue: List[Tuple[str, List[str], List[Dict[str, Any]], float, frozenset, int]] = [
            (seed, [], [], 0.0, frozenset({seed}), 0)
        ]
        limit = max_paths or self.max_paths_per_seed
        hop1_kept = 0
        while queue and len(paths) < limit:
            node, chain, detail, wsum, visited, hop = queue.pop(0)
            if hop >= self.max_hops:
                continue
            for edge in adj.get(node, []):
                nxt = edge["other"]
                if nxt in visited:
                    continue
                rel = edge["rel"]
                arrow = (f"-[{rel['description'][:40] or '相关'}]->" if edge["dir"] == "out"
                         else f"<-[{rel['description'][:40] or '相关'}]-")
                step = f"{node} {arrow} {nxt}"
                prev_doc = detail[-1]["doc"] if detail else ""
                hop_rec = self._make_hop(graph, node, nxt, rel, edge["dir"], prev_doc)
                new_detail = [*detail, hop_rec]
                depth = hop + 1
                if keep is not None and not keep(nxt):
                    # 类型不符：不计入结果，但仍入队（2 跳还要经过它）
                    queue.append((nxt, [*chain, step], new_detail, wsum + rel["weight"],
                                  visited | {nxt}, depth))
                    continue
                if keep is None and depth == 1 and hop1_kept >= self.max_hop1_per_seed:
                    # 1 跳名额已满：不计入结果，但仍入队，好让 2 跳能生成
                    queue.append((nxt, [*chain, step], new_detail, wsum + rel["weight"],
                                  visited | {nxt}, depth))
                    continue
                if keep is None and depth == 1:
                    hop1_kept += 1
                paths.append({
                    "entity": nxt,
                    "chain": [*chain, step],
                    "detail": new_detail,
                    "weight": wsum + rel["weight"],
                    "hops": hop + 1,
                    "cross_kg": sum(1 for h in new_detail if h["cross_kg"]),
                    "cross_doc": sum(1 for h in new_detail if h["cross_doc"]),
                })
                if len(paths) >= limit:
                    break
                queue.append((nxt, [*chain, step], new_detail, wsum + rel["weight"],
                              visited | {nxt}, hop + 1))
        return paths

    # ───────────────────────── 结果组装 ─────────────────────────

    def _to_result(self, seed: str, seed_score: float, path: Dict[str, Any],
                   graph: Dict[str, Any],
                   promote_cross: bool = False) -> Dict[str, Any]:
        ent = graph["entities"].get(path["entity"], {})
        kg = graph["kg_of"].get(path["entity"], "")
        hops = path["hops"]
        # 越近的跳数、越强的边权、越高的种子相似度 => 分数越高
        # hop_decay: 0 跳=1.0, 1 跳=0.667, 2 跳=0.5（原写法在 0 跳时算出 2.0，会虚高）
        hop_decay = 1.0 / (1.0 + 0.5 * hops)
        strength = min(path["weight"] / 20.0, 1.0) if path["weight"] else 0.3
        # 跨边界加分：本课题的核心能力（跨文档多跳），让它优先于等价的单文档链路冒头
        cross_bonus = 0.0
        if promote_cross:
            cross_bonus = min(
                CROSS_KG_BONUS * path.get("cross_kg", 0)
                + CROSS_DOC_BONUS * path.get("cross_doc", 0),
                CROSS_KG_BONUS_CAP,
            )
        score = round(min(0.6 * seed_score + 0.25 * hop_decay
                          + 0.15 * strength + cross_bonus, 1.0), 4)

        chain = path["chain"]
        docs = graph["entity_docs"].get(path["entity"], [])
        kgs = graph["entity_kgs"].get(path["entity"], [])
        # 逐跳原文依据（按 text_unit 去重），让上层既能引用也能核查
        evidence: List[Dict[str, str]] = []
        seen_tu: set = set()
        for h in path.get("detail", []):
            tu = h.get("text_unit") or ""
            if not tu or tu in seen_tu or not h.get("evidence"):
                continue
            seen_tu.add(tu)
            evidence.append({"doc": h.get("doc", ""), "text_unit": tu,
                             "text": h.get("evidence", "")})

        content = f"[{ent.get('type', '')}] {path['entity']}：{ent.get('description', '')}"
        if docs:
            content += f"\n来源文档：{'、'.join(docs)}"
        if chain:
            content += "\n推理路径：" + "；".join(chain)
        if evidence:
            content += f"\n依据（{evidence[0]['doc'] or '未知来源'}）：{evidence[0]['text'][:300]}"
        elif ent.get("description"):
            content += f"\n依据（{docs[0] if docs else '未知来源'}）：{ent['description'][:300]}"

        # source_file 必须是「检索数据根」（data/检索数据/）下的正斜杠相对路径，
        # 与 SDK 文档示例（如 "知识图谱数据/JP3_60"）保持一致；
        # 人类可读的 [KG:..][DOC:..] 标签改放 metadata.source_label。
        if kg:
            src_label = f"{KG_REL_PREFIX}/{kg}"
        else:
            src_label = f"{KG_REL_PREFIX}"
        doc_label = f"[KG:{kg or 'unknown'}]"
        if docs:
            doc_label += f"[DOC:{docs[0]}]"

        # 展示用：本结果涉及哪些规划步骤（老师第 2 步的步骤分解维度）
        names: List[str] = [path["entity"]]
        for h in path.get("detail", []) or []:
            names.extend([h.get("from", ""), h.get("to", "")])
        planning_steps: List[str] = []
        for name in names:
            if name and (graph["entities"].get(name) or {}).get("type") == PHASE_TYPE \
                    and name not in planning_steps:
                planning_steps.append(name)

        citation_graph = self._citation_graph(graph, path, docs)

        return {
            "content": content.strip(),
            "score": score,
            "source_file": src_label,
            "chunk_id": f"{kg}:{path['entity']}",
            "engine": self.name,
            "metadata": {
                "seed": seed,
                "entity": path["entity"],
                "entity_type": ent.get("type", ""),
                "hops": hops,
                "kg_source": kg,
                "kgs": kgs,
                "docs": docs,
                "cross_kg_hops": path.get("cross_kg", 0),
                "cross_doc_hops": path.get("cross_doc", 0),
                "reasoning_path": chain,
                "hops_detail": path.get("detail", []),
                "evidence": evidence,
                "source_label": doc_label,
                "path_text": " → ".join(chain) if chain else path["entity"],
                "planning_steps": planning_steps,
                "citation_graph": citation_graph,
            },
        }

    @staticmethod
    def _dedup(results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for r in results:
            key = r["chunk_id"]
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
            if len(out) >= top_k:
                break
        return out


engine_plugin = CommandGraphEngine()
