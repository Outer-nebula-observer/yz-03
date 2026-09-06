# 参考文献 · 02 长期记忆（事实 + 经验）

对应 `docs/04` 第 2.2 节（长期记忆层）。

## 核心论文

| 论文 | 年份/出处 | arXiv | 一句话要点 |
|---|---|---|---|
| Reflexion | NeurIPS 2023 | [2303.11366](https://arxiv.org/abs/2303.11366) | 语言形式经验 + 自我反思 |
| Voyager | 2023 | [2305.16291](https://arxiv.org/abs/2305.16291) | 可执行技能库（Minecraft） |
| Memp | 2025 | [2508.06433](https://arxiv.org/abs/2508.06433) | 智能体程序性记忆 |
| LARP | 2023 | [2312.17653](https://arxiv.org/abs/2312.17653) | 角色长期记忆与一致性 |
| MemoryBank | 2023 | [2305.10250](https://arxiv.org/abs/2305.10250) | 摘要式长期记忆 + 用户画像 |
| Zep | 2025 | [2501.13956](https://arxiv.org/abs/2501.13956) | 时序知识图谱记忆架构 |
| MemoChat | 2023 | [2308.08239](https://arxiv.org/abs/2308.08239) | 用 memo 维持长程对话一致（对话片段摘要 + 主题索引） |

## 精读笔记与全文

| 论文 | 精读笔记 |
|---|---|
| Reflexion | [笔记_Shinn2023-Reflexion.md](./笔记_Shinn2023-Reflexion.md) |
| Voyager | [笔记_Wang2023-Voyager.md](./笔记_Wang2023-Voyager.md) |
| Memp | [笔记_Fang2025-Memp.md](./笔记_Fang2025-Memp.md) |
| LARP | [笔记_Yan2023-LARP.md](./笔记_Yan2023-LARP.md) |
| MemoryBank | [笔记_Zhong2023-MemoryBank.md](./笔记_Zhong2023-MemoryBank.md) |
| Zep | [笔记_Rasmussen2025-Zep.md](./笔记_Rasmussen2025-Zep.md) |
| MemoChat | [笔记_Lu2023-MemoChat.md](./笔记_Lu2023-MemoChat.md) |

> 全文提取为同名 `<论文>.md`（`scripts/pdf2md.py` 生成）。

## 说明

- **事实记忆**参考：MemoryBank、Zep（结构化/时序）；
- **经验记忆**参考：Reflexion、Voyager、Memp、LARP（经验→策略/技能/程序）；
- **对话长期记忆**参考：MemoChat。
- 下载脚本 `scripts/download_papers.py`；复现代码放 `../paper_code/长期记忆/`；7 篇本地论文均已有精读笔记，要点同时见组会汇报综述第 2 节。
