# 论文精读（深化版）：MemGPT — Towards LLMs as Operating Systems

> - **作者 / 机构**：Charles Packer、Sarah Wooders、Kevin Lin 等（UC Berkeley）
> - **发表**：arXiv 2023（2310.08560），后发展为开源项目 Letta（原 MemGPT）
> - **对应**：`references/01_短期记忆/Packer2023-MemGPT.pdf` → 同名 `.md`
> - **官方代码**：https://github.com/cpacker/MemGPT → 现 Letta https://github.com/letta-ai/letta

## 一句话总结

把 OS 的"虚拟内存分页"搬进 LLM：主上下文（system+working context+FIFO queue）↔ 外部存储（archival/recall）之间由 LLM 自主调用函数换入换出，配队列管理器的"memory pressure 预警 + flush 递归摘要"防溢出——在有限窗口内"假装"无限记忆，文档分析与多会话聊天都能做。

## 1. 核心类比：LLM as OS

| OS 概念 | MemGPT 对应 |
|---|---|
| 物理 RAM（有限） | main context（LLM 上下文窗口） |
| 磁盘/swap（大） | external context（archival + recall storage） |
| 分页/换入换出 | LLM 调用函数在 main↔external 间移数据 |
| 中断/系统调用 | event 触发推理 + 函数调用 |
| 虚拟内存抽象 | 给 LLM"无限记忆"的错觉 |

## 2. 架构：分层记忆 + 函数执行器

```
┌─ Main Context（≈ RAM / 短期记忆，受窗口限制）────────────┐
│  System Instructions（read-only 静态：声明记忆层级与函数 schema）│
│  Working Context（read-write via functions：高频关键事实/偏好/角色）│
│  FIFO Queue（read-write via queue manager：消息/回复/系统消息）  │
└──────────────────────────┬───────────────────────────────┘
                           │  LLM 输出 = 函数调用
┌──────────────────────────▼───────────────────────────────┐
│  Function Executor：解析输出 → 执行 → 结果/错误回灌 main context │
│  （分页、检索都靠它，自省式；request_heartbeat=true 可链式调用）   │
└──────────────────────────┬───────────────────────────────┘
                           ▼
┌─ External Context（≈ 磁盘 / 长期记忆，无限）──────────────┐
│  Recall Storage（完整历史，可检索，flush 出的队列存这里）       │
│  Archival Storage（读写 DB，存任意长度文本对象）              │
└──────────────────────────────────────────────────────────────┘
```

## 3. 关键机制（深化）

### 3.1 队列管理器（Queue Manager）——上下文溢出控制
- **warning token count**（如窗口 70%）：插入系统消息"memory pressure"预警，提示 LLM 用函数把 FIFO 重要信息存进 working context 或 archival storage；
- **flush token count**（如 100%）：驱逐约 50% 队列消息，用"已有递归摘要 + 被驱逐消息"生成**新递归摘要**；驱逐的消息不再 in-context 但无限期存 recall storage，可函数读回。
- 即"分页"由阈值驱动，递归摘要保证被驱逐信息不丢。

### 3.2 函数执行器与自省式记忆
- LLM 输出被解析为函数调用（有 schema + 自然语言描述）；解析失败/运行错误回灌，形成**反馈学习环**；
- 记忆编辑与检索**完全自主**（self-directed）：LLM 据上下文决定何时在 main/external 间移数据、何时修改 working context；
- 系统提示包含两部分：记忆层级描述 + 函数 schema；
- **分页式检索**：检索结果分页返回，防止单次检索溢出窗口。

### 3.3 控制流与函数链
- **event 触发推理**：用户消息、系统消息（容量预警）、用户交互（登录/上传完成）、**定时事件**（允许 MemGPT 无用户输入"自言自语"运行）；
- **函数链**：`request_heartbeat=true` 标志让函数执行后立即把控制交回处理器（链式多步检索）；无此标志（yield）则暂停到下一事件——支撑多页结果导航、跨文档汇总。

## 4. 关键结果

| 场景 | 效果 |
|---|---|
| 文档分析 | 多轮递归阅读远超上下文窗口的大文档 |
| 多会话聊天 | 跨会话记住用户、随时间反思进化，一致性优于长上下文直接拼接 |
| DMR 基准 | 作为该基准提出方，成为后续（Zep 等）对标基线（93.4%） |
| 各 LLM 窗口 | GPT-3.5 16k/300、GPT-4 32k/600、Claude2 100k/2000、Yi-34B-200k 4000（窗口/近似消息数） |

## 5. 代码索引

- 官方：https://github.com/cpacker/MemGPT → Letta https://github.com/letta-ai/letta（自带 agent 记忆管理后端）
- 本仓库语境：**赛题③短期记忆"组织范式"参照物**（working context + FIFO queue + 分页），也可作长期记忆后端候选；运行位 `paper_code/短期记忆/`。

## 6. 优点 / 局限（深化）

- **优点**：首次系统化"记忆分层 + 主动分页"；自省式调度可解释（换页动机可追溯）；OS 类比天然适合系统背景团队汇报；阈值驱动的递归摘要防溢出且不丢信息。
- **局限**：分页决策依赖 LLM 自觉，偶发错误换页/忘关键页；纯文本存取，无结构化/图结构；性能上限受"能想起去读什么"（检索质量）制约；函数链增加 LLM 调用次数（成本）。

## 7. 与赛题③的联系（深化）

| 借鉴点 | 落地 |
|---|---|
| working context + FIFO queue | **短期/工作记忆组织范式**（`docs/04` 2.1 节首选） |
| 阈值驱动的递归摘要（70%/100%） | 短期记忆压缩的触发机制设计：容量预警→主动归档 |
| 自省式函数调度 | 短期↔长期转移由 LLM 自主触发，天然可演示"主动操纵" |
| 分页式检索（防溢出） | 大规模记忆库检索结果分页装载的工程选项 |
| DMR 基准 | 组会汇报评估小节引用（Zep 94.8% vs MemGPT 93.4%） |

---
*被 Zep（`笔记_Rasmussen2025-Zep.md`）等后续工作直接对标。*

## 代码实证（结合 paper_code/）

- 仓库：`paper_code/01_短期记忆/MemGPT/`
- ⚠ 此 clone 是 **Letta landing page**（含 README/AGENTS/SECURITY 等），原 V1 服务端源码在 `archive` 分支；当前实现在 `letta-ai/letta-code`（npm 安装）。
- 赛题用法：主要**学思想**（分层记忆 + 函数分页 + 阈值归档），不直接复用此 clone 代码；如需跑通切 `archive` 分支或装 letta-code。

## 论文核心代码（paper_code 索引）

- ⚠ 此 clone 为 Letta landing page，**无算法源码**；真实现两处：`archive` 分支（V1 服务端，Python）与 `letta-ai/letta-code`（当前版，TypeScript）；
- 关键文件（archive 分支）：`letta/services/`（记忆分层 CRUD）、`letta/prompts/system/`（自省式函数调用的 system prompt 全文——论文 §2.2 的落地）。

## 我们的实现（memsys）

- **思路**：把 MemGPT 的"分层 + 阈值分页 + 递归摘要"三机制原样落地为纯 Python（无函数调用依赖——分页由阈值属性驱动而非 LLM 自主调函数，MVP 更稳）；

## 代码详解（MemGPT 三机制 → 我们的三个属性/方法）

```python
# ① memory_pressure 预警（MemGPT: warning token count 70%）
@property
def memory_pressure(self) -> bool:
    return self.used_ratio >= self.warning_ratio      # 只读属性，上层据此提前归档

# ② flush 递归摘要（MemGPT: flush token count 100% + recursive summary）
def _flush(self, keep_ratio: float = 0.5) -> None:
    cut = max(1, int(n * keep_ratio))                 # 驱逐最旧 50%
    material = (self._recursive_summary + "\n" + "\n".join(evicted)).strip()
    self._recursive_summary = self.llm.summarize(material, 120)  # 旧摘要+驱逐消息→新摘要
    self.archived.append({...})                       # recall storage：被驱逐的不丢

# ③ render 首尾布局（规避 lost-in-the-middle）
#    头部=目标/约束(不可压缩) 尾部=最新消息 —— 关键信息永远在高效区
```
> 差异说明：MemGPT 的分页决策由 LLM 自主函数调用（更灵活但可能错换页）；我们用确定性阈值（可测试、可复现），LLM 自主分页列为进阶项。