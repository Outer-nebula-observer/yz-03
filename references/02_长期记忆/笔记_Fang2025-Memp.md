# 论文精读（深化版）：Mem[p] — Exploring Agent Procedural Memory

> - **作者 / 机构**：Runnan Fang、Yuan Liang、Shuofei Qiao、Ningyu Zhang（浙江大学 & 阿里巴巴）
> - **发表**：arXiv 2025（2508.06433）
> - **对应**：`references/02_长期记忆/Fang2025-Memp.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/zjunlp/MemP

## 一句话总结

给 agent 装"可学习、可更新、终身"的程序性记忆：把历史轨迹蒸馏成**细粒度逐步指令 + 高层脚本抽象**，配套 **Build / Retrieve / Update** 三策略与动态更新纪律——TravelPlanner 与 ALFWorld 上随记忆精化成功率与效率持续提升，强模型记忆可迁移给弱模型。

## 1. 程序性记忆三操作框架（Build/Retrieve/Update）

```
任务轨迹 τ=(τ1..τT) 与奖励 r
  └─① Build（构建）：builder B 把每个 (τt, rt) 蒸馏为程序性记忆 mp[t] = B(τt, rt)
       · 形成程序性记忆库 Mem = {mp[1]..mp[T]}
  └─② Retrieve（检索）：新任务 tnew → 召回最相似任务的记忆
       · mretrieved = argmax_{mp[i]∈Mem} S(tnew, ti)
       · 用任务 embedding 的余弦相似度（向量模型 φ）
       · 实验对比多种 key 构建策略（query-vector matching / keyword-vector matching）
  └─③ Update（更新）：随任务增加，动态 增/删/改/查
       · M(t+1) = U(M(t), E(t), τt)   （E(t)=执行反馈：成功/失败/性能）
       · U = Add(Mnew) ⊖ Del(Mobs) ⊕ Update(Mest)
            Add 新记忆 / Del 过时记忆 / Update 估计修正
       · 动态纪律：持续更新、纠正、弃用，与最新经验同步
```

**两级抽象**：细粒度逐步指令（step-by-step）+ 高层脚本式抽象（script-like）——蒸馏出两种粒度的程序性知识。

## 2. 关键结果

| 环境 | 效果 |
|---|---|
| TravelPlanner | 随记忆精化成功率与效率持续上升，高于无/静态记忆基线 |
| ALFWorld | 同上；程序性记忆显著提升新任务泛化 |
| 记忆迁移 | 强模型构建的记忆→弱模型使用，仍有大幅收益（记忆可移植） |

## 3. 代码索引

- 官方：https://github.com/zjunlp/MemP
- 本仓库语境：**"经验→程序"路线落地样本**；复现位 `paper_code/长期记忆/`。

## 4. 优点 / 局限（深化）

- **优点**：明确区分声明性 vs 程序性记忆；Build/Retrieve/Update 三策略与赛题"写入/检索/进化"一一对应，可直接当模块接口设计参照；记忆可跨模型迁移是亮点；动态更新纪律（增/删/改）量化。
- **局限**：程序抽象依赖 LLM 蒸馏质量；仓库以文本/代码为主，跨长程、多模态待验证；更新纪律（何时纠正/弃用）的量化依据仍需手工规则；两级粒度的取舍未给明确阈值。

## 5. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 程序性记忆层 | 经验记忆再细分：经验教训（Reflexion 文本）+ 可执行策略/流程（Memp 程序） |
| Build/Retrieve/Update 三策略 | **与赛题"写入/检索/进化"三模块一一对应**，模块接口设计参照 |
| Update=Add⊖Del⊕Update | 对应进化"合并去重、遗忘淘汰"，佐证"进化=写+改+删"闭环 |
| 记忆跨模型迁移 | 论证记忆系统对小模型部署的价值（低成本迁移） |

---
*经验记忆三件套之一；另见 `笔记_Shinn2023-Reflexion.md`、`笔记_Wang2023-Voyager.md`。*

## 代码实证（结合 paper_code/）

- 仓库：`paper_code/02_长期记忆/MemP/`
- 看 `ProcedureMem/`（Build/Retrieve/Update 三策略实现）+ `requirements.txt`。
- 赛题用法：程序性记忆三操作接口设计的参照。