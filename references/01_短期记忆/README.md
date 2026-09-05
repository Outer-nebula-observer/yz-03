# 参考文献 · 01 短期记忆（工作记忆 / 上下文压缩）

对应 `docs/04` 第 2.1 节（短期 / 工作记忆层）。

## 核心论文

| 论文 | 年份/出处 | arXiv | 一句话要点 |
|---|---|---|---|
| LLMLingua | EMNLP 2023 | [2310.05736](https://arxiv.org/abs/2310.05736) | 压缩 Prompt 以加速推理 |
| LongLLMLingua | ACL 2024 | [2310.06839](https://arxiv.org/abs/2310.06839) | 问题感知长上下文压缩（文档重排序 + 动态压缩比） |
| ICAE | ICLR 2024 | [2307.06945](https://arxiv.org/abs/2307.06945) | In-context Autoencoder 上下文压缩 |
| MemGPT | 2023 | [2310.08560](https://arxiv.org/abs/2310.08560) | working context + FIFO queue + 虚拟内存分页（工作记忆组织） |

## 相关方法（跨模块，见对应目录）

- **SCM**：`flash memory`（短期）+ `archived memory`（长期）→ 参考 04_记忆进化。

## 精读笔记与全文

| 论文 | 精读笔记 |
|---|---|
| LLMLingua | [笔记_Jiang2023-LLMLingua.md](./笔记_Jiang2023-LLMLingua.md) |
| LongLLMLingua | [笔记_Jiang2024-LongLLMLingua.md](./笔记_Jiang2024-LongLLMLingua.md) |
| ICAE | [笔记_Ge2024-ICAE.md](./笔记_Ge2024-ICAE.md) |
| MemGPT | [笔记_Packer2023-MemGPT.md](./笔记_Packer2023-MemGPT.md) |

> 全文提取为同名 `<论文>.md`（`scripts/pdf2md.py` 生成）。

## 放置约定

- 论文 PDF 放本目录，下载脚本 `scripts/download_papers.py` 会自动命名；
- 精读笔记 `笔记_*.md` + 全文提取 `<同名>.md` 均在本目录；
- 复现代码放 `../paper_code/短期记忆/`。
