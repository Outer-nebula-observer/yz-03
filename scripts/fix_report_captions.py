# -*- coding: utf-8 -*-
"""实验报告 docx 图表题注规范化 + 删除“7 配图与汇报建议”。
直接修改 word/document.xml 字符串，保留其他内容不变。
用法：
    python scripts/fix_report_captions.py --dry     # 只识别，不写入
    python scripts/fix_report_captions.py --apply   # 写入
"""
import argparse, io, re, sys, zipfile

DOCX = "docs/实验报告.docx"
NS_W = "http://purl.oclc.org/ooxml/wordprocessingml/main"

FIG_CAPS = [  # (识别关键词, 新题注文本)
    ("系统四层架构", "图1 系统四层架构"),
    ("系统架构细节与七步闭环", "图2 系统架构细节与七步闭环"),
    ("（不同 S）", "图3 遗忘曲线 R=e^{-t/S}（不同 S）"),
    ("单场任务数据流时序", "图4 单场任务数据流时序"),
    ("测试集8类结构", "图5 测试集 8 类结构"),
    ("G2 vs G3", "图6 G2 vs G3 分类别 hit@5 + 随机基线"),
    ("第一场沉淀→第二场命中", "图7 跨场次复用（第一场沉淀→第二场命中）"),
    ("噪声-召回取舍曲线", "图8 min_score 噪声-召回取舍曲线"),
    ("DeepSeek 规划输出引用记忆", "图9 DeepSeek 规划输出引用记忆"),
]
TBL_NAMES = [
    "问题定义与失败模式（P1–P5）",
    "伪代码与真实实现映射",
    "RQ—假设—操作化—结果映射",
    "测试集用例构成与标注",
    "对照组设计（G0–G6）",
    "系统配置参数",
    "任务层基线（G0–G3）",
    "双库贡献总体指标（G2 vs G3）",
    "分类别 hit@5",
    "跨场次复用结果",
    "检索策略对比",
    "min_score 噪声研究",
    "遗忘保护线检查",
    "阶段亲和（G6）",
    "DeepSeek 真实模型验证",
    "结果小结",
]

def xml_escape(t):
    return t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def unescape(t):
    return (t.replace("&lt;","<").replace("&gt;",">").replace("&quot;",'"')
             .replace("&apos;","'").replace("&amp;","&"))

def para_iter(s):
    for m in re.finditer(r"<w:p\b[^>]*>.*?</w:p>", s, re.S):
        frag = m.group(0)
        text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", frag, re.S))
        yield m.start(), m.end(), frag, unescape(text)

def find_para(s, keyword):
    for st, en, frag, text in para_iter(s):
        if keyword in text:
            return st, en, frag, text
    return None

def caption_xml(t):
    rpr = (f'<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
           f'w:eastAsia="宋体"/><w:b/><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr>')
    return (f'<w:p><w:pPr><w:jc w:val="center"/>{rpr}</w:pPr>'
            f'<w:r>{rpr}<w:t xml:space="preserve">{xml_escape(t)}</w:t></w:r></w:p>')

def table_list(s):
    out=[]
    for m in re.finditer(r"<w:tbl\b[^>]*>.*?</w:tbl>", s, re.S):
        frag=m.group(0)
        tr_list=re.findall(r"<w:tr(?:\s[^>]*)?>.*?</w:tr>", frag, re.S)
        rows=len(tr_list)
        cols=len(re.findall(r"<w:tc(?:\s[^>]*)?>", tr_list[0])) if tr_list else 0
        text="".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", frag, re.S))
        out.append({"start":m.start(),"end":m.end(),"cols":cols,"rows":rows,"text":unescape(text)})
    return out


def find_caption_para(s, keyword, must_fig=False, must_tbl=False):
    first=None
    for st,en,frag,text in para_iter(s):
        if keyword in text:
            ok=True
            if must_fig and not text.strip().startswith("图"): ok=False
            if must_tbl and not text.strip().startswith("表"): ok=False
            if ok: return st,en,frag,text
            if first is None: first=(st,en,frag,text)
    return first

def apply_changes():
    import os, shutil
    z=zipfile.ZipFile(DOCX)
    s=z.read("word/document.xml").decode("utf-8")
    infos=z.infolist(); blobs={i.filename:z.read(i.filename) for i in infos}
    z.close()
    before=len(s)

    # 1) 删除“7 配图与汇报建议”整章（保留 8 参考文献）
    p7=find_para(s,"7 配图与汇报建议"); p8=find_para(s,"8 参考文献")
    assert p7 and p8, "未找到第7章或参考文献"
    s = s[:p7[0]] + s[p8[0]:]
    print("已删除第7章，长度", before, "->", len(s))

    # 2) 图题：按位置重排为 图1..图9，统一居中五号加粗
    for kw,new in FIG_CAPS:
        r=find_caption_para(s,kw,must_fig=True)
        assert r, f"未找到图题: {kw}"
        s = s[:r[0]] + caption_xml(new) + s[r[1]:]
        print("图题 ->", new)

    # 3) 删除旧表题“表 1｜...”
    r=find_caption_para(s,"表 1｜",must_tbl=True)
    if r:
        s=s[:r[0]]+s[r[1]:]
        print("已删除旧表题")

    # 4) 正文交叉引用：该表新编号为 表3
    s=s.replace("对应为表1","对应为表3").replace("对应为表 1","对应为表 3")

    # 5) 为正文数据表插入表题（表前）
    absr=find_para(s,"摘要"); abs_start=absr[0] if absr else 0
    tbls=[t for t in table_list(s) if t["start"]>abs_start and t["cols"]>=2]
    assert len(tbls)==len(TBL_NAMES), f"表数量不符：{len(tbls)} vs {len(TBL_NAMES)}"
    inserts=[]
    for i,t in enumerate(tbls):
        cap=f"表{i+1} {TBL_NAMES[i]}"
        inserts.append((t["start"], caption_xml(cap)))
        print("表题 ->", cap)
    for pos,xml in sorted(inserts,key=lambda x:x[0],reverse=True):
        s=s[:pos]+xml+s[pos:]

    # 6) 写回 docx
    tmp=DOCX+".tmp"
    with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as zout:
        for info in infos:
            data=blobs[info.filename]
            if info.filename=="word/document.xml":
                data=s.encode("utf-8")
            zout.writestr(info,data)
    os.replace(tmp,DOCX)
    print("写入完成:", DOCX)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--apply",action="store_true"); ap.add_argument("--dry",action="store_true")
    args=ap.parse_args()
    z=zipfile.ZipFile(DOCX); s=z.read("word/document.xml").decode("utf-8")
    print("=== 图题识别 ===")
    for kw,new in FIG_CAPS:
        r=find_para(s,kw)
        print(("✓" if r else "✗"), kw, "->", new, "| 原文:", (r[3][:36] if r else "NOT FOUND"))
    print("=== 数据表识别（摘要之后、列数>=2）===")
    abs_para=find_para(s,"摘要")
    abs_start=abs_para[0] if abs_para else 0
    tbls=[t for t in table_list(s) if t["start"]>abs_start and t["cols"]>=2]
    for i,t in enumerate(tbls,1):
        name=TBL_NAMES[i-1] if i<=len(TBL_NAMES) else "??"
        print(f"表{i} {name} | {t['rows']}行 {t['cols']}列 | {t['text'][:42]}")
    print("共识别数据表:", len(tbls), "| 预期:", len(TBL_NAMES))
    if args.apply:
        apply_changes()

if __name__=="__main__":
    main()
