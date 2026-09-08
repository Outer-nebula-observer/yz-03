# annotated_code — 论文核心源码逐行注释（中文精读版）

> **定位**：`paper_code/` 下的克隆仓库**不入库**（.gitignore 全忽略，按需 `scripts/download_paper_code.py` 拉取）；
> 本目录存放**我们加了逐行中文注释的核心源码副本**（或关键方法节选），随仓库分发——队友 clone 即得，无需下载几十 GB。

## 目录

| 论文 | 文件 | 注释内容 | 对应我们的实现 |
|---|---|---|---|
| **ExpeL**（AAAI'24 Oral） | `ExpeL/episode.py` | Trajectory 经验数据结构全文注释：三流解析/三级检索键 | `memsys/long_term/experiential_store.py` |
| | `ExpeL/expel_核心方法节选.py` | setup_vectorstore（经验入库）+ update_dynamic_prompt_components（推理时召回）+ 规则合并 | `memsys/retrieval/hybrid.py` |
| **MemSkill**（arXiv 2602.02474） | `MemSkill/operation_bank.py` | Operation（技能=模板+统计元数据）与 OperationBank（淘汰最差/探索偏置）全文注释 | `memsys/schema.py::op_history`（创新点 A 依据） |
| **SCM**（ACL'23 Findings） | `SCM/chat_核心方法节选.py` | ChatBot 控制器：is_history_need / judge_drop_or_summary（三级判定）/ get_related_turn（相似检索） | `memsys/controller.py`（直系祖先） |

每篇另有 `README_精读导读.md`（三阶段流水线地图 + 可搬走的设计清单）。

## 注释怎么读

每条注释按三层写：
1. **这行代码在干什么**（基础开发者可读）；
2. **【论文对应】**——对应论文哪节哪个机制；
3. **【我们的实现对照】**——memsys 里对应哪个文件哪个方法、我们做了什么改造（如"确定性阈值替代 LLM 判断"）。

## 与其它文档的关系

- 想看"为什么这么设计" → `docs/08_代码设计思路.md`
- 想看"怎么跑起来" → `docs/07_运行指南与效果说明.md`
- 想看"答辩怎么说创新" → `docs/09_想法与创新答辩指南.md`
- 想看单篇论文全貌 → `references/<模块>/笔记_*.md`（每篇末尾三节：论文核心代码/我们的实现/代码详解）

## 补充注释的约定

1. 新注释一个文件 → 复制到 `annotated_code/<论文名>/`（保持原文件名，节选加 `_核心方法节选` 后缀）；
2. 文件头写三段：论文定位 / 为什么精读 / 我们的实现对照表；
3. 原作者的 bug/怪写法**保留原样**并注明"上游遗留，勿学"（如 episode.py 的 `_replace`）；
4. 注释不改任何逻辑——验证方式：`python -m py_compile <文件>` 通过（节选文件除外，它们是教学摘录）。
