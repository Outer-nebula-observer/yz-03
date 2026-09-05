## **LLMLingua: Compressing Prompts for Accelerated Inference** **of Large Language Models**

**Huiqiang Jiang, Qianhui Wu, Chin-Yew Lin, Yuqing Yang, Lili Qiu**

Microsoft Corporation
{hjiang, qianhuiwu, cyl, yuqing.yang, liliqiu}@microsoft.com



**Abstract**


Large language models (LLMs) have been applied in various applications due to their astonishing capabilities. With advancements in
technologies such as chain-of-thought (CoT)
prompting and in-context learning (ICL), the
prompts fed to LLMs are becoming increasingly lengthy, even exceeding tens of thousands
of tokens. To accelerate model inference and
reduce cost, this paper presents _LLMLingua_,
a coarse-to-fine prompt compression method
that involves a budget controller to maintain
semantic integrity under high compression ratios, a token-level iterative compression algorithm to better model the interdependence between compressed contents, and an instruction tuning based method for distribution alignment between language models. We conduct
experiments and analysis over four datasets
from different scenarios, _i.e._, GSM8K, BBH,
ShareGPT, and Arxiv-March23; showing that
the proposed approach yields state-of-the-art
performance and allows for up to 20x compression with little performance loss. [1]


**1** **Introduction**


The widespread adoption of ChatGPT has transformed numerous scenarios by harnessing the powerful generalization and reasoning capabilities of
large language models (LLMs). In practical applications, crafting suitable prompts is crucial
and usually involves techniques such as chain-ofthought, in-context learning, and retrieving related
documents or historical conversations (Wei et al.,
2022; Chase, 2022). While these methods can
elicit highly effective generations by activating
LLMs’ domain-specific knowledge, they often require longer prompts. Therefore, striking a balance
between the massive computational demands of
LLMs and the need for longer prompts has become
an urgent issue. Some studies attempt to accelerate
model inference by modifying the parameters of


[1Our code is available at https://aka.ms/LLMLingua.](https://aka.ms/LLMLingua)



LLMs through quantization (Dettmers et al., 2022;
Xiao et al., 2023), compression (Frantar and Alistarh, 2023), etc. However, these approaches may
be not suitable when the LLMs can be accessed via
APIs only.


Approaches that attempt to reduce the length of
original prompts while preserving essential information have emerged lately. These approaches are
grounded in the concept that natural language is
inherently redundant (Shannon, 1951) and thus can
be compressed. Gilbert et al. (2023) also indicate
that LLMs can effectively reconstruct source code
from compressed text descriptions while maintaining a high level of functional accuracy. Therefore,
we follow this line of studies to compress a long
prompt into a shorter one without any gradient flow
through the LLMs to support applications based on
a larger range of LLMs.


In terms of information entropy, tokens with
lower perplexity (PPL) contribute less to the overall entropy gains of the language model. In other
words, removing tokens with lower perplexity has
a relatively minor impact on the LLM’s comprehension of the context. Motivated by this, Li
(2023) propose Selective-Context, which first employs a small language model to compute the selfinformation of each lexical unit (such as sentences,
phrases, or tokens) in original prompts, and then
drops the less informative content for prompt compression. However, this method not only ignores
the interdependence between the compressed contents but also neglects the correspondence between
the LLM being targeted and the small language
model used for prompt compression.


This paper proposes _LLMLingua_, a coarseto-fine prompt compression method, to address
the aforementioned issues. Specifically, we first
present a budget controller to dynamically allocate different compression ratios to various components in original prompts such as the instruction,
demonstrations, and the question, and meanwhile,


perform coarse-grained, demonstration-level compression to maintain semantic integrity under high
compression ratios. We further introduce a tokenlevel iterative algorithm for fine-grained prompt
compression. Compared with _Selective Context_, it
can better preserve the key information within the
prompt by taking into account the conditional dependencies between tokens. Additionally, we pose
the challenge of distribution discrepancy between
the target LLM and the small language model used
for prompt compression, and further propose an
instruction tuning based method to align the distribution of both language models.

We validate the effectiveness of our approach on
four datasets from different domains, _i.e._, GSM8K
and BBH for reasoning and ICL, ShareGPT for conversation, and Arxiv-March23 for summarization.
The results show that our method yields state-ofthe-art performance across the board. Furthermore,
we conduct extensive experiments and discussions
to analyze why our approach attains superior performance. To our best knowledge, we are the first
to evaluate reasoning and ICL capabilities in the
domain of efficient LLMs.


**2** **Related Work**


**2.1** **Efficient LLMs**


Efficient large language models have gained significant attention in recent research community,
especially with the growing prominence of ChatGPT. Most of these methods aim to reduce the
costs of inference and fine-tuning by modifying the
model parameters through quantization (Dettmers
et al., 2022; Frantar et al., 2023; Xiao et al., 2023),
compression (Frantar and Alistarh, 2023), instruct
tuning (Taori et al., 2023; Chiang et al., 2023; Xu
et al., 2023), or delta tuning (Hu et al., 2022).

A line of studies attempt to optimize inference
costs from the perspective of the input prompts.
Motivated by the observation of the abundance of
identical text spans between the input and the generated result, Yang et al. (2023) directly copy tokens
from prompts for decoding to accelerate the inference process of LLMs. Some approaches focus on
compressing prompts, specifically, learning special
tokens via prompt tuning of LLMs to reduce the
number of tokens to be processed during inference
(Mu et al., 2023; Ge et al., 2022; Wingate et al.,
2022; Chevalier et al., 2023; Ge et al., 2023). Unfortunately, these methods are usually tailored to
particular tasks and some of them (Mu et al., 2023;



Chevalier et al., 2023) even require to fine-tune the
whole language model, which severely limits their
application scenarios. Furthermore, there are some
studies (Chase, 2022; Zhang et al., 2023) that attempt to utilize LLMs to summarize dialog or data,
thereby forming memory and knowledge. However, these approaches require multiple invocations
of LLMs, which are quite costly.

Some methods reduce the prompt length by selecting a subset of demonstrations. For example,
Zhou et al. (2023) introduces a reinforcement learning based algorithm to allocate a specific number
of demonstrations for each question. Some other
methods focus on token pruning (Goyal et al., 2020;
Kim and Cho, 2021; Kim et al., 2022; Rao et al.,
2021; Modarressi et al., 2022) and token merging (Bolya et al., 2023). However, these approaches
are proposed for smaller models such as BERT, ViT.
Moreover, they depend on fine-tuning the models
or obtaining intermediate results during inference.

The most similar work to this paper is SelectiveContext (Li, 2023), which evaluates the informativeness of lexical units by computing selfinformation with a small language model, and
drops the less informative content for prompt compression. This paper is inspired by SelectiveContext and further proposes a coarse-to-fine
framework to address its limitations.


**2.2** **Out-of-Distribution (OoD) Detection**


Recently, a series of studies have been proposed
for unsupervised OoD detection. With only indistribution texts available for learning, these methods either fine-tune a pre-trained language model
(Arora et al., 2021) or train a language model from
scratch (Mai et al., 2022). Wu et al. (2023) analyze
the characteristics of these methods and leverage
multi-level knowledge distillation to integrate their
strengths while mitigating their limitations. Finally,
perplexity output by the resulting language model
is used as the indication of an example being OoD.

This paper also regards perplexity as a measurement of how well a language model predicts a sample. In contrast to out-of-distribution detection,
which identifies examples with high perplexities
as indicative of unreliable predictions, we consider
tokens with higher perplexity to be more influential
during the inference process of language models.


**2.3** **LLMs as a Compressor**


Recently, many perspectives have interpreted
large language models and unsupervised learn

Figure 1: Framework of the proposed approach _LLMLingua_ .



ing as a kind of compressor for world knowledge (Sutskever, 2023; Delétang et al., 2023), by
using arithmetic coding (Rissanen, 1976; Pasco,
1976). Our research can be viewed as an endeavor
to further compress information within prompts by
capitalizing on the compression-like characteristics
of large language models.


**3** **Problem Formulation**



A prompt compression system is designed to generate a compressed prompt _**x**_ - = {� _𝑥𝑖_ } _𝑖_ _[𝐿]_ [�] =1 [from]



erate a compressed prompt _**x**_ - = {� _𝑥𝑖_ } _𝑖_ _[𝐿]_ [�] =1 [from]

a given original prompt _**x**_ = ( _**x**_ [ins] _,_ _**x**_ [dems] _,_ _**x**_ [que] ),
where _**x**_ [ins] = { _𝑥𝑖_ [ins][}] _𝑖_ _[𝐿]_ = [ins] 1 [,] _**[ x]**_ [dems] [=] [{] _[𝑥]_ _𝑖_ [dems] } _𝑖_ _[𝐿]_ = [dems] 1 [, and]

_**x**_ [que] = { _𝑥𝑖_ [que] } _𝑖_ _[𝐿]_ = [que] 1 [denote] [the] [instruction,] [demon-]

strations, and the question in the original prompt
_**x**_ . [�] _𝐿_, _𝐿_ ins, _𝐿_ dems, and _𝐿_ que represent the numbers
of tokens in _**x**_, _**x**_ [ins], _**x**_ [dems], and _**x**_ [que], respectively.
     Let _𝐿_ = _𝐿_ ins + _𝐿_ dems + _𝐿_ que denote the total sequence length of _**x**_, the compression rate is defined
as _𝜏_ = _𝐿_ / _𝐿_, _𝜏_ ∈[0 _,_ 1], and the compression ratio

[�]
is 1/ _𝜏_ . A smaller value of _𝜏_ implies a lower inference cost, which is preferable. Let _**x**_ _𝐺_ represent

           the LLM-generated results derived by _**x**_ and _**x**_ _𝐺_

            denotes the tokens derived by _**x**_, the distribution of
_**x**_ _𝐺_ is expected to be as similar to _**x**_ _𝐺_ as possible.

This can be formulated as:




[ins]

_𝑖_ [}] _𝑖_ _[𝐿]_ [ins]



_𝑖_ [dems] } _𝑖_ _[𝐿]_ [dems]



_𝑖_ [que] } _𝑖_ _[𝐿]_ [que]



_𝑖_ _[𝐿]_ = [ins] 1 [,] _**[ x]**_ [dems] [=] [{] _[𝑥]_ _𝑖_ [dems]



min (1)

_**x**_ _,𝜏_ [KL][(] _[𝑃]_ [(] _**[x]**_ [�] _[𝐺]_ [|] _**[x]**_ [�][)] _[, 𝑃]_ [(] _**[x]**_ _[𝐺]_ [|] _**[x]**_ [))] _[,]_




**4** **Methodology**


In this section, we elaborate on the proposed coarseto-fine prompt compression approach, _LLMLingua_ .
First, we introduce a budget controller to dynamically allocate different compression ratios to various components in prompts and meanwhile, perform coarse-grained, demonstration-level compression to maintain semantic integrity under high compression ratios. Next, we describe the proposed iterative prompt algorithm designed to retain knowledge from the prompt while compressing. Finally,
we introduce alignment to address the distribution
gap between the small model and black-box large
models. Figure 1 show the framework.


**4.1** **Budget Controller**


The budget controller here is designed to allocate
different budgets, _i.e._, compression ratio, to different components in a prompt such as instructions,
demonstrations, and questions, at the sentence or
demonstration level. There are two considerations:

(i) In general, the instruction and the question in
a prompt have a direct influence on the generated
results, as they should contain all the necessary
knowledge to generate the following answer. On
the contrary, if there are multiple demonstrations
in the original prompt, the conveyed information
may be redundant. Therefore, a tailored budget
controller is required to allocate more budget ( _i.e._,


**Algorithm 1** Pseudo code of Budget Controller.

**Input** : A small language model M _𝑠_ ; the original prompt
_**x**_ = ( _**x**_ [ins] _,_ _**x**_ [dems] _,_ _**x**_ [que] ).



1: Set the selected demonstration set D = _𝜙_ .
2: Get demonstration compression rate _𝜏_ dem by Eq.(2).
3: Calculate the perplexity of each demonstration via M _𝑠_ .
4: Rank all demonstrations in descending order of their perplexity as a list ( _**x**_ [dem] _[, ...,]_ _**[ x]**_ [dem] [)][, where] _[ 𝑁]_ [is the number]




[dem] (1) _[, ...,]_ _**[ x]**_ [dem] ( _𝑁_



( _𝑁_ ) [)][, where] _[ 𝑁]_ [is the number]



**Algorithm 2** Pseudo code of Iterative Token-level
Prompt Compression (ITPC).

**Input** : A small language model M _𝑠_ ; the prompt from budget
controller _**x**_ [′] = ( _**x**_ [ins] _,_ _**x**_ [D] _,_ _**x**_ [que] ); target compression rate _𝜏_,
adjusted compression rate △ _𝜏_ ins _,_ que.

1: Set the selected token set T = _𝜙_
2: Get segment set S.
3: **for** _𝑖_ = 1 _,_ 2 _, . . ., 𝑚_ **do**
4: Get the conditional probabilities _𝑝_ ( _**s**_ _𝑖_ ) via Eq.(5)
5: Get the compression threshold _𝛾𝑖_ with Eq. (6).
6: Append the compressed token to T via Eq.(7).
7: **end for**
8: Concatenate all tokens in T as _**x**_ .
               **Output** : The compressed prompt _**x**_ .
              

demonstration to D will make the total number of
tokens in D exceed maximum tokens _𝑘_ - _𝜏_ dems _𝐿_ dems,
where _𝑘_ is the granular control coefficient.


**Adjust compression ratios for instruction and**
**question.** After obtaining the coarse-grained
compression result D = { _𝑥𝑖_ } _𝑖𝐿_ �=D1 [, we allocate the re-]

maining budget to the instruction and the question:



of demonstrations, _**x**_ [dem]



of demonstrations, _**x**_ ( _𝑖_ ) [is the] _[ 𝑖]_ [-th demonstration.]

5: **for** _𝑖_ = 1 **do**
6: **if** [�] _𝐿_ D _>_ _𝑘_ - _𝜏_ dems _𝐿_ dems **then**
7: Break.
8: **end if**
9: Append _**x**_ [dem] [to][ D][.]



9: Append _**x**_ ( _𝑖_ ) [to][ D][.]

10: _𝑖_ = _𝑖_ + 1
11: **end for**
12: Allocate remaining budget to _**x**_ [ins] and _**x**_ [que] via Eq. (3).
**Output** : The subset of demonstrations D obtained from
coarse-grained compression; Additional budget Δ _𝜏_ ins _,_ que for
the instruction and the question.



smaller compression ratios) for instructions and
questions, and less budget for demonstrations.

(ii) When a high compression ratio is required,
token-level dropout as in Li (2023) might make
the compressed prompts too trivial and thus lose
vital information from the original prompt. Consequently, sentence-level dropout should be employed instead to preserve a certain degree of linguistic integrity. Especially in the case of multiple
redundant demonstrations, we can even perform
demonstration-level control to meet the compression requirement.

Algorithm 1 illustrates the overall procedure of
the budget controller.


**Derive** **compression** **ratio** **for** **demonstrations.**
We first compute the compression rate for demon
strations _𝜏_ dems according to the target overall compression rate _𝜏_ and the pre-defined compression
rate for instructions and questions, _i.e._, _𝜏_ ins and
_𝜏_ que, respectively.




[−] [�] _[𝐿]_ [D]
Δ _𝜏_ = _[𝑘]_ [·] _[ 𝜏]_ [dems] _[𝐿]_ [dems]

_𝐿_ ins + _𝐿_ que



_,_ (3)



where [�] _𝐿_ D denote the total number of tokens in D.


**4.2** **Iterative Token-level Prompt Compression**


Utilizing perplexity for prompt compression encounters the intrinsic limitation, _i.e._, the independence assumption, similar to the shortcomings of
the Mask Language Model (Yang et al., 2019) as:



_𝑝_ ( _**x**_ ) =

 


_𝐿_ 


_𝑖_ =1



_𝑝_ (� _𝑥𝑖_ |� _𝑥<𝑖_ )



(4)



≈ _𝑝_ ( _**x**_ [′] ) =



_𝐿_ [′]



_𝑖_ =1



_𝑝_ ( _𝑥𝑖_ |� _𝑥<𝑖, 𝑥<𝑖_ ) _,_




[+] _[ 𝜏]_ [que] _[𝐿]_ [que][)]
_𝜏_ dems = _[𝜏𝐿]_ [−(] _[𝜏]_ [ins] _[𝐿]_ [ins]

_𝐿_ dems



_._ (2)



where _**x**_ [′] = ( _**x**_ [ins] _,_ _**x**_ [D] _,_ _**x**_ [que] ) is the original prompt
after demonstration-level compression; _**x**_ [D] is the
concatenation of all demonstrations in D; _𝑥_ is the
                    final compressed prompt; _𝑥<𝑖_ and _𝑥<𝑖_ denote the
           preserved and compressed tokens before the _𝑖_ -th
token _𝑥𝑖_ ; _𝐿_ [′] and _𝐿_ denote the numbers of all tokens

[�]
in _**x**_ [′] and _**x**_, respectively.
    
Here we propose an iterative token-level prompt
compression (ITPC) algorithm to mitigate the inaccuracy introduced by the conditional independence
assumption. Algorithm 2 shows the pseudo codes.

Specifically, we first divide the target prompt _**x**_ [′]

into several segments S = { _**s**_ 1 _,_ _**s**_ 2 _, ...,_ _**s**_ _𝑚_ }. And



**Demonstration-level** **prompt** **compression.**
With the derived _𝜏_ dems for demonstrations, we

then perform a coarse-grained demonstration-level
prompt compression: we construct D, a subset of
demonstrations from _**x**_ [dems] .

Specifically, we first employ a small language
model M _𝑠_, such as GPT-2 or LLaMA, to compute the perplexity of each demonstration in _**x**_ [dems] .
Then, we select demonstrations in descending order
of their perplexity values, until adding one more


then, we use the smaller model M _𝑠_ to obtain the
perplexity distribution of all segments. The compressed prompt obtained from each segment is
concatenated to the subsequent segment, enabling
more accurate estimation of the conditional probability. The corresponding probability estimation
function can be formulated as:



_𝑝_ ( _**s**_ _𝑗_ ) =

 

≈




- _𝑗_
_𝑘_ _[𝐿]_ [�] _[𝑠,𝑘]_



_𝑖_ =1



_𝑝_ ( _𝑠_ _𝑗,𝑖_ | _𝑠_ _𝑗,<𝑖,_ _**s**_ _< 𝑗_ )

 - - 


_𝐿𝑠, 𝑗_ + [�] _𝑘_ _[𝑗]_ [−][1] _𝐿_ - _𝑠,𝑘_

 


_𝑝_ ( _𝑠_ _𝑗,𝑖_ | _𝑠_ _𝑗,<𝑖,_ _**s**_ _< 𝑗_ ) _,_
      


(5)



_𝑖_ =1


where _𝑠_ _𝑗,𝑖_ denotes the _𝑖_ -th token in the _𝑗_ -th segment, _𝐿𝑠, 𝑗_ and _𝐿𝑠, 𝑗_ represent the token length of _𝑗_ 
[�]
th original and compressed segment, respectively.


When the conditional probabilities for each segment _𝑝_ ( _**s**_ _𝑗_ ) are obtained, the compression ratio
threshold _𝛾_ _𝑗_ _w.r.t._ _**s**_ _𝑗_ are dynamically calculated
based on the PPL distribution and the corresponding compression ratio _𝜏_ _**s**_ _𝑗_, where





_𝜏_ _**s**_ _𝑗_ =





_𝜏_ ins + Δ _𝜏,_ if _**s**_ _𝑗_ from _**x**_ [ins] _,_

_𝜏_ dems _,_ if _**s**_ _𝑗_ from _**x**_ **[D]** _,_

_𝜏_ que + Δ _𝜏,_ if _**s**_ _𝑗_ from _**x**_ [que] _._



(6)



**5** **Experiments**


**5.1** **Settings**


**Datasets** To comprehensively assess the effectiveness of compressed prompts in retaining LLM
abilities, we evaluated their performance across
four datasets. For reasoning and in-context learning (ICL), we use **GSM8K** (Cobbe et al., 2021)
and **BBH** (Suzgun et al., 2022). As for contextual
understanding, we use **ShareGPT** (sha, 2023) for
conversation and **Arxiv-March23** (Li, 2023) for
summarization. It’s worth noting that neither the
small LM nor the target LLMs used in this paper
have seen any of the evaluation datasets, especially
the last two which were newly collected this year.
We followed the experimental setup of previous
work (Fu et al., 2023a; Li, 2023) for the usage of
these datasets. Please refer to Appendix A.1 for
detailed information.


**Evaluation** Following Cobbe et al. (2021), Fu
et al. (2023a), and Li (2023), we utilize the Exact Match as the evaluation metric for GSM8K
and BBH. We use BLEU (Papineni et al., 2002),
ROUGE (Lin, 2004), and BERTScore (Zhang et al.,
2020) as the evaluation metrics for ShareGPT and
Arxiv-March23.


**Implementation** **Details** In this paper, we employ the GPT-3.5-Turbo-0301 and the Claude-v1.3
as the target LLMs, which can be accessed via OpenAI [2] and Claude API [3] . To improve the stability
of outputs produced by LLMs we apply greedy
decoding with a temperature of 0 across all experiments. The Alpaca dataset (Taori et al., 2023) is
exclusively employed for aligning small language
models with black-box LLMs, and is not utilized
in the evaluation process. In our experiments, we
utilize either Alpaca-7B [4] or GPT2-Alpaca as the
small pre-trained language model M _𝑠_ for compression. We implement our approach based on PyTorch 1.12.0 [5] and Huggingface’s Transformers [6] .
We set the granular control coefficient _𝑘_ to 2. We

use the pre-defined compression rates _𝜏_ ins = 0 _._ 85
and _𝜏_ que = 0 _._ 9 for instructions and questions. The
segment size used in the iterative token-level compression is set to 100.


2https://platform.openai.com/
3https://anthropic.com/
4https://github.com/tatsu-lab/stanford_alpaca
5https://pytorch.org/
6https://github.com/huggingface/transformers



Finally, tokens in each _**s**_ _𝑗_ with the PPL greater
than _𝛾_ _𝑗_ are retained in the compressed prompt.


_**s**_ _𝑗_ = { _𝑠_ _𝑗,𝑖_ | _𝑝_ ( _𝑠_ _𝑗,𝑖_ ) _>_ _𝛾_ _𝑗_ } (7)

    

**4.3** **Distribution Alignment**


To narrow the gap between the distribution of the
LLM and that of the small language model used
for prompt compression, here we align the two
distributions via instruction tuning.


Specifically, we start from a pre-trained small
language model M _𝑠_ and use the data generated by
the LLM to perform instruction tuning on M _𝑠_ . The
optimization of M _𝑠_ can be formulated as:



_,_ (8)



_𝑁_
∑︁

L **x** _𝑖,_ **y** _𝑖,_ LLM; _**θ**_ M _𝑠_

[�]

_𝑖_ =1




 



min

_**θ**_ _𝑠_ [E]




1

_𝑁_



where _𝜃_ M _𝑠_ denotes the parameters of M _𝑠_,
( _**x**_ _𝑖,_ _**y**_ _𝑖_ [LLM] ) denotes the pair of instruction _**x**_ _𝑖_ and

the LLM generated texts _**y**_ _𝑖_ [LLM], _𝑁_ is the number of

all examples used for instruction tuning.


**ShareGPT** **Arxiv-March23**
Methods
BLEU Rouge1 Rouge2 RougeL BS F1 Tokens 1/ _𝜏_ BLEU Rouge1 Rouge2 RougeL BS F1 Tokens 1/ _𝜏_


_**Constraint I**_ _2x constraint_ _350 tokens constraint_

_**Constraint II**_ _3x constraint_ _175 tokens constraint_


Table 1: Performance of different methods under different target compression ratios on the conversation (ShareGPT)
and summarization (Arxiv-March23) task.



**GSM8K** **BBH**
Methods
EM Tokens 1/ _𝜏_ EM Tokens 1/ _𝜏_


Full-shot 78.85 2,366 - 70.07 774 
_**1-shot constraint**_

_**half-shot constraint**_


_**quarter-shot constraint**_

|Sentence Selection<br>Selective-Context<br>GPT4 Generation<br>Ours|66.67 195 12x<br>44.20 157 15x<br>56.33 188 20x<br>77.33 117 20x|46.00 109 7x<br>47.37 108 7x<br>26.81 101 8x<br>56.85 110 7x|
|---|---|---|
|zero-shot<br>Simple Prompt|48.75†<br>11<br>215x <br>74.9<br>691<br>3x|32.32<br>16<br>48x<br>-<br>-<br>-|



Table 2: Performance of different methods under different target compression ratios on the GSM8K mathematical reasoning and Big-bench Hard (BBH) datasets. [†] We
also include the instruction of the prompt in zero-shot
experiments for a vertical comparison.


**Baselines** We consider the following baselines:


  - _GPT4-Generation_ : Instruct GPT-4 to compress the original prompt. We used ten sets
of instructions here and reported the best results. Appendix C displays the instructions
we employed.


  - _Random Selection_ : Random select the demonstrations or sentences of the original prompt.


  - _Selective-Context_ (Li, 2023): Use the phraselevel self-information from a small language
model to filter out less informative content.
We use the same small LM, _i.e._, Alpaca-7B

for a fair comparison.


**5.2** **Main Results**


Table 1 and 2 report the results of our approach
alongside those baseline methods on GSM8K,



BBH, ShareGPT, and Arxiv-March23. It can be
seen that our proposed method consistently outperforms the prior methods by a large margin in
almost all experiments.

Specifically, on GSM8K and BBH, the reasoning and in-context learning-related benchmark, our
method even achieves slightly higher results than
the full-shot approach, while also delivering impressive compression ratios (1/ _𝜏_ ) of 5x and 3x
respectively, with the 1-shot constraint. This well
demonstrates that our compressed prompts effectively retain the reasoning information contained
in the original prompt. As the compression ratio
increases, _i.e._, under the half-shot and quarter-shot
constraints, the performance experiences a slight
decline. For instance, on GSM8K, the EM scores
will decrease by 1.44 and 1.52, respectively, despite compression ratios as high as 14x and 20x.
On BBH, our approach achieves compression ratios of 5x and 7x with the EM score decreasing
by 8.5 and 13.2 points, respectively. In fact, this
performance is already quite satisfactory, as it approaches the score of 62.0 achieved by PaLM-540B
in half-shot constraint. Our case study reveals
that this declined performance on BBH is mainly
due to challenging reasoning tasks, such as tracking_shuffled_objects_seven_objects.

Moreover, on ShareGPT and Arxiv-March23,
two contextual understanding benchmarks, we can
see that our approach achieves acceleration ratios
of 9x and 3.3x with a high BERTScore F1, indicating that our approach successfully retains the
semantic information of the initial prompts.


**5.3** **Analysis on Reasoning & ICL Tasks.**


Here we analyze the performance of our approach
and baseline methods on the difficult reasoning and
in-context learning (ICL) benchmarks GSM8K and
BBH.

We notice that our approach shows significant


performance improvements over the strong baseline Selective-Context under all settings. We
conjecture that, as relying on phrase-level selfinformation, Selective-Context is prone to lose
critical reasoning information during the chain-ofthought process. Especially on GSM8K, its performance is lower than ours by 33.10 points at a compression ratio of 20x. The inferior performance of
Sentence Selection suggests that it may face similar
issues of fragmentary reasoning logic. Surprisingly,
though GPT-4 has demonstrated its strong text generation capability, the suboptimal performance on
prompt compression indicates that the generated
prompts may omit crucial details from the original
prompt, particularly reasoning steps.

In addition to the findings mentioned above, the
experiments also demonstrate that our method can
preserve the ICL capacity of prompts for LLMs.
Compared to the zero-shot results, our approach
exhibits significant performance improvements of
51.55 and 24.53 even with the largest compression
ratios. Notably, on GSM8K, our 20x compressed
prompt outperforms the 8-shot 3-step CoT by 2.43,
further suggesting that our method can effectively
retain the reasoning information.


**5.4** **Ablation**


To validate the contributions of different components in our approach, we introduce five variants
of our model for ablation study: i) _Ours_ _w/o_ _It-_
_erative Token-level Compression_, which performs
token-level compression in a single inference rather
than iteratively. ii) _Ours_ _w/o_ _Budget_ _Controller_,
which directly employs ITPC with the same compression ratio for all components. iii) _Ours_ _w/o_
_Dynamic Compression Ratio_, which uses the same
compression ratio for all components. iv) _Ours_
_w/ Random Selection in Budget Controller_, which
randomly selects demonstrations or sentences for
demonstration-level prompt compression. v) _Ours_
_w/o_ _Distribution_ _Alignment_, which removes the
distribution alignment module of our approach and
directly use the pre-trained LLaMA-7B as the small
language model. vi) _Ours w/ Remove Stop Words_,
which removes the stop words in original prompts
using NLTK [7] . Table 3 shows the results.

Comparing Ours with w/o Iterative Token-level
Prompt Compression, we observe a significant decline in Exact Match when the conditional dependence between compressed tokens is not consid

7https://www.nltk.org/



EM Tokens 1/ _𝜏_


Ours **79.08** 439 5x

 - w/o Iterative Token-level Prompt Compression 72.93 453 5x

 - w/o Budget Controller 73.62 486 5x

 - w/o Dynamic Compression Ratio 77.26 457 5x

 - w/ Random Selection in Budget Controller 72.78 477 5x

 - w/o Distribution Alignment 78.62 452 5x

 - w/ Remove Stop Words 76.27 1,882 1.3x


Table 3: Ablation study on GSM8K in 1-shot constraint.


ered. We conjecture this variant may lose essential information in the prompt, especially for lowfrequency keywords that frequently appear in the
given prompt. When comparing Ours with w/o
Dynamic Compression Ratio and with w/o Budget Controller, it reveals that different components
of the prompt exhibit varying sensitivity. Instructions and questions necessitate a lower compression ratio. To balance the relationship between
compression ratio and language integrity, introducing a demonstration or sentence-level filter better
preserves sufficient linguistic information, even at
higher compression ratios. Ours w/ Random Selection in Budget Controller indicates that selecting
sentences or demonstrations based on perplexity
can better identify information-rich sentences for
target LLMs. Distribution Alignment allows small
LMs to generate distributions that more closely resemble those of target LLMs, resulting in a further
improvement of 0.56 on GSM8K.


**5.5** **Discussion**


**Different Target LLMs** Here we test our method
with Claude-v1.3 as the target LLM to demonstrate its generalizability across different black-box
LLMs in addition to the GPT series models. Due
to the limitation of API cost, we only consider the
scenarios with one-shot constraint and half-shot
constraint. Similarly, we employe Alpaca-7B as
the small language model for the challenges in collecting alignment data. As shown in Table 4, our
method can achieve improvements over the simple
prompt by 0.8 and 1.7 EM points with compression
ratios of 5x and 14x, respectively.


EM Tokens 1/ _𝜏_


**Ours** in 1-shot constraint 83.51 439 5x
**Ours** in half-shot constraint 82.61 171 14x
Simple Prompt 81.8 691 3x


Table 4: Ours method on GSM8K using Claude-v1.3.


**Different** **Small** **LMs** We further test our approach with different small language models: we
fine-tune the GPT2-small on the Alpaca dataset and
use it as the small LM for our system. As shown in
Table 5, the results obtained by Alpaca finetuned
GPT2-small are weaker than those obtained by
Alpaca-7B with a performance drop of 2.06, 0.99,
and 1.06 EM points at different compression ratios.
This is due to the significant distribution discrepancy between the small LM and the target LLM.
Even with distribution alignment, it is still difficult to directly estimate the target LLM using the
distribution from the small language model. Similar observations have been reported in Li (2023).
However, benefiting from the proposed budget controller and the iterative token-level prompt compression algorithm, our approach achieves satisfactory results in difficult tasks such as reasoning even
with the less powerful GPT2-Small as the small
language model.


EM Tokens 1/ _𝜏_


**Ours** with GPT2 in 1-shot constraint 77.02 447 5x
**Ours** with GPT2 in half-shot constraint 76.42 173 14x
**Ours** with GPT2 in quarter-shot constraint 76.27 128 18x


Table 5: Our method on GSM8K with GPT2-Alpaca as
the small language model.


**The Generation Results of Compressed Prompt**
Appendix E displays several compressed prompts
along with following generation texts. It is evident
that the compressed prompts can still guide the generation of multi-step reasoning outcomes similar to
the original ones. In contrast, prompts compressed
using Selective-Context exhibit errors in reasoning logic. This highlights the effectiveness of our
method in preserving crucial semantic information
while retaining reasoning capabilities.

As depicted in Figure 2, we also analyze the relationship between the compression ratio and the
length of the corresponding generated texts. It can
be observed that as the compression ratio increases,
the text length produced by target LLMs tends to
decrease, albeit with varying degrees across different datasets. This indicates that prompt compression not only saves computational resources in the
input but also contributes to computational savings
in the generation stage.


**Overhead of LLMLingua** We explore two key
factors to study the computation overhead of LLM


400


300


200


100



|Col1|GSM8K<br>BBH<br>ShareGPT<br>Arxiv|Col3|Col4|Col5|Col6|
|---|---|---|---|---|---|
|||||||
|||||||
|||||||
|||||||


Compression Ratio



Figure 2: The distribution of generated token lengths at
varying compression ratios (1/ _𝜏_ ).


Lingua: the number of tokens involved in computation and the end-to-end latency.

The overall computation of our system is the
sum of the prompt compression and the following
inference. This can be formulated as:


_𝑐_ = ( _𝐿_ + _𝑘𝐿_ / _𝜏_ + _𝐿_ / _𝜏_ ) · _𝑐_ small + _𝐿_ / _𝜏_ - _𝑐_ LLMs _,_ (9)


where _𝑐_ small and _𝑐_ LLMs represent the per token computation load of the small LM and LLM, respectively. _𝐿_, _𝑘𝐿_ / _𝜏_, and _𝐿_ / _𝜏_ are the numbers of token inferences for the budget controller, the perplexity calculation of tokens to compress in ITPC,
and the conditioned perplexity calculation of compressed results in ITPC (using KV cache), respectively. Assuming that the small LM has the same
system optimizations as the LLMs, such as the
use of FasterTransformer [8] and quantization techniques, we can estimate the ratio between _𝑐_ small
and _𝑐_ LLMs based on model parameters: _𝑐_ small ≈
7/175 _𝑐_ LLMs = 1/25 _𝑐_ LLMs. When _𝜏_ = 5, we have
_𝑐_ ≈ 0 _._ 264 · _𝐿𝑐_ LLMs ≈ 1/4 · _𝐿𝑐_ LLMs. That is, we
can achieve nearly 4x savings in computational resources when using the smaller LM with a prompt
compression rate of 5x.


1/ _𝜏_ 1x 2x 5x 10x


End-to-End w/o LLMLingua 8.6 - - End-to-End w/ LLMLingua - 4.9(1.7x) 2.3(3.3x) 1.3(5.7x)
LLMLingua - 0.8 0.3 0.2


Table 6: Latency (s) comparison on GSM8K.


Table 6 shows the end-to-end latency of different
systems on a V100-32G GPU with a compression
rate from 1x to 10x. We can see that LLMLingua
has a relatively small computation overhead and
can achieve a speedup ranging from 1.7x to 5.7x.


8https://github.com/NVIDIA/FasterTransformer


**Recovering** **the** **Compressed** **Prompt** **using**
**LLMs** Appendix D shows some examples restored from the compressed prompts by using GPT4 [9] . It is evident that LLMs can effectively comprehend the semantic information in the compressed
prompts, even if it might be challenging for humans.
Additionally, we notice that how much information
GPT-4 can recover depends on the compression
ratio and the small language model we use. For
instance, in Figure 4, the prompt compressed using
Alpaca-7B is restored to its complete 9-step reasoning process, while in Figure 5, the prompt compressed with GPT2-Alpaca can only be restored to
a 7-step reasoning process, with some calculation
errors.


**Compare with Generation-based Methods** We
do not develop our approach based on LLM generation primarily for three reasons: i) The content
and length of the generated text are uncontrollable.
Uncontrollable length requires more iterations to
satisfy the constraint of the compression ratio. Uncontrollable content leads to low overlap between
the generated text and the original prompt, particularly for complex prompts with multi-step inference, which may lose significant amounts of
reasoning paths or even generate completely unrelated demonstrations. ii) The computational cost
is high. Small language models struggle to handle
such complex tasks, and using models like GPT-4
for compression would further increase computational overhead. Moreover, even powerful generation models like GPT-4 struggle to retain effective
information from prompts as shown in Table 2.
iii) The compressed prompts obtained from generation models are complete and continuous sentences,
usually resulting in a lower compression ratio compared to our coarse-to-fine method.


**Compare** **with** **Prompt** **Engineering** **methods**
Our method is orthogonal to Prompt Engineering
methods, such as prompt retrieval and prompt ordering. Our work focuses on compressing welldesigned prompts, and it performs well on complex and fine-tuned prompts like GSM8K. Moreover, the perplexity-based demonstration filtering
method used in our budget controller can also be
applied to scenarios such as prompt retrieval. This


9An intriguing observation is that GPT-3.5-Turbo struggles
to reconstruct compressed prompts, while GPT-4 has demonstrated an ability to do so. This contrast in performance could
suggest that recovering compressed prompts is an emergent
ability that arises in more advanced language models.



demonstrates the compatibility and adaptability of
our approach in various LLMs settings.


**6** **Conclusion**


We introduce a coarse-to-fine algorithm for prompt

compression, named _LLMLingua_, which is based
on the small LM’s PPL for black-box LLMs. Our
approach consists of three modules: Budget Controller, Iterative Token-level Compression, and
Alignment. We validate the effectiveness of our
approach on 4 datasets from different domains, i.e.,
GSM8K, BBH, ShareGPT, and Arxiv-March23,
demonstrating that our method achieves state-ofthe-art performance across all datasets, with up
to 20x compression with only a 1.5 point performance drop. Moreover, we observe that LLMs
can effectively restore compressed prompts, and
prompt compression contributes to a reduction in
generated text length. Our approach holds substantial practical implications, as it not only reduces
computational costs but also offers a potential solution for accommodating longer contexts in LLMs.
The method of compressing prompts has the potential to enhance downstream task performance
by compressing longer prompts and to improve the
LLMs’s inference efficiency by compressing the
KV cache.


**Limitations**


There are also some limitations in our approach.
For instance, we might observe a notable performance drop when trying to achieve excessively high compression ratios such as 25x-30x
on GSM8K, as shown in Figure 3.


78.85



70


60


50





Compression Ratio


Figure 3: The performance of various prompt compression methods at different compression ratios (1/ _𝜏_ )
on GSM8K. The dashed line corresponds to the Exact
Match score obtained from the full-shot prompt.


It is shown that as the compression ratio increases especially around 25x-30x, all methods as
well as ours will experience a substantial performance drop. In comparison with other methods,
this performance drop derived from our approach
is significantly shifted to much higher compression
ratios. We owe this to the Budget Controller and
the Iterative Token-level Prompt Compression algorithm, which enable our method to maintain the
original prompt information even at some extreme
compression ratios. The upper limit of the compression ratio for different prompts varies, depending
on factors such as prompt length, task type, and the
number of sentences involved.

Additionally, there may be subtle differences
between the tokenizers used by the small language
model and the black-box LLM, which may result
in an underestimation of the prompt’s token length.


**References**


2023. Sharegpt. [https://sharegpt.com/.](https://sharegpt.com/)


Udit Arora, William Huang, and He He. 2021. [Types](https://doi.org/10.18653/v1/2021.emnlp-main.835)

[of out-of-distribution texts and how to detect them.](https://doi.org/10.18653/v1/2021.emnlp-main.835)
In _Proceedings_ _of_ _the_ _2021_ _Conference_ _on_ _Empiri-_
_cal Methods in Natural Language Processing_, pages
10687–10701, Online and Punta Cana, Dominican
Republic. Association for Computational Linguistics.


Daniel Bolya, Cheng-Yang Fu, Xiaoliang Dai, Peizhao

Zhang, Christoph Feichtenhofer, and Judy Hoffman.
2023. Token merging: [Your](https://openreview.net/forum?id=JroZRaRw7Eu) vit but faster. In _The_
_Eleventh International Conference on Learning Rep-_
_resentations_ .


Harrison Chase. 2022. [LangChain.](https://github.com/hwchase17/langchain)


Alexis Chevalier, Alexander Wettig, Anirudh Ajith, and

Danqi Chen. 2023. Adapting [language](https://arxiv.org/abs/2305.14788) models to
[compress contexts.](https://arxiv.org/abs/2305.14788) _ArXiv preprint_, abs/2305.14788.


Wei-Lin Chiang, Zhuohan Li, Zi Lin, Ying Sheng,

Zhanghao Wu, Hao Zhang, Lianmin Zheng, Siyuan
Zhuang, Yonghao Zhuang, Joseph E. Gonzalez, Ion
Stoica, and Eric P. Xing. 2023. Vicuna: [An](https://lmsys.org/blog/2023-03-30-vicuna/) open[source chatbot impressing gpt-4 with 90%* chatgpt](https://lmsys.org/blog/2023-03-30-vicuna/)
[quality.](https://lmsys.org/blog/2023-03-30-vicuna/)


Karl Cobbe, Vineet Kosaraju, Mohammad Bavarian,

Mark Chen, Heewoo Jun, Lukasz Kaiser, Matthias
Plappert, Jerry Tworek, Jacob Hilton, Reiichiro
Nakano, et al. 2021. [Training verifiers to solve math](https://arxiv.org/abs/2110.14168)
[word problems.](https://arxiv.org/abs/2110.14168) _ArXiv preprint_, abs/2110.14168.


Grégoire Delétang, Anian Ruoss, Paul-Ambroise

Duquenne, Elliot Catt, Tim Genewein, Christopher Mattern, Jordi Grau-Moya, Li Kevin Wenliang,
Matthew Aitchison, Laurent Orseau, et al. 2023. [Lan-](https://arxiv.org/abs/2309.10668)
guage [modeling](https://arxiv.org/abs/2309.10668) is compression. _ArXiv_ _preprint_,
abs/2309.10668.



Tim Dettmers, Mike Lewis, Younes Belkada, and Luke

Zettlemoyer. 2022. GPT3.int8(): [8-bit matrix mul-](https://openreview.net/forum?id=dXiGWqBoxaD)
[tiplication for transformers at scale.](https://openreview.net/forum?id=dXiGWqBoxaD) In _Advances in_
_Neural Information Processing Systems_ .


Elias Frantar and Dan Alistarh. 2023. SparseGPT: Mas
sive language models can be accurately pruned in
one-shot. In _International Conference on Machine_
_Learning_ .


Elias Frantar, Saleh Ashkboos, Torsten Hoefler, and Dan

Alistarh. 2023. OPTQ: [Accurate](https://openreview.net/forum?id=tcbBPnfwxS) quantization for
[generative pre-trained transformers.](https://openreview.net/forum?id=tcbBPnfwxS) In _The Eleventh_
_International_ _Conference_ _on_ _Learning_ _Representa-_
_tions_ .


Yao Fu, Litu Ou, Mingyu Chen, Yuhao Wan, Hao

Peng, and Tushar Khot. 2023a. [Chain-of-thought](https://arxiv.org/abs/2305.17306)
hub: [A continuous effort to measure large language](https://arxiv.org/abs/2305.17306)
models’ [reasoning](https://arxiv.org/abs/2305.17306) performance. _ArXiv_ _preprint_,
abs/2305.17306.


Yao Fu, Hao Peng, Ashish Sabharwal, Peter Clark, and

Tushar Khot. 2023b. [Complexity-based prompting](https://openreview.net/forum?id=yf1icZHC-l9)
for [multi-step](https://openreview.net/forum?id=yf1icZHC-l9) reasoning. In _The_ _Eleventh_ _Interna-_
_tional Conference on Learning Representations_ .


Tao Ge, Jing Hu, Li Dong, Shaoguang Mao, Yan Xia,

Xun Wang, Si-Qing Chen, and Furu Wei. 2022.
Extensible prompts [for](https://arxiv.org/abs/2212.00616) language models. _ArXiv_
_preprint_, abs/2212.00616.


Tao Ge, Jing Hu, Xun Wang, Si-Qing Chen, and Furu

Wei. 2023. [In-context autoencoder for context com-](https://arxiv.org/abs/2307.06945)
[pression in a large language model.](https://arxiv.org/abs/2307.06945) _ArXiv preprint_,
abs/2307.06945.


Henry Gilbert, Michael Sandborn, Douglas C Schmidt,

Jesse Spencer-Smith, and Jules White. 2023. [Seman-](https://arxiv.org/abs/2304.12512)
[tic compression with large language models.](https://arxiv.org/abs/2304.12512) _ArXiv_
_preprint_, abs/2304.12512.


Saurabh Goyal, Anamitra Roy Choudhury, Saurabh

Raje, Venkatesan T. Chakaravarthy, Yogish Sabharwal, and Ashish Verma. 2020. [Power-bert:](http://proceedings.mlr.press/v119/goyal20a.html) Accel[erating BERT inference via progressive word-vector](http://proceedings.mlr.press/v119/goyal20a.html)
[elimination.](http://proceedings.mlr.press/v119/goyal20a.html) In _Proceedings of the 37th International_
_Conference on Machine Learning, ICML 2020, 13-18_
_July 2020, Virtual Event_, volume 119 of _Proceedings_
_of_ _Machine_ _Learning_ _Research_, pages 3690–3699.
PMLR.


Edward J Hu, yelong shen, Phillip Wallis, Zeyuan Allen
Zhu, Yuanzhi Li, Shean Wang, Lu Wang, and Weizhu
Chen. 2022. LoRA: Low-rank [adaptation](https://openreview.net/forum?id=nZeVKeeFYf9) of large
[language](https://openreview.net/forum?id=nZeVKeeFYf9) models. In _International_ _Conference_ _on_
_Learning Representations_ .


Gyuwan Kim and Kyunghyun Cho. 2021. [Length-](https://doi.org/10.18653/v1/2021.acl-long.508)
adaptive transformer: [Train once with length drop,](https://doi.org/10.18653/v1/2021.acl-long.508)
[use anytime with search.](https://doi.org/10.18653/v1/2021.acl-long.508) In _Proceedings of the 59th_
_Annual Meeting of the Association for Computational_
_Linguistics and the 11th International Joint Confer-_
_ence_ _on_ _Natural_ _Language_ _Processing_ _(Volume_ _1:_
_Long Papers)_, pages 6501–6511, Online. Association
for Computational Linguistics.


Sehoon Kim, Sheng Shen, David Thorsley, Amir Gho
lami, Woosuk Kwon, Joseph Hassoun, and Kurt
Keutzer. 2022. Learned token pruning for transformers. In _Proceedings of the 28th ACM SIGKDD Con-_
_ference on Knowledge Discovery and Data Mining_,
pages 784–794.


Yucheng Li. 2023. Unlocking [context](https://arxiv.org/abs/2304.12102) constraints of

llms: [Enhancing context efficiency of llms with self-](https://arxiv.org/abs/2304.12102)
[information-based content filtering.](https://arxiv.org/abs/2304.12102) _ArXiv preprint_,
abs/2304.12102.


Chin-Yew Lin. 2004. ROUGE: A [package](https://aclanthology.org/W04-1013) for auto
[matic evaluation of summaries.](https://aclanthology.org/W04-1013) In _Text Summariza-_
_tion Branches Out_, pages 74–81, Barcelona, Spain.
Association for Computational Linguistics.


Ilya Loshchilov and Frank Hutter. 2019. [Decoupled](https://openreview.net/forum?id=Bkg6RiCqY7)

weight decay regularization. In _7th_ _International_
_Conference on Learning Representations, ICLR 2019,_
_New_ _Orleans,_ _LA,_ _USA,_ _May_ _6-9,_ _2019_ . OpenReview.net.


Kimberly T Mai, Toby Davies, and Lewis D Griffin.

2022. Self-supervised [losses](https://arxiv.org/abs/2204.05695) for one-class textual
[anomaly detection.](https://arxiv.org/abs/2204.05695) _ArXiv preprint_, abs/2204.05695.


Ali Modarressi, Hosein Mohebbi, and Mohammad Taher Pilehvar. 2022. [AdapLeR: Speeding up](https://doi.org/10.18653/v1/2022.acl-long.1)
[inference by adaptive length reduction.](https://doi.org/10.18653/v1/2022.acl-long.1) In _Proceed-_
_ings of the 60th Annual Meeting of the Association_
_for Computational Linguistics (Volume 1:_ _Long Pa-_
_pers)_, pages 1–15, Dublin, Ireland. Association for
Computational Linguistics.


Jesse Mu, Xiang Lisa Li, and Noah Goodman. 2023.

Learning to compress [prompts](https://arxiv.org/abs/2304.08467) with gist tokens.
_ArXiv preprint_, abs/2304.08467.


Kishore Papineni, Salim Roukos, Todd Ward, and Wei
Jing Zhu. 2002. Bleu: [a method for automatic evalu-](https://doi.org/10.3115/1073083.1073135)
[ation of machine translation.](https://doi.org/10.3115/1073083.1073135) In _Proceedings of the_
_40th Annual Meeting of the Association for Compu-_
_tational_ _Linguistics_, pages 311–318, Philadelphia,
Pennsylvania, USA. Association for Computational
Linguistics.


Richard Clark Pasco. 1976. _Source coding algorithms_

_for fast data compression_ . Ph.D. thesis, Citeseer.


Yongming Rao, Wenliang Zhao, Benlin Liu, Jiwen Lu,

Jie Zhou, and Cho-Jui Hsieh. 2021. [Dynamicvit:](https://openreview.net/forum?id=jB0Nlbwlybm) Ef[ficient vision transformers with dynamic token spar-](https://openreview.net/forum?id=jB0Nlbwlybm)
[sification.](https://openreview.net/forum?id=jB0Nlbwlybm) In _Advances in Neural Information Pro-_
_cessing Systems_ .


Jorma J Rissanen. 1976. Generalized kraft inequality

and arithmetic coding. _IBM Journal of research and_
_development_, 20(3):198–203.


Claude E Shannon. 1951. Prediction and entropy
of printed english. _Bell_ _system_ _technical_ _journal_,
30(1):50–64.


Ilya Sutskever. 2023. A theory of unsupervised
learning. [https://simons.berkeley.edu/talks/](https://simons.berkeley.edu/talks/ilya-sutskever-openai-2023-08-14)
[ilya-sutskever-openai-2023-08-14.](https://simons.berkeley.edu/talks/ilya-sutskever-openai-2023-08-14)



Mirac Suzgun, Nathan Scales, Nathanael Schärli, Se
bastian Gehrmann, Yi Tay, Hyung Won Chung,
Aakanksha Chowdhery, Quoc V Le, Ed H Chi, Denny
Zhou,, and Jason Wei. 2022. [Challenging big-bench](https://arxiv.org/abs/2210.09261)
[tasks and whether chain-of-thought can solve them.](https://arxiv.org/abs/2210.09261)
_ArXiv preprint_, abs/2210.09261.


Rohan Taori, Ishaan Gulrajani, Tianyi Zhang, Yann

Dubois, Xuechen Li, Carlos Guestrin, Percy Liang,
and Tatsunori B. Hashimoto. 2023. Stanford alpaca:
An instruction-following llama model. [https://](https://github.com/tatsu-lab/stanford_alpaca)
[github.com/tatsu-lab/stanford_alpaca.](https://github.com/tatsu-lab/stanford_alpaca)


Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten

Bosma, brian ichter, Fei Xia, Ed H. Chi, Quoc V Le,
and Denny Zhou. 2022. Chain of [thought](https://openreview.net/forum?id=_VjQlMeSB_J) prompting elicits reasoning in large language models. In
_Advances in Neural Information Processing Systems_ .


David Wingate, Mohammad Shoeybi, and Taylor

Sorensen. 2022. [Prompt compression and contrastive](https://aclanthology.org/2022.findings-emnlp.412)
[conditioning for controllability and toxicity reduction](https://aclanthology.org/2022.findings-emnlp.412)
[in language models.](https://aclanthology.org/2022.findings-emnlp.412) In _Findings of the Association_
_for Computational Linguistics:_ _EMNLP 2022_, pages
5621–5634, Abu Dhabi, United Arab Emirates. Association for Computational Linguistics.


Qianhui Wu, Huqiang Jiang, Haonan Yin, Börje F. Karls
son, and Chin-Yew Lin. 2023. Multi-level knowledge
distillation for out-of-distribution detection in text.
In _Proceedings_ _of_ _the_ _61th_ _Annual_ _Meeting_ _of_ _the_
_Association for Computational Linguistics (Long Pa-_

_pers)_ .


Guangxuan Xiao, Ji Lin, Mickael Seznec, Julien De
mouth, and Song Han. 2023. Smoothquant: Accurate and efficient post-training quantization for large
language models. In _International_ _Conference_ _on_
_Machine Learning_ .


Can Xu, Qingfeng Sun, Kai Zheng, Xiubo Geng,

Pu Zhao, Jiazhan Feng, Chongyang Tao, and Daxin
Jiang. 2023. Wizardlm: [Empowering](https://arxiv.org/abs/2304.12244) large lan[guage models to follow complex instructions.](https://arxiv.org/abs/2304.12244) _ArXiv_
_preprint_, abs/2304.12244.


Nan Yang, Tao Ge, Liang Wang, Binxing Jiao, Daxin

Jiang, Linjun Yang, Rangan Majumder, and Furu
Wei. 2023. Inference with [reference:](https://arxiv.org/abs/2304.04487) Lossless ac[celeration of large language models.](https://arxiv.org/abs/2304.04487) _ArXiv preprint_,
abs/2304.04487.


Zhilin Yang, Zihang Dai, Yiming Yang, Jaime G. Car
bonell, Ruslan Salakhutdinov, and Quoc V. Le. 2019.
Xlnet: Generalized [autoregressive](https://proceedings.neurips.cc/paper/2019/hash/dc6a7e655d7e5840e66733e9ee67cc69-Abstract.html) pretraining for
[language understanding.](https://proceedings.neurips.cc/paper/2019/hash/dc6a7e655d7e5840e66733e9ee67cc69-Abstract.html) In _Advances in Neural In-_
_formation_ _Processing_ _Systems_ _32:_ _Annual_ _Confer-_
_ence on Neural Information Processing Systems 2019,_
_NeurIPS 2019, December 8-14, 2019, Vancouver, BC,_
_Canada_, pages 5754–5764.


Lei Zhang, Yuge Zhang, Kan Ren, Dongsheng Li, and

Yuqing Yang. 2023. Mlcopilot: [Unleashing](https://arxiv.org/abs/2304.14979) the
[power of large language models in solving machine](https://arxiv.org/abs/2304.14979)
[learning tasks.](https://arxiv.org/abs/2304.14979) _ArXiv preprint_, abs/2304.14979.


Tianyi Zhang, Varsha Kishore, Felix Wu, Kilian Q.

Weinberger, and Yoav Artzi. 2020. [Bertscore:](https://openreview.net/forum?id=SkeHuCVFDr) Evalu[ating text generation with BERT.](https://openreview.net/forum?id=SkeHuCVFDr) In _8th International_
_Conference on Learning Representations, ICLR 2020,_
_Addis Ababa, Ethiopia, April 26-30, 2020_ . OpenReview.net.


Wangchunshu Zhou, Yuchen Eleanor Jiang, Ryan Cot
terell, and Mrinmaya Sachan. 2023. [Efficient prompt-](https://arxiv.org/abs/2305.11170)
[ing via dynamic in-context learning.](https://arxiv.org/abs/2305.11170) _ArXiv preprint_,
abs/2305.11170.


**A** **Experiment Details**


**A.1** **Dataset Details**


**GSM8K** A widely used math reasoning dataset
comprising 8,000 problems, including a 1,300 problems test set that assesses models’ capabilities in
arithmetic reasoning and formulating mathematical
steps using language (Cobbe et al., 2021). For this
dataset, we employ the complex multi-step CoT
prompt (Fu et al., 2023b) [10] as the original prompt.


**BBH** A suite of language and symbolic reasoning tasks, consisting of 6,500 problems across 23
subsets, specifically designed to evaluate chain-ofthought prompting. In our experiment, we adopt
the 3-shot CoT prompt [11] as the original prompts,
following the approach described by Suzgun et al.
(2022).


**ShareGPT** A conversation dataset from
ShareGPT.com platform (sha, 2023) which includes users sharing conversations with ChatGPT
in different languages and in various scenarios
(e.g., coding, chitchat, writing assistant, etc.). We
use a dataset of 575 samples provided by Li (2023)
as our test set. We use all dialogues except the
final round as the prompt and generate results with
GPT-3.5-Turbo as the reference.


**Arxiv-March23** A dataset consisting of latest
academic papers created in March 2023 from the
arXiv preprint repository. We use 500 data items
collected by Li (2023) as the test set. Due to the
excessive length of some articles, we take the first
five sections of each article and truncate each section to 10,000 characters. Then, we concatenate
these sections to form the original prompt and use
GPT-3.5-Turbo to generate the summary as the reference.


10https://github.com/FranxYao/chain-of-thought-hub
11https://github.com/suzgunmirac/BIG-Bench-Hard



**A.2** **Other Implementation Details**


All experiments were conducted using a Tesla
V100 (32GB). We trained the GPT2-Alpaca model
on the Alpaca dataset [12] for eight epochs using
a learning rate of 1e-4 and the AdamW optimizer (Loshchilov and Hutter, 2019). The training
process took approximately 150 minutes to complete. We use tiktoken [13] and GPT-3.5-Turbo model
to count all the tokens.


**B** **Economic Cost**


GSM8K BBH ShareGPT Arxiv


Original 5.2 12.8 0.7 1.3
Ours 0.5 4.8 0.3 0.2


Table 7: The inference costs($) for various datasets
using GPT-3.5-Turbo.


Table 7 displays the estimated inference costs
for various datasets, according to the pricing of
GPT-3.5-Turbo. Our approach showcases significant savings in computational resources and monetary expenditures, with cost reductions of $4.7,
$8.0, $0.4, and $0.8 observed in the GSM8K, BBH,
ShareGPT, and Arxiv datasets, respectively.


**C** **Instructions used in GPT-4 Generation**


The instructions we used in the GPT-4 Generation
are shown below:


1. _Could you please rephrase the paragraph to_
_make it short, and keep 5% tokens?_


2. _Condense the passage to retain only 5% of its_
_original tokens, while preserving its meaning._


3. _Short the sentences to 200 tokens._


4. _Trim the text down to 200 tokens in total._


5. _Please provide a concise summary of the given_
_examples in several sentences, ensuring that_
_all reasoning information is included._


6. _Summarize_ _the_ _provided_ _examples_ _in_ _a_ _few_
_sentences, maintaining all essential reasoning_
_aspects._


7. _Remove redundancy and express the text con-_
_cisely_ _in_ _English,_ _ensuring_ _that_ _all_ _key_ _in-_
_formation_ _and_ _reasoning_ _processes_ _are_ _pre-_
_served._


12https://github.com/tatsu-lab/stanford_alpaca
13https://github.com/openai/tiktoken


8. _Eliminate repetitive elements and present the_
_text_ _concisely,_ _ensuring_ _that key details_ _and_
_logical processes are retained._

9. _Follow_ _these_ _steps_ _to_ _shorten_ _the_ _given_ _text_
_content:_ _1._ _First,_ _calculate_ _the_ _amount_ _of_
_information contained in each sentence, and_
_remove_ _sentences_ _with_ _less_ _information._ _2._
_Next,_ _further_ _condense_ _the_ _text_ _by_ _removing_
_stop words, unnecessary punctuation, and re-_
_dundant expressions._ _Refine the content while_
_ensuring that all key information is retained._
_Let’s do it step by step._

10. _To shorten the given text, follow these steps:_
_a)_ _Determine_ _the_ _information_ _value_ _of_ _each_
_sentence and remove those with lower value._
_b) Further reduce the text by removing stop_
_words,_ _unneeded_ _punctuation,_ _and_ _superflu-_
_ous_ _expressions,_ _while_ _making_ _sure_ _to_ _keep_
_all vital information intact._ _Let’s do it step by_
_step._


**D** **Recovering Compressed Prompts with**
**Large Language Model**


In this section, we showcase several examples of
employing black-box LLMs to reconstruct compressed prompts. Specifically, we have selected
three compressed prompts with varying compression ratios, produced by distinct small language
models, on different datasets. These prompts, accompanied by guiding instructions, will serve as
input for the GPT-4 model.


**E** **Cases Study**


We present various cases from multiple datasets,

encompassing compressed prompts, outcomes derived from original prompts, outcomes derived
from compressed prompts, and results achieved
utilizing the selective-context approach.


Figure 4: Recovering the compressed prompt(1/ _𝜏_ =17x, Alpaca-7B as small language model) from GSM8K using
GPT-4.


Figure 5: Recovering the compressed prompt (1/ _𝜏_ =19x, GPT2-Alpaca as small language model) from GSM8K
using GPT-4.





Figure 6: Recovering the compressed prompt(1/ _𝜏_ =7x, Alpaca-7B as small language model) from BBH using
GPT-4.


Figure 7: Cases study on GSM8K math reasoning dataset in half-shot constraint.


Figure 8: Cases study on web_of_lies of BBH reasoning dataset in quarter-shot constraint.


**Compressed Prompt:**
Please provide the example of the radiation beam spectrum in the TOPAS format, and I will learn
from it.
The beam energy spectrum is composed of 12 energy levels with corresponding weights.
dv:So/SARRPbeam/BeamEnergySpectrumValues: Lists the energy values in the spectrum,
separated by tabs.
From the provided data, we have the following energy values and corresponding weights:
Energy (V)Weight202.15E-0520.12.29E-0520.22.43E0520.32.580520.42.74052.52.9152.63.0
952.7.29052.8.49E-0520.93.71E05213.94E-0521.14.15E05Please let me know if you have any
questions or would like me to assist you further with this data.
Now I’ll give you a table with the spectrum of an ElektaAC and I want you to transform it to the
topas format:
Please provide the table with the spectrum of the Elekta LINAC, and I will transform it into theAS
format for you.
E (MeV) Elekta (6 MV)
0.25 0.173E—04(1.5%)\n .5 .100E03(0.5%)\n .75 .110E03(.5%)\n 1 0.952E—04(0.5%)\n 1.25
.827E04(.5\n .5 .721E04(.\n . .63E04(.\n 2 .55E04(.%)\n . .493E04(0.5%)\n 2.5 .437E04(.6\n
2.5 .386E04(.6\n 3 .34E4(.6\n . .30E4(.6\n . .27E4(.7\n 3.7 0.240E—04(.7\n 4 .21E04(.7\n .
.18E(.8\n . .16E(.8\n .14E(.9\n 5 .121E04(.9\n 5.2 .101E4(1.0\n . .81E0(.1\n . .64E.2\n 6 .45E.4\n
.0.300E—05(1.8\n 6.5 .15E0(.4\n .7 .73E0(.4\n 7 .29E0(.0\n . .88E0(.\n .18E—07(19.8%)\n 7.75
0.277E—08(50.0%)\n 8 0.159E—08(70.8%)
**The Generation of Full-shot Prompt:**
Thank you for providing the table with the Elekta LINAC spectrum. Here’s the TOPAS format for







|the same: # Spectrum|Col2|
|---|---|
|s:...Type|"Discrete"|
|dv:...Values|0.25<br>0.5<br>0.75<br>1<br>1.25<br>1.5<br>1.75<br>2<br>2.25<br>2.5<br>2.75<br>3<br>3.25<br>3.5<br>3.75<br>4<br>4.25<br>4.5<br>4.75<br>5<br>5.25<br>5.5<br>5.75<br>6<br>6.25<br>6.5<br>6.75<br>7<br>7.25<br>7.5<br>7.75<br>8|
|uv:...Weights|0.173E-04<br>0.100E-03<br>0.110E-03<br>0.952E-04<br>0.827E-04<br>0.721E-04<br>0.635E-04<br>0.557E-04<br>0.493E-04<br>0.437E-04<br>0.386E-04<br>0.345E-04<br>0.302E-04<br>0.270E-04<br>0.240E-04<br>0.210E-04<br>0.186E-04<br>0.164E-04<br>0.142E-04<br>0.121E-04<br>0.101E-04<br>0.817E-05<br>0.645E-05<br>0.455E-05<br>0.300E-05<br>0.156E-05<br>0.734E-06<br>0.294E-06<br>0.882E-07<br>0.188E-07<br>0.277E-08<br>0.159E-08|


I hope this helps. Let me know if you have any questions or if you need further assistance.
**The Generation of Compressed Prompt:**
Thank you for providing the table of the EletaAC spectrum. Here’s how it can be formatted in the

|TOPAS format: # Spectrum|Col2|
|---|---|
|s:...Type|"Discrete"|
|dv:...Values|0.25<br>1.5<br>2<br>3.2<br>4<br>5<br>6<br>7<br>7.25<br>7.5<br>7.75<br>8|
|uv:...Weights|173E04<br>.10E-0<br>.11E1<br>.950<br>.82<br>.63E-0<br>.55E0<br>.4943<br>.345E0<br>.30E0<br>.27<br>.24E0<br>.16E0<br>.714E52<br>.64E0<br>6.45E0<br>.30E0<br>.15E0<br>.73E0<br>.294E-06<br>.882E-07<br>.188E-07<br>.277E-08<br>.159E-08|



Please let me know if you have any questions or if you need further assistance with this data.
**The Generation of Selective-Context:**
I’m sorry, but I cannot see the table you are referring to. Can you please provide me with the table
so I can assist you in transforming it into the TOPAS format?


Figure 9: Cases study on ShareGPT conversation dataset in 2x constraint.


Figure 10: Cases study on Arxiv-March23 summarization dataset in 200 tokens constraint.


