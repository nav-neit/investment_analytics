/* Page 3 — Market News: LLM digest banner, section filter tabs, card grid. */

let allItems = [];
let activeSection = "all";

document.addEventListener("DOMContentLoaded", () => {
  loadDigest();
  loadNews();
  document.getElementById("refresh-btn").addEventListener("click", () => {
    loadDigest(true);
    loadNews(true);
  });
});

async function loadDigest(force = false) {
  const box = document.getElementById("digest-text");
  box.innerHTML = '<div class="skeleton" style="height:3.2em"></div>';
  try {
    const d = await API.get("/api/news/digest" + (force ? "?refresh=true" : ""));
    box.textContent = d.digest;
  } catch {
    box.textContent = "Digest unavailable — check network connectivity.";
  }
}

async function loadNews(force = false) {
  const grid = document.getElementById("news-grid");
  grid.innerHTML = '<div class="spinner" style="grid-column:1/-1"></div>';
  try {
    const data = await API.get("/api/news" + (force ? "?refresh=true" : ""));
    allItems = data.items;
    buildTabs(data.sections);
    drawCards();
  } catch (err) {
    showError(grid, err, "Could not load news. RSS sources may be unreachable.");
  }
}

function buildTabs(sections) {
  const tabs = document.getElementById("section-tabs");
  const entries = [["all", "All"], ...Object.entries(sections)];
  tabs.innerHTML = entries.map(([id, label]) =>
    `<button data-s="${id}" class="${id === activeSection ? "active" : ""}">${label}</button>`).join("");
  tabs.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    activeSection = b.dataset.s;
    tabs.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
    drawCards();
  }));
}

function drawCards() {
  const grid = document.getElementById("news-grid");
  const items = activeSection === "all" ? allItems : allItems.filter((i) => i.section === activeSection);
  grid.innerHTML = items.length
    ? items.map((n) => `
        <div class="card news-card">
          <span class="badge badge-tag" style="align-self:flex-start">${fmt.esc(n.section_label)}</span>
          <h3><a href="${fmt.esc(n.link)}" target="_blank" rel="noopener">${fmt.esc(n.title)}</a></h3>
          <p>${fmt.esc(n.summary)}</p>
          <div class="news-meta"><span>${fmt.esc(n.source || "")}</span><span>·</span><span>${fmt.date(n.published)}</span></div>
        </div>`).join("")
    : '<p style="color:var(--text-muted);grid-column:1/-1">No items in this section right now.</p>';
}
