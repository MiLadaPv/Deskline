const fmtDur = (sec) => {
  sec = Math.max(0, Math.round(sec || 0));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
};

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return null;
  return res.json();
}

function setActiveTab(name) {
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === name);
  });
  document.querySelectorAll(".panel").forEach((p) => {
    p.classList.toggle("active", p.id === `panel-${name}`);
  });
}

function renderBars(byCategory, total) {
  const order = [
    ["productive", "Focus"],
    ["neutral", "Neutral"],
    ["distracting", "Drift"],
  ];
  const el = document.getElementById("catBars");
  el.innerHTML = order
    .map(([key, label]) => {
      const sec = byCategory[key] || 0;
      const pct = total ? Math.round((sec / total) * 100) : 0;
      return `<div class="cat-row">
        <span>${label}</span>
        <div class="bar ${key}"><span style="width:${pct}%"></span></div>
        <span>${pct}%</span>
      </div>`;
    })
    .join("");
  // trigger width animation
  requestAnimationFrame(() => {
    el.querySelectorAll(".bar > span").forEach((s) => {
      const w = s.style.width;
      s.style.width = "0";
      requestAnimationFrame(() => {
        s.style.width = w;
      });
    });
  });
}

function renderList(el, rows) {
  if (!rows.length) {
    el.innerHTML = `<li><span class="rank-name">No data yet</span><span class="rank-meta">Keep Deskline running</span></li>`;
    return;
  }
  el.innerHTML = rows
    .slice(0, 12)
    .map(
      (r) => `<li>
        <span class="rank-name">${escapeHtml(r.name)}</span>
        <span class="rank-meta">${fmtDur(r.sec)}</span>
      </li>`
    )
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function refreshSummary() {
  const summary = await api("/api/summary/today");
  document.getElementById("focusValue").textContent = `${summary.focus_pct}%`;
  document.getElementById("focusSub").textContent = `${fmtDur(summary.focus_sec)} of ${fmtDur(summary.total_sec)} tracked`;
  renderBars(summary.by_category, summary.total_sec);
  renderList(document.getElementById("topAppsToday"), summary.by_app);
  renderList(document.getElementById("appsList"), summary.by_app);
  renderList(document.getElementById("sitesList"), summary.by_site);
}

async function refreshStatus() {
  const st = await api("/api/status");
  const btn = document.getElementById("toggleBtn");
  btn.textContent = st.paused ? "Resume" : "Pause";
  btn.dataset.paused = st.paused ? "1" : "0";
  const app = st.current_app ? ` · ${st.current_app}` : "";
  document.getElementById("statusLine").textContent = st.paused
    ? "Paused"
    : `Recording${app}`;
}

async function refreshShots() {
  const rows = await api("/api/screenshots");
  const grid = document.getElementById("shotsGrid");
  if (!rows.length) {
    grid.innerHTML = `<p class="hint">No screenshots today.</p>`;
    return;
  }
  grid.innerHTML = rows
    .map(
      (r) => `<figure class="shot">
        <img src="${r.url}" alt="screenshot" loading="lazy" />
        <figcaption>${escapeHtml(r.taken_at)} · ${escapeHtml(r.reason)}</figcaption>
      </figure>`
    )
    .join("");
}

async function loadSettings() {
  const cfg = await api("/api/settings");
  const form = document.getElementById("settingsForm");
  form.screenshot_interval_sec.value = cfg.screenshot_interval_sec;
  form.screenshots_enabled.checked = !!cfg.screenshots_enabled;
  form.screenshot_on_app_switch.checked = !!cfg.screenshot_on_app_switch;
  form.open_dashboard_on_start.checked = !!cfg.open_dashboard_on_start;
  form.autostart.checked = !!cfg.autostart;
}

function wireUi() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      setActiveTab(tab.dataset.tab);
      if (tab.dataset.tab === "shots") refreshShots();
      if (tab.dataset.tab === "settings") loadSettings();
    });
  });

  document.getElementById("toggleBtn").addEventListener("click", async (e) => {
    const paused = e.currentTarget.dataset.paused === "1";
    await api(paused ? "/api/control/resume" : "/api/control/pause", { method: "POST" });
    await refreshStatus();
  });

  document.getElementById("settingsForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.currentTarget;
    const body = {
      screenshot_interval_sec: Number(form.screenshot_interval_sec.value),
      screenshots_enabled: form.screenshots_enabled.checked,
      screenshot_on_app_switch: form.screenshot_on_app_switch.checked,
      open_dashboard_on_start: form.open_dashboard_on_start.checked,
      autostart: form.autostart.checked,
    };
    await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
    alert("Settings saved");
  });

  document.getElementById("clearBtn").addEventListener("click", async () => {
    if (!confirm("Delete all local sessions and screenshot records?")) return;
    await api("/api/data/clear", { method: "POST" });
    await refreshSummary();
    await refreshShots();
  });
}

async function boot() {
  wireUi();
  await Promise.all([refreshSummary(), refreshStatus()]);
  setInterval(() => {
    refreshSummary().catch(() => {});
    refreshStatus().catch(() => {});
  }, 5000);
}

boot().catch((err) => {
  console.error(err);
  document.getElementById("focusSub").textContent = "Failed to load";
});
