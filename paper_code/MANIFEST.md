# paper_code · 论文代码清单与下载指南

> **本目录只跟踪 README/MANIFEST，克隆下来的他人仓库被 `.gitignore` 忽略，不入库。**
> 每位合作者按需用 `scripts/download_paper_code.py` 选择性拉取，避免一次性下载过大。

## 一、合作者怎么用（3 步）

```bash
# 1) 看清单（默认只打印，不下载）
python scripts/download_paper_code.py --list

# 2) 选你要的下载（按 name 选，逗号分隔）
python scripts/download_paper_code.py --only ExpeL,MIRIX        # 只下这两篇
python scripts/download_paper_code.py --module 04_记忆进化       # 下整个模块
python scripts/download_paper_code.py --only MemGPT,Voyager     # 下多篇

# 3) 已下的默认跳过；要重下加 --force
python scripts/download_paper_code.py --only ExpeL --force
```

**默认浅克隆（`git clone --depth 1`，省 90%+ 体积）；要完整历史加 `--no-shallow`。**

## 二、仓库清单（18 个可克隆 + 3 个无公开仓库）

| name | 模块 | 仓库 | 备注 |
|---|---|---|---|
| Survey-List | 00_综述 | https://github.com/nuster1128/LLM_Agent_Memory_Survey | 综述配套论文清单（纯 README） |
| LLMLingua | 01_短期记忆 | https://github.com/microsoft/LLMLingua | LLMLingua/LongLLMLingua/LLMLingua-2 全家桶 |
| ICAE | 01_短期记忆 | https://github.com/ARISE-Initiative/ICAE | In-context Autoencoder 压缩 |
| MemGPT | 01_短期记忆 | https://github.com/cpacker/MemGPT | 虚拟内存分页（现 Letta：https://github.com/letta-ai/letta） |
| Reflexion | 02_长期记忆 | https://github.com/noahshinn024/reflexion | 语言反思 + 情景记忆 |
| Voyager | 02_长期记忆 | https://github.com/MineDojo/Voyager | 可执行技能库 + 自动课程 |
| Memp | 02_长期记忆 | https://github.com/zjunlp/MemP | 程序性记忆 Build/Retrieve/Update |
| MemoryBank | 02_长期记忆 | https://github.com/zhongwanjun/MemoryBank-SiliconFriend | 艾宾浩斯遗忘曲线 + 每日摘要 |
| Zep | 02_长期记忆 | https://github.com/getzep/graphiti | 时序知识图谱引擎（另 https://github.com/getzep/zep） |
| MemoChat | 02_长期记忆 | https://github.com/LuJunru/MemoChat | memo 化长程对话一致 |
| ExpeL | 03_记忆检索 | https://github.com/LeapLabTHU/ExpeL | Faiss 向量召回 + 经验提炼 |
| MIRIX | 03_记忆检索 | https://github.com/Mirix-AI/MIRIX | 六类记忆 + 多智能体（`public_evaluation` 分支） |
| MemAlpha | 03_记忆检索 | https://github.com/wangyu-ustc/Mem-alpha | RL 学习记忆构建 |
| TiM | 04_记忆进化 | https://github.com/Jiahao-Wang-ZJU/TiM | Recalling + Post-thinking + 插入/遗忘/合并 |
| SCM | 04_记忆进化 | https://github.com/wbbeyourself/SCM4LLMs | 记忆控制器 + flash/archived 双记忆 |
| PREMem | 04_记忆进化 | https://github.com/sangyeop-kim/PREMem | 预存储推理 + 跨会话链接对 |
| MemSkill | 04_记忆进化 | https://github.com/ViktorAxelsen/MemSkill | 可学习可进化记忆技能 |
| StructMem | 04_记忆进化 | https://github.com/zjunlp/LightMem | 事件级绑定 + 跨事件整合 |

**无公开代码仓库（仅项目主页，不会克隆）：**
- **LARP**：https://miao-ai-lab.github.io/LARP/（项目主页，无公开代码）
- **ChatDB**：https://chatdatabase.github.io/（项目主页，未见公开代码仓库）
- **LongLLMLingua**：并入 `microsoft/LLMLingua` 仓库（与 LLMLingua 同一仓库，clone LLMLingua 即可）

## 三、网络问题（克隆 GitHub 常被重置）

```bash
# 直连失败 → 让 git 走本地代理（v2rayN 默认 10809）
git config --global http.proxy  http://127.0.0.1:10809
git config --global https.proxy http://127.0.0.1:10809
# 然后重跑失败的：
python scripts/download_paper_code.py --only <name>
```

> 注：本机 `gl hf/monitor.ps1` 已改好，**不会清掉这个 git 代理**（详见该脚本顶部注释）。

## 四、约定

- 克隆目标：`paper_code/<模块>/<dirname>/`（由脚本自动创建）；
- 复现结论（能跑/不能跑/关键修改）记到对应模块 `README.md` 或 `../docs/`；
- 仓库地址以论文官方页为准；如失效，按论文笔记里的 arXiv 链接回查。
