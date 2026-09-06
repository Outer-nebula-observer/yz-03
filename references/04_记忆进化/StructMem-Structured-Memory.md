## **StructMem: Structured Memory for Long-Horizon Behavior in LLMs**

**Buqiang Xu** **[1]** [*] **, Yijun Chen** **[1]** [*] **, Jizhan Fang** **[1]** **, Ruobin Zhong** **[1]** **,**

**Yunzhi Yao** **[1]**, **Yuqi Zhu** **[1,3]**, **Lun Du** **[2,3]**, **Shumin Deng** **[1]** [†]



**Abstract**


Long-term conversational agents need memory systems that capture relationships between
events, not merely isolated facts, to support
temporal reasoning and multi-hop question answering. Current approaches face a fundamental trade-off: flat memory is efficient but fails to
model relational structure, while graph-based
memory enables structured reasoning at the
cost of expensive and fragile construction. To
address these issues, we propose **StructMem**, a
structure-enriched hierarchical memory framework that preserves event-level bindings and induces cross-event connections. By temporally
anchoring dual perspectives and performing
periodic semantic consolidation, StructMem
improves temporal reasoning and multi-hop
performance on LoCoMo, while substantially
reducing token usage, API calls, and runtime
compared to prior memory systems [1] .


**1** **Introduction**


Persistent memory systems are essential for language model agents to maintain coherence in longterm interactions (Park et al., 2023). Beyond factual recall, long-horizon dialogue requires reasoning over temporal dependencies, causal chains,
and multi-hop relationships across turns (Weller
et al., 2025; Huang et al., 2025; Maharana et al.,
2024; Wu et al., 2025; Yang et al., 2018). This necessitates memory representations that organize
events into temporally grounded and relational
structures (Kwiatkowski et al., 2019).

Existing memory systems largely fall into two
paradigms, flat memory and graph memory, exhibit
a trade-off between efficiency and structured reasoning, as illustrated in Figure 1. Specifically, flat
memory systems (Fang et al., 2026; Zhong et al.,
2024; Packer et al., 2023) store facts or summaries


  - Equal contribution.

  - Corresponding author.
[1https://github.com/zjunlp/LightMem](https://github.com/zjunlp/LightMem)



Figure 1: Three paradigms of Memory systems.


as independent units, but fail to preserve crossevent relations, causing retrieval over long histories
to degrade into shallow similarity matching (Liu
et al., 2023; Zhuang et al., 2026). Graph-based systems (Chhikara et al., 2025; Rasmussen et al., 2025)
recover relational structure via entity–relation extraction, but incur high construction cost, require
cascaded inference (Edge et al., 2024), and are
vulnerable to error accumulation from noisy extractions (Zhuang et al., 2026). We argue that these
limitations arise from an inappropriate memory
unit. Rather than isolated facts or triplets, the fundamental unit of conversational memory should
be a _temporally grounded relational event_, which
preserves causal and interpersonal context without
imposing rigid schemas.


Based on this insight, we propose **StructMem**,
a hierarchical memory framework built around
event-centric representations. This abstraction preserves both what happened and how events relate
across agents and time, while avoiding explicit
schema design, entity resolution, and symbolic
graph traversal. Specifically, at the event level,
StructMem constructs structured episodes through
dual-perspective extraction, capturing both event
content and interactional relations within temporal context. At the cross-event level, it performs
periodic consolidation over semantically related
events, exploiting temporal locality to efficiently




























induce higher-level relational structure. Experiments on LoCoMo show that StructMem improves
long-horizon reasoning while significantly reducing computational overhead.


**2** **Related Work**


Long-term memory serves as the cognitive foundation for agents to maintain persona consistency and
perform reasoning across extended horizons (Maharana et al., 2024; Wu et al., 2025; Dong et al.,
2025; Huang et al., 2025).

Early approaches addressed the context window
limitation by externalizing history into flat vector
databases (Park et al., 2023; Packer et al., 2023;
Zhong et al., 2024). While efficient for semantic
matching, this paradigm fundamentally treats interaction history as an unordered bag of propositions,
severing the temporal progression, causal dependencies, and relational substrate that bind events
into coherent narratives (Gao et al., 2023; Liu et al.,
2023). This flat representation leads to fragmented
retrieval where isolated facts are returned without
the contextual scaffolding necessary for complex
reasoning (Weller et al., 2025; Li et al., 2025). Recent work has explored enhanced retrieval strategies through reflective reasoning and closed-loop
control mechanisms (Du et al., 2025), yet these
improvements still operate within the fundamental
constraints of flat representations. Even with extended context windows, flat memory systems suffer from the Lost-in-the-Middle phenomenon (Liu
et al., 2023), where attention mechanisms degrade
in ultra-long sequences, ultimately reducing multihop reasoning to superficial similarity search over
disconnected facts (Zhuang et al., 2026).


To bridge this reasoning gap, the field has increasingly pivoted towards structure-enriched architectures, particularly those leveraging Knowledge Graphs. Static graph approaches, such as
Microsoft GraphRAG (Edge et al., 2024) and HippoRAG (Gutiérrez et al., 2025), employ hierarchical community detection and Personalized PageRank to facilitate global sense-making and multihop traversal. Concurrently, dynamic memory systems tailored for agents, such as Mem0 [g] (Chhikara
et al., 2025) and Zep (Rasmussen et al., 2025),
have introduced evolving schemas to capture the
fluidity of user interactions. Recent advances further explore trainable graph representations (Xia
et al., 2025) and lightweight hierarchical graphs
with entity-relation indexing (Huang et al., 2025),



demonstrating substantial improvements in multiagent collaboration (Zhang et al., 2025) and procedural skill reuse (Fang et al., 2025). Despite these
advances, imposing explicit graph structures on natural dialogue introduces inherent trade-offs. Compressing fluid narratives into rigid entity-relation
triplets often incurs semantic loss (Chaudhri et al.,
2022; Zhuang et al., 2026), while extraction instability allows hallucinated relations to propagate
as persistent structural noise (Zhong and Chen,
2021; Kolluru et al., 2020). The computational
overhead of continuous graph maintenance further
poses latency challenges for real-time agentic applications (Edge et al., 2024; Fang et al., 2026).

A parallel line of research seeks a middle ground
by enabling structured consolidation without rigid
graph schemas. HiMem (Zhang et al., 2026) organizes memory into hierarchical text segments
bounded by physical session boundaries, optimizing for compression and retrieval indexing.
TiMem (Li et al., 2026) introduces per-turn reflective thinking chains to deepen single-turn understanding, though at the cost of continuous per-turn
overhead. PREMem (Kim et al., 2025) shifts inference burden to the memory stage by pre-reasoning
user preferences before storage, targeting longterm persona consistency. EMem (Zhou and Han,
2025) prioritizes retrieval faithfulness through raw
episode preservation, relying on retrieval-driven
passive consolidation rather than active synthesis. MemWeaver (Yu et al., 2025) introduces
lightweight entity extraction to organize experiences at the session level.


**3** **Method**


We propose **StructMem**, a framework that
achieves structure-enriched organization through
hierarchical design. The framework operates at two
levels: event-level structure (§3.1) preserves relational bindings within individual utterances, while
cross-event structure (§3.2) connects information
across temporal boundaries.


**3.1** **Event-Level Binding**


Event-level binding preserves the connection between factual content and relational context within
individual utterances through dual-perspective extraction and temporal anchoring.

**Dual-Perspective** **Extraction.** For each utterance _mi_ in the dialogue stream, we extract entries
from two complementary perspectives using lan

Figure 2: StructMem’s hierarchical memory organization. **Event-Level Binding** constructs event-level structure by
extracting dual perspectives and anchoring them temporally. **Cross-Event Consolidation** constructs cross-event
structure through semantic retrieval, event reconstruction, and consolidation synthesis.



guage model _L_ with prompts _Pfact_ and _Prel_ :


Φ _i ∪_ Ψ _i_ = _L_ ( _Pfact∥mi_ ) _∪L_ ( _Prel∥mi_ ) _,_ (1)


where Φ _i_ = _{ci,_ 1 _, . . ., ci,j}_ contains _factual_
_entries_ describing event content, and Ψ _i_ =
_{ri,_ 1 _, . . ., ri,k}_ contains _relational entries_ capturing interpersonal dynamics, causal influences, and
temporal dependencies.

By representing both in natural language rather
than rigid triplets, we preserve the contextual nuances required for episodic grounding while avoiding entity resolution overhead.

**Temporal Anchoring.** To preserve the binding
between relational and factual information, all entries are anchored to their originating timestamp _τi_,
forming an event-level unit:



query by concatenating all buffered entry texts and
encoding them with an embedding model. We then
rank all historical entries by cosine similarity to
this query and retrieve the top- _K_ most semantically similar entries as seeds, denoted as _Sk_ .

For each seed entry _x_ _[∗]_ _∈Sk_, we reconstruct
its complete event context by retrieving all entries
sharing the same timestamp:


_Eτ_ ( _x_ _[∗]_ ) = _{x_ _[′]_ _∈M | τ_ ( _x_ _[′]_ ) = _τ_ ( _x_ _[∗]_ ) _}._ (4)


These reconstructed events, together with the
buffered events, form the cross-event structure
grounded in semantic relevance.



_Ccross_ = _Cbuf_ _∪_




 

_x_ _[∗]_ _∈Sk_



_Eτ_ ( _x_ _[∗]_ ) _._ (5)



_M ←_



_N_



_i_ =1



_{⟨x,_ **e** _x, τi⟩| x ∈_ Φ _i ∪_ Ψ _i},_ (2)



**Memory Consolidation through Synthesis.** Unlike conventional summarization that performs
lossy compression on sequential text, our consolidation mechanism operates on semanticallyreconstructed event clusters. It explicitly synthesizes cross-event relational hypotheses, forming a
complementary abstraction layer that enables multihop reasoning while faithfully preserving the fidelity of raw episodic memory.


_M ←Ccons_ = _L_ ( _Pcons∥Ccross_ ) _._ (6)


**4** **Experiments**


**4.1** **Experimental Setup**


We first describe the dataset and evaluation metrics,

followed by the baseline systems used for comparison. To ensure reproducibility, complete set of
prompt templates and implementation details used
for memory construction, question answering, and
evaluation is provided in Appendix A.7.



where **e** _x_ denotes the embedding of entry _x_ . This
temporal coupling enables reconstruction of complete factual-relational events during retrieval.


**3.2** **Cross-Event Consolidation**


Cross-event consolidation connects information
across temporal by periodically synthesizing semantically related events. We trigger synthesis
when accumulated events exceed a time threshold.

**Semantic** **Event** **Connections.** We buffer unconsolidated entries since the last consolidation.
The buffered entries are temporally ordered:


_Cbuf_ = Sort _τ_ _{x ∈Mbuffer},_ (3)


where _Mbuffer_ denotes the buffered entries. We
encode the buffered context into an aggregated


**Performance by Type** _↑_ **Build Tokens (M)** _↓_
**Method** **Overall** _↑_ **Calls** _↓_ **Time (s)** _↓_
**Multi** **Open** **Single** **Temp** **In** **Out** **Sum**


Table 1: Performance and resource consumption comparison of memory systems on LoCoMo dataset. _↑_ : larger

OpenAI and FullContext have no construction cost; Zep and Memobase do not expose construction details.



**Dataset** **and** **Metrics.** We evaluate on the
LoCoMo benchmark (Maharana et al., 2024) (see
Appendix A.2 for detailed statistics). Effectiveness
is measured using LLM-as-a-judge evaluation; efficiency is measured by token usage, API calls, and
runtime during memory construction.


**Baselines.** We compare StructMem against RAGbased systems (OpenAI, FullContext, MiniRAG,
LightRAG), flat memory methods (LangMem, AMem, Mem0), and structural memory methods
(MemoryOS, Mem0 [g], Zep, Memobase). All methods use gpt-4o-mini as the backbone and textembedding-3-small for embeddings. Detailed retrieval and configuration parameters for all baselines are provided in Appendix A.4.


**4.2** **Overall Performance**


Table 1 shows StructMem achieves state-of-theart overall performance on LoCoMo, with substantial gains in multi-domain and temporal reasoning
where cross-event connections are critical for understanding causal relationships across dialogue
sessions. Beyond effectiveness, StructMem demonstrates exceptional efficiency: compared to existing
memory systems, it reduces token consumption
and requires significantly fewer API calls, as our
progressive structural organization avoids the expensive post-hoc graph construction. These results
hold consistently across multiple judge models, as
verified in Appendix A.5.



**4.3** **Analysis**


We analyze StructMem from two complementary

perspectives: a paradigm-level comparison that
evaluates effectiveness and efficiency across all
three memory paradigms, and an internal analysis
that examines the mechanism underlying StructMem’s reasoning gains.


**Method** **Multi** **Open** **Single** **Temp**


Flat Memory 66.31 46.88 78.83 78.50
Graph Memory 66.67 48.96 80.50 76.64


w/o Cross-Event 66.31 46.88 80.86 79.44
StructMem 68.77 46.88 81.09 81.62


Table 2: Paradigm comparison and ablation study on
LoCoMo dataset.


**Paradigm** **Comparison.** To validate the effectiveness of each paradigm, we conduct studies in
Table 2. Starting from Flat Memory as the baseline,
Graph Memory achieves improvements on singlesession and open-domain tasks, though it decreases
on temporal reasoning. In contrast, our approach
demonstrates consistent improvements across all
task types. Event-level structure improves performance in temporal reasoning and single-session.
Cross-event structure yields further gains by capturing cross-temporal causal relationships.

To examine computational efficiency, we analyze token usage and runtime on the first conversation of LoCoMo. Figure 3(a) shows that Graph


|Col1|Flat M|emory (Token|s)|Col5|Col6|
|---|---|---|---|---|---|
||<br>Struct|<br>Mem (Tokens)|<br>|||
||<br>~~Graph~~<br>~~Flat~~|<br>~~ Memory (Tok~~<br>~~ emory (Runti~~|<br>~~  ens)~~<br>~~  e)~~|||
||<br>Struct<br>|<br>Mem (Runtim<br>|<br> e)<br>|||
||~~Graph~~|~~ Memory (Run~~|~~  time)~~|||
|||||||
|||||||
|||||||
|||||||


|402.3k|Col2|Col3|Col4|Col5|Col6|Col7|
|---|---|---|---|---|---|---|
||||||||
|~~Entry Extraction~~<br>Entity Extraction<br>|~~Entry Extraction~~<br>Entity Extraction<br>|~~Entry Extraction~~<br>Entity Extraction<br>|~~Entry Extraction~~<br>Entity Extraction<br>|~~Entry Extraction~~<br>Entity Extraction<br>|||
|<br>Entity Deduplication<br>|<br>Entity Deduplication<br>|<br>Entity Deduplication<br>|<br>Entity Deduplication<br>|<br>Entity Deduplication<br>|189.208||
|~~Relation Extraction~~<br>Relation Deduplication<br>|~~Relation Extraction~~<br>Relation Deduplication<br>|~~Relation Extraction~~<br>Relation Deduplication<br>|~~Relation Extraction~~<br>Relation Deduplication<br>|~~Relation Extraction~~<br>Relation Deduplication<br>|||
|~~226.1k~~<br> <br>Synthesize|~~226.1k~~<br> <br>Synthesize|~~226.1k~~<br> <br>Synthesize|~~226.1k~~<br> <br>Synthesize|~~226.1k~~<br> <br>Synthesize|||
||||75.108||~~34.987~~||
||||75.108||||
||||||76.907||
|~~77.6k~~|~~77.6k~~|~~77.6k~~|151.025||26.438||
|~~77.6k~~|||||||
||<br>77.57||||<br>74.808||



77
76.8
76.6
76.4
76.2
76
75.8
75.6
75.4
75.2
75







3500


3000


2500


2000


1500


1000


500


0


77

76

75

74

73

72

71

70

69



400

350

300

250

200

150

100

50


|Token Usage<br>Performance|Col2|Col3|Col4|Col5|Col6|Col7|Col8|Col9|Col10|Col11|Col12|Col13|Col14|Col15|Col16|Col17|Col18|Col19|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|
|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|4.14<br>~~4.64~~<br>5.13<br>~~5.62~~<br>|||||||
|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|||||||||
|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|~~2.67~~<br>3.16<br>~~3.65~~|||||||||||
|2.17<br>|2.17<br>|2.17<br>|2.17<br>|2.17<br>|2.17<br>|2.17<br>|||||||||||||
|1.19<br>~~1.68~~|1.19<br>~~1.68~~|1.19<br>~~1.68~~|||||||||||||||||
||||||||||||||||||||



(d) Effect of the number of semantic retrieval seeds _K_



400

350

300

250

200

150

100

50

0


7


6


5


4


3


2


1


0



Dialogue Turns


(a) Token consumption over dialogue turns


Number of Retrieved Entries


(c) Effect of the number of retrieved entries









(b) Component-wise token consumption



K=0 K=5 K=10 K=15 K=20















Figure 3: Analysis of efficiency across memory paradigms and internal mechanisms of StructMem.



Memory incurs significantly higher token usage
and runtime as dialogue progresses. Figure 3(b)
reveals the source: graph construction requires four
cascading LLM operations per event, with deduplication overhead growing quadratically. In contrast,
StructMem achieves efficiency through buffered
consolidation: by exploiting temporal locality, in
which semantically related events naturally cluster
within short time windows, the system accumulates
events and processes them in batch during periodic
synthesis. This effectively reduces cross-event organization from per-event operations to periodic
batch processing, substantially cutting both API
calls and token consumption.


**StructMem Internal Mechanisms.** We analyze
whether hierarchical organization provides genuine
reasoning gains beyond retrieval scaling.

Figure 3(c) reveals that flat retrieval performance
peaks at 60 entries and plateaus thereafter, indicating that simply retrieving more atomic entries
cannot improve effectiveness, as the bottleneck is
knowledge reasoning rather than coverage. Crossevent consolidation addresses this by synthesizing
semantically related events into higher-level relational hypotheses, creating information that does



not exist in any individual memory entry.


Figure 3(d) confirms this: without event connections ( _K_ = 0), performance matches the flat
retrieval plateau, but introducing cross-event synthesis yields substantial gains, demonstrating that
hierarchical consolidation reconstructs causal relationships across temporal boundaries and enables
fundamentally new reasoning capabilities. Fidelity
analyses in Appendix A.6 further confirm that these
synthesized connections are well-grounded, with
minimal spurious associations.


**5** **Conclusion**


We propose StructMem, which achieves structure
enriched organization through hierarchical design:
preserving event-level bindings and enabling crossevent consolidation, StructMem preserves temporal
and relational structures without the computational
overhead of continuous graph maintenance. Experiments on LoCoMo demonstrate that StructMem
achieves better performance with strong results in
multi-hop and temporal reasoning, while substantially reducing token consumption, API calls, and
runtime compared to prior memory systems.


**Limitations**


Despite its strong performance, StructMem has several limitations. The quality of dual-perspective extraction is highly dependent on instruction prompts,
where suboptimal design may result in incomplete
or inaccurate relational information capture. Future research could investigate automated prompt
optimization to improve robustness across various
dialogue contexts. Additionally, the framework
primarily addresses memory expansion and synthesis but currently lacks an explicit mechanism for
conflict resolution and memory updating. As user
facts or preferences may evolve over long horizons,
the absence of a revision process could lead to inconsistencies between historical summaries and
new information. Future iterations should incorporate memory decay or updating strategies to ensure
the hierarchical organization accurately reflects the
most current state of the interaction.


**Acknowledgements**


We would like to express sincere gratitude to the

reviewers for their thoughtful and constructive feedback. This work was supported by the National Natural Science Foundation of China (No. 62576307),
Yongjiang Talent Introduction Programme (2021A156-G), and Information Technology Center and
State Key Lab of CAD&CG, Zhejiang University.
This work was supported by Ant Group and Zhejiang University - Ant Group Joint Laboratory of
Knowledge Graph.


**References**


Vinay K. Chaudhri, Chaitanya Baru, Naren Chittar,

Xin Luna Dong, Michael Genesereth, James Hendler,
Aditya Kalyanpur, Douglas B. Lenat, Juan Sequeda,
Denny Vrandeˇci´c, and Kuansan Wang. 2022. [Knowl-](https://ojs.aaai.org/aimagazine/index.php/aimagazine/article/view/19119)
edge graphs: [introduction, history and, perspectives.](https://ojs.aaai.org/aimagazine/index.php/aimagazine/article/view/19119)
_AI Magazine_, 43(1):17–29.


Prateek Chhikara, Dev Khant, Saket Aryan, Taranjeet

Singh, and Deshraj Yadav. 2025. Mem0: [Building](https://arxiv.org/abs/2504.19413)
[production-ready ai agents with scalable long-term](https://arxiv.org/abs/2504.19413)
[memory.](https://arxiv.org/abs/2504.19413) _arXiv preprint arXiv:2504.19413_ .


Cody V Dong, Qihong Lu, Kenneth A Norman, and Se
bastian Michelmann. 2025. [Towards large language](https://www.cell.com/trends/cognitive-sciences/abstract/S1364-6613(25)00179-2)
[models with human-like episodic memory.](https://www.cell.com/trends/cognitive-sciences/abstract/S1364-6613(25)00179-2) _Trends in_
_Cognitive Sciences_ .


Xingbo Du, Loka Li, Duzhen Zhang, and Le Song. 2025.

Memr [3] : Memory [retrieval](https://arxiv.org/abs/2512.20237) via reflective reasoning
[for llm agents.](https://arxiv.org/abs/2512.20237) _Preprint_, arXiv:2512.20237.



Darren Edge, Ha Trinh, Newman Cheng, Joshua

Bradley, Alex Chao, Apurva Mody, Steven Truitt,
Dasha Metropolitansky, Robert Osazuwa Ness, and
Jonathan Larson. 2024. From local [to](https://arxiv.org/abs/2404.16130) global: A
[graph rag approach to query-focused summarization.](https://arxiv.org/abs/2404.16130)
_arXiv preprint arXiv:2404.16130_ .


Jizhan Fang, Xinle Deng, Haoming Xu, Ziyan Jiang,

Yuqi Tang, Ziwen Xu, Shumin Deng, Yunzhi Yao,

Mengru Wang, Shuofei Qiao, Huajun Chen, and
Ningyu Zhang. 2026. [Lightmem: Lightweight and ef-](https://openreview.net/forum?id=dyJ0GWpjJB)
[ficient memory-augmented generation.](https://openreview.net/forum?id=dyJ0GWpjJB) In _The Four-_
_teenth International Conference on Learning Repre-_
_sentations_ .


Runnan Fang, Yuan Liang, Xiaobin Wang, Jialong

Wu, Shuofei Qiao, Pengjun Xie, Fei Huang, Huajun Chen, and Ningyu Zhang. 2025. [Memp:](https://arxiv.org/abs/2508.06433) Exploring agent [procedural](https://arxiv.org/abs/2508.06433) memory. _arXiv_ _preprint_
_arXiv:2508.06433_ .


Yunfan Gao, Yun Xiong, Xinyu Gao, Kangxiang Jia,

Jinliu Pan, Yuxi Bi, Yi Dai, Jiawei Sun, and Haofen
Wang. 2023. [Retrieval-augmented](https://arxiv.org/abs/2312.10997) generation for
large language [models:](https://arxiv.org/abs/2312.10997) A survey. _arXiv_ _preprint_
_arXiv:2312.10997_ .


Bernal Jiménez Gutiérrez, Yiheng Shu, Weijian Qi,

Sizhe Zhou, and Yu Su. 2025. [From RAG to memory:](https://openreview.net/forum?id=LWH8yn4HS2)
[Non-parametric continual learning for large language](https://openreview.net/forum?id=LWH8yn4HS2)
[models.](https://openreview.net/forum?id=LWH8yn4HS2) In _Forty-second International Conference_
_on Machine Learning_ .


Zhengjun Huang, Zhoujin Tian, Qintian Guo, Fangyuan

Zhang, Yingli Zhou, Di Jiang, and Xiaofang Zhou.
2025. Licomemory: [Lightweight and cognitive agen-](https://arxiv.org/abs/2511.01448)
[tic memory for efficient long-term reasoning.](https://arxiv.org/abs/2511.01448) _arXiv_
_preprint arXiv:2511.01448_ .


Sangyeop Kim, Yohan Lee, Sanghwa Kim, Hyunjong

Kim, and Sungzoon Cho. 2025. [Pre-storage reason-](https://arxiv.org/abs/2509.10852)
ing for episodic memory: Shifting inference burden
[to memory for personalized dialogue.](https://arxiv.org/abs/2509.10852) _arXiv preprint_
_arXiv:2509.10852_ .


Keshav Kolluru, Vaibhav Adlakha, Samarth Aggarwal,

Mausam, and Soumen Chakrabarti. 2020. [OpenIE6:](https://doi.org/10.18653/v1/2020.emnlp-main.306)
[Iterative Grid Labeling and Coordination Analysis for](https://doi.org/10.18653/v1/2020.emnlp-main.306)
[Open Information Extraction.](https://doi.org/10.18653/v1/2020.emnlp-main.306) In _Proceedings of the_
_2020 Conference on Empirical Methods in Natural_
_Language Processing (EMNLP)_, pages 3748–3761,
Online. Association for Computational Linguistics.


Tom Kwiatkowski, Jennimaria Palomaki, Olivia Red
field, Michael Collins, Ankur Parikh, Chris Alberti,
Danielle Epstein, Illia Polosukhin, Jacob Devlin, Kenton Lee, Kristina Toutanova, Llion Jones, Matthew
Kelcey, Ming-Wei Chang, Andrew M. Dai, Jakob
Uszkoreit, Quoc Le, and Slav Petrov. 2019. [Natu-](https://doi.org/10.1162/tacl_a_00276)
ral questions: [A benchmark for question answering](https://doi.org/10.1162/tacl_a_00276)
[research.](https://doi.org/10.1162/tacl_a_00276) _Transactions of the Association for Compu-_
_tational Linguistics_, 7:452–466.


Kai Li, Xuanqing Yu, Ziyi Ni, Yi Zeng, Yao Xu, Zhe
qing Zhang, Xin Li, Jitao Sang, Xiaogang Duan,
Xuelei Wang, Chengbao Liu, and Jie Tan. 2026.


Timem: [Temporal-hierarchical](https://arxiv.org/abs/2601.02845) memory consolidation for [long-horizon conversational](https://arxiv.org/abs/2601.02845) agents. _arXiv_
_preprint arXiv:2601.02845_ .


Mo Li, L. H. Xu, Qitai Tan, Long Ma, Ting Cao,

and Yunxin Liu. 2025. Sculptor: [Empowering llms](https://arxiv.org/abs/2508.04664)
[with cognitive agency via active context management.](https://arxiv.org/abs/2508.04664)
_Preprint_, arXiv:2508.04664.


Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paran
jape, Michele Bevilacqua, Fabio Petroni, and Percy
Liang. 2023. Lost in the middle: [How language mod-](https://api.semanticscholar.org/CorpusID:259360665)
[els use long contexts.](https://api.semanticscholar.org/CorpusID:259360665) _Transactions of the Association_
_for Computational Linguistics_, 12:157–173.


Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov,

Mohit Bansal, Francesco Barbieri, and Yuwei Fang.
2024. Evaluating very [long-term](https://doi.org/10.18653/v1/2024.acl-long.747) conversational
[memory of LLM agents.](https://doi.org/10.18653/v1/2024.acl-long.747) In _Proceedings of the 62nd_
_Annual Meeting of the Association for Computational_
_Linguistics (Volume 1:_ _Long Papers)_, pages 13851–
13870, Bangkok, Thailand. Association for Computational Linguistics.


Charles Packer, Vivian Fang, Shishir_G Patil, Kevin

Lin, Sarah Wooders, and Joseph_E Gonzalez. 2023.
Memgpt: [Towards llms as operating systems.](https://arxiv.org/abs/2310.08560) _CoRR_,
abs/2310.08560.


Joon Sung Park, Joseph O’Brien, Carrie Jun Cai, Mered
ith Ringel Morris, Percy Liang, and Michael S. Bernstein. 2023. Generative agents: [Interactive simulacra](https://doi.org/10.1145/3586183.3606763)
[of human behavior.](https://doi.org/10.1145/3586183.3606763) In _Proceedings of the 36th An-_
_nual_ _ACM_ _Symposium_ _on_ _User_ _Interface_ _Software_
_and_ _Technology_, UIST ’23, New York, NY, USA.
Association for Computing Machinery.


Preston Rasmussen, Pavlo Paliychuk, Travis Beauvais,

Jack Ryan, and Daniel Chalef. 2025. Zep: [a tempo-](https://arxiv.org/abs/2501.13956)
[ral knowledge graph architecture for agent memory.](https://arxiv.org/abs/2501.13956)
_arXiv preprint arXiv:2501.13956_ .


Orion Weller, Michael Boratko, Iftekhar Naim, and

Jinhyuk Lee. 2025. On the [theoretical](https://arxiv.org/abs/2508.21038) limitations of [embedding-based](https://arxiv.org/abs/2508.21038) retrieval. _Preprint_,
arXiv:2508.21038.


Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang,

Kai-Wei Chang, and Dong Yu. 2025. [Longmemeval:](https://openreview.net/forum?id=pZiyCaVuti)
[Benchmarking chat assistants on long-term interac-](https://openreview.net/forum?id=pZiyCaVuti)
[tive memory.](https://openreview.net/forum?id=pZiyCaVuti) In _ICLR_ . OpenReview.net.


Siyu Xia, Zekun Xu, Jiajun Chai, Wentian Fan, Yan

Song, Xiaohan Wang, Guojun Yin, Wei Lin, Haifeng
Zhang, and Jun Wang. 2025. From [experience](https://arxiv.org/abs/2511.07800)
to strategy: [Empowering llm agents with trainable](https://arxiv.org/abs/2511.07800)
[graph memory.](https://arxiv.org/abs/2511.07800) _arXiv preprint arXiv:2511.07800_ .


Zhilin Yang, Peng Qi, Saizheng Zhang, Yoshua Bengio,

William Cohen, Ruslan Salakhutdinov, and Christopher D Manning. 2018. Hotpotqa: [A](https://aclanthology.org/D18-1259/) dataset for
diverse, [explainable multi-hop question answering.](https://aclanthology.org/D18-1259/)
In _Proceedings_ _of_ _the_ _2018_ _conference_ _on_ _empiri-_
_cal methods in natural language processing_, pages
2369–2380.



Shuo Yu, Mingyue Cheng, Daoyu Wang, Qi Liu, Zirui

Liu, Ze Guo, and Xiaoyu Tao. 2025. [Memweaver:](https://arxiv.org/abs/2510.07713)
[A hierarchical memory from textual interactive be-](https://arxiv.org/abs/2510.07713)
[haviors for personalized generation.](https://arxiv.org/abs/2510.07713) _arXiv preprint_
_arXiv:2510.07713_ .


Guibin Zhang, Muxin Fu, Guancheng Wan, Miao Yu,

Kun Wang, and Shuicheng Yan. 2025. [G-memory:](https://arxiv.org/abs/2506.07398)
[Tracing hierarchical memory for multi-agent systems.](https://arxiv.org/abs/2506.07398)
_arXiv preprint arXiv:2506.07398_ .


Ningning Zhang, Xingxing Yang, Zhizhong Tan, Weip
ing Deng, and Wenyong Wang. 2026. [Himem:](https://arxiv.org/abs/2601.06377) Hierarchical long-term [memory](https://arxiv.org/abs/2601.06377) for llm long-horizon
[agents.](https://arxiv.org/abs/2601.06377) _arXiv preprint arXiv:2601.06377_ .


Wanjun Zhong, Lianghong Guo, Qiqi Gao, He Ye, and

Yanlin Wang. 2024. Memorybank: [Enhancing large](https://doi.org/10.1609/aaai.v38i17.29946)

[language models with long-term memory.](https://doi.org/10.1609/aaai.v38i17.29946) In _AAAI_,
pages 19724–19731. AAAI Press.


Zexuan Zhong and Danqi Chen. 2021. [A frustratingly](https://doi.org/10.18653/v1/2021.naacl-main.5)

[easy approach for entity and relation extraction.](https://doi.org/10.18653/v1/2021.naacl-main.5) In
_Proceedings_ _of_ _the_ _2021_ _Conference_ _of_ _the_ _North_
_American Chapter of the Association for Computa-_

_tional Linguistics:_ _Human Language Technologies_,
pages 50–61, Online. Association for Computational
Linguistics.


Sizhe Zhou and Jiawei Han. 2025. [A simple yet strong](https://arxiv.org/abs/2511.17208)

[baseline for long-term conversational memory of llm](https://arxiv.org/abs/2511.17208)
[agents.](https://arxiv.org/abs/2511.17208) _arXiv preprint arXiv:2511.17208_ .


Luyao Zhuang, Shengyuan Chen, Yilin Xiao, Huachi

Zhou, Yujing Zhang, Hao Chen, Qinggang Zhang,
and Xiao Huang. 2026. [LinearRAG: Linear](https://openreview.net/forum?id=mCtfkypdm6) graph
retrieval augmented [generation](https://openreview.net/forum?id=mCtfkypdm6) on large-scale cor[pora.](https://openreview.net/forum?id=mCtfkypdm6) In _The Fourteenth International Conference on_
_Learning Representations_ .


**A** **Appendix**


**A.1** **License**


This work uses the LoCoMo benchmark dataset,
which is publicly available for academic research
purposes. We follow all usage terms specified by
the dataset authors.


**A.2** **Dataset**


We evaluate on the **LoCoMo** benchmark (Maha
rana et al., 2024), which contains 10 long-term conversations with an average of 588 turns and 16,618
tokens per conversation. We focus on the question
answering task, utilizing four reasoning types from
the benchmark. Table 3 shows the statistics of questions used in our evaluation. Model performance is
evaluated using LLM-as-a-judge.


**Reasoning Type** **# Questions**


Single-hop 841
Multi-hop 282
Temporal 321
Open-domain 96


Table 3: Statistics of LoCoMo questions used.


**A.3** **Implementation Details**


We provide key implementation details for Struct
Mem to facilitate reproducibility. **Memory** **con-**
**struction:** We set the time window threshold to 1
hour for triggering consolidation. For cross-event
consolidation, we retrieve top-15 semantically similar seed entries from historical memory. **Ques-**
**tion answering:** During inference, we retrieve 60
entries and 5 synthesis from memory to provide
context for answer generation.


**A.4** **Baseline Configurations**


To ensure empirical rigor and reproducibility, we
provide the detailed retrieval and architectural configurations for all evaluated systems:

**FullContext** utilizes the entire raw dialogue history fed into the prompt in reverse chronological
order via a full-scan with _k_ = _−_ 1. **OpenAI** processes all conversation turns concatenated as a flat,
unordered text sequence directly without a retrieval
step.

**MiniRAG** and **LightRAG** retrieve the top-20
relevant entries per question to provide factual context. Similarly, **A-MEM** and **LangMem** employ
a global search mechanism to retrieve the top-40
most relevant memory entries for each query.

**MemoryOS** implements a three-tier hierarchical system featuring exhaustive recall of all ShortTerm Memory (STM) pages, a two-stage selection
for Mid-Term Memory (MTM) comprising the top5 segments and top-10 dialogue pages, and the
extraction of the top-10 relevant entries from Longterm Personal Memory (LPM).

For API-based systems including **Mem0**,
**Mem0** **[g]**, **Zep**, and **Memobase**, the top-10 relevant
memories per speaker are retrieved for response
generation.


**A.5** **Robustness of Evaluation**


We validate the reliability of our LLM-as-a-judge

protocol by conducting extensive cross-model evaluations and statistical analyses.



Table 4 summarizes the performance of memory
systems across three distinct judge model families:
gpt-4o-mini, Qwen2.5-32b-Instruct, and DeepSeekV3.2. We further calculate the inter-judge agreement and correlation across all judge pairs, as detailed in Table 5. The Fleiss’ _κ_ among different
models reaches **0.8341**, reflecting a near-perfect
agreement that substantially exceeds the commonly
accepted reliability threshold of 0.8. This high level
of consensus, combined with significant Pearson
correlation coefficients ( _r_ _>_ 0 _._ 81, _p_ _<_ 10 _[−]_ [300] ),
confirms that the automated evaluation protocol
provides a stable and objective assessment of semantic response quality.


**A.6** **Fidelity and Hallucination Study**


We conducted a systematic study to ensure that

the induced structures are grounded in the source
dialogue.


**Event-Level Extraction Fidelity.** We first evaluated whether the atomic memory entries accurately
reflect the original utterances. We employed three
independent judge models (gpt-4o-mini, Qwen2.532B-Instruct, and DeepSeek-V3.2) to identify hallucinated entries across conversations.

Specifically, for each extracted memory entry,
the judges are provided with the corresponding
source dialogue segment and tasked with determining if any factual or relational information is fabricated or unsubstantiated by the original text. The
full prompt templates are provided in Figure 17.

As detailed in Table 6, the mean hallucination rate is only 2.36%, confirming that the **Dual-**
**Perspective Extraction** of our hierarchical memory is highly faithful to the source context.


**Cross-Event Consolidation Fidelity.** The most
critical verification involves the synthesis of crossevent links. To isolate and audit these links, we
employed three independent judge models (gpt-4omini, Qwen2.5-32B-Instruct, and DeepSeek-V3.2)
to identify hallucinated links across conversations.

For each consolidation step, the judge is provided with: (1) _Buffer_ _Text_ (current events), (2)
_Supplementary Text_ (retrieved history), and (3) two
summaries, including **Summary A** (Baseline, _k_ =
0, consolidates only buffer events) and **Summary**
**B** (Test, _k_ = 15, establishes cross-event links).
The judge identifies cross-event links present in
Summary B that are absent from Summary A, then
classifies each cross-event link to judge if the link


Table 4: Robustness check of memory systems across different LLM judges on the LoCoMo dataset. The table is
categorized by three judge models: gpt-4o-mini, Qwen2.5-32B-Instruct, and DeepSeek-V3.2. **Bold**
and underline denote the best and second-best results within each judge block, respectively. _↑_ : larger is better.


**Judge Model** **Method** **Overall** _↑_ **Single Hop** **Multi Hop** **Temporal** **Open Domain**







Table 5: Inter-judge agreement and correlation across
different judge model pairs. GPT, Qwen, and DS denote gpt-4o-mini, qwen2.5-32b-instruct,
and DeepSeek-V3.2, respectively.


**Judge Pair** **Cohen’s** _κ_ **Pearson** _r_ _p_ **-value**


Qwen vs. DS 0.8395 0.8438 _<_ 10 _[−]_ [300]

Qwen vs. GPT 0.8326 0.8362 _<_ 10 _[−]_ [300]

DS vs. GPT 0.8184 0.8234 _<_ 10 _[−]_ [300]


**Overall (Fleiss’** _κ_ **)** **0.8341** - 

is spurious. The full prompt templates are provided
in Figure 18 and Figure 19.

To evaluate the specific impact of our grounding
anchors, we conduct a sensitivity analysis by comparing our default _Constrained_ prompt against an
_Unconstrained_ variant. As illustrated in Figure 20,
the _Unconstrained_ version is created by removing
explicit requirements for timestamp citations and
concrete dependency focus (highlighted in gray).

The results in Table 7 demonstrate that removing these grounding constraints leads to a dramatic
surge in hallucination rates across all judge models. This trend underscores that the high fidelity of
StructMem’s hierarchical organization is directly
tied to our constrained synthesis mechanism, confirming that the **Memory** **Consolidation** of our
hierarchical memory is highly faithful to the source
context.



Table 6: Hallucination rates in the event-level extraction
stage across 10 conversations.


**Conversation** **DS** **Qwen** **GPT** **Mean**


conv-26 2.07% 0.52% 0.78% 1.12%
conv-30 1.81% 0.60% 4.83% 2.41%
conv-41 2.04% 1.88% 2.35% 2.09%
conv-42 3.16% 1.97% 3.94% 3.02%
conv-43 2.94% 1.63% 3.10% 2.56%
conv-44 1.68% 0.92% 1.68% 1.43%
conv-47 5.28% 2.44% 3.05% 3.59%
conv-48 2.71% 1.45% 1.08% 1.75%
conv-49 3.25% 1.16% 1.62% 2.01%
conv-50 3.55% 2.84% 4.26% 3.55%


**Overall** **2.84%** **1.61%** **2.63%** **2.36%**


**A.7** **Prompt Templates**


We present the prompt templates used for memory

construction, question answering, and evaluation
in StructMem.


For memory construction, we design prompts for
different paradigms implemented in the LightMem
framework. For Flat Memory, the factual entry extraction prompt (Figure 4 and Figure 5) guides the
model to decompose utterances into objective event
descriptions. For StructMem, the relational entry
extraction prompt (Figure 6 and Figure 7) instructs
the model to capture interaction dynamics, causal


Table 7: Detailed cross-event link quality comparison across conversations. **S**, **T**, and **R** denote the number of
**S** purious links, **T** otal links, and the error **R** ate (%), respectively. GPT, Qwen, and DS represent gpt-4o-mini,
Qwen2.5-32B-Instruct, and DeepSeek-V3.2. _Constrained_ is the default setting for StructMem.


**Judge:** **GPT** **Judge:** **Qwen** **Judge:** **DS**
**Conversation** **Config**

**S** **T** **R (%)** **S** **T** **R (%)** **S** **T** **R (%)**


Constrained 0 83 0.00 3 70 4.29 1 12 8.33
conv-26
Unconstrained 4 72 5.56 23 101 22.77 10 58 17.24


Constrained 0 73 0.00 0 59 0.00 1 23 4.35
conv-30
Unconstrained 4 84 4.76 6 79 7.59 2 44 4.55


Constrained 4 108 3.70 1 131 0.76 1 31 3.23
conv-41
Unconstrained 13 104 12.50 20 115 17.39 6 74 8.11


Constrained 0 95 0.00 5 93 5.38 1 47 2.13
conv-42
Unconstrained 8 100 8.00 20 106 18.87 6 65 9.23


Constrained 0 104 0.00 5 130 3.85 6 40 15.00
conv-43
Unconstrained 4 109 3.67 11 114 9.65 9 74 12.16


Constrained 0 110 0.00 9 91 9.89 2 39 5.13
conv-44
Unconstrained 6 104 5.77 30 135 22.22 16 88 18.18


Constrained 1 107 0.93 4 90 4.44 0 33 0.00
conv-47
Unconstrained 11 103 10.68 32 108 29.63 16 69 23.19


Constrained 1 102 0.98 2 101 1.98 0 36 0.00
conv-48
Unconstrained 5 100 5.00 27 107 25.23 11 62 17.74


Constrained 0 94 0.00 2 90 2.22 0 52 0.00
conv-49
Unconstrained 7 81 8.64 14 86 16.28 10 61 16.39


Constrained 0 106 0.00 2 113 1.77 1 45 2.22
conv-50
Unconstrained 10 109 9.17 30 114 26.32 18 92 19.57


**Constrained** **6** **982** **0.61%** **33** **968** **3.41%** **13** **358** **3.63%**
**Overall**
**Unconstrained** **72** **966** **7.45%** **213** **1065** **20.00%** **104** **687** **15.14%**



influences, and temporal dependencies. The narrative synthesis prompt (Figure 8) consolidates local and retrieved contexts into coherent summaries
during Macro Synthesis. For Graph Memory, the
entity extraction prompt (Figure 9) identifies key
entities from dialogue. The entity deduplication
prompt (Figure 10) normalizes extracted entities
to eliminate redundancy. The relation extraction
prompt (Figure 11) constructs connections between
entities. The relation deduplication prompt (Figure 12) resolves contradictions in the knowledge
graph.


For question answering, we provide separate
prompts tailored to different memory architectures.
Figure 13 shows the prompt for StructMem with
dual-circuit retrieval that leverages both atomic entries and consolidated summaries. Figure 14 and
Figure 15 present prompts adapted for flat memory



and graph-based memory baselines, respectively.

For evaluation, we use the LLM-as-a-judge
prompt (Figure 16) to assess response correctness
and coherence.

For fidelity and hallucination analysis, we provide the specialized templates used for memory auditing. Figure 17 presents the prompt for verifying
event-level extraction. Figures 18 and 19 presents
the prompt for verifying cross-event consolidation.
We also include the _Unconstrained_ synthesis tem
plate in Figure 20, where the grounding constraints
are intentionally removed to evaluate the impact of
explicit temporal anchors on reducing hallucinated
associations.


**A.8** **Case Study**


Table 8 presents a case study comparing how different memory paradigms handle temporal reasoning


**Query** _When did Caroline and Melanie go to a pride festival together?_


**Method** **Retrieved Content**


**Flat Memory** **Factual Entries:**

             - Caroline attended pride parade on 2023-08-11

              - Caroline had a blast at Pride fest last year (recorded 2023-08-17)

              - Melanie enjoyed time with the whole gang at Pride fest (recorded 2023-08-17)


**Graph Memory** **Factual Entries:**

             - Caroline attended pride parade on 2023-08-11

              - Caroline had a blast at Pride fest last year (recorded 2023-08-17)

              - Melanie enjoyed time with the whole gang at Pride fest (recorded 2023-08-17)
**Entity-Relation Graph:**

               - caroline _→_ attended _→_ pride_parade

               - caroline _→_ had_blast_at _→_ pride_fest

             - melanie _→_ enjoyed_time_at _→_ pride_fest

             - melanie _→_ expressed_excitement _→_ caroline’s_pride_involvement


**StructMem** **Event Memory:**

             - Caroline attended pride parade on 2023-08-11

              - Caroline had a blast at Pride fest last year (recorded 2023-08-17)

              - Melanie showed interest in Caroline’s pride parade experience

              - Melanie enjoyed time with the whole gang at Pride fest (recorded 2023-08-17)

             - Melanie expressed excitement about Caroline’s LGBTQ+ community involvement
**Synthesis Memory:**
“On August 17, 2023... **As they reminisced about their enjoyable time at Pride fest last year**, Melanie
suggested planning a family outing, while Caroline proposed a special outing just for the two of them
this summer...”


**Prediction** **Flat Memory:** “They haven’t gone together.”
**Graph Memory:** “Last month, June 2023.”
**StructMem:** “Last year, August 2022.”
**Reference:** 2022


Table 8: Case study comparing three memory paradigms on joint participation reasoning. Flat Memory and Graph
Memory cannot establish co-participation from isolated entries, while StructMem’s synthesis correctly identifies
shared experiences.



over joint participation. The query asks when two
speakers attended an event together, requiring inference over co-participation relationships that are not
explicitly stated in individual conversational turns.

**Flat Memory** retrieves factual entries independently: Caroline attended Pride fest "last year"
(temporally anchored to August 17, 2023, referring to 2022), while Melanie enjoyed time "with
the whole gang" at Pride fest. Without any mechanism to connect these isolated facts, the system
concludes "they haven’t gone together," failing to
recognize the implicit joint participation.

**Graph** **Memory** constructs entity-relation
triples on top of the same factual entries. While the
graph captures individual attendance, these remain
isolated nodes without explicit co-participation
edges. The post-hoc graph structure cannot infer
that mentions of the same event by different speakers within the same conversation indicate joint attendance. Consequently, it produces an incorrect
temporal inference: "Last month, June 2023."

**StructMem** addresses this limitation through
two mechanisms. First, relational entries capture in


terpersonal dynamics during extraction: "Melanie
showed interest in Caroline’s pride parade experience" provides crucial context about their shared
discussion. Second, synthesis consolidates temporally co-located entries. When Caroline’s Pride
fest mention appears adjacent to Melanie’s in the
chronologically sorted context, the relational entry’s possessive pronoun "their" signals joint participation. The synthesis then makes this implicit
connection explicit: "their enjoyable time at Pride
fest last year," enabling the system to correctly answer "Last year, August 2022."

This case demonstrates why extraction-time
structural capture outperforms post-hoc graph construction for temporal reasoning. By organizing information hierarchically during memory formation
rather than overlaying structure afterward, StructMem preserves the temporal and relational context
necessary for inferring implicit relationships across
conversational turns.


Figure 4: Factual entry extraction prompt (Part 1).


Figure 5: Factual entry extraction prompt (Part 2).


Figure 6: Relational entry extraction prompt (Part 1).


Figure 7: Relational entry extraction prompt (Part 2).


Figure 8: Narrative synthesis prompt for Synthesis.







Figure 9: Entity extraction prompt


Figure 10: Entity deduplicate prompt









Figure 11: Relation extraction prompt


Figure 12: Relation deduplicate prompt







Figure 13: Question answering prompt for StructMem system.


Figure 14: Question answering prompt for flat memory systems.


Figure 15: Question answering prompt for graph-based memory systems.


Figure 16: Evaluate prompt for assessing response quality.


Figure 17: Prompt for assessing extraction fidelity.


Figure 18: Prompt for assessing consolidation fidelity (Part 1).


Figure 19: Prompt for assessing consolidation fidelity (Part 2).


Figure 20: Narrative synthesis prompt for Unconstrained Synthesis. The text highlighted in gray represents the
grounding constraints that are active in our default _Constrained_ setting but disabled for the _Unconstrained_ variant to
evaluate their impact on memory fidelity.


