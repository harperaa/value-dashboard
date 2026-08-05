/**
 * Dashboard — Hermes Dashboard Plugin
 *
 * The mentee's metrics home, first in the sidebar. Widget #1: AI ROI —
 * real provider usage where an API exists, run through the transparent
 * 8-step ai-saves.com methodology, headline as an x-factor (1,900% -> 20x).
 *
 * Plain IIFE, no build step. window.__HERMES_PLUGIN_SDK__ for React.
 */
(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;

  // -------------------------------------------------------------------------
  // Sidebar: Dashboard rides FIRST — above Daily Intel Brief (-20). The
  // branded section label moves up onto /metrics; brief/level/roadmap labels
  // are suppressed while this plugin is installed. Mirrors the daily-brief
  // CSS technique; all bundles compose.
  // -------------------------------------------------------------------------
  try {
    if (!document.getElementById("vd-sidebar-order")) {
      var navStyle = document.createElement("style");
      navStyle.id = "vd-sidebar-order";
      var G = 'div[aria-labelledby="hermes-sidebar-plugin-nav-heading"]';
      navStyle.textContent =
        G + ' li:has(> a[href="/metrics"]){order:-25;}' +
        G + ':has(a[href="/metrics"]) li:has(> a[href="/brief"])::before{content:none;}' +
        G + ':has(a[href="/metrics"]) li:has(> a[href="/level"])::before{content:none;}' +
        G + ':has(a[href="/metrics"]) li:has(> a[href="/roadmap"])::before{content:none;}' +
        G + ' li:has(> a[href="/metrics"])::before{content:"AI CYBER VALUE CREATOR™";' +
        'display:block;padding:10px 20px 4px;font-size:11px;letter-spacing:0.12em;' +
        'font-weight:600;color:var(--color-muted-foreground,#9aa0b4);}' +
        G + ':has(> span[class~="lg:hidden"]) li:has(> a[href="/metrics"])::before{display:none;}';
      document.head.appendChild(navStyle);
    }
  } catch (e) { /* styling nicety only */ }

  // -------------------------------------------------------------------------
  // Ambient FX (standalone installs; yields when the acvc bundle is present)
  // -------------------------------------------------------------------------
  (function ambientBackground() {
    var ROUTES = { "/metrics": 1 };
    var canvas = null, tintEl = null, raf = 0, stars = null;
    var pointer = { x: 0, y: 0 }, eased = { x: 0, y: 0 };
    var theme = { r: 20, g: 184, b: 166 }, fore = { r: 230, g: 230, b: 240 };
    var lightTheme = false, moteBase = 255, dpr = 1;
    var probeCanvas = null;

    function parseColor(col, fallback) {
      if (!probeCanvas) { probeCanvas = document.createElement("canvas"); probeCanvas.width = probeCanvas.height = 1; }
      var x = probeCanvas.getContext("2d", { willReadFrequently: true });
      x.fillStyle = fallback; x.fillStyle = col;
      x.clearRect(0, 0, 1, 1); x.fillRect(0, 0, 1, 1);
      var d = x.getImageData(0, 0, 1, 1).data;
      return { r: d[0], g: d[1], b: d[2] };
    }
    function resolveVar(name, fallback) {
      var probe = document.createElement("span");
      probe.style.color = "var(" + name + ", " + fallback + ")";
      probe.style.display = "none";
      document.body.appendChild(probe);
      var col = getComputedStyle(probe).color;
      probe.remove();
      return parseColor(col, fallback);
    }
    function refreshPalette() {
      theme = resolveVar("--color-primary", "#14b8a6");
      fore = parseColor(getComputedStyle(document.body).color, "#e6e6f0");
      var card = resolveVar("--color-card", "#16162a");
      var lum = 0.2126 * card.r + 0.7152 * card.g + 0.0722 * card.b;
      lightTheme = lum > 140;
      moteBase = lightTheme ? 0 : 255;
    }
    function effectsOff() {
      try { return localStorage.getItem("vcl-effects-off") === "1"; }
      catch (e) { return false; }
    }
    function resize() {
      if (!canvas) return;
      dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
    }
    function onMove(e) {
      pointer.x = (e.clientX / window.innerWidth - 0.5) * 2;
      pointer.y = (e.clientY / window.innerHeight - 0.5) * 2;
    }
    function frame(t) {
      if (!canvas) return;
      var ctx = canvas.getContext("2d");
      var w = canvas.width, hgt = canvas.height;
      if (effectsOff()) { ctx.clearRect(0, 0, w, hgt); raf = requestAnimationFrame(frame); return; }
      eased.x += (pointer.x - eased.x) * 0.03;
      eased.y += (pointer.y - eased.y) * 0.03;
      ctx.clearRect(0, 0, w, hgt);
      var lx = (0.5 + 0.34 * Math.sin(t * 0.000041)) * w;
      var ly = (0.42 + 0.30 * Math.sin(t * 0.000029 + 1.7)) * hgt;
      var lr = Math.max(w, hgt) * 0.42;
      var glow = ctx.createRadialGradient(lx, ly, 0, lx, ly, lr);
      glow.addColorStop(0, "rgba(" + theme.r + "," + theme.g + "," + theme.b + ",0.34)");
      glow.addColorStop(0.55, "rgba(" + theme.r + "," + theme.g + "," + theme.b + ",0.13)");
      glow.addColorStop(1, "rgba(" + theme.r + "," + theme.g + "," + theme.b + ",0)");
      ctx.fillStyle = glow; ctx.fillRect(0, 0, w, hgt);
      var l2x = (0.5 - 0.38 * Math.sin(t * 0.000033 + 0.6)) * w;
      var l2y = (0.55 + 0.28 * Math.cos(t * 0.000047)) * hgt;
      var g2 = ctx.createRadialGradient(l2x, l2y, 0, l2x, l2y, lr * 0.7);
      g2.addColorStop(0, "rgba(" + fore.r + "," + fore.g + "," + fore.b + "," + (lightTheme ? 0.09 : 0.13) + ")");
      g2.addColorStop(1, "rgba(" + fore.r + "," + fore.g + "," + fore.b + ",0)");
      ctx.fillStyle = g2; ctx.fillRect(0, 0, w, hgt);
      for (var i = 0; i < stars.length; i++) {
        var st = stars[i];
        st.x += 0.000012 * (0.3 + st.depth);
        st.y -= 0.0000048 * (0.3 + st.depth);
        if (st.x > 1.02) st.x = -0.02;
        if (st.y < -0.02) st.y = 1.02;
        var px = (st.x + eased.x * 0.012 * st.depth) * w;
        var py = (st.y + eased.y * 0.012 * st.depth) * hgt;
        var a = (0.10 + 0.16 * st.depth) *
          (0.7 + 0.3 * Math.sin(t * 0.00045 * st.twinkle + st.phase));
        var base = st.themed ? theme : fore;
        var cr = Math.round(base.r * 0.45 + moteBase * 0.55);
        var cg = Math.round(base.g * 0.45 + moteBase * 0.55);
        var cb = Math.round(base.b * 0.45 + moteBase * 0.55);
        ctx.beginPath();
        ctx.fillStyle = "rgba(" + cr + "," + cg + "," + cb + "," + a + ")";
        ctx.arc(px, py, (0.5 + st.depth * 0.9) * dpr, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(frame);
    }
    function mount() {
      if (canvas) return;
      stars = [];
      for (var i = 0; i < 140; i++) {
        stars.push({ x: Math.random(), y: Math.random(),
          depth: 0.35 + Math.random() * 0.65,
          phase: Math.random() * Math.PI * 2,
          twinkle: 0.4 + Math.random() * 0.8,
          themed: Math.random() < 0.45 });
      }
      tintEl = document.createElement("div");
      tintEl.className = "vd-ambient-tint";
      canvas = document.createElement("canvas");
      canvas.className = "vd-ambient-canvas";
      canvas.style.opacity = "0.95";
      document.body.appendChild(tintEl);
      document.body.appendChild(canvas);
      refreshPalette(); resize();
      window.addEventListener("resize", resize);
      window.addEventListener("mousemove", onMove);
      raf = requestAnimationFrame(frame);
    }
    function unmount() {
      if (!canvas) return;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
      canvas.remove(); tintEl.remove();
      canvas = null; tintEl = null;
    }
    function check() {
      var acvcOwns = !!document.getElementById("acvc-sidebar-order");
      if (ROUTES[window.location.pathname] && !acvcOwns) mount(); else unmount();
    }
    try {
      new MutationObserver(function () { refreshPalette(); })
        .observe(document.documentElement, { attributes: true, attributeFilter: ["class", "style", "data-theme"] });
    } catch (e) {}
    setInterval(refreshPalette, 3000);
    window.addEventListener("popstate", check);
    setInterval(check, 800);
    check();
  })();

  var React = SDK.React;
  var h = React.createElement;
  var hooks = SDK.hooks;
  var useState = hooks.useState;
  var useEffect = hooks.useEffect;
  var useCallback = hooks.useCallback;

  var API = "/api/plugins/value-dashboard";

  function api(path, options) {
    return SDK.fetchJSON(API + path, options);
  }

  function postJSON(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  var MUTED = "var(--color-muted-foreground, #9aa0b4)";

  function fmtMoney(n) {
    if (n == null) return "—";
    return "$" + Number(n).toLocaleString(undefined,
      { maximumFractionDigits: Math.abs(n) < 100 ? 2 : 0 });
  }

  // -------------------------------------------------------------------------
  // AI ROI widget
  // -------------------------------------------------------------------------
  function RoiWidget(props) {
    var st = props.st;
    var roi = st.roi || {};
    var usage = st.usage || {};
    var params = roi.params || {};
    var busySt = useState(null);
    var busy = busySt[0], setBusy = busySt[1];
    var errSt = useState(null);
    var err = errSt[0], setErr = errSt[1];
    var stepsSt = useState(false);
    var showSteps = stepsSt[0], setShowSteps = stepsSt[1];
    var detSt = useState(function () {
      try { return localStorage.getItem("vd-details") === "1"; }
      catch (e) { return false; }
    });
    var showDetails = detSt[0], setShowDetails = detSt[1];
    function toggleDetails() {
      setShowDetails(function (v) {
        try { localStorage.setItem("vd-details", v ? "0" : "1"); }
        catch (e) {}
        return !v;
      });
    }
    var editSt = useState(null);      // draft params while editing
    var draft = editSt[0], setDraft = editSt[1];

    function run(path) {
      setBusy(path); setErr(null);
      postJSON(path, {})
        .then(function (r) { props.onState(r.state); })
        .catch(function (e) { setErr(String((e && e.message) || e)); })
        .finally(function () { setBusy(null); });
    }
    function saveDraft() {
      setBusy("/params"); setErr(null);
      postJSON("/params", draft)
        .then(function (r) { props.onState(r.state); setDraft(null); })
        .catch(function (e) { setErr(String((e && e.message) || e)); })
        .finally(function () { setBusy(null); });
    }

    function field(label, key, step) {
      return h("div", { className: "vd-field" },
        h("label", null, label),
        h("input", {
          className: "vd-input", type: "number", step: step || 1,
          value: draft[key],
          onChange: function (e) {
            var v = e.target.value;
            setDraft(function (d) {
              var next = Object.assign({}, d);
              next[key] = v === "" ? 0 : Number(v);
              return next;
            });
          },
        }));
    }

    function fmtTok(n) {
      n = Number(n) || 0;
      if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
      if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
      if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
      return String(n);
    }
    var provChips = (usage.providers || []).map(function (p, i) {
      var cls = p.state === "ok" ? "vd-prov-ok"
        : p.state === "error" ? "vd-prov-err" : "vd-prov-warn";
      var label = p.provider +
        (p.state === "ok" ? " " + fmtMoney(p.costUsd) +
          (p.tokens ? " · " + fmtTok(p.tokens) + " tok" : "") : "");
      var chip = h("span", { key: i, className: "vd-prov " + cls,
          title: (p.note || p.error || p.period || "") +
            (p.docUrl ? " — click for the provider's usage-API docs"
                      : "") },
        (p.state === "ok" ? "✓ " : p.state === "error" ? "✕ " : "◌ ") +
        label);
      return p.docUrl
        ? h("a", { key: i, href: p.docUrl, target: "_blank",
            rel: "noreferrer", style: { textDecoration: "none" } }, chip)
        : chip;
    });

    return h("div", null,
      h("div", { className: "vd-card" },
        h("div", { style: { display: "flex", alignItems: "center",
                            gap: 10, flexWrap: "wrap" } },
          h("div", { style: { fontWeight: 800, fontSize: 16, flex: 1 } },
            "🤖 AI ROI"),
          h("span", { className: "vd-note" },
            params.taskLabel || "")),
        roi.xFactor != null
          ? h("div", { className: "vd-hero" },
              h("span", { className: "vd-x" },
                (roi.xFactor >= 10 ? Math.round(roi.xFactor)
                                   : roi.xFactor) + "x"),
              h("span", { className: "vd-roi" },
                "Year-1 ROI " + (roi.roiPct >= 0 ? "+" : "") +
                Number(roi.roiPct).toLocaleString() + "%"),
              h("span", { className: "vd-sub" },
                "every $1 of AI spend returns " +
                fmtMoney(roi.xFactor) + " of value"))
          : h("div", { className: "vd-note", style: { fontSize: 13.5 } },
              roi.roiNote || "Not enough data yet."),
        roi.hoursBasis === "tokens"
          ? h("div", { className: "vd-note", style: { marginTop: 6 } },
              "labor saved is measured from real token usage: " +
              Number(roi.measuredTokensMonthly).toLocaleString() +
              " tokens ≈ " + roi.tokenHoursMonthly + " h of human-equivalent " +
              "output this period")
          : null,
        h("div", { className: "vd-stats" },
          h("div", { className: "vd-stat" },
            h("div", { className: "vd-stat-n" },
              fmtMoney(roi.netMonthlyUsd)),
            h("div", { className: "vd-stat-l" }, "net savings / month")),
          h("div", { className: "vd-stat" },
            h("div", { className: "vd-stat-n" },
              fmtMoney(roi.annualNetUsd)),
            h("div", { className: "vd-stat-l" }, "net benefit / year")),
          h("div", { className: "vd-stat" },
            h("div", { className: "vd-stat-n" },
              fmtMoney(roi.aiMonthlyUsd)),
            h("div", { className: "vd-stat-l" }, "AI cost / month" +
              (usage.measuredMonthlyUsd
                ? " (" + fmtMoney(usage.measuredMonthlyUsd) + " measured)"
                : ""))),
          h("div", { className: "vd-stat" },
            h("div", { className: "vd-stat-n" },
              (roi.steps && roi.steps[3] ? roi.steps[3].value : 0) + " h"),
            h("div", { className: "vd-stat-l" }, "hours automated / month"))),
        // every widget on this page follows the pattern: summary up top,
        // a Details toggle pinned to the widget's bottom edge
        h("div", { style: { marginTop: 14, borderTop:
            "1px solid var(--color-border, #2b2b44)", paddingTop: 10 } },
          h("button", { className: "vd-btn", style: { fontSize: 12 },
              onClick: toggleDetails },
            h("span", { className: "vd-chev" +
                (showDetails ? " vd-chev-open" : "") }, "▸"),
            " Details"))),

      !showDetails ? null : h(React.Fragment, null,
      h("div", { className: "vd-card" },
        h("div", { className: "vd-h" }, "Measured usage by provider"),
        h("div", { style: { display: "flex", gap: 8, flexWrap: "wrap",
                            alignItems: "center" } },
          provChips.length ? provChips
            : h("span", { className: "vd-note" },
                "No provider keys found yet — connect an LLM provider on " +
                "the Keys page."),
          h("span", { style: { flex: 1 } }),
          h("button", { className: "vd-btn", disabled: busy !== null,
              onClick: function () { run("/refresh"); } },
            busy === "/refresh" ? "Checking…" : "⟳ Refresh usage")),
        (usage.unsupportedCount || 0) > 0
          ? h("div", { className: "vd-note", style: { marginTop: 8 } },
              "◌ providers have no usage API — check their console and put " +
              "the monthly figure into “manual AI spend” below so the ROI " +
              "stays honest.")
          : null),

      h("div", { className: "vd-card" },
        h("div", { style: { display: "flex", alignItems: "center",
                            gap: 10, flexWrap: "wrap" } },
          h("div", { className: "vd-h", style: { margin: 0, flex: 1 } },
            "Assumptions" +
            (params.source === "company-context"
              ? " — derived from your Company Context"
              : params.source === "manual" ? " — manually tuned"
              : " — standard blended rates")),
          st.hasCompanyContext
            ? h("button", { className: "vd-btn", disabled: busy !== null,
                onClick: function () { run("/derive"); } },
                busy === "/derive" ? "Deriving…"
                                   : "↻ Derive from Company Context")
            : null,
          draft
            ? h(React.Fragment, null,
                h("button", { className: "vd-btn",
                    onClick: function () { setDraft(null); } }, "Cancel"),
                h("button", { className: "vd-btn vd-btn-primary",
                    disabled: busy !== null, onClick: saveDraft },
                  busy === "/params" ? "Saving…" : "Save"))
            : h("button", { className: "vd-btn",
                onClick: function () {
                  setDraft({
                    hoursBasis: params.hoursBasis || "auto",
                    employees: params.employees,
                    salaryMonthly: params.salaryMonthly,
                    hoursPerWeek: params.hoursPerWeek,
                    weeksPerMonth: params.weeksPerMonth,
                    automationPct: params.automationPct,
                    aiMonthlyManualUsd: params.aiMonthlyManualUsd,
                    implementationUsd: params.implementationUsd,
                  });
                } }, "✎ Edit")),
        params.derivedNote
          ? h("div", { className: "vd-note", style: { margin: "8px 0" } },
              params.derivedNote)
          : null,
        draft
          ? h("div", { className: "vd-params", style: { marginTop: 10 } },
              field("people", "employees"),
              field("salary $/mo", "salaryMonthly", 100),
              field("hours/week", "hoursPerWeek", 0.5),
              field("weeks/mo", "weeksPerMonth", 0.1),
              field("automation %", "automationPct", 5),
              field("manual AI spend $/mo", "aiMonthlyManualUsd", 10),
              field("implementation $", "implementationUsd", 100),
              h("div", { className: "vd-field" },
                h("label", null, "hours basis"),
                h("select", {
                  className: "vd-input",
                  value: draft.hoursBasis || "auto",
                  onChange: function (e) {
                    var v = e.target.value;
                    setDraft(function (d) {
                      return Object.assign({}, d, { hoursBasis: v });
                    });
                  },
                },
                  h("option", { value: "auto" }, "auto (tokens if measured)"),
                  h("option", { value: "assumptions" }, "assumptions"),
                  h("option", { value: "tokens" }, "measured tokens"))))
          : h("div", { className: "vd-note", style: { marginTop: 6 } },
              params.employees + " person(s) · " +
              fmtMoney(params.salaryMonthly) + "/mo gross · " +
              params.hoursPerWeek + " h/wk · " +
              params.automationPct + "% automation · manual AI spend " +
              fmtMoney(params.aiMonthlyManualUsd) + "/mo"),
        err ? h("div", { className: "vd-err" }, err) : null),

      h("div", { className: "vd-card" },
        h("div", { style: { cursor: "pointer", userSelect: "none",
                            fontWeight: 800 },
            onClick: function () { setShowSteps(!showSteps); } },
          h("span", { className: "vd-chev" +
              (showSteps ? " vd-chev-open" : "") }, "▸"),
          " Step-by-step calculation",
          h("span", { className: "vd-note", style: { fontWeight: 400,
              marginLeft: 8 } },
            "the 8-step methodology — every figure verifiable")),
        showSteps
          ? h(React.Fragment, null,
              h("table", { className: "vd-steps",
                           style: { marginTop: 10 } },
                h("tbody", null, (roi.steps || []).map(function (s2) {
                  return h("tr", { key: s2.n },
                    h("td", null, s2.n),
                    h("td", null, s2.label,
                      h("div", { className: "vd-formula" }, s2.formula)),
                    h("td", { className: "vd-val" },
                      (s2.value == null ? "—"
                        : s2.unit === "%"
                          ? Number(s2.value).toLocaleString() + "%"
                          : s2.unit === "$/mo" || s2.unit === "$/h"
                            ? fmtMoney(s2.value) +
                              (s2.unit === "$/h" ? "/h" : "/mo")
                            : s2.value + " " + s2.unit)));
                }))),
              h("div", { className: "vd-note", style: { marginTop: 10 } },
                "Methodology: the transparent 8-step AI-ROI formula from ",
                h("a", { href: "https://www.ai-saves.com/en",
                    target: "_blank", rel: "noreferrer",
                    style: { color: "var(--color-primary, #14b8a6)" } },
                  "ai-saves.com"),
                " — conservative automation medians, payroll burden x1.3, " +
                "net of every AI dollar. The x-factor is ROI% ÷ 100 + 1 " +
                "(1,900% → 20x). When measured tokens exist, hours saved " +
                "use the token→labor model: tokens × 0.75 words × " +
                "1/600 words-per-hour × 35% utilization."))
          : null)));
  }

  // -------------------------------------------------------------------------
  // Page
  // -------------------------------------------------------------------------
  function DashboardPage() {
    var stSt = useState(null);
    var st = stSt[0], setSt = stSt[1];
    var errSt = useState(null);
    var err = errSt[0], setErr = errSt[1];
    var bootSt = useState(false);
    var booted = bootSt[0], setBooted = bootSt[1];

    var refresh = useCallback(function () {
      return api("/state")
        .then(function (d) { setSt(d); setErr(null); return d; })
        .catch(function (e) { setErr(String((e && e.message) || e)); });
    }, []);
    useEffect(function () {
      refresh().then(function (d) {
        if (!d || booted) return;
        setBooted(true);
        // first visit: collect usage once, and derive parameters from the
        // Company Context if it exists and nothing was derived before
        if (!(d.usage && d.usage.at)) {
          postJSON("/refresh", {})
            .then(function (r) { setSt(r.state); })
            .catch(function () {});
        }
        if (d.hasCompanyContext && d.roi &&
            (d.roi.params || {}).source === "defaults") {
          postJSON("/derive", {})
            .then(function (r) { setSt(r.state); })
            .catch(function () {});
        }
      });
    }, [refresh]);

    if (!st) {
      return h("div", { className: "vd-page" },
        h("div", { style: { color: MUTED, padding: 40 } }, err || "Loading…"));
    }

    return h("div", { className: "vd-page" },
      h("div", { className: "vd-inner" },
        h("div", { style: { marginBottom: 14 } },
          h("div", { style: { fontSize: 13, letterSpacing: 1.5, color: MUTED,
                              textTransform: "uppercase" } },
            "AI Cyber Value Creator™"),
          h("h1", { style: { fontSize: 30, margin: "4px 0 6px",
                             fontWeight: 800 } },
            "📊 Dashboard")),
        err ? h("div", { className: "vd-err" }, err) : null,
        h(RoiWidget, { st: st, onState: setSt })));
  }

  window.__HERMES_PLUGINS__.register("value-dashboard", DashboardPage);
})();
