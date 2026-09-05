# 参考文献 · 05 记忆评估

对应 `docs/03` 第 20 节（记忆系统评估）。

## 指标与路线（详见 docs/03 第 20.1–20.3 节）

- 直接评估 / 间接评估；主观 / 客观指标；
- 四大类客观指标：有效性（Accuracy / F1）、检索质量（Hit Rate / MRR / NDCG@K / Recall@K）、生成质量（上下文相关性 / 答案忠实度 / 答案相关性）、效率（Time Cost / Computation Overhead）；
- 记忆形式 × 评估维度表（Token 级 / 参数级 / 隐式 / 工作 / 情景 / 语义 / 事实 / 经验 / 任务内 / 跨任务）。

## Benchmark 清单（按任务）

- **问答**：HotpotQA、2WikiMQA、MuSiQue、Natural Questions (NQ)
- **对话**：LoCoMo、LongMemEval、PerLTQA、MemoryBank、LOCCO、DialSim
- **功能智能体**：MemBench、MemoryAgentBench、WebChoreArena、MT-Mind2Web、PersonaMem、MPR、PrefEval、StoryBench、Madial-Bench
- **代码生成与推理**：SWE-bench Verified、GAIA、XBench、BrowseComp、BRIGHT、OlympiadBench
- **深度研究与报告生成**：Deep Research、WildSeek、Review-5k、SolutionBench

> 说明：benchmark 多为数据集/评测集，未纳入 `scripts/download_papers.py` 的自动下载清单；需要时按官方仓库获取（见 `../paper_code/记忆评估/README.md`）。
> 本模块暂无本地 PDF；记忆评估的**综述口径**已整合进 [组会汇报_模型记忆体系综述.md](../组会汇报_模型记忆体系综述.md) 第 6 节（DMR / LongMemEval / LoCoMo 等索引）。

## 放置约定

- benchmark 论文 / 报告放本目录；
- benchmark 官方仓库放 `../paper_code/记忆评估/`。
