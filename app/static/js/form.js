/* منطق فرم نظرسنجی: استان/شهرستان وابسته، تاریخ جلالی، اعتبارسنجی، ذخیره و ویرایش */
(function () {
  var boot = window.__BOOT__ || {};
  var API = window.S.api;
  var $ = function (id) { return document.getElementById(id); };

  var MONTH_LENS = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];
  var MONTH_NAMES = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];
  var recordId = boot.recordId ? parseInt(boot.recordId, 10) : null;
  var dirty = false;

  /* ---------- تاریخ جلالی ---------- */
  function isLeap(jy) { return (boot.leapYears || []).indexOf(jy) !== -1; }
  function monthLen(jy, jm) { return jm <= 6 ? 31 : (jm <= 11 ? 30 : (isLeap(jy) ? 30 : 29)); }

  function fillYearSelect() {
    var sel = $("jy");
    (boot.years || []).slice().sort(function (a, b) { return b - a; }).forEach(function (y) {
      var o = document.createElement("option");
      o.value = y; o.textContent = window.S.faNum(y);
      sel.appendChild(o);
    });
  }
  function fillMonthSelect() {
    var sel = $("jm");
    MONTH_NAMES.forEach(function (name, i) {
      var o = document.createElement("option");
      o.value = i + 1; o.textContent = name;
      sel.appendChild(o);
    });
  }
  function fillDaySelect() {
    var jy = +$("jy").value, jm = +$("jm").value, jd = +$("jd").value;
    var sel = $("jd");
    sel.innerHTML = "";
    var len = monthLen(jy, jm);
    for (var d = 1; d <= len; d++) {
      var o = document.createElement("option");
      o.value = d; o.textContent = window.S.faNum(d, 2);
      sel.appendChild(o);
    }
    if (jd && jd <= len) sel.value = jd;
  }
  function getDateStr() {
    var jy = $("jy").value, jm = $("jm").value, jd = $("jd").value;
    if (!jy || !jm || !jd) return "";
    return jy + "/" + String(jm).padStart(2, "0") + "/" + String(jd).padStart(2, "0");
  }
  function setDateStr(str) {
    if (!str) return;
    var parts = window.S.toEnDigits(str).trim().split("/");
    if (parts.length !== 3) return;
    $("jy").value = parts[0];
    $("jm").value = String(parseInt(parts[1], 10));
    fillDaySelect();
    $("jd").value = String(parseInt(parts[2], 10));
  }

  /* ---------- استان و شهرستان ---------- */
  async function loadProvinces(selectedId) {
    var provinces = await window.S.fetchJSON(API("/provinces"));
    var sel = $("province_id");
    provinces.forEach(function (p) {
      var o = document.createElement("option");
      o.value = p.id; o.textContent = p.name;
      sel.appendChild(o);
    });
    if (selectedId) sel.value = selectedId;
  }

  async function loadCounties(provinceId, selectedId) {
    var sel = $("county_id");
    sel.innerHTML = "";
    var ph = document.createElement("option");
    ph.value = "";
    ph.textContent = provinceId ? "انتخاب شهرستان…" : "ابتدا استان را انتخاب کنید…";
    sel.appendChild(ph);
    if (!provinceId) { sel.disabled = true; return; }
    sel.disabled = false;
    var counties = await window.S.fetchJSON(API("/counties?province_id=" + provinceId));
    counties.forEach(function (c) {
      var o = document.createElement("option");
      o.value = c.id; o.textContent = c.name;
      sel.appendChild(o);
    });
    if (selectedId) sel.value = selectedId;
  }

  /* ---------- وضعیت تماس و قفل جدول ---------- */
  function contactRequiresAnswers() {
    var checked = document.querySelector('input[name="contact_option_id"]:checked');
    return checked ? checked.getAttribute("data-requires") === "1" : null; // null = هنوز انتخاب نشده
  }

  function refreshRatingLock() {
    var req = contactRequiresAnswers();
    var table = $("qtableWrap");
    if (req === false) {
      table.classList.add("disabled");
      $("ratingNote").textContent =
        "برای این وضعیت تماس، تکمیل جدول نظرسنجی لازم نیست و گزینه‌ها غیرفعال شده‌اند.";
    } else {
      table.classList.remove("disabled");
      $("ratingNote").textContent =
        "برای هر سؤال فقط یک گزینه قابل انتخاب است." +
        (req === true ? " تکمیل همه سؤال‌ها برای این وضعیت تماس الزامی است." : "");
    }
  }

  /* ---------- خطاها کنار فیلد ---------- */
  function clearErrors() {
    document.querySelectorAll(".field.invalid").forEach(function (f) { f.classList.remove("invalid"); });
    document.querySelectorAll(".field .err").forEach(function (e) { e.textContent = ""; });
  }
  function showErrors(errors) {
    clearErrors();
    Object.keys(errors || {}).forEach(function (key) {
      var box = $("f-" + key);
      if (!box) return;
      box.classList.add("invalid");
      var err = box.querySelector(".err");
      if (err) err.textContent = errors[key];
    });
  }
  function setFieldError(key, msg) { showErrors({}); showErrors((function () { var e = {}; e[key] = msg; return e; })()); }

  /* ---------- اعتبارسنجی سمت مرورگر (بازخورد سریع؛ کنترل اصلی سمت سرور است) ---------- */
  function validateClient() {
    var errors = {};
    var fn = $("first_name").value.trim();
    var ln = $("last_name").value.trim();
    if (fn.length < 2) errors.first_name = "نام را وارد کنید (حداقل ۲ نویسه).";
    if (ln.length < 2) errors.last_name = "نام خانوادگی را وارد کنید (حداقل ۲ نویسه).";
    var code = window.S.toEnDigits($("national_code").value).trim();
    if (!/^[0-9]{8,10}$/.test(code)) errors.national_code = "کد ملی باید ۸ تا ۱۰ رقم باشد.";
    var phone = window.S.toEnDigits($("phone").value).trim();
    if (!/^09[0-9]{9}$/.test(phone)) errors.phone = "شماره تماس باید ۱۱ رقم و با ۰۹ شروع شود.";
    if (!$("province_id").value) errors.province_id = "استان را انتخاب کنید.";
    if (!$("county_id").value) errors.county_id = "شهرستان را انتخاب کنید.";
    if (!getDateStr()) errors.survey_date = "تاریخ را انتخاب کنید.";
    var contact = document.querySelector('input[name="contact_option_id"]:checked');
    if (!contact) errors.contact_option_id = "وضعیت تماس را انتخاب کنید.";
    if (contact && contact.getAttribute("data-requires") === "1") {
      var qids = (boot.questions || []).map(function (q) { return q.id; });
      for (var i = 0; i < qids.length; i++) {
        if (!document.querySelector('input[name="q' + qids[i] + '"]:checked')) {
          errors.answers = "برای همه سؤال‌های جدول یک گزینه انتخاب کنید (وضعیت تماس انتخابی الزامی است).";
          break;
        }
      }
    }
    return errors;
  }

  /* ---------- جمع‌آوری و ارسال ---------- */
  function collect() {
    var answers = [];
    (boot.questions || []).forEach(function (q) {
      var sel = document.querySelector('input[name="q' + q.id + '"]:checked');
      if (sel) answers.push({ question_id: q.id, value: sel.value });
    });
    return {
      first_name: $("first_name").value,
      last_name: $("last_name").value,
      national_code: window.S.toEnDigits($("national_code").value).trim(),
      phone: window.S.toEnDigits($("phone").value).trim(),
      province_id: $("province_id").value || null,
      county_id: $("county_id").value || null,
      survey_date: getDateStr(),
      contact_option_id: (document.querySelector('input[name="contact_option_id"]:checked') || {}).value || null,
      answers: answers
    };
  }

  function fillForm(rec) {
    $("first_name").value = rec.first_name;
    $("last_name").value = rec.last_name;
    $("national_code").value = rec.national_code;
    $("phone").value = rec.phone;
    loadProvinces(rec.province.id).then(function () {
      return loadCounties(rec.province.id, rec.county.id);
    });
    setDateStr(rec.survey_date_jalali);
    if (rec.contact_option) {
      var r = document.querySelector('input[name="contact_option_id"][value="' + rec.contact_option.id + '"]');
      if (r) r.checked = true;
    }
    (rec.answers || []).forEach(function (a) {
      var r = document.querySelector('input[name="q' + a.question_id + '"][value="' + a.value + '"]');
      if (r) r.checked = true;
    });
    refreshRatingLock();
  }

  async function loadRecord(id) {
    try {
      var rec = await window.S.fetchJSON(API("/surveys/" + id));
      fillForm(rec);
      recordId = rec.id;
      $("formTitle").textContent = "ویرایش فرم نظرسنجی — رکورد " + window.S.faNum(rec.id);
      $("editBadge").innerHTML = "در حال ویرایش رکورد شماره <bdi>" + rec.id + "</bdi>؛ پس از ذخیره، تغییرات جایگزین می‌شود.";
    } catch (e) {
      window.S.toast(e.message, "err");
    }
  }

  function resetForm() {
    $("surveyForm").reset();
    $("county_id").innerHTML = '<option value="">ابتدا استان را انتخاب کنید…</option>';
    $("county_id").disabled = true;
    clearErrors();
    refreshRatingLock();
    recordId = null;
    dirty = false;
    $("formTitle").textContent = "ثبت فرم نظرسنجی";
    $("editBadge").textContent = "";
    var t = boot.todayJalali || "";
    if (t) setDateStr(t);
    window.history.replaceState(null, "", window.location.pathname);
  }

  $("surveyForm").addEventListener("submit", async function (ev) {
    ev.preventDefault();
    clearErrors();
    var errs = validateClient();
    if (Object.keys(errs).length) {
      showErrors(errs);
      window.S.toast("لطفاً خطاهای مشخص‌شده را اصلاح کنید.", "err");
      return;
    }
    var btn = $("saveBtn");
    btn.disabled = true;               // جلوگیری از ارسال تکراری
    $("saveState").textContent = "در حال ذخیره…";
    var payload = collect();
    try {
      var res = recordId
        ? await window.S.fetchJSON(API("/surveys/" + recordId), {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          })
        : await window.S.fetchJSON(API("/surveys"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });
      dirty = false;
      window.S.toast(res.message + " (شناسه رکورد: " + res.id + ")", "ok");
      $("saveState").textContent = "";
      if (!recordId) {
        // پس از ذخیرهٔ جدید، به حالت ویرایش همان رکورد می‌رویم تا شناسه دیده شود
        window.history.replaceState(null, "", "?id=" + res.id);
        recordId = res.id;
        $("formTitle").textContent = "ویرایش فرم نظرسنجی — رکورد " + window.S.faNum(res.id);
        $("editBadge").innerHTML = "رکورد جدید با شناسه <bdi>" + res.id + "</bdi> ذخیره شد؛ می‌توانید ویرایش یا چاپ کنید:";
      }
    } catch (e) {
      // در خطای شبکه یا دیتابیس، اطلاعات فرم باقی می‌ماند و امکان تلاش مجدد هست
      showErrors(e.errors || {});
      window.S.toast(e.message, "err");
      $("saveState").textContent = "";
    } finally {
      btn.disabled = false;
    }
  });

  $("clearBtn").addEventListener("click", function () {
    if (dirty && !window.S.confirmAction("تغییرات ذخیره‌نشده وجود دارد؛ اطلاعات فرم جاری پاک شود؟")) return;
    resetForm();
    window.S.toast("فرم برای ثبت جدید آماده شد (هیچ رکوردی حذف نشد).", "ok");
  });

  window.addEventListener("beforeunload", function (ev) {
    if (dirty) { ev.preventDefault(); ev.returnValue = ""; }
  });

  /* ---------- شروع ---------- */
  document.addEventListener("DOMContentLoaded", async function () {
    fillYearSelect();
    fillMonthSelect();
    fillDaySelect();
    var t = boot.todayJalali || "";
    if (t) setDateStr(t);

    await loadProvinces();

    $("province_id").addEventListener("change", function () {
      loadCounties(this.value || null);
      // با تغییر استان، شهرستان قبلیِ نامرتبط پاک می‌شود
    });
    ["jy", "jm"].forEach(function (id) {
      $(id).addEventListener("change", fillDaySelect);
    });
    $("todayBtn").addEventListener("click", function () { setDateStr(boot.todayJalali); });

    document.querySelectorAll('input[name="contact_option_id"]').forEach(function (r) {
      r.addEventListener("change", refreshRatingLock);
    });
    $("surveyForm").addEventListener("input", function () { dirty = true; });
    $("surveyForm").addEventListener("change", function () { dirty = true; });

    refreshRatingLock();
    if (recordId) await loadRecord(recordId);
  });
})();
