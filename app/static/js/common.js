/* ابزارهای مشترک: توست، تبدیل ارقام، ناوبری فعال */
(function () {
  window.S = window.S || {};

  // تبدیل ارقام فارسی/عربی به انگلیسی (برای کد ملی، تلفن و تاریخ)
  S.toEnDigits = function (s) {
    if (typeof s !== "string") return "";
    return s.replace(/[۰-۹٠-٩]/g, function (d) {
      return "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩".indexOf(d) % 10 + "";
    });
  };

  S.faNum = function (n, pad) {
    var s = String(n);
    if (pad) s = s.padStart(pad, "0");
    return s.replace(/[0-9]/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[+d]; });
  };

  S.toast = function (msg, kind) {
    var area = document.getElementById("toastArea");
    if (!area) return;
    var el = document.createElement("div");
    el.className = "toast " + (kind || "");
    el.textContent = msg;
    area.appendChild(el);
    setTimeout(function () { el.remove(); }, 4200);
  };

  S.fetchJSON = async function (url, options) {
    var res = await fetch(url, options);
    var data = null;
    try { data = await res.json(); } catch (e) { /* پاسخ غیر JSON */ }
    if (!res.ok) {
      var message = (data && data.detail && data.detail.message) || "خطا در ارتباط با سرور";
      var errors = (data && data.detail && data.detail.errors) || null;
      var err = new Error(message);
      err.errors = errors;
      err.status = res.status;
      throw err;
    }
    return data;
  };

  S.api = function (path) {
    return (window.__PREFIX__ || "/app") + "/api" + path;
  };

  S.confirmAction = function (msg) {
    return window.confirm(msg);
  };

  // هایلایت لینک فعال ناوبری
  document.addEventListener("DOMContentLoaded", function () {
    var page = document.body.getAttribute("data-page") || "";
    document.querySelectorAll(".mainnav a").forEach(function (a) {
      if (a.getAttribute("data-nav") === page) a.classList.add("active");
    });
  });
})();
