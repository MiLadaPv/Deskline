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
  const aliases = { activities: "usage", apps: "usage", sites: "usage" };
  const tab = aliases[name] || name;
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === tab);
  });
  document.querySelectorAll(".panel").forEach((p) => {
    p.classList.toggle("active", p.id === `panel-${tab}`);
  });
  if (aliases[name]) setUsageSlice(name);
}

function setUsageSlice(slice) {
  const allowed = ["activities", "apps", "sites"];
  const key = allowed.includes(slice) ? slice : "activities";
  document.querySelectorAll(".seg-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.usage === key);
  });
  document.querySelectorAll("[data-usage-pane]").forEach((pane) => {
    const on = pane.dataset.usagePane === key;
    pane.classList.toggle("active", on);
    pane.hidden = !on;
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
  if (!el) return;
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

function renderKpis(summary) {
  const el = document.getElementById("kpiStrip");
  if (!el) return;
  const total = summary.total_sec || 0;
  const idlePct = total ? Math.round(((summary.idle_sec || 0) / total) * 100) : 0;
  const unprodPct = total
    ? Math.round(((summary.by_category?.distracting || 0) / total) * 100)
    : 0;
  const items = [
    { label: "Всего", value: fmtDur(total), sub: "tracked" },
    { label: "Активно", value: fmtDur(summary.active_sec), sub: `${summary.activity_pct ?? 0}%` },
    { label: "Idle", value: `${idlePct}%`, sub: fmtDur(summary.idle_sec) },
    { label: "Фокус", value: `${summary.focus_pct ?? 0}%`, sub: fmtDur(summary.focus_sec) },
    { label: "Отвлечения", value: `${unprodPct}%`, sub: fmtDur(summary.by_category?.distracting || 0) },
  ];
  el.innerHTML = items
    .map(
      (it) => `<div class="kpi-card">
        <span class="kpi-label">${it.label}</span>
        <strong class="kpi-value">${it.value}</strong>
        <span class="kpi-sub">${it.sub}</span>
      </div>`
    )
    .join("");
}

function renderProdStack(byCategory, total) {
  const el = document.getElementById("prodStack");
  if (!el) return;
  if (!total) {
    el.innerHTML = `<div class="stack-empty">Нет данных за сегодня</div>`;
    return;
  }
  const segs = [
    ["productive", "Фокус", byCategory.productive || 0],
    ["neutral", "Нейтрально", byCategory.neutral || 0],
    ["distracting", "Отвлечения", byCategory.distracting || 0],
  ].filter(([, , sec]) => sec > 0);
  el.innerHTML =
    `<div class="stack-track">` +
    segs
      .map(([key, label, sec]) => {
        const pct = Math.max(1, Math.round((sec / total) * 100));
        return `<span class="stack-seg ${key}" style="width:${pct}%" title="${label}: ${fmtDur(sec)} (${pct}%)"></span>`;
      })
      .join("") +
    `</div>` +
    `<div class="stack-legend">` +
    segs
      .map(
        ([key, label, sec]) =>
          `<span class="stack-leg"><i class="${key}"></i>${label} ${fmtDur(sec)}</span>`
      )
      .join("") +
    `</div>`;
}

function renderKindBars(byKind, total) {
  const el = document.getElementById("kindBars");
  if (!el) return;
  const KIND_LABELS = {
    work: "Работа",
    messaging: "Мессенджеры",
    email: "Почта",
    video: "Видео",
    social: "Соцсети",
    search: "Поиск",
    shopping: "Покупки",
    remote: "Удалёнка",
    system: "Система",
    other: "Прочее",
  };
  const rows = Object.entries(byKind || {})
    .map(([k, sec]) => ({ key: k, label: KIND_LABELS[k] || k, sec }))
    .filter((r) => r.sec >= 60)
    .sort((a, b) => b.sec - a.sec)
    .slice(0, 8);
  if (!rows.length) {
    el.innerHTML = `<p class="hint">Пока нет данных по типам занятий.</p>`;
    return;
  }
  const max = Math.max(...rows.map((r) => r.sec), 1);
  el.innerHTML = rows
    .map((r) => {
      const pct = Math.round((r.sec / max) * 100);
      const share = total ? Math.round((r.sec / total) * 100) : 0;
      return `<div class="kind-row">
        <span class="kind-name">${escapeHtml(r.label)}</span>
        <div class="kind-bar"><span style="width:${pct}%"></span></div>
        <span class="kind-meta">${fmtDur(r.sec)} · ${share}%</span>
      </div>`;
    })
    .join("");
}

function weekdayShort(isoDay) {
  const d = new Date(`${isoDay}T12:00:00`);
  return d.toLocaleDateString("ru-RU", { weekday: "short", day: "numeric" });
}

function renderHoursChart(trends) {
  const el = document.getElementById("hoursChart");
  if (!el) return;
  const rows = trends || [];
  const max = Math.max(...rows.map((r) => r.active_sec || r.total_sec || 0), 1);
  el.innerHTML = rows
    .map((r) => {
      const sec = r.active_sec || 0;
      const h = Math.max(2, Math.round((sec / max) * 100));
      return `<div class="hours-col" title="${r.day}: ${fmtDur(sec)} активно">
        <div class="hours-bar-wrap"><div class="hours-bar" style="height:${h}%"></div></div>
        <span class="hours-label">${weekdayShort(r.day)}</span>
        <span class="hours-val">${fmtDur(sec)}</span>
      </div>`;
    })
    .join("");
}

function renderProdDaysChart(trends) {
  const el = document.getElementById("prodDaysChart");
  if (!el) return;
  const rows = trends || [];
  el.innerHTML = rows
    .map((r) => {
      const total = r.total_sec || 0;
      const cats = r.by_category || {};
      const segs = ["productive", "neutral", "distracting"]
        .map((k) => {
          const sec = cats[k] || 0;
          const pct = total ? Math.round((sec / total) * 100) : 0;
          return pct > 0
            ? `<span class="stack-seg ${k}" style="height:${pct}%" title="${k}: ${pct}%"></span>`
            : "";
        })
        .join("");
      return `<div class="prod-day-col" title="${r.day}: фокус ${r.focus_pct}%">
        <div class="prod-day-stack">${total ? segs : `<span class="stack-seg empty" style="height:4%"></span>`}</div>
        <span class="hours-label">${weekdayShort(r.day)}</span>
        <span class="hours-val">${Math.round(r.focus_pct || 0)}%</span>
      </div>`;
    })
    .join("");
}

async function refreshTrends() {
  const q = filterProjectId ? `&project_id=${encodeURIComponent(filterProjectId)}` : "";
  const trends = await api(`/api/trends?days=7${q}`);
  renderHoursChart(trends);
  renderProdDaysChart(trends);
}

function categoryClass(cat) {
  const c = (cat || "neutral").toLowerCase();
  if (c === "productive" || c === "distracting" || c === "neutral") return c;
  return "neutral";
}

function renderDayGantt(rows) {
  const el = document.getElementById("dayGantt");
  if (!el) return;
  if (!rows.length) {
    el.innerHTML = `<p class="hint">Пока нет сессий для timeline.</p>`;
    return;
  }

  const parsed = rows.map((r) => ({
    ...r,
    startMs: new Date(r.started_at).getTime(),
    endMs: new Date(r.ended_at || Date.now()).getTime(),
  }));
  let minMs = Math.min(...parsed.map((r) => r.startMs));
  let maxMs = Math.max(...parsed.map((r) => r.endMs));
  const dayStart = new Date(minMs);
  dayStart.setHours(0, 0, 0, 0);
  const dayEnd = new Date(dayStart);
  dayEnd.setDate(dayEnd.getDate() + 1);
  // Prefer full workday window if sessions fit; else pad 30m
  minMs = Math.min(minMs, dayStart.getTime() + 8 * 3600 * 1000);
  maxMs = Math.max(maxMs, dayStart.getTime() + 19 * 3600 * 1000);
  minMs = Math.max(dayStart.getTime(), minMs - 30 * 60 * 1000);
  maxMs = Math.min(dayEnd.getTime(), maxMs + 30 * 60 * 1000);
  const span = Math.max(maxMs - minMs, 60 * 60 * 1000);

  const hours = [];
  const startH = new Date(minMs);
  startH.setMinutes(0, 0, 0);
  for (let t = startH.getTime(); t <= maxMs; t += 3600 * 1000) {
    const left = ((t - minMs) / span) * 100;
    const label = new Date(t).toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
    });
    hours.push(`<span class="gantt-hour" style="left:${left}%">${label}</span>`);
  }

  const blocks = parsed
    .map((r) => {
      const left = ((r.startMs - minMs) / span) * 100;
      const width = Math.max(0.4, ((r.endMs - r.startMs) / span) * 100);
      const cat = categoryClass(r.category);
      const title = `${r.name || ""} · ${fmtClock(r.started_at)}–${fmtClock(r.ended_at)} · ${fmtDur(r.sec)}`;
      return `<div class="gantt-block ${cat}" style="left:${left}%;width:${width}%" title="${escapeHtml(title)}">
        <span>${escapeHtml(r.name || "")}</span>
      </div>`;
    })
    .join("");

  el.innerHTML = `
    <div class="gantt-scale">${hours.join("")}</div>
    <div class="gantt-track">${blocks}</div>
    <div class="gantt-legend">
      <span class="stack-leg"><i class="productive"></i>Фокус</span>
      <span class="stack-leg"><i class="neutral"></i>Нейтрально</span>
      <span class="stack-leg"><i class="distracting"></i>Отвлечение</span>
    </div>`;
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
        ? `<img class="rank-icon-img" src="${escapeHtml(r.icon_url)}" alt="" width="32" height="32" decoding="async" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'rank-icon',textContent:'•'}))" />`
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

let lightboxItems = [];
let lightboxIndex = 0;

function openLightboxAt(index) {
  if (!lightboxItems.length) return;
  lightboxIndex = ((index % lightboxItems.length) + lightboxItems.length) % lightboxItems.length;
  const item = lightboxItems[lightboxIndex];
  const box = document.getElementById("shotLightbox");
  const img = document.getElementById("lightboxImg");
  const cap = document.getElementById("lightboxCaption");
  img.src = item.url;
  img.alt = item.caption || "Скриншот";
  cap.textContent = `${item.caption || ""} · ${lightboxIndex + 1}/${lightboxItems.length}`;
  box.classList.toggle("flag-distracting", !!item.flag);
  box.hidden = false;
  document.body.style.overflow = "hidden";
}

function openLightbox(url, caption, flag) {
  const idx = lightboxItems.findIndex((x) => x.url === url);
  if (idx >= 0) openLightboxAt(idx);
  else {
    lightboxItems = [{ url, caption, flag: !!flag }];
    openLightboxAt(0);
  }
}

function stepLightbox(delta) {
  if (document.getElementById("shotLightbox").hidden) return;
  openLightboxAt(lightboxIndex + delta);
}

function closeLightbox() {
  const box = document.getElementById("shotLightbox");
  if (box.hidden) return;
  box.hidden = true;
  box.classList.remove("flag-distracting");
  document.getElementById("lightboxImg").removeAttribute("src");
  document.body.style.overflow = "";
}

let projectCache = [];
let filterProjectId = "";

function fillProjectSelects(projects, currentId) {
  projectCache = projects || [];
  const opts =
    `<option value="">Проект: не выбран</option>` +
    projectCache
      .map(
        (p) =>
          `<option value="${p.id}" ${String(currentId) === String(p.id) ? "selected" : ""}>${escapeHtml(p.name)}</option>`
      )
      .join("");
  const filterOpts =
    `<option value="">Все</option>` +
    projectCache
      .map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`)
      .join("");
  const cur = document.getElementById("currentProjectSelect");
  const fil = document.getElementById("filterProjectToday");
  if (cur) {
    const keep = cur.value;
    cur.innerHTML = opts;
    if (currentId != null) cur.value = String(currentId);
    else if (keep) cur.value = keep;
  }
  if (fil) {
    const keep = fil.value;
    fil.innerHTML = filterOpts;
    fil.value = keep || filterProjectId || "";
  }
}

async function refreshProjects() {
  const [projects, summary, settings] = await Promise.all([
    api("/api/projects"),
    api("/api/summary/today"),
    api("/api/settings"),
  ]);
  fillProjectSelects(projects, settings.current_project_id);
  const workToggle = document.getElementById("workModeToggle");
  if (workToggle) workToggle.checked = !!settings.work_mode;

  const list = document.getElementById("projectsList");
  if (list) {
    if (!projects.length) {
      list.innerHTML = `<p class="hint">Создайте первый проект — например «Клиент A» или «Учёба».</p>`;
    } else {
      list.innerHTML = projects
        .map((p) => {
          const active = String(settings.current_project_id) === String(p.id);
          return `<div class="project-card" style="--pc:${escapeHtml(p.color || "#2f6f5e")}">
            <div class="project-name">${escapeHtml(p.name)}</div>
            <div class="project-actions">
              <button type="button" class="btn ${active ? "primary" : ""}" data-focus-project="${p.id}">${active ? "Сейчас" : "Выбрать"}</button>
              <button type="button" class="btn danger" data-del-project="${p.id}">Удалить</button>
            </div>
          </div>`;
        })
        .join("");
    }
  }

  const byProj = summary.by_project || [];
  const nameById = Object.fromEntries(projects.map((p) => [String(p.id), p.name]));
  const timeRows = byProj.map((r) => ({
    name: nameById[String(r.project_id)] || `Проект #${r.project_id}`,
    sec: r.sec,
  }));
  const timeEl = document.getElementById("projectTimeList");
  if (timeEl) renderList(timeEl, timeRows, "Пока нет времени по проектам");
}

async function refreshSummary() {
  const q = filterProjectId ? `?project_id=${encodeURIComponent(filterProjectId)}` : "";
  const summary = await api(`/api/summary/today${q}`);
  const key = summaryKey(summary) + `|p:${filterProjectId}`;
  if (key === lastSummaryKey) return;
  lastSummaryKey = key;

  document.getElementById("focusValue").textContent = `${summary.focus_pct}%`;
  document.getElementById("focusSub").textContent = `${fmtDur(summary.focus_sec)} из ${fmtDur(summary.total_sec)}`;
  const activityValue = document.getElementById("activityValue");
  const activitySub = document.getElementById("activitySub");
  if (activityValue) {
    activityValue.textContent = `${summary.activity_pct ?? 0}%`;
  }
  if (activitySub) {
    activitySub.textContent = `${fmtDur(summary.active_sec)} активно · ${fmtDur(summary.idle_sec)} idle`;
  }
  renderKpis(summary);
  renderProdStack(summary.by_category || {}, summary.total_sec || 0);
  renderBars(summary.by_category, summary.total_sec, { animate: false });
  renderKindBars(summary.by_kind || {}, summary.total_sec || 0);
  refreshTrends().catch(() => {});
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
    idle: !!st.idle,
    current_label: st.current_label || "",
    current_app: st.current_app || "",
    work_mode: !!st.work_mode,
    project: st.current_project_id || "",
  });
  if (key === lastStatusKey) return;
  lastStatusKey = key;

  const btn = document.getElementById("toggleBtn");
  btn.textContent = st.paused ? "Продолжить" : "Пауза";
  btn.dataset.paused = st.paused ? "1" : "0";
  const workToggle = document.getElementById("workModeToggle");
  if (workToggle) workToggle.checked = !!st.work_mode;
  const label = st.current_label || st.current_app || "";
  let line = "Запись";
  if (st.paused) line = "Пауза";
  else if (st.idle) line = label ? `Idle · ${label}` : "Idle";
  else if (label) line = `Запись · ${label}`;
  if (st.work_mode) line = `На работе · ${line}`;
  document.getElementById("statusLine").textContent = line;
  const ver = document.getElementById("appVersion");
  if (ver && st.version) ver.textContent = `Deskline v${st.version}`;
}

function fmtShotWhen(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const today = new Date();
  const sameDay =
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate();
  const time = d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  if (sameDay) return time;
  return d.toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtShotReason(reason) {
  const map = {
    app_switch: "Смена приложения",
    interval: "По расписанию",
    manual: "Вручную",
  };
  return map[reason] || reason || "Скриншот";
}

function shotCaption(row) {
  return `${fmtShotWhen(row.taken_at)} · ${fmtShotReason(row.reason)}`;
}

async function refreshShots() {
  const rows = await api("/api/screenshots");
  const grid = document.getElementById("shotsGrid");
  lightboxItems = rows.map((r) => ({
    url: r.url,
    caption: shotCaption(r),
    flag: !!r.flag_distracting,
  }));
  if (!rows.length) {
    grid.innerHTML = `<p class="hint">Сегодня скриншотов нет.</p>`;
    return;
  }
  grid.innerHTML = rows
    .map((r, i) => {
      const caption = shotCaption(r);
      const flag = r.flag_distracting ? "shot-distracting" : "";
      return `<figure class="shot ${flag}" tabindex="0" role="button" data-index="${i}" data-url="${escapeHtml(r.url)}" data-caption="${escapeHtml(caption)}" data-flag="${r.flag_distracting ? "1" : "0"}">
        <img src="${escapeHtml(r.url)}" alt="screenshot" loading="lazy" />
        <figcaption>${escapeHtml(caption)}</figcaption>
      </figure>`;
    })
    .join("");
}

async function loadSettings() {
  const cfg = await api("/api/settings");
  const form = document.getElementById("settingsForm");
  form.idle_after_sec.value = cfg.idle_after_sec ?? 180;
  form.poor_time_popup.checked = cfg.poor_time_popup !== false;
  form.blur_screenshots.checked = !!cfg.blur_screenshots;
  form.screenshot_interval_sec.value = cfg.screenshot_interval_sec;
  form.screenshots_enabled.checked = !!cfg.screenshots_enabled;
  form.screenshot_on_app_switch.checked = !!cfg.screenshot_on_app_switch;
  form.screenshot_retention_days.value = cfg.screenshot_retention_days ?? 7;
  form.open_dashboard_on_start.checked = !!cfg.open_dashboard_on_start;
  form.autostart.checked = !!cfg.autostart;
  if (form.work_mode) form.work_mode.checked = !!cfg.work_mode;
  if (form.work_chat_keywords) {
    const kw = cfg.work_chat_keywords || [];
    form.work_chat_keywords.value = Array.isArray(kw) ? kw.join(", ") : "";
  }
  updateStorageHint(cfg);
  const workToggle = document.getElementById("workModeToggle");
  if (workToggle) workToggle.checked = !!cfg.work_mode;
}

function summaryKey(summary) {
  return JSON.stringify({
    focus_pct: summary.focus_pct,
    activity_pct: summary.activity_pct,
    focus_min: Math.floor((summary.focus_sec || 0) / 60),
    active_min: Math.floor((summary.active_sec || 0) / 60),
    idle_min: Math.floor((summary.idle_sec || 0) / 60),
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

const CAT_LABELS = {
  productive: "Фокус",
  neutral: "Нейтрально",
  distracting: "Отвлечение",
  unrated: "Без оценки",
};

function fmtClock(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

async function refreshTimeline() {
  const rows = await api("/api/timeline/today");
  renderDayGantt(rows);
  const el = document.getElementById("timelineList");
  if (!rows.length) {
    el.innerHTML = `<li><span class="timeline-time">—</span><span class="rank-icon">•</span><span class="rank-name">Пока нет сессий</span><span class="rank-meta"></span></li>`;
    return;
  }
  el.innerHTML = rows
    .map((r) => {
      const icon = r.icon_url
        ? `<img class="rank-icon-img" src="${escapeHtml(r.icon_url)}" alt="" width="32" height="32" decoding="async" />`
        : `<span class="rank-icon">•</span>`;
      const idle =
        r.idle_sec >= 60
          ? `<span class="timeline-idle">idle ${fmtDur(r.idle_sec)}</span>`
          : "";
      const cat = categoryClass(r.category);
      return `<li class="timeline-cat-${cat}">
        <span class="timeline-time">${fmtClock(r.started_at)}</span>
        ${icon}
        <span>
          <span class="rank-name">${escapeHtml(r.name)}</span>
          ${idle}
        </span>
        <span class="rank-meta">${fmtDur(r.sec)}</span>
      </li>`;
    })
    .join("");
}

async function refreshRatings() {
  const rows = await api("/api/ratings");
  const el = document.getElementById("ratingsList");
  if (!rows.length) {
    el.innerHTML = `<p class="hint">Сегодня ещё нет приложений и сайтов для оценки.</p>`;
    return;
  }
  el.innerHTML = rows
    .map((r) => {
      const icon = r.icon_url
        ? `<img class="rank-icon-img" src="${escapeHtml(r.icon_url)}" alt="" width="32" height="32" decoding="async" />`
        : `<span class="rank-icon">•</span>`;
      const kindLabel = r.kind === "site" ? "сайт" : "приложение";
      const btns = ["productive", "neutral", "distracting", "unrated"]
        .map((c) => {
          const active = r.category === c ? "active" : "";
          return `<button type="button" class="cat-${c} ${active}" data-kind="${escapeHtml(r.kind)}" data-key="${escapeHtml(r.key)}" data-cat="${c}">${CAT_LABELS[c]}</button>`;
        })
        .join("");
      return `<div class="rating-row">
        ${icon}
        <div>
          <div class="rating-name">${escapeHtml(r.name)}</div>
          <div class="rating-meta">${kindLabel} · ${fmtDur(r.sec)}</div>
        </div>
        <div class="rating-btns">${btns}</div>
      </div>`;
    })
    .join("");
}

function wireUi() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      setActiveTab(tab.dataset.tab);
      if (tab.dataset.tab === "shots") refreshShots();
      if (tab.dataset.tab === "settings") loadSettings();
      if (tab.dataset.tab === "day") refreshTimeline();
      if (tab.dataset.tab === "ratings") refreshRatings();
      if (tab.dataset.tab === "projects") refreshProjects();
    });
  });

  document.querySelectorAll(".seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => setUsageSlice(btn.dataset.usage));
  });

  document.getElementById("toggleBtn").addEventListener("click", async (e) => {
    const paused = e.currentTarget.dataset.paused === "1";
    lastStatusKey = "";
    await api(paused ? "/api/control/resume" : "/api/control/pause", { method: "POST" });
    await refreshStatus();
  });

  const workToggle = document.getElementById("workModeToggle");
  if (workToggle) {
    workToggle.addEventListener("change", async () => {
      await api("/api/settings", {
        method: "PUT",
        body: JSON.stringify({ work_mode: workToggle.checked }),
      });
      lastSummaryKey = "";
      lastStatusKey = "";
      await refreshSummary();
      await refreshStatus();
      await refreshShots();
    });
  }

  const projectSelect = document.getElementById("currentProjectSelect");
  if (projectSelect) {
    projectSelect.addEventListener("change", async () => {
      const v = projectSelect.value;
      await api("/api/focus", {
        method: "POST",
        body: JSON.stringify({
          project_id: v ? Number(v) : null,
          task_id: null,
        }),
      });
      lastStatusKey = "";
      await refreshProjects();
    });
  }

  const filterToday = document.getElementById("filterProjectToday");
  if (filterToday) {
    filterToday.addEventListener("change", async () => {
      filterProjectId = filterToday.value || "";
      lastSummaryKey = "";
      await refreshSummary();
    });
  }

  const projectForm = document.getElementById("projectCreateForm");
  if (projectForm) {
    projectForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const name = projectForm.name.value.trim();
      const color = projectForm.color.value;
      if (!name) return;
      await api("/api/projects", {
        method: "POST",
        body: JSON.stringify({ name, color }),
      });
      projectForm.reset();
      projectForm.color.value = "#2f6f5e";
      await refreshProjects();
    });
  }

  const projectsList = document.getElementById("projectsList");
  if (projectsList) {
    projectsList.addEventListener("click", async (ev) => {
      const focusBtn = ev.target.closest("[data-focus-project]");
      if (focusBtn) {
        await api("/api/focus", {
          method: "POST",
          body: JSON.stringify({
            project_id: Number(focusBtn.dataset.focusProject),
            task_id: null,
          }),
        });
        await refreshProjects();
        return;
      }
      const delBtn = ev.target.closest("[data-del-project]");
      if (delBtn) {
        if (!confirm("Удалить проект?")) return;
        await api(`/api/projects/${delBtn.dataset.delProject}`, { method: "DELETE" });
        await refreshProjects();
      }
    });
  }

  const shotsGrid = document.getElementById("shotsGrid");
  shotsGrid.addEventListener("click", (ev) => {
    const shot = ev.target.closest(".shot");
    if (!shot) return;
    const idx = Number(shot.dataset.index || 0);
    openLightboxAt(idx);
  });
  shotsGrid.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    const shot = ev.target.closest(".shot");
    if (!shot) return;
    ev.preventDefault();
    openLightboxAt(Number(shot.dataset.index || 0));
  });

  document.getElementById("ratingsList").addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button[data-key]");
    if (!btn) return;
    const kind = btn.dataset.kind;
    const key = btn.dataset.key;
    const category = btn.dataset.cat;
    await api(`/api/rules/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ kind, category }),
    });
    lastSummaryKey = "";
    await refreshRatings();
    await refreshSummary();
  });

  document.getElementById("lightboxClose").addEventListener("click", closeLightbox);
  document.getElementById("lightboxPrev").addEventListener("click", (ev) => {
    ev.stopPropagation();
    stepLightbox(-1);
  });
  document.getElementById("lightboxNext").addEventListener("click", (ev) => {
    ev.stopPropagation();
    stepLightbox(1);
  });
  document.getElementById("shotLightbox").addEventListener("click", (ev) => {
    if (ev.target.id === "shotLightbox") closeLightbox();
  });
  document.getElementById("shotLightbox").addEventListener(
    "wheel",
    (ev) => {
      if (document.getElementById("shotLightbox").hidden) return;
      ev.preventDefault();
      if (ev.deltaY > 0) stepLightbox(1);
      else if (ev.deltaY < 0) stepLightbox(-1);
    },
    { passive: false }
  );
  document.addEventListener("keydown", (ev) => {
    const box = document.getElementById("shotLightbox");
    if (box.hidden) return;
    if (ev.key === "Escape") closeLightbox();
    if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      stepLightbox(-1);
    }
    if (ev.key === "ArrowRight") {
      ev.preventDefault();
      stepLightbox(1);
    }
  });

  document.getElementById("settingsForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.currentTarget;
    const kwRaw = form.work_chat_keywords ? form.work_chat_keywords.value : "";
    const keywords = String(kwRaw || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const body = {
      idle_after_sec: Number(form.idle_after_sec.value),
      poor_time_popup: form.poor_time_popup.checked,
      blur_screenshots: form.blur_screenshots.checked,
      screenshot_interval_sec: Number(form.screenshot_interval_sec.value),
      screenshots_enabled: form.screenshots_enabled.checked,
      screenshot_on_app_switch: form.screenshot_on_app_switch.checked,
      screenshot_retention_days: Number(form.screenshot_retention_days.value),
      open_dashboard_on_start: form.open_dashboard_on_start.checked,
      autostart: form.autostart.checked,
      work_mode: form.work_mode ? form.work_mode.checked : false,
      work_chat_keywords: keywords,
    };
    const saved = await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
    updateStorageHint(saved);
    lastSummaryKey = "";
    lastStatusKey = "";
    await refreshSummary();
    await refreshStatus();
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
  await Promise.all([refreshSummary(), refreshStatus(), refreshProjects()]);
  setInterval(() => {
    refreshSummary().catch(() => {});
    refreshStatus().catch(() => {});
  }, 5000);
}

boot().catch((err) => {
  console.error(err);
  document.getElementById("focusSub").textContent = "Ошибка загрузки";
});
