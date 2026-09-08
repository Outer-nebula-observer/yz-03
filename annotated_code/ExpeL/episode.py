# ============================================================================
# ExpeL: memory/episode.py —— 经验库的最小数据结构【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2308.10144 (AAAI'24 Oral) §3.1：
#   ExpeL 的"经验"= 成功轨迹 + 失败轨迹 + 反思。本文件定义单条轨迹 Trajectory——
#   它是后续 FAISS 经验库（expel.py::setup_vectorstore）的存储单元。
#
# 【为什么精读】赛题③经验记忆库（memsys/long_term/experiential_store.py）
#   的直系参照：我们存"教训文本"，ExpeL 存"结构化轨迹"——
#   看懂这个类，就明白"经验到底该存什么粒度"。
#
# 【我们的实现对照】
#   ExpeL.Trajectory          →  memsys.experiential_store.MemoryEntry
#   两级检索键（task粗/step细） →  我们只一级（content+source 联合编码）
#   三流解析（obs/act/thought） →  我们不做（无 ReAct 环境信号，复盘文本直接入库）
#   反思 reflections 复用       →  我们的 review_text 扮演同等角色
# ============================================================================

from typing import List, Callable, Dict, Optional
from copy import deepcopy

class Trajectory:
    """一条完整任务轨迹（ExpeL 经验库的原子单元）。

    设计精髓（论文 §3.1）：
      - 同一份轨迹文本，解析出【三种粒度】：
          task   （粗）—— 用于"找相似任务"
          step   （中）—— 一个 step = 思考+动作+观察一轮，用于"找相似步骤"
          thought（细）—— 单条思考，用于 reranker 二次精排
      - 多粒度 = 检索时可以"细粒度命中、粗粒度使用"
        （用一条 thought 找到它，但把整条轨迹喂给 LLM 当 fewshot 示例）
    """

    def __init__(
        self,
        task: str,               # 任务描述——检索锚（query 与它比相似度）
        trajectory: str,         # 轨迹原文（ReAct 格式：Thought/Action/Observation 交替）
        splitter: Callable,      # 行切分器：把轨迹文本切成一行行
        identifier: Callable,    # 行分类器：判断某行是 thought/action/observation
        step_splitter: Callable, # 步聚合器：把连续行聚成一个个 step
        embedder: Optional[Callable] = None,  # 向量化器（传入才生成检索键）
        reflections: List[str] = None         # Reflexion 式反思（复用 Reflexion 产物）
    ):
        self._task = task
        self._trajectory = trajectory
        # deepcopy 防外部修改污染（多条轨迹可能共享同一反思列表）
        self._reflections = deepcopy(reflections)

        # ---- 三流解析：一行行分类，动态追加到 _observations/_actions/_thoughts ----
        # 技巧：identifier 返回 'thought'/'action'/'observation'，
        #       拼出属性名 '_thoughts' 等，避免三分支 if-else（元编程省代码）
        self._observations, self._actions, self._thoughts = [], [], []
        for line in splitter(self._trajectory):
            setattr(self, f'_{identifier(line)}s',
                    getattr(self, f'_{identifier(line)}s') + [line])

        # ---- 步聚合：连续的 obs/act/thought 归为一个 step ----
        # （经验提炼 insight_extraction 的最小粒度就是 step）
        self._steps = step_splitter(lines=trajectory, cycler=splitter,
                                    step_identifier=identifier)

        # ---- 检索键：三级向量（task 粗 / step 中 / thought 细）----
        # 【我们的对照】experiential_store.add() 只做一级：
        #   vindex.add(entry.id, f"{content}\n{source}")
        # 我们不需要多级——作战教训是"提炼后产物"（一句话），无轨迹可拆。
        self._keys = {'thought': [], 'step': []}
        if embedder is not None:
            self._keys['task'] = [embedder(self.task)]      # 任务向量：粗检索
            for step in self.steps:
                self._keys['step'].append(embedder(step))   # 步向量：细检索
            for thought in self.thoughts:
                self._keys['thought'].append(embedder(thought))  # 思考向量：rerank 用

    # ---- 以下全是只读属性（外部不可篡改内部状态——经验库的完整性） ----

    @property
    def task(self) -> str:
        return self._task

    @property
    def steps(self) -> List[str]:
        return self._steps

    @property
    def trajectory(self) -> str:
        return self._trajectory

    @property
    def num_steps(self) -> int:
        # 步数 = 三流最大长度（防御性：解析器可能漏分类某些行）
        return max(len(self.thoughts), len(self.actions), len(self.observations))

    @property
    def observations(self) -> List[str]:
        return self._observations

    @property
    def actions(self) -> List[str]:
        return self._actions

    @property
    def thoughts(self) -> List[str]:
        return self._thoughts

    @property
    def reflections(self) -> List[str]:
        return self._reflections

    @property
    def keys(self) -> Dict[str, List[float]]:
        # {task: [vec], step: [vec...], thought: [vec...]}
        # expel.py::setup_vectorstore 会把这些键灌进 FAISS
        return self._keys

    def _replace(self, attr, value):
        # 原作者笔误（self.__setattr__(self,...) 双重 self）——上游遗留，勿学；
        # 意图是"替换某属性"，正确写法应为 self.__setattr__(attr, value)
        self.__setattr__(self, attr, value)
