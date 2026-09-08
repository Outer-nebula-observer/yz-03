# 论文精读（深化版）：MemoryBank — Enhancing Large Language Models with Long-Term Memory

> - **作者 / 机构**：Wanjun Zhong、Lianghong Guo 等（中山大学 / 哈工大 / KTH）
> - **发表**：arXiv 2023（2305.10250），AAAI 2024
> - **对应**：`references/02_长期记忆/Zhong2023-MemoryBank.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/zhongwanjun/MemoryBank-SiliconFriend

## 一句话总结

面向长期陪伴的 LLM 记忆机制：**DPR 双塔检索（FAISS）+ 艾宾浩斯遗忘曲线更新（R=e^(-t/S)）+ 每日高级摘要 + 用户画像洞察**，落地为 AI 陪伴机器人 SiliconFriend——能共情、能召回、能理解用户性格。

## 1. 三组件

```
对话流
  └─① 记忆存储（Memory Storage）：每轮对话 + 事件摘要 = 记忆片 m，带时间/重要性等元数据
  └─② 记忆检索（Memory Retrieval）：DPR 双塔
       · 每条 m 经 encoder E(·) → 向量 hm，FAISS 索引
       · 当前对话上下文 c → hc 作 query，搜最相关记忆
  └─③ 记忆更新（Memory Updating）：艾宾浩斯遗忘曲线
       R = e^(-t/S)   R=留存率, t=距上次时间, S=记忆强度
       · S 离散值，首次提及初始化为 1
       · 被召回时 S+=1、t 重置为 0 → 更不易忘（间隔效应/spacing effect）
       · 长期交互产出 每日事件高级摘要 + 用户性格画像洞察
```

## 2. 艾宾浩斯遗忘曲线（核心机制，深化）

三条原则（论文明确）：
1. **遗忘速率**：记忆留存随时间下降，除非有意识复习；
2. **时间与衰减**：曲线初期陡（几小时/几天内大量遗忘），后期放缓；
3. **间隔效应**：定期复习可重置曲线使其变缓，提升留存。

**简化模型**：`R = e^(-t/S)`，S 离散（init 1，召回 +1 并重置 t=0）。作者注明这是"探索性高度简化模型"——真实记忆更复杂、因人/因信息类型而异。

## 3. 关键结果

| 方面 | 效果 |
|---|---|
| 长期陪伴 | SiliconFriend 能召回相关记忆、理解用户性格、共情回答 |
| 遗忘机制 | 比全存/全忘更接近人类、检索更聚焦（消融验证"有/无遗忘"） |
| 模型兼容 | ChatGPT（闭源）与 ChatGLM（开源）均可接入 |

## 4. 代码索引

- 官方：https://github.com/zhongwanjun/MemoryBank-SiliconFriend
- 本仓库语境：**摘要式事实记忆 + 遗忘机制代表作**；复现位 `paper_code/长期记忆/`。

## 5. 优点 / 局限（深化）

- **优点**：首次把艾宾浩斯遗忘曲线引入 LLM 记忆更新——遗忘有心理学依据；摘要 + 画像两档抽象层次清晰；DPR+FAISS 检索工程成熟；可配闭源/开源模型。
- **局限**：遗忘策略是**手工规则**（时间衰减+重要性），非学习式；检索以关键词/简单语义为主，未做向量检索深度评测；面向单用户陪伴场景，多任务/复杂推理覆盖有限；遗忘模型高度简化（作者自承）。

## 6. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 艾宾浩斯曲线 R=e^(-t/S) | **赛题"遗忘"机制心理学依据**：时间衰减+重要性打分（`docs/04` 避坑点 4 首选） |
| S 召回 +1、t 重置 | "命中强化"机制：被召回的记忆更不易遗忘（间隔效应） |
| 每日摘要 + 用户画像 | 对应"抽象"进化操作：低层对话→高层摘要→用户/任务画像 |
| 召回+更新闭环 | 支撑"检索只读、进化只写"解耦；更新发生在对话后 |
| 消融"有/无遗忘" | 赛题"遗忘量化"消融的文献范式 |

---
*事实记忆参考；结构化/时序方案见 `笔记_Rasmussen2025-Zep.md`。*

## 论文核心代码（paper_code 索引）

- 仓库：`paper_code/02_长期记忆/MemoryBank-SiliconFriend/`
- `memory_bank/`：DPR 双塔编码 + FAISS 检索 + 遗忘更新（R=e^(-t/S) 的工程实现）；`README_cn.md` 中文说明；`eval_data/` 评测数据。

## 我们的实现（memsys）

- **思路**：艾宾浩斯完整落地为"条目属性(S,t) + 两方法(retention/mark_recalled) + 批量淘汰(forget)"三层；
- **代码索引**：`memsys/schema.py::retention()/mark_recalled()` + `memsys/evolution/memory_evolution.py::forget()`。

## 代码详解（R=e^(-t/S) 的三层落地）

```python
# ① schema.py::retention() —— 留存率是条目自身属性（随时可查）
import math
def retention(self, now=None) -> float:
    t = now - (self.last_recalled_at or self.timestamp)   # 距上次召回的时间
    return math.exp(-t / max(self.decay_strength, 1e-6))  # R = e^(-t/S)

# ② schema.py::mark_recalled() —— 间隔效应：命中即强化
def mark_recalled(self):
    self.recall_count += 1
    self.decay_strength += 1.0        # S+1：越常用越难忘
    self.last_recalled_at = time.time()  # t 重置

# ③ evolution.py::forget() —— 批量淘汰（遗忘是操作，不是属性）
if e.importance >= self.protected_importance: continue  # 保护线：失败教训永不删
if e.retention(now) < self.forget_threshold: store.remove(cid)
```
> 设计决策：为什么 retention 放 schema 而 forget 放 evolution——**属性与操作分离**，遗忘策略可换（衰减/重要性/冲突检测三选一，避坑点 4）而数据模型不动。

## 代码实证（结合 paper_code/）

- 仓库：`paper_code/02_长期记忆/MemoryBank-SiliconFriend/`
- 看 `memory_bank/`（DPR+FAISS 检索 + 艾宾浩斯遗忘实现）、`utils/`、`eval_data/`；有 `README_cn.md` 中文说明。
- 赛题用法：遗忘模块（R=e^(-t/S)）+ 每日摘要可直接仿写。