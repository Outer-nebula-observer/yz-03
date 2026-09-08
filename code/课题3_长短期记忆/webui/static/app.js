/* 赛题③ 记忆系统控制台 — 前端逻辑（原生 JS，无依赖） */
"use strict";

const $ = (id) => document.getElementById(id);
let curTab = "fact";

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

/* ---------------- 状态刷新 ---------------- */
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
    $("chip-session").textContent = "无场次";
    $("chip-session").classList.remove("on");
    $("chip-pressure").style.display = "none";
  }
  $("boundary-stats").textContent =
    `放行 ${s.boundary.allowed} · 拒绝 ${s.boundary.rejected}`;
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
}

/* ---------------- ③④ 检索装载 ---------------- */
async function retrieve() {
  const r = await api("/api/session/retrieve", { top_k: +$("topk").value || 3 });
  if (!r) return;
  renderHits(r.hits);
  renderContext(r.context, r.tokens, r.ratio, r.pressure);
  await refreshStatus();
}

/* ---------------- ⑤ 上下文 ---------------- */
async function loadContext() {
  const r = await api("/api/context");
  if (!r) return;
  renderContext(r.context, r.tokens, r.ratio, r.pressure);
}
function renderContext(ctx, tokens, ratio, pressure) {
  $("ctx-metrics").textContent =
    `tokens ${tokens} · ${Math.round(ratio * 100)}% · ${pressure ? "⚠ 预警（>70%）" : "未预警"}`;
  $("context").textContent = ctx || "（空）";
}

/* ---------------- 消息流 ---------------- */
async function pushMsg() {
  const msg = $("msg").value.trim();
  if (!msg) return;
  const r = await api("/api/session/push", { msg });
  if (!r) return;
  await loadContext();
  await refreshStatus();
}

/* ---------------- ⑥⑦ 复盘进化 ---------------- */
async function closeSession() {
  const r = await api("/api/session/close", { review_text: $("review").value });
  if (!r) return;
  renderReport(r.report);
  renderAudit(r.audit);
  await refreshMemory();
  await refreshStatus();
}
function renderReport(rep) {
  const stat = (n, label, zero = false) =>
    `<div class="stat${zero && n === 0 ? " z" : ""}"><b>${n}</b><span>${label}</span></div>`;
  let html = `<div class="row">${
    stat(rep.write, "写入")}${stat(rep.merge, "合并")}${
    stat(rep.forget, "遗忘")}${stat(rep.abstract, "抽象")}${
    stat(rep.skip_duplicate, "查重跳过", true)}</div>`;
  if (rep.abstracted_ids?.length) {
    html += `<div style="margin-top:8px;font-size:12px;color:var(--ink2)">
      抽象产物：${rep.abstracted_ids.join("、")}</div>`;
  }
  if (rep.merged_pairs?.length) {
    html += `<div style="margin-top:4px;font-size:12px;color:var(--ink2)">
      合并对：${rep.merged_pairs.map(([n, s]) => `${n} ← ${s.length}条`).join("；")}</div>`;
  }
  $("report").innerHTML = html;
}

/* ---------------- 检索结果 ---------------- */
function renderHits(hits) {
  if (!hits || !hits.length) {
    $("hits").innerHTML = `<div class="empty">（无命中——低于 min_score 的已被过滤）</div>`;
    return;
  }
  $("hits").innerHTML = hits.map(h => `
    <div class="hit">
      <div class="head">
        <span class="badge ${h.type}">${h.type === "fact" ? "事实" : "经验"}</span>
        <span class="badge route">${h.route}</span>
        <span class="score">${h.score.toFixed(3)}</span>
        <span style="font-size:11px;color:var(--ink2)">#${h.rank}</span>
      </div>
      <div class="content">${esc(h.content)}</div>
      <div class="prov">溯源: ${esc(h.provenance.source || "—")}
        · 场次 ${esc(h.provenance.session_id || "—")}
        · 召回 ${h.provenance.recall_count} 次</div>
    </div>`).join("");
}

/* ---------------- 记忆库浏览 ---------------- */
async function refreshMemory() {
  const r = await api(`/api/memory?type=${curTab}`);
  if (!r) return;
  if (!r.items.length) {
    $("memory-list").innerHTML = `<div class="empty">（空——可先"预置战例/教训"）</div>`;
    return;
  }
  $("memory-list").innerHTML = r.items.map(m => {
    const ret = Math.round(m.retention * 100);
    return `
    <div class="mem">
      <div class="head">
        <span>${esc(m.id)}</span>
        <span>重要性 ${m.importance} · 召回 ${m.recall_count}</span>
      </div>
      <div class="content">${esc(m.content)}</div>
      <div class="bar"><i style="width:${ret}%"></i></div>
      <div class="ops">留存 ${ret}% · 来源 ${esc(m.source || "—")}
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
  renderHits(r.hits);   // 复用中栏渲染
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
  await loadContext();
}

/* ---------------- 启动 ---------------- */
window.addEventListener("DOMContentLoaded", async () => {
  await seed();          // 首次进入自动预置演示数据，开箱即可玩
  await refreshAll();
});
