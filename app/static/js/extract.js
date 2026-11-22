/* استخراج داده از تمام فرم‌ها — انتخاب فرم، فیلتر و هر ستون دلخواه (نسخهٔ 1.7.0) */
(function () {
  var P = window.__PREFIX__ || "/app";
  var FORMS = window.__FORMS__ || [];
  var FORM_SHORT = {};
  FORMS.forEach(function (f) { FORM_SHORT[f.key] = f.short_title || f.key; });

  function checkedBoxes(containerId) {
    var out = [];
    document.querySelectorAll("#" + containerId + " input[type=checkbox]").forEach(function (cb) {
      if (cb.checked) out.push(cb.value);
    });
    return out;
  }

  // همهٔ گروه‌های سؤال (ex_q_<formkey>) — مستقل از تعداد فرم‌ها
  function questionContainers() {
    return Array.prototype.slice.call(document.querySelectorAll('[id^="ex_q_"]')).map(function (d) { return d.id; });
  }

  function setAll(ids, checked) {
    ids.forEach(function (id) {
      document.querySelectorAll("#" + id + " input[type=checkbox]").forEach(function (cb) {
        cb.checked = checked;
      });
    });
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>\"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // استان‌ها — مثل آرشیو
  fetch(P + "/api/provinces", { credentials: "same-origin" })
    .then(function (r) { return r.json(); })
    .then(function (rows) {
      var sel = document.getElementById("ex_province");
      rows.forEach(function (p) {
        var o = document.createElement("option");
        o.value = p.id;
        o.textContent = p.name;
        sel.appendChild(o);
      });
    })
    .catch(function () {});

  function params() {
    var qs = new URLSearchParams();
    checkedBoxes("ex_forms").forEach(function (v) { qs.append("forms", v); });
    checkedBoxes("ex_base").forEach(function (v) { qs.append("fields", v); });
    questionContainers().forEach(function (id) {
      checkedBoxes(id).forEach(function (v) { qs.append("fields", v); });
    });
    var q = document.getElementById("ex_q").value.trim();
    if (q) qs.set("q", q);
    var pv = document.getElementById("ex_province").value;
    if (pv) qs.set("province_id", pv);
    var from = document.getElementById("ex_from").value.trim();
    if (from) qs.set("date_from", from);
    var to = document.getElementById("ex_to").value.trim();
    if (to) qs.set("date_to", to);
    return qs;
  }

  function render(res) {
    var head = document.getElementById("exHeadRow");
    var body = document.getElementById("exBody");
    var cols = res.columns || [];
    head.innerHTML = cols.map(function (c) {
      var label = c.kind === "question" ? "[" + (FORM_SHORT[c.form_key] || c.form_key || "") + "] " + c.label : c.label;
      return "<th title=\"" + esc(c.label) + "\">" + esc(label) + "</th>";
    }).join("");
    var rows = res.rows || [];
    if (!rows.length) {
      body.innerHTML = "<tr><td colspan=\"" + Math.max(1, cols.length) + "\" class=\"muted\">رکوردی با این انتخاب‌ها پیدا نشد.</td></tr>";
    } else {
      body.innerHTML = rows.map(function (r) {
        return "<tr>" + r.map(function (v) { return "<td>" + esc(v) + "</td>"; }).join("") + "</tr>";
      }).join("");
    }
    document.getElementById("exTotalBadge").textContent = (res.total || 0) + " رکورد" + (res.truncated ? " (سقف نمایش)" : "");
  }

  document.getElementById("exRunBtn").onclick = function () {
    S.fetchJSON(P + "/api/extract?" + params().toString())
      .then(render)
      .catch(function (e) { S.toast(e.message, "error"); });
  };

  var excelBtn = document.getElementById("exExcelBtn");
  if (excelBtn) {
    excelBtn.onclick = function () {
      window.location.href = P + "/api/extract/excel?" + params().toString();
    };
  }

  var allIds = ["ex_base"].concat(questionContainers());
  document.getElementById("exAllBtn").onclick = function () { setAll(allIds, true); };
  document.getElementById("exNoneBtn").onclick = function () { setAll(allIds, false); };
})();
