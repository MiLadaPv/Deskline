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

const CAT_LABELS = {
  productive: "Фокус",
  neutral: "Нейтрально",
  distracting: "Отвлечение",
  unrated: "Без оценки",
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
    { label: "Всего", value: fmtDur(total), sub: "за день" },
    { label: "Активно", value: fmtDur(summary.active_sec), sub: `${summary.activity_pct ?? 0}%` },
    { label: "Без ввода", value: `${idlePct}%`, sub: fmtDur(summary.idle_sec) },
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
    messaging: "Чаты",
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
      // Narrow chips only show a letter or two — hide label, keep full tooltip.
      const showLabel = width >= 4.5;
      const labelHtml = showLabel
        ? `<span>${escapeHtml(r.name || "")}</span>`
        : "";
      return `<div class="gantt-block ${cat}${showLabel ? "" : " is-narrow"}" style="left:${left}%;width:${width}%" title="${escapeHtml(title)}">${labelHtml}</div>`;
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
        ? iconImgHtml(r.icon_url)
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

const ICON_ONERROR =
  "this.replaceWith(Object.assign(document.createElement('span'),{className:'rank-icon',textContent:'•'}))";

function iconImgHtml(url) {
  if (!url) return `<span class="rank-icon" aria-hidden="true">•</span>`;
  return `<img class="rank-icon-img" src="${escapeHtml(url)}" alt="" width="32" height="32" decoding="async" onerror="${ICON_ONERROR}" />`;
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

function showToast(message, type = "ok") {
  const region = document.getElementById("toastRegion");
  if (!region) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  region.appendChild(toast);
  window.setTimeout(() => toast.remove(), 4200);
}

function setSaveStatus(el, message, state) {
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
  el.classList.remove("is-saving", "is-ok", "is-error");
  if (state) el.classList.add(state);
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
let taskCache = [];
let filterProjectId = "";
let filterTaskId = "";
let selectedProjectId = "";
let usagePeriod = "today";
let projectsReportPeriod = "today";
let expandedReportProjects = new Set();
let lastFocusNames = { project: "", task: "" };
let reportTaskCache = [];

function periodBounds(period) {
  const end = new Date();
  const start = new Date(end);
  if (period === "today") {
    start.setHours(0, 0, 0, 0);
  } else {
    const days = Number(period) || 7;
    start.setDate(start.getDate() - (days - 1));
    start.setHours(0, 0, 0, 0);
  }
  return { from: start.toISOString(), to: end.toISOString() };
}

function periodQuery(period, projectId = "", taskId = "") {
  const { from, to } = periodBounds(period);
  const parts = [`from=${encodeURIComponent(from)}`, `to=${encodeURIComponent(to)}`];
  if (projectId) parts.push(`project_id=${encodeURIComponent(projectId)}`);
  if (taskId) parts.push(`task_id=${encodeURIComponent(taskId)}`);
  return parts.join("&");
}

async function setFocus(projectId, taskId) {
  await api("/api/focus", {
    method: "POST",
    body: JSON.stringify({
      project_id: projectId != null && projectId !== "" ? Number(projectId) : null,
      task_id: taskId != null && taskId !== "" ? Number(taskId) : null,
    }),
  });
  lastStatusKey = "";
}

function fillTaskSelect(tasks, currentTaskId) {
  taskCache = tasks || [];
  const sel = document.getElementById("currentTaskSelect");
  if (!sel) return;
  const open = taskCache.filter((t) => !t.done);
  if (!selectedProjectId) {
    sel.innerHTML = `<option value="">Без задачи</option>`;
    sel.disabled = true;
    return;
  }
  sel.disabled = false;
  sel.innerHTML =
    `<option value="">Без задачи</option>` +
    open
      .map(
        (t) =>
          `<option value="${t.id}" ${String(currentTaskId) === String(t.id) ? "selected" : ""}>${escapeHtml(t.name)}</option>`
      )
      .join("");
  if (currentTaskId != null && String(currentTaskId)) {
    sel.value = String(currentTaskId);
  }
}

function fillProjectSelects(projects, currentId) {
  projectCache = projects || [];
  const opts =
    `<option value="">Без проекта</option>` +
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
  const filUsage = document.getElementById("filterProjectUsage");
  if (cur) {
    cur.innerHTML = opts;
    if (currentId != null && currentId !== "") cur.value = String(currentId);
  }
  if (fil) {
    const keep = fil.value;
    fil.innerHTML = filterOpts;
    fil.value = keep || filterProjectId || "";
  }
  if (filUsage) {
    const keep = filUsage.value;
    filUsage.innerHTML = filterOpts;
    filUsage.value = keep || filterProjectId || "";
  }
}

async function syncUsageTaskFilter() {
  const sel = document.getElementById("filterTaskUsage");
  if (!sel) return;
  if (!filterProjectId) {
    sel.innerHTML = `<option value="">Все</option>`;
    sel.disabled = true;
    filterTaskId = "";
    return;
  }
  const tasks = await api(`/api/tasks?project_id=${encodeURIComponent(filterProjectId)}`);
  sel.disabled = false;
  sel.innerHTML =
    `<option value="">Все</option>` +
    (tasks || [])
      .filter((t) => !t.done)
      .map(
        (t) =>
          `<option value="${t.id}" ${String(filterTaskId) === String(t.id) ? "selected" : ""}>${escapeHtml(t.name)}</option>`
      )
      .join("");
  if (filterTaskId && !(tasks || []).some((t) => String(t.id) === String(filterTaskId))) {
    filterTaskId = "";
    sel.value = "";
  }
}
async function renderTasksPane(projectId, settings, summary) {
  const list = document.getElementById("tasksList");
  const title = document.getElementById("tasksProjectTitle");
  const createBtn = document.getElementById("taskCreateBtn");
  const form = document.getElementById("taskCreateForm");
  if (!list) return;

  if (!projectId) {
    if (title) title.textContent = "Задачи";
    if (createBtn) createBtn.disabled = true;
    if (form) form.querySelector("input[name=name]").disabled = true;
    list.innerHTML = `<p class="hint">Выберите проект слева.</p>`;
    fillTaskSelect([], null);
    return;
  }

  const proj = projectCache.find((p) => String(p.id) === String(projectId));
  if (title) title.textContent = proj ? `Задачи · ${proj.name}` : "Задачи";
  if (createBtn) createBtn.disabled = false;
  if (form) form.querySelector("input[name=name]").disabled = false;

  const tasks = await api(`/api/tasks?project_id=${encodeURIComponent(projectId)}`);
  fillTaskSelect(tasks, settings.current_task_id);

  const secByTask = Object.fromEntries(
    (summary.by_task || []).map((r) => [String(r.task_id), r.sec])
  );
  const focusTask = String(settings.current_task_id || "");
  if (!tasks.length) {
    list.innerHTML = `<p class="hint">Добавьте первую задачу.</p>`;
    return;
  }
  list.innerHTML = tasks
    .map((t) => {
      const active = focusTask === String(t.id);
      const done = !!t.done;
      const sec = secByTask[String(t.id)] || 0;
      return `<div class="pt-item ${active ? "is-active" : ""} ${done ? "is-done" : ""}" data-task-id="${t.id}">
        <button type="button" class="pt-check" data-toggle-done="${t.id}" title="${done ? "Вернуть" : "Готово"}">${done ? "✓" : "○"}</button>
        <div class="pt-item-main">
          <div class="pt-item-name">${escapeHtml(t.name)}</div>
          <div class="pt-item-meta">${sec ? fmtDur(sec) : "—"}</div>
        </div>
        <button type="button" class="btn ${active ? "primary" : ""}" data-focus-task="${t.id}" ${done ? "disabled" : ""}>${active ? "Сейчас" : "Выбрать"}</button>
        <button type="button" class="btn danger pt-del" data-del-task="${t.id}">×</button>
      </div>`;
    })
    .join("");
}

async function refreshProjects() {
  const q = periodQuery(projectsReportPeriod);
  const [projectsRes, summaryRes, settingsRes] = await Promise.allSettled([
    api("/api/projects"),
    api(`/api/summary?${q}`),
    api("/api/settings"),
  ]);
  if (projectsRes.status !== "fulfilled") {
    throw projectsRes.reason || new Error("Не удалось загрузить проекты");
  }
  if (settingsRes.status !== "fulfilled") {
    throw settingsRes.reason || new Error("Не удалось загрузить настройки");
  }
  const projects = projectsRes.value || [];
  const settings = settingsRes.value || {};
  const summary =
    summaryRes.status === "fulfilled"
      ? summaryRes.value
      : { by_project: [], by_task: [], total_sec: 0 };
  fillProjectSelects(projects, settings.current_project_id);
  const workToggle = document.getElementById("workModeToggle");
  if (workToggle) workToggle.checked = !!settings.work_mode;

  if (!selectedProjectId && settings.current_project_id) {
    selectedProjectId = String(settings.current_project_id);
  }
  if (selectedProjectId && !projects.some((p) => String(p.id) === selectedProjectId)) {
    selectedProjectId = projects[0] ? String(projects[0].id) : "";
  }

  const list = document.getElementById("projectsList");
  if (list) {
    if (!projects.length) {
      list.innerHTML = `<p class="hint">Создайте проект — справа появятся задачи.</p>`;
    } else {
      list.innerHTML = projects
        .map((p) => {
          const selected = selectedProjectId === String(p.id);
          const tracking = String(settings.current_project_id) === String(p.id);
          return `<div class="pt-item pt-project ${selected ? "is-selected" : ""} ${tracking ? "is-active" : ""}" style="--pc:${escapeHtml(p.color || "#2f6f5e")}">
            <button type="button" class="pt-project-main" data-select-project="${p.id}" aria-pressed="${selected ? "true" : "false"}">
              <span class="pt-swatch" aria-hidden="true"></span>
              <span class="pt-item-main">
                <span class="pt-item-name">${escapeHtml(p.name)}</span>
                ${tracking ? `<span class="pt-item-meta">Текущий проект</span>` : ""}
              </span>
            </button>
            <button type="button" class="btn danger pt-del" data-del-project="${p.id}" aria-label="Удалить проект ${escapeHtml(p.name)}">×</button>
          </div>`;
        })
        .join("");
    }
  }

  await renderTasksPane(selectedProjectId, settings, summary);

  reportTaskCache = [];
  for (const p of projects) {
    try {
      const tasks = await api(`/api/tasks?project_id=${encodeURIComponent(p.id)}`);
      reportTaskCache.push(...(tasks || []));
    } catch (_) {}
  }
  const proj = projects.find((p) => String(p.id) === String(settings.current_project_id));
  const task = reportTaskCache.find((t) => String(t.id) === String(settings.current_task_id));
  lastFocusNames = {
    project: proj ? proj.name : "",
    task: task ? task.name : "",
  };

  const byProj = summary.by_project || [];
  const nameById = Object.fromEntries(projects.map((p) => [String(p.id), p.name]));
  renderProjectReport(byProj, summary.by_task || [], nameById, summary.total_sec || 0);
}

function renderProjectReport(byProj, byTask, nameById, totalSec) {
  const el = document.getElementById("projectTimeList");
  if (!el) return;
  if (!byProj.length) {
    el.innerHTML = `<p class="hint">Пока нет времени по проектам.</p>`;
    return;
  }
  const taskNameById = Object.fromEntries((reportTaskCache || []).map((t) => [String(t.id), t.name]));
  el.innerHTML = byProj
    .map((r) => {
      const id = r.project_id;
      const key = id == null ? "null" : String(id);
      const name =
        id == null ? "Без проекта" : nameById[String(id)] || `Проект #${id}`;
      const share = totalSec ? Math.round((r.sec / totalSec) * 100) : 0;
      const open = expandedReportProjects.has(key);
      const tasks =
        id == null
          ? (byTask || []).filter((t) => t.project_id == null)
          : (byTask || []).filter((t) => String(t.project_id) === String(id));
      const taskHtml = open
        ? `<div class="report-tasks">${
            tasks.length
              ? tasks
                  .map((t) => {
                    const tname =
                      t.task_id == null
                        ? "Без задачи"
                        : taskNameById[String(t.task_id)] || `Задача #${t.task_id}`;
                    return `<div class="report-task"><span>${escapeHtml(tname)}</span><span>${fmtDur(t.sec)}</span></div>`;
                  })
                  .join("")
              : `<div class="report-task"><span>Нет задач в этом периоде</span><span></span></div>`
          }</div>`
        : "";
      return `<div class="report-row" data-report-project="${escapeHtml(key)}">
        <button type="button" class="report-row-main" data-toggle-report="${escapeHtml(key)}">
          <span class="report-name">${open ? "▾" : "▸"} ${escapeHtml(name)}</span>
          <span class="report-meta">${share}%</span>
          <span class="report-meta">${fmtDur(r.sec)}</span>
        </button>
        ${taskHtml}
      </div>`;
    })
    .join("");
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
    activitySub.textContent = `${fmtDur(summary.active_sec)} активно · ${fmtDur(summary.idle_sec)} без ввода`;
  }
  renderKpis(summary);
  renderProdStack(summary.by_category || {}, summary.total_sec || 0);
  renderBars(summary.by_category, summary.total_sec, { animate: false });
  renderKindBars(summary.by_kind || {}, summary.total_sec || 0);
  refreshTrends().catch(() => {});
  const activities = summary.by_activity || [];
  renderList(document.getElementById("topAppsToday"), activities, "Занятий пока нет");
}

async function refreshUsageReport() {
  const q = periodQuery(usagePeriod, filterProjectId, filterTaskId);
  const summary = await api(`/api/summary?${q}`);
  const total = summary.total_sec || 0;
  renderUsageList(
    document.getElementById("activitiesList"),
    summary.by_activity || [],
    total,
    "activity",
    "Занятий пока нет"
  );
  renderUsageList(
    document.getElementById("appsList"),
    summary.by_app || [],
    total,
    "app",
    "Приложений пока нет"
  );
  renderUsageList(
    document.getElementById("sitesList"),
    summary.by_site || [],
    total,
    "site",
    "Сайтов пока нет"
  );
}

function renderUsageList(el, rows, total, kind, emptyText) {
  if (!el) return;
  const sliced = (rows || []).slice(0, 20);
  if (!sliced.length) {
    el.innerHTML = `<li class="empty-state"><span class="rank-icon" aria-hidden="true">•</span><span class="rank-name">${emptyText}</span><span class="rank-meta">—</span></li>`;
    return;
  }
  el.innerHTML = sliced
    .map((r) => {
      const icon = r.icon_url
        ? iconImgHtml(r.icon_url)
        : `<span class="rank-icon" aria-hidden="true">•</span>`;
      const cat = r.category || "unrated";
      const share = total ? Math.round((r.sec / total) * 100) : 0;
      const ruleKey =
        kind === "site" ? r.name : kind === "app" ? r.app_name || r.name : "";
      const rate =
        kind === "activity"
          ? ""
          : `<div class="usage-rate" data-rate-kind="${kind === "site" ? "site" : "app"}" data-rate-key="${escapeHtml(ruleKey)}">
              ${["productive", "neutral", "distracting", "unrated"]
                .map(
                  (c) =>
                    `<button type="button" class="cat-${c} ${cat === c ? "active" : ""}" data-cat="${c}">${CAT_LABELS[c]}</button>`
                )
                .join("")}
            </div>`;
      return `<li>
        ${icon}
        <span>
          <span class="rank-name">${escapeHtml(r.name)}<span class="rank-cat ${cat}">${CAT_LABELS[cat] || cat}</span></span>
          ${rate}
        </span>
        <span class="rank-meta">${fmtDur(r.sec)} · ${share}%</span>
      </li>`;
    })
    .join("");
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
    task: st.current_task_id || "",
    focusNames: lastFocusNames,
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
  else if (st.idle) line = label ? `Без ввода · ${label}` : "Без ввода";
  else if (label) line = `Запись · ${label}`;
  if (lastFocusNames.project || lastFocusNames.task) {
    const focusBits = [lastFocusNames.project, lastFocusNames.task].filter(Boolean).join(" · ");
    line = `${focusBits} · ${line}`;
  }
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
  form.screenshot_interval_sec.value = cfg.screenshot_interval_sec ?? 300;
  form.screenshots_enabled.checked = !!cfg.screenshots_enabled;
  form.screenshot_on_app_switch.checked = !!cfg.screenshot_on_app_switch;
  form.screenshot_retention_days.value = cfg.screenshot_retention_days ?? 7;
  if (form.screenshots_dir) {
    form.screenshots_dir.value = cfg.screenshots_dir || "";
  }
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
        ? iconImgHtml(r.icon_url)
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
        ? iconImgHtml(r.icon_url)
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
      if (tab.dataset.tab === "usage") refreshUsageReport();
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
      selectedProjectId = v || "";
      let taskId = null;
      if (v) {
        const tasks = await api(`/api/tasks?project_id=${encodeURIComponent(v)}`);
        const first = (tasks || []).find((t) => !t.done);
        taskId = first ? first.id : null;
      }
      await setFocus(v || null, taskId);
      await refreshProjects();
    });
  }

  const taskSelect = document.getElementById("currentTaskSelect");
  if (taskSelect) {
    taskSelect.addEventListener("change", async () => {
      const pid = document.getElementById("currentProjectSelect")?.value || null;
      const tid = taskSelect.value || null;
      await setFocus(pid, tid);
      await refreshProjects();
    });
  }

  const filterToday = document.getElementById("filterProjectToday");
  if (filterToday) {
    filterToday.addEventListener("change", async () => {
      filterProjectId = filterToday.value || "";
      const usageFil = document.getElementById("filterProjectUsage");
      if (usageFil) usageFil.value = filterProjectId;
      filterTaskId = "";
      await syncUsageTaskFilter();
      lastSummaryKey = "";
      await refreshSummary();
      await refreshUsageReport();
    });
  }

  const usagePeriodSel = document.getElementById("usagePeriod");
  if (usagePeriodSel) {
    usagePeriodSel.addEventListener("change", async () => {
      usagePeriod = usagePeriodSel.value || "today";
      await refreshUsageReport();
    });
  }

  const filterUsage = document.getElementById("filterProjectUsage");
  if (filterUsage) {
    filterUsage.addEventListener("change", async () => {
      filterProjectId = filterUsage.value || "";
      if (filterToday) filterToday.value = filterProjectId;
      filterTaskId = "";
      await syncUsageTaskFilter();
      lastSummaryKey = "";
      await refreshSummary();
      await refreshUsageReport();
    });
  }

  const filterTaskUsage = document.getElementById("filterTaskUsage");
  if (filterTaskUsage) {
    filterTaskUsage.addEventListener("change", async () => {
      filterTaskId = filterTaskUsage.value || "";
      await refreshUsageReport();
    });
  }

  const projectsPeriodSel = document.getElementById("projectsReportPeriod");
  if (projectsPeriodSel) {
    projectsPeriodSel.addEventListener("change", async () => {
      projectsReportPeriod = projectsPeriodSel.value || "today";
      await refreshProjects();
    });
  }

  const projectForm = document.getElementById("projectCreateForm");
  if (projectForm) {
    projectForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const nameInput = projectForm.elements.namedItem("name");
      const colorInput = projectForm.elements.namedItem("color");
      const name = String(nameInput && "value" in nameInput ? nameInput.value : "").trim();
      const color = String(colorInput && "value" in colorInput ? colorInput.value : "#2f6f5e");
      if (!name) return;
      try {
        const created = await api("/api/projects", {
          method: "POST",
          body: JSON.stringify({ name, color }),
        });
        projectForm.reset();
        if (colorInput && "value" in colorInput) colorInput.value = "#2f6f5e";
        selectedProjectId = String(created.id);
        const tasks = await api(`/api/tasks?project_id=${created.id}`);
        const first = (tasks || []).find((t) => !t.done);
        await setFocus(created.id, first ? first.id : null);
        await refreshProjects();
        showToast(`Проект «${name}» создан`, "ok");
      } catch (err) {
        console.error(err);
        showToast(err?.message || "Не удалось создать проект", "error");
      }
    });
  }

  const taskForm = document.getElementById("taskCreateForm");
  if (taskForm) {
    taskForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      if (!selectedProjectId) {
        showToast("Сначала выберите проект", "error");
        return;
      }
      const nameInput = taskForm.elements.namedItem("name");
      const name = String(nameInput && "value" in nameInput ? nameInput.value : "").trim();
      if (!name) return;
      try {
        const created = await api("/api/tasks", {
          method: "POST",
          body: JSON.stringify({ project_id: Number(selectedProjectId), name }),
        });
        taskForm.reset();
        await setFocus(selectedProjectId, created.id);
        await refreshProjects();
        showToast(`Задача «${name}» создана`, "ok");
      } catch (err) {
        console.error(err);
        showToast(err?.message || "Не удалось создать задачу", "error");
      }
    });
  }

  const projectsList = document.getElementById("projectsList");
  if (projectsList) {
    projectsList.addEventListener("click", async (ev) => {
      const delBtn = ev.target.closest("[data-del-project]");
      if (delBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        if (!confirm("Удалить проект и его задачи?")) return;
        await api(`/api/projects/${delBtn.dataset.delProject}`, { method: "DELETE" });
        if (selectedProjectId === String(delBtn.dataset.delProject)) {
          selectedProjectId = "";
          await setFocus(null, null);
        }
        await refreshProjects();
        return;
      }
      const row = ev.target.closest("[data-select-project]");
      if (row) {
        selectedProjectId = String(row.dataset.selectProject);
        await refreshProjects();
      }
    });
  }

  const projectReport = document.getElementById("projectTimeList");
  if (projectReport) {
    projectReport.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-toggle-report]");
      if (!btn) return;
      const key = btn.dataset.toggleReport;
      if (expandedReportProjects.has(key)) expandedReportProjects.delete(key);
      else expandedReportProjects.add(key);
      refreshProjects().catch(() => {});
    });
  }

  document.getElementById("panel-usage")?.addEventListener("click", async (ev) => {
    const btn = ev.target.closest(".usage-rate button[data-cat]");
    if (!btn) return;
    const wrap = btn.closest(".usage-rate");
    if (!wrap) return;
    const kind = wrap.dataset.rateKind;
    const key = wrap.dataset.rateKey;
    const category = btn.dataset.cat;
    if (!kind || !key) return;
    await api(`/api/rules/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ kind, category }),
    });
    lastSummaryKey = "";
    await refreshUsageReport();
    await refreshSummary();
  });

  const tasksList = document.getElementById("tasksList");
  if (tasksList) {
    tasksList.addEventListener("click", async (ev) => {
      const focusBtn = ev.target.closest("[data-focus-task]");
      if (focusBtn) {
        await setFocus(selectedProjectId, focusBtn.dataset.focusTask);
        await refreshProjects();
        return;
      }
      const doneBtn = ev.target.closest("[data-toggle-done]");
      if (doneBtn) {
        const id = doneBtn.dataset.toggleDone;
        const task = taskCache.find((t) => String(t.id) === String(id));
        await api(`/api/tasks/${id}`, {
          method: "PUT",
          body: JSON.stringify({ done: !(task && task.done) }),
        });
        await refreshProjects();
        return;
      }
      const delBtn = ev.target.closest("[data-del-task]");
      if (delBtn) {
        if (!confirm("Удалить задачу?")) return;
        await api(`/api/tasks/${delBtn.dataset.delTask}`, { method: "DELETE" });
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
    const submit = document.getElementById("settingsSaveBtn") || form.querySelector('button[type="submit"]');
    const status = document.getElementById("settingsSaveStatus");
    const defaultLabel = "Сохранить";
    if (submit) {
      submit.disabled = true;
      submit.classList.add("is-busy");
      submit.classList.remove("is-saved");
      submit.textContent = "Сохранение…";
    }
    setSaveStatus(status, "Сохранение настроек…", "is-saving");
    const kwRaw = form.work_chat_keywords ? form.work_chat_keywords.value : "";
    const keywords = String(kwRaw || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const interval = Number(form.screenshot_interval_sec.value);
    const body = {
      idle_after_sec: Number(form.idle_after_sec.value),
      poor_time_popup: form.poor_time_popup.checked,
      blur_screenshots: form.blur_screenshots.checked,
      screenshot_interval_sec: Number.isFinite(interval) ? Math.max(60, Math.min(3600, interval)) : 300,
      screenshots_enabled: form.screenshots_enabled.checked,
      screenshot_on_app_switch: form.screenshot_on_app_switch.checked,
      screenshot_retention_days: Number(form.screenshot_retention_days.value),
      screenshots_dir: form.screenshots_dir ? form.screenshots_dir.value.trim() : "",
      open_dashboard_on_start: form.open_dashboard_on_start.checked,
      autostart: form.autostart.checked,
      work_mode: form.work_mode ? form.work_mode.checked : false,
      work_chat_keywords: keywords,
    };
    try {
      const saved = await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
      form.screenshot_interval_sec.value = saved.screenshot_interval_sec ?? body.screenshot_interval_sec;
      if (form.screenshots_dir) {
        form.screenshots_dir.value = saved.screenshots_dir || "";
      }
      updateStorageHint(saved);
      lastSummaryKey = "";
      lastStatusKey = "";
      await refreshSummary();
      await refreshStatus();
      const msg = `Сохранено · интервал ${saved.screenshot_interval_sec} сек`;
      setSaveStatus(status, `✓ ${msg}`, "is-ok");
      showToast(msg, "ok");
      if (submit) {
        submit.classList.remove("is-busy");
        submit.classList.add("is-saved");
        submit.textContent = "Сохранено";
      }
      window.setTimeout(() => {
        if (submit) {
          submit.disabled = false;
          submit.classList.remove("is-saved", "is-busy");
          submit.textContent = defaultLabel;
        }
      }, 2200);
    } catch (err) {
      console.error(err);
      const message = err?.message || "Не удалось сохранить настройки";
      setSaveStatus(status, message, "is-error");
      showToast(message, "error");
      if (submit) {
        submit.disabled = false;
        submit.classList.remove("is-busy", "is-saved");
        submit.textContent = defaultLabel;
      }
    }
  });

  document.getElementById("purgeShotsBtn").addEventListener("click", async () => {
    if (!confirm("Удалить скриншоты старше срока хранения из настроек?")) return;
    try {
      const result = await api("/api/screenshots/purge", { method: "POST" });
      updateStorageHint({ screenshots_storage: result.screenshots_storage });
      await refreshShots();
      showToast(`Удалено файлов: ${result.deleted_files || 0}`, "ok");
    } catch (err) {
      showToast(err?.message || "Не удалось очистить скриншоты", "error");
    }
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
      showToast("Пароль изменён", "ok");
    } catch (e) {
      showToast("Не удалось сменить пароль. Проверьте текущий пароль.", "error");
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
  await Promise.all([
    refreshSummary(),
    refreshStatus(),
    refreshProjects(),
    refreshUsageReport(),
  ]);
  setInterval(() => {
    refreshSummary().catch(() => {});
    refreshStatus().catch(() => {});
    refreshUsageReport().catch(() => {});
  }, 5000);
}

boot().catch((err) => {
  console.error(err);
  document.getElementById("focusSub").textContent = "Ошибка загрузки";
});
