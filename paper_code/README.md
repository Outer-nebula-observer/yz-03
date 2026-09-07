# paper_code — 论文公开代码（复现 / 参考实现）

> 与 `../code/` 的区分：
> - `../code/` = **我们自己**的开发代码（含老师下发的 SDK）；
> - 本目录 = **他人论文**的公开代码，仅作复现与参考，不做主力开发。

## 子目录与模块

| 子目录 | 对应论文/方法 |
|---|---|
| `短期记忆/` | LLMLingua、LongLLMLingua、ICAE 等 |
| `长期记忆/` | Reflexion、Voyager、Memp、LARP、MemoryBank、Zep 等 |
| `记忆检索/` | ChatDB、ExpeL、MIRIX、Mem-α 等 |
| `记忆进化/` | TiM、SCM、RMM、PREMem、StructMem、MemSkill 等 |
| `记忆评估/` | 各 benchmark 官方仓库 |

## 约定

- **选择性下载**：见 [`MANIFEST.md`](./MANIFEST.md) 清单与 `../scripts/download_paper_code.py`；克隆目录被 `.gitignore` 忽略，不入库；
- 每个子目录 `README.md` 有"论文 → 仓库"索引；**仓库地址以论文官方页面 / PapersWithCode 为准**；
- 复现结论（能跑/不能跑/关键修改）记录到对应子目录 README 或 `../docs/`。
