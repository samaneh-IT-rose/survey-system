/* مدیریت کاربران — سطح کاربری، نقش‌ها، سطوح دسترسی، فرم‌های مجاز */
(function () {
  var T = document.getElementById("usersTable").querySelector("tbody");
  var modal = document.getElementById("userModal");

  var PERM_LABELS = {
    view: "فقط خواندنی",
    edit: "ثبت و ویرایش",
    print: "چاپ و PDF",
    export: "خروجی اکسل",
    delete: "حذف رکورد",
    own_data: "فقط داده‌های خودش",
  };
  var FORM_TITLES = {};
  document.querySelectorAll("#u_forms input[type=checkbox]").forEach(function (cb) {
    FORM_TITLES[cb.value] = cb.parentNode.textContent.trim();
  });

  // نقش‌ها و دسترسی‌های پیش‌فرض — از سرور (جدول roles، شامل نقش‌های سفارشی)
  var ROLES = window.__ROLES__ || [];
  var ROLE_DEFAULTS = {};
  var ROLE_IS_SYSTEM = {};
  ROLES.forEach(function (r) {
    ROLE_DEFAULTS[r.key] = r.permissions || ["view"];
    ROLE_IS_SYSTEM[r.key] = !!r.is_system;
  });
  function roleDefaults(role) {
    return ROLE_DEFAULTS[role] || ["view"];
  }

  function faDate(iso) {
    if (!iso) return "—";
    return iso.replace("T", " ").slice(0, 16);
  }

  // ---------- استان‌ها — کمبوباکس استان کاربر (نسخهٔ 1.8.0) ----------
  var PROVINCES = [];
  function fillProvinceSelect(selectedName) {
    var sel = document.getElementById("u_province");
    var first = sel.querySelector("option[value='']");
    sel.innerHTML = "";
    if (first) sel.appendChild(first);
    PROVINCES.forEach(function (p) {
      var opt = document.createElement("option");
      opt.value = p.name;
      opt.textContent = p.name;
      sel.appendChild(opt);
    });
    var name = selectedName || "";
    if (name && !PROVINCES.some(function (p) { return p.name === name; })) {
      // نام استان خارج از فهرست (مثل ورود دستی/اکسل قبلی) — حفظ می‌شود تا پاک نشود
      var opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name + " (خارج از فهرست)";
      sel.appendChild(opt);
    }
    sel.value = name;
  }
  S.fetchJSON(S.api("/provinces")).then(function (rows) {
    PROVINCES = rows || [];
    fillProvinceSelect("");
  }).catch(function () {});

  function permChips(perms) {
    if (!perms || !perms.length) return "<span class='muted'>پیش‌فرض نقش</span>";
    return perms.map(function (p) {
      return "<span class='permchip perm-" + p + "'>" + (PERM_LABELS[p] || p) + "</span>";
    }).join(" ");
  }

  function formsCell(u) {
    if (u.is_admin_level) return "<span class='muted'>همهٔ فرم‌ها (مدیر — محدودیت فرم اعمال نمی‌شود)</span>";
    if (!u.allowed_forms || !u.allowed_forms.length) return "<span class='muted'>همهٔ فرم‌ها</span>";
    return u.allowed_forms.map(function (k) {
      return "<span class='permchip'>" + (FORM_TITLES[k] || k) + "</span>";
    }).join(" ");
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function row(u) {
    var tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + u.id + "</td>" +
      "<td>" + esc(u.full_name) + "</td>" +
      "<td dir='ltr'>" + esc(u.national_id) + "</td>" +
      "<td>" + esc(u.province_name) + (u.province_name && !u.is_admin_level ? " <span class='permchip' title='این کاربر فقط رکوردهای استان خودش را می‌بیند'>فقط همین استان</span>" : "") + "</td>" +
      "<td dir='ltr'>" + esc(u.phone) + "</td>" +
      "<td>" + esc(u.position) + "</td>" +
      "<td dir='ltr'>" + esc(u.username) + "</td>" +
      "<td><span class='levelbadge level-" + u.level + "'>" + u.level_label + "</span></td>" +
      "<td><span class='rolebadge'>" + u.role_label + "</span></td>" +
      "<td class='permcell'>" + permChips(u.effective_permissions) + "<div class='muted' style='margin-top:4px;font-size:11px'>فرم‌ها: " + formsCell(u) + "</div></td>" +
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

  function checkedBoxes(containerId) {
    var out = [];
    document.querySelectorAll("#" + containerId + " input[type=checkbox]").forEach(function (cb) {
      if (cb.checked) out.push(cb.value);
    });
    return out;
  }

  function setCheckedBoxes(containerId, values) {
    document.querySelectorAll("#" + containerId + " input[type=checkbox]").forEach(function (cb) {
      cb.checked = (values || []).indexOf(cb.value) !== -1;
    });
  }

  function checkedPerms() { return checkedBoxes("u_perms"); }
  function setCheckedPerms(perms) { setCheckedBoxes("u_perms", perms); }
  function checkedForms() { return checkedBoxes("u_forms"); }
  function setCheckedForms(forms) { setCheckedBoxes("u_forms", forms); }

  function applyLevelUi() {
    var level = document.getElementById("u_level").value;
    var role = document.getElementById("u_role").value;
    // نقش «مدیر» هم هرچقدر سطح کاربر باشد، به‌صورت خودکار همهٔ دسترسی‌ها و همهٔ فرم‌ها را دارد —
    // همین بی‌صدا بودن، علت گمراه‌شدن مدیر در تعیین «فرم‌های مجاز» بود؛ حالا در UI هم شفاف است
    var isEffectivelyAdmin = level === "admin" || role === "admin";
    document.querySelectorAll("#u_perms input[type=checkbox]").forEach(function (cb) {
      cb.disabled = isEffectivelyAdmin;
    });
    document.querySelectorAll("#u_forms input[type=checkbox]").forEach(function (cb) {
      cb.disabled = isEffectivelyAdmin;
      if (isEffectivelyAdmin) cb.checked = true; // مدیر همهٔ فرم‌ها را می‌بیند
    });
    document.getElementById("u_level_hint").textContent = isEffectivelyAdmin
      ? (level === "admin"
        ? "مدیر سامانه به همهٔ بخش‌ها و همهٔ فرم‌ها دسترسی دارد و محدودیت فرم برایش اعمال نمی‌شود."
        : "نقش «مدیر» همهٔ دسترسی‌ها و همهٔ فرم‌ها را می‌دهد؛ برای محدودکردن فرم‌ها نقش دیگری انتخاب کنید.")
      : "کاربر سامانه فقط بر اساس نقش، دسترسی‌ها و فرم‌های مجاز وارد می‌شود.";
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
    document.getElementById("u_national_id").value = isEdit ? (u.national_id || "") : "";
    fillProvinceSelect(isEdit ? (u.province_name || "") : "");
    document.getElementById("u_phone").value = isEdit ? (u.phone || "") : "";
    document.getElementById("u_position").value = isEdit ? (u.position || "") : "";
    document.getElementById("u_notes").value = isEdit ? (u.notes || "") : "";
    document.getElementById("u_level").value = isEdit ? u.level : "user";
    document.getElementById("u_role").value = isEdit ? u.role : "operator";
    if (isEdit && u.permissions && u.permissions.length) {
      setCheckedPerms(u.permissions);
    } else {
      setCheckedPerms(roleDefaults(isEdit ? u.role : "operator"));
    }
    // فرم‌های مجاز — خالی یعنی همه
    setCheckedForms(isEdit ? (u.allowed_forms || []) : []);
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
      setCheckedPerms(roleDefaults(role));
    }
    applyLevelUi();
  });

  document.getElementById("u_role").addEventListener("change", function () {
    if (document.getElementById("u_level").value === "admin") return;
    setCheckedPerms(roleDefaults(this.value));
  });

  document.getElementById("userForm").onsubmit = function (ev) {
    ev.preventDefault();
    var id = document.getElementById("u_id").value;
    var body = {
      full_name: document.getElementById("u_fullname").value.trim(),
      national_id: document.getElementById("u_national_id").value.trim(),
      province_name: document.getElementById("u_province").value.trim(),
      phone: document.getElementById("u_phone").value.trim(),
      position: document.getElementById("u_position").value.trim(),
      notes: document.getElementById("u_notes").value.trim(),
      role: document.getElementById("u_role").value,
      level: document.getElementById("u_level").value,
      permissions: checkedPerms(),
      allowed_forms: checkedForms(),
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

  // ---------- ورود گروهی از اکسل ----------
  var importModal = document.getElementById("importModal");
  var impForm = document.getElementById("importForm");
  var impResult = document.getElementById("importResult");
  var impResultBody = document.getElementById("importResultBody");
  var impSubmit = document.getElementById("importSubmit");

  document.getElementById("btnImportUsers").onclick = function () {
    impResult.hidden = true;
    impResultBody.innerHTML = "";
    impForm.reset();
    document.getElementById("imp_fixed_row").hidden = true;
    importModal.hidden = false;
  };
  document.getElementById("importCancel").onclick = function () {
    importModal.hidden = true;
    load();
  };

  document.getElementById("imp_pwmode").addEventListener("change", function () {
    document.getElementById("imp_fixed_row").hidden = (this.value !== "fixed");
  });

  impForm.onsubmit = function (ev) {
    ev.preventDefault();
    var fileInput = document.getElementById("imp_file");
    if (!fileInput.files || !fileInput.files.length) {
      S.toast("فایل اکسل را انتخاب کنید.", "error");
      return;
    }
    var fd = new FormData();
    fd.append("file", fileInput.files[0]);
    fd.append("level", document.getElementById("imp_level").value);
    fd.append("role", document.getElementById("imp_role").value);
    fd.append("password_mode", document.getElementById("imp_pwmode").value);
    fd.append("fixed_password", document.getElementById("imp_fixed").value);
    fd.append("allowed_forms", checkedBoxes("imp_forms").join(","));
    impSubmit.disabled = true;
    S.fetchJSON(S.api("/users/import-excel"), {
      method: "POST",
      body: fd,
    }).then(function (res) {
      impSubmit.disabled = false;
      impResult.hidden = false;
      var lines = [];
      lines.push("<div><b>" + (res.created || []).length + "</b> کاربر ساخته شد، <b>" + (res.skipped || []).length + "</b> ردیف رد شد.</div>");
      if ((res.created || []).length) {
        lines.push("<div style='margin-top:6px'><b>ساخته‌شده‌ها:</b><ul style='margin:4px 0;padding-right:18px'>");
        res.created.forEach(function (c) {
          lines.push("<li>" + esc(c.full_name) + " — کد ملی <span dir='ltr'>" + esc(c.username) + "</span>" + (c.position ? " — " + esc(c.position) : "") + (c.province ? " — " + esc(c.province) : "") + "</li>");
        });
        lines.push("</ul></div>");
      }
      if ((res.skipped || []).length) {
        lines.push("<div style='margin-top:6px;color:#b45309'><b>ردشده‌ها:</b><ul style='margin:4px 0;padding-right:18px'>");
        res.skipped.forEach(function (s) {
          lines.push("<li>شیت «" + esc(s.sheet) + "» ردیف " + esc(s.row) + (s.full_name ? " — " + esc(s.full_name) : "") + ": " + esc(s.reason) + "</li>");
        });
        lines.push("</ul></div>");
      }
      impResultBody.innerHTML = lines.join("");
      S.toast(res.message || "ورود گروهی انجام شد.", "ok");
    }).catch(function (e) {
      impSubmit.disabled = false;
      S.toast(e.message, "error");
    });
  };

  load();
})();
