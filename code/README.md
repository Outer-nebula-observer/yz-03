# code — 实际开发代码（顶层）

> 这里是团队的**实际开发代码目录**（顶层），随本仓库一起 git 提交。

## 目录说明

| 目录 / 文件 | 说明 |
|---|---|
| `记忆检索引擎SDK/` | 老师下发的「记忆检索引擎 SDK」：契约主文档 + `template/` + `graph_rag/` 示例 |
| `课题3_长短期记忆/` | **我们赛题③的实现（v0.1 框架已落地）**：`memsys/` 核心包 + `eval/` + `tests/` + `examples/` + `engine.py` 平台插件 |
| `RAG sdk开发说明.rar` | SDK 压缩包存档（老师原文件） |

## 约定

1. **各课题代码包**：老师下发时按 `课题N_名称/` 放入本目录（如 `课题1_图记忆/`、`课题2_多模态记忆/`）；
2. **我们的开发**：一律在 `课题3_长短期记忆/` 下进行；
3. **开发前先读**：
   - `记忆检索引擎SDK/memory_engine_sdk.md`（引擎契约，先读 §1–§3 与 §6）；
   - `../docs/04_赛题三长短期记忆系统完整方案.md`（技术路线）；
4. **他人论文的公开代码**放 `../paper_code/`，不要混入本目录。

## 快速上手 SDK

```bash
# 三步接入（详见 SDK README 与 memory_engine_sdk.md）
# 1) 复制 template/ 为你的引擎目录
# 2) 改 engine.py 的 name / engine_label / search
# 3) 交付前跑 validate_engine.py + smoke_test_engine.py
```
