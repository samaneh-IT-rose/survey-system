/* داشبورد آماری با ECharts — رنگ نمودارها از پالت فعال رابط خوانده می‌شود */
(function () {
  var API = window.S.api;
  var $ = function (id) { return document.getElementById(id); };
  var charts = {};

  /* رنگ‌های مقیاس لیکرت مستقل از تم‌اند تا معنا ثابت بماند */
  var RATING_COLORS = {
    "خیلی زیاد": "#16a34a",
    "زیاد": "#65d177",
    "متوسط": "#f4c04e",
    "کم": "#f08a4b",
    "خیلی کم": "#e05252",
    "بدون پاسخ": "#94a3b8"
  };

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function chartColors() {
    return [cssVar("--primary", "#ba376d"), "#3b82f6", "#16a34a", "#f4c04e", "#8b5cf6", "#94a3b8"];
  }

  function textColor() { return cssVar("--text", "#263041"); }
  function mutedColor() { return cssVar("--muted", "#6b7382"); }
  function borderColor() { return cssVar("--border", "#e5e7eb"); }

  function makeChart(id) {
    if (charts[id]) { charts[id].dispose(); }
    charts[id] = echarts.init($(id));
    return charts[id];
  }

  function baseAxis() {
    return {
      axisLabel: { color: textColor(), fontFamily: "Vazirmatn", fontSize: 11 },
      axisLine: { lineStyle: { color: borderColor() } },
      axisTick: { show: false }
    };
  }

  function renderQuestions(data) {
    var el = $("chartQuestions");
    var ch = makeChart("chartQuestions");
    var labels = data.rating_labels.concat([data.no_answer_label]);
    var qShort = data.by_question.map(function (q, i) {
      return "سؤال " + window.S.faNum(i + 1);
    });
    var series = labels.map(function (label) {
      return {
        name: label,
        type: "bar",
        stack: "total",
        barMaxWidth: 46,
        itemStyle: { color: RATING_COLORS[label] || "#999", borderRadius: label === labels[labels.length - 1] ? [4, 4, 0, 0] : 0 },
        emphasis: { focus: "series" },
        data: data.by_question.map(function (q) {
          return label === data.no_answer_label ? q.no_answer : (q.counts[label] || 0);
        })
      };
    });
    ch.setOption({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { textStyle: { color: textColor(), fontFamily: "Vazirmatn", fontSize: 12 }, bottom: 0 },
      grid: { right: 20, left: 46, top: 30, bottom: 62, containLabel: false },
      xAxis: Object.assign(baseAxis(), { type: "category", data: qShort }),
      yAxis: Object.assign(baseAxis(), { type: "value", splitLine: { lineStyle: { color: borderColor() } } }),
      series: series
    });
    // راهنمای متن کامل سؤال‌ها زیر نمودار
    var tips = data.by_question.map(function (q, i) {
      return "<b>سؤال " + window.S.faNum(i + 1) + ":</b> " + q.text;
    }).join("<br>");
    var tipEl = document.getElementById("qTips");
    if (tipEl) tipEl.innerHTML = tips;
    else {
      tipEl = document.createElement("div");
      tipEl.id = "qTips";
      tipEl.className = "muted";
      tipEl.style.fontSize = "12px";
      tipEl.style.marginTop = "8px";
      el.parentNode.appendChild(tipEl);
      tipEl.innerHTML = tips;
    }
  }

  function renderContact(data) {
    var ch = makeChart("chartContact");
    ch.setOption({
      tooltip: { trigger: "item" },
      legend: { orient: "vertical", right: 6, top: "middle", textStyle: { color: textColor(), fontFamily: "Vazirmatn", fontSize: 12 } },
      color: chartColors(),
      series: [{
        type: "pie",
        radius: ["42%", "72%"],
        center: ["36%", "50%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: cssVar("--surface", "#fff"), borderWidth: 2 },
        label: { show: false },
        data: data.by_contact.map(function (r) { return { name: r.text, value: r.count }; })
      }]
    });
  }

  function renderProvince(data) {
    var ch = makeChart("chartProvince");
    var rows = data.by_province.slice().reverse();
    ch.setOption({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { right: 30, left: 90, top: 10, bottom: 26, containLabel: false },
      xAxis: Object.assign(baseAxis(), { type: "value", splitLine: { lineStyle: { color: borderColor() } } }),
      yAxis: Object.assign(baseAxis(), { type: "category", data: rows.map(function (r) { return r.name; }) }),
      series: [{
        type: "bar",
        barMaxWidth: 22,
        itemStyle: { color: cssVar("--primary", "#ba376d"), borderRadius: [0, 6, 6, 0] },
        data: rows.map(function (r) { return r.count; })
      }]
    });
  }

  function renderTrend(data) {
    var ch = makeChart("chartTrend");
    ch.setOption({
      tooltip: { trigger: "axis" },
      grid: { right: 24, left: 46, top: 24, bottom: 44 },
      xAxis: Object.assign(baseAxis(), {
        type: "category",
        data: data.by_day.map(function (r) { return r.date; }),
        boundaryGap: false
      }),
      yAxis: Object.assign(baseAxis(), { type: "value", splitLine: { lineStyle: { color: borderColor() } } }),
      series: [{
        name: "تعداد فرم",
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 7,
        lineStyle: { width: 3, color: cssVar("--primary", "#ba376d") },
        itemStyle: { color: cssVar("--primary", "#ba376d") },
        areaStyle: { color: cssVar("--ring", "rgba(186,55,109,.15)") },
        data: data.by_day.map(function (r) { return r.count; })
      }]
    });
  }

  function faKpi(data) {
    $("kpiTotal").textContent = window.S.faNum(data.total);
    $("kpiCompleted").textContent = window.S.faNum(data.completed);
    $("kpiRate").textContent = window.S.faNum(String(data.completion_rate).replace(".", "٫")) + "٪";
    $("kpiUpdated").textContent = window.S.faNum(document.querySelector("footer bdi").textContent);
  }

  async function load() {
    var p = new URLSearchParams();
    if ($("fprovince").value) p.set("province_id", $("fprovince").value);
    if ($("fcounty").value) p.set("county_id", $("fcounty").value);
    if ($("fcontact").value) p.set("contact_option_id", $("fcontact").value);
    var from = window.S.toEnDigits($("ffrom").value.trim());
    var to = window.S.toEnDigits($("fto").value.trim());
    if (from) p.set("date_from", from);
    if (to) p.set("date_to", to);
    var data = await window.S.fetchJSON(API("/dashboard?" + p.toString()));
    faKpi(data);
    renderQuestions(data);
    renderContact(data);
    renderProvince(data);
    renderTrend(data);
  }

  function loadExcel() {
    var p = new URLSearchParams();
    if ($("fprovince").value) p.set("province_id", $("fprovince").value);
    if ($("fcounty").value) p.set("county_id", $("fcounty").value);
    if ($("fcontact").value) p.set("contact_option_id", $("fcontact").value);
    var from = window.S.toEnDigits($("ffrom").value.trim());
    var to = window.S.toEnDigits($("fto").value.trim());
    if (from) p.set("date_from", from);
    if (to) p.set("date_to", to);
    window.location.href = API("/surveys/export/excel?" + p.toString());
  }

  document.addEventListener("DOMContentLoaded", async function () {
    var provinces = await window.S.fetchJSON(API("/provinces"));
    provinces.forEach(function (p) {
      var o = document.createElement("option");
      o.value = p.id; o.textContent = p.name;
      $("fprovince").appendChild(o);
    });
    var contacts = await window.S.fetchJSON(API("/template/contact-options"));
    contacts.forEach(function (c) {
      var o = document.createElement("option");
      o.value = c.id; o.textContent = c.text;
      $("fcontact").appendChild(o);
    });

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

    $("applyBtn").addEventListener("click", function () { load().catch(function (e) { window.S.toast(e.message, "err"); }); });
    $("resetBtn").addEventListener("click", function () {
      $("fprovince").value = ""; $("fcounty").value = ""; $("fcontact").value = "";
      $("ffrom").value = ""; $("fto").value = "";
      $("fcounty").disabled = true;
      load().catch(function (e) { window.S.toast(e.message, "err"); });
    });
    $("excelBtn").addEventListener("click", loadExcel);

    try { await load(); } catch (e) { window.S.toast(e.message, "err"); }

    window.addEventListener("resize", function () {
      Object.values(charts).forEach(function (c) { c.resize(); });
    });
  });
})();
