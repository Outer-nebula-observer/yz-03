# 长短期记忆引擎（long_short_term_memory）

> 赛题③「异构多模态数据环境下大模型作战规划智能体记忆系统构建」交付引擎。
> 按《记忆引擎开发 SDK v1.0.0》实现，目录名 = 引擎 `name` = `long_short_term_memory`，
> 拖入 `server/engines/` 后由 `discover_plugins()` 自动注册。

## 能力

- **只检索、不生成**：`supports_generate=False`、`supports_stream=False`；
- **不 ingest / 不 delete**：记忆写入由场次复盘/智戎适配器调用
  `controller.close_session()` 完成，本引擎不接收文件级 ingest；
- **双库混合检索**：事实库（SQLite 参数级精确）+ 经验库（向量语义召回），
  同一查询同时检索后按融合分排序；
- **记忆进化**：写入查重、合并、艾宾浩斯遗忘、抽象（由外层复盘触发）。

## 检索结果字段

| 字段 | 取值 |
|---|---|
| `content` | 记忆内容片段（≤500 字符） |
| `score` | 0~1（融合分除以三路权重和，已归一化） |
| `source_file` | 记忆来源的可辨识标记；来源为空时用 `[memsys:fact/experience]`，不含系统绝对路径 |
| `chunk_id` | 记忆条目唯一 id |
| `engine` | `long_short_term_memory` |
| `metadata` | memory_type / route / session_id / timestamp 等 |

## 真模型注入（B4）

引擎默认零依赖 Mock（离线可跑）。接入智戎正式环境时，建议配置：

| 环境变量 | 取值 | 说明 |
|---|---|---|
| `LSTM_LLM` | `deepseek` / `glm` / `mock` | 默认 `mock` |
| `LSTM_EMBEDDING` | `glm` / `mock` | 默认 `mock` |

也可使用仓库根 `.env`（模板见 `.env.example`）：
`load_env()` 会自动向上查找并读取 `DEEPSEEK_API_KEY`、`GLM_API_KEY` 等。
配置失败时自动降级 Mock，不阻断服务启动。

## 本地快速验证（需在 SDK 服务端目录内）

```bash
python scripts/validate_engine.py long_short_term_memory
python scripts/smoke_test_engine.py long_short_term_memory
```

离线字段契约可直接运行 `sdk_check.py`（开发版自带）或参考交付包 `自检结果.txt`。
