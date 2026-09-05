# 课题3 — 长短期记忆系统（我们的实现）

> 占位目录：后续在这里开发赛题③代码。

## 待搭建模块（对应 `docs/04` 第 2 节）

- 短期 / 工作记忆层
- 长期记忆层（事实记忆 + 经验记忆）
- 记忆检索（任务感知查询）
- 记忆进化（写入 / 合并 / 遗忘 / 抽象）

## 开发约定

1. 先读 `../记忆检索引擎SDK/memory_engine_sdk.md` 的**引擎契约**；
2. 对外统一实现 `MemoryEnginePlugin`（至少 `engine.py` + `__init__.py` 导出 `engine_plugin`）；
3. 数据模型与接口定义以 `../../docs/04` 第 1.3 节为起点；
4. 模块边界遵循 `docs/04`：检索只读、进化只写，独立评测。

## 建议目录（后续落地）

```text
课题3_长短期记忆/
├── engine.py            # MemoryEnginePlugin 实现
├── __init__.py          # 导出 engine_plugin
├── short_term/          # 工作记忆与上下文压缩
├── long_term/           # 事实/经验双库
├── retrieval/           # 任务感知检索
├── evolution/           # 写入/合并/遗忘/抽象
├── eval/                # 评估脚本
└── README.md
```
