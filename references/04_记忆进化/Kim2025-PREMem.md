## **Pre-Storage Reasoning for Episodic Memory:** **Shifting Inference Burden to Memory for Personalized Dialogue**

**Sangyeop Kim** **[1,2]** _[∗]_ **, Yohan Lee** **[3]** [*] **, Sanghwa Kim** **[4]** **, Hyunjong Kim** **[1]** **, Sungzoon Cho** **[1]** [†]


1Seoul National University, 2Coxwave, 3Independent Researcher, 4KAIST

sy917kim@bdai.snu.ac.kr, yhlee.nlp@gmail.com, zoon@snu.ac.kr



**Abstract**


Effective long-term memory in conversational
AI requires synthesizing information across
multiple sessions. However, current systems
place excessive reasoning burden on response
generation, making performance significantly
dependent on model sizes. We introduce PREMem (Pre-storage Reasoning for Episodic
Memory), a novel approach that shifts complex reasoning processes from inference to
memory construction. PREMem extracts finegrained memory fragments categorized into
factual, experiential, and subjective information; it then establishes explicit relationships
between memory items across sessions, capturing evolution patterns like extensions, transformations, and implications. By performing
this reasoning during pre-storage rather than
when generating a response, PREMem creates
enriched representations while reducing computational demands during interactions. Experiments show significant performance improvements across all model sizes, with smaller
models achieving results comparable to much
larger baselines while maintaining effectiveness even with constrained token budgets. Code
[and dataset are available at https://github.](https://github.com/sangyeop-kim/PREMem)
[com/sangyeop-kim/PREMem.](https://github.com/sangyeop-kim/PREMem)


**1** **Introduction**


Human cognition seamlessly synthesizes past experiences into coherent episodic memories that support personalized interactions (Piaget et al., 1952;
Carey, 1985; Laird, 2012). When engaging with
familiar people, individuals effortlessly perform relevant interactions, track evolving preferences, and
maintain consistent mental models without explicitly reviewing conversation histories. This natural
memory process enables meaningful relationships
through contextualized understanding.


*These authors contributed equally.
†Corresponding author.



In conversational AI, well-designed memory
structures are essential for maintaining personalized interactions across multiple sessions (Martins et al., 2022; Bae et al., 2022; Gutiérrez et al.,
2024). Effective memory mechanisms allow AI
assistants to track user preferences, recall shared
experiences, and sustain consistent understanding
over time—capabilities that form the foundation
of truly personalized dialogue systems (Wu et al.,
2025b; Fountas et al., 2025).
Current memory approaches in conversational
AI systems rely on three core mechanisms (Wang
et al., 2024b; Du et al., 2025): indexing and storing, retrieval, and memory-based generation. Recent advances have explored various structural
granularities—from turn-level and session-level
segmentation to compressed summaries (Pan et al.,
2025) and knowledge graphs (Edge et al., 2025;
Zhu et al., 2025). These approaches primarily investigate how different memory structures affect
retrieval efficiency and accuracy, yet struggle with
cross-session challenges that require understanding
continuity, causality, and state changes.

Recent works (Xu et al., 2025; Gutiérrez et al.,
2025) have attempted to address multi-session reasoning through metadata annotations and conceptlinking knowledge graphs. However, these methods typically define cross-session relationships as
simple clusters without modeling the nature of relationships or temporal evolution.

Beyond these limitations of retrieval-focused
approaches, a more critical challenge emerges
even when retrieval succeeds. Even with optimal retrieval systems that can provide relevant
context, models frequently struggle with complex reasoning tasks that require synthesis and inference—particularly temporal relationships and
cross-session information integration (Mao et al.,
2022; Yuan et al., 2025). Unlike simple information
retrieval, these tasks demand sophisticated cognitive processes including pattern recognition, causal


reasoning, and contextual synthesis. This computational burden during response generation creates
significant inefficiency and amplifies performance
disparities between large and small models.

To address these challenges, we present
**PREMem** ( **P** re-storage **R** easoning for **E** pisodic
**Mem** ory), a cognitive science-grounded approach
that shifts complex reasoning processes from response generation to memory construction. Our approach draws inspiration from human cognitive processes: rather than exhaustively reviewing conversation histories during interactions, humans rely on
pre-consolidated memories that have undergone sophisticated synthesis during offline periods (Squire,
1987; Schacter and Addis, 2007). Based on schema
theory (Rumelhart et al., 1976; Bartlett, 1995), human memory actively transforms information during storage through assimilation and accommodation processes, enabling efficient retrieval and coherent understanding across temporal contexts.

PREMem implements this cognitive principle by extracting memory fragments into three
theoretically-grounded categories—factual, experiential, and subjective information—and establishing explicit cross-session relationships through
five evolution patterns derived from schema modification mechanisms, as shown in Figure 1. By
performing complex reasoning during pre-storage
rather than at response time, our approach creates enriched memory representations while reducing computational demands during interactions—offering both performance gains and practical deployment advantages.

Experimental results on LongMemEval (Wu
et al., 2025a) and LoCoMo (Maharana et al., 2024)
benchmarks demonstrate significant improvements
across all model sizes. PREMem shows particularly strong results on cross-session reasoning tasks,
with even small language models (≤4B) achieving
competitive performance compared to much larger
baseline models. Additional experiments confirm
its practical applicability in resource-constrained
environments through efficient token utilization.

Our contributions include: (1) A cognitive
science-grounded memory framework based on established schema theory that extracts structured
episodic fragments and models information evolution through five theoretically-validated patterns;
(2) A pre-storage reasoning method that shifts complex cross-session synthesis from response time to
memory construction, mirroring human cognitive
consolidation processes; (3) Comprehensive experi


mental validation across two benchmarks, multiple
model families and question types, demonstrating
robust generalization; (4) Practical advantages for
resource-constrained applications through reduced
inference-time computational requirements.


**2** **Related Works**


**2.1** **Memory in Conversational AI Systems**


Long-term memory in conversational AI systems requires integrating and updating experiences
across multi-turn dialogues (Wang et al., 2024b;
Du et al., 2025). Existing approaches employ unstructured formats such as summarization (Zhong
et al., 2024; Wang et al., 2025) or compression (Pan
et al., 2025; Chen et al., 2025), but struggle with
temporal modeling and content overlap, leading to
information loss and fragmented representations.

Knowledge graph-based methods (Edge et al.,
2025; Guo et al., 2025; Zhu et al., 2025) enhance
semantic connectivity through structured representations, but their partial graph construction prevents
establishing relationships between temporally distant nodes across conversation sessions.

Recent efforts such as Li et al. (2025) and Ong
et al. (2025) introduce modular memory architectures and timeline-based linking to better reflect dialogue dynamics. However, these approaches still
perform memory relationship reasoning during response generation, making them heavily dependent
on the capabilities of the underlying model.

Recent systems (Lee et al., 2024; Xu et al., 2025;
Yuan et al., 2025) support dynamic memory evolu
tion and attempt to establish connections between
memories. However, they rely on implicit, unstructured associations rather than explicit schemas for
modeling information evolution across sessions.
This approach can lead to arbitrary links and inconsistent interpretations that are difficult to analyze.

We address these limitations with PREMem, a
novel structured memory approach. Our method
provides clear temporal relationships, well-defined
semantic connections between related information,
and systematically organized memory representations that enhance consistency, interpretability, and
reasoning efficiency.


**2.2** **Cognitive Perspectives on Memory**


Memory in AI-based conversational systems shares
structural and functional characteristics with human memory, prompting researchers to incorporate
cognitive science principles into memory system


Figure 1: **PREMem** architecture divided into _Memory Construction_ phase (comprising Step 1: Episodic Memory
Extraction and Step 2: Pre-Storage Memory Reasoning) and _Inference_ phase.



design (Wang et al., 2024a; Shan et al., 2025). This
enables systems to maintain consistent user representations across multiple conversations.

Inspired by these cognitive principles, researchers have developed various methods for transforming conversation data into structured episodic
memories (Hou et al., 2024; Fountas et al., 2025;
Ge et al., 2025). Hou et al. (2024) models human
memory consolidation by weighting information
based on contextual relevance and recall frequency,
while Fountas et al. (2025) applies event cognition
principles to segment conversations using prediction errors and graph-theoretical clustering.

However, these approaches face limitations in
cross-session reasoning, as they focus more on storage organization than on modeling information evolution across conversations (Qiu et al., 2024; Chu
et al., 2024). Although systems like Xu et al. (2025)
and Gutiérrez et al. (2025) attempt to address this
through linked structures, they still struggle with
tracking changing preferences and resolving contradictions (Huet et al., 2025; Wu et al., 2025a).

To overcome these limitations, we examine how
humans reason about and synthesize memories.
Cognitive science offers guidance through schema
theory—detailed in Appendix B. This theory views
memory as a structured interpretive system (Piaget et al., 1952; Rumelhart et al., 1976; Bartlett,
1995; Rumelhart, 2017). In this framework, new



information actively integrates with existing knowledge through generalization and exception handling (Fauconnier and Turner, 2008; Chi, 2009).


Based on these insights, our study not only structures conversations into temporal episodic units
but also models the semantic relationships between
them. This approach captures continuity, causality,
and change patterns across conversations, enabling
more consistent and personalized responses even
as user preferences evolve over time.


**3** **Methodology**


We present **PREMem**, a novel approach that shifts

complex memory synthesis and analysis from response generation to the memory construction
phase. By performing pre-storage reasoning across
conversations, our approach reduces the computational burden during dialogue while creating more
cognitive-inspired memory representations. Figure
1 illustrates the overall architecture of our approach,
which consists of a _Memory_ _Construction_ phase
(with two steps detailed in the following sections)
and an _Inference_ phase. This method improves
personalized conversation performance across all
model sizes, with smaller models (≤4B) achieving
results comparable to baselines using much larger
models. All prompts and pseudo code can be found
in Appendix A and F, respectively.


**3.1** **Step 1: Episodic Memory Extraction**


We extract episodic memory from conversation his
tory, classifying it into three categories that reflect
human memory components (Squire, 1987; Schacter and Tulving, 1994):


_•_ **Factual Information** : Objective facts about personal states, attributes, possessions, and relationships (“what I am/have/know”)


_•_ **Experiential Information** : Events, actions, and
interactions experienced over time (“what I
did/experienced”)


_•_ **Subjective Information** : Internal states including preferences, opinions, beliefs, goals, and
plans (“what I like/think/want”)


Beyond comprehensive categorization, effective
memory structure needs to solve the challenge of
_temporal_ _reasoning_ —determining accurate time
relationships. Previous research (Xu et al., 2025)
shows language models struggle with relative time
expressions such as “yesterday” and “last week”.
We address this through a structured temporal rep
resentation with four patterns: (1) ongoing facts
use message dates directly; (2) specific past events
convert relative expressions to absolute dates; (3)
unclear past events use “Before [message-date]”;
and (4) future plans use “After [message-date].”

We formalize memory extraction through
_LLMextract_ which operates on conversation sessions _S_ 1 _, S_ 2 _, · · ·_ _, SN_ :



**3.2.1** **Clustering and Temporal Linking**


We organize memory fragments into semantic clus
ters using embeddings generated from combined
key phrases and memory content. For each session
_Si_, we embed the memory fragments _{m_ _[j][}][n][i]_ [into]




_[j]_ _i_ _[}][n]_ _j_ _[i]_



_Si_, we embed the memory fragments _{mi_ _[}]_ _j_ =1 _[i]_ [into]

vectors _{e_ _[j]_ _i_ _[}][n]_ _j_ =1 _[i]_ [using an embedding model] _[ f][emb]_ [,]

that is, _e_ _[j]_ _i_ [=] _[f][emb]_ [(] _[m][j]_ _i_ [)][.] [Using] [silhouette] [scores]

to determine optimal groupings, we form clusters
_Ci_ = _{c_ [1] _i_ _[, c]_ _i_ [2] _[, ..., c]_ _i_ _[k][i][}]_ [ with each cluster containing]




_[j]_ _i_ _[}][n]_ _j_ _[i]_




_[j]_ _i_ [=] _[f][emb]_ [(] _[m][j]_ _i_




[2] _i_ _[, ..., c]_ _i_ _[k][i]_




[1] _i_ _[, c]_ _i_ [2]



_Ci_ = _{c_ [1] _i_ _[, c]_ _i_ [2] _[, ..., c]_ _i_ _[i][}]_ [ with each cluster containing]

embedding of semantically related memory items.
This clustering step serves two critical purposes: it
reduces redundancy in memory representations to
minimize noise during reasoning (Pan et al., 2025),
and it prevents combinatorial explosion by limiting
the number of cross-session comparisons required
during relationship analysis.

For a cluster _c_, the centroid is calculated as _c_ =
1 _|c|_ _e∈c_ _[e]_ [ and the collection of memory fragments]

corresponding to the cluster _c_ is denoted as _Mc_ .



For a cluster _c_, the centroid is calculated as _c_ =
1 _|c|_ _e∈c_ _[e]_ [ and the collection of memory fragments]



_LLMextract_ ( _Si_ ) _→{m_ [1] _i_




[1] _i_ _[, m]_ _i_ [2]




[2] _i_ _[, ..., m]_ _i_ _[n][i]_




_[i]_

_i_ _[}][,]_



where _ni_ is the number of memory fragments
in session _Si_ . Each memory fragment _m_ _[j]_ _i_ [includes]

source identification, key phrase, memory content,
and temporal context:




_[j]_ _i_ _[,]_ [ time] _i_ _[j]_



_m_ _[j]_




_[j]_ _i_ [= (][id] _i_ _[j]_




_[j]_ _i_ _[,]_ [ key] _[j]_ _i_




_[j]_ _i_ _[,]_ [ content] _[j]_ _i_



_i_ [)] _[.]_



**3.2** **Step 2: Pre-Storage Memory Reasoning**


From memory fragments, we analyze relationships
between information across conversation sessions
using cognitive schema theory (Rumelhart et al.,
1976; Anderson, 2013; Meylani, 2024). This approach shifts complex cognitive tasks—including
pattern recognition, information synthesis, and contextual reasoning—to the storage phase, reducing
computational demands during dialogue while creating enriched memory representations with inferred relationships and implications.



We maintain a persistent memory pool _Pi_ of
clusters that have not yet found a semantic match
with a cluster that comes after themselves up to
the _i_ -th session, initialized as _P_ 0 = _{}_ . For each
new session _Si_, we measure the similarity between
existing persistent cluster _p ∈_ _Pi−_ 1 and new cluster
_c ∈_ _Ci_ using the cosine similarity of centroids:


_p_ _· c_
_sim_ ( _p, c_ ) =
_|_ ~~_|_~~ _p_ ~~_|_~~ _| · |_ ~~_|_~~ _c||_ _[.]_


We define a pair ( _p, c_ ) as _connected_ if
_sim_ ( _p, c_ ) _>_ _θ_ . We define a set _CPi_ that contains
connected pairs ( _p, c_ ), that is,


_CPi_ := _{_ ( _p, c_ ) : _sim_ ( _p, c_ ) _> θ}_


where _p ∈_ _Pi−_ 1 _, c ∈_ _Ci_


The set _CPi_ consists of semantically related cluster pairs across sessions.


**3.2.2** **Cross-Session Reasoning Patterns**


For each identified connection, we perform crosssession reasoning based on five information evolution patterns derived from schema modification
mechanisms (Rumelhart et al., 1976; Anderson,
2013). These patterns synthesize findings from extensive cognitive science literature (Bransford and
Johnson, 1972; Chi et al., 1981; Murphy, 2004;
Chi, 2009) to capture fundamental ways humans
integrate new information with existing knowledge
structures. The detailed theoretical foundations are
provided in Appendix B.


_•_ **Extension/Generalization** : Expanding scope
of existing information (e.g., inferring broader
food preferences from restaurant choices)


_•_ **Accumulation** : Reinforcing knowledge
through repeated similar information (e.g.,
recognizing consistent exercise habits)


_•_ **Specification/Refinement** : Developing more
detailed understanding (e.g., clarifying music
preferences from general to specific)


_•_ **Transformation** : Capturing changes in states or
preferences (e.g., identifying shifts in product
satisfaction)


_•_ **Connection/Implication** : Discovering relationships between separate information (e.g., linking language study with travel plans)


The model _LLMreason_ generates reasoning
memory fragments by analyzing memory fragments in _Mp_ and _Mc_ for ( _p, c_ ) _∈_ _CPi_ individually,
extracting insights about the evolution patterns:



LoCoMo


LongMemEval



**3.3** **Inference Phase**



For a user query ( _q_ ), we retrieve the most relevant
items from our total memory store _M ∪R_ and select the top-k items based on the similarity between
embedded vectors _e ∈_ ( _E∪E_ _[′]_ ) and _femb_ ( _q_ ). These
retrieved memory items denoted by _m_ [1] _∗_ _[,][ · · ·]_ _[, m][k]_ _∗_

are arranged chronologically and composed to form
the _context_, with each item including its complete
information (key, content, time). We then generate
a response using this organized context:


_LLMresponse_ ( _context, q_ ) _→_ _response._


**4** **Experiments**


**4.1** **Experimental Setup**


**Dataset** **Category** **# Questions**



single-hop 1,123 (56.5%)
multi-hop 321 (16.1%)
temporal-reasoning 96 (4.8%)
adversarial 446 (22.4%)


single-hop 150 (30.0%)
multi-hop 121 (24.2%)
temporal-reasoning 127 (25.4%)
adversarial 30 (6.0%)
knowledge-update 72 (14.4%)



_p,c_ _[j]_ _[}][d]_ _j_ =1 _[p,c]_



_LLMreason_ ( _Mp, Mc_ ) _→{r_ _[j]_



_j_ =1 _[,]_



where _r_ _[j]_



where _rp,c_ [is the reasoning memory fragment that]

follows the same structure as memory fragments.
We define a reasoning memory pool _Ri_ as the union



_p,c_ _[j]_ _[}][d][p,c]_



of reasoning memory fragments _{r_ _[j]_



of reasoning memory fragments _{rp,c_ _[}]_ _j_ =1 [over all]

connected pairs ( _p, c_ ) _∈_ _CPi_ and denote embedding of _Ri_ using embedding model _femb_ as _Ei_ _[′]_ [.]



ding of _Ri_ using embedding model _femb_ as _Ei_ [.]

After reasoning on the pair ( _p, c_ ) _∈_ _CPi_, we
remove _p_ from the persistent memory pool since it
finds a semantic match with later-coming cluster _c_ .
On the other hand, we put all latest clusters _c ∈_ _Ci_
into the pool, then we get the updated persistent
memory pool _Pi_, which is formally defined as:



_Pi_ = _Pi−_ 1 _\ {p_ : _∃c_ _s.t._ ( _p, c_ ) _∈_ _CPi} ∪_ _Ci._


This process serves two important purposes: first,
it prevents computational explosion as sessions increase by eliminating already-processed information; second, it enables efficient long-term topic
tracking across temporally distant conversations.


After this whole process is performed on the
last conversation session _SN_, we prepare memory
storage _M_ and reasoning memory storage _R_ used
in inference as _M_ := _∪_ _[N]_ _[{][m][j][}][n][i]_ [and] _[R]_ [:=]




_[N]_ _i_ =1 _[{][m][j]_ _i_




_[j]_ _i_ _[}][n]_ _j_ _[i]_



in inference as _M_ := _∪_ _[N]_ _i_ =1 _[{][m]_ _i_ _[}]_ _j_ =1 _[i]_ [and] _[R]_ [:=]

_∪_ _[N]_ _i_ =1 _[R][i]_ [; and denote their embeddings using] _[ f][emb]_

as _E_ and _E_ _[′]_, respectively.



Table 1: Statistics of dataset category.


**Datasets** We utilize two long-term memory QA
datasets: LoCoMo (Maharana et al., 2024) and
LongMemEval (Wu et al., 2025a). LoCoMo contains 1,986 QA instances from conversation history
sets, averaging 27.2 dialogues per set with 21.6
turns per dialogue. LongMemEval has 500 QA
pairs. We adopt the LongMemEvalS subset, which
reflects more realistic constraints. LongMemEvalS
averages 115K tokens per question.

We unify the question types across both datasets
into five categories: _single-hop_, _multi-hop_, _tempo-_
_ral reasoning_, _adversarial_, and _knowledge update_
(only in LongMemEval). Detailed dataset statistics
for each category are provided in Table 1, and comprehensive information about the datasets, including unification criteria, is described in Appendix C.

To ensure a fair comparison across models and
settings, we standardize the answer generation
prompt for all experiments. The specific prompts
used for each dataset are shown in Appendix A.


**Evaluation Metrics** We evaluate using BLEU1, ROUGE-1, ROUGE-L, METEOR, BERTScore,
and LLM-as-a-judge score. BLEU-1 measures
n-gram precision while ROUGE metrics assess
lexical overlap through n-grams. METEOR and


**Model** **Method**



**LongMemEval** **LoCoMo**


**Total** Single-hop Multi-hop Temporal Knowledge Adv **Total** Single-hop Multi-hop Temporal Adv


**LLM** **R1** LLM R1 LLM R1 LLM R1 LLM R1 Acc **LLM** **R1** LLM R1 LLM R1 LLM R1 Acc







Table 2: Performance comparison across different model sizes and memory frameworks. Results show LLMjudge scores (LLM), ROUGE-1 (R1), and adversarial accuracy (Acc). Highest scores in **bold** and second highest
underlined. Additional metrics (BLEU-1, ROUGE-L, METEOR, BERTScore) available in Appendix D.



BERTScore capture semantic similarity beyond exact matches. LLM-as-a-judge score assesses overall
response quality including coherence and informativeness, critical for LongMemEval and LoCoMo
tasks that require recalling information from past interactions. For adversarial QA categories, we report
accuracy based on the proportion of safe responses
that identify unanswerable queries.


**Baselines** We compare our approach against
baselines with varying memory granularity and
state-of-the-art models. For granularity, we implement turn-level and session-level memory structures. For advanced approaches, we evaluate
SeCom (Pan et al., 2025), which partitions dialogue into topic-based segments with compressionbased denoising; HippoRAG-2 (Gutiérrez et al.,
2025), which encodes memory as an open knowledge graph with concept-context structures; and
A-Mem (Xu et al., 2025), which organizes interconnected, evolving notes with semantic metadata.


**Implementation** **Details** In PREMem, we use
identical LLMs for extraction and reasoning,



using the largest variant per family: Qwen2.572B, Gemma3-27B, or gpt-4.1-base (“base” distinguishes from smaller variants). For _LLMresponse_,
we evaluate across three LLM families—gpt-4.1
(OpenAI, 2025) (nano, mini, base), Qwen2.5 (Yang
et al., 2024) (3B, 14B, 72B), and Gemma3 (Team
et al., 2025) (4B, 12B, 27B)—to assess generalizability across different model capacities. During response generation, all models operate with a
temperature of 0 _._ 7. LLM-as-a-judge score uses a
deterministic decoding (temperature 0 _._ 0). We use
Stella_en_400M_v5 (Zhang et al., 2025) as the
embedding model to encode memory items and
queries during retrieval. Additional implementation details are provided in Appendix E.


**4.2** **Main Results**


Table 2 shows comprehensive results across
LongMemEval and LoCoMo benchmarks using
LLM-as-a-judge scores and ROUGE-1. PREMem
achieves superior performance across most categories and model sizes, especially in complex reasoning tasks. For overall performance, PREMem


consistently outperforms all baselines by substantial margins across both benchmarks.

Results highlight two key findings. First, PREMem demonstrates exceptionally strong performance on challenging cross-session reasoning
tasks—multi-hop questions, temporal reasoning,
and knowledge update categories. Second, while
some baselines excel in specific subcategories (e.g.,
A-Mem on single-hop questions), PREMem delivers more consistent performance enhancement
across all question types, maintaining robust results
regardless of question complexity.


**4.3** **Small Language Models**


**Method** **Model** **LongMemEval** **LoCoMo**



Turn 40.6 **63.7**

Session 30.9 54.2
SeCom Qwen2.5 72B 39.4 58.5
HippoRAG-2 45.9 61.6
A-Mem **53.6** 45.6



Turn



Qwen2.5 72B



PREMem Qwen2.5 3B 50.8 53.8



Turn 38.0 49.7

Session 27.6 33.3
SeCom gemma-3 27B 38.9 49.1
HippoRAG-2 43.1 49.5
A-Mem 45.3 44.5



Turn



gemma-3 27B



PREMem gemma-3 4B **53.4** **50.1**



Turn 40.7 57.1

Session 30.3 50.1
SeCom gpt-4.1 42.0 56.7
HippoRAG-2 45.2 57.3
A-Mem 55.9 49.5



Turn



gpt-4.1



PREMem gpt-4.1 nano **58.7** **58.8**


Table 3: Small models with PREMem vs. larger models
with baselines (LLM-as-a-judge scores).


Table 3 shows LLM-as-a-judge scores comparing PREMem with small models against baseline
methods using larger models. The results demon


strate that PREMem enables competitive performance even under limited model capacity.

In Gemma and gpt families, PREMem with
smaller models outperforms baselines using larger
counterparts across both benchmarks. For the
Qwen family, all memory methods using Qwen2.53B achieve scores below 50 on both benchmarks,
except for PREMem which reaches 50.8 on LongMemEval. With Qwen2.5-14B (Table 2), PREMem
performance surpasses all baseline methods that
use the much larger 72B model on both benchmarks. By offloading complex reasoning to the storage phase, PREMem enhances lightweight models with rich memory representations, reducing reliance on large-scale inference models.


**4.4** **Ablation Study**


Table 4 shows ablation studies of PREMem. Step
1 (memory extraction) is vital, as its removal
drops scores by 32.7-69.0%; similarly, Step 2 (prestorage reasoning) proves valuable through crosssession pattern analysis. Our episodic memory categorization and temporal reasoning also contribute
meaningfully, with their removal decreasing scores
by up to 8.9% and 16.4% respectively.

These results confirm two key insights. First, our
structured approach for memory extraction effectively organizes user information into meaningful
categories. Second, performing cross-session reasoning before retrieval time significantly enhances
performance across all model sizes. By shifting
complex cognitive processes to the memory construction phase, models can focus on response generation during inference, leading to more effective handling of temporal relationships and multisession information synthesis.



**Method**



**LLM** **R1**

Qwen2.5 gemma-3 gpt-4.1 Qwen2.5 gemma-3 gpt-4.1



14B 72B 12B 27B mini base 14B 72B 12B 27B mini base

**LongMemEval**

PREMem 64.7 67.5 57.7 61.9 67.6 71.4 40.4 45.4 34.4 39.2 43.2 44.6

w/o Step 2 (+0.5%)65.0 (+3.5%)69.8 (-0.6%)57.4 (-3.2%)59.9 (+0.4%)67.9 (-2.2%)69.8 (-2.1%)39.6 (-0.3%)45.2 (-5.5%)32.5 (-2.7%)38.1 (+0.3%)43.3 (-2.7%)43.4

w/o Step 1 (-51.8%) **31.2** (-46.8%) **35.9** (-59.3%) **23.5** (-61.0%) **24.1** (-52.8%) **31.9** (-52.1%) **34.2** (-57.4%) **17.2** (-59.5%) **18.4** (-67.8%) **11.1** (-69.0%) **12.2** (-63.5%) **15.8** (-61.5%) **17.2**

w/o Step 1 Categories (-0.7%)64.3 (+2.0%)68.9 (-2.4%)56.3 (-3.2%)59.9 (-1.3%)66.7 (-2.4%)69.6 (-0.3%)40.3 (+0.8%)45.7 (-4.1%)33.0 (-2.7%)38.1 (-2.9%)41.9 (-3.7%)42.9

w/o Temporal Reasoning (-1.6%)63.7 (+1.3%)68.4 (-3.0%)56.0 (-5.4%)58.5 (-2.1%)66.2 (-3.4%)69.0 (-3.2%)39.1 (-1.2%)44.8 (-10.6%) **30.8** (-6.8%)36.5 (-0.6%)42.9 (-1.6%)43.9

**LoCoMo**

PREMem 68.0 71.0 50.0 54.6 64.9 67.7 29.4 27.0 30.1 30.6 34.5 35.9

w/o Step 2 (-5.3%)64.4 (-3.8%)68.2 (-5.4%)47.3 (-3.2%)52.8 (-5.4%)61.4 (-4.5%)64.7 (+0.6%)29.6 (+5.6%)28.6 (-6.0%)28.3 (-7.0%)28.5 (-3.6%)33.2 (-4.8%)34.2

w/o Step 1 (-34.6%) **44.5** (-32.7%) **47.8** (-35.4%) **32.3** (-37.8%) **33.9** (-35.4%) **41.9** (-34.9%) **44.1** (-49.9%) **14.7** (-45.9%) **14.6** (-56.4%) **13.1** (-56.7%) **13.2** (-52.1%) **16.5** (-50.1%) **17.9**

w/o Step 1 Categories (-3.4%)65.7 (-4.1%)68.1 (-1.8%)49.1 (-4.0%)52.4 (-6.2%)60.8 (-6.3%)63.5 (-5.3%27.9) (-2.9%)26.3 (-8.7%)27.5 (-8.9%27.9) (-7.2%)32.0 (-5.6%33.9)

w/o Temporal Reasoning (-5.7%)64.2 (-7.3%)65.8 (-4.3%)47.8 (-3.2%)52.8 (-6.1%60.9) (-7.6%)62.6 (-6.9%)27.4 (-2.5%)26.4 (-16.4%) **25.1** (-12.6%) **26.8** (-9.9%)31.1 (-9.1%)32.7


Table 4: Ablation study of PREMem Components. **Bold** : >10% drop, underlined: 5-10% drop from PREMem.


**5** **Practical Applications**


Memory systems are foundational for personalized
conversational agents, with resource efficiency critical for real-world deployment. To demonstrate
the value of PREMem under resource constraints,
we evaluate three key dimensions: (1) storage efficiency through alternative retrieval methods (Section 5.1), (2) computational cost reduction using
smaller reasoning models (Section 5.2), and (3)
token budget for context efficiency (Section 5.3).


**5.1** **BM25 as Embedding Alternative**


Figure 2: Performance comparison (LLM-as-a-judge
score) across retrieval mechanisms (left: BM25 vs. embedding) and memory reasoning models (right: lowspec vs. high-spec).


Vector embeddings for semantic search demand
substantial storage for personalized assistants that
must maintain separate indexes for each user.
While keyword-based retrieval methods like BM25

typically underperform semantic search methods
(Thakur et al., 2021), experimental results shown in
Figure 2 (left) demonstrate BM25 remain surprisingly competitive with PREMem. This provides
an efficient option for resource-constrained deployments with minimal performance tradeoffs.


**5.2** **Low-Spec Reasoning Models**


Memory construction typically requires powerful
LLMs. To explore more efficient alternatives, we
investigate whether smaller models can effectively
perform our pre-storage reasoning. We introduce
PREMemS, which uses smaller variants from each
model family (Qwen2.5-14B, Gemma3-12B, or
gpt-4.1-nano) for memory construction.

Figure 2 (right) shows that reasoning-focused
prompts in _LLMextract_ and _LLMreason_ help
smaller models create high-quality memory representations. This approach effectively provides an



Table 5: Performance across token budgets. **Bold** indicates the highest score in each range.


While other methods degrade significantly with
reduced context lengths, PREMem maintains robust performance even with minimal token, as
shown in Table 5. This stability stems from memory fragments that capture pre-reasoned cognitive
relationships rather than simply storing raw conversation turns or graph connections. The efficiency
allows developers to allocate smaller portions of
context windows to memory while preserving personalization quality in real-world applications.


**6** **Conclusion**


We present PREMem, a novel episodic memory

system that shifts complex reasoning processes
from response generation to the memory construction phase. This method transforms conversations



alternative for real-world applications by reducing
computational costs during memory construction.


**5.3** **Token Budget Efficiency**


Allocating thousands of tokens from limited context windows solely for memory retrieval represents a substantial opportunity cost for multipurpose assistants. We evaluate PREMem performance across varying token budgets.



**Token**
**Method**
**budget**



**Model**
Qwen2.5 gemma-3 gpt-4.1
14B 72B 12B 27B mini base

**LongMemEval**



SeCom


A-Mem


HippoRAG-2


PREMem


SeCom


A-Mem


HippoRAG-2


PREMem



1024 35.8 37.2 33.4 33.0 37.0 35.5
2048 37.6 39.4 37.4 38.9 42.3 42.0
4096 **42.8** **44.4** **38.8** **40.4** **44.3** **44.4**

1024 44.4 48.6 36.4 41.0 49.2 49.4
2048 50.3 53.6 39.0 45.3 53.9 55.9
4096 **54.8** **58.5** **44.9** **50.6** **61.3** **62.0**

1024 41.5 41.5 38.5 38.3 40.8 40.2
2048 44.7 45.9 43.9 43.1 44.8 45.2
4096 **57.5** **57.4** **51.3** **53.5** **61.0** **61.7**

1024 **66.4** **67.6** **58.9** **63.0** **68.7** 70.2
2048 64.7 67.5 57.7 61.9 67.6 71.4
4096 62.2 66.9 55.7 60.5 67.2 **71.8**

**LoCoMo**


1024 57.0 60.5 42.3 47.9 51.5 54.2
2048 60.4 58.5 44.8 49.1 53.4 56.7
4096 **63.4** **63.9** **46.0** **50.1** **54.6** **57.3**

1024 42.9 **45.9** 43.8 **44.5** 52.9 **51.5**
2048 **43.6** 45.6 **43.9** **44.5** 52.7 49.5
4096 43.5 45.1 43.8 44.3 **53.3** 50.2

1024 56.0 55.7 40.8 46.5 49.7 53.1
2048 61.7 61.6 44.3 49.5 54.6 57.3
4096 **64.1** **65.3** **47.0** **51.0** **56.2** **59.5**

1024 63.7 65.6 48.1 52.7 64.6 67.3
2048 **68.0** **71.0** **50.0** **54.6** **64.9** **67.7**
4096 67.0 68.7 47.2 53.3 64.8 67.1


into structured memories with categorized information types and cross-session reasoning patterns. Our
approach significantly improves performance on
LongMemEval and LoCoMo benchmarks, with particularly strong results for temporal reasoning and
multi-session tasks. Notably, even modest-sized
models using PREMem achieve competitive results compared to larger state-of-the-art systems.
Additionally, our focus on token budget, retrieval
efficiency, and streamlined memory construction
makes PREMem effective for real-world conversational AI systems that require long-term personalization under resource constraints.


**Limitations**


Our work has several limitations that present opportunities for future research:


**Reduced** **efficiency** **in** **single-hop** **reasoning**
Our pre-reasoning structure shows lower performance for single-hop questions compared to direct
retrieval methods. This could be due to additional
processing that may not benefit straightforward
queries. To address this, future work could consider
utilizing original messages directly for single-hop
reasoning tasks.


**Lack of original conversation context** Our implementation focuses on extracted and synthesized memory items rather than original conversation messages to reduce storage requirements.
This approach sacrifices access to certain linguistic nuances, including users’ conversational styles
and terminology preferences. A potential solution
might involve query-dependent hybrid retrieval that
combines structured memories with original conversation segments based on the nature of the user’s
question.


**Absence** **of** **memory** **decay** **mechanisms** Our
approach does not incorporate forgetting mechanisms found in human memory. While our similarity threshold helps filter retrieved items, managing truly long-term conversations would require
additional constraints. For extended conversation
histories, implementing explicit memory size limitations or importance-based decay functions would
help control the persistent memory pool.


**Limited theoretical contribution** Our approach
demonstrates practical improvements by applying
cognitive science concepts to conversational systems. However, it remains primarily an empirical



contribution rather than advancing new theoretical
insights about memory or cognition. Future work
could explore deeper theoretical implications for
human-AI interaction.


**Ethical Considerations**


Research on episodic memory systems for conversational AI merits thoughtful consideration of privacy aspects, as these systems retain and process
user information across multiple sessions. PREMem’s structured approach to memory representation offers opportunities for enhanced transparency,
potentially enabling clearer user controls over what
information is stored. In real-world applications,
implementing appropriate data management options would allow users to understand and guide
their personalized experience.

The cross-session reasoning capabilities in our
approach warrant attention to potential biases and
inference accuracy. Our categorization helps distinguish between what users explicitly stated and
what the system infers, but misinterpretations can
still occur. Future research should develop confidence indicators for memory-based responses and
create mechanisms for users to correct the system
when it makes inappropriate connections between
separate conversations, helping prevent potential
misunderstandings from persisting across interactions.


**References**


John R Anderson. 2013. _The architecture of cognition_ .

Psychology Press.


Sanghwan Bae, Donghyun Kwak, Soyoung Kang,

Min Young Lee, Sungdong Kim, Yuin Jeong, Hyeri
Kim, Sang-Woo Lee, Woomyoung Park, and Nako
Sung. 2022. [Keep me updated! memory management](https://doi.org/10.18653/v1/2022.findings-emnlp.276)
[in long-term conversations.](https://doi.org/10.18653/v1/2022.findings-emnlp.276) In _Findings of the Asso-_
_ciation for Computational Linguistics: EMNLP 2022_,
pages 3769–3787, Abu Dhabi, United Arab Emirates.
Association for Computational Linguistics.


Frederic Charles Bartlett. 1995. _Remembering: A study_

_in experimental and social psychology_ . Cambridge
university press.


John D Bransford and Marcia K Johnson. 1972. Contex
tual prerequisites for understanding: Some investigations of comprehension and recall. _Journal of verbal_
_learning and verbal behavior_, 11(6):717–726.


Susan Carey. 1985. Conceptual change in childhood.

_(No Title)_ .


Nuo Chen, Hongguang Li, Jianhui Chang, Juhua Huang,

Baoyuan Wang, and Jia Li. 2025. [Compress](https://aclanthology.org/2025.coling-main.51/) to
impress: Unleashing the potential of compressive
[memory in real-world long-term conversations.](https://aclanthology.org/2025.coling-main.51/) In
_Proceedings_ _of_ _the_ _31st_ _International_ _Conference_
_on Computational Linguistics_, pages 755–773, Abu
Dhabi, UAE. Association for Computational Linguistics.


Michelene TH Chi. 2009. Three types of conceptual

change: Belief revision, mental model transformation,
and categorical shift. In _International handbook of_
_research on conceptual change_, pages 89–110. Routledge.


Michelene TH Chi and 1 others. 1981. Expertise in

problem solving.


Zheng Chu, Jingchang Chen, Qianglong Chen, Weijiang

Yu, Haotian Wang, Ming Liu, and Bing Qin. 2024.
[TimeBench: A comprehensive evaluation of tempo-](https://doi.org/10.18653/v1/2024.acl-long.66)
[ral reasoning abilities in large language models.](https://doi.org/10.18653/v1/2024.acl-long.66) In
_Proceedings of the 62nd Annual Meeting of the As-_
_sociation for Computational Linguistics (Volume 1:_
_Long Papers)_, pages 1204–1228, Bangkok, Thailand.
Association for Computational Linguistics.


Yiming Du, Wenyu Huang, Danna Zheng, Zhaowei

Wang, Sebastien Montella, Mirella Lapata, Kam-Fai
Wong, and Jeff Z. Pan. 2025. [Rethinking](https://arxiv.org/abs/2505.00675) memory
[in ai: Taxonomy, operations, topics, and future direc-](https://arxiv.org/abs/2505.00675)
[tions.](https://arxiv.org/abs/2505.00675) _Preprint_, arXiv:2505.00675.


Darren Edge, Ha Trinh, Newman Cheng, Joshua

Bradley, Alex Chao, Apurva Mody, Steven Truitt,
Dasha Metropolitansky, Robert Osazuwa Ness, and
Jonathan Larson. 2025. From local [to](https://arxiv.org/abs/2404.16130) global: A
[graph rag approach to query-focused summarization.](https://arxiv.org/abs/2404.16130)
_Preprint_, arXiv:2404.16130.


Gilles Fauconnier and Mark Turner. 2008. _The way we_

_think:_ _Conceptual_ _blending_ _and_ _the_ _mind’s_ _hidden_
_complexities_ . Basic books.


Zafeirios Fountas, Martin Benfeghoul, Adnan Oomer
jee, Fenia Christopoulou, Gerasimos Lampouras,
Haitham Bou Ammar, and Jun Wang. 2025. [Human-](https://openreview.net/forum?id=BI2int5SAC)
[inspired episodic memory for infinite context LLMs.](https://openreview.net/forum?id=BI2int5SAC)
In _The Thirteenth International Conference on Learn-_
_ing Representations_ .


Yubin Ge, Salvatore Romeo, Jason Cai, Raphael Shu,

Monica Sunkara, Yassine Benajiba, and Yi Zhang.
2025. [Tremu: Towards neuro-symbolic temporal rea-](https://arxiv.org/abs/2502.01630)
[soning for llm-agents with memory in multi-session](https://arxiv.org/abs/2502.01630)
[dialogues.](https://arxiv.org/abs/2502.01630) _Preprint_, arXiv:2502.01630.


Zirui Guo, Lianghao Xia, Yanhua Yu, Tu Ao, and Chao

Huang. 2025. Lightrag: Simple and fast retrieval[augmented generation.](https://arxiv.org/abs/2410.05779) _Preprint_, arXiv:2410.05779.


Bernal Jiménez Gutiérrez, Yiheng Shu, Yu Gu, Michi
hiro Yasunaga, and Yu Su. 2024. [Hipporag:](https://openreview.net/forum?id=hkujvAPVsg) Neu[robiologically inspired long-term memory for large](https://openreview.net/forum?id=hkujvAPVsg)
[language models.](https://openreview.net/forum?id=hkujvAPVsg) In _The Thirty-eighth Annual Con-_
_ference on Neural Information Processing Systems_ .



Bernal Jiménez Gutiérrez, Yiheng Shu, Weijian Qi,

Sizhe Zhou, and Yu Su. 2025. [From rag to memory:](https://arxiv.org/abs/2502.14802)
[Non-parametric continual learning for large language](https://arxiv.org/abs/2502.14802)
[models.](https://arxiv.org/abs/2502.14802) _Preprint_, arXiv:2502.14802.


Yuki Hou, Haruki Tamoto, and Homei Miyashita. 2024.

"my agent understands [me](https://doi.org/10.1145/3613905.3650839) better": Integrating dy[namic human-like memory recall and consolidation](https://doi.org/10.1145/3613905.3650839)
in [llm-based](https://doi.org/10.1145/3613905.3650839) agents. In _Extended_ _Abstracts_ _of_ _the_
_CHI_ _Conference_ _on_ _Human_ _Factors_ _in_ _Computing_
_Systems_, CHI EA ’24, New York, NY, USA. Association for Computing Machinery.


Alexis Huet, Zied Ben Houidi, and Dario Rossi. 2025.

[Episodic memories generation and evaluation bench-](https://openreview.net/forum?id=6ycX677p2l)
[mark for large language models.](https://openreview.net/forum?id=6ycX677p2l) In _The Thirteenth_
_International_ _Conference_ _on_ _Learning_ _Representa-_
_tions_ .


Frank C Keil. 1979. _Semantic and conceptual develop-_

_ment: An ontological perspective_ . Harvard University Press.


John E. Laird. 2012. _The Soar Cognitive Architecture_ .

The MIT Press.


Kuang-Huei Lee, Xinyun Chen, Hiroki Furuta, John

Canny, and Ian Fischer. 2024. A [human-inspired](https://proceedings.mlr.press/v235/lee24c.html)
[reading agent with gist memory of very long contexts.](https://proceedings.mlr.press/v235/lee24c.html)
In _Proceedings of the 41st International Conference_
_on Machine Learning_, volume 235 of _Proceedings_
_of Machine Learning Research_, pages 26396–26415.
PMLR.


Hao Li, Chenghao Yang, An Zhang, Yang Deng, Xiang

Wang, and Tat-Seng Chua. 2025. [Hello again! LLM-](https://aclanthology.org/2025.naacl-long.272/)
[powered personalized agent for long-term dialogue.](https://aclanthology.org/2025.naacl-long.272/)
In _Proceedings_ _of_ _the_ _2025_ _Conference_ _of_ _the_ _Na-_
_tions of the Americas Chapter of the Association for_
_Computational Linguistics: Human Language Tech-_
_nologies (Volume 1: Long Papers)_, pages 5259–5276,
Albuquerque, New Mexico. Association for Computational Linguistics.


Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov,

Mohit Bansal, Francesco Barbieri, and Yuwei Fang.
2024. Evaluating very [long-term](https://doi.org/10.18653/v1/2024.acl-long.747) conversational
[memory of LLM agents.](https://doi.org/10.18653/v1/2024.acl-long.747) In _Proceedings of the 62nd_
_Annual Meeting of the Association for Computational_
_Linguistics (Volume 1: Long Papers)_, pages 13851–
13870, Bangkok, Thailand. Association for Computational Linguistics.


Jean Matter Mandler. 2014. _Stories, scripts, and scenes:_

_Aspects of schema theory_ . Psychology Press.


Kelong Mao, Zhicheng Dou, and Hongjin Qian. 2022.

Curriculum contrastive [context](https://doi.org/10.1145/3477495.3531961) denoising for few[shot conversational dense retrieval.](https://doi.org/10.1145/3477495.3531961) In _Proceedings_
_of the 45th International ACM SIGIR Conference on_
_Research and Development in Information Retrieval_,
SIGIR ’22, page 176–186, New York, NY, USA. Association for Computing Machinery.


Pedro Henrique Martins, Zita Marinho, and Andre Mar
tins. 2022. _∞_ [-former: Infinite memory transformer.](https://doi.org/10.18653/v1/2022.acl-long.375)


In _Proceedings_ _of_ _the_ _60th_ _Annual_ _Meeting_ _of_ _the_
_Association for Computational Linguistics (Volume_
_1: Long Papers)_, pages 5468–5485, Dublin, Ireland.
Association for Computational Linguistics.


Rusen Meylani. 2024. Innovations with schema the
ory: Modern implications for learning, memory, and
academic achievement. _International_ _Journal_ _for_
_Multidisciplinary Research_, 6(1):2582–2160.


Gregory Murphy. 2004. _The big book of concepts_ . MIT

press.


Kai Tzu-iunn Ong, Namyoung Kim, Minju Gwak,

Hyungjoo Chae, Taeyoon Kwon, Yohan Jo, Seungwon Hwang, Dongha Lee, and Jinyoung Yeo. 2025.
[Towards lifelong dialogue agents via timeline-based](https://aclanthology.org/2025.naacl-long.435/)
[memory management.](https://aclanthology.org/2025.naacl-long.435/) In _Proceedings of the 2025_
_Conference_ _of_ _the_ _Nations_ _of_ _the_ _Americas_ _Chap-_
_ter of the Association for Computational Linguistics:_
_Human Language Technologies (Volume 1: Long Pa-_
_pers)_, pages 8631–8661, Albuquerque, New Mexico.
Association for Computational Linguistics.


OpenAI. 2025. GPT-4.1. [https://openai.com/](https://openai.com/index/gpt-4-1/)
[index/gpt-4-1/.](https://openai.com/index/gpt-4-1/) Accessed: 2025-05-17.


Zhuoshi Pan, Qianhui Wu, Huiqiang Jiang, Xufang Luo,

Hao Cheng, Dongsheng Li, Yuqing Yang, Chin-Yew
Lin, H. Vicky Zhao, Lili Qiu, and Jianfeng Gao. 2025.
[Secom: On memory construction and retrieval for per-](https://openreview.net/forum?id=xKDZAW0He3)
[sonalized conversational agents.](https://openreview.net/forum?id=xKDZAW0He3) In _The Thirteenth_
_International_ _Conference_ _on_ _Learning_ _Representa-_
_tions_ .


Jean Piaget, Margaret Cook, and 1 others. 1952. _The_

_origins of intelligence in children_, volume 8. International universities press New York.


Yifu Qiu, Zheng Zhao, Yftah Ziser, Anna Korhonen,

Edoardo Ponti, and Shay Cohen. 2024. Are [large](https://doi.org/10.18653/v1/2024.naacl-long.391)
[language model temporally grounded?](https://doi.org/10.18653/v1/2024.naacl-long.391) In _Proceed-_
_ings of the 2024 Conference of the North American_
_Chapter_ _of_ _the_ _Association_ _for_ _Computational_ _Lin-_
_guistics: Human Language Technologies (Volume 1:_
_Long Papers)_, pages 7064–7083, Mexico City, Mexico. Association for Computational Linguistics.


David E Rumelhart. 2017. Schemata: The building

blocks of cognition. In _Theoretical issues in reading_
_comprehension_, pages 33–58. Routledge.


David E Rumelhart, Donald A Norman, and 1 others.

1976. _Accretion,_ _tuning_ _and_ _restructuring:_ _Three_
_modes of learning_ . Citeseer.


Daniel L Schacter and Donna Rose Addis. 2007. On the

constructive episodic simulation of past and future
events. _Behavioral and Brain Sciences_, 30(3):331–
332.


Daniel L Schacter and Endel Tulving. 1994. Memory

systems 1994. _Memory Systems_, 199.


Roger C Schank and Robert P Abelson. 2013. _Scripts,_

_plans, goals, and understanding: An inquiry into hu-_
_man knowledge structures_ . Psychology press.



Lianlei Shan, Shixian Luo, Zezhou Zhu, Yu Yuan, and

Yong Wu. 2025. [Cognitive memory in large language](https://arxiv.org/abs/2504.02441)

[models.](https://arxiv.org/abs/2504.02441) _Preprint_, arXiv:2504.02441.


L Squire. 1987. Memory and brain oxford university

press: New york.


Gemma Team, Aishwarya Kamath, Johan Ferret, Shreya

Pathak, Nino Vieillard, Ramona Merhej, Sarah Perrin,
Tatiana Matejovicova, Alexandre Ramé, Morgane
Rivière, Louis Rouillard, Thomas Mesnard, Geoffrey
Cideron, Jean bastien Grill, Sabela Ramos, Edouard
Yvinec, Michelle Casbon, Etienne Pot, Ivo Penchev,

and 197 others. 2025. Gemma 3 [technical](https://arxiv.org/abs/2503.19786) report.
_Preprint_, arXiv:2503.19786.


Nandan Thakur, Nils Reimers, Andreas Rücklé, Ab
hishek Srivastava, and Iryna Gurevych. 2021. [BEIR:](https://openreview.net/forum?id=wCu6T5xFjeJ)
[A heterogeneous benchmark for zero-shot evaluation](https://openreview.net/forum?id=wCu6T5xFjeJ)
[of information retrieval models.](https://openreview.net/forum?id=wCu6T5xFjeJ) In _Thirty-fifth Con-_
_ference on Neural Information Processing Systems_
_Datasets and Benchmarks Track (Round 2)_ .


Lei Wang, Jingsen Zhang, Hao Yang, Zhiyuan Chen,

Jiakai Tang, Zeyu Zhang, Xu Chen, Yankai Lin, Ruihua Song, Wayne Xin Zhao, Jun Xu, Zhicheng Dou,
Jun Wang, and Ji-Rong Wen. 2024a. [User behavior](https://arxiv.org/abs/2306.02552)
[simulation with large language model based agents.](https://arxiv.org/abs/2306.02552)
_Preprint_, arXiv:2306.02552.


Qingyue Wang, Yanhe Fu, Yanan Cao, Shuai Wang,

Zhiliang Tian, and Liang Ding. 2025. [Recur-](https://doi.org/10.1016/j.neucom.2025.130193)
[sively summarizing enables long-term dialogue mem-](https://doi.org/10.1016/j.neucom.2025.130193)
ory in large [language](https://doi.org/10.1016/j.neucom.2025.130193) models. _Neurocomputing_,
639:130193.


Yu Wang, Chi Han, Tongtong Wu, Xiaoxin He,

Wangchunshu Zhou, Nafis Sadeq, Xiusi Chen, Zexue
He, Wei Wang, Gholamreza Haffari, and 1 others.
2024b. Towards lifespan cognitive systems. _arXiv_
_preprint arXiv:2409.13265_ .


Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai
Wei Chang, and Dong Yu. 2025a. [Longmemeval:](https://openreview.net/forum?id=pZiyCaVuti)
[Benchmarking chat assistants on long-term interac-](https://openreview.net/forum?id=pZiyCaVuti)
[tive memory.](https://openreview.net/forum?id=pZiyCaVuti) In _The Thirteenth International Con-_
_ference on Learning Representations_ .


Yaxiong Wu, Sheng Liang, Chen Zhang, Yichao Wang,

Yongyue Zhang, Huifeng Guo, Ruiming Tang, and
Yong Liu. 2025b. [From human memory to ai mem-](https://arxiv.org/abs/2504.15965)

[ory: A survey on memory mechanisms in the era of](https://arxiv.org/abs/2504.15965)
[llms.](https://arxiv.org/abs/2504.15965) _Preprint_, arXiv:2504.15965.


Wujiang Xu, Zujie Liang, Kai Mei, Hang Gao, Jun
tao Tan, and Yongfeng Zhang. 2025. A-mem:
Agentic memory for llm agents. _arXiv_ _preprint_
_arXiv:2502.12110_ .


An Yang, Baosong Yang, Beichen Zhang, Binyuan Hui,

Bo Zheng, Bowen Yu, Chengyuan Li, Dayiheng Liu,
Fei Huang, Haoran Wei, Huan Lin, Jian Yang, Jianhong Tu, Jianwei Zhang, Jianxin Yang, Jiaxi Yang,
Jingren Zhou, Junyang Lin, Kai Dang, and 22 others. 2024. Qwen2.5 technical report. _arXiv preprint_
_arXiv:2412.15115_ .


Ruifeng Yuan, Shichao Sun, Yongqi Li, Zili Wang,

Ziqiang Cao, and Wenjie Li. 2025. [Personalized](https://aclanthology.org/2025.coling-main.254/)
large language model [assistant](https://aclanthology.org/2025.coling-main.254/) with evolving con[ditional memory.](https://aclanthology.org/2025.coling-main.254/) In _Proceedings of the 31st Inter-_
_national Conference on Computational Linguistics_,
pages 3764–3777, Abu Dhabi, UAE. Association for
Computational Linguistics.


Dun Zhang, Jiacheng Li, Ziyang Zeng, and Fulong

Wang. 2025. Jasper and stella: [distillation](https://arxiv.org/abs/2412.19048) of sota
[embedding models.](https://arxiv.org/abs/2412.19048) _Preprint_, arXiv:2412.19048.


Wanjun Zhong, Lianghong Guo, Qiqi Gao, He Ye, and

Yanlin Wang. 2024. [Memorybank: Enhancing large](https://doi.org/10.1609/aaai.v38i17.29946)

[language models with long-term memory.](https://doi.org/10.1609/aaai.v38i17.29946) _Proceed-_
_ings of the AAAI Conference on Artificial Intelligence_,
38(17):19724–19731.


Xiangrong Zhu, Yuexiang Xie, Yi Liu, Yaliang Li, and

Wei Hu. 2025. Knowledge [graph-guided](https://arxiv.org/abs/2502.06864) retrieval
[augmented generation.](https://arxiv.org/abs/2502.06864) _Preprint_, arXiv:2502.06864.


**A** **LLM Prompt**


We include all prompts required to run and evaluate

PREMem. In these figures, placeholders (denoted
by {{$variable}}) indicate positions where specific
content is dynamically inserted during execution.
For Step 1, refer to Figure 3, for Step 2, refer to Figure 4. The response generation prompts for LongMemEval and LoCoMo are provided in Figure 6
and Figure 5, respectively. The LLM-as-a-judge
evaluation prompt is shown in Figure 7.


**B** **Cognitive Scientific Foundation for**
**Memory Evolution Patterns**


In cognitive science, schema is a framework (structure) that organizes an individual’s experiences,
knowledge, and information, as well as the way
they are stored in his memory. The schema stores
one’s experiences, knowledge and information as
its memory, and it is developed by assimilating
and accommodating the information (Piaget et al.,
1952). When new information aligns with an existing schema, the schema assimilation occurs. Conversely, misaligned information requires schema
updates to incorporate new data.

A seminal work in schema theory (Rumelhart
et al., 1976) introduced three modes of learning: accretion, tuning, and restructuring. This work has become the foundation of understanding how existing
knowledge structures—known as schemata—are
transformed whenever new information is encountered. In particular, accretion means adding new
information to an existing schema without altering
its structure. Tuning refines the existing schema,
making it more efficient or accurate. Restructuring,



on the other hand, involves a more fundamental
change in the schema’s structure. Thus, this work
has become the foundation for further investigations on how schemata are modified and reorganized in response to new informaion.


Referring to further schema theory literature
(Chi et al., 1981; Bartlett, 1995; Mandler, 2014;
Rumelhart, 2017), we identify six major mechanisms of how a schema modified: (1) Schema
expansion refers to adding a new attribute or feature to an existing schema; (2) Schema integration occurs when separate, related schemata become connected to form a more cohesive structure; (3) Schema refinement points to the process of a schema being refined or made more specific based on accumulated details; (4) Schema
reinforcement happens when similar information
is repeatedly acquired, strengthening the existing
schema; (5) Schema restructuring completely reorganizes schema structure; and (6) Schema creation
occurs when existing schema structure does not
align with a new information, leading to the creation of an entirely new schema.


During a conversation, the individual acquires
additional information, and integrates new information into established memory. When integrating, it is crucial to consider how the new information is related to prior memory. Referring to
cognitive science (Anderson, 2013; Bransford and
Johnson, 1972), which studies how people perceive
and learn from information, and conceptual development (Carey, 1985; Murphy, 2004; Chi, 2009),
which studies how infants learn concepts, we identify five information types– extension, accumulation, specification, transformation, and connection–
each of which causes a different type of modification in the underlying schema.


**Extension** **(Elaboration)** A new information
broadens the scope of existing knowledge. (Anderson, 2013; Carey, 1985) describe that exposure
to information and experience extend the existing knowledge structure, paralleling the process
of schema expansion.


**Accumulation** The similar type of information
accumulates. Repeated exposure to similar information solidifies an existing framework. (Chi et al.,
1981; Schank and Abelson, 2013) demonstrate that
repeated encounters with similar information and
experience solidify a schema.


Figure 3: Step 1: Personal information extraction and categorization prompt.


Figure 4: Step 2: Memory pattern analysis and inference prompt.


Figure 5: LoCoMo answer generation prompt.


**Specification** The existing information becomes
more detailed and developed more precisely. New
information refines existing knowledge by adding
more detailed or precise features, causing schema
refinement. (Murphy, 2004; Keil, 1979) both claim
that knowledge is refined and differentiated as precise and specific information is encountered.


**Transformation** The previous information is replaced by new information or fundamentally modified. New information drives schema restructuring.
According to (Chi, 2009; Rumelhart et al., 1976),
schema is reconstructed when the new information
does not fit to the existing knowledge significantly.


**Connection** The relationship between the information and the causality are revealed. The connected information promotes existing schemata to
be integrated. (Bransford and Johnson, 1972; Fauconnier and Turner, 2008) show that connection
between information develops individual’s reasoning and understanding.

These five types of new information—extension,
accumulation, specification, transformation, and
connection—are consistent with the schema modification mechanisms: schema expansion, reinforcement, refinement, restructuring, and integration.


**C** **Dataset Description and Category**
**Unification**


For consistency, we unify the question types
into five categories: _single-hop_, _multi-hop_, _tem-_
_poral_ _reasoning_, _adversarial_, and _knowledge_
_update_ (LongMemEval only). For LoCoMo,
we treat all questions originally labeled as
open-domain-knowledge as single-hop. The
other labels—multi-hop, temporal reasoning,
and adversarial—are retained as-is. For LongMemEval, we apply these mappings: Any type containing the word single is mapped to single-hop.





Figure 6: LongMemEval answer generation prompt.


All other types are converted by replacing session
with hop, aligning them with the multi-hop or
temporal reasoning categories. If the question
ID ends with _abs, it is classified as adversarial
based on its original designation as an abstention
question. Questions related to knowledge revision
are assigned to the knowledge update category.

This unified labeling scheme supports direct
comparison across datasets and is used for all
category-level evaluations in this work. Datasets
are available under CC-BY-NC-4.0 (LoCoMo) and
MIT License (LongMemEval).


**D** **Complementary Results**


We present the complete scores including metrics that were omitted from the main paper in Table 6.



**Inference**

**Model**
**LLM**



**LongMemEval** **LoCoMo**


**LLM** ROUGE-1 ROUGE-L BLEU-1 METEOR BERTScore token length **LLM** ROUGE-1 ROUGE-L BLEU-1 METEOR BERTScore token length





Table 6: Complete experimental results.


**E** **Implementation Details**


For our implementation, we set the threshold parameter _θ_ to 0.6 for memory fragment selection.
In Steps 1 and 2 of our methodology, we utilized
few-shot examples to enhance performance, with
the complete prompt templates available in Appendix A. To ensure consistent evaluation across
experiments, we conducted preference testing to
determine which answers were more favorable. Our
analysis revealed no statistically significant difference between using GPT-4o and GPT-4.1-mini as
judges, leading us to select GPT-4.1-mini as our
LLM-as-a-judge for all evaluations.

For embedding generation, we employed
NovaSearch/stella_en_400M_v5 (MIT license)
from Huggingface. Our experiments were
conducted across two model families with
varying parameter sizes: Qwen/Qwen2.5-3BInstruct, Qwen/Qwen2.5-14B-Instruct, and
Qwen/Qwen2.5-72B-Instruct from the Qwen
family, and google/gemma-3-4b-it, google/gemma3-12b-it, and google/gemma-3-27b-it from the
Gemma family.

In compliance with licensing requirements, we
adhered to both the Qwen and Gemma license
agreements. Qwen requires attribution by displaying "Built with Qwen" or "Improved using Qwen"
when distributing AI models and special authorization for services with over 100 million monthly
active users. Gemma requires adherence to their
use restrictions policy and proper attribution with
copies of their license agreement to recipients. Our
academic research complies with these requirements, including appropriate model attribution and
usage within permitted applications.

Our hardware configuration consisted of an
Intel(R) Xeon(R) Gold 6448Y CPU and four
NVIDIA H100 80GB HBM3 GPUs for accelerated
model inference and training.







Figure 7: LLM-as-a-judge prompt used to evaluate response quality.


**F** **Pseudo Code**


**Algorithm 1** Memory-Enhanced Conversational Learning with Dynamic Clustering and Reasoning


1: **Input:** _LLMextract_, _LLMreason_, _LLMresponse_, _femb_
2: **Initialization:** _P_ 0 = _{}_, _M_ = _{}_, _R_ = _{}_

3: **for** _i_ = 1 _, · · · N_ **do**

4: **Step 1: Episodic Memory Extraction**

5: Observe conversation session _Si_
6: Extract memory fragments from _Si_ :




[1] _i_ _[,][ · · ·][ m]_ _i_ _[n][i]_



_{m_ [1]




_[i]_

_i_ _[} ←]_ _[LLM][extract]_ [(] _[S][i]_ [)]



7: Embed memory fragments: _{e_ _[j]_




_[n]_ _j_ =1 _[i]_ [where] _[ e]_ _i_ _[j]_




_[j]_ _i_ _[}][n]_ _j_ _[i]_




_[j]_ _i_ [=] _[ f][emb]_ [(] _[m]_ _i_ _[j]_



_i_ [)]



8: Cluster fragments into _Ci_ = _{c_ 1 _, . . ., cki}_ _▷_ using silhouette scores



9: Construct a set _CPi_ : _▷_ using cosine similarity


_CPi_ = _{_ ( _p, c_ ) : _sim_ ( _p, c_ ) _> θ, p ∈_ _Pi−_ 1 _, c ∈_ _Ci}_


10: **Step 2: Pre-Storage Memory Reasoning**

11: **for** ( _p, c_ ) _∈_ _CPi_ **do**

12: _Mp_ _←_ memory fragments in cluster _p_

13: _Mc_ _←_ memory fragments in cluster _c_ .

14: Generate reasoning



_p,c_ _[j]_ _[}][d]_ _j_ =1 _[p,c]_



_{r_ _[j]_




_[p,c]_

_j_ =1 _[←]_ _[LLM][reason]_ [(] _[M][p][, M][c]_ [)]



15: Store reasoning memory fragments: _R ←R ∪{rp,c_ [1] _[,][ · · ·]_ _[, r]_ _p,c_ _[d][p,c][}]_



16: Update _Pi_ :


17: **end for**



_Pi_ = _Pi−_ 1 _\ {p_ : _∃c_ _s.t._ ( _p, c_ ) _∈_ _CPi} ∪_ _Ci_




[1] _i_ _[, . . ., m]_ _i_ _[n][i]_



18: Store raw memory fragments: _M ←M ∪{m_ [1]




_[i]_

_i_ _[}]_



19: **end for**

20: **Inference Phase**

21: Get user query _q_, compute _eq_ _←_ _f_ emb( _q_ )

22: Retrieve top- _k_ by similarity over _M ∪R_ :


_context ←_ TopK _k_




- _M ∪R_ ; sim( _f_ emb( _·_ ) _, eq_ )�



23: Generate answer: _response ←_ _LLMresponse_ ( _context, q_ )

24: **Output:** _response_


