# 智戎系统对接套装（zhirong_kit）

> 这是本项目对接「智戎」大小模型协同作战规划系统的**一站式入口**。
> 所有你需要的东西都在这个文件夹里：适配器、HTTP 桥、自检脚本、配置模板、对接手册。
>
> 位置：`code/课题3_长短期记忆/integration/zhirong_kit/`

---

## 一、目录说明

| 文件 | 作用 |
|---|---|
| `adapter.py` | 统一适配器工厂：一键创建 `ZhirongAdapter`（Mock/DeepSeek、持久化、降级） |
| `bridge_server.py` | HTTP 桥服务：智戎通过 REST 调三挂接点（适合跨机/前端调用） |
| `selfcheck.py` | 对接前自检：三挂接点全链路 + 时延日志 + 真模型探测，报告落盘 `reports/selfcheck.json` |
| `config.example.json` | 配置模板（桥接端口、SDK 引擎权重、三挂接点说明） |
| `reports/` | 自检/验收报告输出目录 |
| `README.md`（本文件） | 完整对接手册 |

**依赖**：本套装零第三方依赖（Python 标准库），但需要在同一环境能导入 `memsys`（核心包，与本目录同在 `code/课题3_长短期记忆/` 下）。把整个 `课题3_长短期记忆/` 目录部署到智戎环境即可。

---

## 二、三种接入方式（按智戎环境选）

### 方式 A：Python 内嵌（推荐，最简单）

智戎侧代码插入三行：

```python
from integration.zhirong_kit.adapter import create_adapter

adapter = create_adapter(real=False)          # real=True 用 DeepSeek 真 LLM

# ① 规划启动前：返回记忆增强上下文
ctx = adapter.hook_plan("ZR-001", "夜间夺占 2 号高地", ["禁止越境"])["context"]

# ⑤ 智戎原有规划生成，把 ctx 拼进 LLM prompt
plan = zhirong_planning(original_prompt + ctx)

# ⑥ AFSIM 推演后
adapter.hook_feedback("推演：任务部分达成。教训：电子压制不足。")

# ⑦ 场次结束，触发复盘进化
report = adapter.hook_close(extra_review="经验：预备队投入应提前 10 分钟。")
```

### 方式 B：HTTP 桥（适合跨机 / 智戎只暴露 HTTP）

启动服务：

```bash
cd code/课题3_长短期记忆
python integration/zhirong_kit/bridge_server.py --host 0.0.0.0 --port 8390
```

智戎侧发 3 个请求：

```bash
curl -X POST http://<mem-host>:8390/hook/plan \
  -H "Content-Type: application/json" \
  -d '{"plan_id":"ZR-001","goal":"夜间夺占 2 号高地","constraints":["禁止越境"]}'
# → {"context":"...","retrieved":N,"elapsed_ms":...}

curl -X POST http://<mem-host>:8390/hook/feedback \
  -H "Content-Type: application/json" \
  -d '{"text":"推演：任务部分达成。教训：电子压制不足。"}'

curl -X POST http://<mem-host>:8390/hook/close \
  -H "Content-Type: application/json" \
  -d '{"extra_review":"经验：预备队投入应提前 10 分钟。"}'
# → {"write":2,"abstract":1,...,"boundary":{...},"elapsed_ms":...}
```

健康检查：`GET http://<mem-host>:8390/healthz`（返回模型/embedding/库规模/时延）。

### 方式 C：老师 SDK 引擎（只做检索侧）

如果你只需把记忆系统挂进老师的**记忆检索引擎 SDK**，用 `engine.py`（`code/课题3_长短期记忆/engine.py`）：
1. 把 `课题3_长短期记忆/` 整个目录放进 SDK 的 `server/engines/`；
2. 重启服务 → 出现「长短期记忆」引擎；
3. 验证：`python sdk_check.py`（18 项）→ 真实 SDK 环境 `validate_plugin` → HTTP 冒烟；
4. 在 SDK `config.json` 配置权重/超时（见 `config.example.json` 的 `sdk_engine` 节）。

---

## 二·五、事件驱动模式（P0 适配，v0.8 已落地）

当智戎不是严格的“一次任务→结束→复盘”流水线时，使用事件驱动能力避免“记忆不进化”。

### 新增能力（adapter.py `ZhirongEventAdapter`）

| 方法 | 说明 |
|---|---|
| `hook_feedback(text="", structured=None)` | 结构化反馈（result/metrics/events）会被转写成复盘文本再累积 |
| `hook_append_feedback(fragment_text="", structured=None)` | 多次反馈累积缓冲，不立即消费 |
| `hook_evolve(reason="manual|periodic|...", extra_review="")` | **事件驱动进化**：即使没有 open session 也能沉淀经验 |
| `normalize_task(task_json)` | 智戎结构化任务 → `{plan_id, goal, constraints, queries}`；支持中文/英文别名 |
| `structured_to_review(payload)` | AFSIM 数值/事件 → 带“教训/经验”线索的复盘文本（保底转写） |

### HTTP 桥新增端点

```
POST /hook/plan        body 可传 {"task": {...}} 自动规范化（也可传原 plan_id/goal）
POST /hook/feedback    body {"text": "", "structured": {...}}
POST /hook/append_feedback  body {"text": "", "structured": {...}}
POST /hook/evolve      body {"reason": "manual|periodic|...", "extra_review": ""}
POST /hook/normalize   body {"task": {...}} → 规范化结果
```

### 领域巡检与阈值标定

```bash
# 有真实知识库样本时：
python integration/zhirong_kit/domain_check.py \
    --samples samples.json --fact-db ../data/facts.db --exp-db ../data/exps.db

# 没有真实库，先用内置战役种子演示：
python integration/zhirong_kit/domain_check.py --seed-campaign heights_battle
```
输出：每条查询 top-5 命中/hit@5/词表覆盖 + 负例 top1 → **min_score 建议**，报告落盘 `reports/domain_check.json`。

### 自检扩项

`python integration/zhirong_kit/selfcheck.py` 现在 5 项全过：
normalize_task、结构化反馈→事件驱动进化 均已加入自检。

## 三、配置与真模型

### 3.1 环境变量（HTTP 桥/自检读取）

| 变量 | 默认 | 说明 |
|---|---|---|
| `ZR_REAL` | `0` | `1` 启用 DeepSeek 真 LLM（需 `.env` 有 `DEEPSEEK_API_KEY`） |
| `ZR_EMBED_GLM` | `0` | `1` 启用 GLM embedding（需有效 `GLM_API_KEY`；失败回退 Mock） |
| `ZR_FACT_DB` | （内存） | 事实库 SQLite 路径（持久化） |
| `ZR_EXP_DB` | （内存） | 经验库 SQLite 路径（持久化） |

真模型配置统一在仓库根 `.env`（已 gitignore；模板 `.env.example`）。

### 3.2 持久化示例

```bash
ZR_FACT_DB=../../data/facts.db ZR_EXP_DB=../../data/exps.db \
  python integration/zhirong_kit/bridge_server.py --port 8390
```

---

## 四、验收材料与自检

```bash
cd code/课题3_长短期记忆

# 1) 对接前自检（Mock，离线必过）
python integration/zhirong_kit/selfcheck.py

# 2) 真模型探测（可选）
python integration/zhirong_kit/selfcheck.py --real

# 3) 报告位置
integration/zhirong_kit/reports/selfcheck.json
```

自检通过 = 三挂接点全链路 + 时延日志 + 边界审计都正常。验收时把 `selfcheck.json` 与 `IntegrationLog.to_dict()` 一起归档。

---

## 五、降级与稳定性（军规级可用性）

- **检索/记忆故障不阻断规划**：`ZhirongAdapter.hook_plan` 内部 try/except，故障返回空上下文而非抛异常；
- **真模型不可用自动降级**：`create_adapter(real=True)` 时 DeepSeek 密钥缺失/失效 → 回退 MockLLM 并打印警告；
- **HTTP 桥 4xx/5xx 有兜底**：任何 hook 异常返回 `{"error":...,"ok":false}`，不会把进程打挂；
- **GLM embedding 校验**：构造成功≠Key 有效，会实际 embed 一次再回退（防止 401 污染检索）。

---

## 六、常见问题

| 问题 | 处理 |
|---|---|
| 智戎环境导入不了 memsys | 把整个 `课题3_长短期记忆/` 拷过去，保证 `memsys/` 在 PYTHONPATH |
| 中文目录名在服务器不友好 | 复制时改名为 `long_short_term_memory`（`engine_plugin` 名字不受影响） |
| 想用真模型但没网络 | 保持 `real=False`（Mock）即可演示；真模型在本地演示时开 `ZR_REAL=1` |
| 如何录时延 | `adapter.log.to_dict()` / `selfcheck.json` 已含 per-hook avg/max |
| 知识锚定（权威库比对） | 当前未实现，属后续工作（docs/13）；对接时如实说明 |
| 需要阶段化检索（MDMP） | HTTP 桥当前暴露三挂接点；若需要逐步段检索可再扩展 `/hook/stage` |

---

## 七、对接检查清单

- [ ] `python integration/zhirong_kit/selfcheck.py` 全部 PASS
- [ ] （如用 SDK）`python sdk_check.py` 18 项 PASS
- [ ] 智戎侧三处调用已接（方式 A 或 B）
- [ ] 注入的 `context` 确实出现在智戎规划 prompt（打印日志验证）
- [ ] AFSIM 结果写回经验库（close 的 write>0）
- [ ] 时延 JSON 归档；异常降级验证（断掉检索服务，plan 仍返回空上下文）
- [ ] 录一段真实环境演示视频
