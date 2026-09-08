# ============================================================================
# ExpeL: agent/expel.py（核心方法节选）【赛题③逐行注释版】
# ============================================================================
# 【论文定位】arXiv 2308.10144 §3.2/3.3：经验库构建（setup_vectorstore）
#   与推理时召回（update_dynamic_prompt_components）——ExpeL"越用越强"的引擎室。
#
# 【本文件是节选】完整文件 700+ 行（大量 hydra 配置胶水），只注释三个灵魂方法；
#   原文件在 paper_code/03_记忆检索/ExpeL/agent/expel.py（本地 clone 才有，
#   用 scripts/download_paper_code.py --only ExpeL 拉取）。
#
# 【我们的实现对照】
#   setup_vectorstore          → memsys/long_term/experiential_store.py::add()
#   update_dynamic_prompt...   → memsys/retrieval/hybrid.py::retrieve()
#   parse_rules / update_rules → memsys/evolution/memory_evolution.py::evolve_from_review()
# ============================================================================

# ----------------------------------------------------------------------------
# ① setup_vectorstore —— 把历史经验（成功轨迹+fewshots）灌进检索池
# ----------------------------------------------------------------------------
def setup_vectorstore(self) -> None:
    # 反查表：{粒度: {内容: (所属task, 第几条轨迹)}}
    # 用途：检索命中"一条 thought"时，能反查回"整条成功轨迹"喂给 LLM
    # 【我们的对照】memsys 的 merged_from（合并来源）就是这个思想的溯源版
    self.keys2task = {'thought': {}, 'task': {}, 'step': {}, 'reflection': {}, 'action': {}}
    self.docs = []          # LangChain Document 池（FAISS 的原料）

    # 合并两个来源：①训练阶段自主收集的成功轨迹 ②人工 fewshots
    # 【论文 §3.2】"经验 = 自主收集 + 种子示范"——不是从零冷启动
    combined_history = dict(self.succeeded_trial_history)

    if isinstance(self.all_fewshots, list):
        for fewshot in self.all_fewshots:
            # 不同 benchmark 的 fewshot 格式不同：hotpotqa/fever 第一行是 task，
            # webshop 前两行是 task——切法硬编码（工程债，但可读）
            if self.benchmark_name in ['hotpotqa', 'fever']:
                task = fewshot.split('\n')[0]
                trajectory = '\n'.join(fewshot.split('\n')[1:])
            elif self.benchmark_name == 'webshop':
                task = '\n'.join(fewshot.split('\n')[:2])
                trajectory = '\n'.join(fewshot.split('\n')[2:])
            # 把 fewshot 也包装成 Trajectory（与自主收集的同构——统一处理）
            cleaned_traj = Trajectory(
                task=self.remove_task_suffix(task),
                trajectory=trajectory,
                reflections=[],
                splitter=self.message_splitter,
                identifier=self.identifier,
                step_splitter=partial(self.message_step_splitter,
                                      stripper=self.step_stripper),
            )
            combined_history.update({task: [cleaned_traj]})

    # 核心循环：每条轨迹 → 解析 → 五类粒度各自成 Document
    for task in combined_history:
        if combined_history[task] != []:
            # task 本身也是一个 Document（task_similarity 策略的检索单元）
            # metadata 三件套：type(粒度)/task(反查键)/env_name(跨环境隔离)
            self.docs.append(Document(
                page_content=self.remove_task_suffix(task),
                metadata={'type': 'task', 'task': task,
                          'env_name': get_env_name_from_task(task, self.benchmark_name)}))
        for i, traj in enumerate(combined_history[task]):
            cleaned_traj = Trajectory(...)          # 三流解析（见 episode.py 注释）
            cleaned_thoughts = cleaned_traj.thoughts
            cleaned_steps = cleaned_traj.steps
            cleaned_reflections = cleaned_traj.reflections
            cleaned_actions = cleaned_traj.actions
            # ↓ 五类内容全量入库：每种粒度都能被独立检索到
            self.docs.extend([Document(page_content=action,
                             metadata={'type': 'action', 'task': task, ...})
                             for action in cleaned_actions])
            self.docs.extend([Document(..., {'type': 'thought', ...}) for thought in cleaned_thoughts])
            self.docs.extend([Document(..., {'type': 'step', ...}) for step in cleaned_steps])
            if cleaned_reflections != []:
                self.docs.extend([Document(..., {'type': 'reflection', ...})
                                  for reflection in cleaned_reflections])
            # ↓ 反查表填充：命中片段 → 找回整条轨迹（"细粒度命中、粗粒度使用"）
            for thought in cleaned_thoughts:
                self.keys2task['thought'][thought] = (task, i)
            for step in cleaned_steps:
                self.keys2task['step'][step] = (task, i)
            ...
    self.combined_history = combined_history


# ----------------------------------------------------------------------------
# ② update_dynamic_prompt_components —— 推理时召回（论文核心卖点）
# ----------------------------------------------------------------------------
def update_dynamic_prompt_components(self, reset: bool = False):
    if reset:
        ReactAgent.update_dynamic_prompt_components(self)
        return
    # 训练阶段不检索！——两阶段分离：先攒经验（train），后用经验（eval）
    if self.training or self.fewshot_strategy == 'none':
        return

    def filtered_vectorstore(fewshot_strategy: str, docs: List[Document]):
        """按策略建索引：task_similarity 只留 type=task 的 Document…"""
        strat2filter = {
            'task_similarity': 'task', 'step_similarity': 'step',
            'reflection_similarity': 'reflection',
            'thought_similarity': 'thought', 'action_similarity': 'action'
        }
        subset_docs = list(filter(
            lambda doc: doc.metadata['type'] == strat2filter[fewshot_strategy]
            and doc.metadata['env_name'] == self.env.env_name,  # 只在本环境的经验里检索
            docs))
        # webshop 特例：过滤脏轨迹（无效动作/空思考/点击太少）——
        # 【值得学】数据清洗内嵌在检索管道里，而非预处理一次性做完
        if self.benchmark_name == 'webshop':
            filtered_subset_docs = []
            for doc in subset_docs:
                trajectory = self.combined_history[doc.metadata['task']][0].trajectory
                if ('Observation: Invalid action!' not in trajectory
                        and 'think[]' not in trajectory
                        and len(trajectory.split('Observation: You have clicked')) >= 3):
                    filtered_subset_docs.append(doc)
        else:
            filtered_subset_docs = subset_docs
        return FAISS.from_documents(filtered_subset_docs, self.embedder)

    def topk_docs(queries: Dict[str, str], query_type: str):
        """多取再筛 + 可选重排 + 三重过滤，产出最终 fewshot 列表"""
        # 【我们的对照】experiential_store.search() 的 top_k*2 就是抄这里
        fewshot_docs = self.vectorstore.similarity_search(
            queries[query_type], k=self.num_fewshots * self.buffer_retrieve_ratio)

        if self.fewshot_strategy == 'random':
            random.shuffle(fewshot_docs)   # 随机基线（消融对照组）

        fewshots = []
        current_tasks = set()   # 去重：同一任务的多条轨迹只取一条

        # ---- 可选 reranker（二次精排）----
        # 'none'  : 不重排
        # 'len'   : 按轨迹长度排序（控制 token 预算的手段）
        # 'thought': 用"当前思考"与候选轨迹的 thought 再算一次余弦重排——
        #            【精髓】一轮检索用 task，二轮精排用 thought（越走越细）
        # 'task'  : 同理，用任务相似度重排
        if self.reranker == 'none' or (self.reranker == 'thought'
                                       and queries['thought'] == ''):
            fewshot_docs = list(fewshot_docs)
        elif self.reranker == 'len':
            fewshot_docs = list(sorted(fewshot_docs,
                                       key=fewshot_doc_token_count, reverse=True))
        elif self.reranker == 'thought' and queries['thought'] != '':
            fewshot_tasks = set([doc.metadata['task'] for doc in fewshot_docs])
            subset_docs = list(filter(
                lambda doc: doc.metadata['type'] == 'thought'
                and doc.metadata['env_name'] == self.env.env_name
                and doc.metadata['task'] in fewshot_tasks, list(self.docs)))
            fewshot_docs = sorted(subset_docs, key=lambda doc: cosine(
                self.embedder.embed_query(doc.page_content),
                self.embedder.embed_query(queries['thought'])))
        ...

        # ---- 三重过滤 + 装配 ----
        for fewshot_doc in fewshot_docs:
            # 同一任务的多条轨迹里挑最短的（token 经济学）
            idx, shortest_fewshot = sorted(
                enumerate([traj.trajectory
                           for traj in self.combined_history[fewshot_doc.metadata['task']]]),
                key=lambda x: len(x[1]))[0]
            # 过滤①：超 max_fewshot_tokens 的丢（预算硬约束）
            # 过滤②：与当前任务完全相同的丢（防"背答案"泄漏）
            # 过滤③：已选过同任务的丢（多样性）
            if (self.token_counter(shortest_fewshot) > self.max_fewshot_tokens
                    or self.task == fewshot_doc.metadata['task']
                    or fewshot_doc.metadata['task'] in current_tasks):
                continue
            # 装配：任务描述 + 最短轨迹 → 一条 fewshot 示例
            fewshots.append(
                self.combined_history[fewshot_doc.metadata['task']][idx].task
                + '\n' + shortest_fewshot)
            current_tasks.add(fewshot_doc.metadata['task'])
            if len(fewshots) == self.num_fewshots:
                break
        return fewshots

    # 每次评测重建索引（经验可能在训练后更新过——幂等）
    self.setup_vectorstore()
    self.vectorstore = filtered_vectorstore(
        self.fewshot_strategy
        if self.fewshot_strategy not in ['rotation', 'task_thought_similarity']
        else 'task_similarity', docs=list(self.docs))

    # ---- 双 query 构造：第一轮只有 task 可查；后续轮把"已完成轨迹"也编进去 ----
    # 【我们的对照】QueryItem.query_text 单 query；ExpeL 的 queries dict 是
    # {task, thought} 双查询——思想一致："查询要带着上下文状态"
    if self.prompt_history == []:
        queries = {'task': self.step_stripper(
            self.remove_task_suffix(self.task), step_type='task')}
    else:
        history = self.log_history(include_task=False)
        trajectory = Trajectory(...)   # 把当前进行中的轨迹解析后作为查询源
        ...


# ----------------------------------------------------------------------------
# ③ parse_rules / update_rules —— insight 提炼的规则合并（阶段②的收尾）
# ----------------------------------------------------------------------------
def parse_rules(llm_text):
    """从 LLM 输出文本中解析出规则操作列表。
    LLM 按 ['OPERATION: rule text'] 格式输出，这里正则抽取——
    【我们的对照】OpenAICompatibleClient.extract_memory_ops 的正则截取
    JSON 同构；工程上更稳的做法是 MemSkill 用的 json_repair 库。"""

def update_rules(rules, operations, list_full=False):
    """规则合并：新规则与已有规则去重合并，每条规则带计数（被采纳次数）。
    【论文 §3.2】insights 随经验积累不断精炼——不是append-only，
    而是合并去重后保留 top-N（max_num_rules 封顶）。
    【我们的对照】evolution.write() 的 θ 查重 + merge() 就是它的简化版；
    我们额外加 merged_from 溯源（ExpeL 无此设计）。"""
