/**
 * Deskline Chrome MV3 service worker.
 * Tracks active tab locally; optionally forwards closed segments to Desktop :8787.
 */

const DESKTOP_BASE = "http://127.0.0.1:8787";
const ALARM_TICK = "deskline-tick";
const MIN_SEGMENT_SEC = 3;

const defaultState = () => ({
  recording: true,
  current: null, // { tabId, url, title, host, startedAt }
  todaySec: 0,
  dayKey: dayKey(),
  desktopOnline: false,
});

function dayKey(d = new Date()) {
  return d.toISOString().slice(0, 10);
}

function hostOf(url) {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return "";
  }
}

function isTrackable(url) {
  if (!url) return false;
  return (
    url.startsWith("http://") ||
    url.startsWith("https://") ||
    url.startsWith("file://")
  );
}

async function loadState() {
  const { deskline } = await chrome.storage.local.get("deskline");
  const state = { ...defaultState(), ...(deskline || {}) };
  const today = dayKey();
  if (state.dayKey !== today) {
    state.dayKey = today;
    state.todaySec = 0;
  }
  return state;
}

async function saveState(state) {
  await chrome.storage.local.set({ deskline: state });
}

async function probeDesktop() {
  try {
    const res = await fetch(`${DESKTOP_BASE}/api/extension/status`, {
      method: "GET",
      cache: "no-store",
    });
    if (!res.ok) return false;
    const data = await res.json();
    return Boolean(data && data.ok && data.desktop);
  } catch {
    return false;
  }
}

async function forwardEvent(segment) {
  try {
    const res = await fetch(`${DESKTOP_BASE}/api/extension/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(segment),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function closeCurrent(state, endedAt = Date.now()) {
  const cur = state.current;
  if (!cur || !cur.startedAt) {
    state.current = null;
    return state;
  }
  const durationSec = Math.max(0, (endedAt - cur.startedAt) / 1000);
  state.current = null;
  if (durationSec < MIN_SEGMENT_SEC) {
    return state;
  }
  state.todaySec = (state.todaySec || 0) + durationSec;

  const payload = {
    url: cur.url || "",
    title: cur.title || "",
    host: cur.host || hostOf(cur.url),
    started_at: new Date(cur.startedAt).toISOString(),
    ended_at: new Date(endedAt).toISOString(),
    duration_sec: durationSec,
  };

  if (state.desktopOnline) {
    await forwardEvent(payload);
  }

  const { segments = [] } = await chrome.storage.local.get("segments");
  segments.push(payload);
  // Keep last ~200 local segments for popup / debug
  await chrome.storage.local.set({ segments: segments.slice(-200) });
  return state;
}

async function switchToTab(tab) {
  let state = await loadState();
  state.desktopOnline = await probeDesktop();
  if (!state.recording) {
    state.current = null;
    await saveState(state);
    return;
  }
  state = await closeCurrent(state);
  if (tab && isTrackable(tab.url)) {
    state.current = {
      tabId: tab.id,
      url: tab.url,
      title: tab.title || "",
      host: hostOf(tab.url),
      startedAt: Date.now(),
    };
  } else {
    state.current = null;
  }
  await saveState(state);
}

async function refreshActive() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  await switchToTab(tab || null);
}

chrome.runtime.onInstalled.addListener(async () => {
  const state = await loadState();
  await saveState(state);
  chrome.alarms.create(ALARM_TICK, { periodInMinutes: 1 });
  await refreshActive();
});

chrome.runtime.onStartup.addListener(async () => {
  chrome.alarms.create(ALARM_TICK, { periodInMinutes: 1 });
  await refreshActive();
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== ALARM_TICK) return;
  let state = await loadState();
  state.desktopOnline = await probeDesktop();
  if (state.recording && state.current) {
    // Soft flush every minute so Desktop gets data even if Chrome stays on one tab.
    const now = Date.now();
    const elapsed = (now - state.current.startedAt) / 1000;
    if (elapsed >= 60) {
      const snap = { ...state.current };
      state = await closeCurrent(state, now);
      state.current = {
        ...snap,
        startedAt: now,
      };
    }
  }
  await saveState(state);
});

chrome.tabs.onActivated.addListener(async () => {
  await refreshActive();
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" || changeInfo.url || changeInfo.title) {
    const [active] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (active && active.id === tabId) {
      await switchToTab(tab);
    }
  }
});

chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) {
    let state = await loadState();
    state = await closeCurrent(state);
    await saveState(state);
    return;
  }
  await refreshActive();
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    if (msg?.type === "getStatus") {
      const state = await loadState();
      state.desktopOnline = await probeDesktop();
      await saveState(state);
      sendResponse({
        recording: state.recording,
        todaySec: state.todaySec,
        current: state.current,
        desktopOnline: state.desktopOnline,
        desktopUrl: DESKTOP_BASE,
      });
      return;
    }
    if (msg?.type === "setRecording") {
      let state = await loadState();
      state.recording = Boolean(msg.recording);
      if (!state.recording) {
        state = await closeCurrent(state);
      } else {
        await saveState(state);
        await refreshActive();
        return sendResponse({ ok: true });
      }
      await saveState(state);
      sendResponse({ ok: true, recording: state.recording });
      return;
    }
    sendResponse({ ok: false });
  })();
  return true;
});
