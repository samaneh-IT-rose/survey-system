/* صفحه‌کلید مجازی فارسی — برای رایانه‌هایی که کیبورد فارسی ندارند
   با کلیک/لمس حروف، نویسه در محل نشانگرِ آخرین فیلد متنیِ فوکوس‌شده درج می‌شود.
   استفاده: دکمهٔ data-fakbd در صفحه + include این فایل. */
(function () {
  var ROWS = [
    ["۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹", "۰"],
    ["ض", "ص", "ث", "ق", "ف", "غ", "ع", "ه", "خ", "ح", "ج", "چ"],
    ["ش", "س", "ی", "ب", "ل", "ا", "ت", "ن", "م", "ک", "گ"],
    ["ظ", "ط", "ز", "ر", "ذ", "د", "پ", "و", "ژ", "."],
    ["،", ":", "؛", "!", "؟", "-", "/"]
  ];
  var lastFocused = null;
  var panel = null, btn = null;

  function isTarget(el) {
    if (!el || !el.tagName) return false;
    var t = el.tagName.toLowerCase();
    if (t === "textarea") return true;
    if (t === "input") {
      var ty = (el.getAttribute("type") || "text").toLowerCase();
      return ty === "text" || ty === "search";
    }
    return false;
  }

  document.addEventListener("focusin", function (ev) {
    if (isTarget(ev.target)) lastFocused = ev.target;
  });

  function currentTarget() {
    if (isTarget(document.activeElement)) return document.activeElement;
    return lastFocused;
  }

  function fireInput(el) {
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function insert(ch) {
    var el = currentTarget();
    if (!el) { if (window.S && S.toast) S.toast("اول داخل یکی از کادرهای فرم کلیک کنید.", "err"); return; }
    var s = (el.selectionStart == null) ? el.value.length : el.selectionStart;
    var e = (el.selectionEnd == null) ? el.value.length : el.selectionEnd;
    el.value = el.value.slice(0, s) + ch + el.value.slice(e);
    var pos = s + ch.length;
    if (el.setSelectionRange) el.setSelectionRange(pos, pos);
    el.focus({ preventScroll: true });
    fireInput(el);
  }

  function backspace() {
    var el = currentTarget();
    if (!el) return;
    var s = (el.selectionStart == null) ? el.value.length : el.selectionStart;
    var e = (el.selectionEnd == null) ? el.value.length : el.selectionEnd;
    if (s === e && s > 0) { s = s - 1; }
    el.value = el.value.slice(0, s) + el.value.slice(e);
    if (el.setSelectionRange) el.setSelectionRange(s, s);
    el.focus({ preventScroll: true });
    fireInput(el);
  }

  function makeKey(label, title, cls, onpick) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "fakbd-key" + (cls ? " " + cls : "");
    b.textContent = label;
    if (title) b.title = title;
    b.setAttribute("tabindex", "-1");
    b.addEventListener("pointerdown", function (ev) { ev.preventDefault(); }); // فوکوسِ فیلد حفظ می‌شود
    b.addEventListener("click", onpick);
    return b;
  }

  function build() {
    panel = document.createElement("div");
    panel.className = "fakbd";
    panel.dir = "rtl";
    panel.hidden = true;

    var head = document.createElement("div");
    head.className = "fakbd-head";
    var ttl = document.createElement("span");
    ttl.textContent = "صفحه‌کلید فارسی — حروف را با ماوس کلیک کنید";
    var close = makeKey("✕", "بستن", "fakbd-close", function () { setOpen(false); });
    head.appendChild(ttl);
    head.appendChild(close);
    panel.appendChild(head);

    var grid = document.createElement("div");
    grid.className = "fakbd-grid";
    ROWS.forEach(function (row) {
      var r = document.createElement("div");
      r.className = "fakbd-row";
      row.forEach(function (ch) { r.appendChild(makeKey(ch, "", "", function () { insert(ch); })); });
      grid.appendChild(r);
    });
    /* ردیف ویژه: بازگشت، نیم‌فاصله، فاصله */
    var r = document.createElement("div");
    r.className = "fakbd-row";
    r.appendChild(makeKey("⌫ بازگشت", "پاک‌کردن نویسهٔ قبل از نشانگر", "fakbd-wide", backspace));
    r.appendChild(makeKey("نیم‌فاصله", "نیم‌فاصله (‌)", "fakbd-wide", function () { insert("\u200C"); }));
    r.appendChild(makeKey("فاصله", "", "fakbd-space", function () { insert(" "); }));
    grid.appendChild(r);
    panel.appendChild(grid);
    document.body.appendChild(panel);
  }

  function setOpen(v) {
    if (!panel) return;
    panel.hidden = !v;
    if (btn) {
      btn.setAttribute("aria-pressed", v ? "true" : "false");
      btn.classList.toggle("fakbd-on", v);
    }
  }

  function init() {
    btn = document.querySelector("[data-fakbd]");
    if (!btn) return;
    build();
    btn.addEventListener("click", function () { setOpen(panel.hidden); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
