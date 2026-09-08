# annotated_code — 论文源码精读注释（入库分发版）

> **定位**：对 `paper_code/`（克隆仓库，不入库）中**关键源码**的逐段中文注释副本。
> 队友 clone 本仓库即得注释版，无需下载论文原仓库也能读懂核心机制。
>
> **约定**：注释文件 = "原文件核心节选 + 逐段中文注释"，文件头标注【论文定位】
> 【为什么精读】【我们的实现对照】三块，代码内注释保持原逻辑顺序（行号可对照原文件）。
> **覆盖原则**：21 篇论文笔记与"我们的实现"小节中提到的全部源码/核心组件，
> 有官方代码的（16/21 篇）均有对应注释版；无代码的（综述/LARP/ChatDB/
> LongLLMLingua 并库/Reflexion 未 clone/TiM 未 clone/ICAE 未 clone）在笔记中已注明。

## 注释总目录（11 个仓库 · 14 个注释文件）

| # | 注释文件 | 源自（paper_code/） | 核心内容 | 关联论文笔记 |
|---|---|---|---|---|
| 1 | `ExpeL/README_精读导读.md` | — | 三阶段流水线地图（先读） | 笔记_Zhao2023-ExpeL |
| 2 | `ExpeL/episode.py` | `03_记忆检索/ExpeL/memory/episode.py` | Trajectory：三流解析+三级检索键（**全文注释**） | 同上 |
| 3 | `ExpeL/expel_核心注释.py` | `03_记忆检索/ExpeL/agent/expel.py` | 五粒度入库+反查表、多取再筛+重排、推理时召回 | 同上 |
| 4 | `LLMLingua/prompt_compressor_核心注释.py` | `01_短期记忆/LLMLingua/llmlingua/…` | get_ppl 打分（KV cache+shift）、三级过滤主流程 | 笔记_Jiang2023-LLMLingua / Jiang2024-LongLLMLingua |
| 5 | `MemSkill/README_精读导读.md` | — | controller/executor/designer 三角色 | 笔记_MemSkill |
| 6 | `MemSkill/operation_bank_注释.py` | `04_记忆进化/MemSkill/src/operation_bank.py` | 元记忆统计（EMA/增量均值）、末位淘汰、保序 | 同上 |
| 7 | `MemSkill/designer_核心注释.py` | `04_记忆进化/MemSkill/src/designer.py` | 滚动失败池、频次聚合、三段式归因 | 同上 |
| 8 | `SCM/README_精读导读.md` | — | PREMem 四脚本 + SCM 三组件 | 笔记_Liang2023-SCM / Kim2025-PREMem |
| 9 | `SCM/chat_核心注释.py` | `04_记忆进化/SCM4LLMs/core/chat.py` | 三态降级 raw/summary/drop、预算贪心装填、保守二答 | 笔记_Liang2023-SCM |
| 10 | `Zep_graphiti/edges_核心注释.py` | `02_长期记忆/graphiti/graphiti_core/edges.py` | **双时态三时间**（valid/invalid/expired）、事实向量挂边、episode 反向索引 | 笔记_Rasmussen2025-Zep |
| 11 | `MemAlpha/memory_核心注释.py` | `03_记忆检索/Mem-alpha/memory.py` | 三库（core/semantic/episodic）、BM25/向量双路检索、**矩阵批量相似度** | 笔记_Wang2025-MemAlpha |
| 12 | `PREMem/segmentor_核心注释.py` | `04_记忆进化/PREMem/src/memory/segmentor.py` | LLM 语义切分 + **规则兜底双保险**、增量切分 | 笔记_Kim2025-PREMem |
| 13 | `MemoryBank/forget_memory_核心注释.py` | `02_长期记忆/…/forget_memory.py` | 艾宾浩斯**真实实现**（×5 系数校准）、概率遗忘 vs 我们阈值遗忘、检索即强化 | 笔记_Zhong2023-MemoryBank |
| 14 | `Voyager/skill_核心注释.py` | `02_长期记忆/Voyager/voyager/agents/skill.py` | 技能库双存储（描述向量/代码本体）、版本化覆盖、**assert 同步校验** | 笔记_Wang2023-Voyager |
| 15 | `MIRIX/memory_tools_核心注释.py` | `03_记忆检索/MIRIX/mirix/functions/function_sets/memory_tools.py` | 六类记忆工具集、类型化参数（ForLLM）、trigger 多 agent 分发 | 笔记_Wang2025-MIRIX |

## 覆盖核对表（21 篇笔记 → 注释版）

| 论文 | 仓库状态 | 注释版 |
|---|---|---|
| Survey 综述 | 清单库（无算法代码） | 不需要（框架价值） |
| LLMLingua / LongLLMLingua | 同仓库 | ✅ #4 |
| ICAE | 未 clone | —（笔记注明） |
| MemGPT | clone 为 landing page | —（笔记注明 archive 分支） |
| Reflexion | 未 clone | —（笔记注明） |
| Voyager | ✅ | ✅ #14 |
| Memp | ✅ | 笔记"代码实证"已详（ProcedureMem 三策略，结构简单） |
| LARP | 无官方代码 | — |
| MemoryBank | ✅ | ✅ #13 |
| Zep/Graphiti | ✅ | ✅ #10 |
| MemoChat | ✅ | 笔记"代码实证"已详（三阶段微调管线） |
| ChatDB | 无官方代码 | — |
| ExpeL | ✅ | ✅ #1-3 |
| MIRIX | ✅ | ✅ #15 |
| Mem-α | ✅ | ✅ #11 |
| TiM | 未 clone | — |
| SCM | ✅ | ✅ #8-9 |
| PREMem | ✅ | ✅ #8, #12 |
| MemSkill | ✅ | ✅ #5-7 |
| StructMem | ✅（LightMem） | 笔记"代码实证"已详（StructMem.md+src 结构） |

## 阅读顺序建议

```
1. 各目录 README_精读导读.md（5 分钟建地图）
2. ExpeL/episode.py → expel_核心注释.py（经验库怎么建怎么查）
3. LLMLingua/prompt_compressor_核心注释.py（压缩在算什么）
4. MemAlpha/memory_核心注释.py（三库+双路检索——我们双库的近亲）
5. MemoryBank/forget_memory_核心注释.py（遗忘的真实工程细节）
6. MemSkill/operation_bank_注释.py → designer_核心注释.py（可进化操作）
7. Zep_graphiti/edges_核心注释.py（双时态——事实库升级方向）
8. Voyager/skill_核心注释.py（技能库双存储）
9. MIRIX/memory_tools_核心注释.py（六库工具集——工业级全貌）
10. SCM/chat_核心注释.py（控制器——我们 controller 的祖先）
```

## 与我们代码（memsys）的对照总表

| 论文机制（注释版） | 我们的实现 | 改造点 |
|---|---|---|
| ExpeL 多粒度检索+反查 | `experiential_store.py` 单级 | 教训即产物，无轨迹可拆（设计差异非简化） |
| ExpeL 多取再筛+重排 | `hybrid.py` top_k*2 | 三路融合替代单路重排 |
| ExpeL min_score 缺失 | `hybrid.py` 无阈值过滤 | **待搬**：低分不返回（Mem-α 有） |
| LLMLingua force_tokens | `compression.py` 约束不进压缩器 | 更彻底：整字段隔离 |
| Mem-α 矩阵批量相似度 | `embeddings.py` 逐条 cosine | 待搬（库>万条时） |
| Mem-α min_score 阈值 | 同上 | **待搬** |
| MemoryBank 概率遗忘 | `forget()` 阈值确定删 | 认知拟真 vs 实验可控的取舍（答辩点） |
| MemoryBank ×5 系数 | `retention()` 照抄公式 | **待校准**（不足清单#6 根源） |
| MemSkill update_type 四值 | `schema.py` MemoryOp | +abstract 第五操作 |
| MemSkill 末位淘汰/统计 | `EvolutionReport` 计数版 | 升级方向：带 reward 技能进化 |
| MemSkill 滚动失败池 | `EvolutionReport.skipped` | 升级方向：难例档案+频次触发 |
| Zep 双时态三时间 | `MemoryEntry.timestamp` 单字段 | 升级方向：valid/invalid 支撑时序问答 |
| Zep 向量挂边（事实级） | `factual_store` 挂条目 | 多事实行时可考虑 |
| Voyager assert 同步校验 | 双存储无校验 | **待搬**（一行防御） |
| Voyager 版本化覆盖 | `merged_from` 溯源 | 同目的不同实现 |
| MIRIX 类型化参数（ForLLM） | `extract_memory_ops` 输出 Dict | 升级方向：结构化输出 |
| MIRIX 六 agent 分发 | `controller` 单体内联 | MVP 无需进程级，接口已对齐哲学 |
| SCM 三态降级 | `_flush()` 二态+archived 不丢 | 更保守（可回放） |
| SCM 保守二答（模糊=否） | 未实现 | **待搬**：进化判定处 |

> **加新注释的流程**：从 paper_code 复制核心段到对应子目录 → 文件头写三块定位 →
> 代码内逐段注释 → 本 README 两表各登记一行 → `python -m py_compile` 验证。
