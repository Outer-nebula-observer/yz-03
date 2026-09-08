# 源码精读注释 ①：ExpeL（`03_记忆检索/ExpeL/`）

> **读法**：本文按"三阶段流水线"逐段贴源码 + 中文逐行注释。每段末尾有【论文对应】与【我们的实现】。
> **论文**：arXiv 2308.10144（AAAI 2024 Oral）；笔记：`references/03_记忆检索/笔记_Zhao2023-ExpeL.md`。
> **为什么精读它**：赛题经验记忆的直系参照，代码最完整（train→insight→eval 全链路），我们的经验库就是它的简化版。

---

## 0. 三阶段流水线总览（先建立地图）

```
train.py（阶段①经验收集）      → agent自主执行任务，存成功/失败轨迹
insight_extraction.py（阶段②提炼）→ 对比成败轨迹，抽自然语言 insights
eval.py（阶段③评测）           → 新任务来了：FAISS 召回相似轨迹 + insights 注入 prompt
```

对应论文 Figure 2：**gather experiences → extract insights → test-time recall**。

---

## 1. `memory/episode.py::Trajectory` —— 一条经验的数据结构

```python
class Trajectory:
    def __init__(self, task, trajectory, splitter, identifier, step_splitter,
                 embedder=None, reflections=None):
        self._task = task                 # 任务描述——检索时的"锚"（query 用它编向量）
        self._trajectory = trajectory     # 完整轨迹原文（成功/失败都存——论文：失败也是财富）
        self._reflections = deepcopy(reflections)  # Reflexion 式反思文本（可复用 Reflexion 产物）
        # ↓ 把轨迹"解析"成三个流：observations（环境反馈）/ actions（动作）/ thoughts（思考）
        for line in splitter(self._trajectory):
            # identifier 判断每行是哪类，动态追加到 _observations/_actions/_thoughts
            setattr(self, f'_{identifier(line)}s', getattr(self, f'_{identifier(line)}s') + [line])
        # 再把行聚合成 step（一个 step = 思考+动作+观察一轮）——经验提炼的最小粒度
        self._steps = step_splitter(lines=trajectory, cycler=splitter, step_identifier=identifier)
        self._keys = {'thought': [], 'step': []}
        if embedder is not None:
            self._keys['task'] = [embedder(self.task)]   # 任务向量 = 粗检索键
            for step in self.steps:
                ...                                        # 每个 step 也编向量 = 细召回键
```

**【论文对应】** 论文 §3.1：经验 = 成功轨迹 + 失败轨迹 + 反思；**两级键**（task 粗 / step 细）支撑 fewshot_strategy 的五种检索策略（task/step/thought/action/reflection_similarity）。

**【我们的实现】** `memsys/long_term/experiential_store.py` 是它的极简版：`add()` 里 `vindex.add(id, f"{content}\n{source}")` 联合编码 = 只保留"task 级粗键"；三流解析不需要（我们无 ReAct 环境信号，复盘文本直接当 content）。

---

## 2. `agent/expel.py::setup_vectorstore()` —— 把历史经验装进 FAISS

```python
def setup_vectorstore(self) -> None:
    # ① 五类索引字典：内容 → (所属任务, 第几条轨迹)。作用：命中"片段"能反查"整条轨迹"
    self.keys2task = {'thought': {}, 'task': {}, 'step': {}, 'reflection': {}, 'action': {}}
    self.docs = []
    # ② 合并：自主收集的成功轨迹 + 人工 fewshots（不同 benchmark 的切法不同）
    combined_history = dict(self.succeeded_trial_history)
    ...
    # ③ 核心循环：每条轨迹解析后，把 5 类内容各自包成 LangChain Document
    for task in combined_history:
        # task 本身也是一个 Document（task_similarity 策略的检索单元）
        self.docs.append(Document(page_content=..., metadata={'type': 'task', 'task': task, ...}))
        for i, traj in enumerate(combined_history[task]):
            cleaned_traj = Trajectory(...)            # 解析三流
            # ↓ 五类内容全量入库：action/thought/step/reflection 各自成 Document
            self.docs.extend([Document(page_content=action, metadata={'type': 'action', ...})
                              for action in cleaned_actions])
            ...
            # ↓ 反查表：每种内容 → (task, i)。检索命中"一条思考"→ 找回"整条成功轨迹"给 LLM 当 fewshot
            for thought in cleaned_thoughts:
                self.keys2task['thought'][thought] = (task, i)
```

**【论文对应】** §3.2 ExpeL 的"经验库"= 五类粒度混存的向量库——**细粒度命中、粗粒度使用**（用一条 thought 检索，但喂给 LLM 的是整条轨迹）。

**【我们的实现】** 我们的 `experiential_store` 只有一级（教训文本即条目），因为作战教训本身就是"提炼后的产物"，无需再从轨迹反查。**差异是设计而非简化**：ExpeL 面向"轨迹复用"（要完整示范），我们面向"教训复用"（一句话就够）。

---

## 3. `agent/expel.py::update_dynamic_prompt_components()` —— 推理时召回（最核心）

```python
def update_dynamic_prompt_components(self, reset=False):
    if self.training or self.fewshot_strategy == 'none':
        return                     # 训练阶段不检索（先攒经验，后用经验——两阶段分离）

    def filtered_vectorstore(fewshot_strategy, docs):
        # ① 按策略选"用哪类内容检索"：task_similarity 就只留 type=task 的 Document
        strat2filter = {'task_similarity': 'task', 'step_similarity': 'step',
                        'reflection_similarity': 'reflection', ...}
        subset_docs = list(filter(lambda doc: doc.metadata['type'] == strat2filter[...], docs))
        # ② webshop 特例：过滤掉"无效动作/思考空转/点击太少"的脏轨迹——数据清洗内嵌在检索里
        ...
        return FAISS.from_documents(filtered_subset_docs, self.embedder)  # 建索引

    def topk_docs(queries, query_type):
        # ③ 多取一倍再筛（buffer_retrieve_ratio）：k * 2 个候选 → 过滤后保证够数
        fewshot_docs = self.vectorstore.similarity_search(queries[query_type],
                                      k=self.num_fewshots * self.buffer_retrieve_ratio)
        # ④ 可选重排器（三种）：
        #    'len'   → 按轨迹长度降序（优先喂长示范？——其实是防超长的反向处理）
        #    'thought' → 用"当前思考"与候选轨迹的 thoughts 再算一次余弦重排（二次精排！）
        #    'task'  → 同理用任务相似度重排
        ...
        # ⑤ 逐条过滤：超 max_fewshot_tokens 的丢 / 与当前任务相同的丢（防泄漏）/ 已选过的任务丢（去重）
        for fewshot_doc in fewshot_docs:
            idx, shortest_fewshot = sorted(..., key=lambda x: len(x[1]))[0]  # 同任务取最短轨迹
            if self.token_counter(shortest_fewshot) > self.max_fewshot_tokens or \
               self.task == fewshot_doc.metadata['task'] or ...:
                continue
            fewshots.append(...task + '\n' + shortest_fewshot)   # 任务+轨迹拼成 fewshot
        return fewshots

    self.setup_vectorstore()                       # 每次评测重建索引（经验可能又多了）
    self.vectorstore = filtered_vectorstore(...)
    # ⑥ 用"当前任务 + 最近思考"双 query 检索（queries dict：task/thought 两个键）
    if self.prompt_history == []:
        queries = {'task': self.step_stripper(...)}    # 第一轮：只有任务可查
    else:
        trajectory = Trajectory(...)                   # 后续轮：把已完成轨迹也编进去查
```

**【论文对应】** §3.3 "test-time recall"——论文的卖点：**推理时**把"相似任务的成功轨迹 + 提炼的 insights"注入 prompt，性能随经验积累一致上升（Figure 5 的上升曲线就是这段代码跑出来的）。

**【我们的实现】** 对应 `memsys/retrieval/hybrid.py::retrieve()`：同样是"top_k*2 多取再筛"，但我们融合三路（vector/bm25/sql）而非单路 FAISS + 重排器；`answer_memory_ids` 回填对应它的"命中可追溯"（我们更严格——直接挂在 QueryItem 上）。

---

## 4. `insight_extraction.py` —— 从成败对比中提炼经验（阶段②）

```python
@hydra.main(version_base=None, config_path="configs", config_name="insight_extraction")
def main(cfg: DictConfig) -> None:
    # ① 配置驱动：hydra 管理（configs/insight_extraction.yaml）——所有 prompt 模板、
    #    模型、benchmark 参数都外置，复现实验只改 yaml
    ...
    # 核心思想（在 agent/expel.py 的 create_rules/extend_rules 里实现）：
    #   - success_critique:  对比多条成功轨迹 → 抽"成功模式"
    #   - failure_critique:  成功 vs 失败对比   → 抽"失败原因"
    #   - 规则去重合并：LLM 把新抽的 rule 与已有 rules 合并（max_num_rules 封顶）
```

**【论文对应】** §3.2 insight extraction：LLM 看到的是**成对/成组的轨迹对比**（不是单条）——"对比"是提炼质量的关键，这也是它比 Reflexion（单轨迹反思）更强的原因。

**【我们的实现】** 我们的 `evolve_from_review()` 只做单次复盘抽取（无跨场次对比）；**升级方向明确**：攒 N 场后做"成功场次 vs 失败场次"对比提炼——ExpeL 的 `create_rules` 就是现成参考。

---

## 5. 可直接搬走的三件事

1. **buffer_retrieve_ratio（多取再筛）**：`experiential_store.search()` 已采用（top_k*2 → 重排截断）；
2. **命中反查整条**（keys2task）：我们的 `merged_from` 是它的溯源版；
3. **脏数据过滤内嵌检索**（webshop 特例）：作战轨迹入库前也应滤掉"无效动作场次"。

> **跑通它**：`configs/` 改 OPENAI_API_KEY → `python train.py` → `python insight_extraction.py` → `python eval.py`（ALFWorld 最易跑）。
