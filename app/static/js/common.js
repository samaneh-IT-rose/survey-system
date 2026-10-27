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

  /* الگوریتم اعتبارسنجی کد ملی — نسخه اصلاح‌شده
     ایرادهای نسخه قدیمی که در این نسخه رفع شده است:
     1) «return true» انتهای تابع هرگز اجرا نمی‌شد (کد مرده)
     2) کدهایی با همه ارقام یکسان (مثل 1111111111) به‌اشتباه معتبر شمرده می‌شدند
     3) ورودی غیررقمی کنترل نمی‌شد (حروف وارد محاسبه می‌شد)
     4) برای ورودی بیشتر از ۱۰ رقم، substr طول اشتباه برمی‌گرداند
     5) ارقام فارسی/عربی پشتیبانی نمی‌شد
  */
  S.checkCodeMeli = function (input) {
    // ۱) یکسان‌سازی ارقام فارسی/عربی به انگلیسی و حذف فاصله‌های ابتدا و انتها
    var code = S.toEnDigits(String(input == null ? "" : input)).trim();
    // ۲) فقط رقم مجاز است؛ طول مجاز ۸ تا ۱۰ رقم (صفر ابتدایی ممکن است حذف شده باشد)
    if (!/^[0-9]{8,10}$/.test(code)) return false;
    // ۳) تکمیل صفرهای ابتدایی تا ۱۰ رقم (جایگزین مطمئن برای substr)
    while (code.length < 10) code = "0" + code;
    // ۴) همه ارقام یکسان (مثل 0000000000 و 1111111111) هرگز معتبر نیستند
    if (/^([0-9])\1{9}$/.test(code)) return false;
    // ۵) محاسبه رقم کنترل: وزن ۱۰ تا ۲ برای نه رقم اول
    var sum = 0;
    for (var i = 0; i < 9; i++) {
      sum += parseInt(code.charAt(i), 10) * (10 - i);
    }
    var remainder = sum % 11;
    var check = parseInt(code.charAt(9), 10);
    // ۶) باقیمانده کمتر از ۲: رقم کنترل باید همان باقیمانده باشد؛ وگرنه ۱۱ منهای باقیمانده
    return remainder < 2 ? check === remainder : check === 11 - remainder;
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
