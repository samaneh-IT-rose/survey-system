/* آرشیو رکوردها: فهرست، فیلتر، صفحه‌بندی، حذف و خروجی اکسل */
(function () {
  var API = window.S.api;
  var $ = function (id) { return document.getElementById(id); };
  var state = { page: 1, perPage: 10 };
  var contactsCache = [];

  function qs() {
    var p = new URLSearchParams();
    if ($("fq").value.trim()) p.set("q", $("fq").value.trim());
    if ($("fprovince").value) p.set("province_id", $("fprovince").value);
    if ($("fcounty").value) p.set("county_id", $("fcounty").value);
    if ($("fcontact").value) p.set("contact_option_id", $("fcontact").value);
    var from = window.S.toEnDigits($("ffrom").value.trim());
    var to = window.S.toEnDigits($("fto").value.trim());
    if (from) p.set("date_from", from);
    if (to) p.set("date_to", to);
    p.set("page", state.page);
    p.set("per_page", state.perPage);
    return p.toString();
  }

  function opButtons(r) {
    var prefix = window.__PREFIX__;
    return '' +
      '<a class="btn sm" title="ویرایش" href="' + prefix + '/?id=' + r.id + '">✏ ویرایش</a>' +
      '<a class="btn sm" title="چاپ" target="_blank" href="' + prefix + '/print/' + r.id + '">🖨 چاپ</a>' +
      '<a class="btn sm" title="PDF" href="' + API('/surveys/' + r.id + '/pdf') + '">📄 PDF</a>' +
      '<button class="btn sm danger" title="حذف" data-del="' + r.id + '">🗑 حذف</button>';
  }

  function render(data) {
    $("totalBadge").textContent = window.S.faNum(data.total) + " رکورد";
    var body = $("rowsBody");
    if (!data.items.length) {
      body.innerHTML = '<tr><td colspan="8" class="muted">رکوردی یافت نشد.</td></tr>';
    } else {
      body.innerHTML = data.items.map(function (r) {
        return '<tr>' +
          '<td><bdi>#' + r.id + '</bdi></td>' +
          '<td>' + r.first_name + ' ' + r.last_name + '</td>' +
          '<td><bdi>' + r.national_code + '</bdi></td>' +
          '<td><bdi>' + r.phone + '</bdi></td>' +
          '<td>' + r.province.name + ' / ' + r.county.name + '</td>' +
          '<td><bdi>' + window.S.faNum(r.survey_date_jalali.replace(/\//g, "/")) + '</bdi></td>' +
          '<td>' + (r.contact_option ? '<span class="badge">' + r.contact_option.text + '</span>' : '—') + '</td>' +
          '<td><div class="ops">' + opButtons(r) + '</div></td>' +
          '</tr>';
      }).join("");
    }
    $("pageInfo").textContent = "صفحه " + window.S.faNum(data.page) + " از " + window.S.faNum(data.pages);

    var btns = $("pageBtns");
    btns.innerHTML = "";
    function pageBtn(label, page, opts) {
      var b = document.createElement("button");
      b.textContent = label;
      if (opts && opts.cur) b.className = "cur";
      if (opts && opts.disabled) b.disabled = true;
      b.addEventListener("click", function () { state.page = page; load(); });
      btns.appendChild(b);
    }
    var start = Math.max(1, data.page - 2), end = Math.min(data.pages, data.page + 2);
    pageBtn("«", Math.max(1, data.page - 1), { disabled: data.page <= 1 });
    for (var i = start; i <= end; i++) pageBtn(window.S.faNum(i), i, { cur: i === data.page });
    pageBtn("»", Math.min(data.pages, data.page + 1), { disabled: data.page >= data.pages });
  }

  async function load() {
    $("rowsBody").innerHTML = '<tr><td colspan="8" class="muted">در حال بارگذاری…</td></tr>';
    try {
      var data = await window.S.fetchJSON(API("/surveys?" + qs()));
      render(data);
    } catch (e) {
      $("rowsBody").innerHTML = '<tr><td colspan="8" class="muted">' + e.message + '</td></tr>';
    }
  }

  async function loadFilters() {
    var provinces = await window.S.fetchJSON(API("/provinces"));
    provinces.forEach(function (p) {
      var o = document.createElement("option");
      o.value = p.id; o.textContent = p.name;
      $("fprovince").appendChild(o);
    });
    contactsCache = await window.S.fetchJSON(API("/template/contact-options"));
    contactsCache.forEach(function (c) {
      var o = document.createElement("option");
      o.value = c.id; o.textContent = c.text;
      $("fcontact").appendChild(o);
    });
  }

  $("fprovince").addEventListener("change", function () {
    var sel = $("fcounty");
    sel.innerHTML = '<option value="">همه</option>';
    sel.disabled = !this.value;
    if (!this.value) return;
    window.S.fetchJSON(API("/counties?province_id=" + this.value)).then(function (rows) {
      rows.forEach(function (c) {
        var o = document.createElement("option");
        o.value = c.id; o.textContent = c.name;
        sel.appendChild(o);
      });
    });
  });

  $("applyBtn").addEventListener("click", function () { state.page = 1; load(); });
  $("resetBtn").addEventListener("click", function () {
    ["fq", "ffrom", "fto"].forEach(function (id) { $(id).value = ""; });
    $("fprovince").value = ""; $("fcounty").value = ""; $("fcontact").value = "";
    $("fcounty").disabled = true;
    state.page = 1; load();
  });
  $("excelBtn").addEventListener("click", function () {
    var p = new URLSearchParams(qs());
    p.delete("page"); p.delete("per_page");
    window.location.href = API("/surveys/export/excel?" + p.toString());
  });

  document.addEventListener("click", async function (ev) {
    var del = ev.target.closest("[data-del]");
    if (del) {
      var id = del.getAttribute("data-del");
      if (!window.S.confirmAction("رکورد شماره " + id + " برای همیشه حذف شود؟ این عمل بازگشت‌پذیر نیست.")) return;
      try {
        await window.S.fetchJSON(API("/surveys/" + id), { method: "DELETE" });
        window.S.toast("رکورد حذف شد.", "ok");
        load();
      } catch (e) {
        window.S.toast(e.message, "err");
      }
    }
  });

  document.addEventListener("DOMContentLoaded", async function () {
    await loadFilters();
    load();
  });
})();
