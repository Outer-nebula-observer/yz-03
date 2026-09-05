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

## 放置约定

- 论文 PDF 放本目录，下载脚本 `scripts/download_papers.py` 会自动命名；
- 复现代码放 `../paper_code/短期记忆/`。
