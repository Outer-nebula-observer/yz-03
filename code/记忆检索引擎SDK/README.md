# 记忆检索引擎 SDK（开发说明）

> 给第三方开发者开发「记忆检索引擎」的一揽子材料。按契约实现后，把引擎目录交回集成方，放进 `server/engines/` 重启服务即自动注册，前后端自动出现。

## 文件清单

| 文件                     | 用途                                 |
|------------------------|------------------------------------|
| `memory_engine_sdk.md` | 契约主文档（**先读这个**）                    |
| `源数据到检索数据生成过程.md`      | 数据口径：ingest 的输入长什么样、`rel_path` 相对谁 |
| `接入自检清单.md`            | 交付前逐项勾选                            |
| `template/`            | 可复制模板（复制改名即可起步）                    |
| `graph_rag/`   | 图检索引擎示例             |
| `validate_engine.py`   | 契约自检脚本（离线，无需服务端）                   |
| `smoke_test_engine.py` | HTTP 冒烟脚本（需服务端运行）                  |

## 三步上手

1. 读 `memory_engine_sdk.md` 的 §1~§3（契约）和 §6（接入）。
2. 复制 `template/` 为你的引擎目录，改 `engine.py` 的 `name` / `engine_label` / `engine_color` / `search`。
3. 交付前跑自检 + 冒烟（脚本用法见各自文件头部 docstring）。

## 交付物约定（交给集成方）

- 一个目录，目录名 = 引擎 `name`（小写下划线、不以下划线开头、不命中保留名）。
- 目录内至少含 `__init__.py`（导出 `engine_plugin`）和 `engine.py`。
- 若依赖第三方库，请附依赖清单（集成方会装进环境 / `requirements.txt`）。

## 脚本运行前提

两个脚本需在**项目内**运行（会自动向上定位项目根目录）：

    python scripts/validate_engine.py <引擎名>
    python scripts/smoke_test_engine.py <引擎名>

（本目录里的 `validate_engine.py` / `smoke_test_engine.py` 与项目 `scripts/` 下同名，内容一致。）
