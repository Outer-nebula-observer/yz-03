# 源码精读注释 ③：PREMem + SCM（`04_记忆进化/`）

> **论文**：PREMem（2509.10852）/ SCM（2304.13343）；笔记见 `references/04_记忆进化/`。
> **为什么精读**：PREMem 是创新点 A 的"预存储推理"依据；SCM 是我们 controller 的直系祖先。

---

# Part A：PREMem（`PREMem/`）

## 0. 四脚本流水线（预存储推理 = 写入时把活干完）

```
run_extract_episodic_memory.py（① 抽片段：事实/经验/主观）
  → run_reasoning.py（② 链接对推理：扩展/转化/蕴含）
  → save_episodic_embedding.py（③ 编码入库）
  → save_reasoning.py（④ 关系持久化）
数据结构层：src/memory/segmentor.py（切分）+ compressor.py（压缩）
```

## 1. `run_extract_episodic_memory.py` —— 参数即方法论

```python
parser.add_argument("--model_name", default="gpt-4.1-nano")   # 抽取用小模型——写入贵，生成时廉价
parser.add_argument("--mode", default="turn")                  # 切分粒度：turn（轮）/session（会话）
parser.add_argument("--token_budget", type=int, default=2048)  # 单次处理的 token 预算——成本控制内嵌参数
parser.add_argument("--compress_rate", default=0.9)            # 压缩率（配合 compressor.py）
parser.add_argument("--batch_size", default=256)               # 异步批量调 LLM（asyncio）
```

**【论文对应】** "把推理负担从生成移到存储"的工程含义就体现在这组参数：**用便宜的小模型 + 异步批处理**，把昂贵的跨会话综合提前做完；生成时只剩向量检索。

**【我们的实现】** 我们的 `write()` 查重是它的"一步版"；完整版应接入这四脚本流程——尤其 ② 的"关系类型"（extension/transformation/implication）我们还没建模（README 不足清单第 5 条的解法在这里）。

## 2. `src/memory/segmentor.py` —— 会话切分

```python
@dataclass
class SegmentContent:
    segment_id: int
    start_exchange_number: int      # 起始轮次
    end_exchange_number: int        # 结束轮次
    num_exchanges: int
    summary: str                    # 该段摘要
    conversation: List[Message]     # 原始消息（保留！——非损式）

class ConversationSegmentor:
    # LLM 判断"哪里是话题边界" → 切成 segment → 每段带摘要
    # 与我们 WorkingMemory 的"FIFO + flush"不同：这是"语义切分"而非"容量切分"
```

**【论文对应】** PREMem 的细粒度片段 = 事实/经验/主观三类，切分是抽取的前提。

**【我们的实现】** 我们用"容量驱动 flush"（简单、确定）；PREMem 用"语义驱动切分"（质量高、贵）。**折中方案**（可作为我们的进阶）：复盘文本先按"教训/经验"行切（MockLLM 规则已隐式做了），真模型后换语义切分。

---

# Part B：SCM（`SCM4LLMs/`）

## 3. `core/chat.py::Turn` —— 一轮对话的记忆单元

```python
class Turn(object):
    def __init__(self, user_input, system_response, user_sys_text, summ, embedding):
        # 五元组：用户输入 / 系统回复 / 系统思考 / 摘要 / 向量
        # 注意 summ 和 embedding 都在 Turn 级——摘要与向量化在"写入时"完成（与 PREMem 同哲学）
```

## 4. `core/chat.py::ChatBot` —— 控制器的三个关键方法

```python
def _is_concat_history_too_long(self, length_lst):
    """① 容量判断：拼接历史是否超长——我们 memory_pressure 的原型"""
    ...

def judge_drop_or_summary(self, user_query, turn_index):
    """② 核心决策：这一轮历史该'丢弃'还是'摘要压缩'？
       LLM 判断（get_binary_answer）——'是否与当前话题相关'
       相关→保留/摘要；无关→丢弃。这就是'自控'的含义：不是无脑全存"""
    ...

def get_related_turn(self, query, k=3, naive=False):
    """③ 检索：当前问题 → 找最相关的 k 轮历史
       naive 版（get_related_turn_naive）：全量算相似度
       完整版：带优化（缓存/剪枝）——长对话检索的工程细节都在这 100 行"""
    ...

def get_binary_answer(self, prompt, false_choices=[]):
    """工具方法：让 LLM 只回答是/否（judge_drop_or_summary 的基础）
       false_choices：把'模糊回答'也归为否——保守策略，宁错杀不漏判"""
```

**【论文对应】** SCM 三组件：LLM agent / memory stream / **memory controller**——`judge_drop_or_summary` 就是控制器"何时写、写什么"的决策点（我们 controller.py 的直系祖先）。

**【我们的实现】** 对照表：

| SCM（chat.py） | 我们（memsys） | 改造 |
|---|---|---|
| `_is_concat_history_too_long` | `WorkingMemory.memory_pressure` | 阈值化（确定性） |
| `judge_drop_or_summary`（LLM 判断） | `_flush()` + `compress()` | 规则替代 LLM 判断（可测试） |
| `get_related_turn` | `HybridRetriever.retrieve` | 单路相似 → 三路融合 |
| `Turn.summ/embedding` 写入时算 | `experiential_store.add()` 编码 | 同哲学，我们更晚（复盘时） |

**【关键差异——答辩点】** SCM 的控制器决策**每次都调 LLM**（贵、不确定）；我们的时机决策**全部确定性方法**（免费、可断言），LLM 只在"进化抽取"一处介入——这是 docs/09 决策 4 的同源逻辑。

## 5. 可直接搬走的三件事

1. **PREMem 关系三元类型**（extension/transformation/implication）——补足我们合并去重"只看相似度、不看关系性质"的短板；
2. **SCM 的 `get_binary_answer` 保守策略**——凡模糊即否，值得我们进化判定处采纳；
3. **PREMem 的 `token_budget` 内嵌参数化**——成本控制写进接口签名，比写注释强。
