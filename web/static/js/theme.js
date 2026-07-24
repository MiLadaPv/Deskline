/** Theme bootstrap — apply before paint to avoid flash. */
(function () {
  try {
    var stored = localStorage.getItem("deskline_theme") || "system";
    var resolved = stored;
    if (stored === "system") {
      resolved = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    document.documentElement.setAttribute("data-theme", resolved === "dark" ? "dark" : "light");
    document.documentElement.setAttribute("data-theme-pref", stored);
  } catch (e) {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
