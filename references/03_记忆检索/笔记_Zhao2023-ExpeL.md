# 论文精读（深化版）：ExpeL — LLM Agents Are Experiential Learners

> - **作者 / 机构**：Andrew Zhao、Daniel Huang、Gao Huang 等（清华大学自动化系 & 计算机系 BNRist）
> - **发表**：AAAI 2024（arXiv 2308.10144）
> - **对应**：`references/03_记忆检索/Zhao2023-ExpeL.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/LeapLabTHU/ExpeL

## 一句话总结

"体验式学习"agent：不微调参数，在训练任务上自主积累轨迹，用自然语言提炼经验（成功/失败模式），推理时从 Faiss 向量库召回相似成功轨迹 + 提炼经验辅助决策——性能随经验积累持续提升，且具涌现与迁移能力。

## 1. 核心思想：learning from experience without gradient updates

对决策任务微调 LLM 资源密集、损害泛化，且 GPT-4/Claude 权重封闭不可微调。ExpeL 完全在**推理时学习**（类比学生先复习再考试）：从训练任务自主积累经验 → 提炼自然语言 insights → 测试时召回相似成功轨迹作 in-context 示例。

## 2. 技术路线（三阶段）

```
训练任务集
  └─① 经验收集（gather）：agent 自主执行任务，保存完整轨迹（成功+失败）
  └─② 知识提炼（extract）：对比成败轨迹 → 用自然语言提炼 insights/成功模式
  └─③ 经验库（Faiss 向量库：成功轨迹 + 提炼 insights）
       └─ 推理时：新任务 → 检索 Top-K 相似成功轨迹 + insights → 注入执行 prompt → 决策
```

**关键**：经验 = "成功轨迹（向量召回）+ 提炼 insights（自然语言）"双库；insights 跨任务复用；无需梯度更新。

## 3. 关键结果

| 环境 | 效果 |
|---|---|
| ALFWorld / WebShop | 随经验积累成功率持续提升，显著超 ReAct/Act 基线 |
| 通用决策（环境交互） | 表现可媲美需微调方法 |
| 涌现与迁移 | 跨任务经验复用与类比迁移能力 |

## 4. 代码索引

- 官方：https://github.com/LeapLabTHU/ExpeL
- 本仓库语境：**"经验库：向量检索 Top-K 成功轨迹"范式**，赛题经验记忆召回直系参照；复现位 `paper_code/记忆检索/`。

## 5. 优点 / 局限（深化）

- **优点**：免微调、"越用越强"；经验提炼为可读文本可解释；检索+提炼两段式召回质量高；跨任务泛化与迁移亮眼。
- **局限**：经验提炼依赖 LLM 归纳能力；向量检索对"任务相似度"敏感，差距大时召回质量降；**经验库无遗忘/更新机制**，长期积累过时经验（对新方案演进不敏感）——赛题须补进化。
- **启示**：其"无遗忘"恰是赛题要规避的反面教材。

## 6. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 成功轨迹 + 提炼经验双库 | 经验记忆存储形态：原始战例轨迹（向量）+ 提炼作战教训（摘要） |
| Faiss Top-K 检索 | 经验记忆检索基线实现（Recall@K 指标直接对齐） |
| 一致提升曲线 | 组会汇报"经验积累→性能提升"证据链（消融 G3） |
| 无遗忘局限 | 反面教材：赛题必须补"进化/遗忘"防过时经验 |
| 免微调推理时学习 | 对齐赛题"不可微调"约束下的经验沉淀路径 |

---
*与 SQL 符号检索（`笔记_Hu2023-ChatDB.md`）对照：向量近似 vs 符号精确，构成赛题混合检索双路。*

## 代码实证（结合 paper_code/）

- 仓库：`paper_code/03_记忆检索/ExpeL/`
- 三阶段流水线：`train.py`（经验收集）→ `insight_extraction.py`（提炼）→ `eval.py`（评测）。
- 看 `memory/episode.py`（轨迹存储）、`agent/{expel,react,reflect}.py`（三种 agent）、`envs/`（ALFWorld/WebShop）。
- 赛题用法：经验记忆"向量召回+提炼"基线实现，**代码最完整可直接改造**。

## 论文核心代码（paper_code 索引 · 带注释）

- 仓库：`paper_code/03_记忆检索/ExpeL/`

```python
# memory/episode.py::Trajectory（论文核心数据结构，加注释讲解）
class Trajectory:
    def __init__(self, task, trajectory, splitter, identifier, step_splitter,
                 embedder=None, reflections=None):
        self._task = task                 # 任务描述（检索时的 query 锚）
        self._trajectory = trajectory     # 完整轨迹文本（成功/失败都存）
        self._reflections = deepcopy(reflections)  # 轨迹附带的反思（Reflexion 复用）
        # 按 splitter/identifier 把轨迹解析成 observations/actions/thoughts 三流
        for line in splitter(self._trajectory):
            setattr(self, f'_{identifier(line)}s', ...)  # 动态分流到 _observations 等
        self._steps = step_splitter(...)  # 再聚合成 step（经验提炼的粒度）
        if embedder is not None:
            self._keys['task'] = [embedder(self.task)]   # 任务向量 = 检索键
            for step in self.steps:
                ...                        # 每个 step 也编向量（细粒度召回）
```
> 精髓：**一条轨迹 = 任务向量（粗检索键）+ step 向量（细召回键）+ 反思文本**——我们经验库的"content+source 联合编码"就是它的简化版。

## 我们的实现（memsys）

- **思路**：不做"轨迹三流解析"（MVP 无 ReAct 环境信号），保留"成功轨迹+提炼教训双形态"——原始复盘文本存 `content`，提炼产物即经验条目本身；
- **代码索引**：`memsys/long_term/experiential_store.py::search()`（Faiss Top-K 的 dict 版）。

## 代码详解（Top-K 召回 + 重要性加权 + 命中强化三合一）

```python
# experiential_store.py::search()（节选）
raw = self.vindex.search(query, top_k=top_k * 2)   # 多取一倍再重排（ExpeL 取 top-K 的工程细节）
for mid, cos in raw:
    e = self._entries.get(mid)
    # 融合分 = 0.8*语义相似 + 0.2*重要性（Reflexion：失败教训 importance 高 → 更易浮上来）
    score = 0.8 * cos + 0.2 * min(e.importance / 3.0, 1.0)
    e.mark_recalled()    # 艾宾浩斯命中强化：S+1（被用过的经验更难忘）
    results.append(RetrievedMemory(entry=e, score=score, route="vector"))
results.sort(key=lambda r: r.score, reverse=True)  # 加权重排后截断 top_k
```
> 与 ExpeL 差异：我们无 insights 独立库（提炼即写入经验库）；权重 0.8/0.2 是 G3 消融扫描点。