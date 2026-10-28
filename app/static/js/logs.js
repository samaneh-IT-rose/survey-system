/* لاگ فعالیت‌ها — فقط مدیر */
(function () {
  var T = document.getElementById("logsTable").querySelector("tbody");
  var pager = document.getElementById("logsPager");
  var page = 1;

  function load() {
    var action = document.getElementById("f_action").value;
    var username = document.getElementById("f_username").value.trim();
    var url = S.api("/logs?page=" + page + "&per_page=50");
    if (action) url += "&action=" + encodeURIComponent(action);
    if (username) url += "&username=" + encodeURIComponent(username);
    S.fetchJSON(url).then(function (d) {
      T.innerHTML = "";
      d.items.forEach(function (r) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td class='nowrap'>" + r.created_at + "</td>" +
          "<td dir='ltr'>" + r.username + "</td>" +
          "<td><span class='badge'>" + r.action_label + "</span></td>" +
          "<td>" + (r.detail || "—") + "</td>" +
          "<td dir='ltr'>" + (r.ip || "—") + "</td>";
        T.appendChild(tr);
      });
      if (!d.items.length) {
        T.innerHTML = "<tr><td colspan='5' class='empty'>رویدادی ثبت نشده است.</td></tr>";
      }
      pager.innerHTML = "";
      for (var i = 1; i <= d.pages; i++) {
        (function (i) {
          var b = document.createElement("button");
          b.className = "btn sm" + (i === d.page ? " primary" : "");
          b.textContent = S.faNum(i);
          b.onclick = function () { page = i; load(); };
          pager.appendChild(b);
        })(i);
      }
    }).catch(function (e) { S.toast(e.message, "error"); });
  }

  document.getElementById("f_apply").onclick = function () { page = 1; load(); };
  load();
})();
