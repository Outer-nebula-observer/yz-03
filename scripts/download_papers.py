# -*- coding: utf-8 -*-
"""
一键下载《03-记忆系统关键技术-长短期记忆+记忆系统评估.pdf》中提到的相关论文 PDF。

用法（在本仓库根目录运行）：
    python scripts/download_papers.py            # 下载全部
    python scripts/download_papers.py --dry-run  # 只打印将要下载的清单，不联网

下载目标：references/<模块>/*.pdf（与 references 各子目录 README 对应）。
依赖：仅用 Python 标准库（urllib），无需安装第三方包。

网络说明：直连 arxiv.org 常被重置（WinError 10054）。脚本会优先尝试国内镜像：
    1) https://xxx.itp.ac.cn   （中科院理论物理所 arXiv 镜像）
    2) https://cn.arxiv.org    （arXiv 中国镜像，若可用）
    3) https://export.arxiv.org
    4) https://arxiv.org
"""

import argparse
import os
import ssl
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

PDF_HOSTS = [
    "https://xxx.itp.ac.cn",
    "https://cn.arxiv.org",
    "https://export.arxiv.org",
    "https://arxiv.org",
]

API_URLS = [
    "https://export.arxiv.org/api/query",
    "http://export.arxiv.org/api/query",
    "http://xxx.itp.ac.cn/api/query",
]


def _urlopen(url, timeout=60):
    """带 UA 的 urlopen；最后尝试忽略证书校验（兼容部分镜像的证书问题）。"""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except Exception:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def search_arxiv_id(title):
    """用 arXiv API 按标题搜索，返回第一个结果的 id；失败返回 None。"""
    q = urllib.parse.quote(f'ti:"{title}"')
    for api in API_URLS:
        url = f"{api}?search_query={q}&max_results=1"
        try:
            with _urlopen(url, timeout=30) as resp:
                data = resp.read().decode("utf-8", errors="replace")
            ns = {"a": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(data)
            entry = root.find("a:entry", ns)
            if entry is None:
                continue
            id_text = entry.find("a:id", ns).text
            return id_text.rsplit("/abs/", 1)[-1]
        except Exception:
            continue
    return None


def download_pdf(arxiv_id, dest_path):
    """依次尝试多个镜像下载；全部失败则抛异常。"""
    last_exc = None
    for host in PDF_HOSTS:
        url = f"{host}/pdf/{arxiv_id}"
        try:
            with _urlopen(url, timeout=60) as resp:
                data = resp.read()
            # 下载到的是 HTML 说明页面时视为失败（常见于 404 被 200 包装）
            head = data[:200].lstrip().lower()
            if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
                raise ValueError(f"返回了 HTML 页面（可能编号错误或需要跳转）：{url}")
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(data)
            return len(data)
        except Exception as exc:
            last_exc = exc
            continue
    raise last_exc


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
                print(f"    提示：到镜像站 https://xxx.itp.ac.cn 或 Google Scholar 搜标题，下载后命名为 {filename}")
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
        print("\n手动下载建议：打开 https://xxx.itp.ac.cn 搜标题 → 点 PDF 下载；")
        print("或直连 https://arxiv.org/pdf/<编号>（需能访问 arxiv 的网络/VPN）。")


if __name__ == "__main__":
    sys.exit(main())
