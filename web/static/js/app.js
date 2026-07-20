const fmtDur = (sec) => {
  sec = Math.max(0, Math.round(sec || 0));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h > 0) return `${h}ч ${m}м`;
  return `${m}м`;
};

const fmtBytes = (n) => {
  n = Math.max(0, Number(n) || 0);
  if (n < 1024) return `${n} Б`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} КБ`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} МБ`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} ГБ`;
};

let lastSummaryKey = "";
let lastStatusKey = "";
let lastBarsKey = "";

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    location.href = "/login";
    throw new Error("auth required");
  }
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

function listSignature(rows) {
  return (rows || [])
    .slice(0, 15)
    .map((r) => `${r.name}|${Math.floor((r.sec || 0) / 60)}|${r.icon_url || ""}`)
    .join(";");
}

function listStructure(rows) {
  return (rows || [])
    .slice(0, 15)
    .map((r) => `${r.name}|${r.icon_url || ""}`)
    .join(";");
}

function renderBars(byCategory, total, { animate = true } = {}) {
  const order = [
    ["productive", "Фокус"],
    ["neutral", "Нейтрально"],
    ["distracting", "Отвлечения"],
  ];
  const pcts = order.map(([key]) => {
    const sec = byCategory[key] || 0;
    return total ? Math.round((sec / total) * 100) : 0;
  });
  const barsKey = pcts.join(",");
  if (barsKey === lastBarsKey) return;
  const shouldAnimate = animate && lastBarsKey !== "";
  lastBarsKey = barsKey;

  const el = document.getElementById("catBars");
  el.innerHTML = order
    .map(([key, label], i) => {
      const pct = pcts[i];
      return `<div class="cat-row">
        <span>${label}</span>
        <div class="bar ${key}"><span style="width:${pct}%"></span></div>
        <span>${pct}%</span>
      </div>`;
    })
    .join("");

  if (!shouldAnimate) return;
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

function renderList(el, rows, emptyText) {
  const sliced = (rows || []).slice(0, 15);
  const signature = sliced.length
    ? listSignature(sliced)
    : `empty:${emptyText || "Пока нет данных"}`;
  if (el.dataset.sig === signature) return;

  const structure = sliced.length ? listStructure(sliced) : `empty`;
  if (el.dataset.struct === structure && sliced.length) {
    const metas = el.querySelectorAll(".rank-meta");
    sliced.forEach((r, i) => {
      if (metas[i]) metas[i].textContent = fmtDur(r.sec);
    });
    el.dataset.sig = signature;
    return;
  }

  el.dataset.struct = structure;
  el.dataset.sig = signature;

  if (!sliced.length) {
    el.innerHTML = `<li><span class="rank-icon" aria-hidden="true">•</span><span class="rank-name">${emptyText || "Пока нет данных"}</span><span class="rank-meta">Оставьте Deskline включённым</span></li>`;
    return;
  }
  el.innerHTML = sliced
    .map((r) => {
      const icon = r.icon_url
        ? `<img class="rank-icon-img" src="${escapeHtml(r.icon_url)}" alt="" width="28" height="28" decoding="async" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'rank-icon',textContent:'•'}))" />`
        : `<span class="rank-icon" aria-hidden="true">•</span>`;
      return `<li>
        ${icon}
        <span class="rank-name">${escapeHtml(r.name)}</span>
        <span class="rank-meta">${fmtDur(r.sec)}</span>
      </li>`;
    })
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function updateStorageHint(cfg) {
  const el = document.getElementById("shotsStorageHint");
  if (!el) return;
  const storage = cfg.screenshots_storage || {};
  const path = cfg.screenshots_path || storage.path || "локальная папка Deskline";
  const count = storage.count ?? 0;
  const bytes = storage.bytes ?? 0;
  el.textContent = `Папка: ${path} · ${count} файл(ов), ${fmtBytes(bytes)}`;
}

function openLightbox(url, caption) {
  const box = document.getElementById("shotLightbox");
  const img = document.getElementById("lightboxImg");
  const cap = document.getElementById("lightboxCaption");
  img.src = url;
  img.alt = caption || "Скриншот";
  cap.textContent = caption || "";
  box.hidden = false;
  document.body.style.overflow = "hidden";
  document.getElementById("lightboxClose").focus();
}

function closeLightbox() {
  const box = document.getElementById("shotLightbox");
  if (box.hidden) return;
  box.hidden = true;
  document.getElementById("lightboxImg").removeAttribute("src");
  document.body.style.overflow = "";
}

function summaryKey(summary) {
  return JSON.stringify({
    focus_pct: summary.focus_pct,
    focus_min: Math.floor((summary.focus_sec || 0) / 60),
    total_min: Math.floor((summary.total_sec || 0) / 60),
    by_category: {
      productive: Math.floor((summary.by_category?.productive || 0) / 60),
      neutral: Math.floor((summary.by_category?.neutral || 0) / 60),
      distracting: Math.floor((summary.by_category?.distracting || 0) / 60),
    },
    by_activity: listSignature(summary.by_activity),
    by_app: listSignature(summary.by_app),
    by_site: listSignature(summary.by_site),
  });
}

async function refreshSummary() {
  const summary = await api("/api/summary/today");
  const key = summaryKey(summary);
  if (key === lastSummaryKey) return;
  lastSummaryKey = key;

  document.getElementById("focusValue").textContent = `${summary.focus_pct}%`;
  document.getElementById("focusSub").textContent = `${fmtDur(summary.focus_sec)} из ${fmtDur(summary.total_sec)}`;
  renderBars(summary.by_category, summary.total_sec, { animate: false });
  const activities = summary.by_activity || [];
  renderList(document.getElementById("topAppsToday"), activities, "Занятий пока нет");
  renderList(document.getElementById("activitiesList"), activities, "Занятий пока нет");
  renderList(document.getElementById("appsList"), summary.by_app || [], "Приложений пока нет");
  renderList(document.getElementById("sitesList"), summary.by_site || [], "Сайтов пока нет");
}

async function refreshStatus() {
  const st = await api("/api/status");
  const key = JSON.stringify({
    paused: !!st.paused,
    current_label: st.current_label || "",
    current_app: st.current_app || "",
  });
  if (key === lastStatusKey) return;
  lastStatusKey = key;

  const btn = document.getElementById("toggleBtn");
  btn.textContent = st.paused ? "Продолжить" : "Пауза";
  btn.dataset.paused = st.paused ? "1" : "0";
  const label = st.current_label || st.current_app || "";
  document.getElementById("statusLine").textContent = st.paused
    ? "Пауза"
    : label
      ? `Запись · ${label}`
      : "Запись";
}

async function refreshShots() {
  const rows = await api("/api/screenshots");
  const grid = document.getElementById("shotsGrid");
  if (!rows.length) {
    grid.innerHTML = `<p class="hint">Сегодня скриншотов нет.</p>`;
    return;
  }
  grid.innerHTML = rows
    .map(
      (r) => {
        const caption = `${r.taken_at} · ${r.reason}`;
        return `<figure class="shot" tabindex="0" role="button" data-url="${escapeHtml(r.url)}" data-caption="${escapeHtml(caption)}">
        <img src="${escapeHtml(r.url)}" alt="screenshot" loading="lazy" />
        <figcaption>${escapeHtml(caption)}</figcaption>
      </figure>`;
      }
    )
    .join("");
}

async function loadSettings() {
  const cfg = await api("/api/settings");
  const form = document.getElementById("settingsForm");
  form.screenshot_interval_sec.value = cfg.screenshot_interval_sec;
  form.screenshots_enabled.checked = !!cfg.screenshots_enabled;
  form.screenshot_on_app_switch.checked = !!cfg.screenshot_on_app_switch;
  form.screenshot_retention_days.value = cfg.screenshot_retention_days ?? 7;
  form.open_dashboard_on_start.checked = !!cfg.open_dashboard_on_start;
  form.autostart.checked = !!cfg.autostart;
  updateStorageHint(cfg);
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
    lastStatusKey = "";
    await api(paused ? "/api/control/resume" : "/api/control/pause", { method: "POST" });
    await refreshStatus();
  });

  const shotsGrid = document.getElementById("shotsGrid");
  shotsGrid.addEventListener("click", (ev) => {
    const shot = ev.target.closest(".shot");
    if (!shot) return;
    openLightbox(shot.dataset.url, shot.dataset.caption);
  });
  shotsGrid.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    const shot = ev.target.closest(".shot");
    if (!shot) return;
    ev.preventDefault();
    openLightbox(shot.dataset.url, shot.dataset.caption);
  });

  document.getElementById("lightboxClose").addEventListener("click", closeLightbox);
  document.getElementById("shotLightbox").addEventListener("click", (ev) => {
    if (ev.target.id === "shotLightbox") closeLightbox();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") closeLightbox();
  });

  document.getElementById("settingsForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.currentTarget;
    const body = {
      screenshot_interval_sec: Number(form.screenshot_interval_sec.value),
      screenshots_enabled: form.screenshots_enabled.checked,
      screenshot_on_app_switch: form.screenshot_on_app_switch.checked,
      screenshot_retention_days: Number(form.screenshot_retention_days.value),
      open_dashboard_on_start: form.open_dashboard_on_start.checked,
      autostart: form.autostart.checked,
    };
    const saved = await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
    updateStorageHint(saved);
    alert("Сохранено");
  });

  document.getElementById("purgeShotsBtn").addEventListener("click", async () => {
    if (!confirm("Удалить скриншоты старше срока хранения из настроек?")) return;
    const result = await api("/api/screenshots/purge", { method: "POST" });
    updateStorageHint({ screenshots_storage: result.screenshots_storage });
    await refreshShots();
    alert(`Удалено файлов: ${result.deleted_files || 0}`);
  });

  document.getElementById("passwordForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.currentTarget;
    const body = {
      current_password: form.current_password.value,
      new_password: form.new_password.value,
    };
    try {
      await api("/api/auth/change-password", { method: "POST", body: JSON.stringify(body) });
      form.reset();
      alert("Пароль изменён");
    } catch (e) {
      alert("Не удалось сменить пароль. Проверьте текущий пароль.");
    }
  });

  document.getElementById("logoutBtn").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" });
    location.href = "/login";
  });

  document.getElementById("clearBtn").addEventListener("click", async () => {
    if (!confirm("Удалить все локальные сессии и записи скриншотов?")) return;
    lastSummaryKey = "";
    lastBarsKey = "";
    await api("/api/data/clear", { method: "POST" });
    await refreshSummary();
    await refreshShots();
    await loadSettings();
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
  document.getElementById("focusSub").textContent = "Ошибка загрузки";
});
