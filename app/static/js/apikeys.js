/* کلیدهای وب‌سرویس — فقط مدیر */
(function () {
  var T = document.getElementById("keysTable").querySelector("tbody");
  var banner = document.getElementById("keyBanner");

  function faDate(iso) {
    if (!iso) return "—";
    return iso.replace("T", " ").slice(0, 16);
  }

  function row(k) {
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + k.id + "</td>" +
      "<td>" + k.name + "</td>" +
      "<td dir='ltr'><code>" + k.key_prefix + "…</code></td>" +
      "<td>" + (k.is_active ? "<span class='badge ok'>فعال</span>" : "<span class='badge off'>غیرفعال</span>") + "</td>" +
      "<td>" + faDate(k.last_used_at) + "</td>" +
      "<td class='actions'></td>";
    var act = tr.querySelector(".actions");
    var b = document.createElement("button");
    b.className = "btn sm " + (k.is_active ? "danger" : "primary");
    b.textContent = k.is_active ? "لغو" : "فعال‌سازی";
    b.onclick = function () {
      if (k.is_active && !S.confirmAction("کلید «" + k.name + "\" لغو شود؟ سیستم متصل دیگر نمی‌تواند وب‌سرویس را صدا بزند.")) return;
      S.fetchJSON(S.api("/keys/" + k.id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !k.is_active }),
      }).then(load).catch(function (e) { S.toast(e.message, "error"); });
    };
    act.appendChild(b);
    return tr;
  }

  function load() {
    S.fetchJSON(S.api("/keys")).then(function (rows) {
      T.innerHTML = "";
      rows.forEach(function (k) { T.appendChild(row(k)); });
      if (!rows.length) T.innerHTML = "<tr><td colspan='6' class='empty'>هنوز کلیدی ساخته نشده است.</td></tr>";
    }).catch(function (e) { S.toast(e.message, "error"); });
  }

  document.getElementById("btnNewKey").onclick = function () {
    var name = prompt("نام سیستم متصل (مثلاً: نرم‌افزار مرکزی مشاوره):");
    if (!name || name.trim().length < 2) return;
    S.fetchJSON(S.api("/keys"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim() }),
    }).then(function (d) {
      banner.hidden = false;
      document.getElementById("newKeyValue").textContent = d.key;
      load();
    }).catch(function (e) { S.toast(e.message, "error"); });
  };

  document.getElementById("copyKeyBtn").onclick = function () {
    var txt = document.getElementById("newKeyValue").textContent;
    navigator.clipboard.writeText(txt).then(function () { S.toast("کلید کپی شد."); });
  };

  load();
})();
