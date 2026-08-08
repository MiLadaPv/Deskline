const fmtDur = (sec) => {
  sec = Math.max(0, Math.round(sec || 0));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}ч ${m}м`;
  if (m > 0) return `${m}м`;
  if (s > 0) return `${s}с`;
  return "0с";
};

const UI_TEXT_SCALE_KEY = "deskline_ui_text_scale";
const CHART_SCALE_KEY = "deskline_chart_scales";
const TEXT_SCALE_MIN = 0.85;
const TEXT_SCALE_MAX = 1.45;
const CHART_SCALE_MIN = 0.7;
const CHART_SCALE_MAX = 1.8;
const ZOOM_STEP = 0.05;

function clampZoom(value, min, max) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 1;
  return Math.min(max, Math.max(min, Math.round(n * 100) / 100));
}

function getUiTextScale() {
  try {
    return clampZoom(localStorage.getItem(UI_TEXT_SCALE_KEY) || "1", TEXT_SCALE_MIN, TEXT_SCALE_MAX);
  } catch (_) {
    return 1;
  }
}

function setUiTextScale(scale, { persist = true } = {}) {
  const next = clampZoom(scale, TEXT_SCALE_MIN, TEXT_SCALE_MAX);
  document.documentElement.style.setProperty("--ui-text-scale", String(next));
  if (persist) {
    try {
      localStorage.setItem(UI_TEXT_SCALE_KEY, String(next));
    } catch (_) {}
  }
  return next;
}

function readChartScales() {
  try {
    const raw = JSON.parse(localStorage.getItem(CHART_SCALE_KEY) || "{}");
    return raw && typeof raw === "object" ? raw : {};
  } catch (_) {
    return {};
  }
}

function chartZoomKey(el) {
  if (!el) return "chart";
  if (el.id) return el.id;
  const pie = el.closest?.(".pie-chart");
  if (pie?.id) return pie.id;
  const card = el.closest?.(".chart-card");
  if (card) {
    const titled = card.querySelector("h3, .subhead");
    if (titled?.textContent) return `card:${titled.textContent.trim()}`;
  }
  return el.className || "chart";
}

function findChartZoomHost(target) {
  if (!target || !target.closest) return null;
  return target.closest(
    ".pie-chart, .donut-wrap, .pulse-proj-donut, .hours-line, .prod-days-chart, .gantt-wrap"
  );
}

function applyChartScale(host, scale, { persist = true } = {}) {
  if (!host) return 1;
  const next = clampZoom(scale, CHART_SCALE_MIN, CHART_SCALE_MAX);
  const pie = host.closest?.(".pie-chart") || (host.classList?.contains("pie-chart") ? host : null);
  const wrap = host.classList?.contains("donut-wrap")
    ? host
    : host.querySelector?.(".donut-wrap");
  if (pie) pie.style.setProperty("--chart-scale", String(next));
  if (wrap) wrap.style.setProperty("--chart-scale", String(next));
  if (!wrap && !pie) {
    host.style.setProperty("--chart-scale", String(next));
    host.style.zoom = String(next);
  }
  host.classList.add("chart-zoomable");
  if (persist) {
    const map = readChartScales();
    map[chartZoomKey(pie || host)] = next;
    try {
      localStorage.setItem(CHART_SCALE_KEY, JSON.stringify(map));
    } catch (_) {}
  }
  return next;
}

function restoreChartScales() {
  const map = readChartScales();
  Object.entries(map).forEach(([key, scale]) => {
    let host = null;
    if (key.startsWith("card:")) {
      const title = key.slice(5);
      host = [...document.querySelectorAll(".chart-card")].find(
        (card) => (card.querySelector("h3, .subhead")?.textContent || "").trim() === title
      )?.querySelector(".pie-chart, .donut-wrap");
    } else {
      host = document.getElementById(key);
    }
    if (host) applyChartScale(host, scale, { persist: false });
  });
}

function wireZoomControls() {
  if (document.documentElement.dataset.zoomWired === "1") return;
  document.documentElement.dataset.zoomWired = "1";
  setUiTextScale(getUiTextScale(), { persist: false });

  document.addEventListener(
    "wheel",
    (ev) => {
      if (!ev.ctrlKey) return;
      ev.preventDefault();
      const dir = ev.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP;
      const chartHost = findChartZoomHost(ev.target);
      if (chartHost) {
        const pie = chartHost.closest(".pie-chart") || chartHost;
        const current = Number.parseFloat(
          getComputedStyle(pie).getPropertyValue("--chart-scale") ||
            chartHost.style.zoom ||
            "1"
        );
        applyChartScale(chartHost, (Number.isFinite(current) ? current : 1) + dir);
        return;
      }
      setUiTextScale(getUiTextScale() + dir);
    },
    { passive: false }
  );

  document.addEventListener("keydown", (ev) => {
    if (!ev.ctrlKey) return;
    const key = ev.key;
    if (key !== "0" && key !== "=" && key !== "+" && key !== "-" && key !== "_") return;
    const chartHost = findChartZoomHost(document.activeElement) || findChartZoomHost(ev.target);
    if (key === "0") {
      ev.preventDefault();
      if (chartHost) applyChartScale(chartHost, 1);
      else setUiTextScale(1);
      return;
    }
    if (key === "=" || key === "+") {
      ev.preventDefault();
      if (chartHost) {
        const pie = chartHost.closest(".pie-chart") || chartHost;
        const current = Number.parseFloat(getComputedStyle(pie).getPropertyValue("--chart-scale") || "1");
        applyChartScale(chartHost, (Number.isFinite(current) ? current : 1) + ZOOM_STEP);
      } else setUiTextScale(getUiTextScale() + ZOOM_STEP);
      return;
    }
    if (key === "-" || key === "_") {
      ev.preventDefault();
      if (chartHost) {
        const pie = chartHost.closest(".pie-chart") || chartHost;
        const current = Number.parseFloat(getComputedStyle(pie).getPropertyValue("--chart-scale") || "1");
        applyChartScale(chartHost, (Number.isFinite(current) ? current : 1) - ZOOM_STEP);
      } else setUiTextScale(getUiTextScale() - ZOOM_STEP);
    }
  });
}

// Restore text zoom before first paint of dynamic content.
try {
  setUiTextScale(getUiTextScale(), { persist: false });
} catch (_) {}

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

const CAT_COLORS = {
  productive: "#1f6b56",
  neutral: "#6d7c74",
  distracting: "#b54738",
  unrated: "#9aa59f",
};

const KIND_COLORS = [
  "#1f6b56",
  "#3d7ea6",
  "#8a6a3b",
  "#b54738",
  "#6b5b95",
  "#4a7c59",
  "#c47a3a",
  "#5c6b73",
  "#2f6f5e",
  "#7d8a82",
];

let lastSummaryKey = "";
let lastStatusKey = "";
let lastDayViewKey = "";
/** @type {string} YYYY-MM-DD — always defaults to today */
let selectedDayIso = "";
/** @type {any} */
let currentEntitlements = null;

function localDayIso(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function ensureSelectedDay() {
  const today = localDayIso();
  if (!selectedDayIso || !/^\d{4}-\d{2}-\d{2}$/.test(selectedDayIso)) {
    selectedDayIso = today;
  }
  if (selectedDayIso > today) selectedDayIso = today;
  const hist = currentEntitlements?.history_days;
  if (hist) {
    const oldest = shiftDayIso(today, -(hist - 1));
    if (selectedDayIso < oldest) selectedDayIso = oldest;
  }
  return selectedDayIso;
}

function shiftDayIso(iso, deltaDays) {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + deltaDays);
  return localDayIso(d);
}

function startOfWeekMonday(iso) {
  const d = new Date(`${iso}T12:00:00`);
  const dow = d.getDay(); // 0=Sun … 6=Sat
  const delta = dow === 0 ? -6 : 1 - dow;
  d.setDate(d.getDate() + delta);
  return localDayIso(d);
}

function dayQueryBounds(isoDay) {
  const start = new Date(`${isoDay}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { from: start.toISOString(), to: end.toISOString() };
}

function formatDayTitle(isoDay) {
  const d = new Date(`${isoDay}T12:00:00`);
  return d.toLocaleDateString("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function renderDayWeekStrip() {
  const el = document.getElementById("dayNav");
  if (!el) return;
  ensureSelectedDay();
  const today = localDayIso();
  const weekStart = startOfWeekMonday(selectedDayIso);
  const navSig = `${selectedDayIso}|${today}|${weekStart}`;
  if (el.dataset.navSig === navSig) return;
  el.dataset.navSig = navSig;
  const chips = [];
  for (let i = 0; i < 7; i++) {
    const iso = shiftDayIso(weekStart, i);
    const d = new Date(`${iso}T12:00:00`);
    const wd = d.toLocaleDateString("ru-RU", { weekday: "short" });
    const num = String(d.getDate());
    const future = iso > today;
    const active = iso === selectedDayIso;
    const isToday = iso === today;
    chips.push(`<button type="button"
      class="day-chip${active ? " is-active" : ""}${isToday ? " is-today" : ""}"
      data-pick-day="${iso}"
      ${future ? "disabled" : ""}
      aria-pressed="${active ? "true" : "false"}"
      aria-label="${escapeHtml(formatDayTitle(iso))}">
      <span class="day-chip-wd">${escapeHtml(wd)}</span>
      <span class="day-chip-num">${num}</span>
    </button>`);
  }
  const monthLabel = new Date(`${selectedDayIso}T12:00:00`).toLocaleDateString("ru-RU", {
    month: "long",
    year: "numeric",
  });
  const canGoNext =
    shiftDayIso(weekStart, 7) <= today || selectedDayIso < today;
  el.innerHTML = `
    <div class="day-week-toolbar">
      <button type="button" class="btn day-nav-btn" data-shift-week="-7" aria-label="Предыдущая неделя">‹</button>
      <div class="day-week-meta">
        <strong class="day-week-month">${escapeHtml(monthLabel)}</strong>
        <span class="day-week-current">${escapeHtml(formatDayTitle(selectedDayIso))}</span>
      </div>
      <button type="button" class="btn day-nav-btn" data-shift-week="7" aria-label="Следующая неделя" ${canGoNext ? "" : "disabled"}>›</button>
      <button type="button" class="btn ${selectedDayIso === today ? "" : "primary"}" data-go-today ${selectedDayIso === today ? "disabled" : ""}>Сегодня</button>
    </div>
    <div class="day-week-strip" role="listbox" aria-label="Дни недели">${chips.join("")}</div>
  `;
}

async function api(path, opts = {}) {
  const { quiet402, ...fetchOpts } = opts;
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(fetchOpts.headers || {}) },
    ...fetchOpts,
  });
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    location.href = "/login";
    throw new Error("auth required");
  }
  if (!res.ok) {
    const raw = await res.text();
    let message = raw || res.statusText || "Request failed";
    let detail = null;
    try {
      const parsed = JSON.parse(raw);
      detail = parsed?.detail ?? parsed;
      if (typeof detail === "string") message = detail;
      else if (detail && typeof detail.message === "string") message = detail.message;
      else if (Array.isArray(detail)) {
        message = detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      }
    } catch (_) {}
    if (res.status === 402) {
      if (detail?.entitlements) applyEntitlements(detail.entitlements);
      if (!quiet402) showPaywall(message);
      const err = new Error(message);
      err.code = detail?.code || "pro_required";
      err.detail = detail;
      throw err;
    }
    throw new Error(message);
  }
  if (res.status === 204) return null;
  return res.json();
}

function applyEntitlements(ent) {
  if (!ent) return;
  currentEntitlements = ent;
  const chip = document.getElementById("planChip");
  if (chip) chip.textContent = ent.label || ent.tier || "Free";
  const badge = document.getElementById("planBadge");
  if (badge) badge.textContent = `${ent.label || "Free"} · ${ent.status_detail || ""}`;
  const detail = document.getElementById("planDetail");
  if (detail) {
    detail.textContent = ent.license_key_masked
      ? `Ключ: ${ent.license_key_masked}`
      : ent.trial_ends_at
        ? `Trial до ${ent.trial_ends_at.slice(0, 10)}`
        : "Без активного ключа";
  }
  const annual = document.getElementById("checkoutAnnual");
  if (annual && ent.checkout?.annual) annual.href = ent.checkout.annual;
  const teamBuy = document.getElementById("checkoutTeam");
  if (teamBuy && ent.checkout?.team) teamBuy.href = ent.checkout.team;
  const companyToggle = document.getElementById("companyModeToggle");
  if (companyToggle) {
    companyToggle.disabled = !ent.company_hub;
  }
  const shotsToggle = document.querySelector('input[name="screenshots_enabled"]');
  if (shotsToggle) shotsToggle.disabled = !ent.screenshots;
  const teamHint = document.getElementById("teamUpsellHint");
  if (teamHint) teamHint.hidden = !!ent.company_hub;
  ensureSelectedDay();
  syncTrendsPeriodOptions();
}

let _paywallShownAt = 0;

function showPaywall(message) {
  const modal = document.getElementById("paywallModal");
  const msg = document.getElementById("paywallMessage");
  if (msg) msg.textContent = message || "Доступно в Deskline Pro";
  if (!modal) return;
  if (!modal.hidden) return;
  const now = Date.now();
  if (now - _paywallShownAt < 10000) return;
  _paywallShownAt = now;
  modal.hidden = false;
}

const THEME_CYCLE = ["system", "light", "dark"];
const THEME_LABELS = { system: "Система", light: "Светлая", dark: "Тёмная" };

function resolveTheme(pref) {
  if (pref === "dark" || pref === "light") return pref;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyThemePref(pref) {
  const next = THEME_CYCLE.includes(pref) ? pref : "system";
  try {
    localStorage.setItem("deskline_theme", next);
  } catch (_) {}
  document.documentElement.setAttribute("data-theme", resolveTheme(next));
  document.documentElement.setAttribute("data-theme-pref", next);
  const btn = document.getElementById("themeToggle");
  if (btn) btn.textContent = THEME_LABELS[next] || "Тема";
}

async function persistTheme(pref) {
  applyThemePref(pref);
  try {
    await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ theme: pref }),
      quiet402: true,
    });
  } catch (_) {}
}

function wireThemeToggle() {
  const btn = document.getElementById("themeToggle");
  if (!btn || btn.dataset.wired === "1") return;
  btn.dataset.wired = "1";
  applyThemePref(localStorage.getItem("deskline_theme") || "system");
  btn.addEventListener("click", () => {
    const cur = localStorage.getItem("deskline_theme") || "system";
    const idx = THEME_CYCLE.indexOf(cur);
    const next = THEME_CYCLE[(idx < 0 ? 0 : idx + 1) % THEME_CYCLE.length];
    persistTheme(next);
  });
  try {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      const cur = localStorage.getItem("deskline_theme") || "system";
      if (cur === "system") applyThemePref("system");
    });
  } catch (_) {}
}

async function refreshLicenseStatus() {
  try {
    const st = await api("/api/license/status");
    applyEntitlements(st.entitlements);
    return st;
  } catch (_) {
    return null;
  }
}

async function maybeShowOnboarding() {
  const st = await refreshLicenseStatus();
  if (!st || st.onboarding_done) return;
  const modal = document.getElementById("onboardModal");
  if (modal) modal.hidden = false;
}

function setActiveTab(name, { syncHash = true } = {}) {
  const aliases = { activities: "usage", apps: "usage", sites: "usage" };
  const tab = aliases[name] || name;
  document.querySelectorAll(".tab").forEach((t) => {
    const on = t.dataset.tab === tab;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", on ? "true" : "false");
  });
  document.querySelectorAll(".panel").forEach((p) => {
    p.classList.toggle("active", p.id === `panel-${tab}`);
  });
  syncNavMoreState(tab);
  if (aliases[name]) setUsageSlice(name);
  if (syncHash) {
    const next = `#${tab}`;
    if (location.hash !== next) {
      history.replaceState(null, "", next);
    }
  }
  if (tab === "shots") startShotsPolling();
  else stopShotsPolling();
  if (tab === "meetings") refreshMeetings().catch(() => {});
}

const NAV_MORE_TABS = {
  meetings: "Звонки",
  shots: "Скриншоты",
  ratings: "Рейтинги",
};

function closeNavMore() {
  const toggle = document.getElementById("navMoreToggle");
  const menu = document.getElementById("navMoreMenu");
  if (menu) menu.hidden = true;
  if (toggle) toggle.setAttribute("aria-expanded", "false");
}

function syncNavMoreState(tab) {
  const toggle = document.getElementById("navMoreToggle");
  if (!toggle) return;
  const label = NAV_MORE_TABS[tab];
  const inMore = Boolean(label);
  toggle.classList.toggle("is-active-parent", inMore);
  toggle.innerHTML = inMore
    ? `${escapeHtml(label)}<span class="nav-more-caret" aria-hidden="true">▾</span>`
    : `Ещё<span class="nav-more-caret" aria-hidden="true">▾</span>`;
  closeNavMore();
}

function wireNavMore() {
  const wrap = document.getElementById("navMore");
  const toggle = document.getElementById("navMoreToggle");
  const menu = document.getElementById("navMoreMenu");
  if (!wrap || !toggle || !menu || wrap.dataset.wired === "1") return;
  wrap.dataset.wired = "1";

  toggle.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    const open = menu.hidden;
    menu.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });

  document.addEventListener("click", (ev) => {
    if (!wrap.contains(ev.target)) closeNavMore();
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") closeNavMore();
  });
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


/** @type {Record<string, string>} last skeleton context per panel */
const skelContexts = {};

function skelLine(width = "80%", delay = 0) {
  return `<span class="skel-line shimmer" style="width:${width};animation-delay:${delay}s"></span>`;
}

function showSkeleton(el, kind, count = 6) {
  if (!el) return;
  el.setAttribute("aria-busy", "true");
  el.classList.add("is-skel");
  let html = "";
  if (kind === "kpi") {
    const n = count || 5;
    html = Array.from({ length: n }, (_, i) => {
      const d = i * 0.05;
      return `<article class="pulse-ov-card skel-block" aria-hidden="true">
        ${skelLine("44%", d)}
        ${skelLine("62%", d + 0.04)}
        <span class="skel-meter shimmer" style="animation-delay:${d + 0.08}s"></span>
      </article>`;
    }).join("");
  } else if (kind === "chart") {
    html = `<div class="skel-chart shimmer" aria-hidden="true"></div>`;
  } else if (kind === "bars") {
    const n = count || 7;
    html = `<div class="skel-bars" aria-hidden="true">${Array.from({ length: n }, (_, i) => {
      const h = 28 + ((i * 19) % 58);
      return `<div class="skel-bar-col"><div class="skel-bar shimmer" style="height:${h}%;animation-delay:${i * 0.06}s"></div></div>`;
    }).join("")}</div>`;
  } else if (kind === "list") {
    const tag = el.tagName === "OL" || el.tagName === "UL" ? "li" : "div";
    html = Array.from({ length: count || 6 }, (_, i) => {
      const d = i * 0.05;
      return `<${tag} class="skel-list-row" aria-hidden="true">
        <span class="skel-avatar shimmer" style="animation-delay:${d}s"></span>
        <div class="skel-list-copy">${skelLine("72%", d)}${skelLine("42%", d + 0.05)}</div>
        <span class="skel-meta shimmer" style="animation-delay:${d + 0.08}s"></span>
      </${tag}>`;
    }).join("");
  } else if (kind === "pie") {
    html = `<div class="skel-pie-layout" aria-hidden="true">
      <div class="skel-pie shimmer"></div>
      <div class="skel-pie-leg">${skelLine("64%", 0)}${skelLine("52%", 0.05)}${skelLine("40%", 0.1)}</div>
    </div>`;
  } else if (kind === "donut") {
    html = `<div class="skel-donut-layout" aria-hidden="true">
      <div class="skel-donut shimmer"></div>
      <div class="skel-pie-leg">${skelLine("70%", 0)}${skelLine("55%", 0.05)}${skelLine("45%", 0.1)}</div>
    </div>`;
  } else if (kind === "gantt") {
    html = `<div class="skel-gantt" aria-hidden="true">
      <div class="skel-gantt-track shimmer" style="width:92%"></div>
      <div class="skel-gantt-track shimmer" style="width:74%;animation-delay:.08s"></div>
      <div class="skel-gantt-track shimmer" style="width:58%;animation-delay:.16s"></div>
    </div>`;
  } else if (kind === "projects") {
    html = Array.from({ length: count || 4 }, (_, i) => {
      const d = i * 0.06;
      return `<div class="skel-project" aria-hidden="true">${skelLine("48%", d)}${skelLine("88%", d + 0.04)}${skelLine("66%", d + 0.08)}</div>`;
    }).join("");
  } else if (kind === "rating") {
    html = Array.from({ length: count || 5 }, (_, i) => {
      const d = i * 0.05;
      return `<div class="skel-rating-row" aria-hidden="true">
        <span class="skel-avatar shimmer" style="animation-delay:${d}s"></span>
        <div>
          ${skelLine("55%", d)}
          ${skelLine("36%", d + 0.04)}
          <div class="skel-rating-btns">
            <span class="skel-rating-btn shimmer" style="animation-delay:${d + 0.06}s"></span>
            <span class="skel-rating-btn shimmer" style="animation-delay:${d + 0.1}s"></span>
            <span class="skel-rating-btn shimmer" style="animation-delay:${d + 0.14}s"></span>
            <span class="skel-rating-btn shimmer" style="animation-delay:${d + 0.18}s"></span>
          </div>
        </div>
      </div>`;
    }).join("");
  } else if (kind === "shots") {
    html = Array.from({ length: count || 8 }, (_, i) => {
      const delay = (i % 4) * 0.08;
      return `<div class="shot shot-skel" aria-hidden="true">
        <div class="shot-skel-media shimmer" style="animation-delay:${delay}s"></div>
        <div class="shot-skel-cap">
          <span class="shot-skel-line shimmer" style="animation-delay:${delay + 0.04}s"></span>
          <span class="shot-skel-line shot-skel-line-short shimmer" style="animation-delay:${delay + 0.08}s"></span>
        </div>
      </div>`;
    }).join("");
  } else {
    html = `<div class="skel-chart shimmer" aria-hidden="true"></div>`;
  }
  el.innerHTML = html;
}

function markSkelContext(key, ctx) {
  skelContexts[key] = ctx;
}

function clearSkel(el) {
  if (!el) return;
  el.classList.remove("is-skel");
  el.removeAttribute("aria-busy");
}

function needsSkeleton(el, stateKey, contextKey, { force = false } = {}) {
  if (force) return true;
  if (!el) return false;
  if (el.classList.contains("is-skel")) return false;
  if (!contextKey) return !el.childElementCount || !skelContexts[stateKey];
  if (skelContexts[stateKey] !== contextKey) return true;
  return !el.childElementCount;
}

function renderKpis(summary, team) {
  const el = document.getElementById("kpiStrip");
  if (!el) return;
  clearSkel(el);
  const total = summary.total_sec || 0;
  const by = summary.by_category || {};
  const productive = by.productive || 0;
  const distracting = by.distracting || 0;
  const idle = summary.idle_sec || 0;
  const activePeople = (team || []).filter((m) => (m.total_sec || 0) > 60).length;
  const pctOf = (sec) => (total ? Math.round((sec / total) * 100) : 0);
  const items = [
    { label: "Всего учтено", value: fmtDur(total), pct: null, tone: "tracked" },
    { label: "В фокусе", value: fmtDur(productive), pct: pctOf(productive), tone: "productive" },
    { label: "Отвлечения", value: fmtDur(distracting), pct: pctOf(distracting), tone: "distracting" },
    { label: "Без ввода", value: fmtDur(idle), pct: pctOf(idle), tone: "idle" },
    {
      label: companyMode ? "Активные люди" : "Активность",
      value: companyMode ? String(activePeople || 0) : `${summary.activity_pct ?? 0}%`,
      pct: companyMode ? null : summary.activity_pct ?? 0,
      tone: "active",
    },
  ];
  el.innerHTML = items
    .map((it) => {
      const meter =
        it.pct == null
          ? ""
          : `<div class="pulse-ov-meter"><em>${it.pct}%</em><span><i style="width:${Math.max(it.pct, it.pct ? 3 : 0)}%"></i></span></div>`;
      return `<article class="pulse-ov-card ${it.tone}">
        <span class="pulse-ov-label">${it.label}</span>
        <strong class="pulse-ov-value">${it.value}</strong>
        ${meter}
      </article>`;
    })
    .join("");
}

function appsCupSvg(rank) {
  const tone = rank === 1 ? "gold" : rank === 2 ? "silver" : "bronze";
  return `<svg class="apps-cup apps-cup-${tone}" viewBox="0 0 48 48" width="32" height="32" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id="cupGrad-${tone}" x1="12" y1="8" x2="36" y2="40" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="currentColor" stop-opacity="0.92"/>
        <stop offset="55%" stop-color="currentColor"/>
        <stop offset="100%" stop-color="currentColor" stop-opacity="0.72"/>
      </linearGradient>
    </defs>
    <circle class="apps-cup-halo" cx="24" cy="20" r="15" />
    <path class="apps-cup-bowl" fill="url(#cupGrad-${tone})" d="M15.5 9.5h17a2.5 2.5 0 0 1 2.5 2.5v3.2c0 7.1-4.7 11.8-11 11.8s-11-4.7-11-11.8V12a2.5 2.5 0 0 1 2.5-2.5z"/>
    <path class="apps-cup-rim" fill="currentColor" d="M14.2 9.2h19.6a1.2 1.2 0 0 1 0 2.4H14.2a1.2 1.2 0 0 1 0-2.4z"/>
    <path class="apps-cup-handle" d="M15.6 12.2H11c-2.2 0-3.6 2-3 4.1.8 2.8 3.2 4.2 6.4 4.4"/>
    <path class="apps-cup-handle" d="M32.4 12.2H37c2.2 0 3.6 2 3 4.1-.8 2.8-3.2 4.2-6.4 4.4"/>
    <rect class="apps-cup-stem" x="21.6" y="26.8" width="4.8" height="7.2" rx="1.4" fill="currentColor"/>
    <path class="apps-cup-base" fill="currentColor" d="M17 36.2h14a2.2 2.2 0 0 1 0 4.4H17a2.2 2.2 0 0 1 0-4.4z"/>
    <circle class="apps-cup-gem" cx="24" cy="17.5" r="2.2"/>
  </svg>`;
}

/** Browsers / RDP shells — Overview should show what happened inside, not the shell. */
const SHELL_APP_EXES = new Set([
  "chrome.exe",
  "msedge.exe",
  "firefox.exe",
  "browser.exe",
  "opera.exe",
  "brave.exe",
  "vivaldi.exe",
  "mstsc.exe",
  "msrdc.exe",
]);

let lastTopPulseSummary = null;
let topPulseItems = [];

function isShellAppRow(row) {
  const exe = String(row?.app_name || "").trim().toLowerCase();
  if (SHELL_APP_EXES.has(exe)) return true;
  const kind = String(row?.kind || "").toLowerCase();
  if (kind === "remote") return true;
  const name = String(row?.name || "").toLowerCase();
  return name === "remote desktop" || name === "microsoft edge" || name === "google chrome";
}

function formatActivityDisplayName(name) {
  const raw = String(name || "").trim();
  const m = /^RDP\s*·\s*(.+)$/i.exec(raw);
  if (m) return m[1].trim() || raw;
  return raw || "Активность";
}

function shortViaLabel(parentName, appName) {
  const n = String(parentName || "").trim();
  if (!n) return "";
  const exe = String(appName || "").toLowerCase();
  if (exe === "mstsc.exe" || exe === "msrdc.exe" || /^remote desktop$/i.test(n)) return "удалёнка";
  if (/microsoft edge/i.test(n) || exe === "msedge.exe") return "Edge";
  if (/google chrome/i.test(n) || exe === "chrome.exe") return "Chrome";
  if (/yandex/i.test(n) || exe === "browser.exe") return "Яндекс";
  if (/firefox/i.test(n)) return "Firefox";
  if (/opera/i.test(n)) return "Opera";
  if (/brave/i.test(n)) return "Brave";
  return n;
}

/** Prefer sites / RDP hosts over bare browser & Remote Desktop shells. */
function topFocusCandidates(summary) {
  const minSec = 30;
  const grouped = summary.by_app_grouped || [];
  const rows = grouped.length
    ? grouped
    : (summary.by_app || []).map((r) => ({ ...r, children: [] }));
  const bag = [];

  for (const row of rows) {
    const children = (row.children || []).filter((c) => (c.sec || 0) >= minSec);
    const shell = isShellAppRow(row);
    if (shell || children.length) {
      if (children.length) {
        for (const c of children) {
          bag.push({
            name: formatActivityDisplayName(c.name),
            rawName: c.name || "",
            parentName: row.name || "",
            parentApp: row.app_name || "",
            sec: c.sec || 0,
            icon_url: c.icon_url || row.icon_url || "",
            category: c.category || row.category || "neutral",
            via: shortViaLabel(row.name, row.app_name),
            kind: c.kind || row.kind || "",
            site: c.site || "",
          });
        }
        continue;
      }
      if (shell) {
        // No nested detail yet — don't promote empty Edge/RDP shells to the podium.
        continue;
      }
    }
    if ((row.sec || 0) < minSec) continue;
    bag.push({
      name: row.name || row.app_name || "Приложение",
      rawName: row.name || "",
      parentName: row.name || "",
      parentApp: row.app_name || "",
      sec: row.sec || 0,
      icon_url: row.icon_url || "",
      category: row.category || "neutral",
      via: "",
      kind: row.kind || "",
      site: "",
    });
  }

  // Fallback: if shells were skipped and bag is thin, use by_activity directly.
  if (bag.length < 3 && (summary.by_activity || []).length) {
    const seen = new Set(bag.map((b) => String(b.name).toLowerCase()));
    for (const a of summary.by_activity || []) {
      if ((a.sec || 0) < minSec) continue;
      const name = formatActivityDisplayName(a.name);
      const key = name.toLowerCase();
      if (seen.has(key)) continue;
      if (isShellAppRow(a) && !a.site && !/^RDP\s*·/i.test(String(a.name || ""))) continue;
      seen.add(key);
      const parentGuess =
        a.app_name === "mstsc.exe" || a.app_name === "msrdc.exe"
          ? "Remote Desktop"
          : a.app_name === "msedge.exe"
            ? "Microsoft Edge"
            : a.app_name === "chrome.exe"
              ? "Google Chrome"
              : "";
      bag.push({
        name,
        rawName: a.name || "",
        parentName: parentGuess,
        parentApp: a.app_name || "",
        sec: a.sec || 0,
        icon_url: a.icon_url || "",
        category: a.category || "neutral",
        via: shortViaLabel(parentGuess, a.app_name),
        kind: a.kind || "",
        site: a.site || "",
      });
    }
  }

  const merged = new Map();
  for (const it of bag) {
    const key = String(it.name || "").toLowerCase();
    const prev = merged.get(key);
    if (!prev) {
      merged.set(key, { ...it });
      continue;
    }
    prev.sec = Math.round((prev.sec + it.sec) * 10) / 10;
    if (!prev.icon_url && it.icon_url) prev.icon_url = it.icon_url;
    if (!prev.via && it.via) prev.via = it.via;
    if (!prev.parentName && it.parentName) prev.parentName = it.parentName;
    if (!prev.parentApp && it.parentApp) prev.parentApp = it.parentApp;
    if (!prev.rawName && it.rawName) prev.rawName = it.rawName;
  }
  return [...merged.values()].sort((a, b) => b.sec - a.sec);
}

function resolveActivityBreakdown(summary, item) {
  const grouped = summary?.by_app_grouped || [];
  const want = String(item?.rawName || item?.name || "").toLowerCase();
  const wantDisplay = String(item?.name || "").toLowerCase();
  let parent =
    grouped.find((g) => {
      const kids = g.children || [];
      return kids.some((c) => {
        const cn = String(c.name || "").toLowerCase();
        const cd = formatActivityDisplayName(c.name).toLowerCase();
        return cn === want || cd === wantDisplay || cd === want;
      });
    }) || null;
  if (!parent && item?.parentApp) {
    parent = grouped.find(
      (g) => String(g.app_name || "").toLowerCase() === String(item.parentApp).toLowerCase()
    ) || null;
  }
  if (!parent && item?.parentName) {
    parent =
      grouped.find(
        (g) => String(g.name || "").toLowerCase() === String(item.parentName).toLowerCase()
      ) || null;
  }
  if (!parent) {
    parent =
      grouped.find(
        (g) => String(g.name || "").toLowerCase() === wantDisplay || String(g.name || "").toLowerCase() === want
      ) || null;
  }

  const children = (parent?.children || []).filter((c) => (c.sec || 0) >= 30);
  if (parent && children.length) {
    return {
      title: item.name,
      kicker: parent.name || item.via || "Расшифровка",
      lead: `${fmtDur(parent.sec || item.sec)} в «${parent.name || item.name}» сегодня`,
      focusName: item.name,
      rows: children
        .slice()
        .sort((a, b) => (b.sec || 0) - (a.sec || 0))
        .map((c) => ({
          name: formatActivityDisplayName(c.name),
          sec: c.sec || 0,
          icon_url: c.icon_url || parent.icon_url || "",
          category: c.category || parent.category || "neutral",
          active:
            formatActivityDisplayName(c.name).toLowerCase() === wantDisplay ||
            String(c.name || "").toLowerCase() === want,
        })),
    };
  }

  return {
    title: item.name,
    kicker: item.via || "Расшифровка",
    lead: `${fmtDur(item.sec)} · ${CAT_LABELS[item.category] || CAT_LABELS.neutral}`,
    focusName: item.name,
    rows: [
      {
        name: item.name,
        sec: item.sec || 0,
        icon_url: item.icon_url || "",
        category: item.category || "neutral",
        active: true,
      },
    ],
  };
}

function setBodyScrollLock(locked) {
  document.body.classList.toggle("is-scroll-locked", !!locked);
  document.documentElement.classList.toggle("is-scroll-locked", !!locked);
  document.body.style.overflow = locked ? "hidden" : "";
  document.documentElement.style.overflow = locked ? "hidden" : "";
}

function closeActivityDetail() {
  const modal = document.getElementById("activityDetailModal");
  if (!modal || modal.hidden) {
    setBodyScrollLock(false);
    return;
  }
  modal.hidden = true;
  setBodyScrollLock(false);
}

function openActivityDetail(item) {
  const modal = document.getElementById("activityDetailModal");
  const title = document.getElementById("activityDetailTitle");
  const kicker = document.getElementById("activityDetailKicker");
  const lead = document.getElementById("activityDetailLead");
  const list = document.getElementById("activityDetailList");
  if (!modal || !title || !list || !item) return;
  const detail = resolveActivityBreakdown(lastTopPulseSummary || {}, item);
  const total = Math.max(
    1,
    detail.rows.reduce((s, r) => s + (r.sec || 0), 0)
  );
  title.textContent = detail.title;
  if (kicker) kicker.textContent = detail.kicker || "Расшифровка";
  if (lead) lead.textContent = detail.lead || "";
  list.innerHTML = detail.rows
    .map((r) => {
      const share = Math.round(((r.sec || 0) / total) * 100);
      const cat = CAT_LABELS[r.category] || CAT_LABELS.neutral;
      const catColor = CAT_COLORS[r.category] || CAT_COLORS.neutral;
      return `<li class="activity-detail-row${r.active ? " is-active" : ""}">
        ${iconImgHtml(r.icon_url, 28)}
        <span class="activity-detail-copy">
          <strong>${escapeHtml(r.name)}</strong>
          <em style="color:${catColor}">${escapeHtml(cat)}</em>
        </span>
        <span class="activity-detail-bar" aria-hidden="true"><i style="width:${Math.max(6, share)}%;background:${catColor}"></i></span>
        <span class="activity-detail-meta">${fmtDur(r.sec)} · ${share}%</span>
      </li>`;
    })
    .join("");
  modal.hidden = false;
  setBodyScrollLock(true);
}

function wireTopAppsPulse(el) {
  if (!el || el.dataset.topAppsWired === "1") return;
  el.dataset.topAppsWired = "1";
  el.addEventListener("click", (ev) => {
    const hit = ev.target.closest("[data-pulse-idx]");
    if (!hit || !el.contains(hit)) return;
    ev.preventDefault();
    const idx = Number(hit.dataset.pulseIdx);
    const item = topPulseItems[idx];
    if (item) openActivityDetail(item);
  });
  el.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    const hit = ev.target.closest("[data-pulse-idx]");
    if (!hit || !el.contains(hit)) return;
    ev.preventDefault();
    const idx = Number(hit.dataset.pulseIdx);
    const item = topPulseItems[idx];
    if (item) openActivityDetail(item);
  });
}

function renderTopAppsPulse(summary) {
  const el = document.getElementById("topAppsPulse");
  if (!el) return;
  clearSkel(el);
  lastTopPulseSummary = summary || null;
  const dayTotal = Math.max(1, Number(summary.total_sec) || 0);
  const apps = topFocusCandidates(summary)
    .slice(0, 5)
    .map((r, i) => ({
      ...r,
      rank: i + 1,
      share: Math.round(((r.sec || 0) / dayTotal) * 100),
    }));
  topPulseItems = apps;
  if (!apps.length) {
    el.innerHTML = `<p class="hint">Пока нет данных по активностям за сегодня.</p>`;
    return;
  }
  const top3 = apps.slice(0, 3);
  // Classic podium order: silver · gold · bronze
  const slots =
    top3.length >= 2
      ? [top3[1] || null, top3[0] || null, top3[2] || null]
      : [null, top3[0] || null, null];
  const podium = slots
    .map((app) => {
      if (!app) return `<li class="apps-podium-slot is-empty" aria-hidden="true"></li>`;
      const placeClass = app.rank === 1 ? "is-first" : app.rank === 2 ? "is-second" : "is-third";
      const cat = CAT_LABELS[app.category] || CAT_LABELS.neutral;
      const catColor = CAT_COLORS[app.category] || CAT_COLORS.neutral;
      const via = app.via
        ? `<span class="apps-podium-via">${escapeHtml(app.via)}</span>`
        : "";
      const idx = app.rank - 1;
      return `<li class="apps-podium-slot ${placeClass}">
        <button type="button" class="apps-podium-card" data-pulse-idx="${idx}" aria-label="Расшифровка: ${escapeHtml(app.name)}">
          <div class="apps-podium-trophy">${appsCupSvg(app.rank)}</div>
          <div class="apps-podium-icon">${iconImgHtml(app.icon_url, app.rank === 1 ? 40 : 32)}</div>
          <div class="apps-podium-name" title="${escapeHtml(app.name)}">${escapeHtml(app.name)}</div>
          ${via}
          <div class="apps-podium-meta">
            <strong>${fmtDur(app.sec)}</strong>
            <span>${app.share}% · <em style="color:${catColor}">${escapeHtml(cat)}</em></span>
          </div>
          <div class="apps-podium-plinth" aria-hidden="true"><span>#${app.rank}</span></div>
        </button>
      </li>`;
    })
    .join("");
  const runners = apps.slice(3);
  const runnersHtml = runners.length
    ? `<ol class="apps-runners" start="4">${runners
        .map((app) => {
          const via = app.via ? `<em class="apps-runner-via">${escapeHtml(app.via)}</em>` : "";
          const idx = app.rank - 1;
          return `<li>
            <button type="button" class="apps-runner" data-pulse-idx="${idx}" aria-label="Расшифровка: ${escapeHtml(app.name)}">
              <span class="apps-runner-rank">#${app.rank}</span>
              ${iconImgHtml(app.icon_url, 28)}
              <span class="apps-runner-copy">
                <span class="apps-runner-name">${escapeHtml(app.name)}</span>
                ${via}
              </span>
              <span class="apps-runner-bar" aria-hidden="true"><i style="width:${Math.max(8, app.share)}%;background:${CAT_COLORS[app.category] || CAT_COLORS.neutral}"></i></span>
              <span class="apps-runner-meta">${fmtDur(app.sec)} · ${app.share}%</span>
            </button>
          </li>`;
        })
        .join("")}</ol>`
    : "";
  el.innerHTML = `<div class="apps-top">
    <ol class="apps-podium">${podium}</ol>
    ${runnersHtml}
  </div>`;
  wireTopAppsPulse(el);
}

function renderTopProjectsPulse(summary) {
  const el = document.getElementById("topProjectsPulse");
  if (!el) return;
  clearSkel(el);
  const byProj = summary.by_project || [];
  const named = byProj
    .map((row) => {
      const p = (projectCache || []).find((x) => String(x.id) === String(row.project_id));
      return {
        id: row.project_id,
        name: p?.name || (row.project_id == null ? "Без проекта" : `Проект #${row.project_id}`),
        color: p?.color || "#1f6b56",
        sec: row.sec || 0,
      };
    })
    .filter((r) => r.sec >= 30)
    .slice(0, 5);
  if (!named.length) {
    el.innerHTML = `<p class="hint">Пока нет времени по проектам. Выберите проект в шапке.</p>`;
    return;
  }
  const total = named.reduce((s, r) => s + r.sec, 0) || 1;
  const cx = 60;
  const cy = 60;
  let angle = 0;
  const paths = named
    .map((r) => {
      const sweep = (r.sec / total) * 360;
      const d = donutSegmentPath(cx, cy, 52, 34, angle, angle + sweep);
      angle += sweep;
      return d ? `<path d="${d}" fill="${r.color}" stroke="#fff" stroke-width="1.5"/>` : "";
    })
    .join("");
  const legend = named
    .map(
      (r) =>
        `<li><i style="background:${r.color}"></i><span>${escapeHtml(r.name)}</span><b>${fmtDur(r.sec)}</b></li>`
    )
    .join("");
  el.innerHTML = `<div class="pulse-proj-layout">
    <ul class="pulse-proj-legend">${legend}</ul>
    <div class="pulse-proj-donut">
      <svg viewBox="0 0 120 120" width="150" height="150" aria-hidden="true">
        <circle cx="60" cy="60" r="43" fill="none" stroke="rgba(31,107,86,0.08)" stroke-width="16"/>
        ${paths}
      </svg>
      <div class="donut-center">
        <strong>${fmtDur(total)}</strong>
        <span>всего</span>
      </div>
    </div>
  </div>`;
}

function renderQuietPeople(team) {
  const quiet = document.getElementById("quietList");
  const gauges = document.getElementById("teamGauges");
  const title = document.getElementById("quietTitle");
  if (!quiet || !gauges) return;
  clearSkel(quiet);
  clearSkel(gauges);
  const idlePeople = (team || []).filter((m) => !(m.total_sec > 60));
  const active = (team || []).filter((m) => m.total_sec > 60);
  if (companyMode && idlePeople.length) {
    title.textContent = "Ещё не трекали";
    quiet.hidden = false;
    gauges.hidden = active.length === 0;
    quiet.innerHTML = idlePeople
      .map(
        (m) => `<div class="pulse-quiet-row">
          <span class="team-avatar" style="background:${m.color || "#1f6b56"}">${escapeHtml(m.initials || "?")}</span>
          <div>
            <strong>${escapeHtml(m.display_name || "—")}</strong>
            <em>Сегодня тишина</em>
          </div>
        </div>`
      )
      .join("");
    if (active.length) renderTeamGauges(active);
    else gauges.innerHTML = "";
  } else {
    title.textContent = "Кто в фокусе";
    quiet.hidden = true;
    quiet.innerHTML = "";
    gauges.hidden = false;
    renderTeamGauges(team);
  }
}

function renderTeamGauges(team) {
  const el = document.getElementById("teamGauges");
  if (!el) return;
  const rows = team || [];
  if (!rows.length) {
    el.innerHTML = `<p class="hint">Пока нет данных по людям.</p>`;
    return;
  }
  el.innerHTML = rows
    .map((m) => {
      const pct = Math.max(0, Math.min(100, Math.round(Number(m.focus_pct) || 0)));
      const color = m.color || "#1f6b56";
      const name = escapeHtml(m.display_name || "—");
      const initials = escapeHtml(m.initials || "?");
      const c = 2 * Math.PI * 15.9155;
      const dash = (pct / 100) * c;
      const selected = String(m.id) === String(filterEmployeeId) ? " is-selected" : "";
      return `<button type="button" class="team-gauge${selected}" data-employee-id="${m.id}" title="${name}: ${pct}%">
        <div class="team-gauge-ring" style="--ring:${color}">
          <svg viewBox="0 0 36 36" aria-hidden="true">
            <circle class="gauge-track" cx="18" cy="18" r="15.9155" fill="none" stroke-width="2.8"/>
            <circle class="gauge-value" cx="18" cy="18" r="15.9155" fill="none" stroke="${color}" stroke-width="2.8"
              stroke-linecap="round" stroke-dasharray="${dash.toFixed(2)} ${(c - dash).toFixed(2)}" transform="rotate(-90 18 18)"/>
          </svg>
          <span class="team-gauge-pct">${pct}%</span>
        </div>
        <span class="team-person">
          <span class="team-avatar" style="background:${color}">${initials}</span>
          <span class="team-name">${name}</span>
        </span>
      </button>`;
    })
    .join("");
  el.querySelectorAll("[data-employee-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-employee-id") || "";
      filterEmployeeId = filterEmployeeId === id ? "" : id;
      const sel = document.getElementById("filterEmployeeToday");
      if (sel) sel.value = filterEmployeeId;
      lastSummaryKey = "";
      await refreshSummary();
    });
  });
}

function dayBoundsFromRows(rows, fallbackIso) {
  let day = fallbackIso || selectedDayIso || null;
  if (!day && rows && rows.length) {
    const d = new Date(rows[0].started_at);
    day = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }
  if (!day) {
    const n = new Date();
    day = `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}-${String(n.getDate()).padStart(2, "0")}`;
  }
  const dayStart = new Date(`${day}T00:00:00`);
  const dayEnd = new Date(dayStart.getTime() + 24 * 3600 * 1000);
  return { day, dayStartMs: dayStart.getTime(), dayEndMs: dayEnd.getTime(), spanMs: 24 * 3600 * 1000 };
}

/** Crop the day strip to where work actually happened (optional full-day mode). */
function activityViewBounds(rows, dayStartMs, dayEndMs, mode = "active") {
  if (mode !== "active") {
    return { viewStartMs: dayStartMs, viewEndMs: dayEndMs, spanMs: dayEndMs - dayStartMs };
  }
  let min = Infinity;
  let max = -Infinity;
  for (const r of rows || []) {
    const a = new Date(r.started_at).getTime();
    const b = new Date(r.ended_at || Date.now()).getTime();
    const clipped = clipToDay(a, b, dayStartMs, dayEndMs);
    if (!clipped) continue;
    min = Math.min(min, clipped.start);
    max = Math.max(max, clipped.end);
  }
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) {
    return { viewStartMs: dayStartMs, viewEndMs: dayEndMs, spanMs: dayEndMs - dayStartMs };
  }
  const pad = 20 * 60 * 1000;
  const step = 30 * 60 * 1000;
  let viewStartMs = Math.max(dayStartMs, min - pad);
  let viewEndMs = Math.min(dayEndMs, max + pad);
  viewStartMs = dayStartMs + Math.floor((viewStartMs - dayStartMs) / step) * step;
  viewEndMs = dayStartMs + Math.ceil((viewEndMs - dayStartMs) / step) * step;
  if (viewEndMs <= viewStartMs) {
    viewEndMs = Math.min(dayEndMs, viewStartMs + 2 * 3600 * 1000);
  }
  // Keep at least ~2 hours so tiny days aren't a single blob.
  if (viewEndMs - viewStartMs < 2 * 3600 * 1000) {
    const mid = (min + max) / 2;
    viewStartMs = Math.max(dayStartMs, mid - 3600 * 1000);
    viewEndMs = Math.min(dayEndMs, mid + 3600 * 1000);
    viewStartMs = dayStartMs + Math.floor((viewStartMs - dayStartMs) / step) * step;
    viewEndMs = dayStartMs + Math.ceil((viewEndMs - dayStartMs) / step) * step;
  }
  return {
    viewStartMs,
    viewEndMs,
    spanMs: Math.max(step, viewEndMs - viewStartMs),
  };
}

function pctOnDay(ms, dayStartMs, spanMs) {
  return ((ms - dayStartMs) / spanMs) * 100;
}

function clipToDay(a, b, dayStartMs, dayEndMs) {
  const start = Math.max(a, dayStartMs);
  const end = Math.min(b, dayEndMs);
  if (end <= start) return null;
  return { start, end };
}

function fmtClockMs(ms) {
  return new Date(ms).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

/** Untracked gaps within the day (between / around session coverage). */
function voidGapsForDay(rows, dayStartMs, dayEndMs) {
  const intervals = [];
  for (const r of rows || []) {
    const a = new Date(r.started_at).getTime();
    const b = new Date(r.ended_at || Date.now()).getTime();
    const clipped = clipToDay(a, b, dayStartMs, dayEndMs);
    if (clipped) intervals.push(clipped);
  }
  intervals.sort((a, b) => a.start - b.start);
  const merged = [];
  for (const iv of intervals) {
    if (!merged.length || iv.start > merged[merged.length - 1].end) {
      merged.push({ start: iv.start, end: iv.end });
    } else {
      merged[merged.length - 1].end = Math.max(merged[merged.length - 1].end, iv.end);
    }
  }
  const gaps = [];
  let cursor = dayStartMs;
  for (const iv of merged) {
    if (iv.start > cursor + 1000) gaps.push({ start: cursor, end: iv.start });
    cursor = Math.max(cursor, iv.end);
  }
  if (dayEndMs > cursor + 1000) gaps.push({ start: cursor, end: dayEndMs });
  return gaps;
}

function bindPulseDayScrub(track, dayStartMs, spanMs) {
  if (!track) return;
  let tip = track.querySelector(".pulse-scrub-tip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "pulse-scrub-tip";
    tip.hidden = true;
    track.appendChild(tip);
  }
  const place = (ev) => {
    const rect = track.getBoundingClientRect();
    if (!rect.width) return;
    const t = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
    const ms = dayStartMs + t * spanMs;
    tip.hidden = false;
    tip.textContent = fmtClockMs(ms);
    tip.style.left = `${t * 100}%`;
  };
  track.addEventListener("mousemove", place);
  track.addEventListener("mouseenter", place);
  track.addEventListener("mouseleave", () => {
    tip.hidden = true;
  });
}

function donutSegmentPath(cx, cy, rOut, rIn, a0, a1) {
  const sweep = Math.max(0, Math.min(359.999, a1 - a0));
  if (sweep < 0.2) return "";
  const rad = (deg) => ((deg - 90) * Math.PI) / 180;
  const pt = (r, deg) => [cx + r * Math.cos(rad(deg)), cy + r * Math.sin(rad(deg))];
  const [x0, y0] = pt(rOut, a0);
  const [x1, y1] = pt(rOut, a0 + sweep);
  const [x2, y2] = pt(rIn, a0 + sweep);
  const [x3, y3] = pt(rIn, a0);
  const large = sweep > 180 ? 1 : 0;
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${rOut} ${rOut} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)} L${x2.toFixed(2)} ${y2.toFixed(2)} A${rIn} ${rIn} 0 ${large} 0 ${x3.toFixed(2)} ${y3.toFixed(2)} Z`;
}

function wireDonutHover(root) {
  if (!root) return;
  const segs = [...root.querySelectorAll(".donut-seg")];
  const legs = [...root.querySelectorAll(".pie-legend li")];
  const centerPct = root.querySelector(".donut-center strong");
  const centerLabel = root.querySelector(".donut-center span");
  const basePct = centerPct?.textContent || "";
  const baseLabel = centerLabel?.textContent || "";

  const setActive = (key, on) => {
    segs.forEach((s) => {
      const match = s.dataset.key === key;
      s.classList.toggle("is-hot", on && match);
      s.classList.toggle("is-dim", on && !match);
    });
    legs.forEach((li) => {
      const match = li.dataset.key === key;
      li.classList.toggle("is-hot", on && match);
      li.classList.toggle("is-dim", on && !match);
    });
    if (on) {
      const seg = segs.find((s) => s.dataset.key === key);
      if (seg && centerPct && centerLabel) {
        centerPct.textContent = seg.dataset.dur || `${seg.dataset.pct}%`;
        centerLabel.textContent = `${seg.dataset.label || ""} · ${seg.dataset.pct}%`;
      }
    } else if (centerPct && centerLabel) {
      centerPct.textContent = basePct;
      centerLabel.textContent = baseLabel;
    }
  };

  segs.forEach((seg) => {
    seg.addEventListener("pointerenter", () => setActive(seg.dataset.key, true));
    seg.addEventListener("pointerleave", () => setActive(seg.dataset.key, false));
    seg.addEventListener("focus", () => setActive(seg.dataset.key, true));
    seg.addEventListener("blur", () => setActive(seg.dataset.key, false));
  });
  legs.forEach((li) => {
    li.addEventListener("pointerenter", () => setActive(li.dataset.key, true));
    li.addEventListener("pointerleave", () => setActive(li.dataset.key, false));
  });
}

function pieSignature(slices, total, emptyText) {
  const usable = (slices || []).filter((s) => (s.sec || 0) > 0);
  if (!usable.length || !total) return `empty:${emptyText || "Пока нет данных."}`;
  return JSON.stringify({
    totalMin: Math.floor(total / 60),
    slices: usable.map((s) => [
      String(s.key || s.label || ""),
      Math.floor((s.sec || 0) / 60),
      s.color || "",
      s.label || "",
    ]),
  });
}

function renderPieChart(el, slices, total, emptyText) {
  if (!el) return;
  const wasSkel = el.classList.contains("is-skel");
  clearSkel(el);
  const usable = (slices || [])
    .filter((s) => (s.sec || 0) > 0)
    .slice()
    .sort((a, b) => (b.sec || 0) - (a.sec || 0));
  const sig = pieSignature(usable, total, emptyText);
  if (el.dataset.pieSig === sig && !wasSkel) return;
  const animateEnter = !el.dataset.pieSig;
  el.dataset.pieSig = sig;

  if (!usable.length || !total) {
    el.innerHTML = `<p class="hint">${emptyText || "Пока нет данных."}</p>`;
    return;
  }
  const cx = 110;
  const cy = 110;
  const rOut = 96;
  const rIn = 58;
  let angle = 0;
  const paths = usable
    .map((s, idx) => {
      const sweep = (s.sec / total) * 360;
      const a0 = angle;
      const a1 = angle + sweep;
      angle = a1;
      const d = donutSegmentPath(cx, cy, rOut, rIn, a0, a1);
      if (!d) return "";
      const mid = a0 + sweep / 2;
      const share = Math.round((s.sec / total) * 100);
      const key = String(s.key || s.label || idx);
      return `<path class="donut-seg" data-key="${escapeHtml(key)}" data-pct="${share}" data-label="${escapeHtml(s.label)}" data-dur="${escapeHtml(fmtDur(s.sec))}" data-mid="${mid.toFixed(2)}"
        d="${d}" fill="${s.color}" tabindex="0" role="img"
        aria-label="${escapeHtml(s.label)}: ${fmtDur(s.sec)}, ${share}%" style="--i:${idx}"/>`;
    })
    .join("");
  const glowId = `donutGlow-${el.id || "pie"}`;
  const enterClass = animateEnter ? " is-enter" : "";
  el.innerHTML = `<div class="pie-layout">
    <div class="donut-wrap" role="group" aria-label="Диаграмма">
      <svg class="donut-svg" viewBox="0 0 220 220" width="220" height="220">
        <defs>
          <filter id="${glowId}" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="6" stdDeviation="6" flood-color="#15241f" flood-opacity="0.12"/>
          </filter>
        </defs>
        <circle class="donut-track" cx="110" cy="110" r="77" fill="none"/>
        <g class="donut-segs${enterClass}" filter="url(#${glowId})">${paths}</g>
      </svg>
      <div class="donut-center" data-center-mode="total">
        <strong>${fmtDur(total)}</strong>
        <span>всего</span>
      </div>
    </div>
    <ul class="pie-legend">
      ${usable
        .map((s, idx) => {
          const share = Math.round((s.sec / total) * 100);
          const key = String(s.key || s.label || idx);
          return `<li data-key="${escapeHtml(key)}">
            <span class="pie-swatch" style="background:${s.color}"></span>
            <span class="pie-name">${escapeHtml(s.label)}</span>
            <span class="pie-meta">${fmtDur(s.sec)} · ${share}%</span>
          </li>`;
        })
        .join("")}
    </ul>
  </div>`;
  wireDonutHover(el);
  const savedScale = Number.parseFloat(getComputedStyle(el).getPropertyValue("--chart-scale") || "1");
  if (Number.isFinite(savedScale) && savedScale !== 1) {
    applyChartScale(el, savedScale, { persist: false });
  } else {
    const wrap = el.querySelector(".donut-wrap");
    if (wrap) wrap.style.setProperty("--chart-scale", getComputedStyle(el).getPropertyValue("--chart-scale").trim() || "1");
  }
}

function categoryPieSlices(byCategory) {
  return [
    {
      key: "productive",
      label: CAT_LABELS.productive,
      sec: byCategory.productive || 0,
      color: CAT_COLORS.productive,
    },
    {
      key: "neutral",
      label: CAT_LABELS.neutral,
      sec: byCategory.neutral || 0,
      color: CAT_COLORS.neutral,
    },
    {
      key: "distracting",
      label: CAT_LABELS.distracting,
      sec: byCategory.distracting || 0,
      color: CAT_COLORS.distracting,
    },
  ];
}

function kindPieSlices(byKind) {
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
  return Object.entries(byKind || {})
    .map(([k, sec], i) => ({
      key: k,
      label: KIND_LABELS[k] || k,
      sec,
      color: KIND_COLORS[i % KIND_COLORS.length],
    }))
    .filter((r) => r.sec >= 60)
    .sort((a, b) => b.sec - a.sec)
    .slice(0, 8);
}

function renderDaySummaryLine(summary, { gated = false } = {}) {
  const el = document.getElementById("daySummaryLine");
  if (!el) return;
  if (gated) {
    el.textContent = "История дальше Free-лимита — доступно в Pro";
    return;
  }
  const total = summary?.total_sec || 0;
  if (!total) {
    el.textContent = `${formatDayTitle(selectedDayIso)} · пока нет сессий`;
    return;
  }
  const focus = summary.focus_pct ?? 0;
  const active = summary.activity_pct ?? 0;
  el.textContent = `${formatDayTitle(selectedDayIso)} · ${fmtDur(total)} · активно ${active}% · фокус ${focus}%`;
}

function weekdayShort(isoDay) {
  const d = new Date(`${isoDay}T12:00:00`);
  return d.toLocaleDateString("ru-RU", { weekday: "short", day: "numeric" });
}

function niceHoursCeiling(sec) {
  const h = Math.max(sec / 3600, 1);
  if (h <= 4) return Math.ceil(h);
  if (h <= 8) return Math.ceil(h / 2) * 2;
  if (h <= 12) return Math.ceil(h / 3) * 3;
  if (h <= 24) return Math.ceil(h / 4) * 4;
  return Math.ceil(h / 6) * 6;
}

/** @type {"7"|"30"|"90"|"365"|"custom"} */
let trendsPeriod = "7";
let trendsCustomFrom = "";
let trendsCustomTo = "";

function trendsHistoryCap() {
  const hist = currentEntitlements?.history_days;
  if (hist == null) return 366;
  return Math.max(1, Math.min(Number(hist) || 14, 366));
}

function syncTrendsPeriodOptions() {
  const sel = document.getElementById("trendsPeriod");
  if (!sel) return;
  const cap = trendsHistoryCap();
  for (const opt of sel.options) {
    if (opt.value === "custom") {
      opt.disabled = false;
      continue;
    }
    const n = Number(opt.value);
    opt.disabled = Number.isFinite(n) && n > cap;
    if (opt.disabled && opt.selected) {
      // Fall back to largest allowed preset.
      const allowed = [...sel.options]
        .map((o) => Number(o.value))
        .filter((n) => Number.isFinite(n) && n <= cap);
      const best = allowed.length ? String(Math.max(...allowed)) : "7";
      sel.value = best;
      trendsPeriod = best;
    }
  }
  const from = document.getElementById("trendsFrom");
  const to = document.getElementById("trendsTo");
  const todayIso = localDayIso();
  const oldestIso = shiftDayIso(todayIso, -(cap - 1));
  if (from) {
    from.min = oldestIso;
    from.max = todayIso;
  }
  if (to) {
    to.min = oldestIso;
    to.max = todayIso;
  }
}

function trendsQuery() {
  const parts = [];
  if (trendsPeriod === "custom" && trendsCustomFrom && trendsCustomTo) {
    parts.push(`from=${encodeURIComponent(trendsCustomFrom)}`);
    parts.push(`to=${encodeURIComponent(trendsCustomTo)}`);
  } else {
    const days = Number(trendsPeriod) || 7;
    parts.push(`days=${encodeURIComponent(String(days))}`);
  }
  if (filterProjectId) parts.push(`project_id=${encodeURIComponent(filterProjectId)}`);
  if (filterEmployeeId) parts.push(`employee_id=${encodeURIComponent(filterEmployeeId)}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

function trendsTitleForRows(rows) {
  const n = rows?.length || 0;
  if (trendsPeriod === "custom") return "Часы за период";
  if (n <= 7) return "Часы за неделю";
  if (n <= 31) return "Часы за месяц";
  if (n <= 100) return "Часы за квартал";
  return "Часы за год";
}

function shouldShowHoursXLabel(i, n) {
  if (n <= 10) return true;
  if (n <= 31) return i % 3 === 0 || i === n - 1;
  if (n <= 100) return i % 14 === 0 || i === n - 1;
  return i % 30 === 0 || i === 0 || i === n - 1;
}

function hoursXLabel(isoDay, n) {
  const d = new Date(`${isoDay}T12:00:00`);
  if (n <= 10) {
    return d.toLocaleDateString("ru-RU", { weekday: "short" }).replace(".", "");
  }
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function weekStartIso(isoDay) {
  return startOfWeekMonday(isoDay);
}

function monthKey(isoDay) {
  return isoDay.slice(0, 7);
}

/** Collapse many daily rows into weeks/months so focus bars stay readable. */
function aggregateFocusRows(rows) {
  const list = rows || [];
  if (list.length <= 45) {
    return { rows: list, unit: "day", label: `${list.length} дн.` };
  }
  const byMonth = list.length > 120;
  /** @type {Map<string, any>} */
  const map = new Map();
  for (const r of list) {
    const key = byMonth ? monthKey(r.day) : weekStartIso(r.day);
    let bucket = map.get(key);
    if (!bucket) {
      bucket = {
        day: key,
        end_day: r.day,
        total_sec: 0,
        by_category: { productive: 0, neutral: 0, distracting: 0 },
      };
      map.set(key, bucket);
    }
    bucket.end_day = r.day;
    bucket.total_sec += Number(r.total_sec || 0);
    const cats = r.by_category || {};
    bucket.by_category.productive += Number(cats.productive || 0);
    bucket.by_category.neutral += Number(cats.neutral || 0);
    bucket.by_category.distracting += Number(cats.distracting || 0);
  }
  const out = [...map.values()].map((b) => {
    const total = b.total_sec || 0;
    const productive = b.by_category.productive || 0;
    return {
      day: b.day,
      end_day: b.end_day,
      total_sec: total,
      focus_pct: total ? (productive / total) * 100 : 0,
      by_category: b.by_category,
    };
  });
  return {
    rows: out,
    unit: byMonth ? "month" : "week",
    label: byMonth ? `${out.length} мес.` : `${out.length} нед.`,
  };
}

function focusBucketLabel(row, unit) {
  const d = new Date(`${(row.end_day || row.day)}T12:00:00`);
  if (unit === "month") {
    return d.toLocaleDateString("ru-RU", { month: "short" }).replace(".", "");
  }
  if (unit === "week") {
    return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
  }
  const nDay = new Date(`${row.day}T12:00:00`);
  return nDay.toLocaleDateString("ru-RU", { weekday: "short" });
}

function focusBucketTip(row, unit) {
  const focus = Math.round(row.focus_pct || 0);
  if (unit === "month") {
    const d = new Date(`${row.day}-01T12:00:00`);
    return `${d.toLocaleDateString("ru-RU", { month: "long", year: "numeric" })}: фокус ${focus}%`;
  }
  if (unit === "week") {
    const a = new Date(`${row.day}T12:00:00`);
    const b = new Date(`${(row.end_day || row.day)}T12:00:00`);
    const fmt = (x) => x.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
    return `${fmt(a)} — ${fmt(b)}: фокус ${focus}%`;
  }
  const d = new Date(`${row.day}T12:00:00`);
  return `${d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}: фокус ${focus}%`;
}

function bindHoursChartInteractions(el, points, tips) {
  const tip = document.createElement("div");
  tip.className = "hours-tip";
  tip.hidden = true;
  tip.setAttribute("role", "tooltip");
  el.appendChild(tip);

  const svg = el.querySelector(".hours-line-svg");
  if (!svg) return;
  const w = Number(svg.viewBox.baseVal.width) || 360;
  const h = Number(svg.viewBox.baseVal.height) || 168;

  const place = (i) => {
    const [x, y] = points[i];
    const svgRect = svg.getBoundingClientRect();
    const hostRect = el.getBoundingClientRect();
    let px = (x / w) * svgRect.width + (svgRect.left - hostRect.left);
    const py = (y / h) * svgRect.height + (svgRect.top - hostRect.top);
    tip.hidden = false;
    tip.textContent = tips[i];
    tip.classList.remove("is-below");
    // Measure after paint so we can flip when the tip would clip at the top.
    const tipW = tip.offsetWidth || 96;
    const tipH = tip.offsetHeight || 32;
    const roomAbove = py;
    if (roomAbove < tipH + 16) {
      tip.classList.add("is-below");
    }
    const half = tipW / 2;
    px = Math.max(half + 4, Math.min(hostRect.width - half - 4, px));
    tip.style.left = `${px}px`;
    tip.style.top = `${py}px`;
  };

  el.querySelectorAll(".hours-point").forEach((g, i) => {
    const show = () => {
      g.classList.add("is-hot");
      place(i);
    };
    const hide = () => {
      g.classList.remove("is-hot");
      tip.hidden = true;
    };
    g.addEventListener("mouseenter", show);
    g.addEventListener("mouseleave", hide);
    g.addEventListener("focusin", show);
    g.addEventListener("focusout", hide);
  });
}

function hoursSeriesPoints(vals, padL, padT, chartW, chartH, maxScale, n) {
  return vals.map((v, i) => {
    const x = padL + (i * chartW) / Math.max(n - 1, 1);
    const y = padT + chartH - (Math.max(0, v) / maxScale) * chartH;
    return [x, y];
  });
}

function hoursPolyline(pts) {
  return pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
}

function renderHoursChart(trends) {
  const el = document.getElementById("hoursChart");
  if (!el) return;
  clearSkel(el);
  const rows = trends || [];
  const aside = document.getElementById("hoursTrendAside");
  if (aside) aside.textContent = `${rows.length || 0} дн.`;
  const avgEl = document.getElementById("hoursTrendAvg");
  const title = document.getElementById("hoursTrendTitle");
  if (title) title.textContent = trendsTitleForRows(rows);
  const split = document.querySelector(".pulse-split");
  if (split) split.classList.toggle("is-long", rows.length > 45);
  if (!rows.length) {
    if (avgEl) avgEl.textContent = "в среднем —";
    el.innerHTML = `<p class="hint">Пока нет тренда по часам.</p>`;
    return;
  }
  const totalVals = rows.map((r) => Number(r.total_sec || r.active_sec || 0));
  const focusVals = rows.map((r) => Number(r.by_category?.productive || r.focus_sec || 0));
  const neutralVals = rows.map((r) => Number(r.by_category?.neutral || 0));
  const distractVals = rows.map((r) => Number(r.by_category?.distracting || 0));
  const activeVals = totalVals.filter((v) => v >= 60);
  // Mean over days with ≥1м tracked — empty calendar days don't pull the average to zero.
  const avgSec = activeVals.length
    ? activeVals.reduce((a, b) => a + b, 0) / activeVals.length
    : totalVals.reduce((a, b) => a + b, 0) / totalVals.length;
  if (avgEl) {
    avgEl.textContent = `в среднем ${fmtDur(avgSec)} / день`;
    avgEl.title = activeVals.length
      ? `Среднее по ${activeVals.length} дн. с активностью (≥1м)`
      : "Среднее по всем дням периода";
  }
  const maxSec = Math.max(...totalVals, ...focusVals, ...neutralVals, ...distractVals, avgSec, 1);
  const maxH = niceHoursCeiling(maxSec);
  const maxScale = maxH * 3600;
  // Keep a stable viewBox so the SVG fills the card instead of exploding width.
  const w = 560;
  const h = 168;
  const padL = 36;
  const padR = 12;
  const padT = 14;
  const padB = 28;
  const chartW = w - padL - padR;
  const chartH = h - padT - padB;
  const yTicks = [0, 0.5, 1].map((t) => Math.round(maxH * t * 10) / 10);
  const uniqTicks = [...new Set(yTicks)];
  const grid = uniqTicks
    .map((tick) => {
      const y = padT + chartH - (tick / maxH) * chartH;
      return `<line class="hours-grid" x1="${padL}" y1="${y.toFixed(1)}" x2="${w - padR}" y2="${y.toFixed(1)}"/>
        <text x="${padL - 6}" y="${(y + 3).toFixed(1)}" text-anchor="end" class="hours-axis">${tick}ч</text>`;
    })
    .join("");
  const n = rows.length;
  const totalPts = hoursSeriesPoints(totalVals, padL, padT, chartW, chartH, maxScale, n);
  const focusPts = hoursSeriesPoints(focusVals, padL, padT, chartW, chartH, maxScale, n);
  const neutralPts = hoursSeriesPoints(neutralVals, padL, padT, chartW, chartH, maxScale, n);
  const distractPts = hoursSeriesPoints(distractVals, padL, padT, chartW, chartH, maxScale, n);
  const polyTotal = hoursPolyline(totalPts);
  const area = `${padL},${(padT + chartH).toFixed(1)} ${polyTotal} ${(padL + chartW).toFixed(1)},${(padT + chartH).toFixed(1)}`;
  const avgY = padT + chartH - (avgSec / maxScale) * chartH;
  const avgLine =
    avgSec > 0
      ? `<line class="hours-avg-line" x1="${padL}" y1="${avgY.toFixed(1)}" x2="${(w - padR).toFixed(1)}" y2="${avgY.toFixed(1)}"/>
         <text class="hours-avg-tag" x="${(w - padR).toFixed(1)}" y="${(avgY - 4).toFixed(1)}" text-anchor="end">ср. ${escapeHtml(fmtDur(avgSec))}</text>`
      : "";
  const tips = rows.map((r, i) => {
    const d = new Date(`${r.day}T12:00:00`);
    const head = `${d.toLocaleDateString("ru-RU", {
      weekday: "short",
      day: "numeric",
      month: "short",
    })} · всего ${fmtDur(totalVals[i])}`;
    return `${head}\nФокус ${fmtDur(focusVals[i])} · Нейтрально ${fmtDur(neutralVals[i])} · Отвлечение ${fmtDur(distractVals[i])}`;
  });
  const dense = rows.length > 60;
  const dotR = dense ? 2.5 : 4.5;
  const hitR = dense ? 8 : 12;
  const xLabels = totalPts
    .map(([x], i) => {
      if (!shouldShowHoursXLabel(i, rows.length)) return "";
      const label = hoursXLabel(rows[i].day, rows.length);
      return `<text x="${x}" y="${h - 8}" text-anchor="middle" class="hours-axis hours-x">${escapeHtml(label)}</text>`;
    })
    .join("");
  const dots = totalPts
    .map(([x, y], i) => {
      return `<g class="hours-point" tabindex="0" aria-label="${escapeHtml(tips[i].replace(/\n/g, " · "))}">
        <circle cx="${x}" cy="${y}" r="${hitR}" class="hours-dot-hit"/>
        <circle cx="${x}" cy="${y}" r="${dotR}" class="hours-dot"/>
      </g>`;
    })
    .join("");
  el.innerHTML = `<svg class="hours-line-svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${escapeHtml(trendsTitleForRows(rows))}">
    ${grid}
    <polygon class="hours-line-fill" points="${area}"/>
    <polyline class="hours-line-path is-distracting" fill="none" points="${hoursPolyline(distractPts)}"/>
    <polyline class="hours-line-path is-neutral" fill="none" points="${hoursPolyline(neutralPts)}"/>
    <polyline class="hours-line-path is-productive" fill="none" points="${hoursPolyline(focusPts)}"/>
    <polyline class="hours-line-path is-total" fill="none" points="${polyTotal}"/>
    ${avgLine}
    ${xLabels}
    ${dots}
  </svg>`;
  bindHoursChartInteractions(el, totalPts, tips);
}

function renderProdDaysChart(trends) {
  const el = document.getElementById("prodDaysChart");
  if (!el) return;
  clearSkel(el);
  const raw = trends || [];
  const { rows, unit, label } = aggregateFocusRows(raw);
  const rangeEl = document.getElementById("prodDaysRange");
  const foot = document.getElementById("prodDaysFoot");
  if (rangeEl) rangeEl.textContent = label;
  if (raw.length && foot) {
    const a = new Date(`${raw[0].day}T12:00:00`);
    const b = new Date(`${raw[raw.length - 1].day}T12:00:00`);
    const fmt = (d) =>
      d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
    foot.textContent = `${fmt(a)} — ${fmt(b)}`;
  }
  el.classList.toggle("is-dense", rows.length > 16);
  el.classList.toggle("is-scroll", rows.length > 16);
  const maxTotal = Math.max(1, ...rows.map((r) => Number(r.total_sec) || 0));
  el.innerHTML = rows
    .map((r) => {
      const total = Number(r.total_sec) || 0;
      const cats = r.by_category || {};
      const d = new Date(`${r.end_day || r.day}T12:00:00`);
      const isWeekend = unit === "day" && (d.getDay() === 0 || d.getDay() === 6);
      const tip = focusBucketTip(r, unit);
      // Height = activity volume; color mix = focus composition.
      const hPct = total ? Math.max(10, Math.round((total / maxTotal) * 100)) : 0;
      const segs = [
        ["distracting", cats.distracting || 0],
        ["neutral", cats.neutral || 0],
        ["productive", cats.productive || 0],
      ]
        .map(([k, sec]) => {
          const pct = total ? Math.round((sec / total) * 100) : 0;
          return pct > 0
            ? `<span class="stack-seg ${k}" style="height:${pct}%" title="${k}: ${pct}%"></span>`
            : "";
        })
        .join("");
      const showVal = rows.length <= 20;
      const focus = Math.round(r.focus_pct || 0);
      return `<div class="prod-day-col${isWeekend ? " is-weekend" : ""}${total ? "" : " is-empty"}" title="${escapeHtml(tip)}">
        <div class="prod-day-track">
          <div class="prod-day-stack" style="height:${hPct}%">${segs || `<span class="stack-seg empty" style="height:100%"></span>`}</div>
        </div>
        <span class="hours-label">${escapeHtml(focusBucketLabel(r, unit))}</span>
        ${showVal ? `<span class="hours-val">${focus}%</span>` : ""}
      </div>`;
    })
    .join("");
}

async function refreshTrends({ skeleton = false } = {}) {
  const hoursEl = document.getElementById("hoursChart");
  const barsEl = document.getElementById("prodDaysChart");
  const ctx = `trends|${trendsPeriod}|${trendsCustomFrom || ""}|${trendsCustomTo || ""}|${filterProjectId || ""}|${filterEmployeeId || ""}`;
  const show =
    skeleton ||
    needsSkeleton(hoursEl, "trends", ctx, { force: skeleton }) ||
    needsSkeleton(barsEl, "trends", ctx, { force: skeleton });
  if (show) {
    showSkeleton(hoursEl, "chart");
    showSkeleton(barsEl, "bars", 7);
  }
  try {
    const trends = await api(`/api/trends${trendsQuery()}`);
    renderHoursChart(trends);
    renderProdDaysChart(trends);
    markSkelContext("trends", ctx);
  } catch (err) {
    if (hoursEl?.classList.contains("is-skel")) {
      hoursEl.classList.remove("is-skel");
      hoursEl.removeAttribute("aria-busy");
      hoursEl.innerHTML = `<p class="hint">Не удалось загрузить тренд.</p>`;
    }
    throw err;
  }
}

function categoryClass(cat) {
  const c = (cat || "neutral").toLowerCase();
  if (c === "productive" || c === "distracting" || c === "neutral") return c;
  return "neutral";
}

let dayGanttMode = localStorage.getItem("deskline_gantt_mode") === "full" ? "full" : "active";

function syncDayGanttModeButtons() {
  document.querySelectorAll("[data-gantt-mode]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.ganttMode === dayGanttMode);
  });
}

function setDayGanttMode(mode) {
  dayGanttMode = mode === "full" ? "full" : "active";
  try {
    localStorage.setItem("deskline_gantt_mode", dayGanttMode);
  } catch (_) {}
  syncDayGanttModeButtons();
  lastDayViewKey = "";
  refreshTimeline({ skeleton: true }).catch(() => {});
}

function sessionRowKey(startedAt) {
  return String(startedAt || "");
}

function openSessionGroup(groupEl) {
  if (!groupEl) return;
  groupEl.classList.add("is-open");
  const items = groupEl.querySelector(".session-group-items");
  if (items) items.hidden = false;
  const btn = groupEl.querySelector(".session-group-toggle");
  if (btn) btn.setAttribute("aria-expanded", "true");
}

function highlightTimelineSession(startedAt) {
  const list = document.getElementById("timelineList");
  if (!list) return;
  const key = sessionRowKey(startedAt);
  list.querySelectorAll("li.is-hot").forEach((li) => li.classList.remove("is-hot"));
  const row = [...list.querySelectorAll("li[data-started]")].find(
    (li) => li.dataset.started === key
  );
  if (!row) return;
  openSessionGroup(row.closest(".session-group"));
  row.classList.add("is-hot");
  row.scrollIntoView({ behavior: "smooth", block: "center" });
  window.setTimeout(() => row.classList.remove("is-hot"), 2200);
}

function renderDayGantt(rows) {
  const el = document.getElementById("dayGantt");
  if (!el) return;
  clearSkel(el);
  const { dayStartMs, dayEndMs } = dayBoundsFromRows(rows, selectedDayIso);
  const title = document.getElementById("dayPictureTitle");
  const hint = document.getElementById("dayPictureHint");
  syncDayGanttModeButtons();
  if (!rows.length) {
    if (title) title.textContent = "Картина дня";
    if (hint) hint.textContent = "Пока нет сессий для этого дня";
    el.innerHTML = `<p class="hint">Пока нет сессий для этого дня.</p>`;
    return;
  }

  const { viewStartMs, viewEndMs, spanMs } = activityViewBounds(
    rows,
    dayStartMs,
    dayEndMs,
    dayGanttMode
  );
  const hoursSpan = Math.max(1, Math.round(spanMs / 3600000));
  const tickStepH = hoursSpan <= 6 ? 1 : hoursSpan <= 12 ? 2 : 3;
  const hours = [];
  for (let ms = viewStartMs; ms <= viewEndMs + 1000; ms += tickStepH * 3600000) {
    const clamped = Math.min(ms, viewEndMs);
    const left = pctOnDay(clamped, viewStartMs, spanMs);
    const label = fmtClockMs(clamped);
    const edge =
      clamped <= viewStartMs + 1000 ? " is-start" : clamped >= viewEndMs - 1000 ? " is-end" : "";
    hours.push(`<span class="gantt-hour${edge}" style="left:${left}%">${label}</span>`);
    if (clamped >= viewEndMs) break;
  }

  const voids = voidGapsForDay(rows, viewStartMs, viewEndMs)
    .map((g) => {
      const durSec = (g.end - g.start) / 1000;
      if (durSec < 60) return "";
      const left = pctOnDay(g.start, viewStartMs, spanMs);
      const width = ((g.end - g.start) / spanMs) * 100;
      const tip = `Нет трека · ${fmtDur(durSec)} · ${fmtClockMs(g.start)}–${fmtClockMs(g.end)}`;
      return `<div class="gantt-block void-gap is-narrow" style="left:${left}%;width:${Math.max(0.35, width)}%" title="${escapeHtml(tip)}"></div>`;
    })
    .join("");

  const blocks = [];
  for (const r of rows) {
    const a = new Date(r.started_at).getTime();
    const b = new Date(r.ended_at || Date.now()).getTime();
    const clipped = clipToDay(a, b, viewStartMs, viewEndMs);
    if (!clipped) continue;
    const dur = clipped.end - clipped.start;
    const idleMs = Math.min(dur, Math.max(0, Number(r.idle_sec || 0) * 1000));
    const activeMs = Math.max(0, dur - idleMs);
    const cat = categoryClass(r.category);
    const startedKey = sessionRowKey(r.started_at);
    if (activeMs > 0) {
      const left = pctOnDay(clipped.start, viewStartMs, spanMs);
      const width = Math.max(0.35, (activeMs / spanMs) * 100);
      const titleTip = `${r.name || ""} · ${fmtClock(r.started_at)}–${fmtClock(r.ended_at)} · ${fmtDur(activeMs / 1000)}`;
      const showLabel = width >= 4.5;
      blocks.push(
        `<button type="button" class="gantt-block ${cat}${showLabel ? "" : " is-narrow"}" style="left:${left}%;width:${width}%" title="${escapeHtml(titleTip)}" data-started="${escapeHtml(startedKey)}">${showLabel ? `<span>${escapeHtml(r.name || "")}</span>` : ""}</button>`
      );
    }
    if (idleMs > 0) {
      const left = pctOnDay(clipped.start + activeMs, viewStartMs, spanMs);
      const width = Math.max(0.35, (idleMs / spanMs) * 100);
      blocks.push(
        `<div class="gantt-block idle is-narrow" style="left:${left}%;width:${width}%" title="Простой · ${fmtDur(idleMs / 1000)}"></div>`
      );
    }
  }

  let nowMark = "";
  const now = Date.now();
  if (now >= viewStartMs && now <= viewEndMs) {
    const left = pctOnDay(now, viewStartMs, spanMs);
    nowMark = `<div class="gantt-now" style="left:${left}%" title="Сейчас"></div>`;
  }

  if (title) {
    title.textContent = `Картина дня · ${fmtClockMs(viewStartMs)}–${fmtClockMs(viewEndMs)}`;
  }
  if (hint) {
    hint.textContent =
      dayGanttMode === "full"
        ? "Полные сутки. Клик по блоку — прыжок к сессии ниже"
        : "Только активные часы. Клик по блоку — прыжок к сессии ниже · Ctrl+колёсико — масштаб";
  }

  el.innerHTML = `
    <div class="gantt-scale">${hours.join("")}</div>
    <div class="gantt-track gantt-track-fullday" data-pulse-scrub="1" style="--gantt-hours:${Math.max(1, hoursSpan)}">${voids}${blocks.join("")}${nowMark}</div>
    <div class="gantt-legend">
      <span class="stack-leg"><i class="productive"></i>Фокус</span>
      <span class="stack-leg"><i class="neutral"></i>Нейтрально</span>
      <span class="stack-leg"><i class="distracting"></i>Отвлечение</span>
      <span class="stack-leg"><i class="idle"></i>Простой</span>
      <span class="stack-leg"><i class="void"></i>Пусто</span>
    </div>`;
  bindPulseDayScrub(el.querySelector("[data-pulse-scrub]"), viewStartMs, spanMs);
  el.querySelectorAll(".gantt-block[data-started]").forEach((btn) => {
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      highlightTimelineSession(btn.dataset.started);
    });
  });
}

function kindLabel(kind) {
  const map = {
    work: "Работа",
    remote: "Удалёнка",
    video: "Видео / музыка",
    messaging: "Общение",
    email: "Почта",
    social: "Соцсети",
    search: "Поиск",
    shopping: "Покупки",
    system: "Система",
    other: "Прочее",
  };
  return map[kind] || map.other;
}

function kindSubtitle(kind) {
  const key = String(kind || "other").toLowerCase();
  // Hide vague buckets — they clutter the list without helping the user.
  if (!key || key === "other" || key === "system") return "";
  return kindLabel(key);
}

const GROUPED_PAGE = 12;
let expandedActivityGroups = new Set();
let groupedUsageCache = [];
let groupedUsageLimit = GROUPED_PAGE;

function filterGroupedRows(rows, query) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return rows || [];
  return (rows || []).filter((r) => {
    if (String(r.name || "").toLowerCase().includes(q)) return true;
    return (r.children || []).some((c) => String(c.name || "").toLowerCase().includes(q));
  });
}

function renderGroupedList(el, rows, emptyText, opts = {}) {
  if (!el) return;
  clearSkel(el);
  const {
    searchInput = null,
    moreBtn = null,
    limit = GROUPED_PAGE,
    showShare = false,
    total = 0,
    cacheKey = "today",
  } = opts;
  const query = searchInput ? searchInput.value : "";
  const filtered = filterGroupedRows(rows, query);
  const sliced = filtered.slice(0, limit);
  if (moreBtn) {
    moreBtn.hidden = filtered.length <= limit;
  }

  if (!sliced.length) {
    el.innerHTML = `<li class="empty-state"><span class="rank-icon" aria-hidden="true">•</span><span class="rank-text"><span class="rank-name">${escapeHtml(emptyText || "Пока нет данных")}</span></span><span class="rank-meta">—</span></li>`;
    return;
  }

  const parts = [];
  sliced.forEach((r, idx) => {
    const children = r.children || [];
    const expandable = children.length > 0;
    const key = `${cacheKey}:${r.name}`;
    const open = expandable && (expandedActivityGroups.has(key) || !!query);
    const icon = r.icon_url
      ? iconImgHtml(r.icon_url, 22)
      : `<span class="rank-icon" aria-hidden="true">•</span>`;
    const chevron = expandable ? `<span class="rank-chevron" aria-hidden="true">▸</span>` : "";
    const share =
      showShare && total ? ` · ${Math.round((r.sec / total) * 100)}%` : "";
    parts.push(`<li class="rank-row-parent${open ? " is-open" : ""}${expandable ? " is-expandable" : ""}" data-group-key="${escapeHtml(key)}" ${expandable ? 'role="button" tabindex="0"' : ""}>
      ${icon}
      <span class="rank-text">
        <span class="rank-name">${chevron}${escapeHtml(r.name)}</span>
      </span>
      <span class="rank-meta">${fmtDur(r.sec)}${share}</span>
    </li>`);
    if (open) {
      children.forEach((c) => {
        const cIcon = c.icon_url
          ? iconImgHtml(c.icon_url, 18)
          : `<span class="rank-icon" aria-hidden="true">•</span>`;
        const kind = kindSubtitle(c.kind);
        const kindHtml = kind
          ? `<span class="rank-kind">${escapeHtml(kind)}</span>`
          : "";
        const cShare =
          showShare && total ? ` · ${Math.round((c.sec / total) * 100)}%` : "";
        parts.push(`<li class="rank-row-child">
          <span class="rank-nest" aria-hidden="true"></span>
          ${cIcon}
          <span class="rank-text">
            <span class="rank-name">${escapeHtml(c.name)}</span>
            ${kindHtml}
          </span>
          <span class="rank-meta">${fmtDur(c.sec)}${cShare}</span>
        </li>`);
      });
    }
  });
  el.innerHTML = parts.join("");
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
    el.innerHTML = `<li><span class="rank-icon" aria-hidden="true">•</span><span class="rank-text"><span class="rank-name">${emptyText || "Пока нет данных"}</span></span><span class="rank-meta">Оставьте Deskline включённым</span></li>`;
    return;
  }
  el.innerHTML = sliced
    .map((r) => {
      const icon = r.icon_url
        ? iconImgHtml(r.icon_url)
        : `<span class="rank-icon" aria-hidden="true">•</span>`;
      const kind = kindSubtitle(r.kind);
      const kindHtml = kind
        ? `<span class="rank-kind">${escapeHtml(kind)}</span>`
        : "";
      return `<li>
        ${icon}
        <span class="rank-text">
          <span class="rank-name">${escapeHtml(r.name)}</span>
          ${kindHtml}
        </span>
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

function iconImgHtml(url, size = 36) {
  if (!url) return `<span class="rank-icon" aria-hidden="true">•</span>`;
  const s = Number(size) || 36;
  return `<span class="rank-icon"><img class="rank-icon-img" src="${escapeHtml(url)}" alt="" width="${s}" height="${s}" decoding="async" onerror="${ICON_ONERROR}" /></span>`;
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
let filterEmployeeId = "";
let companyMode = false;
let companyEmployees = [];
let selectedProjectId = "";
let usagePeriod = "today";
let projectsReportPeriod = "today";
let projectsSort = "time";
let expandedReportProjects = new Set();
let lastFocusNames = { project: "", task: "" };
/** @type {Record<string, any[]>} */
let tasksByProjectCache = {};

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

function periodQuery(period, projectId = "", taskId = "", employeeId = "") {
  const { from, to } = periodBounds(period);
  const parts = [`from=${encodeURIComponent(from)}`, `to=${encodeURIComponent(to)}`];
  if (projectId) parts.push(`project_id=${encodeURIComponent(projectId)}`);
  if (taskId) parts.push(`task_id=${encodeURIComponent(taskId)}`);
  if (employeeId) parts.push(`employee_id=${encodeURIComponent(employeeId)}`);
  return parts.join("&");
}

function employeeQuerySuffix() {
  return filterEmployeeId ? `&employee_id=${encodeURIComponent(filterEmployeeId)}` : "";
}

function summaryQuery() {
  const parts = [];
  if (filterProjectId) parts.push(`project_id=${encodeURIComponent(filterProjectId)}`);
  if (filterEmployeeId) parts.push(`employee_id=${encodeURIComponent(filterEmployeeId)}`);
  return parts.length ? `?${parts.join("&")}` : "";
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

async function loadProjectTasks(projectId, { force = false } = {}) {
  if (projectId == null || projectId === "" || projectId === "null") return [];
  const key = String(projectId);
  if (!force && Object.prototype.hasOwnProperty.call(tasksByProjectCache, key)) {
    return tasksByProjectCache[key];
  }
  const tasks = await api(`/api/tasks?project_id=${encodeURIComponent(key)}`);
  tasksByProjectCache[key] = tasks || [];
  return tasksByProjectCache[key];
}

function buildSortedProjectRows(projects, summary) {
  const byProj = summary.by_project || [];
  const secById = {};
  let noneSec = 0;
  for (const r of byProj) {
    if (r.project_id == null) noneSec = r.sec || 0;
    else secById[String(r.project_id)] = r.sec || 0;
  }
  const totalSec = summary.total_sec || 0;
  const rows = (projects || []).map((p) => ({
    key: String(p.id),
    id: p.id,
    name: p.name,
    color: p.color || "#2f6f5e",
    sec: secById[String(p.id)] || 0,
    managed: true,
  }));
  if (noneSec > 0) {
    rows.push({
      key: "null",
      id: null,
      name: "Без проекта",
      color: null,
      sec: noneSec,
      managed: false,
    });
  }
  if (projectsSort === "name") {
    rows.sort((a, b) => {
      if (!a.managed) return 1;
      if (!b.managed) return -1;
      return a.name.localeCompare(b.name, "ru", { sensitivity: "base" });
    });
  } else {
    rows.sort((a, b) => {
      if (b.sec !== a.sec) return b.sec - a.sec;
      if (!a.managed) return 1;
      if (!b.managed) return -1;
      return a.name.localeCompare(b.name, "ru", { sensitivity: "base" });
    });
  }
  return { rows, totalSec };
}

function renderProjectTasksHtml(row, settings, summary) {
  const byTask = summary.by_task || [];
  const secByTask = Object.fromEntries(
    byTask
      .filter((t) =>
        row.managed
          ? String(t.project_id) === String(row.id)
          : t.project_id == null
      )
      .map((t) => [String(t.task_id == null ? "null" : t.task_id), t.sec])
  );
  const focusTask = String(settings.current_task_id || "");

  if (!row.managed) {
    const orphanTasks = byTask.filter((t) => t.project_id == null && (t.sec || 0) > 0);
    if (!orphanTasks.length) {
      return `<div class="pt-expand"><p class="hint">Нет задач в этом периоде.</p></div>`;
    }
    return `<div class="pt-expand"><div class="pt-task-list">${orphanTasks
      .map((t) => {
        const tname = t.task_id == null ? "Без задачи" : `Задача #${t.task_id}`;
        return `<div class="pt-item pt-task is-readonly">
          <div class="pt-item-main">
            <div class="pt-item-name">${escapeHtml(tname)}</div>
            <div class="pt-item-meta">${fmtDur(t.sec)}</div>
          </div>
        </div>`;
      })
      .join("")}</div></div>`;
  }

  const tasks = tasksByProjectCache[row.key] || [];
  const form = `<form class="inline-form pt-form pt-task-form" data-create-task-for="${row.id}">
    <input type="text" name="name" placeholder="Новая задача" required maxlength="120" />
    <button type="submit" class="btn" aria-label="Создать задачу">+</button>
  </form>`;

  if (!tasks.length) {
    return `<div class="pt-expand">${form}<p class="hint">Добавьте первую задачу.</p></div>`;
  }

  const taskRows = tasks
    .map((t) => {
      const active = focusTask === String(t.id);
      const done = !!t.done;
      const sec = secByTask[String(t.id)] || 0;
      return `<div class="pt-item pt-task ${active ? "is-active" : ""} ${done ? "is-done" : ""}" data-task-id="${t.id}" data-project-id="${row.id}">
        <button type="button" class="pt-check" data-toggle-done="${t.id}" title="${done ? "Вернуть" : "Готово"}">${done ? "✓" : "○"}</button>
        <div class="pt-item-main">
          <div class="pt-item-name">${escapeHtml(t.name)}</div>
          <div class="pt-item-meta">${sec ? fmtDur(sec) : "—"}</div>
        </div>
        <button type="button" class="btn ${active ? "primary" : ""}" data-focus-task="${t.id}" data-project-id="${row.id}" ${done ? "disabled" : ""}>${active ? "Сейчас" : "Выбрать"}</button>
        <button type="button" class="btn danger pt-del" data-del-task="${t.id}" aria-label="Удалить задачу">×</button>
      </div>`;
    })
    .join("");

  return `<div class="pt-expand">${form}<div class="pt-task-list">${taskRows}</div></div>`;
}

async function renderProjectsWorkspace(projects, settings, summary) {
  const list = document.getElementById("projectsList");
  if (!list) return;
  clearSkel(list);

  if (selectedProjectId && !projects.some((p) => String(p.id) === selectedProjectId)) {
    selectedProjectId = "";
  }
  if (!selectedProjectId && settings.current_project_id) {
    selectedProjectId = String(settings.current_project_id);
  }

  // Keep header task select in sync with focused / selected project.
  const headerProjectId = settings.current_project_id || selectedProjectId || "";
  if (headerProjectId) {
    const headerTasks = await loadProjectTasks(headerProjectId);
    fillTaskSelect(headerTasks, settings.current_task_id);
  } else {
    fillTaskSelect([], null);
  }

  for (const key of expandedReportProjects) {
    if (key !== "null") {
      try {
        await loadProjectTasks(key);
      } catch (_) {}
    }
  }

  const { rows, totalSec } = buildSortedProjectRows(projects, summary);
  if (!rows.length) {
    list.innerHTML = `<p class="hint">Создайте проект — здесь появятся задачи и время за период.</p>`;
    lastFocusNames = { project: "", task: "" };
    return;
  }

  const focusPid = String(settings.current_project_id || "");
  list.innerHTML = rows
    .map((row) => {
      const open = expandedReportProjects.has(row.key);
      const tracking = row.managed && focusPid === String(row.id);
      const share = totalSec ? Math.round((row.sec / totalSec) * 100) : 0;
      const chevron = open ? "▾" : "▸";
      const swatch = row.managed
        ? `<span class="pt-swatch" aria-hidden="true"></span>`
        : `<span class="pt-swatch pt-swatch-muted" aria-hidden="true"></span>`;
      const badge = tracking ? `<span class="pt-badge">Сейчас</span>` : "";
      const del = row.managed
        ? `<button type="button" class="btn danger pt-del" data-del-project="${row.id}" aria-label="Удалить проект ${escapeHtml(row.name)}">×</button>`
        : "";
      const body = open ? renderProjectTasksHtml(row, settings, summary) : "";
      const style = row.managed ? `style="--pc:${escapeHtml(row.color)}"` : "";
      return `<div class="pt-row ${open ? "is-open" : ""} ${tracking ? "is-active" : ""}" data-project-key="${escapeHtml(row.key)}" ${style}>
        <div class="pt-row-head">
          <button type="button" class="pt-row-main" data-toggle-project="${escapeHtml(row.key)}" aria-expanded="${open ? "true" : "false"}">
            <span class="pt-chevron" aria-hidden="true">${chevron}</span>
            ${swatch}
            <span class="pt-item-main">
              <span class="pt-item-name">${escapeHtml(row.name)}${badge}</span>
            </span>
            <span class="pt-row-meta">${share}%</span>
            <span class="pt-row-meta">${fmtDur(row.sec)}</span>
          </button>
          ${del}
        </div>
        ${body}
      </div>`;
    })
    .join("");

  const proj = projects.find((p) => String(p.id) === focusPid);
  const focusTasks = focusPid ? tasksByProjectCache[focusPid] || [] : [];
  const task = focusTasks.find((t) => String(t.id) === String(settings.current_task_id));
  lastFocusNames = {
    project: proj ? proj.name : "",
    task: task ? task.name : "",
  };
}

async function refreshProjects({ skeleton = false } = {}) {
  const list = document.getElementById("projectsList");
  const ctx = `projects|${projectsReportPeriod}`;
  const show = skeleton || needsSkeleton(list, "projects", ctx, { force: skeleton });
  if (show) showSkeleton(list, "projects", 4);
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

  // Drop task cache so mutations and period changes stay fresh.
  tasksByProjectCache = {};

  fillProjectSelects(projects, settings.current_project_id);
  const workToggle = document.getElementById("workModeToggle");
  if (workToggle) workToggle.checked = !!settings.work_mode;

  if (
    expandedReportProjects.size === 0 &&
    settings.current_project_id != null &&
    settings.current_project_id !== ""
  ) {
    expandedReportProjects.add(String(settings.current_project_id));
  }

  await renderProjectsWorkspace(projects, settings, summary);
  markSkelContext("projects", ctx);
}

async function refreshSummary({ skeleton = false } = {}) {
  const kpi = document.getElementById("kpiStrip");
  const proj = document.getElementById("topProjectsPulse");
  const apps = document.getElementById("topAppsPulse");
  const quiet = document.getElementById("quietList");
  const gauges = document.getElementById("teamGauges");
  const ctx = `summary|${filterProjectId || ""}|${filterEmployeeId || ""}`;
  const show =
    skeleton ||
    needsSkeleton(kpi, "summary", ctx, { force: skeleton }) ||
    needsSkeleton(proj, "summary-proj", ctx, { force: skeleton }) ||
    needsSkeleton(apps, "summary-apps", ctx, { force: skeleton });
  if (show) {
    lastSummaryKey = "";
    showSkeleton(kpi, "kpi", 5);
    showSkeleton(proj, "donut");
    if (apps) showSkeleton(apps, "list", 3);
    if (quiet) showSkeleton(quiet, "list", 4);
    if (gauges) showSkeleton(gauges, "list", 3);
    showSkeleton(document.getElementById("hoursChart"), "chart");
    showSkeleton(document.getElementById("prodDaysChart"), "bars", 7);
  }
  const q = summaryQuery();
  const { from, to } = periodBounds("today");
  const teamQ = `from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}${filterProjectId ? `&project_id=${encodeURIComponent(filterProjectId)}` : ""}`;
  const [summary, team] = await Promise.all([
    api(`/api/summary/today${q}`),
    api(`/api/company/team?${teamQ}`, { quiet402: true }).catch(() => []),
  ]);
  const key = summaryKey(summary) + `|p:${filterProjectId}|e:${filterEmployeeId}`;
  if (key === lastSummaryKey && !show) {
    refreshTrends({ skeleton: false }).catch(() => {});
    return;
  }
  lastSummaryKey = key;

  const focusText = `${summary.focus_pct}%`;
  const activityText = `${summary.activity_pct ?? 0}%`;
  const focusEl = document.getElementById("focusValue");
  const activityEl = document.getElementById("activityValue");
  if (focusEl) {
    const changed = focusEl.textContent !== focusText;
    focusEl.textContent = focusText;
    if (changed) pulseMetric(focusEl);
  }
  document.getElementById("focusSub").textContent = `${fmtDur(summary.focus_sec)} из ${fmtDur(summary.total_sec)}`;
  const activitySub = document.getElementById("activitySub");
  if (activityEl) {
    const changed = activityEl.textContent !== activityText;
    activityEl.textContent = activityText;
    if (changed) pulseMetric(activityEl);
  }
  if (activitySub) {
    activitySub.textContent = `${fmtDur(summary.active_sec)} активно · ${fmtDur(summary.idle_sec)} без ввода`;
  }
  renderQuietPeople(team);
  renderKpis(summary, team);
  renderTopAppsPulse(summary);
  renderTopProjectsPulse(summary);
  markSkelContext("summary", ctx);
  markSkelContext("summary-proj", ctx);
  markSkelContext("summary-apps", ctx);
  refreshTrends({ skeleton: show }).catch(() => {});
}

function pulseMetric(el) {
  if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  el.classList.remove("is-tick");
  void el.offsetWidth;
  el.classList.add("is-tick");
  window.setTimeout(() => el.classList.remove("is-tick"), 520);
}

async function refreshUsageReport({ skeleton = false } = {}) {
  const catPie = document.getElementById("usageCatPie");
  const kindPie = document.getElementById("usageKindPie");
  const acts = document.getElementById("activitiesList");
  const apps = document.getElementById("appsList");
  const sites = document.getElementById("sitesList");
  const ctx = `usage|${usagePeriod}|${filterProjectId || ""}|${filterTaskId || ""}|${filterEmployeeId || ""}`;
  const show =
    skeleton ||
    needsSkeleton(catPie, "usage", ctx, { force: skeleton }) ||
    needsSkeleton(acts, "usage-list", ctx, { force: skeleton });
  if (show) {
    showSkeleton(catPie, "pie");
    showSkeleton(kindPie, "pie");
    showSkeleton(acts, "list", 7);
    showSkeleton(apps, "list", 6);
    showSkeleton(sites, "list", 5);
    if (catPie) delete catPie.dataset.pieSig;
    if (kindPie) delete kindPie.dataset.pieSig;
    const line = document.getElementById("usageTotalLine");
    if (line) line.textContent = "Загрузка…";
  }
  const q = periodQuery(usagePeriod, filterProjectId, filterTaskId, filterEmployeeId);
  const summary = await api(`/api/summary?${q}`);
  const total = summary.total_sec || 0;
  const focus = summary.focus_sec || summary.by_category?.productive || 0;
  const idle = summary.idle_sec || 0;
  const line = document.getElementById("usageTotalLine");
  if (line) {
    if (!total) {
      line.textContent = "За период пока нет учтённого времени.";
    } else {
      line.textContent = `Всего ${fmtDur(total)} · в фокусе ${fmtDur(focus)} · без ввода ${fmtDur(idle)}`;
    }
  }
  renderPieChart(
    document.getElementById("usageCatPie"),
    categoryPieSlices(summary.by_category || {}),
    total,
    "Нет данных за период."
  );
  renderPieChart(
    document.getElementById("usageKindPie"),
    kindPieSlices(summary.by_kind || {}),
    total,
    "Нет типов занятий за период."
  );
  groupedUsageCache = summary.by_app_grouped || [];
  renderGroupedList(
    document.getElementById("activitiesList"),
    groupedUsageCache,
    "Занятий пока нет",
    {
      searchInput: document.getElementById("activitySearchUsage"),
      moreBtn: document.getElementById("activitiesListMore"),
      limit: groupedUsageLimit,
      showShare: true,
      total,
      cacheKey: "usage",
    }
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
  markSkelContext("usage", ctx);
  markSkelContext("usage-list", ctx);
}

let meetingsPeriod = "today";
let lastMeetingsKey = "";

function meetingSessionRowHtml(r) {
  const icon = r.icon_url
    ? iconImgHtml(r.icon_url, 28)
    : `<span class="rank-icon">•</span>`;
  const label = r.display_name || r.name || r.app_name || r.site || "Сессия";
  const detail = String(r.detail || "").trim();
  const canExpand = Boolean(detail);
  const expandBtn = canExpand
    ? `<button type="button" class="meeting-expand" aria-expanded="false">Контекст</button>`
    : "";
  const detailBlock = canExpand
    ? `<div class="meeting-detail" hidden><span class="meeting-detail-label">Контекст окна</span><p>${escapeHtml(detail)}</p></div>`
    : "";
  const parts =
    Number(r.parts) > 1
      ? `<span class="timeline-parts">+${Number(r.parts) - 1} коротких</span>`
      : "";
  return `<li class="meeting-session${canExpand ? " is-expandable" : ""}">
    <div class="meeting-session-main">
      <span class="timeline-time">${fmtClock(r.started_at)}</span>
      ${icon}
      <span class="meeting-session-text">
        <span class="rank-name">${escapeHtml(label)}</span>
        ${parts}
        ${expandBtn}
      </span>
      <span class="rank-meta">${fmtDur(r.sec)}</span>
    </div>
    ${detailBlock}
  </li>`;
}

function meetingSessionGroupHtml(g) {
  if (g.sessions.length === 1) return meetingSessionRowHtml(g.sessions[0]);
  const icon = g.icon_url
    ? iconImgHtml(g.icon_url, 28)
    : `<span class="rank-icon">•</span>`;
  const span =
    g.earliest_started !== g.latest_started
      ? `${fmtClock(g.earliest_started)}–${fmtClock(g.latest_started)}`
      : fmtClock(g.latest_started);
  return `<li class="session-group meeting-session-group" data-group="${escapeHtml(g.key)}">
    <button type="button" class="session-group-toggle" aria-expanded="false">
      <span class="timeline-time">${fmtClock(g.latest_started)}</span>
      ${icon}
      <span class="session-group-text">
        <span class="rank-name">${escapeHtml(g.name)}</span>
        <span class="session-group-meta">${sessionVisitLabel(g.visits)} · ${span}</span>
      </span>
      <span class="rank-meta">${fmtDur(g.sec)}</span>
      <span class="session-group-chev" aria-hidden="true"></span>
    </button>
    <ol class="session-group-items" hidden>
      ${g.sessions.map((r) => meetingSessionRowHtml(r)).join("")}
    </ol>
  </li>`;
}

function wireMeetingExpand(listEl) {
  if (!listEl || listEl.dataset.expandWired === "1") return;
  listEl.dataset.expandWired = "1";
  listEl.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".meeting-expand");
    if (!btn || !listEl.contains(btn)) return;
    if (btn.classList.contains("meeting-peers-toggle")) return;
    const row = btn.closest(".meeting-session");
    if (!row) return;
    const open = row.classList.toggle("is-open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.textContent = open ? "Свернуть" : "Контекст";
    const detail = row.querySelector(".meeting-detail");
    if (detail) detail.hidden = !open;
  });
}

function wireMeetingChannelPeers(listEl) {
  if (!listEl || listEl.dataset.peersWired === "1") return;
  listEl.dataset.peersWired = "1";
  listEl.addEventListener("click", async (ev) => {
    const shotBtn = ev.target.closest(".meeting-peers-shot");
    if (shotBtn && listEl.contains(shotBtn)) {
      ev.preventDefault();
      const row = shotBtn.closest(".meeting-channel");
      if (!row) return;
      const panel = row.querySelector(".meeting-peers");
      const key = row.dataset.channelKey || "";
      shotBtn.disabled = true;
      const prev = shotBtn.textContent;
      shotBtn.textContent = "Скрин…";
      try {
        const res = await api("/api/meetings/peers-from-shot", {
          method: "POST",
          body: JSON.stringify({ channel_key: key || null }),
        });
        const peers = res.peers || [];
        if (!peers.length) {
          showToast("На скрине не видно имени собеседника", "error");
          if (panel) {
            const empty = panel.querySelector(".meeting-peers-empty");
            if (empty) empty.textContent = "На последнем скрине имя не распознано.";
          }
          return;
        }
        const peerRows = peers
          .map((p) => {
            const tag = p.kind === "group" ? "группа" : "чат";
            return `<li class="meeting-peer">
              <span class="meeting-peer-tag">${tag}</span>
              <span class="meeting-peer-name">${escapeHtml(p.name)}</span>
              <span class="meeting-peer-meta">со скрина</span>
            </li>`;
          })
          .join("");
        if (panel) {
          panel.innerHTML = `<span class="meeting-detail-label">С кем (со скрина)</span>
            <ul class="meeting-peers-list">${peerRows}</ul>`;
          panel.hidden = false;
          row.classList.add("is-open");
          const toggle = row.querySelector(".meeting-peers-toggle");
          if (toggle) {
            toggle.setAttribute("aria-expanded", "true");
            toggle.textContent = "Свернуть";
          }
        }
        showToast(`Нашли: ${peers.map((p) => p.name).join(", ")}`, "ok");
      } catch (err) {
        showToast(err?.message || "Не удалось распознать со скрина", "error");
      } finally {
        shotBtn.disabled = false;
        shotBtn.textContent = prev;
      }
      return;
    }
    const btn = ev.target.closest(".meeting-peers-toggle");
    if (!btn || !listEl.contains(btn)) return;
    const row = btn.closest(".meeting-channel");
    if (!row) return;
    const open = row.classList.toggle("is-open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.textContent = open ? "Свернуть" : "С кем";
    const panel = row.querySelector(".meeting-peers");
    if (panel) panel.hidden = !open;
  });
}

async function refreshMeetings({ skeleton = false } = {}) {
  const periodSel = document.getElementById("meetingsPeriod");
  if (periodSel) meetingsPeriod = periodSel.value || "today";
  const emp = filterEmployeeId ? `&employee_id=${encodeURIComponent(filterEmployeeId)}` : "";
  const kpi = document.getElementById("meetingsKpi");
  const top = document.getElementById("meetingsTopList");
  const sess = document.getElementById("meetingsSessions");
  const emailList = document.getElementById("meetingsEmailList");
  const emailSess = document.getElementById("meetingsEmailSessions");
  const ctx = `meetings|${meetingsPeriod}|${filterEmployeeId || ""}`;
  const show =
    skeleton ||
    needsSkeleton(kpi, "meetings", ctx, { force: skeleton }) ||
    needsSkeleton(top, "meetings-top", ctx, { force: skeleton });
  if (show) {
    lastMeetingsKey = "";
    showSkeleton(kpi, "kpi", 4);
    showSkeleton(top, "list", 5);
    showSkeleton(sess, "list", 6);
    showSkeleton(emailList, "list", 4);
    showSkeleton(emailSess, "list", 4);
  }
  let report;
  try {
    report = await api(`/api/meetings?period=${encodeURIComponent(meetingsPeriod)}${emp}`, {
      quiet402: true,
    });
  } catch (err) {
    if (err?.code === "history_limit" || err?.code === "pro_required") {
      const note = document.getElementById("meetingsNote");
      if (note) note.textContent = "История дальше Free-лимита — доступно в Pro.";
      if (kpi) kpi.innerHTML = "";
      if (top) {
        top.innerHTML = `<li class="empty-state"><span class="rank-icon">•</span><span class="rank-name">Нужен Pro для этого периода</span><span class="rank-meta">—</span></li>`;
      }
      if (sess) sess.innerHTML = "";
      if (emailList) emailList.innerHTML = "";
      if (emailSess) emailSess.innerHTML = "";
      return;
    }
    throw err;
  }

  const key = [
    meetingsPeriod,
    filterEmployeeId || "",
    report.total_sec,
    report.email_total_sec || 0,
    (report.top || []).map((r) => `${r.key}:${Math.floor(r.sec / 60)}:${(r.peers||[]).length}`).join(","),
    (report.sessions || []).length,
    (report.email_top || []).length,
  ].join("|");
  if (key === lastMeetingsKey && !show) return;
  lastMeetingsKey = key;

  const note = document.getElementById("meetingsNote");
  if (note) note.textContent = report.note || "";

  if (kpi) {
    clearSkel(kpi);
    const total = report.total_sec || 0;
    const share = report.share_pct ?? 0;
    const channels = (report.top || []).length;
    const emailSec = report.email_total_sec || 0;
    kpi.innerHTML = [
      { label: "Встречи / звонки", value: fmtDur(total), pct: share, tone: "productive" },
      { label: "Доля дня", value: `${share}%`, pct: share, tone: "tracked" },
      { label: "Каналы", value: String(channels), pct: null, tone: "active" },
      { label: "Почта", value: fmtDur(emailSec), pct: null, tone: "active" },
    ]
      .map((it) => {
        const meter =
          it.pct == null
            ? ""
            : `<div class="pulse-ov-meter"><em>${it.pct}%</em><span><i style="width:${Math.max(it.pct, it.pct ? 3 : 0)}%"></i></span></div>`;
        return `<article class="pulse-ov-card ${it.tone}">
          <span class="pulse-ov-label">${it.label}</span>
          <strong class="pulse-ov-value">${it.value}</strong>
          ${meter}
        </article>`;
      })
      .join("");
  }

  const topEl = document.getElementById("meetingsTopList");
  if (topEl) {
    clearSkel(topEl);
    const rows = report.top || [];
    if (!rows.length) {
      topEl.innerHTML = `<li class="empty-state"><span class="rank-icon">•</span><span class="rank-name">Пока нет Телемоста, Teams, Zoom…</span><span class="rank-meta">—</span></li>`;
    } else {
      const total = report.total_sec || 0;
      topEl.innerHTML = rows
        .map((r, idx) => {
          const icon = r.icon_url
            ? iconImgHtml(r.icon_url)
            : `<span class="rank-icon" aria-hidden="true">•</span>`;
          const share = total ? Math.round((r.sec / total) * 100) : 0;
          const kind = r.source === "site" ? "сайт" : "приложение";
          const peers = r.peers || [];
          const peerRows = peers.length
            ? peers
                .map((p) => {
                  const tag = p.kind === "group" ? "группа" : "чат";
                  return `<li class="meeting-peer">
                    <span class="meeting-peer-tag">${tag}</span>
                    <span class="meeting-peer-name">${escapeHtml(p.name)}</span>
                    <span class="meeting-peer-meta">${fmtDur(p.sec)}</span>
                  </li>`;
                })
                .join("")
            : "";
          const body = peers.length
            ? `<ul class="meeting-peers-list">${peerRows}</ul>`
            : `<p class="hint meeting-peers-empty">${escapeHtml(r.peers_hint || "Имён в заголовке окна не было.")}</p>
               <button type="button" class="btn meeting-peers-shot">Распознать со скрина</button>`;
          return `<li class="meeting-channel" data-channel-idx="${idx}" data-channel-key="${escapeHtml(r.key || "")}">
            <div class="meeting-channel-main">
              ${icon}
              <span class="meeting-channel-text">
                <span class="rank-name">${escapeHtml(r.name)}</span>
                <span class="rank-kind">${kind}</span>
              </span>
              <button type="button" class="meeting-expand meeting-peers-toggle" aria-expanded="false">С кем</button>
              <span class="rank-meta">${fmtDur(r.sec)} · ${share}%</span>
            </div>
            <div class="meeting-peers" hidden>
              <span class="meeting-detail-label">С кем</span>
              ${body}
            </div>
          </li>`;
        })
        .join("");
    }
    wireMeetingChannelPeers(topEl);
  }

  const sessEl = document.getElementById("meetingsSessions");
  if (sessEl) {
    clearSkel(sessEl);
    const groups = groupFeedByApp(compactFeedRows(report.sessions || [], 60, 180)).slice(0, 12);
    if (!groups.length) {
      sessEl.innerHTML = `<li><span class="timeline-time">—</span><span class="rank-icon">•</span><span class="rank-name">Нет сессий за период</span><span class="rank-meta"></span></li>`;
    } else {
      sessEl.innerHTML = groups.map((g) => meetingSessionGroupHtml(g)).join("");
    }
    wireSessionGroups(sessEl);
    wireMeetingExpand(sessEl);
  }

  const emailEl = document.getElementById("meetingsEmailList");
  if (emailEl) {
    clearSkel(emailEl);
    const rows = report.email_top || [];
    if (!rows.length) {
      emailEl.innerHTML = `<li class="empty-state"><span class="rank-icon">•</span><span class="rank-name">Пока нет времени в почте</span><span class="rank-meta">—</span></li>`;
    } else {
      const total = report.email_total_sec || 0;
      emailEl.innerHTML = rows
        .map((r) => {
          const icon = r.icon_url
            ? iconImgHtml(r.icon_url)
            : `<span class="rank-icon" aria-hidden="true">•</span>`;
          const share = total ? Math.round((r.sec / total) * 100) : 0;
          return `<li>
            ${icon}
            <span class="rank-name">${escapeHtml(r.name)}</span>
            <span class="rank-meta">${fmtDur(r.sec)} · ${share}%</span>
          </li>`;
        })
        .join("");
    }
  }

  const emailSessEl = document.getElementById("meetingsEmailSessions");
  if (emailSessEl) {
    clearSkel(emailSessEl);
    const groups = groupFeedByApp(compactFeedRows(report.email_sessions || [], 60, 180)).slice(0, 10);
    if (!groups.length) {
      emailSessEl.innerHTML = `<li><span class="timeline-time">—</span><span class="rank-icon">•</span><span class="rank-name">Нет почтовых сессий</span><span class="rank-meta"></span></li>`;
    } else {
      emailSessEl.innerHTML = groups.map((g) => meetingSessionGroupHtml(g)).join("");
    }
    wireSessionGroups(emailSessEl);
    wireMeetingExpand(emailSessEl);
  }
  markSkelContext("meetings", ctx);
  markSkelContext("meetings-top", ctx);
}

function renderUsageList(el, rows, total, kind, emptyText) {
  if (!el) return;
  clearSkel(el);
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
        <span class="rank-text">
          <span class="rank-name">${escapeHtml(r.name)}${
            kind === "activity"
              ? ""
              : `<span class="rank-cat ${cat}">${CAT_LABELS[cat] || cat}</span>`
          }</span>
          ${kind === "activity" && kindSubtitle(r.kind) ? `<span class="rank-kind">${escapeHtml(kindSubtitle(r.kind))}</span>` : ""}
          ${rate}
        </span>
        <span class="rank-meta">${fmtDur(r.sec)} · ${share}%</span>
      </li>`;
    })
    .join("");
}

async function refreshStatus() {
  const st = await api("/api/status");
  const pending = st.rdp_vision_pending || null;
  const pendingKey = pending ? `${pending.label}|${pending.created_at}` : "";
  const key = JSON.stringify({
    paused: !!st.paused,
    idle: !!st.idle,
    current_label: st.current_label || "",
    current_app: st.current_app || "",
    work_mode: !!st.work_mode,
    project: st.current_project_id || "",
    task: st.current_task_id || "",
    focusNames: lastFocusNames,
    rdpPending: pendingKey,
  });
  maybeShowRdpVision(pending);
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

let _rdpVisionShownKey = "";

function maybeShowRdpVision(pending) {
  const modal = document.getElementById("rdpVisionModal");
  if (!modal) return;
  if (!pending) {
    modal.hidden = true;
    _rdpVisionShownKey = "";
    return;
  }
  const key = `${pending.label}|${pending.created_at}`;
  if (key === _rdpVisionShownKey && !modal.hidden) return;
  _rdpVisionShownKey = key;
  const msg = document.getElementById("rdpVisionMessage");
  const conf = pending.confidence != null ? ` (${Math.round(pending.confidence * 100)}%)` : "";
  if (msg) {
    msg.textContent = `Похоже: ${pending.label}${conf}. Засчитать как занятие? (Focus % не пересчитывается — только ярлык remote-сессии.)`;
  }
  modal.hidden = false;
  modal.dataset.label = pending.label || "";
  modal.dataset.sessionId = pending.session_id != null ? String(pending.session_id) : "";
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

function shotAppKey(row) {
  let raw = String(row?.app_name || "").trim().toLowerCase();
  if (raw.endsWith(".exe")) raw = raw.slice(0, -4);
  return raw;
}

function shotAppLabel(row) {
  const name = String(row?.display_name || "").trim();
  if (name) return name;
  const key = shotAppKey(row);
  if (!key) return "Без сессии";
  return key.charAt(0).toUpperCase() + key.slice(1);
}

function truncateShotText(text, max = 48) {
  const s = String(text || "").replace(/\s+/g, " ").trim();
  if (!s) return "";
  if (s.length <= max) return s;
  return `${s.slice(0, max - 1)}…`;
}

function shotCaption(row, { details = false } = {}) {
  const parts = [fmtShotWhen(row.taken_at), fmtShotReason(row.reason)];
  const app = shotAppLabel(row);
  if (app) parts.push(app);
  if (details) {
    const activity = truncateShotText(row.activity_label || "", 40);
    const title = truncateShotText(row.window_title || "", 56);
    if (activity && activity.toLowerCase() !== app.toLowerCase()) parts.push(activity);
    if (title && title.toLowerCase() !== activity.toLowerCase() && title.toLowerCase() !== app.toLowerCase()) {
      parts.push(title);
    }
  }
  return parts.filter(Boolean).join(" · ");
}

let shotsPollTimer = null;
const SHOTS_POLL_MS = 15000;
/** @type {any[]} */
let shotsCache = [];
/** @type {Set<string>} selected app keys; empty = all */
let shotsAppFilter = new Set();
/** @type {{ key: string, label: string }[]} */
let shotsAppOptions = [];
let shotsShowDetails = false;
/** Last day successfully rendered in the shots grid */
let shotsLoadedForDay = "";

function stopShotsPolling() {
  if (shotsPollTimer) {
    clearInterval(shotsPollTimer);
    shotsPollTimer = null;
  }
}

function startShotsPolling() {
  stopShotsPolling();
  shotsPollTimer = setInterval(() => {
    if (document.querySelector(".tab.active")?.dataset.tab !== "shots") return;
    if (document.hidden) return;
    refreshShots().catch(() => {});
  }, SHOTS_POLL_MS);
}

function currentTabName() {
  return document.querySelector(".tab.active")?.dataset.tab || "today";
}

/** Visible month for shots calendar: YYYY-MM */
let shotsCalMonth = "";
/** @type {Set<string>} YYYY-MM-DD days that have screenshots */
let shotsDaysWithData = new Set();
/** @type {string[]} newest-first ISO days with screenshots */
let shotsDaysList = [];

function formatShotsDayLabel(isoDay) {
  const today = localDayIso();
  if (isoDay === today) return "Сегодня";
  if (isoDay === shiftDayIso(today, -1)) return "Вчера";
  const d = new Date(`${isoDay}T12:00:00`);
  return d.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function syncShotsDayLabel(isoDay) {
  const label = document.getElementById("shotsDayLabel");
  if (label) label.textContent = formatShotsDayLabel(isoDay);
}

function ensureShotsDayInput() {
  const el = document.getElementById("shotsDay");
  if (!el) return localDayIso();
  if (!el.value) {
    el.value = selectedDayIso || localDayIso();
  }
  const day = el.value || localDayIso();
  syncShotsDayLabel(day);
  return day;
}

function pickShotsDayWithData(preferred) {
  if (preferred && shotsDaysWithData.has(preferred)) return preferred;
  if (shotsDaysList.length) return shotsDaysList[0];
  return preferred || localDayIso();
}

async function loadShotsDays({ quiet = true } = {}) {
  try {
    const data = await api("/api/screenshots/days", { quiet402: true });
    const days = Array.isArray(data?.days) ? data.days : [];
    shotsDaysList = days.filter((d) => /^\d{4}-\d{2}-\d{2}$/.test(d));
    shotsDaysWithData = new Set(shotsDaysList);
  } catch (e) {
    if (e?.code === "pro_required" || e?.detail?.feature === "screenshots") {
      shotsDaysList = [];
      shotsDaysWithData = new Set();
      return;
    }
    if (!quiet) throw e;
  }
}

function setShotsDay(isoDay, { refresh = true, close = true } = {}) {
  const el = document.getElementById("shotsDay");
  let day = isoDay || localDayIso();
  if (shotsDaysWithData.size && !shotsDaysWithData.has(day)) {
    day = pickShotsDayWithData(day);
  }
  if (el) el.value = day;
  syncShotsDayLabel(day);
  shotsCalMonth = day.slice(0, 7);
  if (close) closeShotsCal();
  else renderShotsCal();
  if (refresh) {
    refreshShots().catch((err) => showToast(err?.message || "Не удалось загрузить скриншоты", "error"));
  }
}

function isShotsCalOpen() {
  const cal = document.getElementById("shotsCal");
  return !!(cal && !cal.hidden);
}

function closeShotsCal() {
  const cal = document.getElementById("shotsCal");
  const btn = document.getElementById("shotsDayBtn");
  if (cal) cal.hidden = true;
  if (btn) btn.setAttribute("aria-expanded", "false");
}

async function openShotsCal() {
  const cal = document.getElementById("shotsCal");
  const btn = document.getElementById("shotsDayBtn");
  if (!cal) return;
  await loadShotsDays();
  const day = ensureShotsDayInput();
  shotsCalMonth = day.slice(0, 7);
  renderShotsCal();
  cal.hidden = false;
  if (btn) btn.setAttribute("aria-expanded", "true");
}

function toggleShotsCal() {
  if (isShotsCalOpen()) closeShotsCal();
  else openShotsCal().catch(() => {});
}

function shiftShotsCalMonth(delta) {
  const base = shotsCalMonth || ensureShotsDayInput().slice(0, 7);
  const [y, m] = base.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  shotsCalMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  renderShotsCal();
}

function renderShotsCal() {
  const monthEl = document.getElementById("shotsCalMonth");
  const grid = document.getElementById("shotsCalGrid");
  const todayBtn = document.querySelector("#shotsCal [data-cal-today]");
  if (!monthEl || !grid) return;
  const selected = ensureShotsDayInput();
  const today = localDayIso();
  if (!shotsCalMonth) shotsCalMonth = selected.slice(0, 7);
  const [y, m] = shotsCalMonth.split("-").map(Number);
  const monthStart = new Date(y, m - 1, 1);
  monthEl.textContent = monthStart.toLocaleDateString("ru-RU", {
    month: "long",
    year: "numeric",
  });
  const startPad = (monthStart.getDay() + 6) % 7;
  const daysInMonth = new Date(y, m, 0).getDate();
  const cells = [];
  for (let i = 0; i < startPad; i++) {
    cells.push(`<span class="shots-cal-day is-muted" aria-hidden="true"></span>`);
  }
  const restrict = shotsDaysWithData.size > 0;
  for (let day = 1; day <= daysInMonth; day++) {
    const iso = `${y}-${String(m).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const future = iso > today;
    const hasData = shotsDaysWithData.has(iso);
    const blocked = future || (restrict && !hasData);
    const selectedCls = iso === selected ? " is-selected" : "";
    const todayCls = iso === today ? " is-today" : "";
    const emptyCls = !future && restrict && !hasData ? " is-empty" : "";
    const hasCls = hasData ? " has-shots" : "";
    cells.push(
      `<button type="button" class="shots-cal-day${selectedCls}${todayCls}${emptyCls}${hasCls}" data-cal-day="${iso}" ${
        blocked ? "disabled" : ""
      } aria-pressed="${iso === selected ? "true" : "false"}" aria-label="${escapeHtml(
        formatDayTitle(iso)
      )}${hasData ? "" : " — нет скриншотов"}">${day}</button>`
    );
  }
  grid.innerHTML = cells.join("");
  if (todayBtn) {
    const todayOk = !restrict || shotsDaysWithData.has(today);
    todayBtn.disabled = !todayOk;
    todayBtn.title = todayOk ? "" : "За сегодня скриншотов нет";
  }
}

function wireShotsDayPicker() {
  const wrap = document.querySelector(".shots-day-wrap");
  const btn = document.getElementById("shotsDayBtn");
  const cal = document.getElementById("shotsCal");
  if (!wrap || !btn || !cal || wrap.dataset.wired === "1") return;
  wrap.dataset.wired = "1";

  btn.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    toggleShotsCal();
  });

  cal.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!(t instanceof Element)) return;
    const shift = t.closest("[data-cal-shift]");
    if (shift) {
      ev.preventDefault();
      shiftShotsCalMonth(Number(shift.getAttribute("data-cal-shift") || 0));
      return;
    }
    if (t.closest("[data-cal-today]")) {
      ev.preventDefault();
      const today = localDayIso();
      if (shotsDaysWithData.size && !shotsDaysWithData.has(today)) return;
      setShotsDay(today);
      return;
    }
    const dayBtn = t.closest("[data-cal-day]");
    if (dayBtn && !dayBtn.disabled) {
      const iso = dayBtn.getAttribute("data-cal-day") || "";
      if (shotsDaysWithData.size && iso && !shotsDaysWithData.has(iso)) return;
      ev.preventDefault();
      setShotsDay(iso || localDayIso());
    }
  });

  document.addEventListener("click", (ev) => {
    if (!isShotsCalOpen()) return;
    if (wrap.contains(ev.target)) return;
    closeShotsCal();
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && isShotsCalOpen()) {
      closeShotsCal();
      btn.focus();
    }
  });
}

function fillShotsAppFilter(rows) {
  const map = new Map();
  let orphans = 0;
  for (const r of rows || []) {
    const key = shotAppKey(r);
    if (!key) {
      orphans += 1;
      continue;
    }
    if (!map.has(key)) map.set(key, shotAppLabel(r));
  }
  const next = [...map.entries()]
    .sort((a, b) => a[1].localeCompare(b[1], "ru"))
    .map(([key, label]) => ({ key, label }));
  if (orphans) next.push({ key: "__none__", label: `Без сессии (${orphans})` });
  shotsAppOptions = next;
  const known = new Set(next.map((o) => o.key));
  shotsAppFilter = new Set([...shotsAppFilter].filter((k) => known.has(k)));
  syncShotsAppLabel();
  renderShotsAppList();
}

function shotsAppFilterLabel() {
  if (!shotsAppFilter.size) return "Все";
  const labels = shotsAppOptions
    .filter((o) => shotsAppFilter.has(o.key))
    .map((o) => o.label);
  if (!labels.length) return "Все";
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `${labels[0]}, ${labels[1]}`;
  return `${labels[0]} +${labels.length - 1}`;
}

function syncShotsAppLabel() {
  const label = document.getElementById("shotsAppLabel");
  if (label) label.textContent = shotsAppFilterLabel();
}

function filteredShotsRows() {
  if (!shotsAppFilter.size) return shotsCache.slice();
  return shotsCache.filter((r) => {
    const key = shotAppKey(r);
    if (!key) return shotsAppFilter.has("__none__");
    return shotsAppFilter.has(key);
  });
}

function isShotsAppMenuOpen() {
  const menu = document.getElementById("shotsAppMenu");
  return !!(menu && !menu.hidden);
}

function closeShotsAppMenu() {
  const menu = document.getElementById("shotsAppMenu");
  const btn = document.getElementById("shotsAppBtn");
  if (menu) menu.hidden = true;
  if (btn) btn.setAttribute("aria-expanded", "false");
}

function openShotsAppMenu() {
  const menu = document.getElementById("shotsAppMenu");
  const btn = document.getElementById("shotsAppBtn");
  const search = document.getElementById("shotsAppSearch");
  if (!menu) return;
  if (typeof closeShotsCal === "function") closeShotsCal();
  renderShotsAppList();
  menu.hidden = false;
  if (btn) btn.setAttribute("aria-expanded", "true");
  if (search) {
    search.value = "";
    window.setTimeout(() => search.focus(), 0);
  }
}

function toggleShotsAppMenu() {
  if (isShotsAppMenuOpen()) closeShotsAppMenu();
  else openShotsAppMenu();
}

function renderShotsAppList() {
  const list = document.getElementById("shotsAppList");
  const search = document.getElementById("shotsAppSearch");
  if (!list) return;
  const q = String(search?.value || "")
    .trim()
    .toLowerCase();
  const rows = shotsAppOptions.filter((o) => !q || o.label.toLowerCase().includes(q) || o.key.toLowerCase().includes(q));
  if (!rows.length) {
    list.innerHTML = `<p class="shots-app-empty">${shotsAppOptions.length ? "Ничего не найдено" : "Пока нет приложений за день"}</p>`;
    return;
  }
  list.innerHTML = `<div class="shots-app-list-inner">${rows
    .map((o) => {
      const on = shotsAppFilter.has(o.key);
      return `<button type="button" class="shots-app-option${on ? " is-checked" : ""}" role="option" aria-selected="${on ? "true" : "false"}" data-app-key="${escapeHtml(o.key)}">
        <span class="shots-app-check" aria-hidden="true">${on ? "✓" : ""}</span>
        <span>${escapeHtml(o.label)}</span>
      </button>`;
    })
    .join("")}</div>`;
}

function bumpShotsAppListRubber(list, edge) {
  if (!list || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  list.classList.remove("is-bounce-start", "is-bounce-end");
  void list.offsetWidth;
  list.classList.add(edge === "end" ? "is-bounce-end" : "is-bounce-start");
  window.clearTimeout(list._bounceTimer);
  list._bounceTimer = window.setTimeout(() => {
    list.classList.remove("is-bounce-start", "is-bounce-end");
  }, 420);
}

function wireShotsAppFilter() {
  const wrap = document.querySelector(".shots-app-wrap");
  const btn = document.getElementById("shotsAppBtn");
  const menu = document.getElementById("shotsAppMenu");
  const search = document.getElementById("shotsAppSearch");
  if (!wrap || !btn || !menu || wrap.dataset.wired === "1") return;
  wrap.dataset.wired = "1";

  btn.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    toggleShotsAppMenu();
  });

  search?.addEventListener("input", () => renderShotsAppList());
  search?.addEventListener("click", (ev) => ev.stopPropagation());
  search?.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      closeShotsAppMenu();
      btn.focus();
    }
  });

  menu.addEventListener(
    "wheel",
    (ev) => {
      const list = document.getElementById("shotsAppList");
      ev.stopPropagation();
      if (!list) {
        ev.preventDefault();
        return;
      }
      const onList = list === ev.target || list.contains(ev.target);
      if (!onList) {
        ev.preventDefault();
        return;
      }
      const maxScroll = Math.max(0, list.scrollHeight - list.clientHeight);
      const atTop = list.scrollTop <= 0;
      const atBottom = list.scrollTop >= maxScroll - 1;
      const up = ev.deltaY < 0;
      const down = ev.deltaY > 0;
      if (maxScroll <= 0 || (atTop && up) || (atBottom && down)) {
        ev.preventDefault();
        bumpShotsAppListRubber(list, down ? "end" : "start");
      }
    },
    { passive: false }
  );

  menu.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!(t instanceof Element)) return;
    if (t.closest("[data-app-clear]")) {
      ev.preventDefault();
      shotsAppFilter = new Set();
      syncShotsAppLabel();
      renderShotsAppList();
      renderShotsGrid();
      return;
    }
    const opt = t.closest("[data-app-key]");
    if (!opt) return;
    ev.preventDefault();
    const key = opt.getAttribute("data-app-key") || "";
    if (!key) return;
    if (shotsAppFilter.has(key)) shotsAppFilter.delete(key);
    else shotsAppFilter.add(key);
    syncShotsAppLabel();
    renderShotsAppList();
    renderShotsGrid();
  });

  document.addEventListener("click", (ev) => {
    if (!isShotsAppMenuOpen()) return;
    if (wrap.contains(ev.target)) return;
    closeShotsAppMenu();
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && isShotsAppMenuOpen()) {
      closeShotsAppMenu();
      btn.focus();
    }
  });
}

function renderShotsSkeleton(count = 8) {
  const grid = document.getElementById("shotsGrid");
  const meta = document.getElementById("shotsFilterMeta");
  if (!grid) return;
  if (meta) {
    meta.hidden = false;
    meta.textContent = "Загрузка…";
  }
  lightboxItems = [];
  showSkeleton(grid, "shots", count);
}

function renderShotsGrid() {
  const grid = document.getElementById("shotsGrid");
  const meta = document.getElementById("shotsFilterMeta");
  if (!grid) return;
  clearSkel(grid);
  const rows = filteredShotsRows();
  const details = !!shotsShowDetails;
  lightboxItems = rows.map((r) => ({
    url: r.url,
    caption: shotCaption(r, { details }),
    flag: !!r.flag_distracting,
  }));
  if (meta) {
    if (!shotsCache.length) {
      meta.hidden = true;
      meta.textContent = "";
    } else {
      meta.hidden = false;
      meta.textContent = rows.length === shotsCache.length
        ? `${shotsCache.length} скриншотов`
        : `Показано ${rows.length} из ${shotsCache.length}`;
    }
  }
  if (!shotsCache.length) {
    grid.innerHTML = `<p class="hint">За этот день скриншотов нет.</p>`;
    return;
  }
  if (!rows.length) {
    grid.innerHTML = `<p class="hint">Нет скриншотов для выбранных приложений.</p>`;
    return;
  }
  grid.innerHTML = rows
    .map((r, i) => {
      const caption = shotCaption(r, { details });
      const flag = r.flag_distracting ? "shot-distracting" : "";
      return `<figure class="shot ${flag}" tabindex="0" role="button" data-index="${i}" data-url="${escapeHtml(r.url)}" data-caption="${escapeHtml(caption)}" data-flag="${r.flag_distracting ? "1" : "0"}">
        <img src="${escapeHtml(r.url)}" alt="screenshot" loading="lazy" />
        <figcaption>${escapeHtml(caption)}</figcaption>
      </figure>`;
    })
    .join("");
}

async function refreshShots({ skeleton = false } = {}) {
  const grid = document.getElementById("shotsGrid");
  await loadShotsDays();
  let day = ensureShotsDayInput();
  if (shotsDaysWithData.size && !shotsDaysWithData.has(day)) {
    day = pickShotsDayWithData(day);
    const el = document.getElementById("shotsDay");
    if (el) el.value = day;
    syncShotsDayLabel(day);
  }
  const dayChanged = shotsLoadedForDay !== day;
  const hasRealCards = !!grid?.querySelector(".shot:not(.shot-skel)");
  const showSkeleton = skeleton || dayChanged || (!shotsLoadedForDay && !hasRealCards);
  if (showSkeleton) renderShotsSkeleton();
  let rows;
  try {
    const q = new URLSearchParams({ day });
    rows = await api(`/api/screenshots?${q}`, { quiet402: true });
  } catch (e) {
    shotsCache = [];
    shotsLoadedForDay = "";
    lightboxItems = [];
    if (grid) grid.removeAttribute("aria-busy");
    if (e?.code === "pro_required" || e?.detail?.feature === "screenshots") {
      if (grid) {
        grid.innerHTML = `<p class="hint">Скриншоты доступны в Deskline Pro.</p>`;
      }
      return;
    }
    throw e;
  }
  shotsCache = Array.isArray(rows) ? rows : [];
  shotsLoadedForDay = day;
  fillShotsAppFilter(shotsCache);
  renderShotsGrid();
  if (isShotsCalOpen()) renderShotsCal();
}

async function refreshCurrentView({ quiet = false } = {}) {
  const tab = currentTabName();
  try {
    if (tab === "shots") await refreshShots({ skeleton: true });
    else if (tab === "today") await refreshSummary({ skeleton: true });
    else if (tab === "day") await refreshTimeline({ skeleton: true });
    else if (tab === "usage") await refreshUsageReport({ skeleton: true });
    else if (tab === "projects") await refreshProjects({ skeleton: true });
    else if (tab === "ratings") await refreshRatings({ skeleton: true });
    else if (tab === "meetings") await refreshMeetings({ skeleton: true });
    else if (tab === "settings") await loadSettings();
    if (!quiet) showToast("Обновлено", "ok");
  } catch (err) {
    showToast(err?.message || "Не удалось обновить", "error");
  }
}

async function loadSettings() {
  const cfg = await api("/api/settings");
  const form = document.getElementById("settingsForm");
  form.idle_after_sec.value = cfg.idle_after_sec ?? 180;
  if (form.welcome_back_enabled) {
    form.welcome_back_enabled.checked = cfg.welcome_back_enabled !== false;
  }
  if (form.welcome_back_after_sec) {
    form.welcome_back_after_sec.value = cfg.welcome_back_after_sec ?? 600;
  }
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
  if (form.show_mini_tracker) {
    form.show_mini_tracker.checked = cfg.show_mini_tracker !== false;
  }
  if (form.work_mode) form.work_mode.checked = !!cfg.work_mode;
  if (form.work_chat_keywords) {
    const kw = cfg.work_chat_keywords || [];
    form.work_chat_keywords.value = Array.isArray(kw) ? kw.join(", ") : "";
  }
  if (form.company_mode) form.company_mode.checked = !!cfg.company_mode;
  if (form.company_display_name) {
    form.company_display_name.value = cfg.company_display_name || "";
  }
  if (form.listen_host) form.listen_host.value = cfg.listen_host || "127.0.0.1";
  if (form.hub_url) form.hub_url.value = cfg.hub_url || "";
  if (form.hub_ingest_token) {
    form.hub_ingest_token.value = cfg.hub_ingest_token || "";
  }
  if (form.rdp_vision_consent) form.rdp_vision_consent.checked = !!cfg.rdp_vision_consent;
  if (form.rdp_vision_enabled) form.rdp_vision_enabled.checked = !!cfg.rdp_vision_enabled;
  if (form.rdp_vision_api_key) form.rdp_vision_api_key.value = cfg.rdp_vision_api_key || "";
  if (form.rdp_vision_interval_sec) {
    form.rdp_vision_interval_sec.value = cfg.rdp_vision_interval_sec ?? 180;
  }
  if (form.rdp_vision_base_url) {
    form.rdp_vision_base_url.value = cfg.rdp_vision_base_url || "https://api.openai.com/v1";
  }
  if (form.rdp_vision_model) form.rdp_vision_model.value = cfg.rdp_vision_model || "gpt-4o-mini";
  companyMode = !!cfg.company_mode;
  updateCompanyUiVisibility();
  await refreshCompanyPanel();
  updateStorageHint(cfg);
  const workToggle = document.getElementById("workModeToggle");
  if (workToggle) workToggle.checked = !!cfg.work_mode;
  if (cfg.theme) applyThemePref(cfg.theme);
  if (cfg.entitlements) applyEntitlements(cfg.entitlements);
  filterSettingsSearch();
}

function filterSettingsSearch() {
  const input = document.getElementById("settingsSearch");
  const clearBtn = document.getElementById("settingsSearchClear");
  const empty = document.getElementById("settingsSearchEmpty");
  const shell = document.querySelector("#panel-settings .settings-shell");
  if (!shell) return;
  const q = String(input?.value || "")
    .trim()
    .toLocaleLowerCase("ru");
  if (clearBtn) clearBtn.hidden = !q;

  const groups = [...shell.querySelectorAll("[data-settings-group]")];
  let visibleGroups = 0;
  for (const group of groups) {
    const items = [...group.querySelectorAll("[data-settings-item]")];
    if (!q) {
      group.classList.remove("is-hidden");
      items.forEach((item) => item.classList.remove("is-hidden"));
      visibleGroups += 1;
      continue;
    }
    const groupHit = `${group.dataset.search || ""} ${group.querySelector(".settings-group-title")?.textContent || ""}`
      .toLocaleLowerCase("ru")
      .includes(q);
    let visibleItems = 0;
    items.forEach((item) => {
      const hay = `${item.dataset.search || ""} ${item.textContent || ""}`.toLocaleLowerCase("ru");
      const hit = groupHit || hay.includes(q);
      item.classList.toggle("is-hidden", !hit);
      if (hit) visibleItems += 1;
    });
    const show = groupHit || visibleItems > 0;
    group.classList.toggle("is-hidden", !show);
    if (show) visibleGroups += 1;
  }

  const saveBar = shell.querySelector(".settings-save-bar");
  if (saveBar) saveBar.hidden = !!q && visibleGroups === 0;
  if (empty) empty.hidden = visibleGroups > 0;
}

function wireSettingsSearch() {
  const input = document.getElementById("settingsSearch");
  const clearBtn = document.getElementById("settingsSearchClear");
  if (!input || input.dataset.wired === "1") return;
  input.dataset.wired = "1";
  input.addEventListener("input", () => filterSettingsSearch());
  clearBtn?.addEventListener("click", () => {
    input.value = "";
    filterSettingsSearch();
    input.focus();
  });
}

function updateCompanyUiVisibility() {
  const wrap = document.getElementById("filterEmployeeWrap");
  const hub = document.getElementById("companyHubPanel");
  const whoCap = document.getElementById("whoCaption");
  if (wrap) wrap.hidden = !companyMode;
  if (hub) hub.hidden = !companyMode;
  if (whoCap) {
    whoCap.textContent = companyMode ? "команда" : "сегодня";
  }
}

function fillEmployeeFilter(employees) {
  const sel = document.getElementById("filterEmployeeToday");
  if (!sel) return;
  const keep = filterEmployeeId;
  sel.innerHTML =
    `<option value="">Вся команда</option>` +
    (employees || [])
      .filter((e) => e.active !== false)
      .map(
        (e) =>
          `<option value="${e.id}">${escapeHtml(e.display_name || "—")}</option>`
      )
      .join("");
  sel.value = keep || "";
  if (sel.value !== keep) filterEmployeeId = sel.value || "";
}

async function refreshCompanyPanel() {
  let data;
  try {
    data = await api("/api/company");
  } catch {
    return;
  }
  companyMode = !!data.company_mode;
  companyEmployees = data.employees || [];
  updateCompanyUiVisibility();
  fillEmployeeFilter(companyEmployees);
  const list = document.getElementById("companyEmployeeList");
  if (list) {
    list.innerHTML = (data.employees || [])
      .map((e) => {
        const active = e.active ? "" : " (выкл)";
        return `<li class="company-employee">
          <div>
            <strong>${escapeHtml(e.display_name)}</strong>
            <span class="muted">${escapeHtml(e.role)}${active}</span>
          </div>
          <div class="company-employee-actions">
            <button type="button" class="btn tiny" data-rotate-token="${e.id}">Токен</button>
            <button type="button" class="btn tiny" data-toggle-emp="${e.id}" data-active="${e.active ? "1" : "0"}">${e.active ? "Выкл" : "Вкл"}</button>
          </div>
        </li>`;
      })
      .join("");
  }
  const devices = document.getElementById("companyDeviceList");
  if (devices) {
    const rows = data.devices || [];
    devices.innerHTML = rows.length
      ? rows
          .map(
            (d) =>
              `<li><strong>${escapeHtml(d.hostname)}</strong> · ${escapeHtml(d.employee_name || "")} · ${escapeHtml(d.last_seen_at || "")}</li>`
          )
          .join("")
      : `<li class="hint">Пока нет устройств</li>`;
  }
}

async function showEmployeeToken(employeeId) {
  const row = await api(`/api/company/employees/${employeeId}/token`, { method: "POST", body: "{}" });
  const hint = document.getElementById("companyTokenHint");
  if (hint && row.ingest_token) {
    hint.hidden = false;
    hint.textContent = `Токен для ${row.display_name}: ${row.ingest_token} — сохраните сейчас, повторно не покажется.`;
  }
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

function syncDayDateInput() {
  renderDayWeekStrip();
}

function dayTimelineSignature(rows) {
  return (rows || [])
    .map(
      (r) =>
        `${r.started_at}|${r.ended_at || "open"}|${Math.floor((r.sec || 0) / 60)}|${r.name || ""}|${r.category || ""}`
    )
    .join(";");
}

/** Absorb sub-minute flickers into the previous row — keeps the Day list readable. */
function compactFeedRows(rows, minSec = 60, maxGapSec = 45) {
  if (!rows || !rows.length) return [];
  const chrono = [...rows].sort(
    (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
  );
  const out = [];
  for (const raw of chrono) {
    const cur = {
      ...raw,
      sec: Number(raw.sec) || 0,
      idle_sec: Number(raw.idle_sec) || 0,
      parts: Number(raw.parts) || 1,
    };
    if (out.length) {
      const prev = out[out.length - 1];
      const same =
        String(prev.name || "").toLowerCase() === String(cur.name || "").toLowerCase() &&
        String(prev.app_name || "").toLowerCase() === String(cur.app_name || "").toLowerCase();
      const gap = Math.max(
        0,
        (new Date(cur.started_at).getTime() - new Date(prev.ended_at || cur.started_at).getTime()) /
          1000
      );
      if (cur.sec < minSec || (same && gap <= maxGapSec)) {
        prev.ended_at = cur.ended_at || prev.ended_at;
        prev.sec = Math.round((prev.sec + cur.sec) * 10) / 10;
        prev.idle_sec = Math.round((prev.idle_sec + cur.idle_sec) * 10) / 10;
        prev.parts += cur.parts;
        continue;
      }
    }
    out.push(cur);
  }
  while (out.length >= 2 && out[0].sec < minSec) {
    const first = out.shift();
    const next = out[0];
    next.started_at = first.started_at || next.started_at;
    next.sec = Math.round((next.sec + first.sec) * 10) / 10;
    next.idle_sec = Math.round((next.idle_sec + first.idle_sec) * 10) / 10;
    next.parts += first.parts;
  }
  return out;
}

/** Collapse the day list into app groups — no endless session ribbon. */
function groupFeedByApp(rows) {
  if (!rows || !rows.length) return [];
  const map = new Map();
  for (const raw of rows) {
    const name = String(raw.display_name || raw.name || raw.app_name || "—").trim() || "—";
    const app = String(raw.app_name || "").trim();
    const key = `${app.toLowerCase()}|${name.toLowerCase()}`;
    let g = map.get(key);
    if (!g) {
      g = {
        key,
        name,
        app_name: app,
        icon_url: raw.icon_url || "",
        category: raw.category || "neutral",
        sec: 0,
        idle_sec: 0,
        visits: 0,
        sessions: [],
        latest_started: raw.started_at,
        earliest_started: raw.started_at,
        has_live: false,
      };
      map.set(key, g);
    }
    const sec = Number(raw.sec) || 0;
    const idle = Number(raw.idle_sec) || 0;
    g.sec = Math.round((g.sec + sec) * 10) / 10;
    g.idle_sec = Math.round((g.idle_sec + idle) * 10) / 10;
    g.visits += 1;
    g.sessions.push(raw);
    if (!g.icon_url && raw.icon_url) g.icon_url = raw.icon_url;
    const t = new Date(raw.started_at).getTime();
    if (t >= new Date(g.latest_started).getTime()) {
      g.latest_started = raw.started_at;
      g.category = raw.category || g.category;
      g.name = name;
      if (raw.icon_url) g.icon_url = raw.icon_url;
    }
    if (t < new Date(g.earliest_started).getTime()) g.earliest_started = raw.started_at;
    if (!raw.ended_at) g.has_live = true;
  }
  const groups = [...map.values()];
  for (const g of groups) {
    g.sessions.sort(
      (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
    );
  }
  groups.sort(
    (a, b) => new Date(b.latest_started).getTime() - new Date(a.latest_started).getTime()
  );
  return groups;
}

function sessionVisitLabel(n) {
  const k = Math.abs(Number(n) || 0) % 100;
  const n1 = k % 10;
  if (k > 10 && k < 20) return `${n} заходов`;
  if (n1 === 1) return `${n} заход`;
  if (n1 >= 2 && n1 <= 4) return `${n} захода`;
  return `${n} заходов`;
}

function daySessionRowHtml(r) {
  const icon = r.icon_url
    ? iconImgHtml(r.icon_url, 28)
    : `<span class="rank-icon">•</span>`;
  const idle =
    r.idle_sec >= 60 ? `<span class="timeline-idle">idle ${fmtDur(r.idle_sec)}</span>` : "";
  const parts =
    r.parts > 1 ? `<span class="timeline-parts">+${r.parts - 1} коротких</span>` : "";
  const cat = categoryClass(r.category);
  const open = !r.ended_at ? `<span class="timeline-live">сейчас</span>` : "";
  return `<li class="session-visit timeline-cat-${cat}" data-started="${escapeHtml(sessionRowKey(r.started_at))}">
    <span class="timeline-time">${fmtClock(r.started_at)}</span>
    ${icon}
    <span>
      <span class="rank-name">${escapeHtml(r.name)}</span>
      ${idle}${parts}${open}
    </span>
    <span class="rank-meta">${fmtDur(r.sec)}</span>
  </li>`;
}

function daySessionGroupHtml(g) {
  if (g.sessions.length === 1) return daySessionRowHtml(g.sessions[0]);
  const icon = g.icon_url
    ? iconImgHtml(g.icon_url, 28)
    : `<span class="rank-icon">•</span>`;
  const cat = categoryClass(g.category);
  const span =
    g.earliest_started !== g.latest_started
      ? `${fmtClock(g.earliest_started)}–${fmtClock(g.latest_started)}`
      : fmtClock(g.latest_started);
  const live = g.has_live ? `<span class="timeline-live">сейчас</span>` : "";
  const openClass = g.has_live ? " is-open" : "";
  const expanded = g.has_live ? "true" : "false";
  const hidden = g.has_live ? "" : " hidden";
  return `<li class="session-group timeline-cat-${cat}${openClass}" data-group="${escapeHtml(g.key)}">
    <button type="button" class="session-group-toggle" aria-expanded="${expanded}">
      <span class="timeline-time">${fmtClock(g.latest_started)}</span>
      ${icon}
      <span class="session-group-text">
        <span class="rank-name">${escapeHtml(g.name)}</span>
        <span class="session-group-meta">${sessionVisitLabel(g.visits)} · ${span}</span>
        ${live}
      </span>
      <span class="rank-meta">${fmtDur(g.sec)}</span>
      <span class="session-group-chev" aria-hidden="true"></span>
    </button>
    <ol class="session-group-items"${hidden}>
      ${g.sessions.map((r) => daySessionRowHtml(r)).join("")}
    </ol>
  </li>`;
}

function wireSessionGroups(listEl) {
  if (!listEl || listEl.dataset.sessionGroupsWired === "1") return;
  listEl.dataset.sessionGroupsWired = "1";
  listEl.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".session-group-toggle");
    if (!btn || !listEl.contains(btn)) return;
    ev.preventDefault();
    const group = btn.closest(".session-group");
    if (!group) return;
    const open = group.classList.toggle("is-open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    const items = group.querySelector(":scope > .session-group-items");
    if (items) items.hidden = !open;
  });
}

async function refreshTimeline({ skeleton = false } = {}) {
  ensureSelectedDay();
  renderDayWeekStrip();
  const gantt = document.getElementById("dayGantt");
  const list = document.getElementById("timelineList");
  const ctx = `day|${selectedDayIso}|${filterEmployeeId || ""}|${dayGanttMode}`;
  const show =
    skeleton ||
    needsSkeleton(gantt, "day-gantt", ctx, { force: skeleton }) ||
    needsSkeleton(list, "day-list", ctx, { force: skeleton });
  if (show) {
    lastDayViewKey = "";
    showSkeleton(gantt, "gantt");
    showSkeleton(list, "list", 8);
    const line = document.getElementById("daySummaryLine");
    if (line) line.textContent = "Загрузка…";
  }
  try {
    const { from, to } = dayQueryBounds(selectedDayIso);
    const emp = filterEmployeeId ? `&employee_id=${encodeURIComponent(filterEmployeeId)}` : "";
    const q = `day=${encodeURIComponent(selectedDayIso)}${emp}`;
    const [rowsRes, summaryRes] = await Promise.allSettled([
      api(`/api/timeline?${q}`, { quiet402: true }),
      api(`/api/summary?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}${emp}`, {
        quiet402: true,
      }),
    ]);
    const rows = rowsRes.status === "fulfilled" ? rowsRes.value || [] : [];
    const summary = summaryRes.status === "fulfilled" ? summaryRes.value || {} : {};
    const gated =
      (rowsRes.status !== "fulfilled" &&
        (rowsRes.reason?.code === "history_limit" || rowsRes.reason?.code === "pro_required")) ||
      (summaryRes.status !== "fulfilled" &&
        (summaryRes.reason?.code === "history_limit" ||
          summaryRes.reason?.code === "pro_required"));
    if (rowsRes.status !== "fulfilled" && !gated) {
      console.error(rowsRes.reason);
      showToast("Не удалось загрузить ленту дня", "error");
    }

    const feedRows = compactFeedRows(rows);
    const feedGroups = groupFeedByApp(feedRows);
    const viewKey = [
      selectedDayIso,
      filterEmployeeId || "",
      gated ? "gated" : "ok",
      dayGanttMode,
      summaryKey(summary),
      dayTimelineSignature(rows),
      `feed:${feedRows.length}`,
      `groups:${feedGroups.length}`,
    ].join("|");
    if (viewKey === lastDayViewKey && !show) return;
    lastDayViewKey = viewKey;

    const el = document.getElementById("timelineList");
    if (gated) {
      renderDayGantt([]);
      renderDaySummaryLine({}, { gated: true });
      if (el) {
        clearSkel(el);
        el.innerHTML = `<li><span class="timeline-time">—</span><span class="rank-icon">•</span><span class="rank-name">История дальше Free-лимита — доступно в Pro</span><span class="rank-meta"></span></li>`;
      }
      markSkelContext("day-gantt", ctx);
      markSkelContext("day-list", ctx);
      return;
    }

    // Day strip keeps full detail; the list groups by app instead of a long ribbon.
    renderDayGantt(rows);
    renderDaySummaryLine(summary);

    if (!el) {
      markSkelContext("day-gantt", ctx);
      markSkelContext("day-list", ctx);
      return;
    }
    clearSkel(el);
    if (!feedGroups.length) {
      el.innerHTML = `<li><span class="timeline-time">—</span><span class="rank-icon">•</span><span class="rank-name">Пока нет сессий</span><span class="rank-meta"></span></li>`;
      markSkelContext("day-gantt", ctx);
      markSkelContext("day-list", ctx);
      return;
    }
    wireSessionGroups(el);
    el.innerHTML = feedGroups.map((g) => daySessionGroupHtml(g)).join("");
    markSkelContext("day-gantt", ctx);
    markSkelContext("day-list", ctx);
  } catch (err) {
    console.error(err);
    showToast(err?.message || "Не удалось загрузить день", "error");
  }
}
function selectDay(iso) {
  const today = localDayIso();
  let next = iso || today;
  if (next > today) next = today;
  selectedDayIso = next;
  return refreshTimeline({ skeleton: true });
}

function shiftSelectedWeek(deltaDays) {
  ensureSelectedDay();
  const today = localDayIso();
  let next = shiftDayIso(selectedDayIso, deltaDays);
  if (next > today) next = today;
  selectedDayIso = next;
  return refreshTimeline({ skeleton: true });
}

async function refreshRatings({ skeleton = false } = {}) {
  const el = document.getElementById("ratingsList");
  const ctx = "ratings|today";
  const show = skeleton || needsSkeleton(el, "ratings", ctx, { force: skeleton });
  if (show) showSkeleton(el, "rating", 5);
  const rows = await api("/api/ratings");
  if (!el) return;
  clearSkel(el);
  if (!rows.length) {
    el.innerHTML = `<p class="hint">Сегодня ещё нет приложений и сайтов для оценки.</p>`;
    markSkelContext("ratings", ctx);
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
  markSkelContext("ratings", ctx);
}

function wireGroupedLists() {
  const toggle = (ev) => {
    const row = ev.target.closest(".rank-row-parent.is-expandable");
    if (!row) return;
    const key = row.dataset.groupKey;
    if (!key) return;
    if (expandedActivityGroups.has(key)) expandedActivityGroups.delete(key);
    else expandedActivityGroups.add(key);
    if (key.startsWith("usage:")) {
      renderGroupedList(document.getElementById("activitiesList"), groupedUsageCache, "Занятий пока нет", {
        searchInput: document.getElementById("activitySearchUsage"),
        moreBtn: document.getElementById("activitiesListMore"),
        limit: groupedUsageLimit,
        showShare: true,
        total: groupedUsageCache.reduce((s, r) => s + (r.sec || 0), 0),
        cacheKey: "usage",
      });
    }
  };
  document.getElementById("activitiesList")?.addEventListener("click", toggle);
  document.getElementById("activitiesList")?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      toggle(ev);
    }
  });

  const searchUsage = document.getElementById("activitySearchUsage");
  searchUsage?.addEventListener("input", () => {
    renderGroupedList(document.getElementById("activitiesList"), groupedUsageCache, "Занятий пока нет", {
      searchInput: searchUsage,
      moreBtn: document.getElementById("activitiesListMore"),
      limit: groupedUsageLimit,
      showShare: true,
      total: groupedUsageCache.reduce((s, r) => s + (r.sec || 0), 0),
      cacheKey: "usage",
    });
  });

  document.getElementById("activitiesListMore")?.addEventListener("click", () => {
    groupedUsageLimit += GROUPED_PAGE;
    renderGroupedList(document.getElementById("activitiesList"), groupedUsageCache, "Занятий пока нет", {
      searchInput: document.getElementById("activitySearchUsage"),
      moreBtn: document.getElementById("activitiesListMore"),
      limit: groupedUsageLimit,
      showShare: true,
      total: groupedUsageCache.reduce((s, r) => s + (r.sec || 0), 0),
      cacheKey: "usage",
    });
  });
}

function wireUi() {
  wireSettingsSearch();
  wireThemeToggle();
  wireZoomControls();
  wireNavMore();
  restoreChartScales();
  syncDayGanttModeButtons();
  document.querySelectorAll("[data-gantt-mode]").forEach((btn) => {
    btn.addEventListener("click", () => setDayGanttMode(btn.dataset.ganttMode));
  });
  wireGroupedLists();
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.setAttribute("role", "tab");
    tab.addEventListener("click", () => {
      setActiveTab(tab.dataset.tab);
      if (tab.dataset.tab === "shots") refreshShots({ skeleton: true });
      if (tab.dataset.tab === "settings") loadSettings();
      if (tab.dataset.tab === "day") {
        ensureSelectedDay();
        refreshTimeline({ skeleton: true }).catch(() => {});
      }
      if (tab.dataset.tab === "today") refreshSummary({ skeleton: true }).catch(() => {});
      if (tab.dataset.tab === "ratings") refreshRatings({ skeleton: true });
      if (tab.dataset.tab === "projects") refreshProjects({ skeleton: true });
      if (tab.dataset.tab === "usage") refreshUsageReport({ skeleton: true });
      if (tab.dataset.tab === "meetings") refreshMeetings({ skeleton: true }).catch(() => {});
    });
  });

  document.getElementById("refreshShotsBtn")?.addEventListener("click", async () => {
    const btn = document.getElementById("refreshShotsBtn");
    if (btn) {
      btn.disabled = true;
      btn.classList.add("is-busy");
    }
    try {
      await refreshShots({ skeleton: true });
      showToast("Скриншоты обновлены", "ok");
    } catch (err) {
      showToast(err?.message || "Не удалось обновить скриншоты", "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.classList.remove("is-busy");
      }
    }
  });

  document.getElementById("shotsShowDetails")?.addEventListener("change", (ev) => {
    shotsShowDetails = !!ev.currentTarget.checked;
    renderShotsGrid();
  });
  wireShotsDayPicker();
  wireShotsAppFilter();
  ensureShotsDayInput();

  document.addEventListener("keydown", (ev) => {
    const box = document.getElementById("shotLightbox");
    if (box && !box.hidden) return;
    const tag = (ev.target && ev.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || ev.target?.isContentEditable) {
      return;
    }
    const refreshKey =
      ev.key === "F5" || ((ev.ctrlKey || ev.metaKey) && (ev.key === "r" || ev.key === "R"));
    if (!refreshKey) return;
    ev.preventDefault();
    refreshCurrentView().catch(() => {});
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    if (currentTabName() === "shots") refreshShots().catch(() => {});
  });

  window.addEventListener("hashchange", () => {
    const name = (location.hash || "#today").replace(/^#/, "") || "today";
    const known = ["today", "day", "usage", "projects", "ratings", "shots", "settings", "meetings"];
    if (!known.includes(name)) return;
    setActiveTab(name, { syncHash: false });
    if (name === "today") refreshSummary({ skeleton: true }).catch(() => {});
    if (name === "day") {
      ensureSelectedDay();
      refreshTimeline({ skeleton: true }).catch(() => {});
    }
    if (name === "usage") refreshUsageReport({ skeleton: true }).catch(() => {});
    if (name === "projects") refreshProjects({ skeleton: true }).catch(() => {});
    if (name === "ratings") refreshRatings({ skeleton: true }).catch(() => {});
    if (name === "shots") refreshShots({ skeleton: true }).catch(() => {});
    if (name === "meetings") refreshMeetings({ skeleton: true }).catch(() => {});
    if (name === "settings") loadSettings().catch(() => {});
  });

  const dayPanel = document.getElementById("panel-day");
  if (dayPanel) {
    dayPanel.addEventListener("click", (ev) => {
      const pick = ev.target.closest("[data-pick-day]");
      if (pick && !pick.disabled) {
        ev.preventDefault();
        selectDay(pick.dataset.pickDay).catch(() => {});
        return;
      }
      const shift = ev.target.closest("[data-shift-week]");
      if (shift && !shift.disabled) {
        ev.preventDefault();
        shiftSelectedWeek(Number(shift.dataset.shiftWeek) || 0).catch(() => {});
        return;
      }
      if (ev.target.closest("[data-go-today]")) {
        ev.preventDefault();
        selectDay(localDayIso()).catch(() => {});
      }
    });
  }

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

  const filterEmployee = document.getElementById("filterEmployeeToday");
  if (filterEmployee) {
    filterEmployee.addEventListener("change", async () => {
      filterEmployeeId = filterEmployee.value || "";
      lastSummaryKey = "";
      lastMeetingsKey = "";
      await refreshSummary();
      await refreshUsageReport();
      await refreshTimeline();
      if (document.getElementById("panel-meetings")?.classList.contains("active")) {
        await refreshMeetings().catch(() => {});
      }
    });
  }

  const usagePeriodSel = document.getElementById("usagePeriod");
  if (usagePeriodSel) {
    usagePeriodSel.addEventListener("change", async () => {
      usagePeriod = usagePeriodSel.value || "today";
      await refreshUsageReport();
    });
  }

  const meetingsPeriodSel = document.getElementById("meetingsPeriod");
  if (meetingsPeriodSel) {
    meetingsPeriodSel.addEventListener("change", async () => {
      meetingsPeriod = meetingsPeriodSel.value || "today";
      lastMeetingsKey = "";
      await refreshMeetings();
    });
  }
  document.getElementById("refreshMeetingsBtn")?.addEventListener("click", () => {
    lastMeetingsKey = "";
    refreshMeetings().catch(() => {});
  });

  const trendsPeriodSel = document.getElementById("trendsPeriod");
  const trendsCustomRange = document.getElementById("trendsCustomRange");
  const trendsFrom = document.getElementById("trendsFrom");
  const trendsTo = document.getElementById("trendsTo");
  const trendsApply = document.getElementById("trendsApplyCustom");
  const syncTrendsCustomVisibility = () => {
    if (trendsCustomRange) {
      trendsCustomRange.hidden = trendsPeriod !== "custom";
    }
  };
  syncTrendsPeriodOptions();
  syncTrendsCustomVisibility();
  if (trendsPeriodSel) {
    trendsPeriodSel.addEventListener("change", async () => {
      trendsPeriod = trendsPeriodSel.value || "7";
      syncTrendsCustomVisibility();
      if (trendsPeriod === "custom") {
        const today = localDayIso();
        const weekAgo = shiftDayIso(today, -6);
        if (trendsFrom && !trendsFrom.value) trendsFrom.value = weekAgo;
        if (trendsTo && !trendsTo.value) trendsTo.value = today;
        return;
      }
      await refreshTrends();
    });
  }
  if (trendsApply) {
    trendsApply.addEventListener("click", async () => {
      trendsCustomFrom = trendsFrom?.value || "";
      trendsCustomTo = trendsTo?.value || "";
      if (!trendsCustomFrom || !trendsCustomTo) return;
      if (trendsCustomFrom > trendsCustomTo) {
        const tmp = trendsCustomFrom;
        trendsCustomFrom = trendsCustomTo;
        trendsCustomTo = tmp;
        if (trendsFrom) trendsFrom.value = trendsCustomFrom;
        if (trendsTo) trendsTo.value = trendsCustomTo;
      }
      trendsPeriod = "custom";
      if (trendsPeriodSel) trendsPeriodSel.value = "custom";
      syncTrendsCustomVisibility();
      await refreshTrends();
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

  const projectsSortSel = document.getElementById("projectsSort");
  if (projectsSortSel) {
    projectsSortSel.addEventListener("change", async () => {
      projectsSort = projectsSortSel.value === "name" ? "name" : "time";
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
        expandedReportProjects.add(String(created.id));
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

  const projectsList = document.getElementById("projectsList");
  if (projectsList) {
    projectsList.addEventListener("submit", async (ev) => {
      const form = ev.target.closest("[data-create-task-for]");
      if (!form) return;
      ev.preventDefault();
      const projectId = form.dataset.createTaskFor;
      if (!projectId) return;
      const nameInput = form.elements.namedItem("name");
      const name = String(nameInput && "value" in nameInput ? nameInput.value : "").trim();
      if (!name) return;
      try {
        const created = await api("/api/tasks", {
          method: "POST",
          body: JSON.stringify({ project_id: Number(projectId), name }),
        });
        form.reset();
        selectedProjectId = String(projectId);
        expandedReportProjects.add(String(projectId));
        await setFocus(projectId, created.id);
        await refreshProjects();
        showToast(`Задача «${name}» создана`, "ok");
      } catch (err) {
        console.error(err);
        showToast(err?.message || "Не удалось создать задачу", "error");
      }
    });

    projectsList.addEventListener("click", async (ev) => {
      const delProjectBtn = ev.target.closest("[data-del-project]");
      if (delProjectBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        if (!confirm("Удалить проект и его задачи?")) return;
        const pid = String(delProjectBtn.dataset.delProject);
        await api(`/api/projects/${pid}`, { method: "DELETE" });
        expandedReportProjects.delete(pid);
        if (selectedProjectId === pid) selectedProjectId = "";
        const cur = document.getElementById("currentProjectSelect");
        if (cur && String(cur.value) === pid) {
          await setFocus(null, null);
        }
        await refreshProjects();
        return;
      }

      const focusBtn = ev.target.closest("[data-focus-task]");
      if (focusBtn) {
        ev.preventDefault();
        const pid = focusBtn.dataset.projectId || selectedProjectId;
        selectedProjectId = String(pid || "");
        await setFocus(pid, focusBtn.dataset.focusTask);
        await refreshProjects();
        return;
      }

      const doneBtn = ev.target.closest("[data-toggle-done]");
      if (doneBtn) {
        ev.preventDefault();
        const id = doneBtn.dataset.toggleDone;
        const row = doneBtn.closest("[data-project-id]");
        const pid = row ? row.dataset.projectId : "";
        const tasks = pid ? tasksByProjectCache[String(pid)] || [] : taskCache;
        const task = tasks.find((t) => String(t.id) === String(id));
        await api(`/api/tasks/${id}`, {
          method: "PUT",
          body: JSON.stringify({ done: !(task && task.done) }),
        });
        await refreshProjects();
        return;
      }

      const delTaskBtn = ev.target.closest("[data-del-task]");
      if (delTaskBtn) {
        ev.preventDefault();
        if (!confirm("Удалить задачу?")) return;
        await api(`/api/tasks/${delTaskBtn.dataset.delTask}`, { method: "DELETE" });
        await refreshProjects();
        return;
      }

      const toggleBtn = ev.target.closest("[data-toggle-project]");
      if (toggleBtn) {
        ev.preventDefault();
        const key = toggleBtn.dataset.toggleProject;
        if (expandedReportProjects.has(key)) expandedReportProjects.delete(key);
        else {
          expandedReportProjects.add(key);
          if (key !== "null") selectedProjectId = key;
        }
        await refreshProjects();
      }
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
      welcome_back_enabled: form.welcome_back_enabled ? form.welcome_back_enabled.checked : true,
      welcome_back_after_sec: form.welcome_back_after_sec
        ? Number(form.welcome_back_after_sec.value)
        : 600,
      poor_time_popup: form.poor_time_popup.checked,
      blur_screenshots: form.blur_screenshots.checked,
      screenshot_interval_sec: Number.isFinite(interval) ? Math.max(60, Math.min(3600, interval)) : 300,
      screenshots_enabled: form.screenshots_enabled.checked,
      screenshot_on_app_switch: form.screenshot_on_app_switch.checked,
      screenshot_retention_days: Number(form.screenshot_retention_days.value),
      screenshots_dir: form.screenshots_dir ? form.screenshots_dir.value.trim() : "",
      open_dashboard_on_start: form.open_dashboard_on_start.checked,
      autostart: form.autostart.checked,
      show_mini_tracker: form.show_mini_tracker ? form.show_mini_tracker.checked : true,
      work_mode: form.work_mode ? form.work_mode.checked : false,
      work_chat_keywords: keywords,
      company_mode: form.company_mode ? form.company_mode.checked : false,
      company_display_name: form.company_display_name ? form.company_display_name.value.trim() : "",
      listen_host: form.listen_host ? form.listen_host.value : "127.0.0.1",
      hub_url: form.hub_url ? form.hub_url.value.trim() : "",
      hub_ingest_token: form.hub_ingest_token ? form.hub_ingest_token.value.trim() : "",
      rdp_vision_consent: form.rdp_vision_consent ? form.rdp_vision_consent.checked : false,
      rdp_vision_enabled: form.rdp_vision_enabled ? form.rdp_vision_enabled.checked : false,
      rdp_vision_api_key: form.rdp_vision_api_key ? form.rdp_vision_api_key.value.trim() : "",
      rdp_vision_interval_sec: form.rdp_vision_interval_sec
        ? Number(form.rdp_vision_interval_sec.value)
        : 180,
      rdp_vision_base_url: form.rdp_vision_base_url
        ? form.rdp_vision_base_url.value.trim()
        : "https://api.openai.com/v1",
      rdp_vision_model: form.rdp_vision_model ? form.rdp_vision_model.value.trim() : "gpt-4o-mini",
    };
    try {
      const saved = await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
      form.screenshot_interval_sec.value = saved.screenshot_interval_sec ?? body.screenshot_interval_sec;
      if (form.screenshots_dir) {
        form.screenshots_dir.value = saved.screenshots_dir || "";
      }
      companyMode = !!saved.company_mode;
      updateCompanyUiVisibility();
      await refreshCompanyPanel();
      updateStorageHint(saved);
      lastSummaryKey = "";
      lastStatusKey = "";
      await refreshSummary();
      await refreshStatus();
      const bindNote = saved.listen_host === "0.0.0.0" ? " · перезапустите для LAN" : "";
      const msg = `Сохранено · интервал ${saved.screenshot_interval_sec} сек${bindNote}`;
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

  const addEmpBtn = document.getElementById("addEmployeeBtn");
  if (addEmpBtn) {
    addEmpBtn.addEventListener("click", async () => {
      const input = document.getElementById("newEmployeeName");
      const name = (input?.value || "").trim();
      if (!name) return;
      try {
        const row = await api("/api/company/employees", {
          method: "POST",
          body: JSON.stringify({ display_name: name, role: "member" }),
        });
        if (input) input.value = "";
        const hint = document.getElementById("companyTokenHint");
        if (hint && row.ingest_token) {
          hint.hidden = false;
          hint.textContent = `Токен для ${row.display_name}: ${row.ingest_token}`;
        }
        await refreshCompanyPanel();
        lastSummaryKey = "";
        await refreshSummary();
      } catch (err) {
        showToast(err?.message || "Не удалось добавить сотрудника", "error");
      }
    });
  }

  document.body.addEventListener("click", async (ev) => {
    const rotate = ev.target.closest?.("[data-rotate-token]");
    if (rotate) {
      ev.preventDefault();
      try {
        await showEmployeeToken(rotate.getAttribute("data-rotate-token"));
      } catch (err) {
        showToast(err?.message || "Не удалось выдать токен", "error");
      }
      return;
    }
    const toggle = ev.target.closest?.("[data-toggle-emp]");
    if (toggle) {
      ev.preventDefault();
      const id = toggle.getAttribute("data-toggle-emp");
      const active = toggle.getAttribute("data-active") === "1";
      try {
        await api(`/api/company/employees/${id}`, {
          method: "PUT",
          body: JSON.stringify({ active: !active }),
        });
        await refreshCompanyPanel();
        lastSummaryKey = "";
        await refreshSummary();
      } catch (err) {
        showToast(err?.message || "Не удалось обновить сотрудника", "error");
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

  async function refreshGoogleAuthSettings() {
    const statusEl = document.getElementById("googleAuthStatus");
    const linkBtn = document.getElementById("googleLinkBtn");
    const unlinkBtn = document.getElementById("googleUnlinkBtn");
    if (!statusEl || !linkBtn || !unlinkBtn) return;
    try {
      const st = await fetch("/api/auth/status").then((r) => r.json());
      if (!st.google_configured) {
        statusEl.textContent = "Google OAuth не настроен (нет client credentials).";
        linkBtn.hidden = true;
        unlinkBtn.hidden = true;
        return;
      }
      if (st.google_linked) {
        statusEl.textContent = st.google_email
          ? `Привязан: ${st.google_email}`
          : "Google-аккаунт привязан.";
        linkBtn.hidden = true;
        unlinkBtn.hidden = !st.password_set;
      } else {
        statusEl.textContent = st.google_redirect_uri
          ? `Не привязан. В Google Cloud Clients добавьте redirect: ${st.google_redirect_uri}`
          : "Не привязан. Можно войти через Google после привязки.";
        linkBtn.hidden = false;
        unlinkBtn.hidden = true;
      }
    } catch (_) {
      statusEl.textContent = "Не удалось загрузить статус Google.";
    }
  }
  refreshGoogleAuthSettings();

  document.getElementById("googleUnlinkBtn")?.addEventListener("click", async () => {
    if (!confirm("Отвязать Google? Вход останется по паролю.")) return;
    try {
      await api("/api/auth/google/unlink", { method: "POST" });
      showToast("Google отвязан", "ok");
      await refreshGoogleAuthSettings();
    } catch (e) {
      showToast(e?.message || "Не удалось отвязать Google", "error");
    }
  });

  document.getElementById("logoutBtn").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" });
    location.href = "/login";
  });

  document.getElementById("clearBtn").addEventListener("click", async () => {
    if (!confirm("Удалить все локальные сессии и записи скриншотов?")) return;
    lastSummaryKey = "";
    lastDayViewKey = "";
    await api("/api/data/clear", { method: "POST" });
    await refreshSummary();
    await refreshShots();
    await loadSettings();
  });

  document.getElementById("licenseActivateBtn")?.addEventListener("click", async () => {
    const key = document.getElementById("licenseKeyInput")?.value || "";
    try {
      const res = await api("/api/license/activate", {
        method: "POST",
        body: JSON.stringify({ key }),
      });
      applyEntitlements(res.entitlements);
      showToast("Лицензия активирована", "ok");
      await loadSettings();
    } catch (e) {
      showToast(e.message || "Не удалось активировать", "error");
    }
  });

  document.getElementById("licenseDeactivateBtn")?.addEventListener("click", async () => {
    if (!confirm("Снять локальный ключ? Лимиты Free применятся сразу (если trial истёк).")) return;
    const res = await api("/api/license/deactivate", { method: "POST", body: "{}" });
    applyEntitlements(res.entitlements);
    showToast("Ключ снят", "ok");
  });

  const downloadExport = async (path, filename) => {
    try {
      const res = await fetch(path);
      if (res.status === 402) {
        const raw = await res.text();
        let message = "Нужен Pro";
        try {
          const parsed = JSON.parse(raw);
          message = parsed?.detail?.message || message;
          if (parsed?.detail?.entitlements) applyEntitlements(parsed.detail.entitlements);
        } catch (_) {}
        showPaywall(message);
        return;
      }
      if (!res.ok) throw new Error("export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      showToast(e.message || "Экспорт не удался", "error");
    }
  };
  document.getElementById("exportJsonBtn")?.addEventListener("click", () => {
    downloadExport("/api/export/json", "deskline-export.json");
  });
  document.getElementById("exportCsvBtn")?.addEventListener("click", () => {
    downloadExport("/api/export/csv", "deskline-trends.csv");
  });

  document.getElementById("onboardDoneBtn")?.addEventListener("click", async () => {
    await api("/api/onboarding/complete", { method: "POST", body: JSON.stringify({ done: true }) });
    const modal = document.getElementById("onboardModal");
    if (modal) modal.hidden = true;
  });

  document.getElementById("paywallCloseBtn")?.addEventListener("click", () => {
    const modal = document.getElementById("paywallModal");
    if (modal) modal.hidden = true;
  });

  const activityModal = document.getElementById("activityDetailModal");
  const closeActivity = () => closeActivityDetail();
  document.getElementById("activityDetailClose")?.addEventListener("click", closeActivity);
  document.getElementById("activityDetailDismiss")?.addEventListener("click", closeActivity);
  activityModal?.addEventListener("click", (ev) => {
    if (ev.target === activityModal) closeActivity();
  });
  document.getElementById("activityDetailUsage")?.addEventListener("click", () => {
    closeActivity();
  });
  // Block background scroll while the modal is open (wheel/trackpad on the scrim).
  const blockBgScroll = (ev) => {
    if (!activityModal || activityModal.hidden) return;
    const card = ev.target.closest?.(".activity-detail-card");
    if (card) {
      const canScroll = card.scrollHeight > card.clientHeight + 1;
      if (canScroll) return;
    }
    ev.preventDefault();
  };
  activityModal?.addEventListener("wheel", blockBgScroll, { passive: false });
  activityModal?.addEventListener("touchmove", blockBgScroll, { passive: false });
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    if (activityModal && !activityModal.hidden) closeActivity();
  });

  document.getElementById("rdpVisionConfirmBtn")?.addEventListener("click", async () => {
    const modal = document.getElementById("rdpVisionModal");
    const label = modal?.dataset.label || "";
    const sid = modal?.dataset.sessionId;
    try {
      await api("/api/rdp-vision/confirm", {
        method: "POST",
        body: JSON.stringify({
          label,
          session_id: sid ? Number(sid) : null,
        }),
      });
      showToast(`Засчитано: ${label}`, "ok");
    } catch (e) {
      showToast(e.message || "Не удалось подтвердить", "error");
    }
    if (modal) modal.hidden = true;
    _rdpVisionShownKey = "";
    lastStatusKey = "";
    lastSummaryKey = "";
    lastDayViewKey = "";
    await refreshStatus().catch(() => {});
    await refreshSummary().catch(() => {});
  });
  document.getElementById("rdpVisionSkipBtn")?.addEventListener("click", async () => {
    try {
      await api("/api/rdp-vision/skip", { method: "POST", body: "{}" });
    } catch (_) {}
    const modal = document.getElementById("rdpVisionModal");
    if (modal) modal.hidden = true;
    _rdpVisionShownKey = "";
    lastStatusKey = "";
  });
}

async function boot() {
  const splash = document.getElementById("appSplash");
  const markShellReady = () => document.body.classList.add("is-shell-ready");
  const finishSplash = () => {
    if (!splash) {
      markShellReady();
      return;
    }
    splash.classList.remove("is-playing", "is-leaving");
    splash.classList.add("is-done");
    sessionStorage.setItem("deskline_splash_done", "1");
    markShellReady();
  };
  if (splash && !sessionStorage.getItem("deskline_splash_done")) {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      finishSplash();
    } else {
      requestAnimationFrame(() => splash.classList.add("is-playing"));
      if (document.fonts?.ready) {
        try {
          await Promise.race([
            document.fonts.ready,
            new Promise((r) => window.setTimeout(r, 400)),
          ]);
        } catch (_) {}
      }
      window.setTimeout(() => splash.classList.add("is-leaving"), 1950);
      window.setTimeout(finishSplash, 2480);
    }
  } else if (splash) {
    splash.classList.add("is-done");
    markShellReady();
  } else {
    markShellReady();
  }
  wireUi();
  await maybeShowOnboarding().catch(() => {});
  ensureSelectedDay();
  await refreshCompanyPanel().catch(() => {});
  const hashTab = (location.hash || "").replace(/^#/, "");
  const known = ["today", "day", "usage", "meetings", "projects", "ratings", "shots", "settings"];
  if (known.includes(hashTab)) {
    setActiveTab(hashTab, { syncHash: false });
  } else {
    setActiveTab("today");
  }
  await Promise.all([
    refreshSummary(),
    refreshStatus(),
    refreshProjects(),
    refreshUsageReport(),
  ]);
  if ((location.hash || "").replace(/^#/, "") === "day") {
    await refreshTimeline().catch(() => {});
  }
  setInterval(() => {
    refreshSummary().catch(() => {});
    refreshStatus().catch(() => {});
    refreshUsageReport().catch(() => {});
    if (document.getElementById("panel-day")?.classList.contains("active")) {
      if (selectedDayIso === localDayIso()) {
        refreshTimeline().catch(() => {});
      }
    }
    if (document.getElementById("panel-meetings")?.classList.contains("active")) {
      refreshMeetings().catch(() => {});
    }
  }, 5000);
}

boot().catch((err) => {
  console.error(err);
  document.getElementById("focusSub").textContent = "Ошибка загрузки";
});
