# -*- coding: utf-8 -*-
"""
examples.demo_pipeline — 七步闭环离线演示（组会/答辩可放屏）
==============================================================
跑法（在 课题3_长短期记忆/ 目录下）：
    python examples/demo_pipeline.py

演示内容（两场闭环，验证"越用越强"）：
  场次 1：夜间夺占 2 号高地
    ① 建槽位（目标+约束） → ② 查询列表 → ③ 混合检索 → ④ 装载
    → ⑤ Mock 规划输出 → ⑥ Mock AFSIM 反馈 → ⑦ 复盘进化（写入/合并/遗忘/抽象）
  场次 2：夜间进攻 3 号高地
    展示第一场沉淀的"夜战教训"被召回并影响规划上下文（记忆复用）。

接智戎真链路：把 pipeline.py 中 TODO-INTEGRATION 两处换成真实调用即可，
本演示的数据结构（SessionResult）就是交付日志的格式。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memsys import (MemoryPipeline, QueryItem)


def dump(title: str, obj) -> None:
    print(f"\n----- {title} -----")
    if isinstance(obj, dict):
        for k, v in obj.items():
            print(f"  {k}: {v}")
    else:
        print(f"  {obj}")


def main() -> None:
    pipe = MemoryPipeline()  # 全 Mock：LLM/Embedding/反馈均离线

    # 预置少量"历史记忆"（模拟此前场次已沉淀的知识）
    from memsys import MemoryType, new_entry
    ctl = pipe.controller
    ctl.factual.add(new_entry(
        MemoryType.FACT, "红方 T-90 主战坦克：最大速度 60km/h，主炮 125mm。",
        attrs={"装备": "T-90", "阵营": "红方"}))
    ctl.factual.add(new_entry(
        MemoryType.FACT,
        "2 号高地海拔 320 米，北坡缓南坡陡，仅东侧可装甲通行。",
        attrs={"地点": "2号高地"}))
    ctl.factual.add(new_entry(
        MemoryType.FACT,
        "3 号高地海拔 210 米，地形开阔，有两条机械化通路。",
        attrs={"地点": "3号高地"}))
    ctl.experiential.add(new_entry(
        MemoryType.EXPERIENCE, "教训：夜间行军未派先遣侦察，先头在隘口遭伏击。",
        importance=2.0))

    # ================= 场次 1 =================
    print("=" * 64)
    print("场次 P001：夜间夺占 2 号高地（七步闭环）")
    print("=" * 64)
    queries = [
        QueryItem(q_id="P001-q1", intent="查目标区域地形与通行条件",
                  target="fact", route="vector", query_text="2 号高地 地形 装甲 通行"),
        QueryItem(q_id="P001-q2", intent="召回夜间作战历史教训",
                  target="experience", route="bm25", query_text="夜战 侦察 伏击 教训"),
    ]
    r1 = pipe.run_session(
        "P001", "夜间夺占 2 号高地",
        constraints=["禁止越境", "限时 4 小时", "优先保存装甲力量"],
        queries=queries,
        messages=["指挥所：红方 3 营于东侧集结完毕",
                  "侦察分队：高地南坡发现两处反坦克火力点",
                  "气象：今夜 02:00 起降雨，能见度 < 300 米"],
        review_text=("复盘：任务部分达成。教训：夜间突袭未前置电子压制，"
                     "接敌后通信被干扰。经验：突破口形成后预备队投入应提前 10 分钟。"),
        top_k=3)

    dump("③ 检索命中（带溯源）", r1.retrieved)
    dump("⑤ 规划输出（Mock）", r1.plan_output[:200] + "…")
    dump("⑦ 进化报告", r1.evolution.summary() if r1.evolution else {})
    dump("库规模", {"事实库": ctl.factual.stats()["count"],
                    "经验库": ctl.experiential.stats()["count"]})

    # ================= 场次 2 =================
    print("\n" + "=" * 64)
    print("场次 P002：夜间进攻 3 号高地（验证第一场沉淀可复用）")
    print("=" * 64)
    r2 = pipe.run_session(
        "P002", "夜间进攻 3 号高地",
        constraints=["禁止越境"],
        messages=["指挥所：红方 2 营就位"],
        review_text="复盘：任务达成。经验：电子压制前置后接敌通信保持良好。",
        top_k=3)
    dump("③ 检索命中（含上一场新沉淀）", r2.retrieved)
    dump("⑦ 进化报告", r2.evolution.summary() if r2.evolution else {})
    dump("两场检索统计", {"P001": r1.session_stats, "P002": r2.session_stats})

    print("\n演示完成：七步闭环离线跑通。"
          "（接真模型：get_llm('openai', ...)；接智戎：替换 pipeline ⑤⑥ 两步）")


if __name__ == "__main__":
    main()
