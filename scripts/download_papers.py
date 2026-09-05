# -*- coding: utf-8 -*-
"""
一键下载《03-记忆系统关键技术-长短期记忆+记忆系统评估.pdf》中提到的相关论文 PDF。

用法（在仓库根目录运行）：
    python scripts/download_papers.py                                 # 自动重试下载
    python scripts/download_papers.py --proxy http://127.0.0.1:7890   # 走本地代理（Clash/v2ray）
    python scripts/download_papers.py --retries 6                     # 加大每篇重试轮数
    python scripts/download_papers.py --dry-run                       # 只打印清单，不联网

下载目标：references/<模块>/*.pdf（与 references 各子目录 README 对应）。
依赖：仅用 Python 标准库（urllib）。

网络说明（重要）：
    - arxiv 系域名在国内常被随机重置（WinError 10054），表现为"时好时坏"；
    - 脚本默认对每篇论文做多轮重试（每轮依次尝试 arxiv.org / export.arxiv.org /
      cn.arxiv.org），重置通常是间歇性的，多试几轮即可成功；
    - 若所有轮次都失败，用 --proxy 指定本地代理（常见端口 7890 / 7891 / 1080 / 10809），
      也会自动读取环境变量 HTTPS_PROXY / HTTP_PROXY。
"""

import argparse
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (目标文件名, arxiv_id 或 None, 搜索标题 或 None, 目标子目录)
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

# 注意：xxx.itp.ac.cn 镜像已失效（DNS 解析失败），不再尝试。
HOSTS = [
    "https://arxiv.org",
    "https://export.arxiv.org",
    "https://cn.arxiv.org",
    "http://export.arxiv.org",
]

API_URLS = [
    "https://export.arxiv.org/api/query",
    "http://export.arxiv.org/api/query",
    "https://arxiv.org/api/query",
]


def get_proxy(explicit=None):
    if explicit:
        return explicit
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.get(key)
        if val:
            return val
    return None


def build_opener(proxy, timeout):
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    handlers.append(urllib.request.HTTPSHandler(context=ctx))
    return urllib.request.build_opener(*handlers), timeout


def is_valid_pdf(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"%PDF"
    except OSError:
        return False


def search_arxiv_id(title, opener, timeout, retries):
    q = urllib.parse.quote(f'ti:"{title}"')
    for attempt in range(1, retries + 1):
        for api in API_URLS:
            url = f"{api}?search_query={q}&max_results=1"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with opener.open(req, timeout=timeout) as resp:
                    data = resp.read().decode("utf-8", errors="replace")
                ns = {"a": "http://www.w3.org/2005/Atom"}
                entry = ET.fromstring(data).find("a:entry", ns)
                if entry is None:
                    continue
                id_text = entry.find("a:id", ns).text
                return id_text.rsplit("/abs/", 1)[-1]
            except Exception:
                continue
        if attempt < retries:
            time.sleep(1.5)
    return None


def download_pdf(arxiv_id, dest_path, opener, timeout, retries, proxy):
    errors = []
    for attempt in range(1, retries + 1):
        for host in HOSTS:
            url = f"{host}/pdf/{arxiv_id}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with opener.open(req, timeout=timeout) as resp:
                    data = resp.read()
                if not data.startswith(b"%PDF"):
                    errors.append(f"第{attempt}轮 {url} -> 非 PDF 内容")
                    continue
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(data)
                return len(data)
            except Exception as exc:
                errors.append(f"第{attempt}轮 {url} -> {exc}")
                continue
        if attempt < retries:
            time.sleep(1.5)
    if proxy:
        errors.append(f"(已使用代理 {proxy}，仍失败)")
    raise RuntimeError("；".join(errors[-10:]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy", default=None, help="本地代理地址，如 http://127.0.0.1:7890")
    parser.add_argument("--timeout", type=int, default=20, help="单次请求超时秒数（默认 20）")
    parser.add_argument("--retries", type=int, default=4, help="每篇论文的重试轮数（默认 4）")
    parser.add_argument("--dry-run", action="store_true", help="只打印清单，不下载")
    args = parser.parse_args()

    proxy = get_proxy(args.proxy)
    opener, timeout = build_opener(proxy, args.timeout)
    print(f"[配置] 重试 {args.retries} 轮/篇，超时 {timeout}s，代理={proxy or '无'}")
    if not proxy:
        print("       提示：arxiv 直连是间歇性重置，多轮重试通常能成功；有 Clash/VPN 可加 --proxy http://127.0.0.1:7890")

    ok, skip, fail, manual = 0, 0, 0, 0
    manual_list = []

    for filename, arxiv_id, title, folder in PAPERS:
        dest = os.path.join(ROOT, "references", folder, filename)
        if os.path.exists(dest):
            if is_valid_pdf(dest):
                print(f"[跳过] {folder}/{filename}（已存在且有效）")
                skip += 1
                continue
            os.remove(dest)  # 损坏文件，删掉重下

        if arxiv_id is None and title:
            print(f"[搜索] {folder}/{filename}  <- {title}")
            if args.dry_run:
                continue
            arxiv_id = search_arxiv_id(title, opener, timeout, args.retries)
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
            size = download_pdf(arxiv_id, dest, opener, timeout, args.retries, proxy)
            print(f"  ok ({size // 1024} KB)")
            ok += 1
        except Exception as exc:
            print(f"  失败：{exc}")
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
        print("\n建议：")
        print("  1) 再跑一次：python scripts/download_papers.py（已成功的会自动跳过）")
        print("  2) 有代理：python scripts/download_papers.py --proxy http://127.0.0.1:7890")
        print("  3) 浏览器打开 https://arxiv.org/pdf/<编号>（能访问时）")


if __name__ == "__main__":
    sys.exit(main())
