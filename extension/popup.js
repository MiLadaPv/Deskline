function formatSec(sec) {
  const s = Math.max(0, Math.floor(sec || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function setUi(status) {
  const badge = document.getElementById("statusBadge");
  const toggle = document.getElementById("toggleBtn");
  const hostEl = document.getElementById("currentHost");
  const today = document.getElementById("todayTime");
  const hint = document.getElementById("desktopHint");
  const cta = document.getElementById("desktopCta");

  const recording = Boolean(status.recording);
  badge.textContent = recording ? "Recording" : "Paused";
  badge.classList.toggle("off", !recording);
  toggle.textContent = recording ? "Pause" : "Resume";
  today.textContent = formatSec(status.todaySec);

  if (status.current && status.current.host) {
    hostEl.textContent = status.current.host;
  } else {
    hostEl.textContent = "No active tab";
  }

  if (status.desktopOnline) {
    hint.textContent =
      "Desktop is running — browser segments sync to your local Deskline dashboard.";
    cta.textContent = "Open dashboard";
    cta.href = status.desktopUrl || "http://127.0.0.1:8787";
  } else {
    hint.textContent =
      "Browser-only mode. Install Deskline Desktop to track all apps, screenshots, and tray controls.";
    cta.textContent = "Get Desktop";
    cta.href = chrome.runtime.getURL("download.html");
  }
}

function refresh() {
  chrome.runtime.sendMessage({ type: "getStatus" }, (status) => {
    if (chrome.runtime.lastError || !status) return;
    setUi(status);
  });
}

document.getElementById("toggleBtn").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "getStatus" }, (status) => {
    const next = !(status && status.recording);
    chrome.runtime.sendMessage({ type: "setRecording", recording: next }, () => {
      refresh();
    });
  });
});

refresh();
setInterval(refresh, 2000);
