/* تم و پالت رنگی — ذخیره در localStorage (بخش ۱۲ سند) */
(function () {
  var PALETTES = ["pink", "blue", "green", "purple"];

  function safeGet(k) {
    try { return localStorage.getItem(k); } catch (e) { return null; }
  }
  function safeSet(k, v) {
    try { localStorage.setItem(k, v); } catch (e) { /* بدون ذخیره هم کار می‌کند */ }
  }

  function apply(mode, palette) {
    var root = document.documentElement;
    if (PALETTES.indexOf(palette) === -1) palette = "pink";
    root.setAttribute("data-mode", mode === "dark" ? "dark" : "light");
    root.setAttribute("data-palette", palette);
    document.querySelectorAll("#paletteSwatches .swatch").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-palette") === palette);
    });
    var btn = document.getElementById("modeToggle");
    if (btn) btn.textContent = mode === "dark" ? "☾ حالت شب" : "☀ حالت روز";
  }

  var savedMode = safeGet("survey.theme.mode");
  var savedPalette = safeGet("survey.theme.palette");
  if (window.matchMedia && !savedMode && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    savedMode = "dark";
  }
  apply(savedMode || "light", savedPalette || "pink");

  document.addEventListener("DOMContentLoaded", function () {
    apply(savedMode || "light", savedPalette || "pink");

    var toggle = document.getElementById("modeToggle");
    if (toggle) {
      toggle.addEventListener("click", function () {
        var next = document.documentElement.getAttribute("data-mode") === "dark" ? "light" : "dark";
        safeSet("survey.theme.mode", next);
        apply(next, document.documentElement.getAttribute("data-palette"));
      });
    }
    document.querySelectorAll("#paletteSwatches .swatch").forEach(function (b) {
      b.addEventListener("click", function () {
        var p = b.getAttribute("data-palette");
        safeSet("survey.theme.palette", p);
        apply(document.documentElement.getAttribute("data-mode"), p);
      });
    });
  });
})();
