# 论文精读（深化版）：SCM — Enhancing Large Language Model with Self-Controlled Memory Framework

> - **作者 / 机构**：Bing Wang、Xinnian Liang、Jian Yang 等（北航 / 哈工大 / 字节跳动 AI Lab）
> - **发表**：Findings of ACL 2023（arXiv 2304.13343）
> - **对应**：`references/04_记忆进化/Liang2023-SCM.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/wbbeyourself/SCM4LLMs

## 一句话总结

让 LLM"自主控制"自己的记忆：**记忆流**存储 + **记忆控制器**决定"何时写入、何时读取、读什么"，即插即用接入任意指令跟随 LLM（无需改结构/微调）；自标注数据集覆盖长对话/书籍摘要/会议摘要三类任务。

## 1. 动机：LLM 忘历史信息

LLM 无法处理超长输入、丢失关键历史。SCM 用"自控记忆"框架增强长程记忆与召回，且**即插即用**——不修改结构、不微调，接入任意指令跟随 LLM。

## 2. 技术路线（三组件）

```
输入 → LLM Agent（主干，负责推理生成）
          ▲              │ 生成回答
  读取    │              │ 写入
  ┌───────┴──────────────▼──────────────┐
  │     记忆控制器（memory controller）       │
  │   · 决定何时执行写操作（是否有足够新信息要写）│
  │   · 决定何时读、读哪段（回答是否需查记忆） │
  └───────┬──────────────┬──────────────┘
     memory stream（记忆流：摘要化/关键信息存储）
       · flash memory（短期，联想当前上下文）
       · archived memory（长期，归档）
```

**核心**：控制器把"何时写、何时读、读什么"**显式化、可解释**；flash/archived 双层分层（短期联想 vs 长期归档）。

## 3. 关键结果

| 任务 | 效果 |
|---|---|
| 长程对话 | 检索召回率与回答信息量优于基线 |
| 书籍/会议摘要 | 超长输入下保持关键信息 |
| 即插即用 | 任意指令跟随 LLM 可直接接入（无需微调） |

## 4. 代码索引

- 官方：https://github.com/wbbeyourself/SCM4LLMs
- 本仓库语境：**"记忆控制器"范式代表**，赛题"短期↔长期调度控制器"蓝本；复现位 `paper_code/记忆进化/`。

## 5. 优点 / 局限（深化）

- **优点**：控制器把"何时写、何时读"显式化可解释；即插即用适配任何 LLM；flash/archived 双记忆分层清晰；自标注三任务数据集可复现。
- **局限**：控制器决策依赖 LLM 自省，规则隐式；记忆流以文本摘要为主，无结构化/图谱；对"主动遗忘/合并去重"未系统展开（侧重读写调度）。

## 6. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| 记忆控制器 | **赛题"记忆调度控制器"原型**：决定查询列表何时发、短期何时归档到长期（`docs/04` 2.1/2.4 节） |
| flash/archived 双记忆 | 对应赛题"短期工作记忆+长期记忆"分层 |
| 写读时机显式化 | 支撑"主动操纵+容量受限"的短期记忆认知定义 |
| 即插即用思路 | 赛题方案对齐：记忆系统与智戎规划链路低侵入集成 |

---
*进化三路线：TiM（操作集）、SCM（控制器，本笔记）、PREMem（预存储推理）。*

## 论文核心代码（paper_code 索引）

- 仓库：`paper_code/04_记忆进化/SCM4LLMs/`
- `core/chat.py`：记忆控制器核心（何时触发写/读/摘要的决策逻辑）；`core/cfg.py` 全局配置；`dialogue_demo.py` 长对话入口（跑通即见控制器调度）。

## 我们的实现（memsys）

- **思路**：SCM 控制器 = 我们的 `MemoryController`——"何时写、何时读、读什么"集中在一个类，且是**唯一**同时碰四模块的角色（docs/08 §6）；
- **代码索引**：`memsys/controller.py` 全文件。

## 代码详解（时机决策集中化）

```python
# controller.py（骨架注释版）—— SCM memory controller 的三时机
def start_session(...):      # 何时建槽位/装载查询列表（写时机①）
    ...
def retrieve_and_load(self, top_k=3):   # 何时检索（读时机）+ 读后即时判断压缩
    for q in self._wm.slot.query_list:
        hits = self.retriever.retrieve(q, top_k=top_k)
        ...
    if self._wm.memory_pressure:        # SCM 式：读完后检查容量 → 主动压缩
        get_strategy(self.compression_name).apply(self._wm, ...)
def close_session(self, review_text):   # 何时进化（写时机②：场次末复盘驱动）
    material = review_text + 归档文本   # MemGPT flush 的内容并入复盘（不丢）
    return self.evolution.evolve_from_review(material, ...)
```
> 与 SCM 差异：其控制器决策由 LLM 自省 prompt 驱动（隐式）；我们的时机是**确定性方法调用**（显式、可测试），LLM 只在进化抽取时介入。

## 代码实证（结合 paper_code/）

- 仓库：`paper_code/04_记忆进化/SCM4LLMs/`
- 看 `core/chat.py`（对话核心 + 控制器调度）、`core/cfg.py`（配置）、`core/{book,meeting}.py`（长文/会议摘要）。
- 入口：`dialogue_demo.py`、`book_summary.py`、`meeting_summary.py`；`prompts/`、`config/`（apikey + proxy）。
- 赛题用法：记忆控制器"何时写/读"调度逻辑的蓝本。