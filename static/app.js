/* Night Tech Hub: small helpers. No external libraries. */
document.addEventListener("DOMContentLoaded", function () {
  var root = document.documentElement;

  // Night mode toggle
  var tb = document.querySelector(".theme-btn");
  if (tb) {
    var sync = function () {
      var dark = root.getAttribute("data-theme") === "dark";
      tb.innerHTML = dark ? "&#9728;" : "&#9790;";
      tb.title = dark ? "Light mode" : "Night mode";
    };
    sync();
    tb.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("nthub-theme", next); } catch (e) {}
      sync();
    });
  }

  // Mobile menu
  var mb = document.querySelector(".menu-btn"), nav = document.getElementById("nav");
  if (mb && nav) mb.addEventListener("click", function () {
    var open = nav.classList.toggle("open");
    mb.setAttribute("aria-expanded", open ? "true" : "false");
  });

  // Confirm dangerous buttons
  document.querySelectorAll("[data-confirm]").forEach(function (b) {
    b.addEventListener("click", function (e) { if (!confirm(b.getAttribute("data-confirm"))) e.preventDefault(); });
  });

  // Auto-submit filter selects
  document.querySelectorAll("select[data-autosubmit]").forEach(function (s) {
    s.addEventListener("change", function () { s.form.submit(); });
  });

  // New ticket: show the new-customer box, add device rows
  var cs = document.getElementById("customer_id"), nc = document.getElementById("newcust");
  if (cs && nc) {
    var toggle = function () {
      var isNew = cs.value === "new";
      nc.hidden = !isNew;
      nc.querySelectorAll("input").forEach(function (i) { i.required = isNew && i.name === "name"; });
    };
    cs.addEventListener("change", toggle); toggle();
  }
  var add = document.getElementById("adddev"), box = document.getElementById("devices");
  if (add && box) add.addEventListener("click", function () {
    var row = box.querySelector(".devrow").cloneNode(true);
    row.querySelectorAll("input").forEach(function (i) { i.value = ""; });
    row.querySelectorAll("select").forEach(function (s) { s.selectedIndex = 0; });
    box.appendChild(row);
  });

  // Suggest a strong password (Team page)
  var gen = document.getElementById("genpw"), pw = document.getElementById("newpw");
  if (gen && pw) gen.addEventListener("click", function () {
    var chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789", out = "", buf = new Uint32Array(16);
    crypto.getRandomValues(buf);
    for (var i = 0; i < 16; i++) { out += chars[buf[i] % chars.length]; if (i % 4 === 3 && i < 15) out += "-"; }
    pw.value = out;
  });

  // Copy a value to the clipboard (quote total)
  var copyText = function (text, btn) {
    var done = function () { var o = btn.textContent; btn.textContent = "Copied"; setTimeout(function () { btn.textContent = o; }, 1500); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { window.prompt("Copy this:", text); });
    } else { window.prompt("Copy this:", text); }
  };
  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () { copyText(b.getAttribute("data-copy"), b); });
  });

  // Customer texts: switch template, copy, keep the sms: link in step
  document.querySelectorAll("form.textpick").forEach(function (f) {
    var pick = f.querySelector("[data-textpick]"), body = f.querySelector("[data-textbody]"), sms = f.querySelector("[data-smslink]");
    var syncSms = function () {
      if (!sms) return;
      var base = (pick.options[pick.selectedIndex].getAttribute("data-sms") || "").split("?")[0];
      if (base) sms.href = base + "?&body=" + encodeURIComponent(body.value);
    };
    if (pick && body) {
      pick.addEventListener("change", function () { body.value = pick.options[pick.selectedIndex].getAttribute("data-body") || ""; syncSms(); });
      body.addEventListener("input", syncSms);
    }
    var cp = f.querySelector("[data-copytext]");
    if (cp && body) cp.addEventListener("click", function () { copyText(body.value, cp); });
  });

  // Signature pad (check-in)
  document.querySelectorAll("canvas.sigpad").forEach(function (cv) {
    var form = cv.closest("form"), out = form.querySelector(".sigdata"), ctx = cv.getContext("2d"), drawing = false, inked = false;
    ctx.lineWidth = 2.4; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.strokeStyle = "#1a365d";
    var pos = function (e) {
      var r = cv.getBoundingClientRect();
      return { x: (e.clientX - r.left) * cv.width / r.width, y: (e.clientY - r.top) * cv.height / r.height };
    };
    cv.addEventListener("pointerdown", function (e) {
      drawing = true; inked = true; cv.setPointerCapture(e.pointerId);
      var p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x + 0.1, p.y + 0.1); ctx.stroke(); e.preventDefault();
    });
    cv.addEventListener("pointermove", function (e) { if (!drawing) return; var p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); e.preventDefault(); });
    var stop = function () { drawing = false; };
    cv.addEventListener("pointerup", stop); cv.addEventListener("pointercancel", stop); cv.addEventListener("pointerleave", stop);
    var clr = form.querySelector("[data-sigclear]");
    if (clr) clr.addEventListener("click", function () { ctx.clearRect(0, 0, cv.width, cv.height); inked = false; out.value = ""; });
    form.addEventListener("submit", function () { out.value = inked ? cv.toDataURL("image/png") : ""; });
  });

  // Night sky on the sign-in screens
  var cv = document.querySelector("canvas.sky");
  if (cv && cv.getContext) {
    var ctx = cv.getContext("2d"), stars = [], w = 0, h2 = 0, t0 = performance.now();
    var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var size = function () {
      w = cv.width = window.innerWidth; h2 = cv.height = window.innerHeight; stars = [];
      for (var i = 0; i < Math.round(w * h2 / 9000); i++) stars.push({ x: Math.random() * w, y: Math.random() * h2, r: Math.random() * 1.3 + .3, p: Math.random() * 6.28, s: Math.random() * 1.2 + .4 });
    };
    var draw = function (now) {
      var t = (now - t0) / 1000; ctx.clearRect(0, 0, w, h2);
      stars.forEach(function (s) { ctx.globalAlpha = reduce ? .7 : .3 + .7 * (.5 + .5 * Math.sin(s.p + t * s.s)); ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.2832); ctx.fill(); });
      ctx.globalAlpha = 1;
      if (!reduce && !document.hidden) requestAnimationFrame(draw);
    };
    size(); requestAnimationFrame(draw);
    window.addEventListener("resize", size);
    document.addEventListener("visibilitychange", function () { if (!document.hidden && !reduce) requestAnimationFrame(draw); });
  }
});
