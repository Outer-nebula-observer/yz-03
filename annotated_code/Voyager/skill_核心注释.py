# ============================================================================
# Voyager: voyager/agents/skill.py 核心节选【赛题③精读注释版】
# ============================================================================
# 【论文定位】arXiv 2305.16291 §2.2：
#   技能库 = "描述 embedding 检索 + 可执行代码复用"——
#   key 是 GPT-3.5 生成的事件描述向量，value 是 JS 代码本体。
#
# 【为什么精读】赛题③"经验→可执行策略"路线（Memp 程序记忆）的
#   工程原型；add_new_skill 的"版本化覆盖"与断言同步是
#   向量库与本地状态双存储的教科书处理。
#
# 【我们的实现对照】
#   skills{name: {code, description}}  → experiential_store._entries
#   vectordb.add_texts(描述)           → vindex.add(id, content+source)
#   retrieve_skills 返回代码本体       → 我们返回教训文本（进阶→预案代码）
#   断言 count==len(skills)            → 我们无同步校验（值得补）
# ============================================================================

import os
import U  # utils：文件读写助手


class SkillManager:
    """技能库：chroma 向量库（检索）+ skills dict（本体）双存储。

    双存储的必要性：向量库只存"描述向量"（检索键），代码本体在
    dict + 磁盘 .js 文件（执行件）——检索与执行的解耦。
    """

    def add_new_skill(self, info):
        """新增技能：生成描述 → 版本检查 → 三处同步写入。

        ① 领域过滤：'Deposit useless items' 任务不入库——
        一次性琐碎任务建技能是浪费（不是所有经验都值得沉淀）。
        【作战对应】"例行报告格式"这类无需技能化的操作不进经验库。
        """
        if info["task"].startswith("Deposit useless items into the chest at"):
            return

        program_name = info["program_name"]
        program_code = info["program_code"]
        # ② 描述生成：用 GPT-3.5 给代码写"事件描述"（cheap 模型干杂活）
        #    描述质量决定检索质量——描述写的是"这技能干什么/何时用"
        skill_description = self.generate_skill_description(program_name, program_code)

        # ③ ★ 版本化覆盖：同名技能已存在 → 不覆盖，存 V2/V3...
        #    "already exists. Rewriting!" —— 旧版向量删除，但旧代码文件
        #    保留为 nameV2.js（可回溯），新版挂原名。
        #    【设计价值】技能演化可回放（类似我们 merged_from 溯源）
        if program_name in self.skills:
            self.vectordb._collection.delete(ids=[program_name])  # 删旧向量
            i = 2
            while f"{program_name}V{i}.js" in os.listdir(f"{self.ckpt_dir}/skill/code"):
                i += 1
            dumped_program_name = f"{program_name}V{i}"   # 旧文件改名保留
        else:
            dumped_program_name = program_name

        # ④ 三处同步写入：向量库（描述+id）/ skills dict / 磁盘 .js 文件
        self.vectordb.add_texts(
            texts=[skill_description],          # 检索键 = 描述文本
            ids=[program_name],
            metadatas=[{"name": program_name}],
        )
        self.skills[program_name] = {
            "code": program_code,               # 执行件 = 代码本体
            "description": skill_description,
        }
        # ⑤ ★ 断言同步：向量库条数必须 == skills 条数
        #    双存储的命门是同步——一旦失配，检索命中但取不到代码
        #    （或反之）。这个 assert 是最便宜的防御。
        #    【值得搬】我们 vindex 与 _entries 的同步没校验，建议补：
        #    assert len(self.vindex) == len(self._entries)
        assert self.vectordb._collection.count() == len(self.skills), \
            "vectordb is not synced with skills.json"

        U.dump_text(program_code, f"{self.ckpt_dir}/skill/code/{dumped_program_name}.js")

    def retrieve_skills(self, query):
        """按 query 召回 top-k 技能，返回**代码本体**（非描述）。

        k = min(库容, retrieval_top_k)：库空/不足时自动收缩——
        防止 chroma 在 k>库容时报错（防御式取参）。
        流程：query → 向量相似 → 命中描述 → 从 dict 取 code。
        【对照我们】experiential_store.search() 返回 entry（含 content）；
        Voyager 强调"取回的是可执行物"——检索只是手段，复用才是目的。
        """
        k = min(self.vectordb._collection.count(), self.retrieval_top_k)
        if k == 0:
            return []
        docs_and_scores = self.vectordb.similarity_search_with_score(query, k=k)
        skills = []
        for doc, _ in docs_and_scores:
            # metadata['name'] 反查 dict 拿代码——描述命中，代码出场
            skills.append(self.skills[doc.metadata["name"]]["code"])
        return skills

# ============================================================================
# 【给基础开发者的三条读懂线索】
# 1) 技能库 = 检索键（描述向量）与执行件（代码）分离——
#    检索质量取决于**描述**写得好不好，与代码质量无关：
#    给代码写"何时用我"的描述是被低估的关键工序；
# 2) 版本化覆盖（V2/V3 保留旧版）让技能演化可回溯——
#    比直接覆盖多花一点存储，换来"新技能退化时能回滚"；
# 3) assert 同步校验是双存储的救命符——失配是静默 bug，
#    在写入处 assert 比在检索处 try-except 便宜得多。
# ============================================================================
