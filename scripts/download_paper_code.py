# -*- coding: utf-8 -*-
"""
论文公开代码 · 选择性下载脚本
============================
把各篇论文的官方代码仓库 git clone 到 paper_code/<模块>/ 下。
**默认只打印清单不下载**，合作者按需选择，避免一次性拉取过大。

用法（在仓库根目录运行）：
    # 0) 看清单（默认行为，不下载）
    python scripts/download_paper_code.py
    python scripts/download_paper_code.py --list

    # 1) 下载指定论文（逗号分隔，按清单 "name" 列）
    python scripts/download_paper_code.py --only ExpeL,MIRIX
    python scripts/download_paper_code.py --only MemGPT,Voyager,Reflexion

    # 2) 下载整个模块
    python scripts/download_paper_code.py --module 记忆进化
    python scripts/download_paper_code.py --module 短期记忆      # 模块名片段也可

    # 3) 下载全部（慎用，体积大）
    python scripts/download_paper_code.py --all

    # 4) 浅克隆（默认开，省空间）；要完整历史加 --no-shallow
    python scripts/download_paper_code.py --only ExpeL --no-shallow

    # 5) 已存在则跳过；强制重新克隆加 --force
    python scripts/download_paper_code.py --only ExpeL --force

说明：
    - 默认 git clone --depth 1（浅克隆，只取最新一次提交，省 90%+ 体积）；
    - 仓库克隆到 paper_code/<模块>/<dirname>/，已存在默认跳过；
    - 克隆下来的目录被 .gitignore 忽略（不入库，每人本地按需拉）；
    - 无公开代码仓库的论文（LARP / ChatDB 仅项目主页）会在清单里标注，不会尝试 clone；
    - MIRIX 用其 public_evaluation 分支；
    - 失败的会在汇总里列出，多为网络/代理问题——见末尾"网络提示"；
    - 若 git 配了代理但代理没开（直连本可用），克隆失败后会自动绕过代理直连重试一次。

网络提示（克隆 GitHub 同样可能被重置）：
    - 直连失败时配 git 走本地代理（v2rayN 默认 10809）：
        git config --global http.proxy http://127.0.0.1:10809
        git config --global https.proxy http://127.0.0.1:10809
      （monitor.ps1 已改好，不会清掉这个 git 代理）
    - 或临时走代理：HTTPS_PROXY=http://127.0.0.1:10809 python scripts/download_paper_code.py --only ExpeL
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER_CODE = os.path.join(ROOT, "paper_code")

# (name, 模块, repo_url, target_dirname, 备注)
# name = --only 用的关键字；模块 = paper_code 下的子目录名
PAPERS = [
    # ---- 00 综述（论文清单仓库，非代码，可选）----
    ("Survey-List", "00_综述", "https://github.com/nuster1128/LLM_Agent_Memory_Survey",
     "LLM_Agent_Memory_Survey", "综述配套论文清单仓库（纯 README，体积小）"),
    # ---- 01 短期记忆 ----
    ("LLMLingua", "短期记忆", "https://github.com/microsoft/LLMLingua",
     "LLMLingua", "LLMLingua / LongLLMLingua / LLMLingua-2 全家桶"),
    ("ICAE", "短期记忆", "https://github.com/getao/icae",
     "ICAE", "In-context Autoencoder 上下文压缩（Tao Ge 官方发布；旧链 ARISE-Initiative/ICAE 已失效）"),
    ("MemGPT", "短期记忆", "https://github.com/cpacker/MemGPT",
     "MemGPT", "虚拟内存分页式工作记忆（现 Letta：https://github.com/letta-ai/letta）"),
    # ---- 02 长期记忆 ----
    ("Reflexion", "长期记忆", "https://github.com/noahshinn/reflexion",
     "reflexion", "语言反思 + 情景记忆（原 noahshinn024 已改名 noahshinn）"),
    ("Voyager", "长期记忆", "https://github.com/MineDojo/Voyager",
     "Voyager", "可执行技能库 + 自动课程"),
    ("Memp", "长期记忆", "https://github.com/zjunlp/MemP",
     "MemP", "程序性记忆 Build/Retrieve/Update"),
    ("MemoryBank", "长期记忆", "https://github.com/zhongwanjun/MemoryBank-SiliconFriend",
     "MemoryBank-SiliconFriend", "艾宾浩斯遗忘曲线 + 每日摘要"),
    ("Zep", "长期记忆", "https://github.com/getzep/graphiti",
     "graphiti", "时序知识图谱引擎（Zep 核心）；另有服务端 https://github.com/getzep/zep"),
    ("MemoChat", "长期记忆", "https://github.com/LuJunru/MemoChat",
     "MemoChat", "memo 化长程对话一致"),
    # ---- 03 记忆检索 ----
    ("ExpeL", "记忆检索", "https://github.com/LeapLabTHU/ExpeL",
     "ExpeL", "Faiss 向量召回 + 经验提炼"),
    ("MIRIX", "记忆检索", "https://github.com/Mirix-AI/MIRIX",
     "MIRIX", "六类记忆 + 多智能体（用 public_evaluation 分支）", "public_evaluation"),
    ("MemAlpha", "记忆检索", "https://github.com/wangyu-ustc/Mem-alpha",
     "Mem-alpha", "RL 学习记忆构建；HF 数据/模型见论文笔记"),
    # ---- 04 记忆进化 ----
    ("SCM", "记忆进化", "https://github.com/wbbeyourself/SCM4LLMs",
     "SCM4LLMs", "记忆控制器 + flash/archived 双记忆"),
    ("PREMem", "记忆进化", "https://github.com/sangyeop-kim/PREMem",
     "PREMem", "预存储推理 + 跨会话链接对"),
    ("MemSkill", "记忆进化", "https://github.com/ViktorAxelsen/MemSkill",
     "MemSkill", "可学习可进化记忆技能"),
    ("StructMem", "记忆进化", "https://github.com/zjunlp/LightMem",
     "LightMem", "事件级绑定 + 跨事件整合（论文脚注指向此仓库）"),
]

# 仅论文清单或非纯代码实现（按需克隆；LLMLingua 已并入 LLMLingua 仓库，可略）
NO_REPO_ONLY = {
    "LARP": "https://miao-ai-lab.github.io/LARP/ （项目主页，无公开代码仓库）",
    "ChatDB": "https://chatdatabase.github.io （项目主页，未见公开代码仓库）",
    "TiM": "无公开代码仓库（论文/arXiv 页均未提供，GitHub 检索无官方实现）；论文 https://arxiv.org/abs/2311.08719",
}


def git_available():
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def clone(name, module, url, dirname, note, branch=None, shallow=True, force=False):
    dest = os.path.join(PAPER_CODE, module, dirname)
    if os.path.exists(dest) and not force:
        print(f"[跳过] 已存在: {module}/{dirname}（--force 可重克隆）")
        return "skip"
    if force and os.path.exists(dest):
        # 删除旧目录
        subprocess.run(["rmdir", "/s", "/q", dest], shell=True) if os.name == "nt" \
            else subprocess.run(["rm", "-rf", dest])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    cmd = ["git", "clone", "--depth", "1"] if shallow else ["git", "clone"]
    if branch:
        cmd += ["--branch", branch]
    cmd += [url, dest]
    print(f"[克隆] {name} -> {module}/{dirname}")
    print(f"       $ {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print(f"       完成")
        return "ok"
    except subprocess.CalledProcessError:
        # 常见根因：git 全局配了代理但代理当前没开（直连其实可用）。
        # 若配置了 http.proxy，则绕过代理直连重试一次，自愈这类失败。
        r = subprocess.run(["git", "config", "--get", "http.proxy"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            print("       走代理失败，尝试绕过代理直连重试……")
            retry = ["git", "-c", "http.proxy=", "-c", "https.proxy="] + cmd[1:]
            try:
                subprocess.run(retry, check=True)
                print("       完成（直连）")
                return "ok"
            except subprocess.CalledProcessError:
                pass
        print(f"       失败（多为网络/代理；见脚本顶部'网络提示'）")
        return "fail"
    except Exception as exc:
        print(f"       失败: {exc}")
        return "fail"


def print_list():
    print("=" * 90)
    print(f"{'name':<14}{'模块':<14}{'dirname':<30}{'备注'}")
    print("-" * 90)
    for p in PAPERS:
        name, module, _url, dirname, note = p[0], p[1], p[2], p[3], p[4]
        print(f"{name:<14}{module:<14}{dirname:<30}{note}")
    if NO_REPO_ONLY:
        print("-" * 90)
        print("无公开代码仓库（仅项目主页）：")
        for k, v in NO_REPO_ONLY.items():
            print(f"  {k:<14}{v}")
    print("=" * 90)
    print(f"共 {len(PAPERS)} 个可克隆仓库；选择性下载：")
    print("  python scripts/download_paper_code.py --only ExpeL,MIRIX")
    print("  python scripts/download_paper_code.py --module 记忆进化")
    print("  python scripts/download_paper_code.py --all")


def main():
    parser = argparse.ArgumentParser(description="论文公开代码选择性下载", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="只打印清单不下载（默认行为）")
    parser.add_argument("--only", help="只下载指定论文（逗号分隔 name，如 ExpeL,MIRIX）")
    parser.add_argument("--module", help="只下载某模块（模块名片段即可，如 04 或 进化）")
    parser.add_argument("--all", action="store_true", help="下载全部（体积大，慎用）")
    parser.add_argument("--no-shallow", action="store_true", help="完整克隆（默认浅克隆 --depth 1）")
    parser.add_argument("--force", action="store_true", help="已存在也重新克隆")
    args = parser.parse_args()

    # 默认或 --list：只打印清单
    if not (args.only or args.module or args.all) or args.list:
        print_list()
        return 0

    if not git_available():
        print("错误：未检测到 git，请先安装 git。", file=sys.stderr)
        return 1

    targets = list(PAPERS)
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        unknown = wanted - {p[0] for p in PAPERS}
        for u in unknown:
            if u in NO_REPO_ONLY:
                print(f"[提示] {u}: {NO_REPO_ONLY[u]}")
            else:
                print(f"[警告] 未知 name '{u}'，已忽略。用 --list 查看可用 name。", file=sys.stderr)
        targets = [p for p in PAPERS if p[0] in wanted]
    elif args.module:
        kw = args.module.strip()
        targets = [p for p in PAPERS if kw in p[1]]

    if not targets:
        print("没有匹配的仓库。用 --list 查看清单。")
        return 0

    shallow = not args.no_shallow
    ok = skip = fail = 0
    for p in targets:
        name, module, url, dirname, note = p[0], p[1], p[2], p[3], p[4]
        branch = p[5] if len(p) > 5 else None
        r = clone(name, module, url, dirname, note, branch, shallow, args.force)
        if r == "ok":
            ok += 1
        elif r == "skip":
            skip += 1
        else:
            fail += 1

    print("\n===== 汇总 =====")
    print(f"成功 {ok}，跳过 {skip}，失败 {fail}")
    if NO_REPO_ONLY:
        print("\n以下论文无公开代码仓库，故不在下载范围（仅论文/主页）：")
        for k, v in NO_REPO_ONLY.items():
            print(f"  {k:<12}{v}")
    if fail:
        print("失败多为网络/代理问题，建议：")
        print("  git config --global http.proxy http://127.0.0.1:10809")
        print("  再重跑失败的：python scripts/download_paper_code.py --only <name>")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
