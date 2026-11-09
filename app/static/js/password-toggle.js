/* دکمهٔ چشمی نمایش/پنهان‌کردن رمز عبور — برای همهٔ .eyebtn های صفحه فعال می‌شود */
(function () {
  function applyState(btn, input, show) {
    input.type = show ? "text" : "password";
    var eye = btn.querySelector(".ic-eye");
    var off = btn.querySelector(".ic-eyeoff");
    if (eye) eye.hidden = show;
    if (off) off.hidden = !show;
    var label = show ? "پنهان‌کردن رمز" : "نمایش رمز";
    btn.setAttribute("aria-pressed", show ? "true" : "false");
    btn.setAttribute("aria-label", label);
    btn.title = label;
  }

  function bind(btn) {
    var wrap = btn.closest(".passwrap");
    if (!wrap || btn.getAttribute("data-bound")) return;
    var input = wrap.querySelector('input[type="password"], input[type="text"]');
    if (!input) return;
    btn.setAttribute("data-bound", "1");
    btn.addEventListener("click", function () {
      applyState(btn, input, input.type === "password");
      input.focus({ preventScroll: true });
    });
  }

  function init() {
    document.querySelectorAll(".eyebtn").forEach(bind);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
