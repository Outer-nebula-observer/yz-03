# 课题3 — 长短期记忆系统（我们的实现）

> 赛题③「可演化的外部记忆系统」代码框架 v0.1。
> 技术路线：`docs/04_赛题三长短期记忆系统完整方案.md`；汇报稿：`docs/05`；文献依据：`references/`（21 篇精读笔记）；论文参考代码：`paper_code/`（14 个仓库）。

---

## 一、快速开始（零依赖，离线可跑）

```bash
cd code/课题3_长短期记忆

# 1) 冒烟测试（10 组用例全过 = 框架健康）
python tests/test_smoke.py

# 2) G0–G5 消融跑批（检索指标 + 库规模）
python -m eval.ablation

# 3) 七步闭环演示（两场次，验证"越用越强"）
python examples/demo_pipeline.py

# 4) Web 控制台（浏览器操作七步闭环，组会演示首选）
python webui/server.py            # → http://127.0.0.1:8765
```

**无需安装任何第三方包**：LLM/Embedding 均有 Mock 实现（确定性、离线）。
接真模型时见「四、接入真实组件」。

---

## 二、目录结构

```
课题3_长短期记忆/
├── memsys/                    # 核心包（五大模块 + 编排）
│   ├── schema.py              #   统一数据模型：槽位/记忆条目/查询项/检索结果
│   ├── llm.py                 #   LLM 抽象：MockLLM（离线）/ OpenAI 兼容骨架
│   ├── embeddings.py          #   向量化：MockEmbedding（哈希词袋）/ 内存向量索引
│   ├── boundary.py            #   ① 长短期边界：两把尺子/边界矩阵/双向禁止/晋升门控
│   ├── stages.py              #   ⑤ 阶段感知：MDMP 七阶段模板查询 + 复盘教训阶段归因
│   ├── short_term/            #   ② 短期/工作记忆（MemGPT 分层范式）
│   │   ├── working_memory.py  #     槽位 + FIFO + 阈值 flush + 递归摘要
│   │   └── compression.py     #     压缩策略：truncate / summarize / llmlingua(预留)
│   ├── long_term/             #   ② 长期记忆双库
│   │   ├── base.py            #     抽象基类（读=检索层；写=进化层）
│   │   ├── factual_store.py   #     事实库：SQLite + 属性精确过滤 + 向量辅助
│   │   └── experiential_store.py #  经验库：向量召回 + 重要性加权
│   ├── retrieval/             #   ③ 任务感知检索
│   │   ├── bm25.py            #     零依赖 BM25（词法路）
│   │   └── hybrid.py          #     vector/bm25/sql 三路路由 + 融合重排
│   ├── evolution/             #   ④ 记忆进化（创新重点）
│   │   └── memory_evolution.py #    写入(查重)/合并/遗忘(艾宾浩斯)/抽象 + 复盘驱动
│   ├── controller.py          #   总调度（SCM 思想：何时写/读/归档）
│   └── pipeline.py            #   七步闭环编排（离线可演示全链路）
├── eval/
│   ├── metrics.py             #   hit/recall/mrr/ndcg（零依赖实现）
│   ├── testset.py             #   作战测试集 50 条（8 类：属性/语义/转述/词法/负例/参数干扰/阶段决胜/跨场次）
│   ├── task_metrics.py        #   任务层指标：约束满足率/记忆引用率/噪声污染率
│   ├── stats.py               #   统计推断：bootstrap CI/配对置换检验/解析随机基线
│   └── ablation.py            #   G0–G6 消融 v2（真对照组+显著性检验，报告落盘 JSON）
├── tests/test_smoke.py        # 冒烟测试（零依赖，不用 pytest）
├── examples/demo_pipeline.py  # 两场次闭环演示（组会可放屏）
├── webui/                     # Web 控制台（零依赖 http.server）
│   ├── server.py              #   API 路由 + 全局 controller + 事件流/场次历史
│   ├── _selftest.py           #   全链路自测（48 项：七步闭环 + 过程可视化 + 跨场次复用）
│   └── static/                #   index.html / app.js / style.css（原生 JS）
├── engine.py                  # 老师平台 SDK 插件适配器（MemoryEnginePlugin）
├── __init__.py                # 包入口（导出 engine_plugin 供平台发现）
└── README.md                  # 本文件
```

---

## 三、架构与论文映射（每个文件对应哪篇论文）

| 模块 | 文件 | 范式来源（论文→paper_code） |
|---|---|---|
| 工作记忆 | `short_term/working_memory.py` | MemGPT 分层（working context + FIFO + 阈值 flush + 递归摘要）→ `01_短期记忆/MemGPT/` |
| 压缩 | `short_term/compression.py` | LLMLingua 三档消融对照 → `01_短期记忆/LLMLingua/` |
| 事实库 | `long_term/factual_store.py` | ChatDB 符号记忆（SQL 精确查询）+ Zep 属性结构 |
| 经验库 | `long_term/experiential_store.py` | ExpeL 向量召回 + Reflexion 语言教训 + 重要性加权 |
| 混合检索 | `retrieval/hybrid.py` | MIRIX 多策略路由（vector/bm25/sql）+ ChatDB Chain-of-Memory（查询列表显式化=创新点 C） |
| 进化·写入查重 | `evolution/memory_evolution.py::write` | PREMem 链接对 θ 阈值 → `04_记忆进化/PREMem/` |
| 进化·遗忘 | `::forget` + `schema.py::retention` | MemoryBank 艾宾浩斯 R=e^(-t/S) + 命中强化 → `02_长期记忆/MemoryBank-SiliconFriend/` |
| 进化·合并 | `::merge` | TiM merge / Memp Add⊖Del⊕Update |
| 进化·抽象 | `::abstract` | TiM Post-thinking / StructMem 周期整合 |
| 调度 | `controller.py` | SCM 记忆控制器 → `04_记忆进化/SCM4LLMs/core/` |
| 进化操作 API | `llm.py::extract_memory_ops` | Mem-α 工具化记忆操作（OpenAI tool schema 思想）→ `03_记忆检索/Mem-alpha/functions.py` |

---

## 四、接入真实组件（三步升级）

```python
from memsys import MemoryPipeline, get_llm, OpenAIEmbedding, MemoryController

# 1) 真模型 LLM（智戎平台 / DeepSeek / 本地 vLLM，OpenAI 兼容协议）
llm = get_llm("openai", base_url="http://<网关>/v1",
              api_key=os.environ["LLM_KEY"],   # 环境变量，勿硬编码
              model="deepseek-chat")

# 2) 真 embedding（BGE / OpenAI 兼容 /embeddings）
emb = OpenAIEmbedding(base_url="http://<网关>/v1",
                      api_key=os.environ["LLM_KEY"], model="bge-m3")

# 3) 组装（依赖注入，业务代码零改动）
ctl = MemoryController(llm=llm, embedding=emb,
                       factual=FactualStore("facts.db", emb),
                       experiential=ExperientialStore(emb))
pipe = MemoryPipeline(controller=ctl)
```

**接智戎规划链路**：`pipeline.py` 内两处 `TODO-INTEGRATION` 标记——
⑤ 规划输出换成智戎管线调用；⑥ 反馈换成 AFSIM 推演结果 + 评估。

**挂老师平台**：把本目录放进 SDK 服务的 engines 目录，`engine.py` 的
`engine_plugin`（LongShortTermMemoryEngine）会被自动发现注册，前端出现
「长短期记忆」引擎（检索走双库混合）。

---

## 五、当前不足与下一步（诚实清单）

| # | 不足 | 影响 | 计划 | v0.3 状态 |
|---|---|---|---|---|
| 1 | **MockEmbedding 无真语义**（字符词袋） | C 类转述命中与 G5 混合增益**不可外推**（消融 v2 已如实标注） | 接 BGE 后重跑消融（min_score/θ 按协议重标定） | 未变（P0） |
| 2 | **MockLLM 规则抽取**（关键词 + 句子级） | 抽取覆盖率有限；摘要为截断式 | 接真模型后 extract_memory_ops/abstract 质变 | 部分修复（句级抽取/前缀剥离/摘要有界） |
| 3 | ~~经验库不持久化~~ | — | — | ✅ **已修复**（SQLite 落盘，120 条重启回归通过） |
| 4 | NL→attrs 意图解析未做（attrs 需显式传入） | 自然语言问不精确；模板/场景已可用 attrs | 真模型后加"查询意图→属性条件"解析层 | 部分修复（sql 路 + attrs 通道已通） |
| 5 | 合并/抽象触发是成对启发式 | 漏合并、误合并都会发生 | 换 PREMem 式聚类全量比对 | 未变 |
| 6 | ~~遗忘/检索参数未经数据调优~~ | — | — | ✅ **已修复**（min_score=0.16 按负例分布标定；θ/遗忘/stage_bonus 敏感性扫描入消融 v2；**数据显示 Mock 下 θ 应为 0.6 而非默认 0.8——待决策**） |
| 7 | ~~消融种子集仅 3 例~~ | — | — | ✅ **已修复**（50 条 8 类测试集：负例/参数干扰/转述/阶段决胜/跨场次） |
| 8 | 未接智戎链路/AFSIM（⑤⑥ 是 Mock） | 端到端"真实调用"验收未达成 | 拿到平台接口后替换 TODO-INTEGRATION | 未变（P0） |
| 9 | LLMLingua 未真跑（仅适配器） | 压缩三档消融缺一档 | 装 llmlingua 后补 | 未变 |
| 10 | 无流式/并发 | 服务化需 asyncio | 挂平台时补 async 壳 | 未变 |
| 11 | 知识锚定校验未实现（docs/04 §1.2 承诺） | "库外经验混入"防线缺失 | 接智戎知识库后做"复盘候选 × 权威库"比对 | **新增**（评审指出，如实列出） |

**优先级建议**：1+2（接真模型）→ 8（接链路）→ 4（NL→attrs）→ 11（知识锚定）。

---

## 六、开发约定

1. **检索只读、进化只写**（`long_term/base.py` 注释即契约）——独立评测不互相污染；
2. 所有 LLM/向量依赖走**依赖注入**（Controller 构造参数），禁止模块内私连真模型；
3. 新功能先补 `tests/test_smoke.py` 用例再合入（保持零依赖可跑）；
4. 数据模型改动从 `schema.py` 出发（单一事实源），各模块不得私定义重复结构；
5. 提交信息按 `docs/git协作指南.md`（`feat/fix/docs(scope): 说明`）。

---

## 七、验证状态（v0.3 · 评审修复版）

- ✅ `tests/test_smoke.py`：**21/21 通过**（含「评审修复回归」9 项：上下文注入/单路模式/句级抽取/抽象无残留/bm25 归一/摘要有界/经验库持久化/正规写入入口/跨查询去重）
- ✅ `python -m eval.ablation`：**G0–G6 + 4 项专项研究**（50 条测试集、真对照组、随机基线、bootstrap CI、配对置换检验）——关键结论：G3 vs G2 p=0.0001；G4 跨场次复用 0.83 vs 0；负例返回率 0；详见 `docs/12_评审修复与消融v2报告.md`
- ✅ WebUI 自测 66/66；SDK 契约自检全过；智戎三挂接点全通
- ✅ v0.3 关键修复：**装载记忆真正进入注入 LLM 的上下文**（render 含【装载记忆】段）；sql 路真实现（attrs 属性精确过滤）；经验库 SQLite 持久化；遗忘保护线交互缺陷修复（教训自动 1.5 不越线）；Mock 抽象无指令残留；BM25 自匹配归一（负例噪声 58%→0%）；Mock 摘要中文截断（递归摘要膨胀 29531→有界）
- ⏳ 待办：见「五、当前不足」（#1/#2/#4/#8 未变——真模型与真链路）