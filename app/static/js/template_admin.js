/* مدیریت الگوی فرم: سؤال‌ها و وضعیت‌های تماس */
(function () {
  var API = window.S.api;
  var $ = function (id) { return document.getElementById(id); };

  function miniBtns(kind, item) {
    return '<div class="mini">' +
      '<button class="iconbtn" data-up="' + kind + ':' + item.id + '" title="بالا">↑</button>' +
      '<button class="iconbtn" data-down="' + kind + ':' + item.id + '" title="پایین">↓</button>' +
      '<button class="iconbtn" data-edit="' + kind + ':' + item.id + '" title="ویرایش متن">✏</button>' +
      '<button class="iconbtn" data-toggle="' + kind + ':' + item.id + '" title="' +
      (item.is_active ? "غیرفعال‌سازی" : "فعال‌سازی") + '">' + (item.is_active ? "◉" : "○") + '</button>' +
      '</div>';
  }

  function renderQuestions(rows) {
    var box = $("qList");
    if (!rows.length) { box.innerHTML = '<span class="muted">سؤالی ثبت نشده است.</span>'; return; }
    box.innerHTML = rows.map(function (q) {
      return '<div class="tmrow' + (q.is_active ? "" : " inactive") + '" data-kind="q" data-id="' + q.id + '">' +
        '<span class="txt">' + q.text + '</span>' +
        miniBtns("q", q) +
        '</div>';
    }).join("");
  }

  function renderContacts(rows) {
    var box = $("cList");
    if (!rows.length) { box.innerHTML = '<span class="muted">وضعیتی ثبت نشده است.</span>'; return; }
    box.innerHTML = rows.map(function (c) {
      return '<div class="tmrow' + (c.is_active ? "" : " inactive") + '" data-kind="c" data-id="' + c.id + '">' +
        '<span class="txt">' + c.text +
        '<br><span class="muted" style="font-size:11.5px">' +
        (c.requires_answers ? "نیازمند تکمیل جدول نظرسنجی" : "بدون نیاز به تکمیل جدول") +
        '</span></span>' +
        '<label class="switchline"><input type="checkbox" data-requires="' + c.id + '"' +
        (c.requires_answers ? " checked" : "") + '> نیازمند تکمیل جدول</label>' +
        miniBtns("c", c) +
        '</div>';
    }).join("");
  }

  async function reload() {
    var qs = await window.S.fetchJSON(API("/template/questions"));
    var cs = await window.S.fetchJSON(API("/template/contact-options"));
    renderQuestions(qs);
    renderContacts(cs);
  }

  function parseToken(token) {
    var parts = token.split(":");
    return { kind: parts[0], id: parseInt(parts[1], 10) };
  }

  async function move(token, direction) {
    var t = parseToken(token);
    var path = t.kind === "q" ? "/template/questions/" + t.id + "/move" : "/template/contact-options/" + t.id + "/move";
    await window.S.fetchJSON(API(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction: direction })
    });
    reload();
  }

  async function editText(token) {
    var t = parseToken(token);
    var row = document.querySelector('.tmrow[data-kind="' + (t.kind === "q" ? "q" : "c") + '"][data-id="' + t.id + '"] .txt');
    if (!row) return;
    var current = row.childNodes[0].textContent.trim();
    var val = window.prompt("متن جدید را وارد کنید (پاسخ‌های قبلی از متن مستقل می‌مانند):", current);
    if (val === null) return;
    val = val.trim();
    if (val.length < 2) { window.S.toast("متن باید حداقل ۲ نویسه باشد.", "err"); return; }
    var path = t.kind === "q" ? "/template/questions/" + t.id : "/template/contact-options/" + t.id;
    await window.S.fetchJSON(API(path), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: val })
    });
    window.S.toast("متن به‌روزرسانی شد.", "ok");
    reload();
  }

  async function toggleActive(token) {
    var t = parseToken(token);
    var rowEl = document.querySelector('.tmrow[data-kind="' + (t.kind === "q" ? "q" : "c") + '"][data-id="' + t.id + '"]');
    var nowInactive = rowEl && rowEl.classList.contains("inactive");
    var path = t.kind === "q" ? "/template/questions/" + t.id : "/template/contact-options/" + t.id;
    await window.S.fetchJSON(API(path), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !!nowInactive })
    });
    reload();
  }

  async function setRequires(id, value) {
    await window.S.fetchJSON(API("/template/contact-options/" + id), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ requires_answers: value })
    });
    window.S.toast("تنظیم الزام تکمیل جدول به‌روزرسانی شد.", "ok");
    reload();
  }

  document.addEventListener("click", async function (ev) {
    var el;
    if ((el = ev.target.closest("[data-up]"))) return move(el.getAttribute("data-up"), "up");
    if ((el = ev.target.closest("[data-down]"))) return move(el.getAttribute("data-down"), "down");
    if ((el = ev.target.closest("[data-edit]"))) return editText(el.getAttribute("data-edit"));
    if ((el = ev.target.closest("[data-toggle]"))) return toggleActive(el.getAttribute("data-toggle"));
  });

  document.addEventListener("change", function (ev) {
    var el;
    if ((el = ev.target.closest("[data-requires]"))) return setRequires(el.getAttribute("data-requires"), el.checked);
  });

  document.addEventListener("DOMContentLoaded", function () {
    $("addQBtn").addEventListener("click", async function () {
      var text = $("newQ").value.trim();
      if (text.length < 2) { window.S.toast("متن سؤال را وارد کنید.", "err"); return; }
      await window.S.fetchJSON(API("/template/questions"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
      });
      $("newQ").value = "";
      window.S.toast("سؤال جدید افزوده شد.", "ok");
      reload();
    });
    $("addCBtn").addEventListener("click", async function () {
      var text = $("newC").value.trim();
      if (text.length < 2) { window.S.toast("متن وضعیت تماس را وارد کنید.", "err"); return; }
      await window.S.fetchJSON(API("/template/contact-options"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, requires_answers: $("newCRequires").checked })
      });
      $("newC").value = "";
      window.S.toast("وضعیت تماس جدید افزوده شد.", "ok");
      reload();
    });
    reload();
  });
})();
