/* مدیریت نقش‌ها — فقط مدیر سامانه: ساخت/ویرایش/حذف نقش‌های کاربران */
(function () {
  var T = document.getElementById("rolesTable").querySelector("tbody");
  var modal = document.getElementById("roleModal");

  var PERM_LABELS = {
    view: "فقط خواندنی",
    edit: "ثبت و ویرایش",
    print: "چاپ و PDF",
    export: "خروجی اکسل",
    delete: "حذف رکورد",
    own_data: "فقط داده‌های خودش",
  };
  var LEVEL_LABELS = { admin: "مدیر سامانه", user: "کاربر سامانه" };

  function permChips(perms) {
    if (!perms || !perms.length) return "<span class='muted'>فقط خواندنی</span>";
    return perms.map(function (p) {
      return "<span class='permchip perm-" + p + "'>" + (PERM_LABELS[p] || p) + "</span>";
    }).join(" ");
  }

  function row(r) {
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + r.id + "</td>" +
      "<td>" + r.name + "</td>" +
      "<td dir='ltr' class='muted'>" + r.key + "</td>" +
      "<td><span class='levelbadge level-" + r.level + "'>" + (LEVEL_LABELS[r.level] || r.level) + "</span></td>" +
      "<td class='permcell'>" + permChips(r.permissions) + "</td>" +
      "<td>" + r.users_count + "</td>" +
      "<td>" + (r.is_system ? "<span class='badge ok'>سیستمی</span>" : "<span class='badge'>سفارشی</span>") + "</td>" +
      "<td class='actions'></td>";
    var act = tr.querySelector(".actions");

    var bEdit = document.createElement("button");
    bEdit.className = "btn sm";
    bEdit.textContent = "ویرایش";
    bEdit.onclick = function () { openModal(r); };
    act.appendChild(bEdit);

    if (!r.is_system) {
      var bDel = document.createElement("button");
      bDel.className = "btn sm danger";
      bDel.textContent = "حذف";
      bDel.onclick = function () {
        if (!window.confirm("نقش «" + r.name + "\" حذف شود؟")) return;
        S.fetchJSON(S.api("/roles/" + r.id), { method: "DELETE" })
          .then(function () { S.toast("نقش حذف شد."); load(); })
          .catch(function (e) { S.toast(e.message, "error"); });
      };
      act.appendChild(bDel);
    }
    return tr;
  }

  function load() {
    S.fetchJSON(S.api("/roles")).then(function (rows) {
      T.innerHTML = "";
      rows.forEach(function (r) { T.appendChild(row(r)); });
    }).catch(function (e) { S.toast(e.message, "error"); });
  }

  function checkedPerms() {
    var out = [];
    document.querySelectorAll("#r_perms input[type=checkbox]").forEach(function (cb) {
      if (cb.checked) out.push(cb.value);
    });
    return out;
  }

  function setCheckedPerms(perms) {
    document.querySelectorAll("#r_perms input[type=checkbox]").forEach(function (cb) {
      cb.checked = (perms || []).indexOf(cb.value) !== -1;
    });
  }

  function openModal(r) {
    var isEdit = !!r;
    document.getElementById("roleModalTitle").textContent = isEdit ? "ویرایش نقش" : "نقش جدید";
    document.getElementById("r_id").value = isEdit ? r.id : "";
    document.getElementById("r_name").value = isEdit ? r.name : "";
    document.getElementById("r_desc").value = isEdit ? (r.description || "") : "";
    document.getElementById("r_level").value = isEdit ? r.level : "user";
    if (isEdit && r.permissions && r.permissions.length) {
      setCheckedPerms(r.permissions);
    } else {
      setCheckedPerms(["view"]);
    }
    modal.hidden = false;
  }

  document.getElementById("btnNewRole").onclick = function () { openModal(null); };
  document.getElementById("roleCancel").onclick = function () { modal.hidden = true; };

  document.getElementById("roleForm").onsubmit = function (ev) {
    ev.preventDefault();
    var id = document.getElementById("r_id").value;
    var body = {
      name: document.getElementById("r_name").value.trim(),
      description: document.getElementById("r_desc").value.trim(),
      level: document.getElementById("r_level").value,
      permissions: checkedPerms(),
    };
    var p;
    if (id) {
      p = S.fetchJSON(S.api("/roles/" + id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } else {
      p = S.fetchJSON(S.api("/roles"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    }
    p.then(function () {
      S.toast("ذخیره شد.");
      modal.hidden = true;
      load();
    }).catch(function (e) { S.toast(e.message, "error"); });
  };

  load();
})();
