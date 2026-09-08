# annotated_code — 论文源码精读注释（入库分发版）

> **定位**：对 `paper_code/`（克隆仓库，不入库）中**关键源码**的逐段中文注释副本。
> 队友 clone 本仓库即得注释版，无需下载论文原仓库也能读懂核心机制。
>
> **约定**：注释文件 = "原文件核心节选 + 逐段中文注释"，文件头标注【论文定位】
> 【为什么精读】【我们的实现对照】三块，代码内注释保持原逻辑顺序（行号可对照原文件）。
> 只注释**关键组件**（检索核心/数据结构/进化机制），不求全文覆盖。

## 目录

| 注释文件 | 源自（paper_code/） | 内容 | 关联论文笔记 |
|---|---|---|---|
| `ExpeL/episode.py` | `03_记忆检索/ExpeL/memory/episode.py` | Trajectory：经验库原子单元，三流解析+三级检索键（全文注释） | `references/03_记忆检索/笔记_Zhao2023-ExpeL.md` |
| `ExpeL/expel_核心注释.py` | `03_记忆检索/ExpeL/agent/expel.py` | 五粒度入库+反查表、多取再筛+重排、推理时召回 | 同上 |
| `ExpeL/README_精读导读.md` | — | ExpeL 三阶段流水线导读（先读这个再看代码） | 同上 |
| `LLMLingua/prompt_compressor_核心注释.py` | `01_短期记忆/LLMLingua/llmlingua/prompt_compressor.py` | get_ppl 困惑度打分（KV cache+shift 技巧）、compress_prompt 三级过滤主流程 | `references/01_短期记忆/笔记_Jiang2023-LLMLingua.md` |
| `MemSkill/operation_bank_注释.py` | `04_记忆进化/MemSkill/src/operation_bank.py` | Operation 元记忆统计（EMA/增量均值）、末位淘汰、确定性排序 | `references/04_记忆进化/笔记_MemSkill-Memory-Skills.md` |
| `MemSkill/designer_核心注释.py` | `04_记忆进化/MemSkill/src/designer.py` | CaseCollector 滚动失败池、频次聚合、三段式归因 | 同上 |
| `MemSkill/README_精读导读.md` | — | 三角色架构（controller/executor/designer）导读 | 同上 |
| `SCM/chat_核心注释.py` | `04_记忆进化/SCM4LLMs/core/chat.py` | judge_drop_or_summary 三态降级、预算内贪心检索、保守二答 | `references/04_记忆进化/笔记_Liang2023-SCM.md` |
| `SCM/README_精读导读.md` | — | PREMem 四脚本 + SCM 三组件导读 | 同上 + PREMem 笔记 |

## 阅读顺序建议

```
1. 各目录 README_精读导读.md（5 分钟建地图）
2. ExpeL/episode.py → expel_核心注释.py（经验库怎么建怎么查）
3. LLMLingua/prompt_compressor_核心注释.py（压缩在算什么）
4. MemSkill/operation_bank_注释.py → designer_核心注释.py（可进化操作）
5. SCM/chat_核心注释.py（控制器决策——我们 controller 的祖先）
```

## 与我们代码（memsys）的对照总表

| 论文机制（注释版） | 我们的实现 | 改造点 |
|---|---|---|
| ExpeL 多粒度检索+反查 | `experiential_store.py` 单级 | 教训即产物，无轨迹可拆（设计差异非简化） |
| ExpeL 多取再筛+重排 | `hybrid.py` top_k*2 | 三路融合替代单路重排 |
| LLMLingua force_tokens | `compression.py` 约束不进压缩器 | 更彻底：整字段隔离 |
| MemSkill update_type 四值 | `schema.py` MemoryOp | +abstract 第五操作 |
| MemSkill 末位淘汰/统计 | `EvolutionReport` 计数版 | 升级方向：带 reward 的技能进化 |
| MemSkill 滚动失败池 | `EvolutionReport.skipped` | 升级方向：难例档案+频次触发 |
| SCM 三态降级 raw/summary/drop | `_flush()` 二态+archived 不丢 | 更保守（可回放），代价 archived 增长 |
| SCM 保守二答（模糊=否） | 未实现 | 待搬：进化判定处采纳 |

> **加新注释的流程**：从 paper_code 复制核心段到对应子目录 → 文件头写三块定位 →
> 代码内逐段注释 → 本 README 登记一行 → 对照总表加一行。
