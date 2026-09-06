# 参考文献 · 04 记忆进化（写入 / 合并 / 遗忘 / 抽象）

对应 `docs/04` 第 2.4 节（记忆进化）。

## 核心论文

| 论文 | arXiv/出处 | 一句话要点 |
|---|---|---|
| TiM | [2311.08719](https://arxiv.org/abs/2311.08719) | 回忆-反思双阶段 + 时间衰减更新（插入/遗忘/合并） |
| SCM | [2304.13343](https://arxiv.org/abs/2304.13343) | 记忆流 + 记忆控制器（archived/flash） |
| RMM | ACL 2025（无固定 arXiv，见脚本按标题检索） | 前向/后向反思式记忆管理 |
| PREMem | [2509.10852](https://arxiv.org/abs/2509.10852) | 预存储推理：聚类 → 链接对（θ=0.6）→ 链接对推理 |
| StructMem | 待检索（无固定 arXiv） | 事件级绑定 + 跨事件整合的分层记忆 |
| MemSkill | 待检索（无固定 arXiv） | 可学习记忆操作 INSERT / UPDATE / DELETE / SKIP |

> RMM / StructMem / MemSkill 的 arXiv 条目由下载脚本 `scripts/download_papers.py` 按标题自动检索；若检索不到，请到论文页或 ACL Anthology 手动下载。

## 精读笔记与全文

| 论文 | 精读笔记 |
|---|---|
| TiM | [笔记_Liu2023-TiM.md](./笔记_Liu2023-TiM.md) |
| SCM | [笔记_Liang2023-SCM.md](./笔记_Liang2023-SCM.md) |
| PREMem | [笔记_Kim2025-PREMem.md](./笔记_Kim2025-PREMem.md) |
| MemSkill | [笔记_MemSkill-Memory-Skills.md](./笔记_MemSkill-Memory-Skills.md) |
| StructMem | [笔记_StructMem-Structured-Memory.md](./笔记_StructMem-Structured-Memory.md) |

> 全文提取为同名 `<论文>.md`（`scripts/pdf2md.py` 生成）；5 篇本地论文均已有精读笔记；RMM 暂无本地 PDF（下载脚本会按标题检索）。

## 放置约定

- 论文 PDF 放本目录，下载脚本 `scripts/download_papers.py`；
- 精读笔记 `笔记_*.md` + 全文提取 `<同名>.md` 均在本目录；
- 复现代码放 `../paper_code/记忆进化/`。
