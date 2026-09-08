/* 赛题③ 记忆系统控制台 — 前端逻辑（原生 JS，无依赖）
   可视化主线：输入 → 运行过程 → 产出；短期（场生场灭）vs 长期（跨场次沉淀） */
"use strict";

const $ = (id) => document.getElementById(id);
let curTab = "fact";
let lastMemItems = [];      // 记忆库客户端排序缓存
let pastPlanIds = new Set(); // 已复盘场次 id（"往场沉淀"徽标判定）
let lastSessions = [];      // 场次历史缓存

/* ---------------- 基础请求 ---------------- */
async function api(path, body = null) {
  const opt = body === null
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) };
  try {
    const r = await fetch(path, opt);
    const j = await r.json();
    if (!r.ok) { showErr(j.error || r.statusText); return null; }
    showErr("");
    return j;
  } catch (e) { showErr("网络错误: " + e.message); return null; }
}
function showErr(msg) { $("err").textContent = msg || ""; }
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const fmtTime = (t) => new Date(t * 1000).toTimeString().slice(0, 8);
const fmtDur = (s) => s < 60 ? `${Math.round(s)} 秒` : `${Math.floor(s / 60)} 分 ${Math.round(s % 60)} 秒`;

/* ---------------- 状态刷新 + 七步进度 ---------------- */
async function refreshStatus() {
  const s = await api("/api/status");
  if (!s) return;
  $("chip-facts").textContent = `事实库 ${s.facts}`;
  $("chip-exps").textContent = `经验库 ${s.experiences}`;
  const sess = s.session;
  if (sess && sess.open) {
    $("chip-session").textContent = `场次 ${sess.plan_id} 进行中`;
    $("chip-session").classList.add("on");
    $("chip-pressure").style.display = sess.pressure ? "" : "none";
  } else {
    $("chip-session").textContent =
      s.sessions_closed ? `无场次（已复盘 ${s.sessions_closed} 场）` : "无场次";
    $("chip-session").classList.remove("on");
    $("chip-pressure").style.display = "none";
  }
  $("boundary-stats").textContent =
    `放行 ${s.boundary.allowed} · 拒绝 ${s.boundary.rejected}`;
  updateStepper(s.steps || {});
  // 无场次时禁用需要活动场次的按钮
  const open = !!(sess && sess.open);
  document.querySelectorAll("button[data-need-session]")
    .forEach(b => { b.disabled = !open; });
}
function updateStepper(steps) {
  const order = ["s1", "s2", "s3", "s4", "s5", "s6", "s7"];
  const anyDone = order.some(k => steps[k]);
  let nowMarked = false;
  document.querySelectorAll("#stepper .step").forEach(el => {
    const k = el.dataset.step;
    el.classList.remove("done", "now");
    if (steps[k]) el.classList.add("done");
    else if (anyDone && !nowMarked) { el.classList.add("now"); nowMarked = true; }
  });
  if (!anyDone) { // 无进度：第一步为待办高亮
    document.querySelector('#stepper .step[data-step="s1"]').classList.add("now");
  }
}

/* ---------------- ①② 开场 ---------------- */
function collectQueries() {
  return [...document.querySelectorAll(".query-row")]
    .map(row => ({
      intent: row.querySelector(".q-intent").value || "查询",
      target: row.querySelector(".q-target").value,
      route: row.querySelector(".q-route").value,
      query_text: row.querySelector(".q-text").value,
    }))
    .filter(q => q.query_text.trim() || q.intent.trim());
}
function addQueryRow() {
  const div = document.createElement("div");
  div.className = "query-row";
  div.innerHTML = `
    <span class="qtag">查询②</span>
    <input class="q-intent" placeholder="意图">
    <select class="q-target"><option value="fact">事实</option><option value="experience">经验</option></select>
    <select class="q-route"><option>vector</option><option>bm25</option><option>sql</option></select>
    <input class="q-text" placeholder="查询文本">`;
  $("query-list").appendChild(div);
}
async function startSession() {
  const body = {
    plan_id: $("plan-id").value.trim() || undefined,
    goal: $("goal").value.trim(),
    constraints: $("constraints").value.split("\n").map(s => s.trim()).filter(Boolean),
    queries: collectQueries(),
  };
  if (!body.goal) { showErr("请填写作战目标"); return; }
  const r = await api("/api/session/start", body);
  if (!r) return;
  await refreshStatus();
  await loadContext();
  await refreshEvents();
  await refreshSessions();
}

/* ---------------- ③④ 检索装载 ---------------- */
async function retrieve() {
  const r = await api("/api/session/retrieve", { top_k: +$("topk").value || 3 });
  if (!r) return;
  renderHits(r.hits);
  renderContext(r);
  renderWM(r.wm);
  renderReuseBanner(r.reused);
  await refreshStatus();
  await refreshEvents();
  await refreshSessions();
}
function renderReuseBanner(reused) {
  const el = $("reuse-banner");
  if (!reused || !reused.length) { el.style.display = "none"; return; }
  el.style.display = "";
  el.innerHTML = `⏪ <b>长期记忆跨场次生效</b>：本场召回了往场
    ${reused.map(x => `<b>${esc(x.plan_id)}</b> 沉淀的记忆 ×${x.count}`).join("、")}
    —— 上一场复盘的教训正在影响本场规划（多轮长期性）`;
}

/* ---------------- ⑤ 上下文 + 工作记忆构成 ---------------- */
async function loadContext() {
  const r = await api("/api/context");
  if (!r) return;
  renderContext(r);
  renderWM(r.wm);
}
function renderContext(r) {
  $("ctx-metrics").textContent =
    `tokens ${r.tokens} / 4000 · ${Math.round(r.ratio * 100)}% · ${r.pressure ? "⚠ 预警（>70%）" : "未预警"}`;
  $("context").textContent = r.context || "（空）";
}
function renderWM(wm) {
  const el = $("wm");
  if (!wm) {
    el.innerHTML = `<div class="empty">（无场次——开场后这里实时展示：目标 / 约束 / 装载记忆 / FIFO 消息 / 容量水位）</div>`;
    return;
  }
  // 容量水位条
  const pct = Math.min(100, Math.round(wm.ratio * 100));
  const warnAt = Math.round(wm.warning_ratio * 100);
  let g = `<div class="gauge">
    <div class="g-track"><i class="g-fill${wm.pressure ? " hot" : ""}" style="width:${pct}%"></i>
      <i class="g-mark" style="left:${warnAt}%" title="预警线 ${warnAt}%"></i></div>
    <div class="g-text">tokens <b>${wm.tokens}</b> / ${wm.capacity}（${pct}%）
      ${wm.pressure ? '<span class="hot-t">⚠ 已过预警线（70%）</span>' : "· 未预警"}
      <span class="dim">预警线 ${warnAt}% · flush 线 100%</span></div>
  </div>`;
  // 目标 / 约束（不可压缩）
  let h = g + `
    <div class="wm-sec"><span class="wm-k">🎯 目标</span><span class="lock">🔒 不可压缩</span>
      <div class="wm-v">${esc(wm.goal) || "—"}</div></div>`;
  if (wm.constraints?.length) {
    h += `<div class="wm-sec"><span class="wm-k">⛓ 约束</span><span class="lock">🔒 不可压缩</span>
      <div class="wm-v chips-inline">${wm.constraints.map(c =>
        `<span class="lockchip">${esc(c)}</span>`).join("")}</div></div>`;
  }
  // 查询列表（② 检索计划）
  if (wm.queries?.length) {
    h += `<div class="wm-sec"><span class="wm-k">📋 查询列表</span>
      <div class="wm-v">${wm.queries.map(q =>
        `<span class="qchip" title="${esc(q.query_text)}">${esc(q.q_id)} ${esc(q.intent)} · ${q.route}→${q.target === "fact" ? "事实" : "经验"}${q.answer_memory_ids.length ? ` · 命中${q.answer_memory_ids.length}` : ""}</span>`).join("")}</div></div>`;
  }
  // 已装载长期记忆（④ 的结果，逐条溯源）
  if (wm.loaded?.length) {
    h += `<div class="wm-sec"><span class="wm-k">📥 已装载长期记忆</span><span class="cnt">${wm.loaded.length} 条 · 逐条溯源</span>
      <div class="wm-v">${wm.loaded.map(m => `
        <div class="loaded-item">
          <span class="badge ${m.type}">${m.type === "fact" ? "事实" : "经验"}</span>
          <span class="li-c">${esc(m.content)}</span>
          ${m.session_id && pastPlanIds.has(m.session_id)
            ? `<span class="badge past">⏪ 往场 ${esc(m.session_id)}</span>` : ""}
        </div>`).join("")}</div></div>`;
  }
  // FIFO 消息流
  if (wm.fifo?.length) {
    h += `<div class="wm-sec"><span class="wm-k">📨 FIFO 消息流</span><span class="cnt">${wm.fifo.length} 条 · 最旧先出</span>
      <div class="wm-v fifo">${wm.fifo.map((m, i) => `
        <div class="fifo-item${i === wm.fifo.length - 1 ? " last" : ""}">${esc(m)}</div>`).join("")}</div></div>`;
  }
  // 归档（flush 产物）
  if (wm.archived?.length) {
    h += `<div class="wm-sec"><span class="wm-k">🗄 归档摘要</span><span class="cnt">${wm.archived.length} 批 · 复盘时并入沉淀</span>
      <div class="wm-v">${wm.archived.map(a =>
        `<div class="arch">…${esc(a.summary.slice(-90))}</div>`).join("")}</div></div>`;
  }
  el.innerHTML = h;
}

/* ---------------- 消息流 ---------------- */
async function pushMsg() {
  const msg = $("msg").value.trim();
  if (!msg) return;
  const r = await api("/api/session/push", { msg });
  if (!r) return;
  await loadContext();
  await refreshStatus();
  await refreshEvents();
}

/* ---------------- ⑥⑦ 复盘进化 ---------------- */
async function closeSession() {
  const r = await api("/api/session/close", { review_text: $("review").value });
  if (!r) return;
  renderReport(r.report);
  renderAudit(r.audit);
  await refreshMemory();
  await refreshSessions();
  await refreshStatus();
  await refreshEvents();
}
function renderReport(rep) {
  const stat = (n, label, zero = false) =>
    `<div class="stat${zero && n === 0 ? " z" : ""}"><b>${n}</b><span>${label}</span></div>`;
  let html = `<div class="row">${
    stat(rep.write, "写入")}${stat(rep.merge, "合并")}${
    stat(rep.forget, "遗忘")}${stat(rep.abstract, "抽象")}${
    stat(rep.skip_duplicate, "查重跳过", true)}</div>`;
  const produced = [...(rep.wrote_ids || []), ...(rep.abstracted_ids || [])];
  if (produced.length) {
    html += `<div class="rep-note">✍ 本场新沉淀：${produced.map(id =>
      `<span class="idchip">${esc(id)}</span>`).join("")}
      —— 已进入长期记忆，<b>后续场次可检索复用</b></div>`;
  }
  if (rep.merged_pairs?.length) {
    html += `<div class="rep-note">合并对：${rep.merged_pairs.map(([n, s]) =>
      `${esc(n)} ← ${s.length}条`).join("；")}</div>`;
  }
  $("report").innerHTML = html;
}

/* ---------------- 检索结果（含"往场沉淀"徽标） ---------------- */
function renderHits(hits) {
  if (!hits || !hits.length) {
    $("hits").innerHTML = `<div class="empty">（无命中——低于 min_score 的已被过滤）</div>`;
    return;
  }
  $("hits").innerHTML = hits.map(h => {
    const sid = h.provenance?.session_id || "";
    const past = sid && pastPlanIds.has(sid);
    return `
    <div class="hit${past ? " past" : ""}">
      <div class="head">
        <span class="badge ${h.type}">${h.type === "fact" ? "事实" : "经验"}</span>
        <span class="badge route">${h.route}</span>
        <span class="score">${h.score.toFixed(3)}</span>
        <span style="font-size:11px;color:var(--ink2)">#${h.rank}</span>
        ${past ? `<span class="badge past">⏪ 往场 ${esc(sid)} 沉淀</span>` : ""}
      </div>
      <div class="content">${esc(h.content)}</div>
      <div class="prov">溯源: ${esc(h.provenance.source || "—")}
        ${sid ? ` · 场次 ${esc(sid)}` : ""}
        · 召回 ${h.provenance.recall_count} 次</div>
    </div>`;
  }).join("");
}

/* ---------------- 记忆库浏览（客户端排序 + 来源场次徽标） ---------------- */
async function refreshMemory() {
  const r = await api(`/api/memory?type=${curTab}`);
  if (!r) return;
  lastMemItems = r.items;
  renderMemoryList();
}
function renderMemoryList() {
  const el = $("memory-list");
  if (!lastMemItems.length) {
    el.innerHTML = `<div class="empty">（空——可先"预置战例/教训"）</div>`;
    return;
  }
  const key = $("mem-sort").value;
  const items = [...lastMemItems].sort((a, b) =>
    key === "timestamp" ? b.timestamp - a.timestamp : (b[key] || 0) - (a[key] || 0));
  el.innerHTML = items.map(m => {
    const ret = Math.round(m.retention * 100);
    const sid = m.session_id || "";
    return `
    <div class="mem${sid && pastPlanIds.has(sid) ? " past" : ""}">
      <div class="head">
        <span>${esc(m.id)}</span>
        <span>重要性 ${m.importance} · 召回 ${m.recall_count}</span>
      </div>
      <div class="content">${esc(m.content)}</div>
      <div class="bar"><i style="width:${ret}%"></i></div>
      <div class="ops">留存 ${ret}% · 来源 ${esc(m.source || "—")}
        ${sid ? ` · <span class="src-sess">场次 ${esc(sid)}</span>` : ""}
        ${m.op_history.length ? " · 操作 " + m.op_history.join("→") : ""}
        ${m.merged_from.length ? " · 合并自 " + m.merged_from.length + " 条" : ""}</div>
    </div>`;
  }).join("");
}
function switchTab(btn) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  btn.classList.add("active");
  curTab = btn.dataset.type;
  refreshMemory();
}
async function doSearch() {
  const q = $("search-q").value.trim();
  if (!q) { refreshMemory(); return; }
  const r = await api("/api/search", {
    query: q, target: $("search-target").value,
    route: $("search-route").value, top_k: 8,
  });
  if (!r) return;
  renderHits(r.hits);   // 复用产出区渲染
  await refreshEvents();
  // 同步把目标库 tab 切到检索目标
  const want = $("search-target").value;
  document.querySelectorAll(".tab").forEach(t =>
    t.classList.toggle("active", t.dataset.type === want));
  curTab = want;
  refreshMemory();
}

/* ---------------- 边界审计 ---------------- */
function renderAudit(log) {
  if (!log || !log.length) {
    $("audit").innerHTML = `<div class="empty">（暂无决策——复盘进化后产生）</div>`;
    return;
  }
  $("audit").innerHTML = log.slice().reverse().map(a => `
    <div class="a-row${a.allowed ? "" : " rej"}">
      ${a.allowed ? "✓ 放行" : "✗ 拒绝"} · ${esc(a.layer)} · ${esc(a.kind)} · ${esc(a.reason)}
    </div>`).join("");
}
async function refreshAudit() {
  const r = await api("/api/audit");
  if (r) renderAudit(r.log);
}

/* ---------------- 运行事件流（输入 → 产出） ---------------- */
async function refreshEvents() {
  const r = await api("/api/events");
  if (!r) return;
  const evs = r.events;
  if (!evs.length) {
    $("events").innerHTML = `<div class="empty">（暂无事件——左侧任意操作都会在这里留下输入/产出记录）</div>`;
    return;
  }
  const kindMeta = {
    input: ["→ 输入", "in"], output: ["← 产出", "out"],
    info: ["· 系统", "sys"], divider: ["━━", "div"],
  };
  $("events").innerHTML = evs.map(e => {
    if (e.kind === "divider") {
      return `<div class="evt divider"><span class="d-line"></span>
        <b>${esc(e.title)}</b><span class="d-line"></span></div>`;
    }
    const [tag, cls] = kindMeta[e.kind] || ["·", "sys"];
    return `<div class="evt ${cls}">
      <span class="t">${fmtTime(e.t)}</span>
      <span class="tag ${cls}">${tag}</span>
      <span class="stepn">${esc(e.step)}</span>
      <div class="bd"><b>${esc(e.title)}</b>${e.detail ? `<div class="d">${esc(e.detail)}</div>` : ""}</div>
    </div>`;
  }).join("");
  const el = $("events");
  el.scrollTop = el.scrollHeight;
}

/* ---------------- 场次历史（多轮沉淀主线） ---------------- */
async function refreshSessions() {
  const r = await api("/api/sessions");
  if (!r) return;
  lastSessions = r.sessions;
  pastPlanIds = new Set(r.sessions.filter(s => s.closed_at).map(s => s.plan_id));
  const el = $("sessions");
  if (!r.sessions.length) {
    el.innerHTML = `<div class="empty">（暂无场次——开场后本场会出现在这里）</div>`;
    return;
  }
  el.innerHTML = r.sessions.map(s => {
    const rep = s.report;
    const badges = [];
    if (rep) {
      badges.push(`✍ 写入 ${rep.write}`, `🔀 合并 ${rep.merge}`,
                  `🗑 遗忘 ${rep.forget}`);
    } else {
      badges.push("● 进行中");
    }
    if (s.reused?.length) {
      badges.push(`⤴ 复用往场 ${s.reused.reduce((a, b) => a + b.count, 0)} 条`);
    }
    const produced = rep ? [...(rep.wrote_ids || []), ...(rep.abstracted_ids || [])] : [];
    return `
    <div class="sess${s.closed_at ? " closed" : " open"}">
      <div class="head"><b>${esc(s.plan_id)}</b>
        <span>${s.closed_at ? `✓ 已复盘 · ${fmtDur(s.duration_s)}` : "● 进行中"}</span></div>
      <div class="goal">${esc(s.goal) || "（无目标）"}</div>
      <div class="badges">${badges.map(b => `<span>${b}</span>`).join("")}</div>
      ${produced.length ? `<div class="prod">沉淀记忆：${produced.map(id =>
        `<span class="idchip">${esc(id)}</span>`).join("")}</div>` : ""}
      ${s.reused?.length ? `<div class="prod reuse">复用往场：${s.reused.map(x =>
        `<span class="idchip past">${esc(x.plan_id)} ×${x.count}</span>`).join("")}</div>` : ""}
    </div>`;
  }).join("");
}

/* ---------------- 演示数据 ---------------- */
async function seed() { await api("/api/seed", {}); await refreshAll(); }
async function resetAll() { await api("/api/reset", {}); location.reload(); }

/* ---------------- 工具 ---------------- */
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
async function refreshAll() {
  await refreshStatus();
  await refreshMemory();
  await refreshAudit();
  await refreshSessions();
  await refreshEvents();
  await loadContext();
}

/* ---------------- 场景库（自动填充样例 + 一键演示） ---------------- */
let curScene = null;

async function loadScenes() {
  const r = await api("/api/scenarios");
  if (!r) return;
  const sel = $("scene-select");
  sel.innerHTML = r.scenarios.map(s =>
    `<option value="${s.id}">${s.title}</option>`).join("");
  if (r.scenarios.length) fillScenario();   // 默认填充第一个
}

async function fillScenario(force = false, sceneId = null) {
  if (sceneId) $("scene-select").value = sceneId;
  const id = $("scene-select").value;
  if (!id) return;
  if (!force && curScene === id) return;    // 同场景不重复拉取
  const sc = await api("/api/scenario", { id });
  if (!sc) return;
  curScene = id;
  // —— 填充四张表单 ——
  $("plan-id").value = "";
  $("goal").value = sc.goal;
  $("constraints").value = sc.constraints.join("\n");
  $("msg").value = sc.messages.join("\n");
  $("review").value = sc.review;
  // 查询列表：先清空再按场景重建
  $("query-list").innerHTML = "";
  sc.queries.forEach(q => {
    addQueryRow();
    const rows = document.querySelectorAll(".query-row");
    const row = rows[rows.length - 1];
    row.querySelector(".q-intent").value = q.intent;
    row.querySelector(".q-target").value = q.target;
    row.querySelector(".q-route").value = q.route;
    row.querySelector(".q-text").value = q.query_text;
  });
  $("scene-desc").textContent = sc.desc;
}

/* ---------------- 自动演示 ---------------- */
/* 跑完一个场景的完整闭环（①→⑦）；opt.reset 控制是否先重置（连续两场时第二场不重置） */
async function runScenario(sceneId, opt = {}) {
  const { reset = true, planId = null } = opt;
  const st = await api("/api/status");
  if (!st) return;
  if (st.session && st.session.open) {
    await api("/api/session/close", { review_text: "（自动演示前的收尾）" });
  }
  if (reset) {
    await api("/api/reset", {});
    await api("/api/seed", {});
    await refreshAll();
  }
  await fillScenario(true, sceneId);
  if (planId) $("plan-id").value = planId;
  await sleep(500);   await startSession();   // ①②
  await sleep(700);   await retrieve();       // ③④⑤
  // 消息流逐条推入（视觉上像实时战报）
  const msgs = $("msg").value.split("\n").filter(x => x.trim());
  for (const m of msgs) {
    $("msg").value = m;
    await pushMsg();
    await sleep(450);
  }
  $("msg").value = msgs.join("\n");
  await sleep(600);   await closeSession();   // ⑥⑦
  await refreshAll();
}

async function autoDemo() {
  /* 自动演示：代点当前所选场景的 ①→⑦ 全部按钮（每个动作间停顿便于讲解）。 */
  await runScenario($("scene-select").value, { reset: true });
  $("scene-desc").textContent =
    "✅ 自动演示完成：检索命中 → 装载 → 复盘进化 全链路已跑通（结果见中/右栏）";
}

async function demoTwoSessions() {
  /* 连续两场演示（多轮长期性）：
     第一场 night_hill 复盘沉淀"电子压制/预备队"教训 → 第二场 night_hill_2
     开场检索应**召回第一场的沉淀**（右栏场次历史 + 复用横幅可见）。
     关键：两场之间不 reset——长期记忆必须跨场次存活。 */
  const btn = document.querySelector("button.chain");
  btn.disabled = true;
  $("scene-desc").textContent = "⏳ 第一场：夜间夺占 2 号高地（将沉淀夜战教训）…";
  await runScenario("night_hill", { reset: true, planId: "W1-夜袭首战" });
  $("scene-desc").textContent = "⏳ 第二场：再战 2 号高地（应召回第一场沉淀的教训）…";
  await sleep(800);
  await runScenario("night_hill_2", { reset: false, planId: "W2-再战" });
  // 最终把检索面板恢复为第二场的命中，便于讲解复用
  btn.disabled = false;
  const s2 = lastSessions.find(s => s.plan_id === "W2-再战");
  const nReuse = s2?.reused?.reduce((a, b) => a + b.count, 0) || 0;
  $("scene-desc").textContent = nReuse
    ? `✅ 两场演示完成：第二场召回了第一场沉淀的记忆 ×${nReuse}（见场次历史/复用横幅）—— 长期记忆跨场次生效`
    : "⚠ 两场演示完成，但第二场未检出往场复用（请检查第一场是否写入了教训）";
}

/* ---------------- 启动 ---------------- */
window.addEventListener("DOMContentLoaded", async () => {
  await seed();          // 首次进入自动预置演示数据（幂等），开箱即可玩
  await loadScenes();    // 场景库加载并默认填充第一场景
  await refreshAll();
});
