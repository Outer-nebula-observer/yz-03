# ============================================================================
# ExpeL: agent/expel.py 核心节选【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2308.10144 (AAAI'24 Oral)
#   §3.2 经验收集/提炼、§3.3 推理时召回（test-time recall）。
#   本文件是 ExpelAgent 主体：管理成功/失败轨迹库 + FAISS 检索 + prompt 动态组装。
#
# 【为什么精读】赛题③"经验记忆召回"的完整参照——我们的
#   experiential_store.py 是它的单级简化版；看懂它的"多粒度检索 +
#   命中反查整条轨迹"，就明白经验库该怎么组织。
#
# 【我们的实现对照】
#   setup_vectorstore（五类粒度入库）→  我们只入"教训文本"一级
#   topk_docs（多取再筛+重排）      →  我们 search() 的 top_k*2 同源
#   insert_before_task_prompt（注入规则）→ 我们 render() 的查询列表装载
#
# 注：原文件 743 行，节选四个关键方法，逻辑保持原序。
# ============================================================================

from langchain.vectorstores import FAISS
from langchain.schema import HumanMessage, Document
from scipy.spatial.distance import cosine
from memory import Trajectory


class ExpelAgent(ReflectAgent):
    # ------------------------------------------------------------------
    # 【方法 1】setup_vectorstore —— 把历史经验灌进 FAISS（L420-497）
    # ------------------------------------------------------------------
    def setup_vectorstore(self) -> None:
        # ① 反查表：内容片段 → (所属任务, 第几条轨迹)
        #    作用：检索命中"一条思考/一步"时，能反查回"整条成功轨迹"喂给 LLM
        #    【设计精髓】细粒度命中、粗粒度使用！
        self.keys2task = {'thought': {}, 'task': {}, 'step': {},
                          'reflection': {}, 'action': {}}
        self.docs = []

        # ② 合并经验源：自主收集的成功轨迹 + 人工 fewshot 示例
        #    （不同 benchmark 的 fewshot 切法不同：hotpotqa 首行是任务，
        #     webshop 前两行、alfworld 前三行——环境差异的适配代码）
        combined_history = dict(self.succeeded_trial_history)
        # fewshot 合并逻辑略（benchmark 差异适配代码）

        # ③ 核心循环：每条轨迹 → Trajectory 解析三流 → 五类内容各自成 Document
        for task in combined_history:
            if combined_history[task] != []:
                # 任务本身也是一个 Document（task_similarity 策略的检索单元）
                self.docs.append(Document(
                    page_content=self.remove_task_suffix(task),
                    metadata={'type': 'task', 'task': task,
                              'env_name': get_env_name_from_task(...)}))
            for i, traj in enumerate(combined_history[task]):
                cleaned_traj = Trajectory(task=..., trajectory=traj.trajectory,
                                          reflections=list(traj.reflections),
                                          splitter=self.message_splitter,
                                          identifier=self.identifier,
                                          step_splitter=...)
                # ↓ 五类内容全量转 Document：metadata['type'] 标粒度
                #   action/thought/step/reflection 各自成条 —— 混粒度入库
                # ↓ 五类内容各自 extend（action/thought/step/reflection 同构，原文全列）
                self.docs.extend([Document(page_content=action,
                                  metadata={'type': 'action', 'task': task})
                                  for action in cleaned_traj.actions])
                # thought/step/reflections 的 extend 结构同上（此处省略重复样板）

                # ↓ 填反查表：这条思考/步骤属于哪个任务的哪条轨迹
                #   （之后 topk_docs 命中片段 → keys2task 查回整条 → 当 fewshot）
                for thought in cleaned_thoughts:
                    self.keys2task['thought'][thought] = (task, i)
                # step/reflection/action 同构填表（略）
        self.combined_history = combined_history

    # ------------------------------------------------------------------
    # 【方法 2】update_dynamic_prompt_components —— 推理时召回（L498 起）
    #     论文核心：test-time recall，性能随经验积累上升的代码来源
    # ------------------------------------------------------------------
    def update_dynamic_prompt_components(self, reset: bool = False):
        if reset:
            ReactAgent.update_dynamic_prompt_components(self)
            return
        # 训练阶段不检索——两阶段分离：先攒经验（train），后用经验（eval）
        if self.training or self.fewshot_strategy == 'none':
            return

        # ---- 嵌套函数 ①：按策略过滤 Document 子集，建 FAISS 索引 ----
        def filtered_vectorstore(fewshot_strategy, docs):
            # 策略 → 用哪类粒度的内容做检索键
            strat2filter = {'task_similarity': 'task',
                            'step_similarity': 'step',
                            'reflection_similarity': 'reflection',
                            'thought_similarity': 'thought',
                            'action_similarity': 'action'}
            subset_docs = list(filter(
                lambda doc: doc.metadata['type'] == strat2filter[...]
                and doc.metadata['env_name'] == self.env.env_name,  # 同环境才可比
                docs))
            # webshop 特例：滤掉"无效动作/思考空转/点击太少"的脏轨迹
            # —— 数据清洗内嵌在检索里（脏 fewshot 会教坏 LLM）
            if self.benchmark_name == 'webshop':
                filtered = []
                for doc in subset_docs:
                    trajectory = self.combined_history[doc.metadata['task']][0].trajectory
                    if ('Observation: Invalid action!' not in trajectory
                            and 'think[]' not in trajectory
                            and len(trajectory.split('Observation: You have clicked')) >= 3):
                        filtered.append(doc)
                subset_docs = filtered
            return FAISS.from_documents(subset_docs, self.embedder)

        # ---- 嵌套函数 ②：取 top-k fewshot（多取再筛 + 可选重排 + 三重过滤）----
        def topk_docs(queries, query_type):
            # (a) 多取一倍：k * buffer_retrieve_ratio 个候选
            #     为什么多取？后面要按长度/泄漏/去重过滤，取少了筛完不够数
            fewshot_docs = self.vectorstore.similarity_search(
                queries[query_type],
                k=self.num_fewshots * self.buffer_retrieve_ratio)

            # (b) 可选重排器（reranker 参数）：
            #     'none'    → 原序
            #     'len'     → 按轨迹长度排（控制 token 开销）
            #     'thought' → 用"当前最新思考"与候选轨迹的 thoughts
            #                 再算一次余弦 → 二次精排（更贴当前推理状态！）
            #     'task'    → 同理，用任务相似度重排
            if self.reranker == 'thought' and queries['thought'] != '':
                fewshot_tasks = set(d.metadata['task'] for d in fewshot_docs)
                subset = list(filter(
                    lambda doc: doc.metadata['type'] == 'thought'
                    and doc.metadata['task'] in fewshot_tasks, self.docs))
                fewshot_docs = sorted(subset, key=lambda doc: cosine(
                    self.embedder.embed_query(doc.page_content),
                    self.embedder.embed_query(queries['thought'])))

            # (c) 逐条过滤 + 拼装：
            #     - 超长丢弃（max_fewshot_tokens 封顶）
            #     - 与当前任务相同丢弃（防"答案泄漏"给 LLM 作弊）
            #     - 同任务只留最短轨迹（等价经验取最省 token 的版本）
            #     - 已选任务去重（fewshot 多样性）
            for fewshot_doc in fewshot_docs:
                idx, shortest = sorted(
                    enumerate([t.trajectory
                               for t in self.combined_history[fewshot_doc.metadata['task']]]),
                    key=lambda x: len(x[1]))[0]
                if (self.token_counter(shortest) > self.max_fewshot_tokens
                        or self.task == fewshot_doc.metadata['task']
                        or fewshot_doc.metadata['task'] in current_tasks):
                    continue
                fewshots.append(fewshot_doc.metadata['task'] + '\n' + shortest)
                current_tasks.add(fewshot_doc.metadata['task'])
                if len(fewshots) == self.num_fewshots:
                    break
            return fewshots

        # ---- 主流程：重建索引（经验可能更新了）→ 构造 query → 按策略检索 ----
        self.setup_vectorstore()
        self.vectorstore = filtered_vectorstore(self.fewshot_strategy, docs=list(self.docs))

        # 双 query 设计：第一轮只有 task 可查；
        # 后续轮把"当前轨迹的最新 thought/step/action"也编进 queries dict
        # → 检索锚随推理推进而演进（越走越像"找相似处境"而非"找相似任务"）
        if self.prompt_history == []:
            queries = {'task': self.step_stripper(self.remove_task_suffix(self.task),
                                                  step_type='task')}
        else:
            history = self.log_history(include_task=False)
            trajectory = Trajectory(task=..., trajectory=history, splitter=..., identifier=..., step_splitter=...)  # 已完成部分也解析成轨迹
            steps = self.message_splitter(trajectory.steps[-1])
            step_types = [self.identifier(step) for step in steps]
            # 步未完成（无 observation）→ 用上一步（检索锚的平滑处理）
            if 'observation' not in step_types and self.fewshot_strategy == 'step':
                steps = self.message_splitter(trajectory.steps[-2])
            queries = {
                'task': ...,
                'thought': '' if not trajectory.thoughts else \
                    self.step_stripper(trajectory.thoughts[-1], ...),
                'step': cleaned_step,
                'action': ...,
            }

        # 按策略路由（rotation：随步骤类型切换检索粒度——
        #   thought 阶段用 thought 查、observation 后用 step 查，动态适配）
        if self.fewshot_strategy == 'rotation':
            last_step_type = self.identifier(self.message_splitter(trajectory.trajectory)[-1])
            if self.prompt_history == [] or not trajectory.thoughts:
                self.fewshots = topk_docs(queries, 'task')
            elif last_step_type == 'thought':
                self.fewshots = topk_docs(queries, 'thought')
            elif last_step_type == 'observation':
                self.fewshots = topk_docs(queries, 'step')
        ...

    # ------------------------------------------------------------------
    # 【方法 3】insert_before_task_prompt —— 把规则/经验注入 prompt（L404）
    # ------------------------------------------------------------------
    def insert_before_task_prompt(self):
        # 训练期：走 ReflectAgent（反思模式——攒经验阶段）
        if self.training:
            return ReflectAgent.insert_before_task_prompt(self)
        # 评测期：把提炼出的 rules（insights）注入 system prompt
        # ——【对照我们的实现】controller.render() 里装载查询列表命中记忆，
        #    同为"把记忆变成 prompt 的一部分"，我们多了 provenance 溯源
        if not self.no_rules:
            self.prompt_history.append(
                self.rule_template.format_messages(rules=self.rules)[0])

# ============================================================================
# 【给基础开发者的三条读懂线索】
# 1) 经验库的本质 = "多粒度 Document + 反查表"：片段可检索，轨迹可反查；
# 2) 检索质量三件套：多取再筛（防过滤后不够）→ 重排（贴当前推理状态）
#    → 三重过滤（长度/泄漏/去重）——缺一个都会劣化 fewshot 质量；
# 3) queries dict 随步骤演进 = "检索锚动态化"：从"找相似任务"
#    进化到"找相似处境"，这是 rotation 策略的精髓。
# ============================================================================
