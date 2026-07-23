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
let lastBarsKey = "";
/** @type {string} YYYY-MM-DD — always defaults to today */
let selectedDayIso = "";

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
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    location.href = "/login";
    throw new Error("auth required");
  }
  if (!res.ok) {
    const raw = await res.text();
    let message = raw || res.statusText || "Request failed";
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed.detail === "string") message = parsed.detail;
      else if (parsed && Array.isArray(parsed.detail)) {
        message = parsed.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      }
    } catch (_) {}
    throw new Error(message);
  }
  if (res.status === 204) return null;
  return res.json();
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
  if (aliases[name]) setUsageSlice(name);
  if (syncHash) {
    const next = `#${tab}`;
    if (location.hash !== next) {
      history.replaceState(null, "", next);
    }
  }
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

function renderKpis(summary, team) {
  const el = document.getElementById("kpiStrip");
  if (!el) return;
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

function renderTopProjectsPulse(summary) {
  const el = document.getElementById("topProjectsPulse");
  if (!el) return;
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

function renderTodayTimelineStrip(rows, summary) {
  const el = document.getElementById("todayTimelineStrip");
  const meta = document.getElementById("todayTimelineMeta");
  if (!el) return;
  const list = rows || [];
  if (!list.length) {
    el.innerHTML = `<p class="hint">Пока нет сессий за сегодня.</p>`;
    if (meta) meta.textContent = "";
    return;
  }
  const startMs = Math.min(...list.map((r) => new Date(r.started_at).getTime()));
  const endMs = Math.max(...list.map((r) => new Date(r.ended_at || Date.now()).getTime()));
  const span = Math.max(endMs - startMs, 1);
  const startLabel = fmtClock(new Date(startMs).toISOString());
  const endLabel = fmtClock(new Date(endMs).toISOString());
  if (meta) {
    meta.textContent = fmtDur(summary?.total_sec || 0);
  }

  const hours = [];
  const startH = new Date(startMs);
  startH.setMinutes(0, 0, 0);
  for (let t = startH.getTime(); t <= endMs; t += 3600 * 1000) {
    const left = ((t - startMs) / span) * 100;
    if (left < -1 || left > 101) continue;
    hours.push(
      `<span class="pulse-hour" style="left:${left}%"><b>${fmtClock(new Date(t).toISOString())}</b></span>`
    );
  }

  const segs = list
    .map((r) => {
      const a = new Date(r.started_at).getTime();
      const b = new Date(r.ended_at || Date.now()).getTime();
      const left = ((a - startMs) / span) * 100;
      const width = Math.max(0.35, ((b - a) / span) * 100);
      const idleRatio = r.sec > 0 ? Math.min(1, (r.idle_sec || 0) / r.sec) : 0;
      const cat = idleRatio >= 0.55 ? "idle" : categoryClass(r.category);
      return `<span class="pulse-seg ${cat}" style="left:${left}%;width:${width}%" title="${escapeHtml(r.name || "")}: ${fmtDur(r.sec)}"></span>`;
    })
    .join("");

  el.innerHTML = `
    <div class="pulse-ribbon-meta">
      <span>с ${startLabel}</span>
      <span class="pulse-ribbon-total">${fmtDur(summary?.total_sec || 0)}</span>
      <span>до ${endLabel}</span>
    </div>
    <div class="pulse-hour-row">${hours.join("")}</div>
    <div class="pulse-track">${segs}</div>
    <div class="pulse-legend">
      <span><i class="productive"></i>Фокус</span>
      <span><i class="neutral"></i>Нейтрально</span>
      <span><i class="distracting"></i>Отвлечения</span>
      <span><i class="idle"></i>Простой</span>
    </div>`;
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

function renderPieChart(el, slices, total, emptyText) {
  if (!el) return;
  const usable = (slices || []).filter((s) => (s.sec || 0) > 0);
  if (!usable.length || !total) {
    el.innerHTML = `<p class="hint">${emptyText || "Пока нет данных."}</p>`;
    return;
  }
  const cx = 60;
  const cy = 60;
  const rOut = 52;
  const rIn = 34;
  let angle = 0;
  const paths = usable
    .map((s) => {
      const sweep = (s.sec / total) * 360;
      const d = donutSegmentPath(cx, cy, rOut, rIn, angle, angle + sweep);
      angle += sweep;
      if (!d) return "";
      return `<path d="${d}" fill="${s.color}" stroke="#fff" stroke-width="1.5"/>`;
    })
    .join("");
  const primary = usable[0];
  const primaryPct = Math.round((primary.sec / total) * 100);
  el.innerHTML = `<div class="pie-layout">
    <div class="donut-wrap" role="img" aria-label="Диаграмма">
      <svg class="donut-svg" viewBox="0 0 120 120" width="148" height="148">
        <circle cx="60" cy="60" r="43" fill="none" stroke="rgba(21,36,31,0.06)" stroke-width="16"/>
        ${paths}
      </svg>
      <div class="donut-center">
        <strong>${primaryPct}%</strong>
        <span>${escapeHtml(primary.label)}</span>
      </div>
    </div>
    <ul class="pie-legend">
      ${usable
        .map((s) => {
          const share = Math.round((s.sec / total) * 100);
          return `<li>
            <span class="pie-swatch" style="background:${s.color}"></span>
            <span class="pie-name">${escapeHtml(s.label)}</span>
            <span class="pie-meta">${fmtDur(s.sec)} · ${share}%</span>
          </li>`;
        })
        .join("")}
    </ul>
  </div>`;
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

function renderDayKpis(summary) {
  const el = document.getElementById("dayKpiStrip");
  if (!el) return;
  const total = summary.total_sec || 0;
  const idlePct = total ? Math.round(((summary.idle_sec || 0) / total) * 100) : 0;
  const items = [
    { label: "Всего", value: fmtDur(total), sub: formatDayTitle(selectedDayIso) },
    { label: "Активно", value: fmtDur(summary.active_sec), sub: `${summary.activity_pct ?? 0}%` },
    { label: "Без ввода", value: `${idlePct}%`, sub: fmtDur(summary.idle_sec) },
    { label: "Фокус", value: `${summary.focus_pct ?? 0}%`, sub: fmtDur(summary.focus_sec) },
  ];
  el.innerHTML = items
    .map(
      (it) => `<div class="kpi-card">
        <span class="kpi-label">${it.label}</span>
        <strong class="kpi-value">${it.value}</strong>
        <span class="kpi-sub">${escapeHtml(it.sub)}</span>
      </div>`
    )
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
  const aside = document.getElementById("hoursTrendAside");
  if (aside) aside.textContent = `${rows.length || 7} дн.`;
  if (!rows.length) {
    el.innerHTML = `<p class="hint">Пока нет тренда по часам.</p>`;
    return;
  }
  const vals = rows.map((r) => Number(r.active_sec || r.total_sec || 0));
  const max = Math.max(...vals, 1);
  const w = 320;
  const h = 140;
  const padX = 12;
  const padY = 16;
  const pts = vals.map((v, i) => {
    const x = padX + (i * (w - padX * 2)) / Math.max(vals.length - 1, 1);
    const y = h - padY - (v / max) * (h - padY * 2);
    return [x, y];
  });
  const poly = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const dots = pts
    .map(([x, y], i) => {
      const label = new Date(`${rows[i].day}T12:00:00`).toLocaleDateString("ru-RU", {
        weekday: "narrow",
      });
      return `<g>
        <circle cx="${x}" cy="${y}" r="4" class="hours-dot"/>
        <text x="${x}" y="${h - 2}" text-anchor="middle" class="hours-axis">${label}</text>
      </g>`;
    })
    .join("");
  const maxH = Math.round(max / 3600);
  el.innerHTML = `<svg class="hours-line-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="Часы за неделю">
    <text x="${w - 4}" y="14" text-anchor="end" class="hours-axis">${maxH}ч</text>
    <polyline class="hours-line-path" fill="none" points="${poly}"/>
    ${dots}
  </svg>`;
}

function renderProdDaysChart(trends) {
  const el = document.getElementById("prodDaysChart");
  if (!el) return;
  const rows = trends || [];
  const rangeEl = document.getElementById("prodDaysRange");
  const foot = document.getElementById("prodDaysFoot");
  if (rows.length && rangeEl) {
    rangeEl.textContent = `${rows.length} дн.`;
  }
  if (rows.length && foot) {
    const a = new Date(`${rows[0].day}T12:00:00`);
    const b = new Date(`${rows[rows.length - 1].day}T12:00:00`);
    const fmt = (d) =>
      d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
    foot.textContent = `${fmt(a)} — ${fmt(b)}`;
  }
  el.innerHTML = rows
    .map((r) => {
      const total = r.total_sec || 0;
      const cats = r.by_category || {};
      const d = new Date(`${r.day}T12:00:00`);
      const isWeekend = d.getDay() === 0 || d.getDay() === 6;
      const label = d.toLocaleDateString("ru-RU", { weekday: "short" });
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
      return `<div class="prod-day-col${isWeekend ? " is-weekend" : ""}" title="${r.day}: фокус ${r.focus_pct}%">
        <div class="prod-day-stack">${total ? segs : `<span class="stack-seg empty" style="height:6%"></span>`}</div>
        <span class="hours-label">${label}</span>
        <span class="hours-val">${Math.round(r.focus_pct || 0)}%</span>
      </div>`;
    })
    .join("");
}

async function refreshTrends() {
  const q = `?days=7${filterProjectId ? `&project_id=${encodeURIComponent(filterProjectId)}` : ""}${employeeQuerySuffix()}`;
  const trends = await api(`/api/trends${q}`);
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
    el.innerHTML = `<p class="hint">Пока нет сессий для этого дня.</p>`;
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
  // Prefer a workday window; snap to whole hours so labels never go negative.
  minMs = Math.min(minMs, dayStart.getTime() + 8 * 3600 * 1000);
  maxMs = Math.max(maxMs, dayStart.getTime() + 19 * 3600 * 1000);
  const snapMin = new Date(minMs);
  snapMin.setMinutes(0, 0, 0);
  minMs = Math.max(dayStart.getTime(), snapMin.getTime());
  const snapMax = new Date(maxMs);
  if (
    snapMax.getMinutes() ||
    snapMax.getSeconds() ||
    snapMax.getMilliseconds()
  ) {
    snapMax.setHours(snapMax.getHours() + 1, 0, 0, 0);
  } else {
    snapMax.setMinutes(0, 0, 0);
  }
  maxMs = Math.min(dayEnd.getTime(), snapMax.getTime());
  if (maxMs <= minMs) maxMs = minMs + 3600 * 1000;
  const span = maxMs - minMs;
  const hourCount = Math.max(1, Math.round(span / 3600000));

  const hours = [];
  for (let t = minMs; t <= maxMs + 1; t += 3600 * 1000) {
    if (t > maxMs + 500) break;
    const left = ((t - minMs) / span) * 100;
    if (left < -0.1 || left > 100.1) continue;
    const label = new Date(t).toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
    });
    const edge =
      left < 2 ? " is-start" : left > 98 ? " is-end" : "";
    hours.push(
      `<span class="gantt-hour${edge}" style="left:${Math.min(100, Math.max(0, left))}%">${label}</span>`
    );
  }

  const blocks = parsed
    .map((r) => {
      const left = ((r.startMs - minMs) / span) * 100;
      const width = Math.max(0.4, ((r.endMs - r.startMs) / span) * 100);
      const cat = categoryClass(r.category);
      const title = `${r.name || ""} · ${fmtClock(r.started_at)}–${fmtClock(r.ended_at)} · ${fmtDur(r.sec)}`;
      const showLabel = width >= 4.5;
      const labelHtml = showLabel
        ? `<span>${escapeHtml(r.name || "")}</span>`
        : "";
      return `<div class="gantt-block ${cat}${showLabel ? "" : " is-narrow"}" style="left:${left}%;width:${width}%" title="${escapeHtml(title)}">${labelHtml}</div>`;
    })
    .join("");

  el.innerHTML = `
    <div class="gantt-scale">${hours.join("")}</div>
    <div class="gantt-track" style="--gantt-hours:${hourCount}">${blocks}</div>
    <div class="gantt-legend">
      <span class="stack-leg"><i class="productive"></i>Фокус</span>
      <span class="stack-leg"><i class="neutral"></i>Нейтрально</span>
      <span class="stack-leg"><i class="distracting"></i>Отвлечение</span>
    </div>`;
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

function iconImgHtml(url) {
  if (!url) return `<span class="rank-icon" aria-hidden="true">•</span>`;
  return `<span class="rank-icon"><img class="rank-icon-img" src="${escapeHtml(url)}" alt="" width="36" height="36" decoding="async" onerror="${ICON_ONERROR}" /></span>`;
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
}

async function refreshSummary() {
  const q = summaryQuery();
  const { from, to } = periodBounds("today");
  const teamQ = `from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}${filterProjectId ? `&project_id=${encodeURIComponent(filterProjectId)}` : ""}`;
  const [summary, team, timelineRows] = await Promise.all([
    api(`/api/summary/today${q}`),
    api(`/api/company/team?${teamQ}`).catch(() => []),
    api(`/api/timeline/today${q}`).catch(() => []),
  ]);
  const key = summaryKey(summary) + `|p:${filterProjectId}|e:${filterEmployeeId}`;
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
  renderQuietPeople(team);
  renderKpis(summary, team);
  renderTopProjectsPulse(summary);
  renderTodayTimelineStrip(timelineRows, summary);
  renderPieChart(
    document.getElementById("catPie"),
    categoryPieSlices(summary.by_category || {}),
    summary.total_sec || 0,
    "Пока нет категорий за сегодня."
  );
  renderPieChart(
    document.getElementById("kindPie"),
    kindPieSlices(summary.by_kind || {}),
    summary.total_sec || 0,
    "Пока нет типов занятий."
  );
  renderProdStack(summary.by_category || {}, summary.total_sec || 0);
  renderBars(summary.by_category, summary.total_sec, { animate: false });
  renderKindBars(summary.by_kind || {}, summary.total_sec || 0);
  refreshTrends().catch(() => {});
  const activities = summary.by_activity || [];
  renderList(document.getElementById("topAppsToday"), activities, "Занятий пока нет");
}

async function refreshUsageReport() {
  const q = periodQuery(usagePeriod, filterProjectId, filterTaskId, filterEmployeeId);
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
  companyMode = !!cfg.company_mode;
  updateCompanyUiVisibility();
  await refreshCompanyPanel();
  updateStorageHint(cfg);
  const workToggle = document.getElementById("workModeToggle");
  if (workToggle) workToggle.checked = !!cfg.work_mode;
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

async function refreshTimeline() {
  ensureSelectedDay();
  renderDayWeekStrip();
  try {
    const { from, to } = dayQueryBounds(selectedDayIso);
    const emp = filterEmployeeId ? `&employee_id=${encodeURIComponent(filterEmployeeId)}` : "";
    const q = `day=${encodeURIComponent(selectedDayIso)}${emp}`;
    const [rowsRes, summaryRes] = await Promise.allSettled([
      api(`/api/timeline?${q}`),
      api(`/api/summary?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}${emp}`),
    ]);
    const rows = rowsRes.status === "fulfilled" ? rowsRes.value || [] : [];
    const summary = summaryRes.status === "fulfilled" ? summaryRes.value || {} : {};
    if (rowsRes.status !== "fulfilled") {
      console.error(rowsRes.reason);
      showToast("Не удалось загрузить ленту дня", "error");
    }

    renderDayGantt(rows);
    renderDayKpis(summary);
    const total = summary.total_sec || 0;
    renderPieChart(
      document.getElementById("dayCatPie"),
      categoryPieSlices(summary.by_category || {}),
      total,
      "Нет данных за этот день."
    );
    renderPieChart(
      document.getElementById("dayKindPie"),
      kindPieSlices(summary.by_kind || {}),
      total,
      "Нет типов занятий за этот день."
    );

    const el = document.getElementById("timelineList");
    if (!el) return;
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
  return refreshTimeline();
}

function shiftSelectedWeek(deltaDays) {
  ensureSelectedDay();
  const today = localDayIso();
  let next = shiftDayIso(selectedDayIso, deltaDays);
  if (next > today) next = today;
  selectedDayIso = next;
  return refreshTimeline();
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
    tab.setAttribute("role", "tab");
    tab.addEventListener("click", () => {
      setActiveTab(tab.dataset.tab);
      if (tab.dataset.tab === "shots") refreshShots();
      if (tab.dataset.tab === "settings") loadSettings();
      if (tab.dataset.tab === "day") {
        ensureSelectedDay();
        refreshTimeline().catch(() => {});
      }
      if (tab.dataset.tab === "ratings") refreshRatings();
      if (tab.dataset.tab === "projects") refreshProjects();
      if (tab.dataset.tab === "usage") refreshUsageReport();
    });
  });

  window.addEventListener("hashchange", () => {
    const name = (location.hash || "#today").replace(/^#/, "") || "today";
    const known = ["today", "day", "usage", "projects", "ratings", "shots", "settings"];
    if (!known.includes(name)) return;
    setActiveTab(name, { syncHash: false });
    if (name === "day") {
      ensureSelectedDay();
      refreshTimeline().catch(() => {});
    }
    if (name === "usage") refreshUsageReport().catch(() => {});
    if (name === "projects") refreshProjects().catch(() => {});
    if (name === "ratings") refreshRatings().catch(() => {});
    if (name === "shots") refreshShots().catch(() => {});
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
      await refreshSummary();
      await refreshUsageReport();
      await refreshTimeline();
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
  const splash = document.getElementById("appSplash");
  if (splash && !sessionStorage.getItem("deskline_splash_done")) {
    window.setTimeout(() => {
      splash.classList.add("is-done");
      sessionStorage.setItem("deskline_splash_done", "1");
    }, 1000);
  } else if (splash) {
    splash.classList.add("is-done");
  }
  wireUi();
  ensureSelectedDay();
  await refreshCompanyPanel().catch(() => {});
  const hashTab = (location.hash || "").replace(/^#/, "");
  const known = ["today", "day", "usage", "projects", "ratings", "shots", "settings"];
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
  }, 5000);
}

boot().catch((err) => {
  console.error(err);
  document.getElementById("focusSub").textContent = "Ошибка загрузки";
});
