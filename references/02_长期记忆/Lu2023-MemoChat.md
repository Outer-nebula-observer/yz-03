## **MemoChat: Tuning LLMs to Use Memos for Consistent Long-Range** **Open-Domain Conversation**

**Junru Lu** [1] **, Siyu An** [2] **, Mingbao Lin** [2] **, Gabriele Pergola** [1] **, Yulan He** [3] **,**

**Di Yin** [2] **, Xing Sun** [2] **and Yunsheng Wu** [2]

1University of Warwick, 2Tecent YouTu Lab, 3King’s College London
1{junru.lu, gabriele.pergola}@warwick.ac.uk, 3yulan.he@kcl.ac.uk
2{siyuan, marlin, endymecyyin, winfredsun, simonwu}@tencent.com


**Abstract**



We propose MemoChat, a pipeline for refining
instructions that enables large language models
(LLMs) to effectively employ self-composed
memos for maintaining consistent long-range
open-domain conversations. We demonstrate a
long-range open-domain conversation through
iterative “ _memorization-retrieval-response_ ” cycles. This requires us to carefully design tailored tuning instructions for each distinct stage.
The instructions are reconstructed from a collection of public datasets to teach the LLMs
to memorize and retrieve past dialogues with
structured memos, leading to enhanced consistency when participating in future conversations. We invite experts to manually annotate a test set designed to evaluate the consistency of long-range conversations questions.
Experiments on three testing scenarios involving both open-source and API-accessible chatbots at scale verify the efficacy of MemoChat,
which outperforms strong baselines [1] .


**1** **Introduction**


Large language models (LLMs) have brought about
a substantial revolution, fundamentally changing
our lifestyle. They have emerged as a new platform
that connects the realms of academia and industry
within the field of artificial intelligence (Zhao et al.,
2023b; Yang et al., 2023). In particular, LLMs have
demonstrated an enhanced ability to synchronize
effectively with human cognitive processes (Du
et al., 2022; Taori et al., 2023; Zheng et al., 2023;
Liu et al., 2023c; Ouyang et al., 2022) and consequently have served as a foundation towards creating human-like conversational dialogues.

In contrast to the traditional dialogue systems,
which mainly involve short conversations on similar topics (Dinan et al., 2019b; Komeili et al., 2022;
Dinan et al., 2019a), the emerging trend in humanchatbot interaction is characterized by longer conversations encompassing diverse topics (Kim et al.,


1Codes: [https://github.com/LuJunru/MemoChat.](https://github.com/LuJunru/MemoChat)



Figure 1: An example of a long-range open-domain
conversation. It contains multiple topics.


2023). Figure 1 illustrates an example of such
long-range conversations with more than 20 exchanges between a human user and a chat bot. It
involves several sequential topics such as “ _Quan-_
_tum_ _Physics_ ” (1 to 8 turns), “ _Business_ _Etiquette_
_in Japan_ ” (11 to 14 turns) and “ _Polynomial Math_
_Problem_ ” (16 to 18 turns), while other topics are
simply referred to as “ _MULTIPLE TURNS_ ”. Also,
two topics-related long-range questions are raised
subsequently, including one for evoking memories
associated with “ _Business Etiquette in Japan_ ”, and
the other for retrieving historical information pertaining to “ _Quantum_ _Physics_ ”. Such long-range
open-domain conversations that involve diverse
topics presents a challenge for conventional methods, as they struggle to effectively address the issue of retaining contextual coherence over long
stretches of discourse. One possible strategy is to
expand the input text window (Tworkowski et al.,
2023; Li et al., 2023; Ding et al., 2023). For example, positional interpolation (Chen et al., 2023)
was presented to empower RoPE-based (Su et al.,
2022) LLMs with a text window that is 600 times
longer than its original pretraining version. Unfortunately, the window length can not be arbitrar

ily expanded (Beltagy et al., 2020; Kitaev et al.,
2020). Another potential solution is to resort to
additional memories for tracking the history of conversations (Zhong et al., 2023; Zhao et al., 2023a).
For example, MPC was proposed (Lee et al., 2023)
to regularly store persona summaries of recent conversations as history, then use new user query _**Q**_ to
retrieve the top-K history _**D**_ via an external DPR
retriever (Karpukhin et al., 2020), and finally generate a new response based on both _**Q**_ and _**D**_ . Similarly, an event and user portrait memory managed
with FAISS (Johnson et al., 2019) were adopted
by (Zhong et al., 2023). Despite the advantage in
retaining infinite contextual inputs, compared with
text window extension, memory mechanism may
cause accumulation errors during the retrieval of
past evidence (Xu et al., 2022b). As a result, how
to enhance the accuracy of memory recall and improve the response consistency of LLM-powered
chatbots in long-range open-domain conversation
remains unsolved (Xu et al., 2022a).


In this paper, we are particularly interested in
building memory-enhanced chatbots. Instead of
replying on external tools for memory creation
and recall (Lee et al., 2023; Zhong et al., 2023;
Hu et al., 2023; Kynoch and Latapie, 2023), we
propose a streamlined approach where we eliminate the need for these complex associate modules. Instead, we create a simplified pipeline that
solely utilizes LLMs to power chatbots. The proposed memo-equipped pipeline, MemoChat, aims
for guiding LLMs to use simple on-the-fly memos
for maintaining consistent long-range open-domain
conversation. We base our approach on the concept
of “ _memorization-retrieval-response_ ” loops within
the context of long-range open-domain conversations. To achieve this, except for zero-shot learning
with chatbots accessed via public APIs (OpenAI,
2023; Google, 2023), we reconstruct a series of
instructions from publicly available datasets (Adlakha et al., 2022; Chen et al., 2021; Ghosal et al.,
2023) to fine-tune open-source LLM-powered chatbots. This fine-tuning process helps the chatbots
familiarize themselves with each stage within the
loop, and employ structured memos for maintaining a consistent long-range conversation. For fair
evaluation, we invite experts to manually annotate a
testing set specifically designed to evaluate the consistency of long-range conversations across three
different types of testing scenarios. We verify the
effectiveness of the proposed MemoChat through a



comprehensive evaluation involving both a chatbot
accessible via public API and four different opensource LLMs. This evaluation is carried out using
a very strong LLM judge (Zheng et al., 2023). The
contributions of this paper are listed as follows:


  - We introduce MemoChat, an instruction tuning
pipeline, to assist LLM-powered chatbots carrying on consistent long-range open-domain
conversations through an on-the-fly memo.


  - We leverage several publicly available
datasets to reconstruct instructions to help
open-source LLMs familiarize themselves
with the MemoChat pipeline.


  - We curate an expert-annotated evaluation set,
which serves as a benchmark for assessing
response consistency. Experiments on both
open-source and API-accessible chatbots verify the efficacy of MemoChat.


**2** **Related Work**


**2.1** **Long-Range Open-Domain Conversation**


Long-range open-domain conversation has been a
widely explored task recently. Doc2Dial, a goaloriented document-grounded dialogue dataset is
proposed by (Feng et al., 2020), including around
48k long-range conversations with an average of
14 turns. MultiSessionChat is a dataset concerning
one long-range conversation over multiple sessions
(Xu et al., 2022a). While most of these traditional
datasets focus on few-topic human-human scenarios, there has been a proliferation on newly multitopic human-chatbot scenarios (Kim et al., 2023).

The challenges of long-range open-domain conversations lie on the answerability of open-domain
questions and the capacity of long-range input understanding. External knowledge graph was incorporated to improve the answer ability of out-ofdistribution open-domain questions (Zhou et al.,
2020). With the development of LLMs, LLMpowered chatbots have largely improved their answering ability (Shuster et al., 2022b,a). On the
other hand, various strategies have been proposed
to tackle the challenge of long-range input understanding. One possible strategy is to use additional
memory to filter shorter key facts in the past longrange history to replace it. MPC (Lee et al., 2023)
and MemoryBank (Zhong et al., 2023) were proposed to use additional memory and external retriever to manage persona, event or user portrait


Figure 2: The overall architecture of our proposed MemoChat pipeline. While maintaining a chatting stream between
the human user and the chatbot (left part), the chatbot will have a memo-equipped inner thinking (right part).



information. Our work differs from existing studies in that we solely teach the chatbot to self-use
memos, and we focus on summarizing all facts in
the history instead of partial persona or event facts.


**2.2** **Instruction Tuning**


Instruction tuning is a widely used strategy to
fine-tune LLMs on tasks with meta-instruction
ahead (Wei et al., 2022a). The effectiveness of
instruction tuning has been proved on many tasks,
including text reasoning (Sanh et al., 2022), humanbot alignment (Ouyang et al., 2022), document
ranking (Qin et al., 2023; Sun et al., 2023), document retrieval (Mueller et al., 2023), and general
conversation ability (Gupta et al., 2022). In this
work, we spend low-cost yet carefully design instructions to teach LLM-powered chatbots for selfusing on-the-fly memo to strengthen the response
consistency within long-range chatting stream.


**3** **Methodology**


**3.1** **Formulation**


We start with formulating the long-range open
domain conversation as Generative Question Answering (GQA), in which a chatbot is expected to
generate an answer _Y_ [ˆ] = argmax _Y_ _p_ ( _Y |_ _**x**_ _[q]_ _,_ _**x**_ _[h]_ ),
given previous conversation history _**x**_ _[h]_ and current user query _**x**_ _[q]_ . To improve the response
consistency of _Y_ [ˆ], our MemoChat takes an step
forward and proposes to decompose the longrange open-domain conversation as a three-stage



“ _memorization-retrieval-response_ ” loop, intending

to retrieve query-related evidences _**x**_ _[h][′]_ from structured memo _**x**_ _[m]_, which is modeled as _**x**_ _[m]_ =
_f_ ( _**x**_ _[h]_ ), _**x**_ _[h][′]_ = _g_ ( _**x**_ _[q]_ _,_ _**x**_ _[m]_ ), with _f_ ( _∗_ ) and _g_ ( _∗_ ) as
the memo build-up and retrieval functions respectively. Therefore, GQA in our MemoChat can be
reformulated as as _Y_ [ˆ] = argmax _Y_ _p_ ( _Y |_ _**x**_ _[q]_ _,_ _**x**_ _[h][′]_ ).


**3.2** **MemoChat**


Figure 2 depicts the overall framework of our proposed MemoChat pipeline, which assigns the chatbot with a “ _memorization-retrieval-response_ ” loop
of inner thinking. In the left of Figure 2, the user
starts with the topic of “ _Quantum Physics_ ”, then
ends with “ _Business_ _Etiquette_ ” topic after multiple turns of the conversation. Very different
from traditional methods that retrieve directly on
these accumulated dialogues, the chatbot under our
MemoChat, as shown on the upper-right of Figure 2,
will automatically builds and updates a structured
on-the-fly memo, storing past dialogues in categories. Then, the retrieval is conducted over all
recordings according to their topics and summaries.
In the bottom-left, Figure 2 illustrates an occurrence in which the chatbot is required to link the
concept of “ _Quantum Physics_ ” aforementioned in
the very beginning of the conversation. The chatbot
manages to recall related evidences, and generate a
consistent answer in bottom-right Figure 2.

By allowing chatbots to reorganize the dialogue
histories according to different topics, summarize


Figure 3: Instruction templates in MemoChat (better view in colors). Three instructions are carefully designed
to serve MemoChat inner thinking pipeline including “Memo Writing”, “Memo Retrieval” and “Chat w/ Memo”,
partitioned by gray boxes. The organization of all instructions consists of general task introduction ( _green area_ ),
main body of task-oriented inputs ( _bisque area_ ), and detailed task explanation ( _yellow area_ ). Ground-truth answers
are provided during fine-tuning ( _blue area_ ). More specific examples are provided in Appendix B.



the partial dialogue faithfully, and retrieve one or
more query-related evidences quickly, MemoChat
becomes a simple-yet-effective pipeline to guide
chatbots to generate consistent responses.


**Instruction Structure** . “ _Memorization-retrieval-_
_response_ ” mechanism stores the past dialogues in
memo _**x**_ _**[m]**_, recalls query-related evidences _**x**_ _**[h][′]**_

from memo, and generates response _Y_ [ˆ] based on
retrieved evidences. Different from previous literature (Lee et al., 2023; Zhong et al., 2023) requiring
additional complex modules, we reorganize the dialogue histories into structured on-the-fly memos,
such that the basic LLM-powered chatbots can simultaneously handle the memo. Thus, we develop
three instructions for each stage as shown in Figure 3. Overall, all instructions follow similar structure: (1) description of each stage task ( _green area_ );
(2) main body of task-oriented inputs ( _bisque area_ );
(3) explanation of each task ( _yellow_ _area_ ). The
combination of three serves as the input prompts of
the chatbot and ground-truth answers are provided
( _blue area_ ) for fine-tuning.


Herein, the “Memo Writing” task asks the chatbot to read a task conversation, partition the conversation based on all possible topics, write short
summaries for every sub-dialogues, and write the



above results to the memo in a JSON format with
each instance including keys of “topic”, “summary”
and “dialogues”. We consolidate the task explanation with Chain-of-Thought (CoT) (Wei et al.,
2022b) and In-Context Learning (ICL) (Dong et al.,
2023). The “Memo Retrieval” task asks the chatbot
to read a user query and a series of topic options,
select out one or more related options and report
option ID with a special format. Inspired by previous literature (Rajpurkar et al., 2018), one “ _None_
_of the others (NOTO)_ ” option is randomly inserted
in the candidate options, given that the user may
arbitrarily launch a new topic. To support a fast
implementation, we retrieve related contents only
upon the “topics” and “summaries” from the on-thefly memo. Finally, the “Chat w/ Memo” task feeds
the latest query, prefixed with retrieved evidences
and recent dialogues, to the chatbot. With these
related evidences, the chatbot can now produce
more consistent response even in the long-range
open-domain conversations.


**Dataset Reconstruction** . To implement our Memo
pipeline, we reconstruct 10k instruction data from
three public dialogue datasets including TopicoQA (Adlakha et al., 2022), DialogSum (Chen
et al., 2021) and Alpaca-GPT4 (Ghosal et al., 2023).


|Col1|Data Size|Avg. Tokens|Sources|
|---|---|---|---|
|**Memo Writing**|3,046|951.92|1,790 from T*<br>1,256 from D*|
|**Memo Retrieval**|3,654|329.86|1,719 from T*<br>1,935 from D*|
|**Chat w/ Memo**|3,300|273.04|1,602 from D*<br>1,698 from A*|


Table 1: Statistics of our instruction training sets. “Avg.
Tokens” stands for the average token number of each
instruction. T*, D* and A* stand for TopicoQA, DialogSum and Alpaca-GPT4 dataset, respectively.


TopicoQA covers 3.9k conversations that involve 4
topics and 13 turns of dialogue on average. DialogSum covers 13k conversations that focus on 1 topic
across 5.5 turns on average, and provides manual
summary for each conversation. Both TopicoQA
and DialogSum use human-human conversations in
spoken style, and focus on daily life scenes. While
Alpaca-GPT4 is a human-chatbot 1-turn conversation dataset created by running GPT4 API (OpenAI,
2023) on the Alpaca dataset (Taori et al., 2023). It
covers more sophisticated topics in written style.
We sample 1.6k cases to balance the instructions

from another two datasets.


Table 1 reports the statistics and sources of the
three instruction training sets. The “Memo Writing” set consists of 1,790 instances from TopicoQA
and 1,256 samples from DialogSum. Given the unavailability of “summary” information, we only
construct “topic” and “dialogues” in the memo for
conversations from TopicoQA dataset. Considering
only one topic in each conversation of DialogSum,
we combine a few variable set of conversations to
mimic a multi-topic long-range conversation. Similar strategies are adopted to form “Memo Retrieval”
set that contains 1,719 and 1,935 instructions from
TopicoQA and DialogSum, respectively. For each
retrieval instruction, its query sentence is made
up with several sequential sentences from original conversation and related topics are extracted
as options. The “ _NOTO_ ” option is inserted with
a probability of 10%. The “Chat w/ Memo” set
comprises 1,602 and 1,698 instructions from DialogSum and Alpaca-GPT4. The former aims at
generating instructions with related evidences, and
the latter generates instructions without any related
evidences to fit with unseen topics.


In conclusion, we succeed in building three training sets to achieve our “memorization-retrievalresponse” loop. Besides, a total of 400 evaluation



instructions are similarly constructed from the testing sets of the source datasets, including 160, 82
and 65 samples for “Memo Writing”, “Memo Retrieval” and “Chat w/ Memo”, respectively.
**Challenges** . To our best knowledge, we are the
first to build such a group of systematic sequential
instructions. We report major challenges for any
potential future follow-ups. Some specific examples are available in Appendix C.

The first challenge faceed is “Prompt Copy” in
which the LLMs found a special shortcut to directly copy format examples in the prompts as the
answer. To avoid this, we suggest to use dummy
variables to replace any numerical values to avoid
possible answer leaking. The second challenge
refers to “Catastrophic Forgetting” in which the
chatbots lean towards generating early-stopped or
repeated answers if the volume of “Chat w/ Memo”
is less than “Memo Writing” or “Memo Retrieval”.
A balanced volume is encouraged by mixing with
certain amount of dialogue corpus to maintain the
chatting ability (Ghosal et al., 2023). We consider
Alpaca-GPT4 in our construction. The third challenge lies in “Prompt Misplacement” in which the
chatbots performance degrade when swapping the
input order of the main body of task-oriented inputs ( _bisque area_ in Figure 3) and explanation of
each task ( _yellow area_ in Figure 3). Task explanation attached at the end is crucial for chatbots to
understand instructions better (Liu et al., 2023b).


**4** **Experiments**


**4.1** **Experimental Setting**


**Datasets** . Except for the reconstructed instruction
datasets, we also invite three experts to manually
annotate a new long-range open-domain conversation dataset to validate the response consistency.
The annotated dataset, referred to as MT-Bench+,
is built based on MT-Bench (Zheng et al., 2023),
a human-chatbot testing dataset with a total of 80
two-turn open-domain questions, covering topics
such as “STEM exams” and “literary writing”. This
is achieved by: (1) expanding each of the twoturn questions to a four-turn version by the experts;
(2) sampling 2 _∼_ 4 questions from every 3 _∼_ 4 of
four-turn versions to form a long-range chatting
stream with a total of 12 _∼_ 15 turns; (3) adding longrange questions to the end of the chatting streams
for “Retrospection”, “Continuation” and “Conjunction” by the experts. Herein, “Retrospection” is
restricted to the aforementioned terms related ques

tions ( _e.g._, span extraction), “Continuation” makes
a further task based on previous knowledge ( _e.g._,
story completion), and “Conjunction” is to ask a
cross-topic response ( _e.g._, redo task 2 in reference
to task 1). We build 18 questions for each of the
three types in MT-Bench+, 54 in total.
**Baselines** . We consider the popular Fastchat-T5-3b
and Vicuna-7b/13b/33b (Zheng et al., 2023), which
are human-aligned versions of Flan-T5 (Chung
et al., 2022) and Llama (Touvron et al., 2023) with
massive human-bot dialogues (Kim et al., 2023), respectively, as the baseline models. We further finetune them on our reconstructed instruction data to
form our MemoChat. For all experiments, we set the
text window to 2k to follow off-the-shelf conventions (Workshop, 2023). However, our MemoChat
keeps the flexibility and scalability to larger windows as chatbots can automatically adjust memory
range. As for downstream consistency testing, one
public API and two open-source memory-assistant
chatbots are included as baselines:


  - **ChatGPT-2k** . We use the same 2k text window to arrange the input of gpt-3.5-turbo API.


  - **MPC-ChatGPT** . Plug MPC (Lee et al., 2023)
pipeline with ChatGPT-2k.


  - **MemoryBank-ChatGPT** . Plug MemoryBank (Zhong et al., 2023) with ChatGPT-2k.


GPT4 API is excluded as GPT4-generated data
are included in the training set, and we rely on
GPT4 for evaluation in downstream chatting test.
**Metrics** . We adopt four groups of metrics to evaluate the performance of intermediate instruction
tuning and the downstream consistency checking.
Since we ask chatbots to partition dialogue histories to build memo, in reference to Name Entity
Recognition (NER) (Ding et al., 2021), we therefore evaluate generated topics and summaries in
“Memo Writing” task with precision ( _**P**_ ), recall ( _**R**_ )

and micro F1-score ( _**F**_ **1** ) only when predicted subsession range and ground truth matches. In detail,
the _**P**_ score of topic checking uses exact match
following NER, while the _**P**_ score of summary
checking is replaced with float BertScore (Zhang
et al., 2020) number varying between 0 to 1. We
use regular F1-score ( _**F**_ **1** ) on “Memo Retrieval”,
and use BertScore to check the semantic similarity between generated response and golden references in “Chat w/ Memo” task. As for downstream
response consistency checking, inspired by LLMas-a-judge strategy (Zheng et al., 2023), we select



|Col1|Fastchat-<br>T5-3B|Vicuna-7B|Vicuna-13B|Vicuna-33B|
|---|---|---|---|---|
|**Batch**|8|16|8|4|
|**Accumulations**|2|1|2|4|
|**HyperParams**|Epoch=3, Global Batch=128, Seq Len=2048,<br>Lr=2e-5, Warmup Ratio=0.04, Gen Temperature=0.2|Epoch=3, Global Batch=128, Seq Len=2048,<br>Lr=2e-5, Warmup Ratio=0.04, Gen Temperature=0.2|Epoch=3, Global Batch=128, Seq Len=2048,<br>Lr=2e-5, Warmup Ratio=0.04, Gen Temperature=0.2|Epoch=3, Global Batch=128, Seq Len=2048,<br>Lr=2e-5, Warmup Ratio=0.04, Gen Temperature=0.2|
|**CPU RAM (GB)**|73.01|189.49|356.42|790.57|
|**Per GPU (GB)**|37.12|33.22|37.29|38.96|
|**Training (10k)**|1.04h|0.98h|2.35h|5.74h|


Table 2: Hyperparameters and training cost. We use
full-param training instead of light training such as
LoRA (Hu et al., 2022).


out related dialogue histories, and the long-range
checking question with corresponding response,
then use GPT4 to score the faithfulness with an
integer scale 1 _∼_ 100. It has been explored in (Pan
et al., 2023) to show that credible LLMs such as
GPT4 have a comparable analysis ability to human.
**Hyperparameters** . Our training details are reported in Table 2. We fine-tune all models on one
node server equipped with 900G CPU RAM and
8 A100 40G GPUs. Although single batch size
is set in difference due to model size, we maintain a same global batch. Meanwhile, all other
hyperparameters are set as the same. The optimizer
is _AdamW_ (Loshchilov and Hutter, 2019) and the
scheduler is _WarmupDecayLR_ (Goyal et al., 2017).
We incorporate Deepspeed (Ren et al., 2021) and

Flash Attention (Dao et al., 2022) to improve the
training efficiency. Hardware consumption and
time cost are reported as well. Although the training efficiency can be improved, we keep related parameters consistent with Alpaca and Vicuna (Taori
et al., 2023; Zheng et al., 2023) for stable training.


**4.2** **Experimental Results**


**Memo-usage Ability** . We report results of tuning
open-source LLMs to obtain memo-usage ability.
Table 3 coincides the conclusion that larger LLMs
are better zero- and few-shot learners (Brown et al.,
2020). Largest ChatGPT and GPT4 models show
a strong zero-shot inference ability, reaching over
60 and 50 scores on retrieval and chatting tasks,
respectively. In contrast, smaller LLMs cannot
fully understand prompts, especially the dummy
templates such as “N#M” in “Memo Retrieval”.
Among open-source LLMs, it is clearly that larger
models have better initial understanding towards
new instructions, although the performance gap
keeps in a low level range from 0.3 to 4.0 _**F**_ **1** _**∗**_ and
_**F**_ **1** # scores on “Memo Writing” and “Retrieval”.




|Col1|Col2|Memo Writing|Col4|Memo<br>Retrieval|Chat with<br>Memo|
|---|---|---|---|---|---|
|||**Topic**|**Summary**|**Summary**|**Summary**|


|Col1|Col2|Topic|Summary|Retrieval|Memo|
|---|---|---|---|---|---|
|**Setting**|**Model**|**_P ∗_**<br>**_R∗_**<br>**_F_1****_∗_**|**_P_** #<br>**_R_**#<br>**_F_1**#|**_F_1**|**BertScore**|
|Zero-shot|GPT4<br>ChatGPT<br>Fastchat-T5-3B<br>Vicuna-7B<br>Vicuna-13B<br>Vicuna-33B|7.28<br>9.84<br>8.37<br>0.52<br>1.25<br>0.74<br>0.00<br>0.00<br>0.00<br>0.34<br>0.54<br>0.42<br>0.61<br>1.07<br>0.78<br>1.31<br>2.15<br>1.63|43.72<br>48.01<br>45.76<br>5.37<br>12.27<br>7.47<br>0.00<br>0.00<br>0.00<br>1.64<br>4.48<br>2.40<br>3.53<br>7.26<br>4.75<br>4.21<br>7.96<br>5.51|79.19<br>66.54<br>0.99<br>0.00<br>2.55<br>4.25|50.31<br>50.86<br>20.83<br>19.55<br>29.10<br>45.94|
|10% Training<br>(1,000)|MemoChat-Fastchat-T5-3B<br>MemoChat-Vicuna-7B<br>MemoChat-Vicuna-13B<br>MemoChat-Vicuna-33B|5.34<br>5.01<br>5.17<br>10.77<br>11.27<br>11.01<br>26.34<br>26.30<br>26.32<br>24.77<br>28.98<br>26.71|26.18<br>18.73<br>21.84<br>16.98<br>17.31<br>17.14<br>42.88<br>42.88<br>42.88<br>41.32<br>44.16<br>42.69|68.24<br>63.09<br>69.04<br>78.95|52.03<br>55.39<br>55.83<br>56.07|
|100% Training<br>(10,000)|MemoChat-Fastchat-T5-3B<br>MemoChat-Vicuna-7B<br>MemoChat-Vicuna-13B<br>MemoChat-Vicuna-33B|38.57<br>35.60<br>37.02<br>45.08<br>52.58<br>43.79<br>53.83<br>52.77<br>53.30<br>**57.07**<br>**57.07**<br>**57.07**|63.87<br>63.25<br>63.56<br>57.27<br>57.84<br>57.55<br>64.20<br>64.20<br>64.20<br>**67.99**<br>**68.65**<br>**68.32**|83.02<br>82.33<br>86.26<br>**87.79**|54.69<br>55.62<br>57.30<br>**58.68**|


Table 3: Evaluation results of intermediate instruction tuning on LLMs with different scales. We report all scores
in the unit of %. _**F**_ **1** _**∗**_, _**F**_ **1** # and _**F**_ **1** refer to NER-based metrics, BertScore-fused NER-based metrics and regular
metrics, respectively. So do the _**P**_ and _**R**_ scores. 1,000 and 10,000 refer to the scale of data used for fine-tuning.

|Col1|Col2|Auto Rating by GPT4-4k (1 to 100)|
|---|---|---|
|**Type**|**Model**|**Retrospection**<br>**Continuation**<br>**Conjunction**<br>**Average**|
|2k text window|ChatGPT-2k|52.11<br>55.33<br>48.22<br>51.89|
|Public APIs with<br>additional memory<br>storage and recall|MPC-ChatGPT (Lee et al., 2023)<br>MemoryBank-ChatGPT (Zhong et al., 2023)<br>MemoChat-ChatGPT|53.00<br>61.22<br>49.33<br>54.52<br>23.39<br>55.28<br>48.67<br>42.44<br>66.28<br>73.50<br>72.50<br>70.76|
|Fine-tuned<br>open-source LLMs|MemoChat-Vicuna-13B (1k)<br>MemoChat-Vicuna-33B (1k)<br>MemoChat-Fastchat-T5-3B (10k)<br>MemoChat-Vicuna-7B (10k)<br>MemoChat-Vicuna-13B (10k)<br>MemoChat-Vicuna-33B (10k)|64.78<br>56.06<br>51.67<br>57.50<br>56.61<br>55.11<br>50.94<br>54.22<br>30.50<br>29.94<br>21.56<br>27.33<br>61.17<br>61.22<br>50.78<br>57.72<br>62.28<br>63.17<br>**52.83**<br>59.43<br>**69.00**<br>**65.00**<br>50.56<br>**61.52**|



Table 4: Evaluation results of downstream response consistency. Except for the aforementioned baselines,
MemoChat-ChatGPT combines public APIs with MemoChat baseline. “ _Fine-tuned open-source LLMs_ ” models are
fine-tuned with designed instructions. 1k and 10k refer to the scale of data used in accordance with Table 3.



To check the learning ability of open-source
LLMs, two groups of settings are taken. The
10% and 100% training groups refer to fine-tune
LLMs with 1k and 10k samples, respectively. It
can be observed that, with only 1k samples, larger
LLMs MemoChat-Vicuna-13B and -33B can familiarize the instructions better than smaller LLMs
MemoChat-Fastchat-T5-3B and -Vicuna-7B, raising significant performance gaps by 15 _∼_ 30 scores
on _**F**_ **1** _**∗**_ and _**F**_ **1** # in “Memo Writing”. Also, except for “Memo Retrieval”, MemoChat-Vicuna13B maintains similar performance to -33B in this
setting, which may be due to insufficient training. When training set is scaled to 10k, the largest
MemoChat-Vicuna-33B has the most potential to



push highest scores over all tasks. In general, all
models fully fine-tuned with 10k training data show
better performance than ChatGPT/GPT4, and their
performances are gradually improved when model
scale increases. The only reversal happens on
MemoChat-Vicuna-7B and -T5-3B, where -7B gets
lower scores on summary generation and retrieval.


**Response Consistency** . As in Table 3, MemoChatVicuna-13B and -33B are able to reach similar zeroshot performance of ChatGPT and GPT4 fine-tuned
with 1k instruction. Thus, we suppose MemoChatVicuna-13B (1k), -33B (1k) and all MemoChat
(10k) models have obtained self-use ability of
on-the-fly memos, and to be involved in consistency testing. We report results of response con

Figure 4: Case analysis of different types of testing questions with different chatbots. We show the key points ( **in**
**bold** ) in the answers, and some parts of the answer context are replaced by **ellipsis** due to length limitation.



sistency checking in Table 4: (1) Compared with
previous baselines mostly focusing on persona or
user portrait summary, MemoChat guides the chatbots to produce a general summary, which significantly improves the downstream performance by
7.0 _∼_ 19.5 score on average, as shown by the results of MPC-ChatGPT, MemoryBank-ChatGPT
and MemoChat-ChatGPT; (2) Except for T5-3B,
all fine-tuned MemoChat models show better performance than ChatGPT-2k by 2.4 to 9.7 scores
on average, proving the effectiveness of reconstructed instructions; (3) When the LLMs are not
fully fine-tuned, MemoChat-Vicuna-13B (1k) even
show higher performance than -33B version by 3.3
score on average. The less-finetuned -13B model
gets a pretty good score 64.78 on the retrospection questions, due to its tendency to generate short
answers and thus memorize more. (4) When all
open-source LLMs are fully fine-tuned, the average performance is improved as model scale grows.
However, the performances on conjunction questions remain similar. This may be due to the limitation of long-form question answering ability, while
ChatGPT is an expert (Liu et al., 2023a).


**Case Analysis** . We report a specific case in Figure 4. The case starts with discussions on “ _Ma-_
_chine_ _Learning_ ” and “ _Antitrust_ _Laws_ ” in first 8
turns. After over 7 turns of other topics, we raise
two long-range questions. The first retrospection
question asks about the number of “ _types_ _of_ _ma-_
_chine learning_ ”, which requires to recall relevant
“ _Machine Learning_ ” topics and accurately count the



term number in the first local question. ChatGPT2k can not correctly answer the question due to
text window limits, while both MemoChat-based
chatbots work. The second question belongs to
conjunction type that cross-topic retrieval and understanding are required. ChatGPT-2k completely
misinterpretes it. While MemoChat-ChatGPT precisely links antitrust laws to machine learning. The
MemoChat-Vicuna-33B (10k) correctly identifies
that the “ _Sherman Antitrust Act_ ”, the specific name
of an antitrust law, applies to the machine learning
industry, although it incorrectly states “ _the Euro-_
_pean_ _Commission_ _fined_ _Google_ ” under the Sherman Act which is an American legislation, with the
European Commission operating instead under EU
law. Thus, GPT4 scores ChatGPT-2k, MemoChatChatGPT, and MemoChat-Vicuna-33B (10k), with
1, 100, and 90, respectively.


**5** **Conclusion**


We proposed MemoChat, an instruction tuning

pipeline to teach LLMs to self-use on-the-fly
structured memos towards consistent long-range
open-domain conversations, which can be decomposed as “ _memorization-retrieval-response_ ” loops.
We carefully designed three trainable instructions

based on public datasets for structured writing, fast
retrieval, and interations with memos. An expertannotated downstream evaluation set was curated
and provided. Experiments on three testing scenarios and various LLM-based chatbots demonstrated
the effectiveness of MemoChat.


**References**


Vaibhav Adlakha, Shehzaad Dhuliawala, Kaheer Sule
man, Harm de Vries, and Siva Reddy. 2022. [Top-](https://doi.org/10.1162/tacl_a_00471)
iOCQA: Open-domain [conversational](https://doi.org/10.1162/tacl_a_00471) question answering with [topic](https://doi.org/10.1162/tacl_a_00471) switching. _Transactions_ _of_ _the_
_Association for Computational Linguistics_, 10.


Iz Beltagy, Matthew E Peters, and Arman Cohan.

2020. Longformer: The long-document transformer.
_arXiv:2004.05150_ .


Tom Brown, Benjamin Mann, Nick Ryder, Melanie

Subbiah, Jared D Kaplan, Prafulla Dhariwal, Arvind
Neelakantan, Pranav Shyam, Girish Sastry, Amanda
Askell, et al. 2020. Language models are few-shot
learners. _Advances in Neural Information Processing_
_Systems_, 33.


Shouyuan Chen, Sherman Wong, Liangjian Chen, and

Yuandong Tian. 2023. Extending context window of

large language models via positional interpolation.
_arXiv:2306.15595_ .


Yulong Chen, Yang Liu, Liang Chen, and Yue Zhang.

2021. DialogSum: [A real-life scenario dialogue sum-](https://doi.org/10.18653/v1/2021.findings-acl.449)
[marization dataset.](https://doi.org/10.18653/v1/2021.findings-acl.449) In _Findings of the Association for_
_Computational Linguistics:_ _ACL-IJCNLP 2021_ .


Hyung Won Chung, Le Hou, Shayne Longpre, Bar
ret Zoph, Yi Tay, William Fedus, Eric Li, Xuezhi
Wang, Mostafa Dehghani, Siddhartha Brahma, et al.
2022. Scaling instruction-finetuned language models.
_arXiv:2210.11416_ .


Tri Dao, Dan Fu, Stefano Ermon, Atri Rudra, and

Christopher Ré. 2022. Flashattention: Fast and
memory-efficient exact attention with io-awareness.
_Advances in Neural Information Processing Systems_,

35.


Emily Dinan, Varvara Logacheva, Valentin Malykh,

Alexander Miller, Kurt Shuster, Jack Urbanek,
Douwe Kiela, Arthur Szlam, Iulian Serban, Ryan
Lowe, Shrimai Prabhumoye, Alan W Black, Alexander Rudnicky, Jason Williams, Joelle Pineau, Mikhail
Burtsev, and Jason Weston. 2019a. [The second con-](http://arxiv.org/abs/1902.00098)
[versational intelligence challenge (convai2).](http://arxiv.org/abs/1902.00098)


Emily Dinan, Stephen Roller, Kurt Shuster, Angela Fan,

Michael Auli, and Jason Weston. 2019b. Wizard
of Wikipedia: Knowledge-powered conversational
agents. In _Proceedings of the International Confer-_
_ence on Learning Representations (ICLR)_ .


Jiayu Ding, Shuming Ma, Li Dong, Xingxing Zhang,

Shaohan Huang, Wenhui Wang, Nanning Zheng, and
Furu Wei. 2023. Longnet: [Scaling transformers to](http://arxiv.org/abs/2307.02486)
[1,000,000,000 tokens.](http://arxiv.org/abs/2307.02486)


Ning Ding, Guangwei Xu, Yulin Chen, Xiaobin Wang,

Xu Han, Pengjun Xie, Haitao Zheng, and Zhiyuan
Liu. 2021. Few-NERD: A [few-shot](https://doi.org/10.18653/v1/2021.acl-long.248) named entity
[recognition dataset.](https://doi.org/10.18653/v1/2021.acl-long.248) In _Proceedings of the 59th An-_
_nual Meeting of the Association for Computational_



_Linguistics and the 11th International Joint Confer-_
_ence on Natural Language Processing_, pages 3198–
3213.


Qingxiu Dong, Lei Li, Damai Dai, Ce Zheng, Zhiyong

Wu, Baobao Chang, Xu Sun, Jingjing Xu, Lei Li, and
Zhifang Sui. 2023. [A survey on in-context learning.](http://arxiv.org/abs/2301.00234)


Zhengxiao Du, Yujie Qian, Xiao Liu, Ming Ding,

Jiezhong Qiu, Zhilin Yang, and Jie Tang. 2022. [GLM:](https://doi.org/10.18653/v1/2022.acl-long.26)
[General language model pretraining with autoregres-](https://doi.org/10.18653/v1/2022.acl-long.26)
[sive blank infilling.](https://doi.org/10.18653/v1/2022.acl-long.26) In _Proceedings of the 60th An-_
_nual Meeting of the Association for Computational_
_Linguistics (Volume 1:_ _Long Papers)_ .


Song Feng, Hui Wan, Chulaka Gunasekara, Siva Patel,

Sachindra Joshi, and Luis Lastras. 2020. [doc2dial:](https://doi.org/10.18653/v1/2020.emnlp-main.652) A
[goal-oriented document-grounded dialogue dataset.](https://doi.org/10.18653/v1/2020.emnlp-main.652)
In _Proceedings of Empirical Methods in Natural Lan-_
_guage Processing (EMNLP)_ .


Deepanway Ghosal, Yew Ken Chia, Navonil Majumder,

and Soujanya Poria. 2023. Flacuna: Unleashing
the problem solving power of vicuna using flan finetuning. _arXiv:2307.02053_ .


Google. 2023. Palm 2 technical report.
_arXiv:2305.10403_ .


Priya Goyal, Piotr Dollár, Ross Girshick, Pieter No
ordhuis, Lukasz Wesolowski, Aapo Kyrola, Andrew
Tulloch, Yangqing Jia, and Kaiming He. 2017. Accurate, large minibatch sgd: Training imagenet in 1
hour. _arXiv:1706.02677_ .


Prakhar Gupta, Cathy Jiao, Yi-Ting Yeh, Shikib Mehri,

Maxine Eskenazi, and Jeffrey Bigham. 2022. [In-](https://aclanthology.org/2022.emnlp-main.33)
structDial: Improving [zero](https://aclanthology.org/2022.emnlp-main.33) and few-shot generalization in dialogue [through](https://aclanthology.org/2022.emnlp-main.33) instruction tuning. In
_Proceedings_ _of_ _the_ _2022_ _Conference_ _on_ _Empirical_
_Methods in Natural Language Processing_ .


Chenxu Hu, Jie Fu, Chenzhuang Du, Simian Luo, Junbo

Zhao, and Hang Zhao. 2023. Chatdb: [Augmenting](http://arxiv.org/abs/2306.03901)
[llms with databases as their symbolic memory.](http://arxiv.org/abs/2306.03901)


Edward J Hu, Yelong Shen, Phillip Wallis, Zeyuan

Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, and
Weizhu Chen. 2022. Lora: Low-rank adaptation of
large language models. In _International Conference_
_on Learning Representations_ .


Jeff Johnson, Matthijs Douze, and Hervé Jégou. 2019.

Billion-scale similarity search with GPUs. _IEEE_
_Transactions on Big Data_, 7(3):535–547.


Vladimir Karpukhin, Barlas Oguz, Sewon Min, Patrick

Lewis, Ledell Wu, Sergey Edunov, Danqi Chen, and
Wen-tau Yih. 2020. [Dense passage retrieval for open-](https://doi.org/10.18653/v1/2020.emnlp-main.550)
[domain question answering.](https://doi.org/10.18653/v1/2020.emnlp-main.550) In _Proceedings of the_
_2020 Conference on Empirical Methods in Natural_
_Language Processing (EMNLP)_ .


Sungdong Kim, Sanghwan Bae, Jamin Shin, Soyoung

Kang, Donghyun Kwak, Kang Min Yoo, and Minjoon Seo. 2023. Aligning large language models
through synthetic feedback. _arXiv:2305.13735_ .


Nikita Kitaev, Łukasz Kaiser, and Anselm Levskaya.

2020. Reformer: The efficient transformer. In _Inter-_
_national Conference on Learning Representations_ .


Mojtaba Komeili, Kurt Shuster, and Jason Weston. 2022.

[Internet-augmented dialogue generation.](https://doi.org/10.18653/v1/2022.acl-long.579) In _Proceed-_
_ings of the 60th Annual Meeting of the Association for_
_Computational Linguistics (Volume 1:_ _Long Papers)_ .


Brandon Kynoch and Hugo Latapie. 2023. [Recallm:](http://arxiv.org/abs/2307.02738)

[An architecture for temporal context understanding](http://arxiv.org/abs/2307.02738)
[and question answering.](http://arxiv.org/abs/2307.02738)


Gibbeum Lee, Volker Hartmann, Jongho Park, Dimitris

Papailiopoulos, and Kangwook Lee. 2023. [Prompted](https://aclanthology.org/2023.findings-acl.277)
[LLMs as chatbot modules for long open-domain con-](https://aclanthology.org/2023.findings-acl.277)
[versation.](https://aclanthology.org/2023.findings-acl.277) In _Findings of the Association for Compu-_
_tational Linguistics:_ _ACL 2023_ .


Dacheng Li, Rulin Shao, Anze Xie, Ying Sheng, Lian
min Zheng, Joseph E. Gonzalez, Ion Stoica, Xuezhe
Ma, and Hao Zhang. 2023. How long can open[source llms truly promise on context length?](https://lmsys.org/blog/2023-06-29-longchat)


Hanmeng Liu, Ruoxi Ning, Zhiyang Teng, Jian Liu, Qiji

Zhou, and Yue Zhang. 2023a. [Evaluating the logical](http://arxiv.org/abs/2304.03439)
[reasoning ability of chatgpt and gpt-4.](http://arxiv.org/abs/2304.03439)


Nelson F Liu, Kevin Lin, John Hewitt, Ashwin Paran
jape, Michele Bevilacqua, Fabio Petroni, and Percy
Liang. 2023b. Lost in the middle: How language
models use long contexts. _arXiv:2307.03172_ .


Xiao Liu, Hanyu Lai, Hao Yu, Yifan Xu, Aohan Zeng,

Zhengxiao Du, Peng Zhang, Yuxiao Dong, and Jie
Tang. 2023c. Webglm: [Towards](http://arxiv.org/abs/2306.07906) an efficient webenhanced question [answering](http://arxiv.org/abs/2306.07906) system with human
[preferences.](http://arxiv.org/abs/2306.07906)


Ilya Loshchilov and Frank Hutter. 2019. Decoupled

weight decay regularization. In _International Confer-_
_ence on Learning Representations_ .


Aaron Mueller, Kanika Narang, Lambert Mathias, Qi
fan Wang, and Hamed Firooz. 2023. [Meta-training](http://arxiv.org/abs/2307.00119)
with demonstration [retrieval](http://arxiv.org/abs/2307.00119) for efficient few-shot
[learning.](http://arxiv.org/abs/2307.00119)


OpenAI. 2023. [Gpt-4 technical report.](http://arxiv.org/abs/2303.08774)


Long Ouyang, Jeff Wu, Xu Jiang, Diogo Almeida, Car
roll L. Wainwright, Pamela Mishkin, Chong Zhang,
Sandhini Agarwal, Katarina Slama, Alex Ray, John
Schulman, Jacob Hilton, Fraser Kelton, Luke Miller,
Maddie Simens, Amanda Askell, Peter Welinder,
Paul Christiano, Jan Leike, and Ryan Lowe. 2022.
Training language models to follow instructions with
human feedback. In _Thirty-Sixth Conference on Neu-_
_ral Information Processing Systems_ .


Alexander Pan, Jun Shern Chan, Andy Zou, Nathaniel

Li, Steven Basart, Thomas Woodside, Hanlin Zhang,
Scott Emmons, and Dan Hendrycks. 2023. Do the
rewards justify the means? measuring trade-offs between rewards and ethical behavior in the machiavelli
benchmark. In _International Conference on Machine_
_Learning_ . PMLR.



Zhen Qin, Rolf Jagerman, Kai Hui, Honglei Zhuang,

Junru Wu, Jiaming Shen, Tianqi Liu, Jialu Liu, Donald Metzler, Xuanhui Wang, and Michael Bendersky. 2023. [Large language models are effective text](http://arxiv.org/abs/2306.17563)
[rankers with pairwise ranking prompting.](http://arxiv.org/abs/2306.17563)


Pranav Rajpurkar, Robin Jia, and Percy Liang. 2018.

Know what you don’t [know:](https://doi.org/10.18653/v1/P18-2124) Unanswerable ques[tions for SQuAD.](https://doi.org/10.18653/v1/P18-2124) In _Proceedings of the 56th Annual_
_Meeting_ _of_ _the_ _Association_ _for_ _Computational_ _Lin-_
_guistics_ .


Jie Ren, Samyam Rajbhandari, Reza Yazdani Am
inabadi, Olatunji Ruwase, Shuangyan Yang, Minjia
Zhang, Dong Li, and Yuxiong He. 2021. _{_ ZeROOffload _}_ : Democratizing _{_ Billion-Scale _}_ model
training. In _2021_ _USENIX_ _Annual_ _Technical_ _Con-_
_ference_ .


Victor Sanh, Albert Webson, Colin Raffel, Stephen H

Bach, Lintang Sutawika, Zaid Alyafeai, Antoine
Chaffin, Arnaud Stiegler, Teven Le Scao, Arun Raja,
et al. 2022. Multitask prompted training enables zeroshot task generalization. In _The Tenth International_
_Conference on Learning Representations_ .


Kurt Shuster, Mojtaba Komeili, Leonard Adolphs,

Stephen Roller, Arthur Szlam, and Jason Weston.
2022a. Language models that seek for knowledge: Modular search & generation for dialogue and
prompt completion. In _Findings of the Association_
_for Computational Linguistics:_ _EMNLP 2022_ .


Kurt Shuster, Jing Xu, Mojtaba Komeili, Da Ju,

Eric Michael Smith, Stephen Roller, Megan Ung,
Moya Chen, Kushal Arora, Joshua Lane, et al.
2022b. Blenderbot 3: a deployed conversational
agent that continually learns to responsibly engage.
_arXiv:2208.03188_ .


Jianlin Su, Yu Lu, Shengfeng Pan, Ahmed Murtadha,

Bo Wen, and Yunfeng Liu. 2022. [Roformer:](http://arxiv.org/abs/2104.09864) En[hanced transformer with rotary position embedding.](http://arxiv.org/abs/2104.09864)


Weiwei Sun, Lingyong Yan, Xinyu Ma, Pengjie Ren,

Dawei Yin, and Zhaochun Ren. 2023. Is [chatgpt](http://arxiv.org/abs/2304.09542)
good at search? [investigating large language models](http://arxiv.org/abs/2304.09542)
[as re-ranking agent.](http://arxiv.org/abs/2304.09542)


Rohan Taori, Ishaan Gulrajani, Tianyi Zhang, Yann

Dubois, Xuechen Li, Carlos Guestrin, Percy Liang,
and Tatsunori B Hashimoto. 2023. Stanford alpaca:
An instruction-following llama model.


Hugo Touvron, Thibaut Lavril, Gautier Izacard, Xavier

Martinet, Marie-Anne Lachaux, Timothée Lacroix,
Baptiste Rozière, Naman Goyal, Eric Hambro, Faisal
Azhar, et al. 2023. Llama: Open and efficient foundation language models. _arXiv:2302.13971_ .


Szymon Tworkowski, Konrad Staniszewski, Mikołaj

Pacek, Yuhuai Wu, Henryk Michalewski, and Piotr
Miło´s. 2023. Focused transformer: Contrastive training for context scaling. _arXiv:2307.03170_ .


Jason Wei, Maarten Bosma, Vincent Y Zhao, Kelvin

Guu, Adams Wei Yu, Brian Lester, Nan Du, Andrew M Dai, and Quoc V Le. 2022a. Finetuned
language models are zero-shot learners. In _The Tenth_
_International_ _Conference_ _on_ _Learning_ _Representa-_
_tions_ .


Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten

Bosma, Brian Ichter, Fei Xia, Ed Chi, Quoc Le, and
Denny Zhou. 2022b. Chain-of-thought prompting
elicits reasoning in large language models. In _36th_
_Conference on Neural Information Processing Sys-_
_tems_ .


BigScience Workshop. 2023. Bloom: A 176b[parameter open-access multilingual language model.](http://arxiv.org/abs/2211.05100)


Jing Xu, Arthur Szlam, and Jason Weston. 2022a. Be
yond goldfish memory: Long-term open-domain conversation. In _Proceedings of the 60th Annual Meeting_
_of the Association for Computational Linguistics_ .


Xinchao Xu, Zhibin Gou, Wenquan Wu, Zheng-Yu Niu,

Hua Wu, Haifeng Wang, and Shihang Wang. 2022b.
Long time no see! open-domain conversation with
long-term persona memory. In _Findings of the Asso-_
_ciation for Computational Linguistics:_ _ACL 2022_ .


Jingfeng Yang, Hongye Jin, Ruixiang Tang, Xiao
tian Han, Qizhang Feng, Haoming Jiang, Bing
Yin, and Xia Hu. 2023. Harnessing the power of

llms in practice: A survey on chatgpt and beyond.
_arXiv:2304.13712_ .


Tianyi Zhang, Varsha Kishore, Felix Wu, Kilian Q.

Weinberger, and Yoav Artzi. 2020. [Bertscore:](https://openreview.net/forum?id=SkeHuCVFDr) Evaluating text [generation](https://openreview.net/forum?id=SkeHuCVFDr) with bert. In _International_
_Conference on Learning Representations_ .


Kang Zhao, Wei Liu, Jian Luan, Minglei Gao, Li Qian,

Hanlin Teng, and Bin Wang. 2023a. [Unimc:](http://arxiv.org/abs/2306.10543) A uni[fied framework for long-term memory conversation](http://arxiv.org/abs/2306.10543)
[via relevance representation learning.](http://arxiv.org/abs/2306.10543)


Wayne Xin Zhao, Kun Zhou, Junyi Li, Tianyi Tang,

Xiaolei Wang, Yupeng Hou, Yingqian Min, Beichen
Zhang, Junjie Zhang, Zican Dong, et al. 2023b. A
survey of large language models. _arXiv:2303.18223_ .


Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan

Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin,
Zhuohan Li, Dacheng Li, Eric Xing, et al. 2023.
Judging llm-as-a-judge with mt-bench and chatbot
arena. _arXiv:2306.05685_ .


Wanjun Zhong, Lianghong Guo, Qiqi Gao, He Ye, and

Yanlin Wang. 2023. Memorybank: [Enhancing large](http://arxiv.org/abs/2305.10250)

[language models with long-term memory.](http://arxiv.org/abs/2305.10250)


Hao Zhou, Chujie Zheng, Kaili Huang, Minlie Huang,

and Xiaoyan Zhu. 2020. KdConv: [A](https://doi.org/10.18653/v1/2020.acl-main.635) Chinese
multi-domain dialogue [dataset](https://doi.org/10.18653/v1/2020.acl-main.635) towards multi-turn
[knowledge-driven conversation.](https://doi.org/10.18653/v1/2020.acl-main.635) In _Proceedings of_
_the 58th Annual Meeting of the Association for Com-_
_putational Linguistics_ .



**A** **Basic Published Datasets**


In Table 5, we draw examples of the basic published datasets that used for instruction reconstruction in our MemoChat pipeline.


**TopicoQA**


A: of the four galilean moons which is the closest
to Jupiter
B: Io
A: who discovered it?
B: Galileo Galilei
···
A: does it belong to any album?
B: 'A Night at the Opera”


'topic': 'Io (moon)', 'start': 1, 'end': 2
'topic': 'Galilean moons', 'start': 3, 'end': 4
···
'topic': 'Bohemian Rhapsody', 'start': 13, 'end': 20


**DialogSum**


A: Ms. Dawson, I need you to take a dictation for
me.
B: Yes, sir.
···
A: Yes. Please get this memo typed up and distributed to all employees before 4 pm.


'summary1': 'Ms. Dawson helps A to write a memo
to ···', 'topic1': 'communication method'
'summary2': 'In order to prevent employees from
wasting time ···', 'topic2': 'company policy'
'summary3': 'Ms. Dawson takes a dictation for A
about prohibiting ···', 'topic3': 'dictation'


**Alpaca-GPT4**


User: Make a list of behaviors that show strong
leadership.
GPT: 1. Clear communication: Strong leaders communicate ···10. Continuous learning: Effective
leaders strive for continuous learning ···


Table 5: Examples of three basic published datasets we
adopts in the main paper. Parts of contents are replaced
by **ellipsis** due to page length limits.


**B** **Involved Prompts**


As a supplement, we list complete examples of
involved prompts used in both intermediate memorelated tuning and downstream response consistency checking. Table 6, 7, 8, and 9 refer to complete instructions for intermediate “Memo Writ

Figure 5: Examples to illustrate observed instruction design challenges (better view in colors): “Prompt Copy” (1a,
1b), “Catastrophic Forgetting” (2) and “Prompt Misplacement” (3). Inferior instruction designs are shown in gray
boxes, paired with parallel superior instruction design shown in green boxes. The key features are in bold.



ing”, “Memo Retrival”, “Chat w/ Memo” tasks,
and downstream response consistency checking,
respectively. As mentioned in Figure 3, all instructions share a similar structure, including a general
task introduction, context body of task-specific inputs, and a detailed task introduction. Ground truth
are provided for during tuning.


**C** **Instruction Design Challenges**


We provide examples of instruction design chal
lenges reported in above sessions. The examples
of “Prompt Copy”, “Catastrophic Forgetting” and
“Prompt Misplacement” are illustrated in Figure 5.


We suppose to use dummy variables to replace
numerical values, in order to avoid the first challenge “Prompt Copy”. Any in-distribution values
such as line number in “Memo Writing“ or option
id in “Memo Retrival“ may lead to a shortcut that
LLMs can directly cope the values to meet format
requirement, while dummy variables will push the
models to understand prompts indeed. Sub-figures



(1a) and (1b) illustrate “Prompt Copy” obstacle in
“Memo Writing” and “Memo Retrieval”, respec
tively. The replacement of dummy inputs “M” and
“N” with actual numbers can obviously lead to rea
sonable generation. The second challenge lies in
“Catastrophic Forgetting“, which refers to the re
sponse collapse if all types of instructions are not
balanced. As shown in the Sub-figure (2), when
the scale of “Chat w/ Memo“ data is significantly
smaller than the others, the chat response will be
meaningless repetition. While such ill generation
can be significantly eliminated once sufficient chatting corpus are supplemented. When is comes to
the third challenge “Prompt Misplacement“, we
supposed that the most important component of
prompt should be placed to the end of prompt. Otherwise, the LLMs tend to do natural text generation
instead of memo-related tasks. The Sub-figure (3)
shows that when detailed task explanation is placed
in front of task content, in “Memo Writing”, the
chatbot does unexpected conversation continuation.


**Memo Writing Instruction**


You will be shown a 20-line Task Conversation between user and bot. Please read, memorize, and
understand Task Conversation, then complete the task under the guidance of Task Introduction.


```
Task Conversation
(line 1) user: Anna just email to say that the managers meeting is put off till next Monday. Will you have
everything ready by then, Sabrina? Hey Sabrina, what's wrong?
(line 2) bot: I'm so worried. I haven't heard from my sister for 2 weeks.
(line 3) user: How often do you call each other?
(line 4) bot: Normally at least once a week. But she's now a volunteer teacher in a mountain village in
Africa. I can only write her.
(line 5) user: The Mail can be really slow sometimes. I'm sure you'll hear from her soon.
(line 6) bot: I hope so.
···
(line 14) bot: It'll take about 20 minutes.
(line 15) user: The streets are heavy with traffic at this time of a day, are they?
(line 16) bot: Yes, they are.
(line 17) user: Is it the rush hour?
(line 18) bot: Yes, it is. Are you in a hurry, sir?
(line 19) user: No, I'm not. Would you please drive slowly and carefully?
(line 20) bot: Yes, sir.
```


```
Task Introduction:
Based on the Task Conversation, perform the following actions:
1 - Conclude all possible topics in the conversation with concise spans.
2 - Determine the chat range of each topic. These ranges should be a set of non-intersecting, sequentially
connected end-to-end intervals.
3 - Conclude a summary of each chat with brief sentences.
4 - Report topic, summary and range results in JSON format only with the assigned keys: 'topic', 'summary',
'start', 'end'. For example, assuming an M-line conversation talks about 'banana'from line 1 to line N, then

turns to talk about 'mango'from line N+1 to line M. Thus, its task result could be: [{'topic': 'banana',
'summary': 'user talks banana with bot.', 'start': 1, 'end': N}, {'topic': 'mango', 'summary': 'bot brings

mango for user.', 'start': N+1, 'end': M}].
Besides, following notations are provides:
1 - For each element of Task Conversation's JSON result, the value of 'end'should be smaller than the
value of 'start', while both values should be larger than 0 but not exceed the total num of Task Conversation
lines 20.
2 - Intersecting intervals such as {'topic': 'apple', 'summary': 'user and bot share apples.', 'start': K, 'end':
N} and {'topic': 'pear', 'summary': 'bot sends pear to user.', 'start': N-2, 'end': M} are illegal.
```


Task Result:


[{'topic': 'worry', 'summary': 'Sabrina is worried about her sister because she hasn't heard from her sister
for 2 weeks. user comforts her.', 'start': 1, 'end': 8}, {'topic': 'taxi conversation', 'summary': 'user takes
bot's taxi to the railway station. As user is not rush, bot will drive slowly and carefully.', 'start': 9, 'end':
20}]


Table 6: A complete typical example of Memo Writing instruction, with ground truth provided.


**Memo Retrieval Instruction**


You will be shown 1 Query Sentence and 5 Topic Options. Please read, memorize, and understand given
materials, then complete the task under the guidance of Task Introduction.


```
Query Sentence:
I need help with the office party. Yes, of course. We could split it. What part would you like to do, the
food or the entertainment? I think we will have opportunities to meet each other in the future. OK, I
think it's time for you to check in. If you run into any difficulty, we'll be here to assist you immediately.
Your credit is fine, Sir. Now, tell me, what is it that you need the loan for? I've just bought a second hand

apartment and I'm looking to do some renovations. You know, a bit of decorating, some new furniture,
nothing flashy.
Topic Options:
(1) see off. Mr. Wang sees user off at the airport and they share good expectations of their business
relationship.
(2) party preparation. bot helps user to prepare for the party. They decide the style, food, and music and
will plan it in detail on Friday.
(3) NOTO. None of the others.
(4) Loan for renovations. bot wants to go for the Petty Consumer Loan for the renovations of his apartment.
user says the maximum they can lend bot is 20,000 RMB and bot accepts it.
(5) annoying things. Gav had a good sleep last night but worries about the traffic jam and classes to teach.
bot asks Gav's plan for the weekend and bot gives the suggestions when Gav feels upset.
```


```
Task Introduction:
Select one or more topics from Topic Options that relevant with Query Sentence. Note that there is a
NOTO option, select it if all other topic options are not related to Query Sentence. Do not report the
option content, but only report selected option numbers in a string separated with '#'. For example, if topic
option N and M are chosen, then the output is: N#M. For Query Sentence in the task, any chosen option
numbers should be larger than 0 but not exceed the total num of Topic Options 5.
```


Task Result:


1#2#4


Table 7: A complete typical example of Memo Retrieval instruction, with ground truth provided.


**Chat w/ Memo Instruction**


You are an intelligent dialog bot. You will be shown Related Evidences supporting for User Input, and
Recent Dialogs between user and you. Please read, memorize, and understand given materials, then
generate one concise, coherent and helpful response.


```
Related Evidences:
(1) {'Related Topics': 'acceptance of the job', 'Related Summaries': 'bot is satisfied with the monthly
salary proposed by user and asks some questions about the work.', 'Related Dialogs': 'user: What's your
expected salary? ### bot: What is important to me is the job and the people who I will be working with,
so regarding salary, I leave it to you and I am sure that you will make me a fair offer. ### user: I can
offer you 5, 000 yuan per month. Raises are given after three months'probation period according to your
performance. Is this satisfactory? ### bot: Yes, it is quite satisfactory. I accept it. ### user: Any question
about the work? ### bot: To whom should I report? ### user: The general manager of your section. ###
bot: What are the benefits? ### user: We'll offer that on holidays. ### bot: I would like to know if there
would be any opportunity to work abroad in the future? ### user: Yes, we have inspection abroad. ###
bot: Thank you. Then I think it's time for us to sign a letter of intent. ### user: Okay.'}
(2) {'Related Topics': 'find a job', 'Related Summaries': 'user wants to find a job at the computer center.',
'Related Dialogs': 'user: I'd like to find a job. ### bot: We have several part-time jobs available here,
Would you like to look through the list? ### user: Yes, thank you. I'd like to apply for the job at the
computer center. ### bot: Please fill out the form.'}
(3) {'Related Topics': 'check in', 'Related Summaries': 'It's user's first time on a plane. bot tells user how to
check in.', 'Related Dialogs': 'user: Excuse me, this is my first time on a plane. How do I check in? ###
bot: May I see your ticket, please? ### user: Yes. Here you are. ### bot: You can get a boarding pass at
that counter. Do you have anything to check in? ### user: No, I only have a handbag. ### bot: Then you
could wait in the departure area after going through security. ### user: Is that all? ### bot: Yeah, I think
so. It is very simple. ### user: I see. Thank you very much.'}
```


```
Recent Dialogs:
user: What's the tallest building? ### bot: You mean the white building near the playground? ### user:
Yes. ### bot: That is the library. And it has more than 1, 000, 000 books. ### user: What's the building to

the south of the library? ### bot: You know, our school is divided into two parts, the junior high school
and the senior high school. That is the new classroom building for our senior high school. ### user: Is
there a swimming pool in your school? ### bot: Yes. There is a large swimming pool, but it is only
available in summer. ### user: I do envy you. And I hope I can enter your school one day. ### bot: I
believe that you can make your dream come true.
```


User Input:
user: What is your salary now? ### bot:


My present pay is RMB 3, 000 yuan each month.


Table 8: A complete typical example of Chat w/ Memo instruction, with ground truth provided.


**GPT4 Evaluation Prompt**


You are an impartial judge. You will be shown Related Conversation History, User Question and Bot
Response.


```
Related Conversation History


user: Please describe the concept of machine learning. Could you elaborate on the differences between
supervised, unsupervised, and reinforcement learning? Provide real-world examples of each.
bot: Sure! Machine learning ··· In summary, machine learning is an powerful tool for making predictions
and decisions based on data ···


user: In your last example of reinforcement learning, can we use supervised learning to solve it?
bot: Supervised learning would not be the best approach for solving the self-driving car problem, because
··· or penalties, which is more suitable for autonomous driving.


user: Discuss antitrust laws and their impact on market competition. Compare the antitrust laws in US
and China along with some case studies.
bot: Antitrust laws are designed to promote and maintain market competition by preventing anticompetitive behavior by companies ··· playing field for all companies.


user: Pick one case study and explain it in detail.
bot: One notable case study is the US government's antitrust lawsuit against Microsoft. ··· is considered
a prime example of how antitrust laws can be used to promote market competition.
```


```
User Question
user: Does the law we discussed apply to the machine learning industry? Use previous examples to
explain your answer.
```


```
Bot Response
bot: Yes, the law we discussed, the Sherman Antitrust Act, applies to the machine learning industry. The
Sherman Antitrust Act prohibits anti-competitive behavior, such as price-fixing, market allocation, and
monopolization. In the machine learning industry, there have been examples of companies collaborating
to fix prices or engaging in other anti-competitive behavior, which would be in violation of the Sherman
Antitrust Act. For example, in 2010, several technology companies, including Apple, Google, and Adobe,
were accused of conspiring to suppress wages by agreeing not to poach each other's employees. This
agreement was found to be in violation of the Sherman Antitrust Act, and the companies were forced
to abandon the agreement and pay a settlement. Additionally, in 2018, the European Commission fined
Google $5 billion for violating the Sherman Antitrust Act by engaging in anti-competitive behavior
with its Android operating system. The Commission found that Google had required mobile device
manufacturers to pre-install its search engine and Chrome browser on their devices, which had the effect
of stifling competition from other search engines and browsers.
```


Please evaluate whether Bot Response is faithful to the content of Related Conversation History to answer
User Question. Begin your evaluation by providing a short explanation, then you must rate Bot Response
on an integer rating of 1 to 100 by strictly following this format: [[rating]].


Table 9: Example of GPT4 Evaluation Prompt. Parts of the content are replaced by **ellipsis** due to page length limits.


