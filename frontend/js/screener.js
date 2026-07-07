/* Page 1 — Index Screener. Three drill-down levels routed by URL hash:
     #/                    Level 1: indices overview table
     #/index/<id>          Level 2: constituents + index charts
     #/company/<symbol>    Level 3: company deep dive
*/
const view = document.getElementById("view");
let indicesCache = null;

/* ── router ─────────────────────────────────────────────────────────────── */
function route() {
  const hash = location.hash.replace(/^#\/?/, "");
  const [kind, id] = hash.split("/");
  if (kind === "index" && id) return renderIndexDetail(id);
  if (kind === "company" && id) return renderCompany(decodeURIComponent(id));
  return renderOverview();
}
window.addEventListener("hashchange", route);
document.addEventListener("DOMContentLoaded", () => { chartDefaults(); route(); });

/* ── Level 1: overview ──────────────────────────────────────────────────── */
async function renderOverview() {
  view.innerHTML = `
    <h1>Index Screener</h1>
    <p class="subtitle">Five tracked ETF indices — click a row to drill into constituents and valuation charts.</p>
    <div id="ov-table"><div class="skeleton skeleton-row"></div>${'<div class="skeleton skeleton-row"></div>'.repeat(5)}</div>`;
  const box = document.getElementById("ov-table");
  try {
    const { indices } = indicesCache ? { indices: indicesCache } : await API.get("/api/indices");
    indicesCache = indices;
    box.innerHTML = `
      <div class="table-wrap"><table>
        <thead><tr>
          <th>Index</th><th class="spark-cell">Trend (60d)</th><th>Price</th><th>Day</th>
          <th>Mkt Cap</th><th>52W High</th><th>52W Low</th><th>P/E</th><th>P/B</th>
          <th>Div Yield</th><th>CAGR 1Y</th><th>CAGR 5Y</th><th>CAGR 10Y</th>
        </tr></thead>
        <tbody>${indices.map((ix) => `
          <tr class="clickable" onclick="location.hash='#/index/${ix.id}'">
            <td class="cell-name"><span class="swatch" style="background:${ix.color}"></span>${fmt.esc(ix.name)}
              <span class="cell-sub">${ix.constituent_count} constituents ${sourceBadge(ix.source)}</span></td>
            <td class="spark-cell"><canvas id="spark-${ix.id}" height="34"></canvas></td>
            <td>${fmt.price(ix.price)}</td>
            <td>${fmt.pctCell(ix.day_change_pct)}</td>
            <td>${fmt.cr(ix.market_cap_cr)}</td>
            <td>${fmt.num(ix.high_52w)}</td>
            <td>${fmt.num(ix.low_52w)}</td>
            <td>${fmt.num(ix.pe, 1)}</td>
            <td>${fmt.num(ix.pb, 1)}</td>
            <td>${fmt.pct(ix.div_yield)}</td>
            <td>${fmt.pctCell(ix.cagr_1y)}</td>
            <td>${fmt.pctCell(ix.cagr_5y)}</td>
            <td>${fmt.pctCell(ix.cagr_10y)}</td>
          </tr>`).join("")}
        </tbody>
      </table></div>`;
    indices.forEach((ix) => sparkline(`spark-${ix.id}`, ix.sparkline, ix.color));
  } catch (err) {
    showError(box, err, "Could not load index overview.");
  }
}

function sparkline(canvasId, data, color) {
  renderChart(canvasId, {
    type: "line",
    data: { labels: data.map((_, i) => i), datasets: [{ data, borderColor: color, borderWidth: 1.5, fill: false, tension: 0.3 }] },
    options: {
      responsive: false, animation: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
    },
  });
}

/* ── Level 2: index detail ──────────────────────────────────────────────── */
let constituents = [];
let sortState = { key: "market_cap_cr", dir: -1 };

async function renderIndexDetail(indexId) {
  view.innerHTML = `
    <div class="crumbs"><a href="#/">Screener</a><span>›</span><span id="crumb-name">…</span></div>
    <div id="idx-head"><div class="skeleton skeleton-row"></div></div>
    <div class="card section">
      <div class="toolbar">
        <h2 style="margin:0">Price &amp; Valuation</h2><span class="spacer"></span>
        <div class="range-toggle" id="range-toggle">
          ${["1M", "6M", "1Y", "5Y"].map((r) => `<button data-range="${r}" class="${r === "1Y" ? "active" : ""}">${r}</button>`).join("")}
        </div>
      </div>
      <div class="grid grid-2">
        <div><h2>Price history</h2><div class="chart-box short"><canvas id="idx-price"></canvas></div></div>
        <div><h2>P/E ratio trend <small style="color:var(--text-muted)">(proxy)</small></h2><div class="chart-box short"><canvas id="idx-pe"></canvas></div></div>
      </div>
    </div>
    <div class="card section">
      <div class="toolbar">
        <h2 style="margin:0">Constituents</h2><span class="spacer"></span>
        <input type="text" id="co-filter" placeholder="Filter companies…">
      </div>
      <div id="co-table"><div class="spinner"></div></div>
    </div>`;

  try {
    const idx = await API.get(`/api/indices/${indexId}`);
    document.getElementById("crumb-name").textContent = idx.name;
    document.getElementById("idx-head").innerHTML = `
      <h1><span class="swatch" style="background:${idx.color}"></span>${fmt.esc(idx.name)} ${sourceBadge(idx.source)}</h1>
      <p class="subtitle">${fmt.esc(idx.description)}</p>
      <div class="stat-row">
        ${statTile("Price", fmt.price(idx.price), fmt.pctCell(idx.day_change_pct) + " today")}
        ${statTile("P/E · P/B", `${fmt.num(idx.pe, 1)} · ${fmt.num(idx.pb, 1)}`, "Dividend yield " + fmt.pct(idx.div_yield))}
        ${statTile("52-week range", `${fmt.num(idx.low_52w)} – ${fmt.num(idx.high_52w)}`, "")}
        ${statTile("CAGR 1Y / 5Y / 10Y", [idx.cagr_1y, idx.cagr_5y, idx.cagr_10y].map((v) => fmt.pct(v)).join(" / "), "")}
      </div>`;
  } catch (err) {
    showError(document.getElementById("idx-head"), err, "Could not load index.");
    return;
  }

  const loadCharts = async (range) => {
    try {
      const h = await API.get(`/api/indices/${indexId}/history?range=${range}`);
      lineChart("idx-price", h.dates, [{ label: h.name, data: h.close, color: h.color, fill: true }]);
      lineChart("idx-pe", h.dates, [{ label: "P/E", data: h.pe, color: h.color }]);
    } catch { /* charts stay blank; table below still works */ }
  };
  document.getElementById("range-toggle").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-range]");
    if (!btn) return;
    document.querySelectorAll("#range-toggle button").forEach((b) => b.classList.toggle("active", b === btn));
    loadCharts(btn.dataset.range);
  });
  loadCharts("1Y");

  try {
    const { companies } = await API.get(`/api/indices/${indexId}/constituents`);
    constituents = companies;
    sortState = { key: "market_cap_cr", dir: -1 };
    drawConstituents();
    document.getElementById("co-filter").addEventListener("input", drawConstituents);
  } catch (err) {
    showError(document.getElementById("co-table"), err, "Could not load constituents.");
  }
}

function statTile(label, value, sub) {
  return `<div class="stat-tile"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`;
}

const CO_COLS = [
  ["symbol", "Company"], ["price", "Price"], ["day_change_pct", "Day %"],
  ["market_cap_cr", "Mkt Cap"], ["pe", "P/E"], ["pb", "P/B"],
  ["div_yield", "Div %"], ["roe", "ROE %"], ["high_52w", "52W H"], ["low_52w", "52W L"],
];

function drawConstituents() {
  const box = document.getElementById("co-table");
  const q = (document.getElementById("co-filter")?.value || "").toLowerCase();
  let rows = constituents.filter((c) => !q || c.symbol.toLowerCase().includes(q) || (c.name || "").toLowerCase().includes(q));
  rows.sort((a, b) => {
    const va = a[sortState.key], vb = b[sortState.key];
    if (va == null) return 1;
    if (vb == null) return -1;
    return (va < vb ? -1 : va > vb ? 1 : 0) * sortState.dir;
  });
  box.innerHTML = `
    <div class="table-wrap"><table>
      <thead><tr>${CO_COLS.map(([k, label]) =>
        `<th class="sortable" data-key="${k}">${label}${sortState.key === k ? ` <span class="arrow">${sortState.dir > 0 ? "↑" : "↓"}</span>` : ""}</th>`).join("")}
      </tr></thead>
      <tbody>${rows.map((c) => `
        <tr class="clickable" onclick="location.hash='#/company/${encodeURIComponent(c.symbol)}'">
          <td class="cell-name">${fmt.esc(c.symbol)}<span class="cell-sub">${fmt.esc(c.name || "")}</span></td>
          <td>${fmt.price(c.price)}</td>
          <td>${fmt.pctCell(c.day_change_pct)}</td>
          <td>${fmt.cr(c.market_cap_cr)}</td>
          <td>${fmt.num(c.pe, 1)}</td>
          <td>${fmt.num(c.pb, 1)}</td>
          <td>${fmt.pct(c.div_yield)}</td>
          <td>${fmt.num(c.roe, 1)}</td>
          <td>${fmt.num(c.high_52w)}</td>
          <td>${fmt.num(c.low_52w)}</td>
        </tr>`).join("")}
      </tbody>
    </table></div>`;
  box.querySelectorAll("th.sortable").forEach((th) => th.addEventListener("click", () => {
    const key = th.dataset.key;
    sortState = { key, dir: sortState.key === key ? -sortState.dir : -1 };
    drawConstituents();
  }));
}

/* ── Level 3: company deep dive ─────────────────────────────────────────── */
async function renderCompany(symbol) {
  view.innerHTML = `
    <div class="crumbs"><a href="#/">Screener</a><span>›</span><a href="#" id="crumb-idx"></a><span id="crumb-sep" style="display:none">›</span><span>${fmt.esc(symbol)}</span></div>
    <div id="co-head"><div class="skeleton skeleton-row"></div></div>
    <div class="card section">
      <div class="toolbar">
        <h2 style="margin:0">Price &amp; volume</h2><span class="spacer"></span>
        <div class="range-toggle" id="co-range">
          ${["1M", "6M", "1Y", "5Y"].map((r) => `<button data-range="${r}" class="${r === "1Y" ? "active" : ""}">${r}</button>`).join("")}
        </div>
      </div>
      <div class="chart-box"><canvas id="co-price"></canvas></div>
      <div class="chart-box short" style="margin-top:1rem"><canvas id="co-vol"></canvas></div>
    </div>
    <div class="grid grid-2 section">
      <div class="card"><h2>✦ AI investment brief</h2><div id="co-brief"><div class="spinner"></div></div></div>
      <div class="card"><h2>Latest news</h2><div id="co-news"><div class="spinner"></div></div></div>
    </div>`;

  try {
    const p = await API.get(`/api/companies/${encodeURIComponent(symbol)}`);
    const q = p.quote, m = p.metrics;
    if (p.index) {
      const link = document.getElementById("crumb-idx");
      link.textContent = p.index;
      link.href = `#/index/${p.index}`;
      document.getElementById("crumb-sep").style.display = "";
    }
    document.getElementById("co-head").innerHTML = `
      <h1>${fmt.esc(p.name)} <small style="color:var(--text-muted)">${fmt.esc(symbol)}</small> ${sourceBadge(p.source)}</h1>
      <p class="subtitle">${fmt.esc([p.sector, p.industry].filter(Boolean).join(" · "))}</p>
      <div class="stat-row">
        ${statTile("Price", fmt.price(q.price), fmt.pctCell(q.day_change_pct) + " today")}
        ${statTile("Market cap", fmt.cr(q.market_cap_cr), "52W " + fmt.num(q.low_52w) + " – " + fmt.num(q.high_52w))}
        ${statTile("P/E · P/B", `${fmt.num(q.pe, 1)} · ${fmt.num(q.pb, 1)}`, "Div yield " + fmt.pct(q.div_yield))}
        ${statTile("ROE", fmt.pct(q.roe), "EPS ₹" + fmt.num(m.eps, 1))}
        ${statTile("Margins", fmt.pct(m.profit_margin_pct), "Rev growth " + fmt.pct(m.revenue_growth_pct, true))}
        ${statTile("D/E · Beta", `${fmt.num(m.debt_to_equity, 1)} · ${fmt.num(m.beta, 2)}`, "Avg vol " + fmt.num(m.avg_volume, 0))}
      </div>
      ${p.summary ? `<div class="card section"><h2>About</h2><p style="color:var(--text-secondary)">${fmt.esc(p.summary)}</p></div>` : ""}`;
  } catch (err) {
    showError(document.getElementById("co-head"), err, "Could not load company.");
    return;
  }

  const loadCharts = async (range) => {
    try {
      const h = await API.get(`/api/companies/${encodeURIComponent(symbol)}/history?range=${range}`);
      const lineColor = cssVar("--series-nifty50");
      lineChart("co-price", h.dates, [{ label: symbol, data: h.close, color: lineColor, fill: true }]);
      renderChart("co-vol", {
        type: "bar",
        data: { labels: h.dates, datasets: [{ label: "Volume", data: h.volume, backgroundColor: lineColor + "73", borderRadius: 2 }] },
        options: { plugins: { legend: { display: false } }, scales: { x: { ticks: sparseTicks(8), grid: { display: false } }, y: { border: { display: false } } } },
      });
    } catch { /* leave charts empty */ }
  };
  document.getElementById("co-range").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-range]");
    if (!btn) return;
    document.querySelectorAll("#co-range button").forEach((b) => b.classList.toggle("active", b === btn));
    loadCharts(btn.dataset.range);
  });
  loadCharts("1Y");

  API.get(`/api/companies/${encodeURIComponent(symbol)}/news`).then(({ items }) => {
    const box = document.getElementById("co-news");
    box.innerHTML = items.length
      ? items.slice(0, 8).map((n) => `
          <div style="padding:.55rem 0;border-bottom:1px solid var(--border)">
            <a href="${fmt.esc(n.link)}" target="_blank" rel="noopener"><b>${fmt.esc(n.title)}</b></a>
            <div class="news-meta"><span>${fmt.esc(n.source || "")}</span><span>${fmt.date(n.published)}</span></div>
          </div>`).join("")
      : '<p style="color:var(--text-muted)">No recent news found (network may be unavailable).</p>';
  }).catch((err) => showError(document.getElementById("co-news"), err, "News unavailable."));

  API.get(`/api/companies/${encodeURIComponent(symbol)}/brief`).then((b) => {
    document.getElementById("co-brief").innerHTML =
      mdToHtml(b.brief_md) + `<div class="news-meta" style="margin-top:.5rem"><span>engine: ${fmt.esc(b.llm)}</span></div>`;
  }).catch((err) => showError(document.getElementById("co-brief"), err, "Brief unavailable."));
}

/* shared line chart builder */
function lineChart(canvasId, labels, series) {
  renderChart(canvasId, {
    type: "line",
    data: {
      labels,
      datasets: series.map((s) => ({
        label: s.label, data: s.data, borderColor: s.color, tension: 0.25,
        fill: s.fill || false, backgroundColor: s.fill ? s.color + "22" : undefined,
      })),
    },
    options: {
      plugins: { legend: { display: series.length > 1 } },
      scales: { x: { ticks: sparseTicks(9), grid: { display: false } }, y: { border: { display: false } } },
    },
  });
}
