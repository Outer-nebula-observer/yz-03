Preprint

## MEM- α : LEARNING MEMORY CONSTRUCTION VIA REINFORCEMENT LEARNING


**Yu Wang** [1] _[,]_ [2] **,** _[∗]_ **Ryuichi Takanobu** [1] **,** **Zhiqi Liang** [2] **,** **Yuzhen Mao** [3] **,**

**Yuanzhe Hu** [2], **Julian McAuley** [2], **Xiaojian Wu** [1],
1Anuttacon, 2University of California San Diego, 3 Stanford University
yuw164@ucsd.edu, truthless11@gmail.com


[Datasets](https://huggingface.co/datasets/YuWangX/Memalpha) [Models](https://huggingface.co/YuWangX/Memalpha-4B) [Source Code](https://github.com/wangyu-ustc/Mem-alpha)


ABSTRACT


Large language model (LLM) agents are constrained by limited context windows,
necessitating external memory systems for long-term information understanding.
Current memory-augmented agents typically depend on pre-defined instructions
and tools for memory updates. However, language models may lack the ability to determine which information to store, how to structure it, and when to
update it—especially as memory systems become more complex. This results
in suboptimal memory construction and information loss. To this end, we propose Mem- _α_, a reinforcement learning framework that trains agents to effectively
manage complex memory systems through interaction and feedback. We also
construct a specialized training dataset spanning diverse multi-turn interaction
patterns paired with comprehensive evaluation questions designed to teach effective memory management. During training, agents process sequential information
chunks, learn to extract, store, and update the memory system. The reward signal
derives from downstream question-answering accuracy over the full interaction
history, directly optimizing for memory construction. To illustrate the effectiveness of our training framework, we design a memory architecture comprising core,
episodic, and semantic components, equipped with multiple tools for memory
operations. Empirical evaluation demonstrates that Mem- _α_ achieves significant
improvements over existing memory-augmented agent baselines. Despite being
trained exclusively on instances with a maximum length of 30k tokens, our agents
exhibit remarkable generalization to sequences exceeding 400k tokens—over 13×
the training length, highlighting the robustness of Mem- _α_ .


1 INTRODUCTION


Large language model (LLM) agents are fundamentally constrained by limited context windows
when processing long information streams, leading to the development of memory-augmented
agents (Wang et al., 2025/02; Fang et al., 2025). These agents are equipped with persistent, updatable memory systems that actively stores long-term information and manage the context seen by
the language model (Packer et al., 2023; Lin et al., 2025; Cai et al., 2025). Most existing memory
systems rely entirely on pre-defined instructions and fixed tool sets without any training to optimize
memory construction, such as Mem0 (Chhikara et al., 2025), MemGPT (Packer et al., 2023), and
MIRIX (Wang & Chen, 2025). These memory systems provide agents with various memory update
tools—ranging from simple fact extraction to complex multi-component memory architectures—but
expect models to utilize these tools effectively out-of-the-box. However, models lack the inherent
ability to determine what to store, how to structure, and when to update different memory components. Although complicated system prompts can partially mitigate this issue, manual adjustment
of system prompts is challenging to address all scenarios. For small language models with weak
instruction-following abilities, complicated instructions may even confuse the model (Wen et al.,
2024; Wang et al., 2025b).


To address this challenge, we turn to reinforcement learning (RL) as a principled approach for training agents to learn effective memory management strategies. Unlike supervised fine-tuning, which


_∗_ Work done during the internship at Anuttacon.


1


Preprint


Figure 1: **Reinforcement learning teaches agents to select appropriate memory tools and types.**
Before training (left), agents struggle with tool selection when given new information. After RL
training (right), agents learn effective memory management policies.


requires ground-truth memory construction traces, RL enables agents to discover optimal memory
strategies through trial and error. This approach is necessary across all model scales: even state-ofthe-art models like GPT-4o struggle with proper tool selection for memory updates (Wang & Chen,
2025), while smaller models become completely overwhelmed by complex tool sets (Wang & Chen,
2025; Wang et al., 2025b). Since we cannot obtain reliable supervision signals from any existing
model, we instead directly optimize for downstream task performance—using question-answering
accuracy and memory quality metrics as reward signals. Through RL, language models learn to
navigate complex memory systems effectively, discovering strategies that optimize memory construction without relying on potentially suboptimal predefined behaviors. Existing works including
MEM1 (Zhou et al., 2025), MemAgent (Yu et al., 2025) and Memory-R1 (Yan et al., 2025) are
the first works exploring this direction. However, they employ relatively simple memory structures
(e.g., memory rewriting or maintaining a list of facts) that are insufficient for handling complex data
such as long narratives, procedural rules, evolving knowledge, or even multi-modal information.


To this end, we propose Mem- _α_, a reinforcement learning framework that trains agents to effectively
manage complex memory systems through interaction and feedback. Unlike existing approaches
that either provide sophisticated tools without teaching models how to use them, or train models
on simplistic memory operations, Mem- _α_ enables agents to learn memory construction strategies
for complex, multi-component memory architectures (as shown in Figure 1). Our approach addresses three key challenges in memory-augmented agent training. First, we formulate the process
of memory construction as a sequential decision-making problem where agents process information chunks, decide which memory operations to perform, and receive multiple rewards based on
downstream question-answering accuracy over the full interaction history. This direct optimization
for end-task performance naturally teaches agents to save the most important information and organize the existing memory effectively. Second, we construct a specialized training dataset spanning
diverse multi-turn interaction patterns, including conversations, document sharing, pattern recognition, and storytelling, paired with comprehensive evaluation questions that require comprehensive
memory to answer correctly. This design exposes agents to various scenarios of memory management during training. Lastly, we adopt a comprehensive memory architecture comprising core,
episodic, and semantic components, each equipped with specialized tools for memory operations,
providing sufficient expressiveness to handle diverse information types while remaining learnable
through reinforcement.


Empirical evaluation demonstrates that Mem- _α_ achieves significant improvements over existing
memory-augmented agent baselines across diverse benchmarks. Most remarkably, despite being
trained exclusively on instances with a maximum length of 30k tokens, our agents exhibit robust
generalization to sequences exceeding 400k tokens, over 13× the training length. This exceptional
length generalization suggests that reinforcement learning enables agents to learn fundamental memory management principles rather than merely memorizing specific patterns, highlighting the potential of learning-based approaches for long-context retention.


2


Preprint


2 RELATED WORK


**Latent-Space** **Memory** These methods encode new information directly into a model’s internal
components—such as hidden states (Wang et al., 2024; 2025a; Bulatov et al., 2022; He et al., 2024),
key-value caches (Qian et al., 2025; Li et al., 2024; Zhang et al., 2023b; Zhong et al., 2023), soft
prompts (Burtsev & Sapunov, 2020; Ge et al., 2023), model parameters (Behrouz et al., 2024; Berges
et al., 2024; Wang et al.; Wei et al., 2025), or learnable external matrices (Das et al., 2024). The
main advantage is efficient compression: for instance, SELF-PARAM (Wang et al.) can memorize
hundreds of contexts without external storage. However, these approaches face two key limitations.
First, their memory capacity remains bounded—M+ (Wang et al., 2025a) achieves retention of approximately 160k tokens, which falls short of state-of-the-art memory agents like MIRIX (Wang &
Chen, 2025). Second, they require direct access to model internals, making them incompatible with
proprietary systems (e.g., GPT-4/5). Since open-weight alternatives typically underperform leading
proprietary models, these constraints limit practical deployment.


**LLM Agents with External Memory** An alternative approach equips language models with external memory systems built on databases or vector stores (Zhang et al., 2025a), as demonstrated by
MemGAS (Xu et al., 2025a), SCM (Wang et al., 2023), A-MEM (Xu et al., 2025b), MemTree (Rezazadeh et al., 2024) MemGPT (Packer et al., 2023), Mem0 (Chhikara et al., 2025), Zep (Rasmussen
et al., 2025), Nemori (Nan et al., 2025), EgoMem (Yao et al., 2025), MIRIX (Wang & Chen, 2025),
Memobase [1], MemoChat (Lu et al., 2023) and similar frameworks. These architectures offer two
key advantages: they work seamlessly with proprietary frontier models (e.g., GPT-4/5, Claude family) and can efficiently organize, retrieve, and update large amounts of information through welldesigned schemas and controllers. However, their effectiveness depends heavily on the base model’s
ability to follow instructions and use tools (function-calling)—capabilities that smaller, more costeffective models often lack. Meanwhile, when the system becomes complex, even proprietary models may not update the memory systems well (Wang & Chen, 2025). This limitation motivates
approaches that explicitly _train_ models to manage memory rather than relying purely on prompting.


**Learning Memory Construction with Reinforcement Learning** Recent work explores training
language models to construct memory using reinforcement learning, though results remain preliminary. Early efforts such as MEM1 (Zhou et al., 2025) and MemAgent (Yu et al., 2025) train models
to update simple, text-only memories. Memory-R1 (Yan et al., 2025), Learn-to-Memorize (Zhang
et al., 2025b) and REMEMBER (Zhang et al., 2023a) introduce a slightly richer memory representation and a simplified tool-calling interface, but focuses on LoCoMo (Maharana et al., 2024) settings
with relatively short maximum context (less than _∼_ 26k tokens) and train on subsets of the same
distribution, which makes the task comparatively easier. In this paper, we develop an RL framework that trains a model to operate a substantially more capable memory system and demonstrate
significant improvements across multiple dimensions of memory quality and efficiency.


3 METHOD


3.1 REINFORCEMENT LEARNING FRAMEWORK


We formulate memory construction as a reinforcement learning problem where the agent learns to
optimize memory building policies. The quality of the constructed memory is evaluated through
a separate question-answering process using retrieval-augmented generation (RAG). The complete
training framework is shown in Figure 2.


3.1.1 TASK SETUP


We consider a memory construction task where an agent processes a sequence of conversations _C_ =
_{c_ 1 _, . . ., cn}_ between a user and an assistant. These conversations span diverse formats, including
casual discussions, storytelling, book sharing, and classification examples. At step _t_ _∈{_ 1 _, . . ., n}_
the agent observes _ct_ and the current memory _Mt−_ 1 (here _M_ is the memory and _M_ 0 is initialized
as an empty memory) and may issue a _sequence_ of write operations before advancing to the next


1https://github.com/memodb-io/memobase


3


Preprint


Figure 2: **Training Framework of Mem-** _α_ .


chunk. Formally, the action at step _t_ is



_t_



_at_ =




 - _a_ [(1)]




[(1)] _t_ _[, . . ., a]_ _t_ [(] _[K][t]_ [)]







where each _a_ [(] _t_ _[k]_ [)] _∈A_ write = _{_ memory ~~i~~ nsert _,_ memory ~~u~~ pdate _,_ memory ~~d~~ elete _}_ is a struc
tured function call with arguments (e.g., record id, memory type, string content), and _Kt_ is the
number of operations in this action. Then we apply these function calls on _Mt−_ 1:




[(] _t−_ _[k]_ [)] 1 [)] [for] _[ k]_ [= 1] _[, . . ., K][t][,]_ _Mt_ = _M_ [(] _t−_ _[K]_ 1 _[t]_ [)]



_M_ [(0)]




[(0)] _t−_ 1 [=] _[ M][t][−]_ [1] _[,]_ _M_ [(] _t−_ _[k]_ [)]



_t−_ 1 [=] _[ T]_




- _M_ [(] _[k][−]_ [1)]




_[t]_

_t−_ 1 _[,]_




[(] _t−_ _[k][−]_ 1 [1)] _,_ _a_ [(] _t−_ _[k]_ [)]



After processing all the chunks in _C_, we obtain the final memory _Mn_ . Then we can calculate the
rewards according to the final memory _Mn_ and all the actions _A_ = _{a_ 1 _, · · ·_ _, an}_ across the whole
list of chunks.


3.1.2 REWARD FUNCTIONS


**Correctness** **Reward** **(** _r_ 1 **)** The correctness reward evaluates the comprehensiveness of the final
memory _Mn_ through question-answering performance. Given questions _Q_ = _{q_ 1 _, . . ., qm}_ and
predicted answers _ANS_ = _{ans_ 1 _, . . ., ansm}_ obtained via the RAG pipeline, we compute _r_ 1
using dataset-specific metrics (Table 6). For example, on SQuAD: _r_ 1 = _l/m_ where _l_ is the number
of correctly answered questions.


**Tool Call Format Reward (** _r_ 2 **)** To ensure reliable function execution, we reward tool calls with
the correct format. For each function call _a_ [(] _t_ _[k]_ [)], let _s_ ( _a_ [(] _t_ _[k]_ [)] ) _∈{_ 0 _,_ 1 _}_ be a binary indicator where

_s_ ( _a_ [(] _t_ _[k]_ [)] ) = 1 if _a_ [(] _t_ _[k]_ [)] has the correct format and executes successfully and 0 otherwise. The reward is:

_r_ 2 _,t_ = [�] _k_ _[K]_ =1 _[t]_ _[s]_ [(] _[a]_ _t_ [(] _[k]_ [)] ) _/Kt_, measuring the percentage of successfully executed function calls.

**Compression** **Reward** **(** _r_ 3 **)** To encourage efficient memory usage, we define: _r_ 3 = 1 _−_ _lm/lc_,
where _lm_ is the total memory length and _lc_ is the total length of the chunks. This promotes compact
memory representations while preserving essential information.


**Memory** **Content** **Reward** **(** _r_ 4 **)** To ensure memory operations satisfy their semantic definitions,
we use Qwen3-32b to validate memory updates (prompts in Appendix C.3). For each operation
_a_ [(] _t_ _[k]_ [)], let _v_ ( _a_ [(] _t_ _[k]_ [)] ) _∈{_ 0 _,_ 1 _}_ be a binary indicator where _v_ ( _a_ [(] _t_ _[k]_ [)] ) = 1 if _a_ [(] _t_ _[k]_ [)] is semantically valid and 0

otherwise. The reward is: _r_ 4 _,t_ = [�] _k_ _[K]_ =1 _[t]_ _[v]_ [(] _[a]_ _t_ [(] _[k]_ [)] ) _/Kt_, measuring the fraction of valid operations.

Formal mathematical definitions of all reward components are provided in Appendix B.


Then we combine four rewards together to obtain the final reward _rt_ for action _at_ :

_rt_ = _r_ 1 + _r_ 2 _,t_ + _βr_ 3 + _γr_ 4 _,t_ (1)


4




[(] _t_ _[k]_ [)], let _s_ ( _a_ [(] _t_ _[k]_ [)]




[(] _t_ _[k]_ [)] ) = 1 if _a_ [(] _t_ _[k]_ [)]




_[K][t]_

_k_ =1 _[s]_ [(] _[a]_ _t_ [(] _[k]_ [)]



_t_ ) _/Kt_, measuring the percentage of successfully executed function calls.




[(] _t_ _[k]_ [)], let _v_ ( _a_ [(] _t_ _[k]_ [)]




[(] _t_ _[k]_ [)] ) _∈{_ 0 _,_ 1 _}_ be a binary indicator where _v_ ( _a_ [(] _t_ _[k]_ [)]




[(] _t_ _[k]_ [)] ) = 1 if _a_ [(] _t_ _[k]_ [)]




_[K][t]_

_k_ =1 _[v]_ [(] _[a]_ _t_ [(] _[k]_ [)]



_t_ ) _/Kt_, measuring the fraction of valid operations.


Preprint



where _β, γ_ are hyperparameters requiring tuning. We fix the weight of _r_ 2 _,t_ at 1 (rather than varying
it) because the function call success rate is critical for memory updates. The four reward components
operate at different granularities: _r_ 1 (correctness) and _r_ 3 (compression) are computed globally based
on the final memory state _Mn_ and thus share the same value across all actions in the sequence. In
contrast, _r_ 2 _,t_ (tool call success) and _r_ 4 _,t_ (memory content quality) are evaluated at the action level,
with each action _at_ = ( _a_ [(1)] _t_ _[,][ · · ·]_ _[, a]_ [(] _t_ _[K][t]_ [)] ) _, t_ _∈{_ 1 _, · · ·_ _, n}_ receiving its own specific reward values




[(1)] _t_ _[,][ · · ·]_ _[, a]_ [(] _t_ _[K][t]_ [)]



with each action _at_ = ( _at_ _[,][ · · ·]_ _[, a]_ _t_ _[t]_ ) _, t_ _∈{_ 1 _, · · ·_ _, n}_ receiving its own specific reward values

based on the success rate of its function calls and the quality of its memory updates.



3.1.3 MEMORY COMPREHENSIVENESS EVALUATION VIA RAG



As outlined in Section 3.1.2, the comprehensiveness of the learned memory is evaluated by a decoupled retrieval-augmented generation (RAG) pipeline, where only the write policy is learnable
and both retrieval and generation components remain fixed. After processing all context chunks, the
agent outputs the terminal memory state _Mn_ . For each question _qj_, evaluation proceeds in three
stages: (1) **Retrieval** : For both semantic memory and episodic memory in _Mn_, we use a fixed
retriever _ϕ_ that selects the top- _k_ memory entries from the corresponding memory pool using the
BM25 retriever. (2) **Generation** : A frozen generator _g_ receives _qj_ and the retrieved support set
and produces an answer _ans_ _[′]_ [=] _[g]_ - _qj,_ _ϕ_ ( _Mn, qj_ )�. The system prompt is presented in Appendix



and produces an answer _ans_ _[′]_ _j_ [=] _[g]_ - _qj,_ _ϕ_ ( _Mn, qj_ )�. The system prompt is presented in Appendix

C.3. (3) **Scoring** : We compare _ans_ _[′]_ _j_ [with the reference] _[ ans][j]_ [to obtain correctness indicators, which]

induce the correctness reward _r_ 1 described in Section 3.1.2.



_j_ [=] _[g]_




- _qj,_ _ϕ_ ( _Mn, qj_ )



3.2 POLICY OPTIMIZATION


We employ Group Relative Policy Optimization (GRPO) (Shao et al., 2024). In section 3.1.2, we
eventually obtain the rewards for each action _at_ at step _t ∈{_ 1 _, · · ·_ _, n}_ . The advantage is:



_At_ = _A_ ( _Mt, ct, at_ ) = _[r][t][ −]_ _[µ]_ [group]



_,_
_σ_ group + _ϵ_




_[t][ −]_ _[µ]_ [group]

[(] _[r]_ [1][ +] _[ r]_ [2] _[,t]_ [ +] _[ βr]_ [3][ +] _[ γr]_ [4] _[,t]_ [)] _[ −]_ _[µ]_ [group]
_σ_ group + _ϵ_ [=] _σ_ group + _ϵ_



where _rt_ is the obtained final reward for _at_ which consists of four different rewards. Then _µ_ group and
_σ_ group are the mean and standard deviation of rewards within the sampled action group, and _ϵ_ is a
small constant for numerical stability. The objective of Mem- _α_ is to maximize the expected reward
over all actions in the sequence:



_G_



_i_ =1



1
_|at|_



_|at|_



_j_ =1



min( _[π][θ]_ [(] _[a][t,j][|M][t][, c][t][, a][t,<j]_ [)]

_π_ old( _at,j|Mt, ct, at,<j_ ) _[A][t][,]_



_J_ ( _θ_ ) = E _C∼P_ ( _C_ ) _,A∼π_ old( _·|C,M_ 0)



_n_



_t_ =1




- 1

_G_



clip( _[π][θ]_ [(] _[a][t,j][|M][t][, c][t][, a][t,<j]_ [)]




_,_ (2)



_π_ old( _at,j|Mt, ct, at,<j_ ) _[,]_ [ 1] _[ −]_ _[ϵ,]_ [ 1 +] _[ ϵ]_ [)] _[A][t]_ [)]



where _C_ is a list of context chunks, and _P_ ( _C_ ) is the total set of possible lists. _M_ 0 is the initial empty
memory, and _A_ is the obtained actions from the chunks _C_ and the initial memory _M_ 0. We discard
the KL term in GRPO to encourage policy exploration.


3.3 MEMORY INSTANTIATION


We design a memory architecture comprising three complementary components, each serving
distinct functional roles in long-term information management. (1) **Core** **Memory** : Following
MemGPT (Packer et al., 2023), we maintain a persistent text summary (maximum 512 tokens)
that remains continuously accessible in the agent’s context. This component serves as a condensed
representation of the most critical information, providing immediate access to essential context
without retrieval overhead. (2) **Semantic Memory** : This component stores factual knowledge and
declarative information about the world and user (Li & Li, 2024). We implement semantic memory as a structured collection of discrete factual statements, where each entry represents an atomic
piece of knowledge that can be independently retrieved and updated. (3) **Episodic Memory** : This
component captures temporally-grounded events and experiences (Li & Li, 2024; Liu et al., 2025;
Anokhin et al., 2024; Pink et al., 2025; Fountas et al., 2024). We implement episodic memory
as a chronologically-organized collection of timestamped events, enabling the agent to maintain
temporal context and reconstruct interaction histories. Figure 3 illustrates the complete memory


5


Preprint


Figure 3: **Memory Architecture** : Core Memory stores a single paragraph (max 512 tokens), while
Semantic Memory and Episodic Memory maintain expandable lists of sentences for facts and timestamped events, respectively.


architecture and the interactions between these components. Each memory component is equipped
with specialized operations tailored to its functional requirements. Semantic and episodic memories
support fine-grained manipulation through three operations: memory ~~i~~ nsert (adding new entries), memory ~~u~~ pdate (modifying existing entries), and memory ~~d~~ elete (removing entries).
In contrast, core memory supports only memory ~~u~~ pdate, requiring complete rewriting to maintain coherence in its condensed representation. This design reflects the different update patterns:
while semantic and episodic memories benefit from incremental modifications, core memory requires holistic revision to preserve its summarization quality. Importantly, our memory architecture
is modular and decoupled from the reinforcement learning framework. Researchers can seamlessly
substitute alternative memory designs—whether simpler or more complex—without modifying the
training methodology, enabling flexible adaptation to diverse application requirements.


3.4 TRAINING DATASET PREPARATION


MemoryAgentBench (Hu et al., 2025) evaluates memory agents across four dimensions: (1) **Accu-**
**rate Retrieval** : extracting correct information from historical data to address queries, encompassing
both single-hop and multi-hop retrieval scenarios; (2) **Test-Time Learning** : acquiring new behaviors or capabilities during deployment; (3) **Long-Range** **Understanding** : integrating information
distributed across multiple segments to answer queries requiring comprehensive sequence analysis; and (4) **Conflict Resolution** : revising, overwriting, or removing previously stored information
when encountering contradictory evidence. Our work focuses on the first three dimensions, excluding Conflict Resolution due to the lack of realistic evaluation benchmarks—existing datasets for
this dimension remain predominantly synthetic and do not adequately capture real-world complexity. We compile a training dataset comprising 4,139 instances, with detailed statistics presented in
Table 6. Each instance consists of multiple context chunks, each of which triggers a distinct write
action, resulting in long action sequences per instance. Given the computational overhead of reinforcement learning and the significant class imbalance in the full dataset, we employ a stratified
sampling approach to create a balanced subset of 562 instances. The resulting distribution is detailed
in Table 7, with comprehensive dataset preprocessing procedures described in Appendix A.1.


4 EXPERIMENTS


4.1 EXPERIMENTAL SETUP


**Evaluation** **Datasets** **and** **Metrics** We follow MemoryAgentBench (Hu et al., 2025) and select
representative datasets from three categories to comprehensively evaluate our approach: (1) Accurate Retrieval: We use Single-Doc, Multi-Doc and LME(S*) as the evaluation tasks. (2) Test-Time
Learning: We evaluate on five multi-class classification datasets: TREC-C, TREC-F, NLU, CLINIC,
BANKING77. (3) Long-Ran-Understanding, we use InfBench-Sum as the summarization task for
evaluation. The detailed introduction of these datasets is in Appendix A.2.


**Baselines** We compare with the following baselines: (1) Long-Context: We simply use Qwen332B as the long-context model. In our experiments, this model always has the maximum context
window as 32k. (2) RAG-Top2: We use BM25 as the retrieval method, and use the question as the
query, retrieve top two chunks from all the previous chunks, and then use Qwen3-32B as the model


6


Preprint

|Method Metric|AR<br>SQuAD HotpotQA PerLTQA|TTL<br>TREC-C NLU Pubmed|LRU<br>BookSum|Avg.|
|---|---|---|---|---|
|Long-Context<br>Perf.<br>Mem.<br>RAG-Top2<br>Perf.<br>Mem.<br>MemAgent<br>Perf.<br>Mem.<br>MEM1<br>Perf.<br>Mem.<br>Mem-_α_<br>Perf.<br>Mem.|0.742<br>**0.852**<br>0.605<br>10.6K<br>9.7K<br>13.1K<br>0.762<br>0.849<br>0.623<br>10.6K<br>9.7K<br>16.7K<br>0.091<br>0.140<br>0.052<br>0.79K<br>0.76K<br>0.29K<br>0.039<br>0.083<br>0.068<br>0.16K<br>0.22K<br>0.14K<br>**0.786**<br>0.832<br>**0.659**<br>10.1k<br>8.7k<br>11.2k|0.623<br>**0.708**<br>0.533<br>3.9K<br>6.1K<br>16.7K<br>0.612<br>0.508<br>**0.570**<br>3.9K<br>6.1K<br>16.7K<br>0.562<br>0.290<br>0.343<br>1.24K<br>0.99K<br>0.94K<br>0.269<br>0.056<br>0.175<br>0.23K<br>0.22K<br>0.08K<br>**0.666**<br>0.658<br>0.545<br>4.0k<br>6.5k<br>12.3k|0.052<br>15.4K<br>0.042<br>15.6K<br>0.103<br>0.59K<br>0.085<br>0.16K<br>**0.187**<br>2.2k|0.588<br>10.8K<br>0.567<br>11.3K<br>0.236<br>0.84K<br>0.111<br>0.17K<br>**0.642**<br>7.9k|



Table 1: Performance and the total number of tokens in the memory across validation datasets.
**Perf.** : task-specific metrics (F1/Accuracy), **Mem.** : memory in thousands of tokens. AR: Accurate
Retrieval, TTL: Time Time Learning, LRU: Long Range Understanding. Same as below.


to answer the questions. (3) MemAgent: We give the agent the specific task description, and then
let the agent go over all the chunks, then ask the question according to the accumulated memory.
(4) MEM1: Given all the chunks, the agent is required to maintain a paragraph of memory, retrieve
some chunks, update the memory, and then answer the question according to the memory. The
implementation details of the baselines are shown in Appendix C.2.


**Implementation Details** Here we present the implementation details of Mem- _α_ to ensure reproducibility. We use verl framework, choose Qwen3-4B as the backbone model [2], train on 32 H100
GPUs with learning ~~r~~ ate as 1e-6, batch ~~s~~ ize as 32, grpo ~~r~~ ollout ~~n~~ as 8 for three days. The complete
training is 205 steps and we choose the best checkpoint according to the validation performance. In
the main experiments, we choose the hyperparameters in Eq.(1) as _β_ = 0 _._ 05 _, γ_ = 1. We show the
performance variations with respect to different hyperparameter configurations in Section 4.4.


4.2 OVERALL PERFORMANCE COMPARISON


We present performance comparisons on validation datasets (matching the training distribution) in
Table 1 and out-of-distribution test datasets (MemoryAgentBench) in Table 2. Our analysis yields
four key findings: (1) Superior performance across tasks: Our method significantly outperforms
existing baselines across all metrics. On MemoryAgentBench (Table 2), we observe particularly
substantial improvements on Accurate Retrieval (AR) and Long-Range Understanding (LRU) tasks,
demonstrating robust generalization to unseen distributions. (2) Efficient memory compression:
Compared to Long-Context and RAG-Top2, our approach reduces memory footprint by approximately 50(3) Structured memory architecture matters: The limited performance of flat memory
baselines (MEM1 and MemAgent), which employ single-paragraph representations, highlights the
inadequacy of unstructured memory for complex information processing. This performance gap validates our hierarchical memory design and reinforcement learning-based optimization strategy. (4)
Strong length generalization: Despite training exclusively on documents averaging _<_ 20K tokens,
our method successfully generalizes to documents exceeding 400K tokens (up to 474K in MemoryAgentBench’s Multi-Doc dataset), demonstrating the robustness of our training framework to
extreme length extrapolation.


4.3 PERFORMANCE BOOST FROM REINFORCEMENT LEARNING


To demonstrate that the performance improvements in Section 4.2 stem from our reinforcement
learning approach rather than merely the memory structure, we conduct ablation studies comparing
three configurations: (1) our RL-tuned model with RL framework Mem- _α_, (2) the base Qwen3-4B
model with our memory framework, and (3) gpt-4.1-mini with our memory framework. Table
3 presents the validation dataset results. The base Qwen3-4B model achieves only 0.389 average
performance—substantially below both RAG-Top2 (0.567) and Long-Context (0.588) from Table
1. While gpt-4.1-mini demonstrates stronger baseline performance (leveraging its superior
instruction-following capabilities), our RL-tuned Mem- _α_ achieves the highest performance, sur

2We also tried Qwen3-8B but the performances are not as good, see details in Appendix C.1.


7


Preprint

|Method Metric|AR<br>Single-Doc Multi-Doc LME(S)|TTL<br>TREC-C NLU TREC-F Clinic Banking77|LRU<br>InfBench|Avg.|
|---|---|---|---|---|
|Long-Context Perf.<br>Mem.<br>RAG-Top2<br>Perf.<br>Mem.<br>MemAgent<br>Perf.<br>Mem.<br>MEM1<br>Perf.<br>Mem.<br>Mem-_α_-4B<br>Perf.<br>Mem.|0.280<br>0.270<br>0.292<br>33K<br>33K<br>33K<br>0.690<br>0.450<br>**0.581**<br>217K<br>474K<br>348K<br>0.070<br>0.160<br>0.050<br>1.02K<br>1.02K<br>0.56K<br>0.070<br>0.180<br>0.090<br>0.30K<br>0.38K<br>0.22K<br>**0.740**<br>**0.680**<br>0.520<br>160K<br>323K<br>127K|0.640<br>**0.740**<br>0.340<br>**0.860**<br>**0.770**<br>33K<br>33K<br>33K<br>33K<br>33K<br>0.690<br>0.650<br>0.210<br>0.700<br>0.750<br>124K<br>134K<br>126K<br>131K<br>128K<br>0.370<br>0.260<br>0.210<br>0.250<br>0.370<br>1.02K<br>1.02K<br>0.77K<br>1.02K<br>1.02K<br>0.180<br>0.000<br>0.000<br>0.090<br>0.000<br>0.16K<br>0.11K<br>0.13K<br>0.28K<br>0.11K<br>**0.710**<br>0.710<br>**0.410**<br>0.730<br>0.700<br>120K<br>142K<br>123K<br>18K<br>133K|0.125<br>33K<br>0.065<br>181K<br>0.043<br>0.73K<br>0.029<br>0.19K<br>**0.129**<br>19K|0.461<br>33K<br>0.502<br>207K<br>0.198<br>0.92K<br>0.071<br>0.21K<br>**0.592**<br>129K|



Table 2: Performance and the total number of tokens in the memory on MemoryAgentBench. **Perf.** :
task-specific metrics (F1/Accuracy), **Mem.** : memory in thousands of tokens.








|Method Metric|AR<br>SQuAD HotpotQA PerLTQA|TTL<br>TREC-C NLU Pubmed|LRU<br>BookSum|Avg.|
|---|---|---|---|---|
|Qwen3-4B<br>Perf.<br>Mem.<br>gpt-4.1-mini<br>Perf.<br>Mem.<br>Qwen3-4B w/<br>Mem-_α_<br>Perf.<br>Mem.|0.338<br>0.637<br>0.557<br>3.3K<br>4.8K<br>9.0K<br>0.426<br>0.749<br>0.492<br>3.8K<br>4.9K<br>3.7K<br>**0.786**<br>**0.832**<br>**0.659**<br>10.1K<br>8.7K<br>11.2K|0.416<br>0.381<br>0.281<br>2.3K<br>2.9K<br>4.4K<br>0.637<br>0.519<br>0.544<br>3.4K<br>5.9K<br>10.6K<br>**0.666**<br>**0.658**<br>**0.545**<br>4.0K<br>6.5K<br>12.3K|0.130<br>0.9K<br>**0.246**<br>1.5K<br>0.187<br>2.2K|0.389<br>3.9K<br>0.517<br>4.8K<br>**0.642**<br>7.9K|



Table 3: Performance and memory consumption comparison across evaluation datasets. **Perf.** : taskspecific metrics (F1/Accuracy), **Mem.** : memory in thousands of tokens. All methods use BM25
retrieval with qwen3-32b. Bold indicates best results.


passing even gpt-4.1-mini. These results provide compelling evidence that our performance
gains originate from the reinforcement learning optimization rather than the memory architecture
alone. The dramatic improvement from base Qwen3-4B (0.389) to Mem- _α_ (0.642) demonstrates
that our RL framework successfully trains the model to effectively utilize the memory structure,
transforming a relatively weak base model into a state-of-the-art memory-augmented agent.


4.4 ABLATION STUDIES


Our reward function, defined in Eq. (1), comprises four components: _r_ 1 (accuracy), _r_ 2 (tool call
format), _r_ 3 (compression), and _r_ 4 (memory content quality). We fix the weights of the primary
components _r_ 1 and _r_ 2 to 1.0, as they directly measure task performance, and tune only the compression weight _β_ and memory content weight _γ_ . Our experiments employ _β_ = 0 _._ 05 and _γ_ = 0 _._ 1
as default values. Table 4 presents ablation studies (The results on the test dataset MemoryAgentBench is shown in Appendix C.4.) examining the impact of these hyperparameters, yielding two
key findings. First, the memory content reward ( _γ_ ) proves critical for effective learning: setting
_γ_ = 0 leads to catastrophic performance degradation, as the model fails to acquire meaningful
memory construction strategies, resulting in disorganized memory representations that cannot support downstream tasks. Second, the compression reward ( _β_ ) exhibits task-dependent effects. While
maintaining _γ_ = 0 _._ 1, increasing _β_ produces shorter memories at the cost of reduced performance.
Notably, comparing configurations ( _β_ = 0 _._ 05 _, γ_ = 0 _._ 1) and ( _β_ = 0 _, γ_ = 0 _._ 1), we observe substantial memory reduction on BookSum (2.2K vs. 4.5K tokens) while maintaining comparable memory
lengths on other datasets. This demonstrates that our chosen configuration ( _β_ = 0 _._ 05 _, γ_ = 0 _._ 1)
achieves an optimal balance between memory efficiency and task performance.


4.5 CASE STUDIES


In this section, we report some memory construction traces obtained from Mem- _α_ and compare
them with baseline approaches to demonstrate the effectiveness of our memory management strategy. Table 5 illustrates critical differences in how different models handle memory construction.
Qwen3-4B exhibits severe limitations: it fails to update the core memory entirely (leaving it empty),
and only maintains a single semantic memory entry, resulting in significant information loss as multiple distinct concepts are compressed into one generic statement. GPT-4.1-mini demonstrates better
semantic organization with three distinct entries, but suffers from inefficient episodic memory man

8


Preprint

|β γ|Metric|AR<br>SQuAD HotpotQA PerLTQA|TTL<br>TREC-C NLU Pubmed|LRU<br>BookSum|Avg.|
|---|---|---|---|---|---|
|0.05<br>0.0<br>0.0<br>0.1<br>0.05<br>0.1<br>0.2<br>0.1<br>0.4<br>0.1|Perf.<br>Mem.<br>Perf.<br>Mem.<br>Perf.<br>Mem.<br>Perf.<br>Mem.<br>Perf.<br>Mem.|0.701<br>0.802<br>0.652<br>9.2K<br>8.2K<br>10.8K<br>0.817<br>**0.853**<br>**0.678**<br>9.7K<br>8.1K<br>11.7K<br>0.786<br>0.832<br>0.659<br>10.1K<br>8.7K<br>11.2K<br>**0.822**<br>0.838<br>0.615<br>9.8K<br>7.8K<br>10.4K<br>0.691<br>0.810<br>0.533<br>8.8K<br>8.1K<br>5.2K|0.423<br>0.542<br>0.501<br>3.0K<br>3.5K<br>11.0K<br>0.605<br>0.629<br>**0.572**<br>3.7K<br>5.4K<br>12.5K<br>**0.666**<br>**0.658**<br>0.545<br>4.0K<br>6.5K<br>12.3K<br>0.558<br>0.176<br>0.401<br>0.4K<br>0.8K<br>0.4K<br>0.475<br>0.405<br>0.455<br>0.7K<br>1.4K<br>1.3K|0.183<br>4.9K<br>0.183<br>4.5K<br>0.187<br>2.2K<br>0.193<br>3.0K<br>**0.201**<br>1.5K|0.543<br>7.5K<br>0.630<br>7.9K<br>**0.642**<br>7.9K<br>0.525<br>4.7K<br>0.509<br>3.6K|



Table 4: Performance and memory consumption comparison across evaluation datasets. **Perf.** : taskspecific metrics (F1/Accuracy), **Mem.** : memory in thousands of tokens. All methods use BM25
retrieval with qwen3-32b. Bold indicates best results.


**Memory**
**Qwen3-4B** **GPT-4.1-mini** **Qwen3-4B w/ Mem-** _α_
**Type**



User is looking to get some advice on
condo living ... looking at options for
condo in the downtown area ... ✓


_2 distinct entries:_

- Noise proof tips ...

- Research methods ...
(✓ Complete)


At 2023/03/08 (Wed) 01:55 user looked to
get some advice on condo living... assistant responded with ...
(✓ Concise and Complete)



**Core** _∅_ ✗ Should not be empty



User is ... focusing on minimizing noise
pollution ... currently looking for condos,
particularly in downtown areas ... ✓


_3 distinct entries:_

- Noise pollution tips

- Neighborhood evaluation

- Research importance
(✓ Complete)


At 2023/03/08 01:55, Asked for noise tips
At 2023/03/08 01:55, Requested neighborhood eval
At 2023/03/08 01:55, Inquired about research
✗ Multiple events with same timestamps,
can be consolidated; Only records user behavior, missing all assistant behaviors.



**Semantic**


**Episodic**



User is seeking advice on ...
noise pollution ... amenities.
✗ Should record more


At 2023/03/08 01:55, User
asked ... Assistant provided ...
(✓ Concise and Complete)



Table 5: Comparison of Memory Management Strategies Across Models


agement by creating multiple entries with identical timestamps that should be merged to conserve
memory space. Meanwhile, GPT-4.1-mini is only storing the user behavior, completely ignoring
the responses from the assistant. In contrast, Mem- _α_ demonstrates better memory construction by
maintaining informative core memory, organizing semantic information into detailed, distinct entries, efficiently consolidating episodic events with the same timestamp into a single comprehensive
entry, paying attention to both the user behavior and the assistant response. This superior memory
organization enables Mem- _α_ to retain more information while using memory space more efficiently.


5 CONCLUSION, LIMITATION AND FUTURE WORK


In this work, we presented Mem- _α_, a reinforcement learning framework that enables LLM agents
to learn effective memory management strategies through interaction and feedback. By moving
beyond pre-defined heuristics, our approach allows agents to discover optimal memory operations
for diverse scenarios through a carefully designed training dataset and reward mechanism based
on question-answering correctness. Our experiments demonstrate that Mem- _α_ achieves significant
improvements over existing memory-augmented baselines, with agents developing robust memory
management strategies that generalize well to much longer interaction patterns. While our framework shows strong performance, several promising directions remain for future exploration. Our
current memory architecture could benefit from integration with more sophisticated systems like
MIRIX, which may provide additional structural advantages for complex reasoning tasks. Furthermore, extending Mem- _α_ from simulated environments to real-world applications would require
connecting the reinforcement learning framework with actual databases and production systems, introducing challenges around latency, scalability, and safety that warrant careful investigation. These
directions represent exciting opportunities to bridge the gap between learned memory management
and practical deployment of memory-augmented LLM agents in real-world applications.


9


Preprint


REFERENCES


Petr Anokhin, Nikita Semenov, Artyom Sorokin, Dmitry Evseev, Andrey Kravchenko, Mikhail Burt
sev, and Evgeny Burnaev. Arigraph: Learning knowledge graph world models with episodic
memory for llm agents. _arXiv preprint arXiv:2407.04363_, 2024.


Ali Behrouz, Peilin Zhong, and Vahab Mirrokni. Titans: Learning to memorize at test time. _arXiv_

_preprint arXiv:2501.00663_, 2024.


Vincent-Pierre Berges, Barlas O˘guz, Daniel Haziza, Wen-tau Yih, Luke Zettlemoyer, and Gargi

Ghosh. Memory layers at scale. _arXiv preprint arXiv:2412.09764_, 2024.


Aydar Bulatov, Yuri Kuratov, and Mikhail S. Burtsev. Recurrent memory transformer. In _NeurIPS_,

2022.


Mikhail S. Burtsev and Grigory V. Sapunov. Memory transformer. _CoRR_, abs/2006.11527, 2020.

[URL https://arxiv.org/abs/2006.11527.](https://arxiv.org/abs/2006.11527)


Linyue Cai, Yuyang Cheng, Xiaoding Shao, Huiming Wang, Yong Zhao, Wei Zhang, and Kang

Li. A scenario-driven cognitive approach to next-generation ai memory. _arXiv_ _preprint_
_arXiv:2509.13235_, 2025.


I˜nigo Casanueva, Tadas Temˇcinas, Daniela Gerz, Matthew Henderson, and Ivan Vuli´c. Efficient in
tent detection with dual sentence encoders. In Tsung-Hsien Wen, Asli Celikyilmaz, Zhou Yu,
Alexandros Papangelis, Mihail Eric, Anuj Kumar, I˜nigo Casanueva, and Rushin Shah (eds.),
_Proceedings_ _of_ _the_ _2nd_ _Workshop_ _on_ _Natural_ _Language_ _Processing_ _for_ _Conversational_ _AI_, pp.
38–45, Online, July 2020. Association for Computational Linguistics. doi: 10.18653/v1/2020.
nlp4convai-1.5. [URL https://aclanthology.org/2020.nlp4convai-1.5/.](https://aclanthology.org/2020.nlp4convai-1.5/)


Prateek Chhikara, Dev Khant, Saket Aryan, Taranjeet Singh, and Deshraj Yadav. Mem0: Building

production-ready ai agents with scalable long-term memory. _arXiv_ _preprint_ _arXiv:2504.19413_,
2025.


Payel Das, Subhajit Chaudhury, Elliot Nelson, Igor Melnyk, Sarathkrishna Swaminathan, Sihui

Dai, Aur´elie C. Lozano, Georgios Kollias, Vijil Chenthamarakshan, Jir´ı Navr´atil, Soham Dan,
and Pin-Yu Chen. Larimar: Large language models with episodic memory control. In _ICML_ .
OpenReview.net, 2024.


Franck Dernoncourt and Ji Young Lee. Pubmed 200k rct: a dataset for sequential sentence classifi
cation in medical abstracts. _arXiv preprint arXiv:1710.06071_, 2017.


Yiming Du, Hongru Wang, Zhengyi Zhao, Bin Liang, Baojun Wang, Wanjun Zhong, Zezhong Wang,

and Kam-Fai Wong. Perltqa: A personal long-term memory dataset for memory classification,
retrieval, and fusion in question answering. In _Proceedings_ _of_ _the_ _10th_ _SIGHAN_ _Workshop_ _on_
_Chinese_ _Language_ _Processing_ _(SIGHAN-10)_, pp. 152–164, Bangkok, Thailand, August 2024.
Association for Computational Linguistics. URL [https://aclanthology.org/2024.](https://aclanthology.org/2024.sighan-1.18/)
[sighan-1.18/.](https://aclanthology.org/2024.sighan-1.18/)


Jinyuan Fang, Yanwen Peng, Xi Zhang, Yingxu Wang, Xinhao Yi, Guibin Zhang, Yi Xu, Bin Wu,

Siwei Liu, Zihao Li, et al. A comprehensive survey of self-evolving ai agents: A new paradigm
bridging foundation models and lifelong agentic systems. _arXiv preprint arXiv:2508.07407_, 2025.


Zafeirios Fountas, Martin A Benfeghoul, Adnan Oomerjee, Fenia Christopoulou, Gerasimos Lam
pouras, Haitham Bou-Ammar, and Jun Wang. Human-like episodic memory for infinite context
llms. _arXiv preprint arXiv:2407.09450_, 2024.


Tao Ge, Jing Hu, Lei Wang, Xun Wang, Si-Qing Chen, and Furu Wei. In-context autoencoder for

context compression in a large language model. _arXiv preprint arXiv:2307.06945_, 2023.


Zexue He, Leonid Karlinsky, Donghyun Kim, Julian McAuley, Dmitry Krotov, and Rogerio Feris.

Camelot: Towards large language models with training-free consolidated associative memory.
_arXiv preprint arXiv:2402.13449_, 2024.


10


Preprint


Cheng-Ping Hsieh, Simeng Sun, Samuel Kriman, Shantanu Acharya, Dima Rekesh, Fei Jia,

Yang Zhang, and Boris Ginsburg. RULER: What’s the Real Context Size of Your LongContext Language Models?, August 2024. [URL http://arxiv.org/abs/2404.06654.](http://arxiv.org/abs/2404.06654)
arXiv:2404.06654 [cs].


Yuanzhe Hu, Yu Wang, and Julian McAuley. Evaluating memory in llm agents via incremental

multi-turn interactions. _arXiv preprint arXiv:2507.05257_, 2025.


Wojciech Kry´sci´nski, Nazneen Rajani, Divyansh Agarwal, Caiming Xiong, and Dragomir Radev.

Booksum: A collection of datasets for long-form narrative summarization. _arXiv_ _preprint_
_arXiv:2105.08209_, 2021.


Stefan Larson, Anish Mahendran, Joseph J. Peper, Christopher Clarke, Andrew Lee, Parker Hill,

Jonathan K. Kummerfeld, Kevin Leach, Michael A. Laurenzano, Lingjia Tang, and Jason Mars.
An evaluation dataset for intent classification and out-of-scope prediction. In Kentaro Inui, Jing
Jiang, Vincent Ng, and Xiaojun Wan (eds.), _Proceedings_ _of_ _the_ _2019_ _Conference_ _on_ _Empir-_
_ical_ _Methods_ _in_ _Natural_ _Language_ _Processing_ _and_ _the_ _9th_ _International_ _Joint_ _Conference_ _on_
_Natural_ _Language_ _Processing_ _(EMNLP-IJCNLP)_, pp. 1311–1316, Hong Kong, China, November 2019. Association for Computational Linguistics. doi: 10.18653/v1/D19-1131. URL
[https://aclanthology.org/D19-1131/.](https://aclanthology.org/D19-1131/)


Jitang Li and Jinzheng Li. Memory, consciousness and large language model. _arXiv_ _preprint_
_arXiv:2401.02509_, 2024.


Xin Li and Dan Roth. Learning question classifiers. In _COLING_ _2002:_ _The_ _19th_ _International_

_Conference_ _on_ _Computational_ _Linguistics_, 2002. URL [https://aclanthology.org/](https://aclanthology.org/C02-1150/)
[C02-1150/.](https://aclanthology.org/C02-1150/)


Yuhong Li, Yingbing Huang, Bowen Yang, Bharat Venkitesh, Acyr Locatelli, Hanchen Ye, Tianle

Cai, Patrick Lewis, and Deming Chen. Snapkv: LLM knows what you are looking for before
generation. _CoRR_, abs/2404.14469, 2024. doi: 10.48550/ARXIV.2404.14469. URL [https:](https://doi.org/10.48550/arXiv.2404.14469)
[//doi.org/10.48550/arXiv.2404.14469.](https://doi.org/10.48550/arXiv.2404.14469)


Kevin Lin, Charlie Snell, Yu Wang, Charles Packer, Sarah Wooders, Ion Stoica, and Joseph E Gonza
lez. Sleep-time compute: Beyond inference scaling at test-time. _arXiv preprint arXiv:2504.13171_,
2025.


WenTao Liu, Ruohua Zhang, Aimin Zhou, Feng Gao, and JiaLi Liu. Echo: A large language model

with temporal episodic memory. _arXiv preprint arXiv:2502.16090_, 2025.


Xingkun Liu, Arash Eshghi, Pawel Swietojanski, and Verena Rieser. Benchmarking natural
language understanding services for building conversational agents, 2019. URL [https://](https://arxiv.org/abs/1903.05566)
[arxiv.org/abs/1903.05566.](https://arxiv.org/abs/1903.05566)


Junru Lu, Siyu An, Mingbao Lin, Gabriele Pergola, Yulan He, Di Yin, Xing Sun, and Yunsheng

Wu. Memochat: Tuning llms to use memos for consistent long-range open-domain conversation.
_arXiv preprint arXiv:2308.08239_, 2023.


Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov, Mohit Bansal, Francesco Barbieri, and

Yuwei Fang. Evaluating very long-term conversational memory of llm agents. _arXiv_ _preprint_
_arXiv:2402.17753_, 2024.


Jiayan Nan, Wenquan Ma, Wenlong Wu, and Yize Chen. Nemori: Self-organizing agent memory

inspired by cognitive science. _arXiv preprint arXiv:2508.03341_, 2025.


Charles Packer, Vivian Fang, Shishir ~~G~~ Patil, Kevin Lin, Sarah Wooders, and Joseph ~~E~~ Gonzalez.

Memgpt: Towards llms as operating systems. 2023.


Mathis Pink, Qinyuan Wu, Vy Ai Vo, Javier Turek, Jianing Mu, Alexander Huth, and Mariya

Toneva. Position: Episodic memory is the missing piece for long-term llm agents. _arXiv preprint_
_arXiv:2502.06975_, 2025.


11


Preprint


Hongjin Qian, Zheng Liu, Peitian Zhang, Kelong Mao, Defu Lian, Zhicheng Dou, and Tiejun

Huang. Memorag: Boosting long context processing with global memory-enhanced retrieval
augmentation. In _Proceedings of the ACM on Web Conference 2025_, pp. 2366–2377, 2025.


Pranav Rajpurkar, Jian Zhang, Konstantin Lopyrev, and Percy Liang. Squad: 100,000+ questions

for machine comprehension of text. _arXiv preprint arXiv:1606.05250_, 2016.


Preston Rasmussen, Pavlo Paliychuk, Travis Beauvais, Jack Ryan, and Daniel Chalef. Zep: A
temporal knowledge graph architecture for agent memory. _arXiv_ _preprint_ _arXiv:2501.13956_,
2025.


Alireza Rezazadeh, Zichao Li, Wei Wei, and Yujia Bao. From isolated conversations to hierarchical

schemas: Dynamic tree memory representation for llms. _arXiv preprint arXiv:2410.14052_, 2024.


Zhihong Shao, Peiyi Wang, Qihao Zhu, Runxin Xu, Junxiao Song, Xiao Bi, Haowei Zhang,

Mingchuan Zhang, YK Li, Yang Wu, et al. Deepseekmath: Pushing the limits of mathematical reasoning in open language models. _arXiv preprint arXiv:2402.03300_, 2024.


Bing Wang, Xinnian Liang, Jian Yang, Hui Huang, Shuangzhi Wu, Peihao Wu, Lu Lu, Zejun Ma,

and Zhoujun Li. Enhancing large language model with self-controlled memory framework. _arXiv_
_preprint arXiv:2304.13343_, 2023.


Yu Wang and Xi Chen. Mirix: Multi-agent memory system for llm-based agents. _arXiv_ _preprint_

_arXiv:2507.07957_, 2025.


Yu Wang, Xinshuang Liu, Xiusi Chen, Sean O’Brien, Junda Wu, and Julian McAuley. Selfupdatable large language models by integrating context into model parameters. In _The Thirteenth_
_International Conference on Learning Representations_ .


Yu Wang, Yifan Gao, Xiusi Chen, Haoming Jiang, Shiyang Li, Jingfeng Yang, Qingyu Yin, Zheng

Li, Xian Li, Bing Yin, et al. Memoryllm: Towards self-updatable large language models. _arXiv_
_preprint arXiv:2402.04624_, 2024.


Yu Wang, Dmitry Krotov, Yuanzhe Hu, Yifan Gao, Wangchunshu Zhou, Julian McAuley, Dan

Gutfreund, Rogerio Feris, and Zexue He. M+: Extending memoryLLM with scalable longterm memory. In _Forty-second_ _International_ _Conference_ _on_ _Machine_ _Learning_, 2025a. URL
[https://openreview.net/forum?id=OcqbkROe8J.](https://openreview.net/forum?id=OcqbkROe8J)


Yu Wang, Chi Han, Tongtong Wu, Xiaoxin He, Wangchunshu Zhou, Nafis Sadeq, Xiusi Chen, Zexue

He, Wei Wang, Gholamreza Haffari, Heng Ji, and Julian J. McAuley. Towards lifespan cognitive
systems. _TMLR_, 2025/02.


Zhenting Wang, Qi Chang, Hemani Patel, Shashank Biju, Cheng-En Wu, Quan Liu, Aolin Ding,

Alireza Rezazadeh, Ankit Shah, Yujia Bao, et al. Mcp-bench: Benchmarking tool-using llm
agents with complex real-world tasks via mcp servers. _arXiv preprint arXiv:2508.20453_, 2025b.


Jiale Wei, Xiang Ying, Tao Gao, Fangyi Bao, Felix Tao, and Jingbo Shang. Ai-native memory 2.0:

Second me. _arXiv preprint arXiv:2503.08102_, 2025.


Bosi Wen, Pei Ke, Xiaotao Gu, Lindong Wu, Hao Huang, Jinfeng Zhou, Wenchuang Li, Binxin Hu,

Wendy Gao, Jiaxing Xu, et al. Benchmarking complex instruction-following with multiple constraints composition. _Advances_ _in_ _Neural_ _Information_ _Processing_ _Systems_, 37:137610–137645,
2024.


Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, and Dong Yu. Longmemeval:

Benchmarking chat assistants on long-term interactive memory. _arXiv preprint arXiv:2410.10813_,
2024.


Derong Xu, Yi Wen, Pengyue Jia, Yingyi Zhang, Yichao Wang, Huifeng Guo, Ruiming Tang, Xi
angyu Zhao, Enhong Chen, Tong Xu, et al. Towards multi-granularity memory association and
selection for long-term conversational agents. _arXiv preprint arXiv:2505.19549_, 2025a.


Wujiang Xu, Kai Mei, Hang Gao, Juntao Tan, Zujie Liang, and Yongfeng Zhang. A-mem: Agentic

memory for llm agents. _arXiv preprint arXiv:2502.12110_, 2025b.


12


Preprint


Sikuan Yan, Xiufeng Yang, Zuchao Huang, Ercong Nie, Zifeng Ding, Zonggen Li, Xiaowen

Ma, Hinrich Sch¨utze, Volker Tresp, and Yunpu Ma. Memory-r1: Enhancing large language
model agents to manage and utilize memories via reinforcement learning. _arXiv_ _preprint_
_arXiv:2508.19828_, 2025.


Zhilin Yang, Peng Qi, Saizheng Zhang, Yoshua Bengio, William W Cohen, Ruslan Salakhutdinov,

and Christopher D Manning. Hotpotqa: A dataset for diverse, explainable multi-hop question
answering. _arXiv preprint arXiv:1809.09600_, 2018.


Yiqun Yao, Naitong Yu, Xiang Li, Xin Jiang, Xuezhi Fang, Wenjia Ma, Xuying Meng, Jing Li, Aixin

Sun, and Yequan Wang. Egomem: Lifelong memory agent for full-duplex omnimodal models.
_arXiv preprint arXiv:2509.11914_, 2025.


Hongli Yu, Tinghong Chen, Jiangtao Feng, Jiangjie Chen, Weinan Dai, Qiying Yu, Ya-Qin Zhang,

Wei-Ying Ma, Jingjing Liu, Mingxuan Wang, et al. Memagent: Reshaping long-context llm with
multi-conv rl-based memory agent. _arXiv preprint arXiv:2507.02259_, 2025.


Danyang Zhang, Lu Chen, Situo Zhang, Hongshen Xu, Zihan Zhao, and Kai Yu. Large language

models are semi-parametric reinforcement learning agents. _Advances in Neural Information Pro-_
_cessing Systems_, 36:78227–78239, 2023a.


Xinrong Zhang, Yingfa Chen, Shengding Hu, Zihang Xu, Junhao Chen, Moo Hao, Xu Han, Zhen

Thai, Shuo Wang, Zhiyuan Liu, et al. _∞_ bench: Extending long context evaluation beyond 100k
tokens. In _Proceedings_ _of_ _the_ _62nd_ _Annual_ _Meeting_ _of_ _the_ _Association_ _for_ _Computational_ _Lin-_
_guistics (Volume 1:_ _Long Papers)_, pp. 15262–15277, 2024.


Zeyu Zhang, Quanyu Dai, Xu Chen, Rui Li, Zhongyang Li, and Zhenhua Dong. Memengine: A

unified and modular library for developing advanced memory of llm-based agents. In _Companion_
_Proceedings of the ACM on Web Conference 2025_, pp. 821–824, 2025a.


Zeyu Zhang, Quanyu Dai, Rui Li, Xiaohe Bo, Xu Chen, and Zhenhua Dong. Learn to
memorize: Optimizing llm-based agents with adaptive memory framework. _arXiv_ _preprint_
_arXiv:2508.16629_, 2025b.


Zhenyu Zhang, Ying Sheng, Tianyi Zhou, Tianlong Chen, Lianmin Zheng, Ruisi Cai, Zhao Song,

Yuandong Tian, Christopher R´e, Clark W. Barrett, Zhangyang Wang, and Beidi Chen. H2O:
heavy-hitter oracle for efficient generative inference of large language models. In _NeurIPS_, 2023b.


Wanjun Zhong, Lianghong Guo, Qiqi Gao, and Yanlin Wang. Memorybank: Enhancing large lan
guage models with long-term memory. _arXiv preprint arXiv:2305.10250_, 2023.


Zijian Zhou, Ao Qu, Zhaoxuan Wu, Sunghwan Kim, Alok Prakash, Daniela Rus, Jinhua Zhao,

Bryan Kian Hsiang Low, and Paul Pu Liang. Mem1: Learning to synergize memory and reasoning
for efficient long-horizon agents. _arXiv preprint arXiv:2506.15841_, 2025.


13


Preprint


A DATASETS DETAILS


A.1 TRAINING DATASET


We organize our training data into three categories based on the memory capabilities they target, as
illustrated in Section 3.4. The detailed dataset statistics are provided in Table 6.


**Training Set** **Validation Set**
**Dataset** **Cat.** **Metric**

**Ins.** **Tok/Ch** **Ch/Ins** **Q/Ins** **Ins.** **Tok/Ch** **Ch/Ins** **Q/Ins**


SQuAD AR SubEM 264 1,078 10.0 95.5 30 1,057 10.0 96.8
HotpotQA AR SubEM 1,966 1,051 9.3 17.0 219 1,052 9.2 17.0
PerLTQA AR SubEM 27 517 23.3 100.0 4 568 23.0 100.0
LME-Train AR LLM-J 45 1,522 15.6 4.0 5 1,576 13.4 4.0
NLU TTL EM 180 610 10.0 100.0 20 606 10.0 100.0
TREC-C TTL EM 180 390 10.0 100.0 20 390 10.0 100.0
PubMed TTL EM 90 1,676 10.0 100.0 10 1,673 10.0 100.0
BookSum LRU KW Hit 1,387 1,916 8.0 1.0 155 1,914 8.1 1.0


**Total** **4,139** - - - **463** - - 

Table 6: Dataset statistics across 8 data sources. Each dataset is evaluated with specific metrics
suitable for its task type. Column abbreviations: Cat. = Category (AR: Accurate Retrieval, TTL:
Test-Time-Learning, LRU: Long Range Understanding); Ins. = Number of Instances; Tok/Ch =
Average Tokens per Chunk; Ch/Ins = Average Chunks per Instance; Q/Ins = Average Questions per
Instance.


**Accurate Retrieval (AR)** This category focuses on training the model’s ability to store and precisely retrieve information from memory. We employ the following datasets:


(1) **SQuAD** (Rajpurkar et al., 2016): We adapt this single-document question answering dataset
by combining multiple documents into single instances. The agent must memorize these documents
and subsequently answer questions based on the constructed memory, testing its ability to accurately
retrieve specific information.


(2) **HotPotQA** (Yang et al., 2018): This multi-document question answering dataset presents the
agent with sequential chunks, each potentially containing multiple documents. The agent must
memorize the documents, identify relationships between them, and answer questions requiring information synthesis across independent chunks.


(3) **PerLTQA** (Du et al., 2024): This dataset challenges the agent to reason over memory chunks
containing both episodic and semantic information about users. The agent must identify relevant
memories, integrate information across different memory types, maintain user profile consistency,
and perform multi-hop reasoning to answer questions.


(4) **LongMemEval-Train** (Wu et al., 2024): We construct a training subset from LongMemEval by
collecting 200 questions from longmemeval ~~o~~ racle.json [3], ensuring no overlap with the evaluation data in MemoryAgentBench. We concatenate haystack dialogues into contexts ranging from
10K to 30K tokens, with each context paired with 4-5 questions, resulting in 50 training samples.


**Test-Time** **Learning** **(TTL)** This category trains the model’s ability to learn new classification
patterns from examples and apply them to new instances. We employ the following datasets:


(1) **PubMed-RCT** (Dernoncourt & Lee, 2017): We adapt this large-scale dataset of randomized controlled trial abstracts from medical literature for test-time learning. Each sentence is originally annotated with semantic roles (Background, Objective, Method, Result, or Conclusion). We transform
this into a classification learning task by segmenting the data into conversational chunks containing
multiple sentence-label pairs as training examples. To evaluate the agent’s ability to learn abstract
patterns, we replace semantic labels with numeric labels (0-4). Each instance ensures coverage of
all five categories across chunks, with questions prompting classification of new examples.


[3(https://huggingface.co/datasets/xiaowu0162/longmemeval/tree/main)](https://huggingface.co/datasets/xiaowu0162/longmemeval/tree/main)


14


Preprint


**Training Set** **Validation Set**
**Dataset** **Cat.** **Metric**

**Ins.** **Ch/Ins** **Tok/Ch** **Q/Ins** **Ins.** **Ch/Ins** **Tok/Ch** **Q/Ins**


SQuAD AR SubEM 100 9.9 1,084.1 94.8 30 10.0 1,057.0 96.8
HotpotQA AR SubEM 100 9.7 1,005.4 16.7 219 9.2 1,051.6 17.0
PerLTQA AR SubEM 27 23.3 517.1 100.0 4 23.0 567.8 100.0
LME-Train AR LLM-J 50 15.4 1527.7 4.0 - - - NLU TTL EM 49 10.0 610.9 100.0 20 10.0 606.2 100.0
TREC-Coarse TTL EM 51 10.0 390.1 100.0 20 10.0 390.2 100.0
PubMed-RCT TTL EM 90 10.0 1,676.1 100.0 10 10.0 1,673.3 100.0
BookSum LRU KW Hit 100 7.8 1,909.7 1.0 155 8.1 1,914.3 1.0


**Total** **562** - - - **463** - - 

Table 7: Dataset statistics across 8 data sources. Each dataset is evaluated with specific metrics
suitable for its task type. Column abbreviations: Cat. = Category (AR: Accurate Retrieval, TTL:
Test-Time-Learning, LRU: Long Range Understanding); Ins. = Number of Instances; Tok/Ch =
Average Number of Tokens per Chunk; Ch/Ins = Average Number of Chunks per Instance; Q/Ins =
Average Questions per Instance.


(2) **NLU** **and** **TREC-C** : These datasets are adapted from MemoryAgentBench (Hu et al., 2025),
containing documents with labeled sentences across 68 classes (NLU) and 6 classes (TREC-C).
Given the original instances contain approximately 100K tokens, we partition them into manageable
chunks. We create 200 instances per dataset, each containing 10 chunks with roughly 500 _∼_ 2,000
tokens distributed across chunks. Each instance preserves all original labels while redistributing
training examples to ensure complete label coverage within each instance.


**Long Range Understanding (LRU)** This category focuses on training the model’s ability to comprehend and summarize information across extended contexts. We employ the following dataset:


**BookSum** (Kry´sci´nski et al., 2021): We utilize the cleaned version of this dataset [4], where each
item consists of a book chapter paired with its summary. We segment each chapter into 10-20
conversational chunks to simulate incremental information processing. For evaluation, we extract
keywords from ground-truth summaries using the prompt shown in Figure 4. The evaluation metric
is the ratio of correctly identified keywords in generated summaries compared to the ground-truth
keyword set.


Due to computational constraints and dataset imbalance, we limit each dataset to a maximum of
100 instances. Despite training for three days with 32 H100 GPUs, we could only process a small
portion of the complete datasets. The final dataset composition and statistics are presented in Table
7. We process every chunk into the format of conversations, with the examples or formats of each
dataset shown in Figure 5.


A.2 EVALUATION DATASET


To comprehensively evaluate our model’s memory capabilities across different scenarios, we adopt
the evaluation framework from MemoryAgentBench (Hu et al., 2025) and select representative
datasets from three core categories. This evaluation suite encompasses 9 datasets with 112 test
instances, designed to assess accurate retrieval, test-time learning, and long-range understanding
capabilities. The detailed statistics for each dataset are presented in Table 8.


**Accurate** **Retrieval** **(AR)** This category evaluates the model’s ability to precisely locate and retrieve specific information from memory. We employ the following datasets:


(1) **RULER-QA1** **(Single-Hop)** and **RULER-QA2** **(Multi-Hop)** : These datasets test single-hop
and multi-hop question answering capabilities respectively. RULER-QA1 (Hsieh et al., 2024) requires direct information retrieval, while RULER-QA2 demands reasoning across multiple memory
chunks to synthesize answers.


[4https://huggingface.co/datasets/ubaada/booksum-complete-cleaned](https://huggingface.co/datasets/ubaada/booksum-complete-cleaned)


15


Preprint



Figure 4: The prompt used to extract keywords in the summaries of BookSum and InfBench-Sum.



**Evaluation**
**Dataset** **Category**

**Metric**



**Test Set**


**# of Ins.** **Avg.** **Chunks** **Avg.** **Tokens** **Avg.** **Q’s**
**per Instance** **per Chunk** **per Instance**



Banking77 ICL Source-based 1 111.0 1,150.3 100.0
Clinic150 ICL Source-based 1 38.0 3,440.5 100.0
NLU ICL EM 1 115.0 1,166.7 100.0
TREC-Coarse ICL EM 1 111.0 1,114.6 100.0
TREC-Fine ICL EM 1 108.0 1,163.3 100.0
InfBench-Sum LRU Source-based 100 88.9 2,034.1 1.0
LongMemEval AR LLM judge 5 218.6 1,591.4 60.0
RULER-QA1 AR Source-based 1 103.0 2,103.9 100.0
RULER-QA2 AR Source-based 1 219.0 2,163.5 100.0


**Total** **112** - - 

Table 8: Test dataset statistics across 9 data sources. Each dataset is evaluated with specific metrics
suitable for its task type.


(2) **LME(S*)** : Originally from LongMemEval (Wu et al., 2024), this dataset was processed by Hu
et al. (2025) to create a more evaluation-efficient format where multiple questions are posed against
fewer contexts, testing the model’s ability to maintain and query complex memory representations
over extended interactions.


**Test-Time Learning (TTL)** This category assesses the model’s ability to learn new classification
patterns from examples and apply them to novel instances. The context used in this dataset includes
thousands of labeled examples. Each example is labeled with a number to indicate the category. We
employ the following datasets:


16


Preprint



Figure 5: The examples in the training dataset. For SQuAD, HotpotQA, PerLTQA, LME-Train, we
show the examples directly; for Test-Time-Learning datasets (Pubmed-RCT, NLU, and Trec-C) and
BookSum, we demonstrate the format for clarity.


(1) **TREC-Coerse** : A question classification dataset with 6 broad categories, testing the model’s
ability to learn coarse-grained classification patterns from limited examples. The original dataset (Li
& Roth, 2002) contains 5,452 training questions and 500 test questions and it is a standard benchmark for QA question-type classification.


(2) **TREC-Fine** : A fine-grained version with 50 specific question types, evaluating the model’s
capacity to distinguish between subtle classification boundaries. The original dataset (Li & Roth,
2002) keeps the same size (5,452 train / 500 test) but refines labels into 50 subtypes under the 6
top-level categories, increasing granularity for few-shot intent learning.


(3) **NLU** : A natural language understanding dataset with 68 intent categories, challenging the model
to learn complex semantic patterns from conversational examples. The original released corpus has
25,715 utterances across 18 scenarios and 68 intents (Liu et al., 2019).


(4) **CLINIC150** : A medical intent classification dataset with 150 categories, testing domain-specific
learning capabilities in healthcare scenarios. The official full split provides 150 in-scope intents
across 10 domains with 100/20/30 train/validation/test examples per intent (Larson et al., 2019).


(5) **Banking77** : A financial services dataset with 77 intent categories, evaluating the model’s ability
to learn domain-specific classification patterns in banking contexts. Casanueva et al. (2020) comprises 13,083 customer-service queries (77 intents) with a 10,003/3,080 train/test split and targets
fine-grained single-domain intent detection.


17


Preprint


**Long** **Range** **Understanding** **(LRU)** This category evaluates the model’s ability to comprehend
and synthesize information across extended contexts. We employ the following dataset:


**InfBench-Sum** : A summarization dataset from InfBench (Zhang et al., 2024), requiring the model
to process long-form content across multiple chunks and generate coherent summaries. This tests
the model’s capacity to maintain contextual understanding over extended sequences and synthesize
information from distributed memory representations. This dataset includes 100 novels, with an
average context length of 172k tokens. During evaluation, the model is required to read a long novel
and generate a corresponding high-level summary.


B FORMAL DEFINITIONS OF REWARD COMPONENTS


This section provides the formal mathematical definitions of the four reward components used in
our reinforcement learning framework.


**Correctness** **Reward** **(** _r_ 1 **)** Given a final memory state _Mn_ after processing all chunks _C_ =
_{c_ 1 _, . . ., cn}_, and a set of questions _Q_ = _{q_ 1 _, . . ., qm}_ with ground truth answers _R_ =
_{r_ 1 _, . . ., rm}_, the correctness reward is defined as:



_r_ 1 = [1]

_m_



_m_


I[metric(ˆ _rj, rj_ )]


_j_ =1



where ˆ _rj_ = _g_ ( _qj, ϕ_ ( _Mn, qj_ )) is the predicted answer generated by the RAG pipeline, metric( _·, ·_ ) is
the dataset-specific evaluation metric (e.g., exact match, F1 score), and I[ _·_ ] is the indicator function.



**Tool** **Call** **Format** **Reward** **(** _r_ 2 **)** For each time step _t_ _∈_ _{_ 1 _, . . ., n}_ with action _at_ =
( _a_ [(1)] _[, . . ., a]_ [(] _[K][t]_ [)] ), define the tool call format correctness indicator:




[(1)] _t_ _[, . . ., a]_ _t_ [(] _[K][t]_ [)]



_t_ _[t]_ ), define the tool call format correctness indicator:



_s_ ( _a_ [(] _t_ _[k]_ [)] ) =




1 if function call _a_ [(] _t_ _[k]_ [)] executes without error

0 otherwise



The tool call format reward at time step _t_ is:


_r_ 2 _,t_ = [1]

_Kt_



_Kt_



_k_ =1



_s_ ( _a_ [(] _t_ _[k]_ [)] )



**Compression** **Reward** **(** _r_ 3 **)** Given the total length of input chunks _lc_ = [�] _i_ _[n]_ =1 _[|][c][i][|]_ [and] [the] [total]

memory length _lm_ = _|Mn|_ (sum of all memory entries), the compression reward is:



_r_ 3 = 1 _−_ _[l][m]_

_lc_



This reward encourages the agent to maintain compact memory representations while preserving
essential information. The reward approaches 1 when memory is highly compressed and approaches
0 when memory size equals input size.



**Memory** **Content** **Reward** **(** _r_ 4 **)** For each time step _t_ _∈_ _{_ 1 _, . . ., n}_ with action _at_ =
( _a_ [(1)] _[, . . ., a]_ [(] _[K][t]_ [)] ), define the validity indicator using a language model judge:




[(1)] _t_ _[, . . ., a]_ _t_ [(] _[K][t]_ [)]



_t_ _[t]_ ), define the validity indicator using a language model judge:



_v_ ( _a_ [(] _t_ _[k]_ [)] ) =




1 if operation _a_ [(] _t_ _[k]_ [)] is semantically valid per LM judge

0 otherwise



The memory content reward at time step _t_ is:



18


Preprint



Figure 6: The universal prompt used in the training of Mem- _α_ .



_r_ 4 _,t_ = [1]

_Kt_



_Kt_



_k_ =1



_v_ ( _a_ [(] _t_ _[k]_ [)] )



The overall reward combines these components as: _r_ = _r_ 1 + _r_ 2 + _βr_ 3 + _γr_ 4, where _r_ 1 and _r_ 3 are
global rewards shared across all time steps, while _r_ 2 and _r_ 4 are computed per time step.


C EXPERIMENTAL DETAILS


C.1 JUSTIFICATION OF BACKBONE MODEL SELECTION


We also evaluated Qwen3-8B but encountered critical instruction-following issues that
made it unsuitable for our experiments. Despite explicit function signature specifications requiring the argument memory ~~t~~ ype to accept only the values ’semantic’,
’core’, or ’episodic’, Qwen3-8B consistently generated malformed function calls such as
new ~~m~~ emory ~~i~~ nsert(memory type=’semantic ~~m~~ emory’), appending an unnecessary ’ ~~m~~ emory’ suffix to the argument values. This systematic failure to adhere to the specified API format occurred reliably across multiple trials. To investigate whether this was a formatting preference
rather than a fundamental limitation, we modified our function signatures to accommodate the
model’s apparent preference, changing the valid arguments to ’semantic ~~m~~ emory’, ’core ~~m~~ emory’,
and ’episodic ~~m~~ emory’. While this adaptation did not impact Qwen3-4B’s performance (which
handled both formats correctly), Qwen3-8B continued to exhibit lower reward values compared to
Qwen3-4B even with this accommodation. This counterintuitive result—where the larger model
demonstrated both poorer instruction-following capabilities and lower overall performance than the
4B variant—led us to exclude Qwen3-8B from our final experiments.


C.2 BASELINE INTRODUCTION AND IMPLEMENTATION DETAILS


We compare with the following baselines:


(1) **Long-Context** : We simply use Qwen3-32B as the long-context model. In our experiments, this
model always has the maximum context window as 32k. For the dataset with a total chunk length
exceeding 32k, we truncate the combined chunk to keep the last 32k tokens.


(2) **RAG-Top2** : We use BM25 as the retrieval method, and use the question as the query, retrieve
top two chunks from all the previous chunks, and then use Qwen3-32B as the model to answer the
questions.


19


Preprint



Figure 7: The prompt used to measure the content of the Core Memory during training.


(3) **MemAgent** : We adopt the code from [https://github.com/BytedTsinghua-SIA/](https://github.com/BytedTsinghua-SIA/MemAgent)
[MemAgent and use the 14B version BytedTsinghua-SIA/RL-MemoryAgent-14B to con-](https://github.com/BytedTsinghua-SIA/MemAgent)
struct the memory.


(4) **MEM1** : [We use the code from https://github.com/MIT-MI/MEM1 and use the model](https://github.com/MIT-MI/MEM1)
[https://huggingface.co/Mem-Lab/Qwen2.5-7B-RL-RAG-Q2-EM-Release](https://huggingface.co/Mem-Lab/Qwen2.5-7B-RL-RAG-Q2-EM-Release) to
construct the memory.


For both baselines MemAgent and MEM1, we let the model go over all the chunks _C_ with the instruction including the task description, then with the obtained memory, we let the model answer
questions. For MemAgent, we use the original model to answer the questions, for MEM1, after obtaining the memory, we use Qwen3-32B as the model to answer the questions based on the question
and the obtained memory.


C.3 PROMPTS USED IN TRAINING


**Instruction** **to** **Memorize** **the** **Chunk** In our training, we use a universal prompt for the whole
dataset, and we show the prompt in Figure 6. During update, when processing each chunk, we use
this prompt to ask the agent to memorize the information in the chunk.


**Prompt to Measure Memory Content** When computing the memory content reward _r_ 4, we use
the model Qwen3-32B as the judge. For Core Memory, Episodic Memory and Semantic Memory,
we use the prompt in Figure 7, 8, 9, respectively.


**Prompt to Answer the Questions** When using the final model Qwen3-32B to answer the questions, we use the prompt as shown in Figure 10.


C.4 ADDITIONAL ABLATION STUDY


In Section 4.4, we show the performance comparison of different _β, γ_ on the validation dataset.
We also compare these settings on the test dataset (MemoryAgentBench), shown in Table 9. The
observations are consistent with Section 4.4.


20


Preprint





Figure 8: The prompt used to measure the content of the Episodic Memory during training.







Figure 9: The prompt used to measure the content of the Semantic Memory during training.

|β γ|Metric|AR<br>Single-Doc Multi-Doc LME(S)|TTL<br>TREC-C NLU TREC-F CLINIC BANKING77|LRU<br>InfBench-Sum|Avg.|
|---|---|---|---|---|---|
|0.05 0.0 <br>0.0<br>0.1 <br>0.05 0.1 <br>0.2<br>0.1 <br>0.4<br>0.1|Perf.<br>Mem.<br> Perf.<br>Mem.<br> Perf.<br>Mem.<br> Perf.<br>Mem.<br> Perf.<br>Mem.|0.420<br>0.340<br>**0.527**<br>86K<br>123K<br>159K<br>**0.770**<br>0.610<br>0.387<br>160K<br>362K<br>47K<br>0.740<br>0.680<br>0.520<br>160K<br>323K<br>127K<br>0.710<br>**0.730**<br>0.367<br>160K<br>344K<br>139K<br>0.590<br>0.610<br>0.453<br>138K<br>312K<br>27K|0.480<br>0.640<br>0.200<br>0.720<br>0.550<br>75K<br>100K<br>65K<br>20K<br>97K<br>0.690<br>**0.730**<br>0.370<br>**0.780**<br>**0.770**<br>124K<br>113K<br>127K<br>47K<br>119K<br>0.710<br>0.710<br>**0.410**<br>0.730<br>0.700<br>120K<br>142K<br>123K<br>18K<br>133K<br>**0.810**<br>0.270<br>0.280<br>0.140<br>0.020<br>3K<br>3K<br>3K<br>1K<br>5K<br>0.500<br>0.360<br>0.190<br>0.170<br>0.380<br>1K<br>1K<br>1K<br>2K<br>1K|0.108<br>54K<br>0.109<br>41K<br>**0.129**<br>19K<br>0.113<br>118K<br>0.119<br>16K|0.445<br>87K<br>0.580<br>127K<br>**0.592**<br>129K<br>0.351<br>87K<br>0.375<br>55K|



Table 9: Performance and memory consumption on MemoryAgentBench. **Perf.** : task-specific metrics (F1/Accuracy), **Mem.** : memory in thousands of tokens. AR: Accurate Retrieval, TTL: Time
Time Learning, LRU: Long Range Understanding. Best performance values are shown in **bold** .


21


Preprint



Figure 10: The prompt used to answer questions in Mem- _α_ .


22


