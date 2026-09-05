# 参考文献 · 01 短期记忆（工作记忆 / 上下文压缩）

对应 `docs/04` 第 2.1 节（短期 / 工作记忆层）。

## 核心论文

| 论文 | 年份/出处 | arXiv | 一句话要点 |
|---|---|---|---|
| LLMLingua | EMNLP 2023 | — | 压缩 Prompt 以加速推理 |
| LongLLMLingua | ACL 2024 | — | 问题感知长上下文压缩（文档重排序 + 动态压缩比） |
| ICAE | ICLR 2024 | — | In-context Autoencoder 上下文压缩 |

## 相关方法（跨模块，见对应目录）

- **MemGPT**：`working context` + `FIFO queue`（工作记忆组织）→ 参考 02/04；
- **SCM**：`flash memory`（短期）+ `archived memory`（长期）→ 参考 04_记忆进化。

## 放置约定

- 论文 PDF 放本目录，命名 `<一作><年份>-<短标题>.pdf`；
- 复现代码放 `../paper_code/短期记忆/`。
