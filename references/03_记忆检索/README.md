# 参考文献 · 03 记忆检索（任务感知检索）

对应 `docs/04` 第 2.3 节（记忆检索）。

## 核心论文

| 论文 | arXiv | 一句话要点 |
|---|---|---|
| ChatDB | [2306.03901](https://arxiv.org/abs/2306.03901) | 数据库符号记忆 + NL→SQL |
| ExpeL | [2308.10144](https://arxiv.org/abs/2308.10144) | 向量库 Top-K 相似轨迹召回 |
| MIRIX | [2507.07957](https://arxiv.org/abs/2507.07957) | 多智能体 + 多策略主动检索（embedding/bm25/string） |
| Mem-α | [2509.25911](https://arxiv.org/abs/2509.25911) | 用强化学习学习记忆构建 |

## 相关方法（跨模块）

- **RMM 后向反思检索**（在线强化学习精化检索）→ 见 04_记忆进化；
- **TiM Recalling**（检索与当前上下文相关的历史信息）→ 见 04_记忆进化。

## 放置约定

- 论文 PDF 放本目录，下载脚本 `scripts/download_papers.py`；
- 复现代码放 `../paper_code/记忆检索/`。
