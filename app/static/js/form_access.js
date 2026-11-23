/* سطح دسترسی فرم‌ها — قواعد دو لایهٔ «سطح استان» و «ادارهٔ استان» (نسخهٔ 1.9.0) */
(function () {
  var T = document.getElementById("faTable").querySelector("tbody");
  var saveBtn = document.getElementById("faSave");
  var stateEl = document.getElementById("faState");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function row(r, idx) {
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + idx + "</td>" +
      "<td>" + esc(r.title) + "</td>" +
      "<td><label class='tickline'><input type='checkbox' data-key='" + esc(r.form_key) + "' data-field='visible_to_province'" + (r.visible_to_province ? " checked" : "") + "><span>سطح استان می‌بیند</span></label></td>" +
      "<td><label class='tickline'><input type='checkbox' data-key='" + esc(r.form_key) + "' data-field='visible_to_department'" + (r.visible_to_department ? " checked" : "") + "><span>ادارهٔ استان می‌بیند</span></label></td>" +
      "<td>" + (r.enabled ? "<span class='badge ok'>فعال</span>" : "<span class='badge off'>غیرفعال در رجیستری</span>") + "</td>";
    return tr;
  }

  function load() {
    S.fetchJSON(S.api("/form-access")).then(function (res) {
      T.innerHTML = "";
      (res.rules || []).forEach(function (r, i) { T.appendChild(row(r, i + 1)); });
    }).catch(function (e) { S.toast(e.message, "error"); });
  }

  saveBtn.onclick = function () {
    var seen = {};
    var rules = [];
    T.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
      var key = cb.getAttribute("data-key");
      var field = cb.getAttribute("data-field");
      if (!seen[key]) { seen[key] = { form_key: key, visible_to_province: true, visible_to_department: true }; rules.push(seen[key]); }
      seen[key][field] = cb.checked;
    });
    saveBtn.disabled = true;
    stateEl.textContent = "در حال ذخیره…";
    S.fetchJSON(S.api("/form-access"), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rules: rules }),
    }).then(function (res) {
      saveBtn.disabled = false;
      stateEl.textContent = "";
      S.toast(res.message || "قواعد ذخیره شد.", "ok");
    }).catch(function (e) {
      saveBtn.disabled = false;
      stateEl.textContent = "";
      S.toast(e.message, "error");
    });
  };

  load();
})();
