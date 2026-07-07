/* VittaLens — central API client, formatting helpers, shared chart defaults,
   and the navbar alert bell. Loaded on every page before page scripts. */

const API = {
  async get(path) {
    const res = await fetch(path, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
    return res.json();
  },
  async post(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
    return res.json();
  },
  async del(path) {
    const res = await fetch(path, { method: "DELETE" });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
    return res.json();
  },
};

/* ── formatting ─────────────────────────────────────────────────────────── */
const fmt = {
  num(v, dp = 2) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return Number(v).toLocaleString("en-IN", { maximumFractionDigits: dp, minimumFractionDigits: 0 });
  },
  price(v) { return v == null ? "—" : "₹" + fmt.num(v); },
  cr(v) {
    if (v == null) return "—";
    if (v >= 1e5) return "₹" + fmt.num(v / 1e5, 1) + " L Cr";
    return "₹" + fmt.num(v, 0) + " Cr";
  },
  pct(v, signed = false) {
    if (v == null) return "—";
    const s = signed && v > 0 ? "+" : "";
    return s + fmt.num(v) + "%";
  },
  pctCell(v) {
    if (v == null) return "—";
    const cls = v > 0 ? "num-up" : v < 0 ? "num-down" : "";
    const arrow = v > 0 ? "▲ " : v < 0 ? "▼ " : "";
    return `<span class="${cls}">${arrow}${fmt.pct(Math.abs(v))}</span>`;
  },
  date(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return Number.isNaN(d) ? "" : d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  },
  esc(s) {
    const div = document.createElement("div");
    div.textContent = s ?? "";
    return div.innerHTML;
  },
};

/* naive markdown → HTML for LLM output (bold, headers, bullets, code) */
function mdToHtml(md) {
  let h = fmt.esc(md || "");
  h = h.replace(/^### (.*)$/gm, "<h3>$1</h3>")
       .replace(/^## (.*)$/gm, "<h2>$1</h2>")
       .replace(/^# (.*)$/gm, "<h1>$1</h1>")
       .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
       .replace(/`([^`]+)`/g, "<code>$1</code>")
       .replace(/^[-*] (.*)$/gm, "<li>$1</li>")
       .replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
       .replace(/\n{2,}/g, "</p><p>");
  return `<div class="md"><p>${h}</p></div>`;
}

/* read a theme token from CSS */
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/* ── shared Chart.js defaults (recessive grid, theme ink, hover layer) ───── */
function chartDefaults() {
  Chart.defaults.color = cssVar("--axis-tick");
  Chart.defaults.borderColor = cssVar("--grid-line");
  Chart.defaults.font.family = cssVar("--font") || "Inter, sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.boxHeight = 10;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.tooltip.backgroundColor = cssVar("--tooltip-bg");
  Chart.defaults.plugins.tooltip.borderColor = cssVar("--border-strong");
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.titleColor = cssVar("--tooltip-text");
  Chart.defaults.plugins.tooltip.bodyColor = cssVar("--tooltip-text");
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.interaction = { mode: "index", intersect: false };
  Chart.defaults.elements.line.borderWidth = 2;
  Chart.defaults.elements.point.radius = 0;
  Chart.defaults.elements.point.hoverRadius = 4;
  Chart.defaults.animation.duration = 350;
}

/* destroy-and-recreate helper so range toggles don't leak chart instances */
const _charts = {};
function renderChart(canvasId, cfg) {
  if (_charts[canvasId]) _charts[canvasId].destroy();
  _charts[canvasId] = new Chart(document.getElementById(canvasId), cfg);
  return _charts[canvasId];
}

/* thin every Nth label for long category axes */
function sparseTicks(maxTicks = 10) {
  return { autoSkip: true, maxTicksLimit: maxTicks, maxRotation: 0 };
}

/* ── UI helpers ─────────────────────────────────────────────────────────── */
function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}
function showError(container, err, note) {
  container.innerHTML = `<div class="error-box">⚠ ${fmt.esc(note || "Failed to load data.")} <small>${fmt.esc(err?.message || "")}</small></div>`;
}
function skeletonRows(n, container) {
  container.innerHTML = Array.from({ length: n }, () => '<div class="skeleton skeleton-row"></div>').join("");
}
function sourceBadge(source) {
  return source === "synthetic"
    ? '<span class="badge badge-synth" title="Live source unreachable — showing deterministic demo data">demo data</span>'
    : '<span class="badge badge-live">live</span>';
}

/* ── navbar: active link + alert bell ───────────────────────────────────── */
function initNavbar() {
  const page = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a").forEach((a) => {
    if (a.getAttribute("href") === page) a.classList.add("active");
  });

  const bell = document.getElementById("bell-btn");
  const dropdown = document.getElementById("bell-dropdown");
  const badge = document.getElementById("bell-badge");
  if (!bell) return;

  bell.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.classList.toggle("open");
    if (dropdown.classList.contains("open")) badge.style.display = "none";
  });
  document.addEventListener("click", () => dropdown.classList.remove("open"));

  API.post("/api/alerts/evaluate").then(({ fired, history }) => {
    if (fired.length) {
      badge.textContent = fired.length;
      badge.style.display = "flex";
    }
    dropdown.innerHTML = history.length
      ? history.map((h) => `<div class="bell-item"><b>${fmt.esc(h.label)}</b> — actual ${fmt.num(h.actual)}<time>${fmt.date(h.at)}</time></div>`).join("")
      : '<div class="bell-empty">No alerts yet. Define rules on the Model Analytics page.</div>';
  }).catch(() => {
    dropdown.innerHTML = '<div class="bell-empty">Alert service unavailable.</div>';
  });
}
document.addEventListener("DOMContentLoaded", initNavbar);
