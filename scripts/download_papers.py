# -*- coding: utf-8 -*-
"""
一键下载《03-记忆系统关键技术-长短期记忆+记忆系统评估.pdf》中提到的相关论文 PDF。

用法（在本仓库根目录运行）：
    python scripts/download_papers.py            # 下载全部
    python scripts/download_papers.py --dry-run  # 只打印将要下载的清单，不联网

下载目标：references/<模块>/*.pdf（与 references 各子目录 README 对应）。
依赖：仅用 Python 标准库（urllib），无需安装第三方包。
"""

import argparse
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (目标文件名, arxiv_id 或 None, 搜索标题 或 None, 目标子目录)
# arxiv_id 优先；没有把握的论文用标题走 arXiv API 搜索。
PAPERS = [
    # ---- 00 综述 ----
    ("Zhang2024-Survey-Memory-Mechanism.pdf", "2404.13501", None, "00_综述"),
    # ---- 01 短期记忆 ----
    ("Jiang2023-LLMLingua.pdf",            "2310.05736", None, "01_短期记忆"),
    ("Jiang2024-LongLLMLingua.pdf",        "2310.06839", None, "01_短期记忆"),
    ("Ge2024-ICAE.pdf",                    "2307.06945", None, "01_短期记忆"),
    ("Packer2023-MemGPT.pdf",              "2310.08560", None, "01_短期记忆"),
    # ---- 02 长期记忆 ----
    ("Shinn2023-Reflexion.pdf",            "2303.11366", None, "02_长期记忆"),
    ("Wang2023-Voyager.pdf",               "2305.16291", None, "02_长期记忆"),
    ("Fang2025-Memp.pdf",                  "2508.06433", None, "02_长期记忆"),
    ("Yan2023-LARP.pdf",                   "2312.17653", None, "02_长期记忆"),
    ("Zhong2023-MemoryBank.pdf",           "2305.10250", None, "02_长期记忆"),
    ("Rasmussen2025-Zep.pdf",              "2501.13956", None, "02_长期记忆"),
    ("Lu2023-MemoChat.pdf",                "2308.08239", None, "02_长期记忆"),
    # ---- 03 记忆检索 ----
    ("Hu2023-ChatDB.pdf",                  "2306.03901", None, "03_记忆检索"),
    ("Zhao2023-ExpeL.pdf",                 "2308.10144", None, "03_记忆检索"),
    ("Wang2025-MIRIX.pdf",                 "2507.07957", None, "03_记忆检索"),
    ("Wang2025-MemAlpha.pdf",              "2509.25911", None, "03_记忆检索"),
    # ---- 04 记忆进化 ----
    ("Liu2023-TiM.pdf",                    "2311.08719", None, "04_记忆进化"),
    ("Liang2023-SCM.pdf",                  "2304.13343", None, "04_记忆进化"),
    ("Kim2025-PREMem.pdf",                 "2509.10852", None, "04_记忆进化"),
    ("Tan2025-RMM.pdf",                    None,
     "In Prospect and Retrospect: Reflective Memory Management for Long-term Personalized Dialogue Agents",
     "04_记忆进化"),
    ("StructMem-Structured-Memory.pdf",    None,
     "StructMem: Structured Memory for Long-Horizon Behavior in LLMs",
     "04_记忆进化"),
    ("MemSkill-Memory-Skills.pdf",         None,
     "MemSkill: Learning and Evolving Memory Skills for Self-Evolving Agents",
     "04_记忆进化"),
]

USER_AGENT = "Mozilla/5.0 (research-paper-downloader)"


def search_arxiv_id(title):
    """用 arXiv API 按标题搜索，返回第一个结果的 id；失败返回 None。"""
    q = urllib.parse.quote(f'ti:"{title}"')
    url = f"http://export.arxiv.org/api/query?search_query={q}&max_results=1"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"    搜索失败: {exc}")
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(data)
        entry = root.find("a:entry", ns)
        if entry is None:
            return None
        id_text = entry.find("a:id", ns).text
        return id_text.rsplit("/abs/", 1)[-1]
    except Exception:
        return None


def download_pdf(arxiv_id, dest_path):
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(data)
    return len(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印清单，不下载")
    args = parser.parse_args()

    ok, skip, fail, manual = 0, 0, 0, 0
    manual_list = []

    for filename, arxiv_id, title, folder in PAPERS:
        dest = os.path.join(ROOT, "references", folder, filename)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            print(f"[跳过] {folder}/{filename}（已存在）")
            skip += 1
            continue

        if arxiv_id is None and title:
            print(f"[搜索] {folder}/{filename}  <- {title}")
            if args.dry_run:
                continue
            arxiv_id = search_arxiv_id(title)
            if arxiv_id is None:
                print(f"  ! 未找到 arXiv 条目，请手动检索：{title}")
                manual_list.append((folder, filename, title))
                manual += 1
                continue

        if args.dry_run:
            print(f"[待下载] {folder}/{filename}  <- arXiv:{arxiv_id}")
            continue

        print(f"[下载] {folder}/{filename}  <- arXiv:{arxiv_id}")
        try:
            size = download_pdf(arxiv_id, dest)
            print(f"  ok ({size // 1024} KB)")
            ok += 1
        except Exception as exc:
            print(f"  失败: {exc}")
            fail += 1
            manual_list.append((folder, filename, f"arXiv:{arxiv_id}"))
            if os.path.exists(dest):
                os.remove(dest)

    print("\n===== 汇总 =====")
    print(f"成功 {ok}，跳过 {skip}，失败 {fail}，需手动 {manual}")
    if manual_list:
        print("需手动处理的条目：")
        for folder, filename, ref in manual_list:
            print(f"  - references/{folder}/{filename}  （{ref}）")


if __name__ == "__main__":
    sys.exit(main())
