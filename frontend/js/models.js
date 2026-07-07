/* Page 2 — Model Analytics: DS model outputs (dummy data via /api/models/*),
   month-range filter, CSV downloads, and the Signals & Alerts panel. */

let range = { start: null, end: null };

document.addEventListener("DOMContentLoaded", () => {
  chartDefaults();
  loadSummary();
  loadAll();
  initAlerts();

  document.getElementById("apply-range").addEventListener("click", () => {
    range.start = document.getElementById("m-start").value || null;
    range.end = document.getElementById("m-end").value || null;
    loadAll();
  });
  document.getElementById("clear-range").addEventListener("click", () => {
    document.getElementById("m-start").value = "";
    document.getElementById("m-end").value = "";
    range = { start: null, end: null };
    loadAll();
  });
});

function qs() {
  const p = new URLSearchParams();
  if (range.start) p.set("start", range.start);
  if (range.end) p.set("end", range.end);
  const s = p.toString();
  return s ? "?" + s : "";
}

function loadAll() {
  loadGrowth();
  loadDeltas();
  loadComparison();
  loadAllocations();
}

/* ── summary stat cards ─────────────────────────────────────────────────── */
async function loadSummary() {
  const box = document.getElementById("summary-row");
  try {
    const s = await API.get("/api/models/summary");
    box.innerHTML = `
      <div class="stat-tile"><div class="label">Projected portfolio CAGR</div>
        <div class="value num-up">${fmt.pct(s.projected_portfolio_cagr)}</div>
        <div class="sub">allocation-weighted, next 12M</div></div>
      <div class="stat-tile"><div class="label">Best-performing index</div>
        <div class="value">${fmt.esc(s.best_index_name)}</div>
        <div class="sub">${fmt.pct(s.best_index_cagr)} projected CAGR</div></div>
      <div class="stat-tile"><div class="label">Top allocation — ${fmt.esc(s.current_month)}</div>
        <div class="value">${fmt.pct(s.top_allocation_pct)}</div>
        <div class="sub">${fmt.esc(s.top_allocation_name)}</div></div>
      <div class="stat-tile"><div class="label">Model run</div>
        <div class="value" style="font-size:1.05rem">${fmt.date(s.generated_at)}</div>
        <div class="sub">dummy data — swap in backend/routers/models.py</div></div>`;
  } catch (err) {
    showError(box, err, "Could not load model summary.");
  }
}

/* ── 1. long-term growth + growth rate ──────────────────────────────────── */
async function loadGrowth() {
  try {
    const g = await API.get("/api/models/growth" + qs());
    const entries = Object.entries(g.series);
    multiLine("growth-chart", g.months, entries.map(([, s]) => ({ label: s.name, data: s.values, color: s.color })), { indexed: true });
    multiLine("growthrate-chart", g.months, entries.map(([, s]) => ({ label: s.name, data: s.growth_rate_yoy, color: s.color })), { unit: "%" });
    tableFrom("growth-table", ["Month", ...entries.map(([, s]) => s.name)],
      g.months.map((m, i) => [m, ...entries.map(([, s]) => fmt.num(s.values[i]))]), true);
  } catch (err) {
    showError(document.getElementById("growth-table"), err, "Growth data unavailable.");
  }
}

/* ── 2. combined delta ──────────────────────────────────────────────────── */
async function loadDeltas() {
  try {
    const d = await API.get("/api/models/deltas" + qs());
    const entries = Object.entries(d.series);
    multiLine("delta-chart", d.months, entries.map(([, s]) => ({ label: s.name, data: s.delta_pct, color: s.color })), { unit: "%", zeroLine: true });
    tableFrom("delta-table", ["Month", ...entries.map(([, s]) => s.name + " Δ%")],
      d.months.map((m, i) => [m, ...entries.map(([, s]) => fmt.pct(s.delta_pct[i], true))]), true);
  } catch (err) {
    showError(document.getElementById("delta-table"), err, "Delta data unavailable.");
  }
}

/* ── 3. index comparison ────────────────────────────────────────────────── */
async function loadComparison() {
  try {
    const { indices } = await API.get("/api/models/comparison");
    const labels = indices.map((i) => i.name);
    const colors = indices.map((i) => i.color);
    barChart("cmp-valuation", labels, [
      { label: "P/E", data: indices.map((i) => i.pe), colors },
      { label: "P/B", data: indices.map((i) => i.pb), colors: colors.map((c) => c + "88") },
    ]);
    barChart("cmp-cagr", labels, [
      { label: "CAGR 1Y %", data: indices.map((i) => i.cagr_1y), colors },
      { label: "Projected CAGR %", data: indices.map((i) => i.projected_cagr), colors: colors.map((c) => c + "88") },
    ]);
    tableFrom("cmp-table",
      ["Index", "P/E", "P/B", "MA 50d", "MA 200d", "CAGR 1Y", "CAGR 5Y", "Projected CAGR"],
      indices.map((i) => [
        `<span class="swatch" style="background:${i.color}"></span>${fmt.esc(i.name)}`,
        fmt.num(i.pe, 1), fmt.num(i.pb, 1), fmt.num(i.ma_50d), fmt.num(i.ma_200d),
        fmt.pct(i.cagr_1y, true), fmt.pct(i.cagr_5y, true), fmt.pct(i.projected_cagr, true),
      ]));
  } catch (err) {
    showError(document.getElementById("cmp-table"), err, "Comparison data unavailable.");
  }
}

/* ── 4. predicted allocations ───────────────────────────────────────────── */
async function loadAllocations() {
  try {
    const a = await API.get("/api/models/allocations" + qs());
    renderChart("alloc-chart", {
      type: "bar",
      data: {
        labels: a.months,
        datasets: a.indices.map((ix) => ({
          label: ix.name,
          data: a.rows.map((r) => r[ix.id]),
          backgroundColor: ix.color,
          borderColor: cssVar("--surface"), borderWidth: 2, /* 2px surface gap between segments */
          borderRadius: 3, borderSkipped: false,
        })),
      },
      options: {
        plugins: { tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${c.parsed.y}%` } } },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, max: 100, ticks: { callback: (v) => v + "%" }, border: { display: false } },
        },
      },
    });
    tableFrom("alloc-table", ["Month", ...a.indices.map((i) => i.name + " %")],
      a.months.map((m, k) => [m, ...a.indices.map((i) => fmt.num(a.rows[k][i.id], 1))]));
  } catch (err) {
    showError(document.getElementById("alloc-table"), err, "Allocation data unavailable.");
  }
}

/* ── chart + table builders ─────────────────────────────────────────────── */
function multiLine(canvasId, labels, series, opts = {}) {
  renderChart(canvasId, {
    type: "line",
    data: { labels, datasets: series.map((s) => ({ label: s.label, data: s.data, borderColor: s.color, tension: 0.25, spanGaps: true })) },
    options: {
      plugins: { legend: { position: "bottom" } },
      scales: {
        x: { ticks: sparseTicks(10), grid: { display: false } },
        y: {
          border: { display: false },
          ticks: opts.unit ? { callback: (v) => v + opts.unit } : {},
          ...(opts.zeroLine ? { grid: { color: (ctx) => (ctx.tick.value === 0 ? cssVar("--grid-zero") : cssVar("--grid-line")) } } : {}),
        },
      },
    },
  });
}

function barChart(canvasId, labels, groups) {
  renderChart(canvasId, {
    type: "bar",
    data: {
      labels,
      datasets: groups.map((g) => ({ label: g.label, data: g.data, backgroundColor: g.colors, borderRadius: 4, maxBarThickness: 42 })),
    },
    options: {
      plugins: { legend: { position: "bottom" } },
      scales: { x: { grid: { display: false } }, y: { border: { display: false } } },
    },
  });
}

function tableFrom(containerId, headers, rows, newestFirst = false) {
  const box = document.getElementById(containerId);
  const body = newestFirst ? [...rows].reverse() : rows;
  box.innerHTML = `
    <div class="table-wrap" style="max-height:320px;overflow-y:auto"><table>
      <thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
      <tbody>${body.map((r) => `<tr>${r.map((c, i) => `<td${i === 0 ? ' class="cell-name"' : ""}>${c}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`;
}

/* ── Signals & Alerts panel ─────────────────────────────────────────────── */
async function initAlerts() {
  const rulesBox = document.getElementById("rules-list");
  const histBox = document.getElementById("alert-history");

  const refresh = async () => {
    try {
      const { rules } = await API.get("/api/alerts/rules");
      rulesBox.innerHTML = rules.length
        ? rules.map((r) => `<span class="rule-chip">${fmt.esc(r.label)}<button title="Delete rule" data-id="${r.id}">✕</button></span>`).join("")
        : '<p style="color:var(--text-muted)">No rules yet — add one above.</p>';
      rulesBox.querySelectorAll("button[data-id]").forEach((b) => b.addEventListener("click", async () => {
        await API.del(`/api/alerts/rules/${b.dataset.id}`);
        refresh();
      }));
      const { history } = await API.get("/api/alerts/history");
      histBox.innerHTML = history.length
        ? history.slice(0, 12).map((h) => `<div class="bell-item"><b>${fmt.esc(h.label)}</b> — actual ${fmt.num(h.actual)}<time>${fmt.date(h.at)}</time></div>`).join("")
        : '<div class="bell-empty">Nothing triggered yet.</div>';
    } catch (err) {
      showError(rulesBox, err, "Alert service unavailable.");
    }
  };

  try {
    const meta = await API.get("/api/alerts/rules");
    document.getElementById("rule-index").innerHTML = meta.indices.map((i) => `<option value="${i.id}">${i.name}</option>`).join("");
    document.getElementById("rule-metric").innerHTML = meta.metrics.map((m) => `<option>${m}</option>`).join("");
  } catch { /* form selects stay empty; refresh() shows the error */ }

  document.getElementById("rule-add").addEventListener("click", async () => {
    const threshold = parseFloat(document.getElementById("rule-threshold").value);
    if (Number.isNaN(threshold)) return;
    await API.post("/api/alerts/rules", {
      index: document.getElementById("rule-index").value,
      metric: document.getElementById("rule-metric").value,
      operator: document.getElementById("rule-op").value,
      threshold,
    }).catch((e) => alert(e.message));
    document.getElementById("rule-threshold").value = "";
    await API.post("/api/alerts/evaluate").catch(() => {});
    refresh();
  });

  refresh();
}
