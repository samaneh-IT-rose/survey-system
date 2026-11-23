/* انتقادات و پیشنهادات — فهرست رکوردهای دارای متن انتقاد/پیشنهاد (نسخهٔ 1.9.0) */
(function () {
  var T = document.getElementById("critTable").querySelector("tbody");
  var countEl = document.getElementById("critCount");
  var pageInfo = document.getElementById("critPageInfo");
  var page = 1;
  var pages = 1;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // فیلتر فرم — فقط فرم‌های مجاز این کاربر (از سرور با قواعد لایه آمده)
  var formSel = document.getElementById("cform");
  (window.__CRIT_FORMS__ || []).forEach(function (f) {
    var o = document.createElement("option");
    o.value = f.key;
    o.textContent = f.short_title || f.title;
    formSel.appendChild(o);
  });

  // استان‌ها — کاربرِ دارای محدودیت استانی فقط استان خودش را می‌بیند
  S.fetchJSON(S.api("/provinces")).then(function (rows) {
    var sel = document.getElementById("cprovince");
    (rows || []).forEach(function (p) {
      var o = document.createElement("option");
      o.value = p.id;
      o.textContent = p.name;
      sel.appendChild(o);
    });
  }).catch(function () {});

  function qs() {
    var p = new URLSearchParams();
    p.set("page", page);
    var v;
    if ((v = document.getElementById("cq").value.trim())) p.set("q", v);
    if ((v = formSel.value)) p.set("form", v);
    if ((v = document.getElementById("cprovince").value)) p.set("province_id", v);
    if ((v = document.getElementById("cdate_from").value.trim())) p.set("date_from", v);
    if ((v = document.getElementById("cdate_to").value.trim())) p.set("date_to", v);
    return p.toString();
  }

  function faDate(iso) {
    if (!iso) return "—";
    return iso.replace("T", " ").slice(0, 16);
  }

  function row(r, idx) {
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + idx + "</td>" +
      "<td><span class='permchip'>" + esc(r.form_title) + "</span></td>" +
      "<td>" + esc(r.first_name + " " + r.last_name) + "</td>" +
      "<td dir='ltr'>" + esc(r.national_code) + "</td>" +
      "<td>" + esc(r.province) + "</td>" +
      "<td>" + esc(r.county) + "</td>" +
      "<td>" + esc(r.survey_date_jalali) + "</td>" +
      "<td class='crittext' style='max-width:420px;white-space:pre-wrap'>" + esc(r.criticism) + "</td>" +
      "<td dir='ltr'>" + esc(faDate(r.created_at)) + "</td>";
    return tr;
  }

  function load() {
    S.fetchJSON(S.api("/criticisms") + "?" + qs()).then(function (res) {
      T.innerHTML = "";
      (res.items || []).forEach(function (r, i) { T.appendChild(row(r, (res.page - 1) * res.per_page + i + 1)); });
      if (!(res.items || []).length) {
        var tr = document.createElement("tr");
        tr.innerHTML = "<td colspan='9' class='muted'>رکوردی با انتقادات و پیشنهادات در محدودهٔ دسترسی شما پیدا نشد.</td>";
        T.appendChild(tr);
      }
      countEl.textContent = "مجموع: " + res.total + " رکورد دارای انتقادات و پیشنهادات";
      pageInfo.textContent = "صفحهٔ " + res.page + " از " + res.pages;
      pages = res.pages;
      page = res.page;
    }).catch(function (e) { S.toast(e.message, "error"); });
  }

  document.getElementById("critSearchBtn").onclick = function () { page = 1; load(); };
  document.getElementById("cq").addEventListener("keydown", function (ev) {
    if (ev.key === "Enter") { page = 1; load(); }
  });
  document.getElementById("critPrev").onclick = function () { if (page > 1) { page--; load(); } };
  document.getElementById("critNext").onclick = function () { if (page < pages) { page++; load(); } };
  document.getElementById("critExportBtn").onclick = function () {
    var url = S.api("/criticisms/export/excel") + "?" + qs().replace(/page=\d+&?/, "");
    window.location.href = url;
  };

  load();
})();
