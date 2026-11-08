/* مدیریت کاربران — فقط مدیر سامانه: سطح کاربری، نقش و سطوح دسترسی */
(function () {
  var T = document.getElementById("usersTable").querySelector("tbody");
  var modal = document.getElementById("userModal");

  var PERM_LABELS = {
    view: "فقط خواندنی",
    edit: "ثبت و ویرایش",
    print: "چاپ و PDF",
    export: "خروجی اکسل",
    delete: "حذف رکورد",
  };
  // دسترسی‌های پیش‌فرض هر نقش — هماهنگ با سرور
  var ROLE_DEFAULTS = {
    admin: ["view", "edit", "print", "export", "delete"],
    operator: ["view", "edit", "print", "export"],
    data_entry: ["view", "edit", "print"],
    supervisor: ["view", "edit", "print"],
    reporter: ["view", "print", "export"],
    viewer: ["view"],
  };

  function faDate(iso) {
    if (!iso) return "—";
    return iso.replace("T", " ").slice(0, 16);
  }

  function permChips(perms) {
    if (!perms || !perms.length) return "<span class='muted'>پیش‌فرض نقش</span>";
    return perms.map(function (p) {
      return "<span class='permchip perm-" + p + "'>" + (PERM_LABELS[p] || p) + "</span>";
    }).join(" ");
  }

  function row(u) {
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + u.id + "</td>" +
      "<td>" + u.full_name + "</td>" +
      "<td dir='ltr'>" + u.username + "</td>" +
      "<td><span class='levelbadge level-" + u.level + "'>" + u.level_label + "</span></td>" +
      "<td><span class='rolebadge role-" + u.role + "'>" + u.role_label + "</span></td>" +
      "<td class='permcell'>" + permChips(u.effective_permissions) + "</td>" +
      "<td>" + (u.is_active ? "<span class='badge ok'>فعال</span>" : "<span class='badge off'>غیرفعال</span>") + "</td>" +
      "<td>" + faDate(u.last_login_at) + "</td>" +
      "<td class='actions'></td>";
    var act = tr.querySelector(".actions");

    var bEdit = document.createElement("button");
    bEdit.className = "btn sm";
    bEdit.textContent = "ویرایش";
    bEdit.onclick = function () { openModal(u); };
    act.appendChild(bEdit);

    var bPass = document.createElement("button");
    bPass.className = "btn sm";
    bPass.textContent = "بازنشانی رمز";
    bPass.onclick = function () {
      var p = prompt("رمز عبور جدید برای «" + u.username + "\" (حداقل ۶ نویسه):");
      if (p === null) return;
      if (p.length < 6) { S.toast("رمز باید حداقل ۶ نویسه باشد.", "error"); return; }
      S.fetchJSON(S.api("/users/" + u.id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: p }),
      }).then(function () {
        S.toast("رمز بازنشانی شد. کاربر در ورود بعدی باید رمز جدید بگذارد.");
        load();
      }).catch(function (e) { S.toast(e.message, "error"); });
    };
    act.appendChild(bPass);

    var bToggle = document.createElement("button");
    bToggle.className = "btn sm " + (u.is_active ? "danger" : "primary");
    bToggle.textContent = u.is_active ? "غیرفعال" : "فعال";
    bToggle.onclick = function () {
      S.fetchJSON(S.api("/users/" + u.id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !u.is_active }),
      }).then(function () { load(); })
        .catch(function (e) { S.toast(e.message, "error"); });
    };
    act.appendChild(bToggle);
    return tr;
  }

  function load() {
    S.fetchJSON(S.api("/users")).then(function (rows) {
      T.innerHTML = "";
      rows.forEach(function (u) { T.appendChild(row(u)); });
    }).catch(function (e) { S.toast(e.message, "error"); });
  }

  function checkedPerms() {
    var out = [];
    document.querySelectorAll("#u_perms input[type=checkbox]").forEach(function (cb) {
      if (cb.checked) out.push(cb.value);
    });
    return out;
  }

  function setCheckedPerms(perms) {
    document.querySelectorAll("#u_perms input[type=checkbox]").forEach(function (cb) {
      cb.checked = perms.indexOf(cb.value) !== -1;
    });
  }

  function applyLevelUi() {
    var isAdmin = document.getElementById("u_level").value === "admin";
    document.querySelectorAll("#u_perms input[type=checkbox]").forEach(function (cb) {
      cb.disabled = isAdmin;
    });
    document.getElementById("u_level_hint").textContent = isAdmin
      ? "مدیر سامانه به همهٔ بخش‌ها از جمله مدیریت کاربران دسترسی دارد."
      : "کاربر سامانه فقط بر اساس نقش و سطوح دسترسی وارد می‌شود.";
  }

  function openModal(u) {
    var isEdit = !!u;
    document.getElementById("userModalTitle").textContent = isEdit ? "ویرایش کاربر" : "کاربر جدید";
    document.getElementById("u_id").value = isEdit ? u.id : "";
    var un = document.getElementById("u_username");
    un.value = isEdit ? u.username : "";
    un.disabled = isEdit; // نام کاربری پس از ساخت تغییر نمی‌کند
    document.getElementById("u_username_hint").style.display = isEdit ? "none" : "inline";
    document.getElementById("u_fullname").value = isEdit ? u.full_name : "";
    document.getElementById("u_level").value = isEdit ? u.level : "user";
    document.getElementById("u_role").value = isEdit ? u.role : "operator";
    if (isEdit && u.permissions && u.permissions.length) {
      setCheckedPerms(u.permissions);
    } else {
      setCheckedPerms(ROLE_DEFAULTS[isEdit ? u.role : "operator"] || ["view"]);
    }
    var pw = document.getElementById("u_password");
    if (isEdit) {
      pw.value = "";
      pw.required = false;
      document.getElementById("u_password_label").textContent = "رمز جدید (اگر می‌خواهی عوض شود — اختیاری)";
    } else {
      pw.value = "";
      pw.required = true;
      document.getElementById("u_password_label").textContent = "رمز عبور اولیه (حداقل ۶ نویسه) — کاربر در اولین ورود مجبور به تغییر می‌شود";
    }
    applyLevelUi();
    modal.hidden = false;
  }

  document.getElementById("btnNewUser").onclick = function () { openModal(null); };
  document.getElementById("userCancel").onclick = function () { modal.hidden = true; };

  document.getElementById("u_level").addEventListener("change", function () {
    // سطح مدیر: همهٔ تیک‌ها روشن (ولی غیرقابل تغییر)
    if (this.value === "admin") {
      setCheckedPerms(Object.keys(PERM_LABELS));
    } else {
      var role = document.getElementById("u_role").value;
      setCheckedPerms(ROLE_DEFAULTS[role] || ["view"]);
    }
    applyLevelUi();
  });

  document.getElementById("u_role").addEventListener("change", function () {
    if (document.getElementById("u_level").value === "admin") return;
    setCheckedPerms(ROLE_DEFAULTS[this.value] || ["view"]);
  });

  document.getElementById("userForm").onsubmit = function (ev) {
    ev.preventDefault();
    var id = document.getElementById("u_id").value;
    var body = {
      full_name: document.getElementById("u_fullname").value.trim(),
      role: document.getElementById("u_role").value,
      level: document.getElementById("u_level").value,
      permissions: checkedPerms(),
    };
    var pw = document.getElementById("u_password").value;
    var p;
    if (id) {
      if (pw) body.password = pw;
      p = S.fetchJSON(S.api("/users/" + id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } else {
      body.username = document.getElementById("u_username").value.trim();
      body.password = pw;
      p = S.fetchJSON(S.api("/users"), {
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
