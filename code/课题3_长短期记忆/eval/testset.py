# -*- coding: utf-8 -*-
"""
eval.testset — 作战规划记忆测试集（44 条 · 8 类 · 检索 + 任务双层）
====================================================================
对应 docs/04 §5.2"自建作战测试集（≥40 条）"的落地，并按评审意见补齐
旧种子集（3 条）完全缺失的四类用例：

  A fact_param_sql   属性精确查询（sql 路 + attrs）——ChatDB 符号路真实验证
  B fact_semantic    事实语义查询（vector 路，转述措辞）
  C exp_semantic     经验语义查询（vector 路，转述措辞——同义不同词）
  D exp_lexical      经验词法查询（bm25 路）
  E negative         负例查询（无 gold）——测噪声返回率（旧集缺失①）
  F distractor_param 参数干扰查询——考"参数张冠李戴"（旧集缺失②：
                      T-90(60km/h) 与 M1A2(67km/h) 同库，查 T-90 必须命中
                      T-90 且排在 M1A2 之前——双库分治主张的直接检验）
  G stage_decisive   阶段决胜对——同内容不同 stage 标签，阶段亲和是唯一
                      判别依据（G6 消融专用；旧集缺失③）
  H cross_session    跨场次复用——场次1复盘写入 → 场次2 相关查询应召回
                      （"越用越强"的量化检验；旧集缺失④）

标注规范（防循环论证——评审 §1.6）：
  - 查询与记忆正文**刻意避免共享关键词**（语义类 C 用转述：查询"黑夜机动
    吃了什么亏" vs 记忆"夜间行军未派先遣侦察…遭敌伏击"）；
  - gold 由内容语义独立标注，不含任何系统实现信息；
  - E 类负例全部 gold=[]，用于测 min_score 滤噪；
  - 干扰记忆成对入库（同类装备、相邻数值），考精确性而非"库里只有一条
    貌似相关的就必中"。

用法：
    from eval.testset import build_stores, RETRIEVAL_CASES, CROSS_SESSION_CASES
    ctl = build_stores()               # 预置 28+8 条种子记忆
    cases = RETRIEVAL_CASES(ctl)       # A–G 类 38 条（gold id 绑定本次实例）
    h_cases = CROSS_SESSION_CASES()    # H 类 6 条（gold 在运行期由进化写入解析）
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from memsys import (MemoryController, MemoryType, QueryItem, new_entry)


# ================================================================ 种子记忆
# （与查询独立撰写；经验条目措辞与查询刻意错开）
SEED_FACTS: List[Tuple[str, dict]] = [
    # ---- 装备参数（含成对干扰：T-90/M1A2、红箭-9/标枪）----
    ("红方 T-90 主战坦克最大速度 60km/h，主炮 125mm。",
     {"装备": "T-90", "阵营": "红方", "stage": "mission_analysis"}),
    ("蓝方 M1A2 主战坦克最大速度 67km/h，主炮 120mm。",
     {"装备": "M1A2", "阵营": "蓝方", "stage": "mission_analysis"}),
    ("红方红箭-9 反坦克导弹射程 5.5 公里，破甲厚度 1200mm。",
     {"装备": "红箭-9", "stage": "mission_analysis"}),
    ("蓝方标枪反坦克导弹射程 2.5 公里，攻顶模式破甲 750mm。",
     {"装备": "标枪", "stage": "mission_analysis"}),
    ("红方 09 式自行榴弹炮射程 30 公里，最大射速 8 发/分。",
     {"装备": "09式自行榴弹炮", "stage": "mission_analysis"}),
    ("红方察打一体无人机续航 8 小时，挂载 4 枚空地导弹。",
     {"装备": "察打一体无人机", "stage": "mission_analysis"}),
    ("红方电子对抗连压制距离 15 公里，持续干扰时长 40 分钟。",
     {"装备": "电子对抗连", "stage": "mission_analysis"}),
    # ---- 地形/水文 ----
    ("2 号高地海拔 320 米，北坡缓南坡陡，仅东侧一条装甲通行道路。",
     {"地点": "2号高地", "stage": "mission_analysis"}),
    ("3 号高地海拔 210 米，地形开阔，有两条机械化通路。",
     {"地点": "3号高地", "stage": "mission_analysis"}),
    ("5 号高地海拔 450 米，坡度大，仅步兵小道可通行。",
     {"地点": "5号高地", "stage": "mission_analysis"}),
    ("青川河汛期水深 2.1 米，流速 1.8 米/秒，仅 3 号渡口可架舟桥。",
     {"地点": "青川河", "stage": "mission_analysis"}),
    # ---- 条令（orders_production 阶段 sql/attrs 路）----
    ("条令：营进攻战斗炮火准备不少于 15 分钟，步坦协同按三线配置。",
     {"类别": "条令", "stage": "orders_production"}),
    ("条令：强渡江河时工兵分队先期侦察渡口，舟桥架设按双舟方案。",
     {"类别": "条令", "stage": "orders_production"}),
    ("条令：战斗报告按'情况-决心-请求'三段式，每 30 分钟上报一次。",
     {"类别": "条令", "stage": "orders_production"}),
]

SEED_EXPS: List[Tuple[str, float, str]] = [
    # (内容, importance, stage) —— 种子经验显式 importance=2.0 表示
    # "人工标注的保命教训"（受遗忘保护线保护）；1.5 为普通经验。
    ("教训：夜间行军未派先遣侦察，先头分队在隘口遭敌伏击。",
     2.0, "coa_analysis"),
    ("经验：炮火准备前置 20 分钟，可显著压制敌方反坦克火力点。",
     1.5, "coa_development"),
    ("教训：渡河架桥耗时超出预估四成，主攻梯队因此迟到。",
     2.0, "coa_analysis"),
    ("经验：方案比选优先权衡风险与代价，而非只看预期战果。",
     1.5, "coa_comparison"),
    ("教训：定下决心时犹豫观望，曾错失最佳反击战机。",
     2.0, "coa_approval"),
    ("教训：逐屋清剿未交替掩护，突击组在楼道遭火力封锁。",
     2.0, "coa_analysis"),
    ("经验：无人机先行标注火力点，可缩短三成街区清剿时间。",
     1.5, "coa_development"),
    ("教训：反坦克阵地间距过近，遭敌炮火一次覆盖。",
     2.0, "coa_analysis"),
    ("经验：预设多个预备阵地每 20 分钟轮换，可显著降低损失。",
     1.5, "coa_development"),
    ("教训：无线电静默过久导致协同脱节，佯动分队暴露后无人接应。",
     2.0, "coa_analysis"),
    ("经验：假渡口佯动 15 分钟可有效牵制敌直瞄火力。",
     1.5, "coa_development"),
    ("教训：敌情通报滞后，预备队投入时机过晚。",
     1.5, "mission_analysis"),
    ("经验：命令文书使用标准三段式格式，可减少协同歧义。",
     1.5, "orders_production"),
    ("教训：未核查敌预备队位置，侧翼暴露遭反冲击。",
     2.0, "mission_analysis"),
]

# 阶段决胜对（G6 专用）：同内容、不同 stage——阶段亲和是唯一判别依据。
# 内容完全一致以隔离机制变量（类"数据集形态的单元测试"）。
STAGE_PAIRS: List[Tuple[str, str, str]] = [
    # (内容, stage_a, stage_b)  —— 查询用 stage_b，gold=stage_b 条
    ("经验：预备队应留置在便于机动的位置。", "coa_development", "coa_approval"),
    ("经验：交战前应完成目标区电子频谱侦察。", "mission_analysis", "coa_analysis"),
    ("经验：火力协同计划应明确到单一责任人。", "coa_development", "orders_production"),
    ("经验：穿插路线应避开敌直瞄火器封锁区。", "coa_development", "mission_analysis"),
]


def build_stores(controller: Optional[MemoryController] = None,
                 with_stage_pairs: bool = True,
                 with_exps: bool = True) -> MemoryController:
    """预置种子记忆（A–G 类用例的检索目标）。

    每组建独立 controller（消融要求互不污染）；gold id 绑定该实例。
    with_exps=False → 不注入经验种子（G2"仅事实库"对照组——真对照：
    固定用例集不变，只关能力开关）。
    """
    ctl = controller or MemoryController()
    for content, attrs in SEED_FACTS:
        e = new_entry(MemoryType.FACT, content, source="seed", attrs=attrs)
        e.id = _det_id("seed-f", content)   # 确定性 id：同内容跨实例同 id
        ctl.factual.add(e)
    if with_exps:
        for content, imp, stage in SEED_EXPS:
            e = new_entry(MemoryType.EXPERIENCE, content, source="seed",
                          importance=imp, attrs={"stage": stage})
            e.id = _det_id("seed-e", content)
            ctl.experiential.add(e)
    if with_stage_pairs:
        for content, stage_a, stage_b in STAGE_PAIRS:
            for st in (stage_a, stage_b):
                e = new_entry(MemoryType.EXPERIENCE, content,
                              source="seed-stagepair", importance=1.0,
                              attrs={"stage": st})
                e.id = _det_id("seed-g", content + st)  # 同内容两条按 stage 区分
                ctl.experiential.add(e)
    return ctl


def _det_id(prefix: str, content: str) -> str:
    """确定性 id：sha1(内容) 前 10 位——同内容同 id（跨 controller 实例）。

    消融各组各建独立 controller，uuid 会造成 gold id 无法跨组对应；
    确定性 id 使"用例集构建一次、多组复用"成为可能（G2 空经验库时，
    经验类 gold id 不会出现在该组检索结果里 → miss，语义正确）。
    """
    import hashlib
    return f"{prefix}-{hashlib.sha1(content.encode('utf-8')).hexdigest()[:10]}"


# ---------------------------------------------------------------- 参考实例
_REF: Optional[MemoryController] = None


def _reference() -> MemoryController:
    """全量种子的参考实例（gold 解析用；确定性 id 保证跨组一致）。"""
    global _REF
    if _REF is None:
        _REF = build_stores()
    return _REF


# ================================================================ 用例构造
def _fact_id(ctl: MemoryController, keyword: str) -> str:
    """按关键词定位种子事实 id（对参考实例解析；确定性 id 跨组一致）。"""
    ref = _reference()
    for cid in ref.factual.candidates():
        if keyword in ref.factual.get(cid).content:
            return cid
    raise KeyError(f"种子事实未找到: {keyword}")


def _exp_id(ctl: MemoryController, keyword: str) -> str:
    ref = _reference()
    for cid in ref.experiential.candidates():
        if keyword in ref.experiential.get(cid).content:
            return cid
    raise KeyError(f"种子经验未找到: {keyword}")


def RETRIEVAL_CASES(ctl: MemoryController) -> List[dict]:
    """A–G 类 38 条检索用例（gold id 绑定传入的 controller 实例）。

    每条：{qid, category, query: QueryItem, gold: List[str], distractor: str}
    """
    cases: List[dict] = []

    def add(category: str, qid: str, q: QueryItem, gold: List[str],
            distractor: str = "") -> None:
        cases.append({"qid": qid, "category": category, "query": q,
                      "gold": gold, "distractor": distractor})

    # ---------------- A. 属性精确查询（sql 路 + attrs）×6 ----------------
    add("A", "a1", QueryItem("a1", "查 T-90 参数（精确）", "fact", "sql",
                             attrs={"装备": "T-90"}), [_fact_id(ctl, "T-90")],
        _fact_id(ctl, "M1A2"))
    add("A", "a2", QueryItem("a2", "查 M1A2 参数（精确）", "fact", "sql",
                             attrs={"装备": "M1A2"}), [_fact_id(ctl, "M1A2")],
        _fact_id(ctl, "T-90"))
    add("A", "a3", QueryItem("a3", "查红箭-9 参数", "fact", "sql",
                             attrs={"装备": "红箭-9"}), [_fact_id(ctl, "红箭-9")],
        _fact_id(ctl, "标枪"))
    add("A", "a4", QueryItem("a4", "查青川河水文", "fact", "sql",
                             attrs={"地点": "青川河"}), [_fact_id(ctl, "青川河")])
    add("A", "a5", QueryItem("a5", "查全部条令", "fact", "sql",
                             attrs={"类别": "条令"}),
        [_fact_id(ctl, "炮火准备不少于 15 分钟"),
         _fact_id(ctl, "强渡江河"),
         _fact_id(ctl, "三段式")])
    add("A", "a6", QueryItem("a6", "查无人机参数", "fact", "sql",
                             attrs={"装备": "察打一体无人机"}),
        [_fact_id(ctl, "察打一体无人机")])

    # ---------------- B. 事实语义查询（vector 路，转述）×6 ----------------
    add("B", "b1", QueryItem("b1", "查红方坦克行驶速度", "fact", "vector",
                             "红方 主战坦克 行驶 速度"),
        [_fact_id(ctl, "T-90")], _fact_id(ctl, "M1A2"))
    add("B", "b2", QueryItem("b2", "哪座高地仅一条装甲通路", "fact", "vector",
                             "高地 只有一条 装甲 通行 道路"),
        [_fact_id(ctl, "仅东侧一条装甲")])
    add("B", "b3", QueryItem("b3", "炮兵能打多远", "fact", "vector",
                             "炮兵 火力 覆盖 距离"),
        [_fact_id(ctl, "09 式自行榴弹炮")])
    add("B", "b4", QueryItem("b4", "江河渡口架桥条件", "fact", "vector",
                             "渡口 架设 舟桥 水深 流速"),
        [_fact_id(ctl, "青川河")])
    add("B", "b5", QueryItem("b5", "反坦克导弹最远打多远", "fact", "vector",
                             "反坦克 导弹 最远 射程"),
        [_fact_id(ctl, "红箭-9"), _fact_id(ctl, "标枪")])
    add("B", "b6", QueryItem("b6", "步坦协同怎么配置", "fact", "vector",
                             "步兵 坦克 协同 配置 要求"),
        [_fact_id(ctl, "步坦协同按三线配置")])

    # ---------------- C. 经验语义查询（vector 路，转述·少共享词）×8 ----------------
    # 刻意转述：查询措辞与记忆正文字面重叠极低（换真 embedding 后
    # 这一类才是"语义泛化"的真检验；Mock 词袋下靠判别性单字）
    add("C", "c1", QueryItem("c1", "黑夜机动吃过什么亏", "experience", "vector",
                             "黑夜 机动 吃亏"), [_exp_id(ctl, "隘口遭敌伏击")])
    add("C", "c2", QueryItem("c2", "火力准备有什么心得", "experience", "vector",
                             "火力 准备 心得"), [_exp_id(ctl, "炮火准备前置 20 分钟")])
    add("C", "c3", QueryItem("c3", "过河耽误过事吗", "experience", "vector",
                             "过河 耽误"), [_exp_id(ctl, "渡河架桥耗时")])
    add("C", "c4", QueryItem("c4", "选方案时怎么权衡", "experience", "vector",
                             "方案 权衡"), [_exp_id(ctl, "方案比选优先权衡")])
    add("C", "c5", QueryItem("c5", "犹豫不决有什么后果", "experience", "vector",
                             "犹豫 后果"), [_exp_id(ctl, "犹豫观望")])
    add("C", "c6", QueryItem("c6", "巷战推进要注意什么", "experience", "vector",
                             "巷战 推进 注意"), [_exp_id(ctl, "逐屋清剿")])
    add("C", "c7", QueryItem("c7", "怎么防侧翼被反咬", "experience", "vector",
                             "侧翼 反咬 防范"), [_exp_id(ctl, "遭反冲击")])
    add("C", "c8", QueryItem("c8", "佯动有什么技巧", "experience", "vector",
                             "佯动 技巧"), [_exp_id(ctl, "假渡口佯动")])

    # ---------------- D. 经验词法查询（bm25 路）×4 ----------------
    add("D", "d1", QueryItem("d1", "伏击 隘口", "experience", "bm25",
                             "伏击 隘口 先头"), [_exp_id(ctl, "隘口遭敌伏击")])
    add("D", "d2", QueryItem("d2", "炮火准备 前置", "experience", "bm25",
                             "炮火准备 前置 压制"), [_exp_id(ctl, "炮火准备前置 20 分钟")])
    add("D", "d3", QueryItem("d3", "舟桥 渡口 佯动", "experience", "bm25",
                             "假渡口 佯动 牵制"), [_exp_id(ctl, "假渡口佯动")])
    add("D", "d4", QueryItem("d4", "静默 协同 脱节", "experience", "bm25",
                             "无线电静默 协同 脱节"), [_exp_id(ctl, "无线电静默过久")])

    # ---------------- E. 负例查询（无 gold）×6（×2 库=12 条）----------------
    # 预期：min_score 滤噪后应尽量返回空。指标：噪声返回率。
    for i, (neg_q, text) in enumerate([
        ("量子计算机的纠错原理", "量子计算机 纠错 原理"),
        ("食堂菜谱和后勤采购", "食堂 菜谱 后勤 采购"),
        ("足球比赛阵型安排", "足球 比赛 阵型 安排"),
        ("诗词格律与押韵", "诗词 格律 押韵"),
        ("股票量化交易策略", "股票 量化 交易 策略"),
        ("电影票房统计", "电影 票房 统计"),
    ], start=1):
        add("E", f"e{i}", QueryItem(f"e{i}", neg_q, "fact", "vector", text), [])
        cases.append({"qid": f"e{i}x", "category": "E",
                      "query": QueryItem(f"e{i}x", neg_q, "experience",
                                         "vector", text),
                      "gold": [], "distractor": ""})

    # ---------------- F. 参数干扰查询 ×4（张冠李戴检验）----------------
    add("F", "f1", QueryItem("f1", "T-90 最大速度", "fact", "vector",
                             "T-90 最大速度 多少"),
        [_fact_id(ctl, "T-90")], _fact_id(ctl, "M1A2"))
    add("F", "f2", QueryItem("f2", "M1A2 最大速度", "fact", "vector",
                             "M1A2 最大速度 多少"),
        [_fact_id(ctl, "M1A2")], _fact_id(ctl, "T-90"))
    add("F", "f3", QueryItem("f3", "红箭-9 射程", "fact", "vector",
                             "红箭-9 射程 多远"),
        [_fact_id(ctl, "红箭-9")], _fact_id(ctl, "标枪"))
    add("F", "f4", QueryItem("f4", "标枪导弹射程", "fact", "vector",
                             "标枪 导弹 射程 多远"),
        [_fact_id(ctl, "标枪")], _fact_id(ctl, "红箭-9"))

    # ---------------- G. 阶段决胜对 ×4（G6 专用）----------------
    for i, (content, stage_a, stage_b) in enumerate(STAGE_PAIRS, start=1):
        kw = content[3:13]  # 内容片段定位（两条同内容，按 metadata.stage 区分）
        gold_id = dist_id = ""
        for cid in _reference().experiential.candidates():
            e = _reference().experiential.get(cid)
            if kw in e.content and e.source == "seed-stagepair":
                if e.metadata.get("stage") == stage_b:
                    gold_id = cid
                elif e.metadata.get("stage") == stage_a:
                    dist_id = cid
        q_text = content.replace("经验：", "").replace("。", "")
        add("G", f"g{i}", QueryItem(f"g{i}", f"阶段决胜：{q_text}",
                                    "experience", "vector", q_text,
                                    stage=stage_b), [gold_id], dist_id)
    return cases


# ================================================================ H. 跨场次
def CROSS_SESSION_CASES() -> List[dict]:
    """H 类 6 条：场次1 复盘写入 → 场次2 查询复用（gold 运行期解析）。

    每条：{qid, s1_goal, s1_review, s2_goal, s2_query(5 元组), expect_keyword}
    gold = 场次1 进化写入、内容含 expect_keyword 的条目 id（由消融
    runner 在进化后解析——"越用越强"的运行期检验，无法静态标注）。
    """
    return [
        {"qid": "h1",
         "s1_goal": "夜间夺占 2 号高地",
         "s1_review": "复盘：任务部分达成。教训：夜间突袭未前置电子压制，接敌后通信被干扰。",
         "s2_goal": "夜间进攻 3 号高地",
         "s2_query": ("h1", "夜间进攻通信保障教训", "experience", "vector",
                      "夜间 进攻 通信 干扰 教训"),
         "expect_keyword": "电子压制"},
        {"qid": "h2",
         "s1_goal": "夺占 2 号高地",
         "s1_review": "复盘：任务达成。经验：突破口形成后预备队投入应提前 10 分钟。",
         "s2_goal": "夜间夺占 5 号高地",
         "s2_query": ("h2", "预备队使用经验", "experience", "vector",
                      "突破口 预备队 投入 经验"),
         "expect_keyword": "预备队投入应提前"},
        {"qid": "h3",
         "s1_goal": "山地进攻 5 号高地",
         "s1_review": "复盘：任务未达成。教训：山地进攻未控制制高点观察哨，全程被敌俯视。",
         "s2_goal": "山地防御 5 号高地",
         "s2_query": ("h3", "山地作战教训", "experience", "vector",
                      "山地 进攻 观察 教训"),
         "expect_keyword": "制高点"},
        {"qid": "h4",
         "s1_goal": "装甲梯队开进集结地域",
         "s1_review": "复盘：开进完成。经验：装甲梯队行军间隔保持 50 米，可有效降低敌炮火损失。",
         "s2_goal": "装甲梯队向 3 号高地开进",
         "s2_query": ("h4", "行军队形经验", "experience", "vector",
                      "装甲 梯队 行军 间隔"),
         "expect_keyword": "间隔保持 50 米"},
        {"qid": "h5",
         "s1_goal": "雨夜机动至出发阵地",
         "s1_review": "复盘：机动迟缓。教训：雨夜能见度低时未减速，导致车辆掉队两台。",
         "s2_goal": "雨夜夺占 2 号高地",
         "s2_query": ("h5", "雨夜机动教训", "experience", "vector",
                      "雨夜 能见度 机动 教训"),
         "expect_keyword": "能见度"},
        # h6：无关迁移控制——场次1 沉淀"渡河"教训，场次2 查"城市巷战"，
        # 期望**不**召回该教训（防"什么都召回"的假阳性）。
        {"qid": "h6",
         "s1_goal": "强渡青川河",
         "s1_review": "复盘：任务达成。教训：渡口选择保守，未利用上游浅滩。",
         "s2_goal": "夺控城市街区建筑群",
         "s2_query": ("h6", "巷战经验", "experience", "vector",
                      "城市 巷战 逐屋 经验"),
         "expect_keyword": None},  # None = 负控（不期召回）
    ]


def resolve_cross_session_gold(ctl: MemoryController,
                               expect_keyword) -> List[str]:
    """H 类 gold 解析：找场次1 复盘写入、含关键词的经验条目。"""
    if not expect_keyword:
        return []
    return [cid for cid in ctl.experiential.candidates()
            if expect_keyword in ctl.experiential.get(cid).content
            and ctl.experiential.get(cid).source.startswith("复盘:")]
