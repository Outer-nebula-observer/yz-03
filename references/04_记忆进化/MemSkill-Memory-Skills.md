#### **MemSkill: Learning and Evolving Memory Skills for Self-Evolving Agents**

**Haozhen Zhang** [1] **Quanyu Long** [1] **Jianzhu Bao** [1] **Tao Feng** [2] **Weizhi Zhang** [3] **Haodong Yue** [4] **Wenya Wang** [1]



**Abstract**

Most Large Language Model (LLM) agent memory systems rely on a small set of static, handdesigned operations for extracting memory. These
fixed procedures hard-code human priors about
what to store and how to revise memory, making them rigid under diverse interaction patterns
and inefficient on long histories. To this end, we
present **MemSkill**, which reframes these operations as learnable and evolvable memory skills,
structured and reusable routines for extracting,
consolidating, and pruning information from interaction traces. Inspired by the design philosophy of
agent skills, MemSkill employs a _controller_ that
learns to select a small set of relevant skills, paired
with an LLM-based _executor_ that produces skillguided memories. Beyond learning skill selection,
MemSkill introduces a _designer_ that periodically
reviews hard cases where selected skills yield
incorrect or incomplete memories, and evolves
the skill set by proposing refinements and new
skills. Together, MemSkill forms a closed-loop
procedure that improves both the skill-selection
policy and the skill set itself. Experiments on
LoCoMo, LongMemEval, HotpotQA, and ALFWorld demonstrate that MemSkill improves task
performance over strong baselines and generalizes well across settings. Further analyses shed
light on how skills evolve, offering insights toward more adaptive, self-evolving memory management for LLM agents. Code is available at
[https://github.com/ViktorAxelsen/MemSkill](https://github.com/ViktorAxelsen/MemSkill)


**1. Introduction**


As Large Language Model (LLM) agents engage in longer,
open-ended interactions, they must handle growing histories
that are essential yet challenging to leverage, motivating


1Nanyang Technological University 2University of Illinois Urbana-Champaign 3University of Illinois Chicago
4Tsinghua University. Correspondence to: Haozhen
Zhang _<_ haozhen001@e.ntu.edu.sg _>_, Wenya Wang
_<_ wangwy@ntu.edu.sg _>_ .


_Preprint._ _May 26, 2026._



memory for retaining experience and maintaining coherence (Hu et al., 2025). This need has driven rapid progress
in agent memory, including approaches that summarize
and retrieve past interactions or manage external memory
stores (Kang et al., 2025; Chhikara et al., 2025; Packer et al.,
2023; Xu et al., 2025). However, most methods still rely on
static, hand-designed memory mechanisms, including fixed
operation primitives (e.g., add/update/delete/skip) (Wang
et al., 2025a; Yan et al., 2025) and heuristic modules that
govern what to store, how to revise it (Kang et al., 2025;
Fang et al., 2025), and when to prune it. Such designs bake
in strong human assumptions and often suffer under diverse
interaction patterns, scaling poorly as histories grow.


We argue that this formulation fundamentally limits the
adaptability of agent memory. Rather than treating memory
as the output of fixed operations or hand-designed modules,
we propose to elevate memory extraction itself into a _learn-_
_able abstraction_ . Concretely, we view memory construction
as the outcome of applying a small set of generic, reusable
_memory skills_ : structured behaviors that specify when and
how interaction traces should be transformed into memory
and revised over time. This perspective reveals a key bottleneck of prior pipelines: they hard-code memory behaviors
into fixed procedural workflows that interleave heuristics
with LLM-mediated extraction and revision, making them
brittle under distribution shift (Fang et al., 2025).


Under this view, an ideal agent memory system should satisfy three properties. (i) _Minimal reliance on human priors._
Instead of manually encoding what is worth remembering
for a domain (Zhong et al., 2024), memory behaviors should
be shaped by interaction data and updated as task demands
evolve. (ii) _Support for larger extraction granularity._ Many
approaches are tuned to a fixed unit, such as per-turn processing (Fang et al., 2025), and can weaken when applied
to longer spans. A practical system should be able to operate at larger extraction granularity when needed. (iii)
_Skill-conditioned, compositional memory construction._ Existing systems often decompose memory construction into
specialized modules (Kang et al., 2025). In contrast, we
prefer to _select and compose_ a small set of relevant skills for
the current context and apply them in one generation step,
enabling flexible reuse and evolution of memory behaviors.


Based on the above observations, we introduce **MemSkill**,



1


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**



**(a) Prior:** Turn-level + Handcrafted Operations



**(b) MemSkill:** Span-level + Skill-conditioned Generation

































































which reframes memory operations as a learnable and evolvable set of memory skills. MemSkill maintains a shared
_skill bank_, where each skill captures a reusable way to extract, consolidate, or revise memories from interaction text
(Figure 1 shows the structured template of a memory skill).
Given the current context, a _controller_ learns to select a
small set of relevant skills, and an LLM-based _executor_
conditions on these skills to generate skill-guided memories
in one pass. This skill-conditioned formulation is not tied to
a fixed extraction unit and can be applied to different span
lengths when processing long interaction histories.


Crucially, MemSkill goes beyond learning how to use a
fixed set of skills. We introduce a closed-loop evolution
process that alternates between learning to use the current
skill bank and evolving the skill bank itself. Specifically,
we train the _controller_ with reinforcement learning (RL)
using downstream task signals as feedback for skill selection. Periodically, a _designer_ aggregates the hardest cases
produced during training, selects representative failures, and
uses an LLM to refine existing skills and propose new ones.
After each evolution step, the controller continues training
on the evolved skill bank, with additional exploration to
facilitate adopting newly introduced skills. Overall, this
process gradually strengthens both the skill selection policy
and the evolving skill bank, moving toward a more adaptive
memory management system driven by interaction data.


Experiments on LoCoMo, LongMemEval, HotpotQA, and
ALFWorld show that MemSkill consistently improves task
performance and generalizes well. Further analyses vali


date key components and showcase representative evolved
skills, offering insights toward more adaptive, self-evolving
memory management for LLM agents.


Our contributions can be summarized as follows.


  - We propose **MemSkill**, an agent memory method that
represents memory operations as an evolving skill
bank, where each skill provides reusable guidance for
selecting, extracting, and organizing useful memories.
This turns memory construction from a fixed handcrafted pipeline into an adaptive skill-conditioned generation process.


  - We introduce a closed-loop optimization recipe that
combines reinforcement learning for skill selection
with LLM-guided skill evolution from hard cases, enabling continual refinement of the skill bank and taking
a step toward self-evolving agent memory systems.


  - We evaluate MemSkill on LoCoMo, LongMemEval,
HotpotQA, and ALFWorld, demonstrating consistent
gains and strong transfer ability across conversational
QA and embodied interaction settings, offering insights
for self-evolving memory in LLM agents.


**2. Related Work**


**2.1. LLM Agent Memory Systems**


Prior work on agent memory focuses on constructing external memories from interaction histories and leveraging them



2


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**



to support downstream reasoning and decision making. Typical pipelines periodically extract salient information into a
memory store, retrieve relevant entries for a new query, and
update the store via consolidation or pruning (Kang et al.,
2025; Zhong et al., 2024; Xu et al., 2025; Packer et al., 2023;
Chhikara et al., 2025; Fang et al., 2025). More recently,
learning-based approaches such as Memory-R1 (Yan et al.,
2025) and Mem- _α_ (Wang et al., 2025a) optimize memory
management with reinforcement learning using downstream
task signals. Despite this progress, memory management
is still largely governed by static, hand-crafted routines for
extraction, consolidation, and pruning.


Several concurrent works also explore self-evolving memory in agent settings, but differ from our focus. EvoMemory (Wei et al., 2025) evaluates streaming memory
evolution, MemEvolve (Zhang et al., 2025b) optimizes
predefined memory architectures, MemGen (Zhang et al.,
2025a) targets latent memory for reasoning, and ReasoningBank (Ouyang et al., 2025) distills reasoning strategies from
experience. By contrast, we target the evolution of memory
skills themselves, enabling the system to refine and grow
reusable memory operations over time.


**2.2. Self-Evolving LLM Agents**


Recent work on self-evolving LLM agents studies how
agents can improve from interaction experience with minimal manual supervision. ExpeL (Zhao et al., 2024) distills
trajectories into editable natural-language insights and retrieves relevant experiences to guide future decisions, while
EvolveR (Wu et al., 2025) formalizes an experience lifecycle that consolidates interactions into reusable principles
and closes the loop with reinforcement learning updates. A
complementary line reduces reliance on curated data via
self-play style curricula: Absolute Zero Reasoner (Zhao
et al., 2025) trains a proposer and solver with verifiable rewards from a code executor, and Multi-Agent Evolve (Chen
et al., 2025) extends this to a proposer solver judge triad with
LLM-based evaluation; R-Zero (Huang et al., 2025) follows
a similar challenger solver co-evolution pattern. Beyond curricula, systems such as AgentEvolver (Zhai et al., 2025) and
RAGEN (Wang et al., 2025b) study efficient agent learning dynamics and stabilization in multi-turn RL settings,
while ADAS (Hu et al., 2024) and AlphaEvolve (Novikov
et al., 2025) explore automated discovery and evolutionary
improvement of agent designs. Finally, SkillWeaver (Zheng
et al., 2025) shows that agents can discover and refine
reusable skills for web interaction. In contrast, our focus
is on self-evolving _memory skills_ that govern how agents
construct and revise memories over time.



**3. Method**


In this section, we first provide an overview of MemSkill
(Section 3.1), then detail the _skill_ _bank_ (Section 3.2) and
the three core components ( _controller_ (Section 3.3.1), _ex-_
_ecutor_ (Section 3.3.2), and _designer_ (Section 3.4)), and
finally summarize the closed-loop optimization procedure
that alternates between learning to use the current skills and
evolving the skill bank from hard cases (Section 3.5).


**3.1. Overview**


As shown in Figure 2, we propose **MemSkill**, which optimizes agent memory through two intertwined processes.
First, it **learns to use a given skill bank** : a controller selects context-relevant skills, and an executor applies them
to produce memory updates. Second, it **improves the skill**
**bank itself** : a designer periodically revises existing skills
and adds new ones based on challenging training cases.


To disentangle trace-specific memories from reusable memory management knowledge, MemSkill maintains two
stores. The _memory bank_ is trace-specific and stores memories for each training trace (e.g., a long dialogue). In contrast,
the _skill bank_ is shared across traces and contains reusable
memory skills. During training, the controller and executor
build each trace’s memory bank, while the designer updates
the shared skill bank between phases. This alternating procedure gradually improves both the skill selection policy
and the skill bank for memory construction.


**3.2. Skill Bank**


As shown in Figure 2, a _memory skill_ specifies a reusable
memory operation as structured guidance, including when
it is applicable and how it should be applied to the current
context. Concretely, each skill _s_ _∈S_ contains (i) a short
_description_ for skill representation and selection, and (ii) a
detailed _content_ specification that instructs the executor on
memory extraction or revision.


We start from a minimal set of general-purpose primitives
to ensure a stable and functional initialization. Specifically,
we initialize the skill bank with four basic skills corresponding to canonical memory operations: INSERT, UPDATE,
DELETE, and SKIP. Starting from this minimal set, the
designer progressively refines existing skills and expands
the bank by proposing new skills that address uncovered
failure modes. (Appendix C details skill description)


**3.3. Learning to Use Memory Skills**


In this part, we describe how MemSkill learns to use memory skills, covering (i) the skill-selection policy and (ii)
skill-conditioned memory construction.



3


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**






















































































































































|Failu|re Ca<br>Fail|se 2<br>ure C|ase 3<br>ilure C|Col5|
|---|---|---|---|---|
|<br> <br>~~**Failu**~~|~~ion~~<br> <br>~~ Predi~~<br> <br>|~~ tion~~<br> <br> <br>~~**Fa**~~|~~ tion~~<br> <br> <br>~~**Fa**~~|~~ tion~~<br> <br> <br>~~**Fa**~~|
|<br> <br>~~**Failu**~~|e<br> h<br> <br>ard Sc<br>und Tru<br>il Coun<br>**......**<br>Mod<br>Re<br>Gr<br>F|<br> ore<br> th<br> t<br>e~~l Prediction~~<br>ward Score<br>ound Truth<br>ail Count<br>**......**<br> <br>Model Pred<br>Reward S<br>Ground T<br>Fail Cou<br>**.....**|<br> ore<br> th<br> t<br>e~~l Prediction~~<br>ward Score<br>ound Truth<br>ail Count<br>**......**<br> <br>Model Pred<br>Reward S<br>Ground T<br>Fail Cou<br>**.....**|<br> iction<br> core<br> ruth<br> nt<br>|



_Figure 2._ **MemSkill architecture overview.** Given an interaction trace, MemSkill processes it span by span: the controller selects a
Top- _K_ subset of skills from a shared _skill bank_ conditioned on the current text span and retrieved memories, and an LLM executor applies
the selected skills in one pass to update the trace-specific _memory bank_ . The constructed memory is then evaluated on memory-dependent
training queries to provide task reward for optimizing the controller, while query-centric failures are logged into a sliding hard-case buffer.
Periodically, the designer mines representative hard cases to refine existing skills and propose new ones, yielding alternating phases of
skill usage and skill evolution. More skill case study can be found in Section 4.5 and Appendix C.



3.3.1. CONTROLLER: SKILL SELECTION POLICY


To enable effective skill selection as the _skill bank_ evolves,
we introduce a controller that selects a small set of relevant
memory skills for the current context. At each memory
construction step, **we update memory at the span level** :
we split each interaction trace (e.g., a dialogue) into fixedlength contiguous spans by token count and process them
sequentially. For each span, the controller conditions its
selection on (i) the current text span and (ii) the retrieved
existing memories from the current trace’s memory bank
(empty for initial span), rather than operating turn by turn.


To remain compatible with a variable-size skill bank as it
continuously evolves, the controller scores each skill by
measuring the semantic distance between the current state
and skill representations, supporting a changing skill set
while staying sensitive to what is already stored in memory.


**State and skill representations.** Formally, let _xt_ denote the
current text span at step _t_, and let _Mt_ = _{mt,_ 1 _, . . ., mt,R}_
be the retrieved memories from the current trace’s memory
bank. We first encode _xt_ and _Mt_ with a fixed embedding
model _e_ ( _·_ ), aggregate the retrieved memory embeddings by
element-wise averaging, and concatenate it with the span
embedding:



ory embedding, and is omitted when _Mt_ is empty. Here,
_ui_ is the representation of skill _si_ _∈St_, computed from its
description as a compact and stable semantic signal rather
than the full skill content. The embedding model _e_ ( _·_ ) is
shared and fixed, while _fθ_ [ctx] and _fθ_ [skill] are trainable neural

networks in the controller for learnable skill selection.


**Compatibility** **with** **an** **evolving** **skill** **bank.** Instead of
producing a fixed-dimensional action head tied to a fixed
number of skills, the controller concatenates the state representation with each candidate skill representation and applies a shared scorer to all such state-skill pairs in parallel:



_θ_ [ctx] and _fθ_ [skill]



_ht_ = _fθ_ [ctx]



_θ_ [ctx] ([ _e_ ( _xt_ ); _m_ ¯ _t_ ]) _,_ _ui_ = _fθ_ [skill]



_θ_ ( _e_ (desc( _si_ ))) _,_



(1)
where _m_ ¯ _t_ = [1] - _Rr_ =1 _[e]_ [(] _[m][t,r]_ [)][ denotes the aggregated mem-]



_zt,i_ = _fθ_ [score] ([ _ht_ ; _ui_ ]) _,_ _pθ_ ( _i | ht_ ) = softmax( _zt_ ) _i,_

(2)
where _fθ_ [score] is a trainable neural network, and _zt_ _∈_ R _[|S][t][|]_

adapts as the skill bank evolves.


**Top-** _K_ **skill selection.** Given the categorical distribution
_pθ_ ( _i_ _|_ _ht_ ) over the current skill bank _St_, the controller
selects an ordered Top- _K_ set of skills _At_ = ( _at,_ 1 _, . . ., at,K_ )
(e.g., via Gumbel-Top- _K_ (Kool et al., 2019)), and only
passes the selected skills to the executor, keeping the skill
context concise and relevant.


3.3.2. EXECUTOR: SKILL-CONDITIONED MEMORY
EXTRACTION


Given the selected skills _At_, the fixed executor constructs
memory updates by conditioning an LLM on (i) the current



_R_




- _R_
_r_ =1 _[e]_ [(] _[m][t,r]_ [)][ denotes the aggregated mem-]



4


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**



text span _xt_, (ii) the retrieved memory items _Mt_, and (iii)
the selected skills _At_ . This mirrors skill-conditioned inference in agent systems, where a small set of relevant skills
is provided to guide behavior for the current context. The
executor produces structured memory updates, which are
parsed and applied to the trace’s memory bank. By composing several skills for the same text span and extracting
memory in one LLM call, MemSkill reduces repeated perturn processing and scales better to long interaction histories.
Appendix D details the executor prompt.


3.3.3. CONTROLLER OPTIMIZATION


We train the controller with reinforcement learning, using
downstream task performance as feedback for its skill selections. For each training trace, the controller makes a
sequence of Top- _K_ selections while the executor incrementally builds the trace-specific memory bank. After construction, we evaluate the resulting memory bank on the trace’s
memory-dependent training queries and use the resulting
task performance as the reward (e.g., F1 or success rate).


A key technical detail is that the controller’s action is an
ordered Top- _K list_ selected without replacement, rather than
a single discrete action. We therefore compute the joint logprobability log _πθ_ ( _At_ _| ht_ ) under this selection process and
use it in standard policy-gradient objectives (Schulman et al.,
2017) via importance weighting and clipping. Concretely,
for _At_ = ( _at,_ 1 _, . . ., at,K_ ), the joint probability is



using a difficulty score that increases when task performance
is low and when the same case fails repeatedly. This produces a compact set of high-value cases for skill evolution
while preserving diversity across error types.


**Two-stage skill evolution.** The designer updates the skill
bank in two stages. First, it employs an LLM to analyze
the selected hard cases and identify what memory behaviors
are missing or mis-specified. Second, it uses the resulting
analysis to propose concrete edits to existing skills and to
introduce new skills. We keep the designer description
concise and provide prompts in Appendix D.


Notably, we maintain snapshots of the best-performing skill
bank and roll back if an update degrades performance, with
early stopping when repeated designer updates fail to improve the training signal. After each evolution step, we
also briefly increase exploration by biasing selection toward
newly introduced skills, encouraging the controller to try
them and facilitating efficient learning of their utility. Due
to page limit, more details about the designer can be found
in Appendix B.2.


**3.5. Closed-Loop Optimization**


MemSkill alternates between (i) learning to select and apply
skills to build memory banks and (ii) evolving the skill
bank from hard cases mined during training. Each cycle
begins with controller training on the current skill bank,
where the executor constructs memories and accumulates
challenging cases. The designer then updates the skill bank
using representative hard cases, optionally rolling back to
a prior snapshot if performance regresses. The next cycle
resumes controller training on the updated skill bank, with
additional exploration to encourage early use of new skills.
Over cycles, this closed loop gradually improves how skills
are selected, applied, and refined for memory construction.


**4. Experiments**


**4.1. Experiment Setup**


**Datasets** **and** **Baselines.** We evaluate MemSkill on four
benchmarks: LoCoMo (Maharana et al., 2024), LongMemEval (Wu et al., 2024), HotpotQA (Yang et al., 2018),
and ALFWorld (Shridhar et al., 2020), where HotpotQA
is used in Section 4.3 to study skill transfer under distribution shift. The remaining three benchmarks cover two
representative settings. (i) _Conversational Benchmarks_ include LoCoMo and LongMemEval, which evaluate memory
construction from long, dialogue-style interaction histories.
For these datasets, we report F1-score (F1) and an LLMbased judge score (L-J). (ii) _Embodied Interactive Tasks_ are
evaluated on ALFWorld with two standard subsets, ALFSeen and ALF-Unseen, and we report success rate (SR)
and the number of environment interaction steps (#Stps).



_πθ_ ( _At_ _| ht_ ) =



_K_



_j_ =1



_pθ_ ( _at,j_ _| ht_ )

(3)

1 _−_ [�] _ℓ<j_ _[p][θ]_ [(] _[a][t,ℓ]_ _[|][ h][t]_ [)] _[,]_



which reduces to the single-action case when _K_ = 1. Appendix B.4 gives implementation details.


**3.4. Skill Evolution through Designer Feedback**


Beyond learning to select from a fixed set of skills, MemSkill evolves the skill bank using an LLM-based designer
(fixed) that operates periodically during training.


**Hard-case buffer.** During controller training, we maintain
a sliding-window buffer of challenging cases observed recently. Each case is query-centric, recording the query along
with its ground-truth and metadata (e.g., retrieved memories
and model prediction), as well as summary statistics such
as task performance and the number of failures observed so
far. The buffer uses two expiration rules: cases are removed
if they become too old (exceeding a maximum training step
gap) or if the buffer reaches its capacity limit, which tracks
recent failure patterns without growing unbounded.


**Selecting representative hard cases.** To focus designer updates on impactful failures, we cluster cases (e.g., KMeans)
into groups that naturally reflect different query or error
types. Within each cluster, we prioritize representative cases



5


**Model** **Methods**



**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


_Table 1._ **Main comparison results on LoCoMo, LongMemEval, and ALFWorld.**


**Conversational Benchmarks** **Embodied Interactive Tasks**


**LoCoMo**   - **LongMemEval** **Avg.** **ALF-Seen** _[†]_ **ALF-Unseen** _[†]_ **Avg.**



|F1 L-J F1 L-J L-J|SR #Stps↓ SR #Stps↓ SR|
|---|---|
|**LLaMA3.3**<br>**70B-Instruct**<br>No-Memory<br>-<br>-<br>-<br>-<br>-<br>CoN<br>30.86<br>41.72<br>30.78<br>56.44<br>49.08<br>ReadAgent<br>28.63<br>38.25<br>24.48<br>42.62<br>40.44<br>MemoryBank<br>36.80<br>44.43<br>30.56<br>41.96<br>43.20<br>A-MEM<br>39.39<br>49.71<br>25.83<br>38.04<br>43.88<br>Mem0<br>25.48<br>34.58<br>30.25<br>46.81<br>40.70<br>LangMem<br>30.91<br>35.82<br>18.36<br>24.35<br>30.09<br>MemoryOS<br>41.39<br>48.64<br>17.59<br>39.83<br>44.24<br>**MemSkill**<br>**44.21**<br>**53.82**<br>**31.12**<br>**60.89**<br>**57.36**|62.14<br>26.10<br>73.88<br>21.36<br>68.01<br>75.00<br>19.15<br>80.60<br>17.38<br>77.80<br>62.86<br>26.14<br>71.64<br>22.88<br>67.25<br>60.71<br>28.23<br>66.42<br>24.64<br>63.57<br>62.86<br>27.53<br>70.15<br>23.79<br>66.51<br>74.29<br>19.77<br>81.34<br>17.15<br>77.82<br>72.86<br>21.25<br>79.85<br>18.30<br>76.36<br>57.86<br>27.94<br>65.67<br>24.46<br>61.77<br>**77.14**<br>**18.91**<br>**83.58**<br>**16.63**<br>**80.36**|
|▲**Qwen3-Next**<br>**80B-A3B-Instruct**<br>No-Memory<br>-<br>-<br>-<br>-<br>-<br>CoN<br>38.46<br>50.96<br>**29.19**<br>44.06<br>47.51<br>ReadAgent<br>25.89<br>34.26<br>24.13<br>42.25<br>38.26<br>MemoryBank<br>29.56<br>44.15<br>8.45<br>26.37<br>35.26<br>A-MEM<br>36.43<br>50.30<br>13.84<br>36.59<br>43.45<br>Mem0<br>23.29<br>33.68<br>27.36<br>46.20<br>39.94<br>LangMem<br>28.17<br>32.94<br>18.35<br>23.86<br>28.40<br>MemoryOS<br>39.86<br>47.37<br>15.97<br>39.25<br>43.31<br>**MemSkill**<br>**42.08**<br>**54.14**<br>25.29<br>**60.40**<br>**57.27**|63.57<br>24.61<br>60.45<br>26.57<br>62.01<br>77.14<br>17.59<br>70.90<br>20.74<br>74.02<br>73.57<br>20.21<br>65.67<br>23.28<br>69.62<br>63.57<br>23.68<br>52.24<br>29.01<br>57.91<br>55.71<br>27.42<br>54.48<br>28.60<br>55.10<br>71.43<br>19.89<br>64.93<br>23.32<br>68.18<br>73.57<br>19.76<br>64.18<br>23.58<br>68.88<br>62.14<br>25.64<br>50.75<br>30.35<br>56.45<br>**85.71**<br>**13.84**<br>**76.87**<br>**18.16**<br>**81.29**|


**Bold** indicates the best score within each base model block; [▲] indicates transfer evaluation only.

_†_ indicates evaluation with in-context demonstrations. Appendix A reports more baselines and datasets.



Appendix B.1 provides dataset splits.


We compare MemSkill against several strong baselines: (1)
**No-Memory**, which answers directly without an external
memory; (2) **CoN** (Yu et al., 2024); (3) **ReadAgent** (Lee
et al., 2024); (4) **MemoryBank** (Zhong et al., 2024); (5)
**A-MEM** (Xu et al., 2025); (6) **Mem0** (Chhikara et al.,
2025); (7) **LangMem** (LangChain, 2025); and (8) **Memo-**
**ryOS** (Kang et al., 2025). Overall, this setup spans diverse
benchmarks and baselines, enabling a broad and consistent
comparison across diverse settings.



**Implementation Details.** We instantiate _f_ [ctx]



_θ_ [ctx], _fθ_ [skill]



**Implementation Details.** We instantiate _fθ_, _fθ_, and

_fθ_ [score] as independent lightweight multilayer perceptrons

(MLPs), and use LLaMA-3.3-70B-Instruct (Grattafiori et al.,
2024) and Qwen3-Next-80B-A3B-Instruct (Yang et al.,
2025) as the base LLMs, accessed through an API service.
Unless otherwise specified, we train MemSkill on LLaMA
and use Qwen only for transfer experiments. LongMemEval
is also evaluated in a transfer setting, where we directly apply the skills learned on LoCoMo without further training.


During training, we optimize the controller with PPO (Schulman et al., 2017). MemSkill constructs memory at the span
level; on conversational benchmarks, each dialogue session is a processing unit, and the controller selects _K_ =3



skills per unit. We instantiate _e_ ( _·_ ) with Qwen3-Embedding0.6B (Yang et al., 2025), also used as the memory retriever,
and retrieve up to 20 memory items for MemSkill and all
baselines for consistency. For the designer, skill evolution is
triggered every 100 training steps, with at most 3 skill edits
per evolution round. For ALFWorld, we cap environment
interactions at 50 steps.


At evaluation time, we keep the same span-level formulation
and set the span/chunk size to 512 by default, while keeping
the overall procedure unchanged. Unless otherwise specified, we use _K_ =7 skills for LoCoMo and LongMemEval
at evaluation time, and _K_ =5 for ALFWorld. Additional
implementation details and prompt templates are provided
in Appendix B and Appendix D.


**4.2. Comparison Experiments**


**Effectiveness** **across** **conversational** **and** **embodied** **set-**
**tings.** Table 1 summarizes the main comparison results on
LoCoMo, LongMemEval, and ALFWorld. Across these
datasets, MemSkill achieves the strongest overall performance among all compared methods. On conversational
benchmarks, MemSkill attains the best LLM-judge scores
on both LoCoMo and LongMemEval within each base


6


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**



68


66


64



200 Docs Concatenated





68

66

64

62

60





100 Docs Concatenated



~~67.57~~



50 Docs Concatenated


66.02
~~65.63~~

64.85

64.06





72


70


68


66





under more pronounced distribution shifts.






**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


**LoCoMo (Conversational Skills)** **ALFWorld (Embodied Task Skills)**



















_Figure 4._ **Case study.** We show representative evolved skills learned on LoCoMo and ALFWorld.



sistently degrades performance, confirming that MemSkill
benefits from both targeted skill selection and skill evolution. In particular, random skill selection leads to a clear
drop from the default setting, highlighting the importance
of learning to choose relevant skills rather than providing
arbitrary ones. Disabling the designer yields an even larger
degradation, especially under Qwen, suggesting that evolving the skill bank is important for learning reusable memory
behaviors that generalize beyond a fixed, manually specified operation set. Finally, refinement-only consistently
outperforms static skills on both LLaMA and Qwen, with a
particularly large gain under Qwen, yet remains below the
default setting, indicating that introducing new skills yields
additional benefits beyond refining the initial primitives.


_Table 2._ **LoCoMo ablation** (L-J).


**Variant** **LLaMA** **Qwen**


**MemSkill** **53.82** **54.14**
w/o Ctrl 48.43 42.84
w/o Des 46.50 36.15
Ref.-only 47.45 48.88


**4.5. Discussion**


**Case** **study.** To make MemSkill more interpretable, we
inspect the final evolved skill bank and report representative
skills from LoCoMo and ALFWorld. As shown in Figure 4,
the learned skills show clear domain specialization. LoCoMo skills emphasize temporal context and activity details,
suggesting that dialogue memory benefits from lightweight
event structure. In contrast, ALFWorld skills focus on ac


tion constraints and object locations, showing that embodied
tasks require actionable world-state memories for multi-step
execution. Overall, the evolved skill bank reflects recurring
information needs from the data, rather than a fixed notion
of what to remember.


Together, these skills show that MemSkill distills and refines
reusable memory behaviors from interaction data, reducing
reliance on hand-crafted memory designs. Appendix C
gives more examples.


**Cost** **analysis.** We conduct a runtime cost analysis on
LoCoMo using LLaMA, additionally including **Light-**
**Mem** (Fang et al., 2025) as a baseline. We report L-J,
input/output tokens, and LLM calls, accounting for all
inference-time LLM calls from memory extraction and
query answering, excluding LLM-judge calls used only
for evaluation. Since MemSkill learns and evolves the skill
bank before deployment, this preparation cost is amortized
over repeated use, with further evolution triggered only occasionally. We therefore focus on runtime cost as the practical
efficiency measure. At inference time, MemSkill constructs
memory at the span level rather than turn by turn, substantially reducing LLM calls. To show this trade-off, we vary
the span size (SS) and report the quality-cost frontier in
Table 3.


MemSkill achieves a stronger quality-cost trade-off than
prior baselines. With moderate span sizes, it obtains higher
L-J scores while using fewer input/output tokens and LLM
calls. In particular, Span Size=512 offers the best overall
balance, achieving the highest quality with much lower
runtime cost than MemoryOS, A-MEM, and LightMem.
This suggests span-level construction reduces redundant



8


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**



LLM calls without sacrificing memory quality. Larger span
sizes reduce cost, but may hurt performance because each
memory update covers a longer span. This makes span
size a knob for adapting MemSkill to different efficiency
requirements.


_Table 3._ **Cost analysis on LoCoMo.**


**Setting** **L-J** **In (K)** **Out (K)** **Calls**


MemoryOS 48.64 1013 165 1288
A-MEM 49.71 2850 362 1548
LightMem 51.95 789 209 685


**5. Conclusion**


We present **MemSkill**, an agent memory method that reframes memory operations as an evolving skill bank. MemSkill learns to select relevant skills for each context span
and conditions an LLM executor on them to construct skillguided memories. Beyond learning to use a fixed skill set,
MemSkill introduces a designer that improves the skill bank
by refining existing skills and proposing new ones from
challenging cases, forming a closed-loop training procedure. Experiments on LoCoMo, LongMemEval, HotpotQA,
and ALFWorld show consistent improvements over strong
baselines, while qualitative analyses illustrate how evolving
skills enable more adaptive memory management. We hope
MemSkill encourages future work on self-improving agent
memory systems that learn not only to use memory, but
also to continually improve how memory is constructed and
maintained.


**Acknowledgements**


This research/project is supported by the NTU Start-Up
Grant (#023284-00001), Singapore, and the MOE AcRF
Tier 1 Seed Grant (RS37/24, #025041-00001), Singapore.


**References**


Chen, Y., Wang, Y., Zhu, S., Yu, H., Feng, T., Zhang,

M., Patwary, M., and You, J. Multi-agent evolve:
Llm self-improve through co-evolution. _arXiv preprint_
_arXiv:2510.23595_, 2025.


Chhikara, P., Khant, D., Aryan, S., Singh, T., and Yadav, D.

Mem0: Building production-ready ai agents with scalable
long-term memory. _arXiv_ _preprint_ _arXiv:2504.19413_,
2025.


Fang, J., Deng, X., Xu, H., Jiang, Z., Tang, Y., Xu, Z.,



Deng, S., Yao, Y., Wang, M., Qiao, S., et al. Lightmem:
Lightweight and efficient memory-augmented generation.
_arXiv preprint arXiv:2510.18866_, 2025.


Grattafiori, A., Dubey, A., Jauhri, A., Pandey, A., Kadian,

A., Al-Dahle, A., Letman, A., Mathur, A., Schelten, A.,
Vaughan, A., et al. The llama 3 herd of models. _arXiv_
_preprint arXiv:2407.21783_, 2024.


Hu, S., Lu, C., and Clune, J. Automated design of agentic

systems. _arXiv preprint arXiv:2408.08435_, 2024.


Hu, Y., Liu, S., Yue, Y., Zhang, G., Liu, B., Zhu, F., Lin, J.,

Guo, H., Dou, S., Xi, Z., et al. Memory in the age of ai
agents. _arXiv preprint arXiv:2512.13564_, 2025.


Huang, C., Yu, W., Wang, X., Zhang, H., Li, Z., Li,

R., Huang, J., Mi, H., and Yu, D. R-zero: Selfevolving reasoning llm from zero data. _arXiv_ _preprint_
_arXiv:2508.05004_, 2025.


Kang, J., Ji, M., Zhao, Z., and Bai, T. Memory os of ai

agent. _arXiv preprint arXiv:2506.06326_, 2025.


Kool, W., Van Hoof, H., and Welling, M. Stochastic beams

and where to find them: The gumbel-top-k trick for sampling sequences without replacement. In _International_
_conference on machine learning_, pp. 3499–3508. PMLR,
2019.


LangChain. Langmem. [https://github.com/](https://github.com/langchain-ai/langmem)
[langchain-ai/langmem, 2025.](https://github.com/langchain-ai/langmem) GitHub repository.


Lee, K.-H., Chen, X., Furuta, H., Canny, J., and Fischer, I. A

human-inspired reading agent with gist memory of very
long contexts. _arXiv preprint arXiv:2402.09727_, 2024.


Maharana, A., Lee, D.-H., Tulyakov, S., Bansal, M., Bar
bieri, F., and Fang, Y. Evaluating very long-term
conversational memory of llm agents. _arXiv_ _preprint_
_arXiv:2402.17753_, 2024.


Novikov, A., Vu, N., Eisenberger, M., Dupont, E., Huang,˜

P.-S., Wagner, A. Z., Shirobokov, S., Kozlovskii, B., Ruiz,
F. J., Mehrabian, A., et al. Alphaevolve: A coding agent
for scientific and algorithmic discovery. _arXiv preprint_
_arXiv:2506.13131_, 2025.


Ouyang, S., Yan, J., Hsu, I., Chen, Y., Jiang, K., Wang,

Z., Han, R., Le, L. T., Daruki, S., Tang, X., et al. Reasoningbank: Scaling agent self-evolving with reasoning
memory. _arXiv preprint arXiv:2509.25140_, 2025.


Packer, C., Fang, V., Patil, S., Lin, K., Wooders, S., and

Gonzalez, J. Memgpt: Towards llms as operating systems.
2023.



9


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**



Schulman, J., Wolski, F., Dhariwal, P., Radford, A., and

Klimov, O. Proximal policy optimization algorithms.
_arXiv preprint arXiv:1707.06347_, 2017.


Shridhar, M., Yuan, X., Cotˆ e,´ M.-A., Bisk, Y., Trischler,

A., and Hausknecht, M. Alfworld: Aligning text and
embodied environments for interactive learning. _arXiv_
_preprint arXiv:2010.03768_, 2020.


Trivedi, H., Khot, T., Hartmann, M., Manku, R., Dong, V.,

Li, E., Gupta, S., Sabharwal, A., and Balasubramanian,
N. Appworld: A controllable world of apps and people
for benchmarking interactive coding agents. In _Proceed-_
_ings of the 62nd Annual Meeting of the Association for_
_Computational Linguistics (Volume 1:_ _Long Papers)_, pp.
16022–16076, 2024.


Wang, Y., Takanobu, R., Liang, Z., Mao, Y., Hu, Y.,

McAuley, J., and Wu, X. Mem- _{\_ alpha _}_ : Learning
memory construction via reinforcement learning. _arXiv_
_preprint arXiv:2509.25911_, 2025a.


Wang, Z., Wang, K., Wang, Q., Zhang, P., Li, L., Yang, Z.,

Jin, X., Yu, K., Nguyen, M. N., Liu, L., et al. Ragen:
Understanding self-evolution in llm agents via multi-turn
reinforcement learning. _arXiv preprint arXiv:2504.20073_,
2025b.


Wang, Z. Z., Mao, J., Fried, D., and Neubig, G. Agent

workflow memory. _arXiv_ _preprint_ _arXiv:2409.07429_,
2024.


Wei, T., Sachdeva, N., Coleman, B., He, Z., Bei, Y., Ning,

X., Ai, M., Li, Y., He, J., Chi, E. H., et al. Evo-memory:
Benchmarking llm agent test-time learning with selfevolving memory. _arXiv_ _preprint_ _arXiv:2511.20857_,
2025.


Wu, D., Wang, H., Yu, W., Zhang, Y., Chang, K.-W.,

and Yu, D. Longmemeval: Benchmarking chat assistants on long-term interactive memory. _arXiv_ _preprint_
_arXiv:2410.10813_, 2024.


Wu, R., Wang, X., Mei, J., Cai, P., Fu, D., Yang, C., Wen, L.,

Yang, X., Shen, Y., Wang, Y., et al. Evolver: Self-evolving

llm agents through an experience-driven lifecycle. _arXiv_
_preprint arXiv:2510.16079_, 2025.


Xu, W., Liang, Z., Mei, K., Gao, H., Tan, J., and Zhang, Y.

A-mem: Agentic memory for llm agents. _arXiv preprint_
_arXiv:2502.12110_, 2025.


Yan, S., Yang, X., Huang, Z., Nie, E., Ding, Z., Li, Z., Ma,

X., Kersting, K., Pan, J. Z., Schutze, H., et al.¨ Memoryr1: Enhancing large language model agents to manage
and utilize memories via reinforcement learning. _arXiv_
_preprint arXiv:2508.19828_, 2025.



Yang, A., Li, A., Yang, B., Zhang, B., Hui, B., Zheng, B.,

Yu, B., Gao, C., Huang, C., Lv, C., et al. Qwen3 technical

report. _arXiv preprint arXiv:2505.09388_, 2025.


Yang, Z., Qi, P., Zhang, S., Bengio, Y., Cohen, W., Salakhut
dinov, R., and Manning, C. D. Hotpotqa: A dataset for
diverse, explainable multi-hop question answering. In
_Proceedings of the 2018 conference on empirical methods_
_in natural language processing_, pp. 2369–2380, 2018.


Yu, H., Chen, T., Feng, J., Chen, J., Dai, W., Yu, Q., Zhang,

Y.-Q., Ma, W.-Y., Liu, J., Wang, M., et al. Memagent: Re
shaping long-context llm with multi-conv rl-based memory agent. _arXiv preprint arXiv:2507.02259_, 2025.


Yu, W., Zhang, H., Pan, X., Cao, P., Ma, K., Li, J., Wang,

H., and Yu, D. Chain-of-note: Enhancing robustness in
retrieval-augmented language models. In _Proceedings_
_of the 2024 conference on empirical methods in natural_
_language processing_, pp. 14672–14685, 2024.


Zhai, Y., Tao, S., Chen, C., Zou, A., Chen, Z., Fu, Q., Mai,

S., Yu, L., Deng, J., Cao, Z., et al. Agentevolver: Towards efficient self-evolving agent system. _arXiv preprint_
_arXiv:2511.10395_, 2025.


Zhang, G., Fu, M., and Yan, S. Memgen: Weaving gen
erative latent memory for self-evolving agents. _arXiv_
_preprint arXiv:2509.24704_, 2025a.


Zhang, G., Ren, H., Zhan, C., Zhou, Z., Wang, J., Zhu, H.,

Zhou, W., and Yan, S. Memevolve: Meta-evolution of
agent memory systems. _arXiv preprint arXiv:2512.18746_,
2025b.


Zhao, A., Huang, D., Xu, Q., Lin, M., Liu, Y.-J., and Huang,

G. Expel: Llm agents are experiential learners. In _Pro-_
_ceedings_ _of_ _the_ _AAAI_ _Conference_ _on_ _Artificial_ _Intelli-_
_gence_, volume 38, pp. 19632–19642, 2024.


Zhao, A., Wu, Y., Yue, Y., Wu, T., Xu, Q., Lin, M., Wang,

S., Wu, Q., Zheng, Z., and Huang, G. Absolute zero:
Reinforced self-play reasoning with zero data. _arXiv_
_preprint arXiv:2505.03335_, 2025.


Zheng, B., Fatemi, M. Y., Jin, X., Wang, Z. Z., Gandhi, A.,

Song, Y., Gu, Y., Srinivasa, J., Liu, G., Neubig, G., et al.
Skillweaver: Web agents can self-improve by discovering and honing skills. _arXiv preprint arXiv:2504.07079_,
2025.


Zhong, W., Guo, L., Gao, Q., Ye, H., and Wang, Y. Memo
rybank: Enhancing large language models with long-term
memory. In _Proceedings of the AAAI Conference on Arti-_
_ficial Intelligence_, volume 38, pp. 19724–19731, 2024.



10


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


**A. More Experimental Results**


**A.1. More Comparison Experiments**


We further compare MemSkill with additional baselines on ALFWorld, including LightMem (Fang et al., 2025), AWM (Wang
et al., 2024), and Expel (Zhao et al., 2024). As shown in Table 4, MemSkill consistently achieves the best performance across
both base models and evaluation splits. With LLaMA, MemSkill obtains an average success rate of 80.36, outperforming
the strongest baseline LightMem by 5.53 points. The gain is especially clear on ALF-Unseen, where MemSkill improves the
success rate from 75.37 to 83.58 while reducing the average number of steps from 20.69 to 16.63.


The advantage remains under transfer evaluation with Qwen, where MemSkill is not trained using this base model or dataset.
MemSkill achieves an average success rate of 81.29, surpassing the strongest baseline Expel by 7.61 points. It also requires
fewer interaction steps on both ALF-Seen and ALF-Unseen. These results suggest that the learned memory skills can
capture reusable experience patterns for embodied decision-making, leading to both higher task success and more efficient
execution across seen and unseen environments.


_Table 4._ **More comparison results on ALFWorld.**


**Embodied Interactive Tasks**



**ModelMethods**



**ALF-Seen** _[†]_ **ALF-Unseen** _[†]_ **Avg.**


**SR** **#Stps** _↓_ **SR** **#Stps** _↓_ **SR**



LightMem 74.29 21.69 75.37 20.69 74.83
AWM 66.43 23.25 68.66 22.25 67.55
Expel 67.14 23.26 66.42 22.40 66.78


LightMem 70.71 20.48 58.21 25.62 64.46
AWM 74.29 19.03 61.19 24.67 67.74
Expel 75.71 18.81 71.64 20.98 73.68

**Bold** indicates the best score within each base model block.

              - indicates no training using this base model or dataset.

_†_ indicates evaluation with in-context demonstrations.


Table 5 further reports ALFWorld results _without_ in-context demonstrations. This setting is complementary to the main-table
evaluation with demonstrations, but is more controlled for studying memory itself. Since in-context demonstrations can also
act as an external form of memory, including them may confound the gains brought by each method’s constructed memory.
Therefore, this setting decouples demonstrations from memory construction and isolates the contribution of the learned
memory mechanism.


Under this stricter setting, MemSkill still consistently outperforms all baselines across both base models and both evaluation
splits. With LLaMA, MemSkill achieves an average success rate of 57.71, outperforming the strongest baseline LightMem
by 11.72 points. The improvement is larger on ALF-Unseen, where MemSkill improves the success rate from 46.27 to
59.70, suggesting stronger generalization to unseen environments. MemSkill also requires fewer interaction steps than all
baselines, reducing the average steps on ALF-Seen and ALF-Unseen to 26.87 and 25.88, respectively.


The same trend holds in the transfer setting with Qwen, where MemSkill is not trained using this base model or dataset.
MemSkill achieves an average success rate of 63.83, improving over the strongest baseline by 8.03 points. It also obtains the
lowest number of steps on both ALF-Seen and ALF-Unseen. These results show that the gains of MemSkill do not rely on
in-context demonstrations, and that the learned memory skills provide reusable task experience that improves both success
rate and execution efficiency.


**A.2. More Results on Appworld**


To further evaluate whether memory skills generalize beyond conversational and embodied household settings, we extend
our study to AppWorld (Trivedi et al., 2024), a more challenging interactive tool-use benchmark. We report results on both
Test-Normal (Test-N) and Test-Challenge (Test-C), using Pass Rate (PR) and the average number of execution steps as
evaluation metrics. Our default setting follows the stronger evaluation protocol with in-context demonstrations. In addition,


11


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


_Table 5._ **More comparison results on ALFWorld** _**without**_ **in-context demonstrations.**


**Embodied Interactive Tasks**



**ModelMethods**



**ALF-Seen** **ALF-Unseen** **Avg.**


**SR** **#Stps** _↓_ **SR** **#Stps** _↓_ **SR**



No-Memory 17.14 43.74 20.15 42.99 18.65
CoN 40.71 33.44 30.60 37.66 35.66
ReadAgent 32.86 37.09 38.06 34.78 35.46
MemoryBank 25.00 39.96 32.84 36.54 28.92
A-MEM 24.29 40.51 28.36 38.83 26.33
Mem0 32.86 36.47 32.09 37.32 32.48
LangMem 37.86 34.39 35.07 35.70 36.47
MemoryOS 15.71 43.74 14.18 44.54 14.95
LightMem 45.71 31.76 46.27 30.66 45.99
AWM 35.71 35.87 39.55 34.93 37.63
Expel 42.14 34.61 43.28 33.25 42.71
**MemSkill** **55.71** **26.87** **59.70** **25.88** **57.71**


No-Memory 18.57 42.48 26.12 39.35 22.35
CoN 57.86 25.81 53.73 28.40 55.80
ReadAgent 53.57 27.88 54.48 27.41 54.03
MemoryBank 37.86 35.15 38.06 34.99 37.96
A-MEM 25.00 40.28 29.10 39.04 27.05
Mem0 38.57 33.64 41.04 33.16 39.81
LangMem 37.14 34.42 31.34 37.17 34.24
MemoryOS 19.29 42.43 18.66 42.95 18.98
LightMem 30.71 36.81 26.87 38.96 28.79
AWM 47.86 31.24 47.01 31.69 47.44
Expel 54.29 28.90 55.22 29.57 54.76
**MemSkill** **65.71** **22.49** **61.94** **24.59** **63.83**

**Bold** indicates the best score within each base model block.

              - indicates no training using this base model or dataset.


we also report a controlled variant without demonstrations, which helps isolate the contribution of each method’s constructed
memory from the task guidance provided by demonstrations.


As shown in Table 6, MemSkill achieves the best average PR across both base models under the default demonstration-based
setting. With LLaMA, the No-Memory baseline already performs strongly, indicating that in-context demonstrations provide
substantial task-specific guidance and make this setting partially saturated. As a result, the performance gaps among different
memory methods become relatively small. Nevertheless, MemSkill still achieves the best overall pass rate and uses the
fewest execution steps across both splits, suggesting that the learned memory skills can still improve efficiency even when
demonstrations already provide strong external guidance.


The benefit of MemSkill is more evident with Qwen, where the demonstration-based setting leaves more room for memorybased improvement. In this case, MemSkill consistently outperforms prior memory methods and also improves over the
No-Memory baseline. It further achieves the lowest execution steps on both Test-N and Test-C, indicating that MemSkill
can effectively complement in-context demonstrations and support more efficient tool-use behavior.


The controlled setting without in-context demonstrations further confirms the independent contribution of learned memory
skills. In this setting, MemSkill achieves the best average PR under both base models, with consistent gains on both Test-N
and Test-C. This shows that MemSkill is not merely benefiting from demonstrations, but can provide useful experience
abstraction when the agent must rely more directly on constructed memory.


Overall, these results show that MemSkill generalizes to interactive tool-use environments beyond conversational and
embodied household tasks. Under the default demonstration-based setting, MemSkill remains competitive even when
demonstrations provide strong task guidance, and brings clearer gains when the base model leaves more room for memorybased improvement. Under the controlled no-demonstration setting, MemSkill consistently improves pass rate over prior
memory methods, further supporting the effectiveness of skill-conditioned memory construction for complex multi-step tool
use.


12


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


_Table 6._ **More comparison results on AppWorld** _**with**_ **and** _**without**_ **in-context demonstrations.**


**Interactive Tool-Use Benchmark**



**ModelMethods**



**Test-N** **Test-C** **Avg.** **Test-N** _[†]_ **Test-C** _[†]_ **Avg.**



|PR #Steps↓ PR #Steps↓ PR|PR #Steps↓ PR #Steps↓ PR|
|---|---|
|**PR**<br>**#Steps**_↓_<br>**PR**<br>**#Steps**_↓_<br>**PR**|**PR**<br>**#Steps**_↓_<br>**PR**<br>**#Steps**_↓_<br>**PR**|
|**LLaMA3.3**<br>**70B-Instruct**<br>No-Memory<br>22.80<br>36.71<br>19.10<br>37.92<br>20.95<br>ReadAgent<br>23.43<br>34.82<br>20.49<br>31.36<br>21.96<br>MemoryBank<br>23.28<br>35.66<br>19.96<br>33.34<br>21.62<br>A-MEM<br>22.13<br>38.46<br>17.60<br>38.46<br>19.87<br>Mem0<br>27.02<br>27.04<br>21.62<br>30.64<br>24.32<br>MemoryOS<br>23.24<br>38.26<br>19.17<br>36.17<br>21.21<br>LightMem<br>25.42<br>30.73<br>21.32<br>30.33<br>23.37<br>AWM<br>29.00<br>**17.73**<br>21.83<br>**20.48**<br>25.42<br>Expel<br>25.29<br>29.96<br>21.20<br>30.63<br>23.25<br>**MemSkill**<br>**31.12**<br>29.38<br>**22.29**<br>32.17<br>**26.71**|54.03<br>14.21<br>38.78<br>19.12<br>46.41<br>53.76<br>14.54<br>38.67<br>19.24<br>46.22<br>53.66<br>14.89<br>38.46<br>18.84<br>46.06<br>52.85<br>14.31<br>38.16<br>18.78<br>45.51<br>54.32<br>14.14<br>39.73<br>18.55<br>47.03<br>53.14<br>13.62<br>38.52<br>17.83<br>45.83<br>51.25<br>14.10<br>39.12<br>18.50<br>45.19<br>54.68<br>14.26<br>39.54<br>18.64<br>47.11<br>52.88<br>13.56<br>39.49<br>17.91<br>46.19<br>**54.84**<br>**13.25**<br>**39.79**<br>**17.59**<br>**47.32**|
|▲**Qwen3-Next**<br>**80B-A3B-Instruct**<br>No-Memory<br>22.41<br>38.39<br>19.99<br>36.78<br>21.20<br>ReadAgent<br>26.29<br>34.77<br>20.36<br>35.07<br>23.33<br>MemoryBank<br>24.41<br>36.94<br>20.28<br>36.19<br>22.35<br>A-MEM<br>23.03<br>37.17<br>18.39<br>37.43<br>20.71<br>Mem0<br>40.42<br>**18.48**<br>22.16<br>22.97<br>31.29<br>MemoryOS<br>25.00<br>35.98<br>21.46<br>35.20<br>23.23<br>LightMem<br>36.90<br>23.71<br>23.44<br>27.05<br>30.17<br>AWM<br>27.02<br>23.90<br>22.05<br>22.63<br>24.54<br>Expel<br>25.00<br>22.20<br>20.40<br>**21.00**<br>22.70<br>**MemSkill**<br>**43.05**<br>26.11<br>**25.41**<br>31.39<br>**34.23**|47.68<br>16.81<br>38.42<br>19.70<br>43.05<br>46.83<br>17.59<br>37.65<br>21.12<br>42.24<br>46.50<br>16.98<br>37.18<br>22.03<br>41.84<br>45.44<br>17.49<br>38.14<br>21.40<br>41.79<br>50.19<br>15.11<br>39.64<br>20.33<br>44.92<br>50.98<br>16.11<br>38.03<br>21.32<br>44.51<br>48.91<br>17.23<br>40.85<br>21.14<br>44.88<br>53.23<br>16.77<br>41.26<br>22.95<br>47.25<br>49.88<br>16.86<br>39.17<br>20.06<br>44.53<br>**54.53**<br>**15.05**<br>**42.30**<br>**19.23**<br>**48.42**|


**Bold** indicates the best score within each base model block.

    - indicates no training using this base model or dataset.

_†_ indicates evaluation with in-context demonstrations.


**A.3. Experimental Results on Small Models**


We further evaluate MemSkill with Llama-3.1-8B-Instruct to examine whether the learned memory skills remain effective
when the base model has more limited capacity. As shown in Table 7, MemSkill consistently achieves the best performance
across both LoCoMo and LongMemEval. Compared with prior memory methods, MemSkill improves both F1 and L-J on
the two conversational benchmarks, indicating that skill-conditioned memory construction can provide useful support even
for smaller backbone models.


The improvement is also maintained on LongMemEval, where no training is performed using this base model or dataset.
This suggests that the learned memory skills are not tightly coupled to a specific backbone, and can transfer to smaller
models under long-context conversational settings. Overall, these results show that MemSkill does not rely solely on the
capability of a large base model. Instead, its learned memory skills provide complementary gains that remain effective under
a more resource-efficient model setting.


**A.4. Training Stability**


MemSkill incorporates several mechanisms to improve the stability of skill learning and evolution. First, we maintain a
snapshot of the skill bank after each evolution round. If the updated skill bank underperforms the best-performing snapshot
observed so far, we roll back to the best snapshot and continue subsequent evolution from it. This prevents occasional
harmful skill updates from permanently degrading the memory system.


Second, hard cases are selected according to difficulty scores, so the designer is guided by recurring failure patterns rather
than noisy random examples. This encourages each evolution round to focus on systematic weaknesses of the current skill
bank. Third, skill evolution is performed at controlled intervals, with a capped number of skill modifications in each round.
This avoids abrupt changes to the skill bank and makes the learning process more gradual.


Together, these mechanisms make the evolution process less sensitive to noisy feedback and reduce the risk of unstable skill
drift. In practice, we observe that the learned skill bank improves progressively over evolution rounds, suggesting that the
snapshot rollback, hard-case selection, and controlled update strategy provide a stable basis for self-evolving memory skills.


13


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


_Table 7._ **Experimental results on LoCoMo and LongMemEval using Llama-3.1-8B-Instruct.**


**Conversational Benchmarks**



**ModelMethods**



**LoCoMo** - **LongMemEval** **Avg.**


**F1** **L-J** **F1** **L-J** **L-J**



ReadAgent 17.53 21.49 9.45 18.80 20.15
MemoryBank 18.84 22.36 13.27 24.59 23.48
A-MEM 19.95 25.62 16.12 25.71 25.67
Mem0 14.26 17.12 14.59 26.38 21.75
LangMem 13.36 15.71 6.52 17.16 16.44
MemoryOS 17.68 23.08 7.88 18.24 20.66
LightMem 19.74 26.85 17.68 29.40 28.13
**MemSkill** **20.59** **27.23** **18.13** **30.20** **28.72**

**Bold** indicates the best score within each base model block.

              - indicates no training using this base model or dataset.


More details can be found in Appendix B.2


**B. More Implementation Details**


**B.1. Evaluation Details**


**LLM judge and infrastructure.** We use openai/gpt-oss-120b as the LLM judge (judge prompts can be found in
Appendix D). All API-based models are accessed through the NV NIM API [1] and Together API [2] . Training is conducted on
NVIDIA A6000 GPUs.


**LoCoMo (Maharana et al., 2024).** LoCoMo contains 10 long interaction samples, each paired with roughly 200 training
queries on average. We split the dataset by sample into train, validation, and test sets with a 6/2/2 ratio. We further remove
_adversarial_ queries, since their supporting evidence is absent from the provided context and may introduce noisy supervision
during training.


**LongMemEval (Wu et al., 2024).** We use the LongMemEval-S split, where each example contains an ultra-long conversation
of roughly 100K tokens. We remove abstention questions, since they do not require retrieving or constructing useful memory
from the conversation history. We split the remaining data into train, validation, and test sets. Although the training split
is not used for learning in this transfer setting, the validation split is used to tune dataset-specific configurations. We then
conduct transfer evaluation on a stratified test sample of about one-fifth of the dataset, approximately 100 samples, ensuring
coverage of different question types for a comprehensive assessment.


**ALFWorld (Shridhar et al., 2020).** We first collect expert trajectories from the training split and use them as the corpus
for memory or experience construction. We then evaluate on the official ALF-Seen and ALF-Unseen splits. More training
configuration details can be found in Appendix B.3.


**HotpotQA (Yang et al., 2018).** We use HotpotQA to study transfer under distribution shift, following the evaluation protocol
of (Yu et al., 2025). Specifically, we evaluate on three context-length settings with increasing difficulty, corresponding to 50,
100, and 200 concatenated documents, denoted as eval ~~5~~ 0, eval ~~1~~ 00, and eval ~~2~~ 00. Unless otherwise specified, all
results in this part use LLaMA as the base model and report the LLM-judge score (L-J).


**Span-level evaluation.** During evaluation, we construct memory at the span level with a default span size of 512 tokens,
rather than updating memory turn by turn. This substantially reduces the number of LLM calls and improves evaluation
efficiency.


**B.2. More Details of the Designer**


**Hard-case buffer and representative case mining.** The designer maintains a sliding _hard-case buffer_ that tracks recently
challenging evaluation cases without growing unbounded. Each case stores the query, the retrieved memories used to answer


[1https://docs.nvidia.com/nim/](https://docs.nvidia.com/nim/)
[2https://docs.together.ai/](https://docs.together.ai/)


14


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


it, the model prediction, the reference answer, the resulting task reward (e.g., F1), and a failure counter that records how
many times the case has been answered incorrectly. To prioritize cases that are both low-reward and repeatedly failed, we
assign each case a difficulty score



_d_ ( _q_ ) =



�1 _−_ _r_ ( _q_ )� _· c_ ( _q_ ) _,_ (4)



where _r_ ( _q_ ) _∈_ [0 _,_ 1] is the task reward for query _q_ and _c_ ( _q_ ) is its cumulative failure count within the buffer window. Higher
_d_ ( _q_ ) indicates more critical cases that should be examined first.


To encourage coverage over _diverse_ failure types, we further cluster hard cases by semantic similarity of their queries
and mine representative cases from each cluster. For example, in LoCoMo, some queries focus on temporal cues (e.g.,
_when_ an event happened) while others emphasize locations (e.g., _where_ something occurred). Clustering helps separate
these semantic types so the designer feedback is not dominated by a single frequent error mode, improving diversity and
completeness of the mined supervision.


**Exploration incentive for newly introduced skills.** After each evolution round, the designer may introduce new skills
that the controller has not yet learned to utilize. To facilitate adoption, we apply a short post-update exploration phase by
biasing the controller toward new skills directly at the logit level. Let _S_ new _⊆St_ denote the newly added skills, and let
_pθ_ ( _i | ht_ ) = softmax( _zt_ ) _i_ be the controller distribution at step _t_ . We encourage the total probability mass assigned to new
skills to reach a target threshold _τq_ :

      - _pθ_ ( _i | ht_ ) _≥_ _τq,_ _τq_ _∈_ [0 _,_ 1] _._ (5)


_i∈S_ new


When the constraint in Eq. (5) is violated, we add a uniform logit gain _δq_ to all new skills,



_zt,i_ _[′]_ [=]




_zt,i_ + _δq,_ _i ∈S_ new _,_
_p_ _[′]_
_zt,i,_ otherwise _,_




_[′]_ _θ_ [(] _[· |][ h][t]_ [) = softmax(] _[z]_ _t_ _[′]_



_t_ [)] _[,]_ (6)



_i∈S_ new _[p][′]_



where _δq_ is chosen as the minimal value that makes

[�]



where _δq_ is chosen as the minimal value that makes [�] _i∈S_ new _[p]_ _θ_ [(] _[i]_ _[|]_ _[h][t]_ [)] _[≥]_ _[τ][q]_ [.] [By] [operating] [on] [logits,] [this] [mechanism]

preserves the controller architecture and provides a smooth probability-level encouragement toward new skills.


We apply this incentive for the first _T_ explore=50 training steps after each evolution round. To avoid persistent bias, the target
threshold decays linearly within this window:



_τq_ = _τ_ 0 _·_




- _q_
1 _−_
_T_ explore




_,_ _q_ = 0 _,_ 1 _, . . ., T_ explore _−_ 1 _,_ (7)



with default _τ_ 0=0 _._ 3. This schedule provides strong initial exploration and then gradually fades, yielding a smooth transition
back to the controller’s learned selection behavior.


**Early stopping and rollback based on stabilized rewards.** MemSkill performs skill evolution periodically, where each
evolution cycle consists of a fixed number of controller-training steps (e.g., 100 steps) on the current skill bank. Because the
reward signal can be volatile immediately after a skill-bank update, we assess whether a cycle improves performance using a
_stabilized_ reward estimate: we compute the average task reward over the _last quarter_ of training steps within the cycle, and
treat this value as the cycle’s score.


Let _L_ denote the number of controller-training steps per cycle and _{rt}_ _[L]_ _t_ =1 [the step-level rewards within the cycle.] [We]

define the cycle score as



1
_r_ ¯tail =
_L/_ 4



_L_

 

_t_ =3 _L/_ 4+1



_rt._ (8)



We compare _r_ ¯tail against the best score observed so far. If the current cycle does not improve this criterion, then before
performing the next skill evolution step, we roll back the skill bank to the previously best-performing snapshot and restart
evolution from that snapshot. This rollback prevents compounding degradations from suboptimal designer updates.


Finally, if the stabilized reward fails to improve for several consecutive evolution cycles (we use a fixed patience), we early
stop training and return the best skill bank snapshot encountered during training.


15


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


**B.3. Details on ALFWorld Training**


ALFWorld differs from the other benchmarks in that it is an interactive environment rather than a static text corpus. To
instantiate MemSkill in this setting, we first convert ALFWorld into an offline training protocol by collecting expert
trajectories on the training split. Each trajectory records the agent’s interaction sequence (observations, actions, and
outcomes) and serves as an interaction trace for memory construction.


**Task-type grouping.** ALFWorld tasks naturally fall into a small number of recurring goal templates. Following common
practice, we group trajectories by task type (i.e., goal template), such as PICK & PLACE (put an object into/on a target
receptacle), CLEAN & PLACE (clean an object and then place it), HEAT & PLACE (heat an object and then place it), and
COOL & PLACE (cool an object and then place it). [3]


**Experience corpus vs. evaluation cases.** To fit ALFWorld into our training framework, we construct per-type train-time
data splits from the offline expert trajectories. For each task type, we randomly sample a subset of trajectories as the
_experience corpus_ used for memory construction, and sample another _non-overlapping_ subset of trajectories from the same
type as _evaluation cases_ . During training, MemSkill builds a trajectory-specific memory bank from the experience corpus
(span by span, via controller and executor), and then evaluates the constructed memory on the evaluation cases to obtain task
reward and to log failure cases.


**Motivation.** Using non-overlapping trajectories from the _same_ task type for experience construction and evaluation
provides a controlled generalization signal: trajectories within a type share goal structure and recurrent interaction patterns,
making memories and skills more transferable across different instances of the same template. This setup encourages
MemSkill to learn reusable memory skills that capture type-level regularities (e.g., relevant object states and action
prerequisites) rather than overfitting to a single trajectory, while still ensuring that evaluation traces are held out from the
traces used to build memory.


**B.4. Details on Training Objectives**


This part details the reinforcement learning objective used to optimize the controller in MemSkill when each decision selects
an ordered Top- _K_ _set_ of skills without replacement.


**Episode, states, and Top-** _K_ **actions.** Training iterates over interaction traces (episodes). For a trace, MemSkill processes
spans sequentially. At step _t_, the controller observes the raw state _st_ ≜ ( _xt, Mt_ ), represented by the learned state embedding
_ht_ defined in Section 3.3.1. Let _St_ = _{_ 1 _, . . ., Nt}_ denote the current skill bank, whose size _Nt_ may change as the designer
evolves skills. The controller computes logits _zt_ _∈_ R _[N][t]_ by applying the shared scorer to all state-skill pairs, and induces


_pθ_ ( _i | ht_ ) = softmax( _zt_ ) _i._ (9)


Instead of sampling a single skill, the controller selects an _ordered_ Top- _K_ set _At_ = ( _at,_ 1 _, . . ., at,K_ ) _without replacement_,
implemented via Gumbel-Top- _K_ sampling (Kool et al., 2019) (i.e., adding i.i.d. Gumbel noise to logits and taking the top- _K_
indices).


**Joint** **probability** **of** **Top-** _K_ **without-replacement** **selection.** For PPO-style policy optimization, we need the joint
probability of sampling the ordered set _At_ under the without-replacement process. This probability can be written as



_πθ_ ( _At_ _| ht_ ) =


with the corresponding joint log-probability



_K_



_j_ =1



_pθ_ ( _at,j_ _| ht_ )

(10)

1 _−_ [�] _ℓ<j_ _[p][θ]_ [(] _[a][t,ℓ]_ _[|][ h][t]_ [)] _[,]_



�1 _−_ 

_ℓ<j_




      - [�]

_pθ_ ( _at,ℓ_ _| ht_ ) _._ (11)



log _πθ_ ( _At_ _| ht_ ) =



_K_



_j_ =1




log _pθ_ ( _at,j_ _| ht_ ) _−_ log



When _K_ = 1, Eq. 10 reduces to the standard single-action case.


3We use the task template provided by the environment to define task types.


16


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


**Rewards from memory-dependent evaluation.** For each trace, after processing all spans and constructing the tracespecific memory bank, we evaluate the memory bank on the trace’s memory-dependent training queries and obtain a scalar
task score (e.g., F1 or success rate). We treat this score as the episode-level reward:


_R_ ≜ Eval(memory bank; training queries) _∈_ R _._ (12)


This reward is then assigned to the sequence of controller decisions within the trace. Concretely, we use standard return
computation with discount factor _γ_ :



_Gt_ =



_T_



_τ_ = _t_



_γ_ _[τ]_ _[−][t]_ _rτ_ _,_ (13)



where _rτ_ is the per-step reward. In our default setting, reward is provided only after memory construction completes, i.e.,
_rT_ = _R_ and _rτ_ = 0 for _τ_ _<_ _T_, so _Gt_ = _γ_ _[T][ −][t]_ _R_ . We learn a value function _Vϕ_ ( _ht_ ) and compute advantages _A_ [ˆ] _t_ using
generalized advantage estimation (GAE).


**PPO objective with Top-** _K_ **actions.** We optimize the controller using proximal policy optimization (PPO) (Schulman
et al., 2017), replacing the standard single-action log-probability with the Top- _K_ joint log-probability in Eq. 11. Let
_θ_ old denote the parameters of the behavior policy used to collect rollouts. For simplicity, we use _ht_ to denote the state
representation computed under the policy being evaluated. Define the importance ratio:




_[|][ h][t]_ [)]
_rt_ ( _θ_ ) = _[π][θ]_ [(] _[A][t]_

_πθ_ old ( _At_ _| ht_ ) [= exp]


The clipped surrogate policy objective is




- log _πθ_ ( _At_ _| ht_ ) _−_ log _πθ_ old( _At_ _| ht_ ) _._ (14)




- _rt_ ( _θ_ ) _A_ [ˆ] _t,_ clip( _rt_ ( _θ_ ) _,_ 1 _−_ _ϵ,_ 1 + _ϵ_ ) _A_ [ˆ] _t_




- [�]
_._ (15)



_L_ policy( _θ_ ) = E _t_




min



We additionally optimize a value function and include an entropy bonus for exploration:



��
_Vϕ_ ( _ht_ ) _−_ _Gt_



_L_ value( _ϕ_ ) = E _t_


_H_ ( _θ_ ) = E _t_



�2 [�] _,_ (16)




 - _H_ ( _pθ_ ( _· | ht_ ))� _,_ (17)



where _H_ ( _·_ ) is the entropy of the categorical distribution over all skills. The overall objective (to maximize) is


max _L_ policy( _θ_ ) _−_ _cv L_ value( _ϕ_ ) + _cH H_ ( _θ_ ) _._ (18)

_θ,ϕ_


In implementation, we minimize the negative of Eq. 18.


**Gumbel-Top-** _K_ **exploration.** To sample Top- _K_ skills without replacement during rollout collection, we use Gumbel-Top_K_ sampling: at each step we draw i.i.d. Gumbel noise _{gi}_ _[N]_ _i_ =1 _[t]_ [, form perturbed logits][ ˜] _[z][t,i]_ [=] _[ z][t,i]_ [ +] _[ g][i]_ [, and take the indices of]

the _K_ largest _z_ ˜ _t,i_ to obtain _At_ . This provides stochastic exploration over skill subsets while remaining compatible with PPO
through the joint probability in Eq. 10. For training stability, entropy regularization is computed from the base categorical
distribution _pθ_ ( _·_ _|_ _ht_ ) over all skills (Eq. 17), which encourages exploration of the evolving skill bank even though the
executed action is a Top- _K_ set.


17


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


**C. Case Study**


**C.1. Initial Primitive Skills**







18


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





19


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


**C.2. Evolved Skills on LoCoMo**





20


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





21


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





22


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





23


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





**C.3. Evolved Skills on ALFWorld**







24


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**







25


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





26


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





**D. Prompts**











27


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





28


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





29


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





30


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**





31


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**



**E. Use of Large Language Models**


LLMs are used as part of our method and evaluation pipeline. Specifically, MemSkill uses an LLM executor for skillconditioned memory generation, an LLM designer for skill evolution, and an LLM judge for evaluation on tasks where
automatic metrics are insufficient. The corresponding prompts are provided in Appendix D.


LLM-based tools may also be used for grammar polishing and code assistance. The authors take full responsibility for all
scientific claims, experimental results, figures, and references in this paper.


**F. Limitations and Societal Impact**


**Limitations.** This work focuses on benchmarked research settings for skill-conditioned memory construction. Practical
deployments of agent memory systems may require additional mechanisms for privacy protection, user consent, access
control, and data retention. These considerations are orthogonal to the core algorithmic contribution of MemSkill and are
left for future deployment-oriented studies.


32


**MemSkill:** **Learning and Evolving Memory Skills for Self-Evolving Agents**


**Societal impact.** MemSkill contributes toward more adaptive and reusable memory mechanisms for long-horizon LLM
agents. Instead of repeatedly designing task-specific memory pipelines, the proposed skill-based formulation allows memory
behaviors to be learned, reused, and evolved from interaction traces, which may lower the engineering barrier for building
memory-augmented agents. This can benefit research and practical applications that require long-term context management,
such as personalized assistants, educational agents, research support tools, and embodied task-solving systems. Since
agent memory may involve user-provided or task-specific information, practical deployments should follow standard data
governance practices, including user consent, privacy protection, data retention control, and mechanisms for inspecting or
deleting stored memories. Our work focuses on benchmarked research settings and does not target surveillance, deception,
or high-stakes decision making.


33


