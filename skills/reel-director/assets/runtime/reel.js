/* reel-director runtime: builds every effect from window.REEL (written by build.py) into ONE paused
   GSAP timeline. Deterministic and seek-safe: no timers, no randomness; state that depends on the
   playhead is derived inside tweens. */
(function () {
  const R = window.REEL, FPS = R.fps, END = R.duration, U = R.u;
  const q = (t) => Math.round(t * FPS) / FPS;
  const tl = gsap.timeline({ paused: true });
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  /* ---------------- icons (stroke = currentColor) ---------------- */
  const P = {
    phone: '<rect x="20" y="6" width="24" height="52" rx="6"/><path d="M29 50h6"/>',
    wallet: '<rect x="6" y="16" width="52" height="36" rx="8"/><path d="M6 27h52"/><circle cx="46" cy="40" r="3"/>',
    chat: '<path d="M8 10h48v32H28L16 54V42H8z"/>',
    target: '<circle cx="32" cy="32" r="25"/><circle cx="32" cy="32" r="13"/><circle cx="32" cy="32" r="3"/>',
    shield: '<path d="M32 5l23 9v17c0 15-11 25-23 29C20 56 9 46 9 31V14z"/><path d="M22 32l7 7 13-14"/>',
    chart: '<path d="M8 56h48M14 56V36M28 56V22M42 56V30M56 56V12"/>',
    growth: '<path d="M6 52l18-20 12 10 22-26M42 16h16v16"/>',
    tower: '<path d="M8 58h48M14 58V34M32 58V16M50 58V30M10 34L32 12l22 18"/>',
    globe: '<circle cx="32" cy="32" r="25"/><ellipse cx="32" cy="32" rx="11" ry="25"/><path d="M8 24h48M8 40h48"/>',
    people: '<circle cx="22" cy="22" r="9"/><circle cx="44" cy="24" r="7"/><path d="M6 54c0-10 7-17 16-17s16 7 16 17M38 54c0-8 4-14 10-14s10 6 10 14"/>',
    user: '<circle cx="32" cy="22" r="11"/><path d="M12 56c0-11 9-19 20-19s20 8 20 19"/>',
    tool: '<path d="M14 50l22-22M40 10a11 11 0 1 0 14 14l-7-2-3-7-4-5z"/>',
    bank: '<path d="M6 24L32 8l26 16zM12 30v20M24 30v20M40 30v20M52 30v20M6 56h52"/>',
    money: '<rect x="6" y="16" width="52" height="32" rx="6"/><circle cx="32" cy="32" r="8"/>',
    check: '<path d="M12 33l13 13 27-28"/>',
    cross: '<path d="M16 16l32 32M48 16L16 48"/>',
    clock: '<circle cx="32" cy="32" r="25"/><path d="M32 18v15l10 6"/>',
    bolt: '<path d="M36 6L14 36h16l-4 22 22-30H32z"/>',
    heart: '<path d="M32 54S8 40 8 23a12 12 0 0 1 24-4 12 12 0 0 1 24 4c0 17-24 31-24 31z"/>',
    star: '<path d="M32 6l8 17 18 2-13 12 4 18-17-9-17 9 4-18L6 25l18-2z"/>',
    home: '<path d="M8 30L32 10l24 20M14 26v28h36V26"/>',
    book: '<path d="M8 12h20a6 6 0 0 1 6 6v36a5 5 0 0 0-5-5H8zM56 12H36a6 6 0 0 0-6 6v36a5 5 0 0 1 5-5h21z"/>',
    cart: '<path d="M6 10h8l7 30h30l5-20H18"/><circle cx="24" cy="52" r="4"/><circle cx="46" cy="52" r="4"/>',
    car: '<path d="M8 40l5-16h38l5 16v10H8z"/><circle cx="18" cy="50" r="5"/><circle cx="46" cy="50" r="5"/>',
    lock: '<rect x="12" y="28" width="40" height="28" rx="6"/><path d="M20 28v-8a12 12 0 0 1 24 0v8"/>',
    wifi: '<path d="M6 24a38 38 0 0 1 52 0M14 33a26 26 0 0 1 36 0M22 42a14 14 0 0 1 20 0"/><circle cx="32" cy="51" r="3"/>',
    signal: '<path d="M10 52v-6M22 52V38M34 52V26M46 52V14"/>',
    idea: '<path d="M22 44a16 16 0 1 1 20 0v6H22zM24 56h16"/>',
    rocket: '<path d="M32 6c12 8 16 22 12 36H20C16 28 20 14 32 6z"/><path d="M20 42l-8 10M44 42l8 10"/><circle cx="32" cy="24" r="5"/>',
    calendar: '<rect x="8" y="12" width="48" height="44" rx="6"/><path d="M8 24h48M20 6v10M44 6v10"/>',
    mail: '<rect x="6" y="14" width="52" height="36" rx="6"/><path d="M6 18l26 18 26-18"/>',
    play: '<path d="M20 12l30 20-30 20z"/>',
    pin: '<path d="M32 58S12 38 12 24a20 20 0 0 1 40 0c0 14-20 34-20 34z"/><circle cx="32" cy="24" r="7"/>',
    language: '<path d="M8 12h28M22 8v4M14 12c2 10 10 18 18 20M30 12c-2 10-10 18-18 20M34 56l10-24 10 24M38 46h12"/>',
    trend_down: '<path d="M6 14l18 20 12-10 22 26M42 50h16V34"/>',
  };
  const icon = (n) => `<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">${P[n] || P.star}</svg>`;

  /* ---------------- helpers ---------------- */
  const pageRanges = [], hide = [];
  const inR = (t, Rg) => Rg.some(([a, b]) => t >= a && t < b);
  function fitText(node, maxW) { // shrink a single line until it fits the width
    let fs = parseFloat(getComputedStyle(node).fontSize);
    for (let i = 0; i < 30 && node.scrollWidth > maxW; i++) { fs *= 0.94; node.style.fontSize = fs + "px"; }
  }
  function countUp(t, d, to, fn, from) {
    const o = { v: from || 0 };
    tl.to(o, { v: to, duration: d, ease: "power3.out", onUpdate: () => fn(o.v) }, q(t));
  }
  const pop = (s, t, extra) => tl.fromTo(s, { opacity: 0, y: 30 * U, scale: 0.85 }, Object.assign({ opacity: 1, y: 0, scale: 1, duration: 0.32, ease: "back.out(2)" }, extra || {}), q(t));

  /* ---------------- wall words ---------------- */
  function words(b, root) {
    const zone = R.wall;
    const stack = el("div", "stack"); stack.style.top = zone.top + "px"; root.appendChild(stack);
    const base = { big: 128, box: 128, serif: 72 };
    const lines = b.lines.map((L) => {
      const ln = el("div", "ln s-" + (L.style || "big") + (L.style === "serif" ? " serif" : ""));
      ln.style.fontSize = ((L.size || base[L.style || "big"]) * U) + "px";
      const inner = L.style === "box" ? `<span class="box">${esc(L.text)}</span>` : esc(L.text);
      ln.innerHTML = b.anim === "drop" ? inner.replace(/(<[^>]+>)|([^<])/g, (m, tag, ch) => tag || (ch === " " ? "&nbsp;" : `<span class="ch">${ch}</span>`))
                                        : `<span class="mask"><span>${inner}</span></span>`;
      if (L.strike_at != null) ln.appendChild(el("div", "strike"));
      if (L.swap) { ln.style.position = "absolute"; ln.style.left = "0"; ln.style.right = "0"; }
      stack.appendChild(ln); fitText(ln, R.W * 0.92); return { L, ln };
    });
    // swapped lines sit exactly where the line they replace was
    lines.forEach((o, i) => { if (o.L.swap && i > 0) o.ln.style.top = lines[i - 1].ln.offsetTop + "px"; });
    const h = stack.scrollHeight, room = zone.bottom - zone.top;
    if (h > room) stack.style.transform = `scale(${room / h})`, stack.style.transformOrigin = "50% 0";
    else stack.style.top = (zone.top + (room - h) * (b.valign === "top" ? 0 : 0.5)) + "px";
    lines.forEach(({ L, ln }, i) => {
      const t = L.at != null ? L.at : b.at + i * 0.3;
      if (b.anim === "drop") tl.fromTo($$(".ch", ln), { y: -R.H * 0.5 }, { y: 0, duration: 0.6, ease: "bounce.out", stagger: 0.045 }, q(t));
      else if (b.anim === "slam") tl.fromTo(ln, { scale: 1.8, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.22, ease: "power4.out" }, q(t));
      // opacity too: italic overhangs can peek past the mask, and a stray pixel on frame 1 shows on every loop
      else tl.fromTo($(".mask > span", ln), { yPercent: 150, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 0.42, ease: "power4.out" }, q(t));
      if (L.strike_at != null) tl.to($(".strike", ln), { width: "100%", duration: 0.32, ease: "power3.inOut" }, q(L.strike_at));
      if (L.out_at != null) tl.to(ln, { opacity: 0, y: -20 * U, duration: 0.25, ease: "power2.in" }, q(L.out_at));
    });
    if (b.role === "loop") tl.to($$(".mask > span", stack), { yPercent: -150, opacity: 0, duration: 0.18, ease: "power3.in" }, q(END - 0.2));
    else tl.to(stack, { opacity: 0, y: -24 * U, duration: 0.22, ease: "power2.in" }, q(b.until - 0.24));
  }

  /* ---------------- page kinds ---------------- */
  const K = {};
  K.title = (b, c, root) => {
    root.classList.remove("dots");
    c.innerHTML = `${b.kicker ? `<div class="k">${esc(b.kicker)}</div>` : ""}<div class="t1">${esc(b.title || "")}</div>${b.serif ? `<div class="t2 serif">${esc(b.serif)}</div>` : ""}`;
    $$(".t1,.t2", c).forEach((n) => fitText(n, R.W * 0.9));
    tl.from($(".t1", c), { y: 60 * U, opacity: 0, duration: 0.35, ease: "power3.out" }, q(b.at + 0.15));
    if (b.serif) tl.from($(".t2", c), { y: 60 * U, opacity: 0, duration: 0.35, ease: "power3.out" }, q(b.at + 0.55));
  };
  K.counter = (b, c) => {
    c.innerHTML = `<div class="num">${esc(b.prefix || "")}<span class="v">0</span>${esc(b.suffix || "")}</div>${b.sub ? `<div class="sub">${esc(b.sub)}</div>` : ""}`;
    const v = $(".v", c), d = b.decimals || 0;
    countUp(b.count_at || b.at + 0.3, b.count_dur || 1.1, b.value, (x) => (v.textContent = Number(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })), b.from);
    tl.fromTo(c.firstChild, { scale: 0.85, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.4, ease: "back.out(1.8)" }, q(b.at + 0.15));
  };
  K.donut = (b, c) => {
    const C = 2 * Math.PI * 330;
    const baseArc = b.base != null ? `<circle cx="400" cy="400" r="330" fill="none" stroke-width="74" stroke="var(--primary-20)" transform="rotate(-90 400 400)" stroke-dasharray="${C * b.base / 100} ${C}"/>` : "";
    const rot = b.base != null ? -90 + 360 * b.base / 100 : -90;
    c.innerHTML = `<div class="ringwrap"><svg viewBox="0 0 800 800"><circle cx="400" cy="400" r="330" fill="none" stroke-width="74" stroke="var(--ink-08)"/>${baseArc}
      <circle class="arc" cx="400" cy="400" r="330" fill="none" stroke-width="74" stroke="var(--primary)" stroke-linecap="round" transform="rotate(${rot} 400 400)" stroke-dasharray="0 ${C}"/></svg>
      <div class="center"><div class="num"><span class="v">0</span>${esc(b.suffix == null ? "%" : b.suffix)}</div>${b.sub ? `<div class="sub">${esc(b.sub)}</div>` : ""}</div></div>`;
    const v = $(".v", c), arc = $(".arc", c);
    countUp(b.count_at || b.at + 0.3, 1.1, b.value, (x) => { v.textContent = Math.round(x); arc.setAttribute("stroke-dasharray", (C * x / 100).toFixed(1) + " " + C); });
    tl.fromTo($(".center", c), { scale: 0.85, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.4, ease: "back.out(1.8)" }, q(b.at + 0.2));
  };
  K.bars = (b, c) => {
    const max = Math.max(...b.items.map((i) => i.value));
    c.innerHTML = `<div class="rows">${b.items.map((i) => `<div class="row"><div class="top"><span>${esc(i.label)}</span><span class="v">0${esc(b.unit || "")}</span></div><div class="track"><div class="fill"></div></div></div>`).join("")}</div>`;
    $$(".row", c).forEach((row, k) => {
      const it = b.items[k], t = it.at != null ? it.at : b.at + 0.4 + k * 0.35, v = $(".v", row);
      tl.to($(".fill", row), { width: (it.value / max * 100) + "%", duration: 0.8, ease: "power3.out" }, q(t));
      countUp(t, 0.8, it.value, (x) => (v.textContent = Math.round(x) + (b.unit || "")));
    });
  };
  K.list = (b, c) => {
    c.innerHTML = `<div class="rows">${b.items.map((i, k) => `<div class="row"><div class="ic" style="color:var(--on-primary)">${icon(i.icon)}</div><div class="tx"><small>${String(k + 1).padStart(2, "0")}</small>${esc(i.text)}</div></div>`).join("")}</div>`;
    $$(".tx", c).forEach((n) => fitText(n, R.W * 0.68));
    $$(".row", c).forEach((row, k) => tl.fromTo(row, { opacity: 0, x: -60 * U }, { opacity: 1, x: 0, duration: 0.32, ease: "power3.out" }, q((b.items[k].at != null ? b.items[k].at : b.at + 0.4 + k * 0.5) - 0.05)));
  };
  K.compare = (b, c) => {
    c.innerHTML = `<div class="side l">${esc(b.left)}</div><div class="op">${esc(b.op || "=")}<div class="x"></div></div><div class="side r">${esc(b.right)}</div>${b.verdict ? `<div class="verdict">${esc(b.verdict)}</div>` : ""}`;
    $$(".side", c).forEach((n) => fitText(n, R.W * 0.86));
    tl.fromTo($(".side.l", c), { opacity: 0, y: 40 * U }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }, q(b.left_at || b.at + 0.3));
    tl.fromTo($(".op", c), { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)" }, q(b.op_at || b.at + 0.8));
    tl.fromTo($(".side.r", c), { opacity: 0, y: 40 * U }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }, q(b.right_at || b.at + 1.3));
    if (b.strike_at) {
      tl.to($(".op .x", c), { width: 210 * U, duration: 0.2, ease: "power3.inOut" }, q(b.strike_at));
      tl.to(c, { x: 12 * U, duration: 0.04, repeat: 5, yoyo: true }, q(b.strike_at + 0.02));
    }
    if (b.verdict) tl.fromTo($(".verdict", c), { opacity: 0, scale: 1.6 }, { opacity: 1, scale: 1, duration: 0.2, ease: "power4.out" }, q(b.verdict_at || b.strike_at || b.until - 0.8));
  };
  K.source = (b, c) => {
    c.innerHTML = `<div class="zone"><div class="zl">${esc(b.zone || "SOURCE")}</div><div class="file"><div class="doc"><i style="top:30%"></i><i style="top:44%;right:30%"></i><i style="top:58%"></i></div>
      <div><div class="fn">${esc(b.name)}</div><div class="fm">${esc(b.sub || "")}</div></div><div class="ok">${icon("check").replace('stroke="currentColor"', 'stroke="var(--on-primary)"')}</div></div></div>`;
    tl.fromTo($(".zone", c), { scale: 0.92, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.35, ease: "power3.out" }, q(b.at + 0.1));
    tl.fromTo($(".file", c), { y: -R.H * 0.4, rotate: -6 }, { y: 0, rotate: 0, duration: 0.75, ease: "bounce.out" }, q(b.at + 0.3));
    tl.fromTo($(".ok", c), { scale: 0 }, { scale: 1, duration: 0.3, ease: "back.out(3)" }, q(b.at + 1.1));
    tl.to($(".zone", c), { borderColor: "var(--primary)", duration: 0.3 }, q(b.at + 1.05));
  };
  K.converge = (b, c) => {
    c.innerHTML = `<svg class="lines"></svg><div class="roles">${b.items.map((i) => `<div class="role"><div class="ic" style="color:var(--primary)">${icon(i.icon)}</div><div class="nm">${esc(i.text)}</div></div>`).join("")}</div>
      <div class="target"><div class="n">${esc(b.target)}</div>${b.target_sub ? `<div class="t">${esc(b.target_sub)}</div>` : ""}</div>`;
    $$(".role", c).forEach((r, k) => pop(r, b.items[k].at != null ? b.items[k].at : b.at + 0.2 + k * 0.22));
    const svg = $("svg.lines", c), tg = $(".target", c), cr = c.getBoundingClientRect(), tr = tg.getBoundingClientRect();
    svg.setAttribute("viewBox", `0 0 ${cr.width} ${cr.height}`);
    $$(".role .ic", c).forEach((ic) => {
      const r = ic.getBoundingClientRect(), x1 = r.left + r.width / 2 - cr.left, y1 = r.bottom - cr.top + 50 * U, x2 = tr.left + tr.width / 2 - cr.left, y2 = tr.top - cr.top;
      const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", `M${x1} ${y1} C ${x1} ${(y1 + y2) / 2}, ${x2} ${(y1 + y2) / 2}, ${x2} ${y2}`); svg.appendChild(p);
    });
    tl.fromTo($$("path", svg), { strokeDashoffset: 300, opacity: 0 }, { strokeDashoffset: 0, opacity: 1, duration: 0.6, ease: "power2.out" }, q(b.target_at ? b.target_at - 0.5 : b.at + 0.9));
    tl.fromTo(tg, { opacity: 0, scale: 0.5 }, { opacity: 1, scale: 1, duration: 0.45, ease: "back.out(1.8)" }, q(b.target_at || b.at + 1.3));
  };
  K.apps = (b, c) => {
    const shades = R.shades;
    c.innerHTML = `<div class="grid">${b.items.map((i, k) => `<div class="app"><div class="ic" style="background:${shades[k % shades.length]}">${esc(i.letter || i.name[0])}<div class="x">×</div></div><div class="nm">${esc(i.name)}</div></div>`).join("")}</div>${b.after ? `<div class="after serif">${esc(b.after)}</div>` : ""}`;
    const apps = $$(".app", c);
    tl.fromTo(apps, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)", stagger: 0.07 }, q(b.at + 0.1));
    const del = b.delete_at || b.until - 1.4;
    const jig = Math.max(2, Math.floor((del - b.at - 0.5) / 0.09));
    tl.to(apps, { rotate: (i) => (i % 2 ? 2.5 : -2.5), duration: 0.09, repeat: jig, yoyo: true, ease: "sine.inOut" }, q(b.at + 0.5));
    tl.to($$(".x", c), { opacity: 1, duration: 0.2, stagger: 0.08 }, q(b.at + 0.6));
    apps.forEach((a, k) => tl.to(a, { scale: 0, opacity: 0, duration: 0.26, ease: "back.in(2)" }, q(del + k * 0.16)));
    if (b.after) tl.fromTo($(".after", c), { opacity: 0, y: 40 * U }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }, q(del + apps.length * 0.16 + 0.1));
  };
  K.pick = (b, c) => {
    const shades = R.shades;
    c.innerHTML = `<div class="grid">${b.items.map((i, k) => `<div class="sw"><div class="chip"><div class="fill" style="background:${shades[k % shades.length]}"></div><span style="color:var(--on-primary);display:contents">${icon(i.icon)}</span></div><div class="lb">${esc(i.text)}</div></div>`).join("")}
      <svg class="dropper" viewBox="0 0 120 120"><g transform="rotate(45 60 60)"><rect x="49" y="6" width="22" height="30" rx="8" fill="var(--primary)"/><rect x="53" y="34" width="14" height="58" rx="4" fill="#fff" stroke="var(--primary)" stroke-width="5"/><path d="M60 92 L60 112" stroke="var(--primary)" stroke-width="6" stroke-linecap="round"/></g></svg></div>`;
    const grid = $(".grid", c), drop = $(".dropper", c), gr = grid.getBoundingClientRect();
    tl.set(drop, { x: gr.width * 0.6, y: gr.height + 40 * U }, 0);
    $$(".sw", c).forEach((sw, k) => {
      const it = b.items[k], t = it.at != null ? it.at : b.at + 0.5 + k * 0.6, r = sw.getBoundingClientRect();
      tl.to(drop, { x: r.left - gr.left + r.width * 0.55, y: r.top - gr.top + r.height * 0.3, duration: 0.3, ease: "power3.inOut" }, q(t - 0.32));
      tl.to($(".fill", sw), { scale: 1, duration: 0.32, ease: "back.out(1.6)" }, q(t));
      tl.to($("svg", sw), { opacity: 1, duration: 0.2 }, q(t + 0.1));
      tl.to($(".lb", sw), { opacity: 1, duration: 0.2 }, q(t));
      tl.to($(".chip", sw), { borderColor: "rgba(0,0,0,0)", duration: 0.2 }, q(t));
    });
    tl.to(drop, { x: gr.width + 200 * U, y: -200 * U, duration: 0.4, ease: "power2.in" }, q(b.until - 0.7));
  };
  K.prompt = (b, c) => {
    c.innerHTML = `<div class="bar"><div class="txt"><span class="t"></span><span class="cur"></span></div><div class="go"><svg width="40%" viewBox="0 0 40 40"><path d="M20 32V9M10 18l10-10 10 10" fill="none" stroke="var(--on-primary)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg></div></div>
      ${b.answer ? `<div class="ans"><div class="l">${esc(b.answer_label || "ANSWER")}</div><div class="v">${esc(b.answer)}</div></div>` : ""}`;
    tl.fromTo($(".bar", c), { opacity: 0, scale: 0.9 }, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(1.8)" }, q(b.at + 0.1));
    const T = b.text || "", keys = b._keys || [];
    typeInto($(".t", c), T, keys);
    const done = keys.length ? keys[keys.length - 1] : b.at + 0.5, dur = done - b.at - 0.4;
    tl.to($(".go", c), { scale: 0.85, duration: 0.08, yoyo: true, repeat: 1 }, q(done + 0.2));
    if (b.answer) tl.fromTo($(".ans", c), { opacity: 0, y: -20 * U }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }, q(b.answer_at || b.at + 0.7 + dur));
  };
  K.timeline = (b, c) => {
    const ticks = b.ticks || ["NOW", "", "", "", "LATER"];
    c.innerHTML = `<div class="panel"><div class="ruler">${ticks.map((t) => `<span>${esc(t)}</span>`).join("")}</div>${(b.tracks || []).map((tr) => `<div class="trk">${tr.map((cl) => `<div class="clp${cl.alt ? " alt" : ""}" style="left:${cl.from}%" data-w="${cl.to - cl.from}">${esc(cl.text)}</div>`).join("")}</div>`).join("")}<div class="head"></div></div>`;
    const panel = $(".panel", c), pw = panel.clientWidth - 60 * U;
    let k = 0;
    (b.tracks || []).forEach((tr) => tr.forEach((cl) => {
      const node = $$(".clp", c)[k++];
      tl.to(node, { width: (cl.to - cl.from) + "%", duration: 0.5, ease: "back.out(1.3)" }, q(cl.at != null ? cl.at : b.at + 0.4 + k * 0.4));
    }));
    tl.fromTo($(".head", c), { x: 0 }, { x: pw, duration: Math.max(1, b.until - b.at - 0.6), ease: "none" }, q(b.at + 0.3));
  };
  K.image = (b, c, root) => {
    if (b.full) root.classList.add("full");
    const isVid = /\.(mp4|mov|webm)$/i.test(b.src || "");
    c.innerHTML = `<div class="media">${isVid ? `<video src="${esc(b.src)}" muted playsinline></video>` : `<img src="${esc(b.src)}" alt="">`}</div>${b.caption ? `<div class="sub">${esc(b.caption)}</div>` : ""}`;
    tl.fromTo($(".media > *", c), { scale: 1.12 }, { scale: 1, duration: Math.max(1, b.until - b.at), ease: "none" }, q(b.at));
  };
  K.broll = (b, c, root) => {
    // the <video> is a static layer written by build.py in an untimed wrapper #bw<i>; it gets the same
    // wipe as every page, a slow push-in, and an optional label on the (transparent) beat div
    root.classList.remove("dots");
    const wrap = document.getElementById("bw" + root.id.slice(1));
    if (wrap) {
      tl.set(wrap, { clipPath: "inset(0 0 0 100%)" }, 0);
      tl.fromTo(wrap, { clipPath: "inset(0 0 0 100%)" }, { clipPath: "inset(0 0 0 0%)", duration: 0.32, ease: "power4.out" }, q(b.at));
      tl.to(wrap, { clipPath: "inset(0 100% 0 0)", duration: 0.28, ease: "power3.in" }, q(b.until - 0.28));
      tl.fromTo($(".bv", wrap), { scale: 1.0 }, { scale: 1.06, duration: Math.max(1, b.until - b.at), ease: "none" }, q(b.at));
    }
    if (b.caption) {
      const tag = el("div", "btag mono", esc(b.caption)); root.appendChild(tag);
      tl.fromTo(tag, { opacity: 0, y: -16 * U }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out" }, q(b.at + 0.35));
    }
  };
  /* ---------- shared: real typing driven by build.py's per-character key times ---------- */
  function typeInto(node, text, keys, onChange) {
    if (!keys || !keys.length) { node.textContent = text; return; }
    const o = { p: 0 };
    let last = -1;
    tl.to(o, { p: 1, duration: Math.max(0.05, keys[keys.length - 1] - keys[0] + 0.05), ease: "none", onUpdate: () => {
      const t = tl.time(); let n = 0;
      while (n < keys.length && keys[n] <= t + 1e-4) n++;
      if (n !== last) { last = n; node.textContent = text.slice(0, n); if (onChange) onChange(n); }
    } }, q(keys[0]));
  }
  function blink(caret, from, to) {  // finite, seek-safe caret blink
    const n = Math.max(1, Math.floor((to - from) / 0.5));
    tl.fromTo(caret, { opacity: 1 }, { opacity: 0, duration: 0.25, ease: "steps(1)", yoyo: true, repeat: n * 2 - 1 }, q(from));
  }
  const CURSOR = '<svg class="cursor" viewBox="0 0 24 24"><path d="M4 2 L4 19 L8.6 14.8 L11.6 21.6 L14.4 20.4 L11.4 13.6 L17.6 13.6 Z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  const pos = (elm, root, fx, fy) => { const r = elm.getBoundingClientRect(), rr = root.getBoundingClientRect(); return { x: r.left - rr.left + r.width * fx, y: r.top - rr.top + r.height * fy }; };
  const GLOGO = '<span style="color:#4285F4">G</span><span style="color:#EA4335">o</span><span style="color:#FBBC05">o</span><span style="color:#4285F4">g</span><span style="color:#34A853">l</span><span style="color:#EA4335">e</span>';
  const MAG = '<svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="#9aa0a6" stroke-width="2.2"/><path d="M15.5 15.5 L21 21" stroke="#9aa0a6" stroke-width="2.2" stroke-linecap="round"/></svg>';
  const MIC = '<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3" fill="#4285F4"/><path d="M6 11a6 6 0 0 0 12 0" fill="none" stroke="#34A853" stroke-width="2"/><path d="M12 17v4" stroke="#EA4335" stroke-width="2"/><path d="M9 21h6" stroke="#FBBC05" stroke-width="2"/></svg>';

  /* ---------- Google-style search: cursor, real typing, autocomplete, results, highlight ---------- */
  K.search = (b, c, root) => {
    root.classList.remove("dots");
    const text = b.text || "", keys = b._keys || [];
    const sugg = (b.suggestions || [text, text + " 2026", text + " statistics", text + " explained"]).slice(0, 4);
    const res = b.results || [{ site: "Wikipedia", url: "en.wikipedia.org", title: text.replace(/^./, (m) => m.toUpperCase()), snippet: text }];
    root.insertAdjacentHTML("afterbegin", '<div class="ui-bg"><i class="a"></i><i class="b"></i><i class="c"></i></div>');
    c.style.display = "none";
    const win = el("div", "sx-win");
    win.innerHTML = `<div class="sx-bar"><span class="d" style="background:#ff5f57"></span><span class="d" style="background:#febc2e"></span><span class="d" style="background:#28c840"></span>
        <div class="sx-url"><svg width="1em" height="1em" viewBox="0 0 24 24"><rect x="5" y="10" width="14" height="10" rx="2" fill="#5f6368"/><path d="M8 10V7a4 4 0 0 1 8 0v3" fill="none" stroke="#5f6368" stroke-width="2"/></svg>google.com</div></div>
      <div class="sx-body"><div class="sx-home"><div class="sx-logo">${GLOGO}</div>
        <div class="sx-box">${MAG}<div class="sx-q"><span class="t"></span><i class="caret"></i></div>${MIC}</div>
        <div class="sx-sugg">${sugg.map(() => `<div class="row">${MAG}<span></span></div>`).join("")}</div></div>
        <div class="sx-res"><div class="hd"><div class="lg">${GLOGO}</div><div class="pill">${esc(text)}</div></div>
          <div class="tabs"><span class="on">All</span><span>News</span><span>Images</span><span>Videos</span><span>More</span></div>
          ${res.slice(0, 3).map((r) => `<div class="card"><div class="site"><div class="fav">${esc((r.site || "?")[0])}</div><div><div>${esc(r.site || "")}</div><div class="url">${esc(r.url || "")}</div></div></div>
            <div class="tt">${esc(r.title || "")}</div><div class="sn">${esc(r.snippet || "")}</div></div>`).join("")}</div></div>`;
    root.appendChild(win);
    if (b.highlight && b.highlight.text) {  // wrap the phrase to highlight in the first matching snippet
      const sn = $$(".sn", win).find((s) => s.textContent.includes(b.highlight.text));
      if (sn) sn.innerHTML = esc(sn.textContent).replace(esc(b.highlight.text), `<mark>${esc(b.highlight.text)}</mark>`);
    }
    root.insertAdjacentHTML("beforeend", CURSOR);
    const cur = $(".cursor", root), box = $(".sx-box", win), rows = $$(".sx-sugg .row span", win), dd = $(".sx-sugg", win);
    // camera: window rises in, slow push while typing
    tl.fromTo(win, { y: 80 * U, scale: 0.92, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: 0.45, ease: "power3.out" }, q(b.at + 0.05));
    tl.to(win, { scale: 1.05, duration: Math.max(0.5, b._enter - b.at - 0.5), ease: "sine.inOut" }, q(b.at + 0.5));
    // cursor glides to the box and clicks
    const p0 = pos(box, root, 0.55, 0.5);
    tl.fromTo(cur, { x: R.W * 0.9, y: R.H * 0.9, opacity: 0 }, { x: p0.x, y: p0.y, opacity: 1, duration: 0.5, ease: "power2.inOut" }, q(b.at + 0.1));
    tl.to(cur, { scale: 0.82, duration: 0.07, yoyo: true, repeat: 1 }, q(b.at + 0.55));
    tl.to(box, { boxShadow: "0 2px 14px rgba(26,115,232,0.45)", duration: 0.2 }, q(b.at + 0.55));
    tl.to(cur, { opacity: 0, duration: 0.25 }, q(b.at + 0.8));
    // typing + live autocomplete (completion in bold, like the real thing)
    blink($(".caret", win), b.at + 0.55, keys.length ? keys[0] : b.at + 0.8);
    typeInto($(".sx-q .t", win), text, keys, (n) => {
      const typed = text.slice(0, n);
      dd.style.opacity = n >= 3 ? 1 : 0;
      rows.forEach((r, i) => {
        const s = sugg[i] || "";
        r.innerHTML = s.toLowerCase().startsWith(typed.toLowerCase()) ? esc(s.slice(0, n)) + "<b>" + esc(s.slice(n)) + "</b>" : "<b>" + esc(s) + "</b>";
      });
    });
    // Enter: home page out, results in, camera pushes toward the top result
    tl.to($(".sx-home", win), { opacity: 0, y: -40 * U, duration: 0.25, ease: "power2.in" }, q(b._enter));
    tl.fromTo($(".sx-res", win), { opacity: 0 }, { opacity: 1, duration: 0.25 }, q(b._results));
    tl.fromTo($$(".sx-res .card", win), { opacity: 0, y: 30 * U }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out", stagger: 0.12 }, q(b._results + 0.1));
    tl.to(win, { scale: 1.16, duration: Math.max(0.6, b.until - b._results - 0.4), ease: "sine.inOut" }, q(b._results + 0.3));
    if (b.highlight && $("mark", win)) tl.to($("mark", win), { backgroundSize: "100% 100%", duration: 0.45, ease: "power2.out" }, q(b.highlight.at || b._results + 1.0));
  };

  /* ---------- AI chat app: type the question, send, typing dots, streamed reply / agent steps ---------- */
  const CHECK = '<svg viewBox="0 0 24 24"><path d="M5 12.5 L10 17 L19 7" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  K.chat = (b, c, root) => {
    root.classList.remove("dots");
    c.style.display = "none";
    root.insertAdjacentHTML("afterbegin", '<div class="ui-bg"><i class="a"></i><i class="b"></i><i class="c"></i></div>');
    const app = el("div", "ch-app");
    const words = (b.reply || "").split(/\s+/).filter(Boolean);
    app.innerHTML = `<div class="ch-hd"><div class="ch-av"><svg viewBox="0 0 24 24"><path d="M12 2l2.2 6.3L20 10l-5.8 1.7L12 18l-2.2-6.3L4 10l5.8-1.7z" fill="#fff"/></svg></div>
        <div><div class="ch-name">${esc(b.assistant || "AI Assistant")}</div><div class="ch-st">● online</div></div></div>
      <div class="ch-msgs"><div class="ch-u">${esc(b.user || "")}</div>
        <div class="ch-a"><div class="ch-dots"><i></i><i></i><i></i></div><div class="ch-txt">${words.map((w) => `<span style="opacity:0">${esc(w)} </span>`).join("")}</div>
          ${(b.steps || []).map((s) => `<div class="ch-step"><div class="s">${CHECK}</div><span>${esc(s.text)}</span></div>`).join("")}</div></div>
      <div class="ch-in"><div class="ch-field"><span class="ph">Message ${esc(b.assistant || "AI Assistant")}...</span><span class="t"></span><i class="caret"></i></div>
        <div class="ch-send"><svg viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg></div></div>`;
    root.appendChild(app);
    root.insertAdjacentHTML("beforeend", CURSOR);
    const keys = b._keys || [], field = $(".ch-field .t", app), ph = $(".ch-field .ph", app), cur = $(".cursor", root);
    tl.fromTo(app, { y: 80 * U, scale: 0.94, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: 0.45, ease: "power3.out" }, q(b.at + 0.05));
    if (keys.length) tl.set(ph, { display: "none" }, q(keys[0]));
    blink($(".ch-field .caret", app), b.at + 0.3, b._send);
    typeInto(field, b.user || "", keys);
    // the cursor arrives just in time to press send
    const ps = pos($(".ch-send", app), root, 0.5, 0.55);
    tl.fromTo(cur, { x: R.W * 0.9, y: R.H * 0.95, opacity: 0 }, { x: ps.x, y: ps.y, opacity: 1, duration: 0.45, ease: "power2.inOut" }, q(b._send - 0.5));
    tl.to(cur, { scale: 0.82, duration: 0.07, yoyo: true, repeat: 1 }, q(b._send - 0.04));
    tl.to(cur, { opacity: 0, duration: 0.25 }, q(b._send + 0.35));
    tl.set(field, { textContent: "" }, q(b._send));
    tl.fromTo($(".ch-u", app), { opacity: 0, y: 60 * U, scale: 0.9 }, { opacity: 1, y: 0, scale: 1, duration: 0.35, ease: "back.out(1.6)" }, q(b._send));
    // assistant is typing...
    tl.fromTo($(".ch-a", app), { opacity: 0, y: 20 * U }, { opacity: 1, y: 0, duration: 0.3 }, q(b._send + 0.25));
    const dotsN = Math.max(1, Math.floor((b._reply - b._send - 0.25) / 0.45));
    tl.fromTo($$(".ch-dots i", app), { y: 0 }, { y: -8 * U, duration: 0.15, yoyo: true, repeat: dotsN * 2 - 1, stagger: 0.1, ease: "sine.inOut" }, q(b._send + 0.3));
    tl.set($(".ch-dots", app), { display: "none" }, q(b._reply));
    $$(".ch-txt span", app).forEach((s, i) => tl.to(s, { opacity: 1, duration: 0.08 }, q(b._reply + i * 0.06)));
    $$(".ch-step", app).forEach((st, i) => {
      const t = b.steps[i].at;
      tl.fromTo(st, { opacity: 0, x: -20 * U }, { opacity: 1, x: 0, duration: 0.25 }, q(Math.max(b._reply, t - 0.5)));
      tl.to($(".s", st), { rotate: 360, duration: 0.5, ease: "none" }, q(Math.max(b._reply, t - 0.5)));
      tl.to($(".s", st), { borderColor: "#16a34a", backgroundColor: "#16a34a", duration: 0.15 }, q(t));
      tl.to($(".s svg", st), { opacity: 1, duration: 0.15 }, q(t));
    });
  };
  K.quote = (b, c) => {
    c.innerHTML = `<div class="q serif">“${esc(b.text)}”</div>${b.by ? `<div class="by">${esc(b.by)}</div>` : ""}`;
    tl.from($(".q", c), { opacity: 0, y: 40 * U, duration: 0.5, ease: "power3.out" }, q(b.at + 0.2));
  };
  K.comment = (b, c) => {
    c.innerHTML = (b.items || [{ handle: b.handle, text: b.text, at: b.at + 0.3 }]).map((i) => `<div class="bubble"><div class="av">${esc((i.handle || "@")[1] || "@").toUpperCase()}</div><div><div class="who">${esc(i.handle || "")}</div><div class="msg">${esc(i.text)}</div></div></div>`).join("");
    $$(".bubble", c).forEach((n, k) => pop(n, (b.items && b.items[k].at) || b.at + 0.3 + k * 0.6));
  };

  function page(b, i, root) {
    root.classList.add("page", "dots", b.kind);
    if (b.label && b.kind !== "title") root.appendChild(el("div", "lbl", esc(b.label)));
    const c = el("div", "content"); root.appendChild(c);
    (K[b.kind] || K.quote)(b, c, root);
    if (b.kind === "title") {
      tl.fromTo(root, { clipPath: "inset(50% 0 50% 0)" }, { clipPath: "inset(0% 0 0% 0)", duration: 0.32, ease: "power4.out" }, q(b.at));
      tl.to(root, { clipPath: "inset(50% 0 50% 0)", duration: 0.25, ease: "power3.in" }, q(b.until - 0.25));
    } else {
      tl.fromTo(root, { clipPath: "inset(0 0 0 100%)" }, { clipPath: "inset(0 0 0 0%)", duration: 0.32, ease: "power4.out" }, q(b.at));
      tl.to(root, { clipPath: "inset(0 100% 0 0)", duration: 0.28, ease: "power3.in" }, q(b.until - 0.28));
    }
    if (b.until < END - 0.1) tl.fromTo("#vwrap", { scale: 1.07 }, { scale: 1, duration: 0.5, ease: "power3.out" }, q(b.until));
  }

  /* ---------------- build all beats ---------------- */
  R.beats.forEach((b, i) => {
    const root = document.getElementById("b" + i);
    if (b.type === "page") {
      page(b, i, root);
      if (b.kind !== "broll") pageRanges.push([b.at, b.until]);  // over footage, captions keep their normal style
      if (b.kind === "title" || b.hide_captions) hide.push([b.at, b.until]);
    }
    else { words(b, root); if (b.hide_captions !== false) hide.push([b.at, b.until]); }
  });

  /* ---------------- captions ---------------- */
  const C = R.captions;
  if (C.style !== "none") {
    const W = R.words, caps = document.getElementById("caps"), phrases = []; let cur = [];
    W.forEach((w, i) => {
      if (w[0] === "%" && cur.length) { cur[cur.length - 1] = [cur[cur.length - 1][0] + "%", cur[cur.length - 1][1], w[2]]; return; }
      cur.push(w);
      const nx = W[i + 1], gap = nx ? nx[1] - w[2] : 9, chars = cur.map((x) => x[0]).join(" ").length;
      if (/[,.?!;:]$/.test(w[0]) || gap > 0.6 || cur.length >= (C.max_words || 3) || chars > (C.max_chars || 17) || !nx) { phrases.push(cur); cur = []; }
    });
    const upper = C.case === "upper";
    phrases.forEach((p, pi) => {
      const t0 = p[0][1], last = p[p.length - 1][2];
      const t1 = phrases[pi + 1] ? Math.min(phrases[pi + 1][0][1], last + 0.6) : Math.min(last + 0.5, END - 0.05);
      if (inR(t0 + 0.05, hide)) return;
      const onPage = inR(t0 + 0.05, pageRanges);
      const ph = el("div", "phrase cap-" + C.style + (onPage ? " on-page" : ""));
      ph.style.top = (onPage ? R.capsPageY : R.capsY) + "px";
      const spans = p.map((w) => { const s = el("span", "w"); let t = w[0].replace(/[,.;:]$/, ""); s.textContent = upper ? t.toUpperCase() : t; ph.appendChild(s); return s; });
      caps.appendChild(ph);
      tl.set(ph, { opacity: 1 }, q(t0 - 0.04));
      tl.fromTo(spans, { opacity: 0, y: 26 * U, scale: 0.8 }, { opacity: 1, y: 0, scale: 1, duration: 0.18, ease: "back.out(2.4)", stagger: 0.035 }, q(t0 - 0.04));
      if (C.style !== "clean") p.forEach((w, k) => {
        const off = p[k + 1] ? p[k + 1][1] : Math.min(w[2] + 0.25, t1);
        const rest = getComputedStyle(spans[k]);
        const on = C.style === "bold-box" ? { backgroundColor: "var(--primary)", color: "var(--on-primary)", webkitTextStroke: "0px rgba(0,0,0,0)", textShadow: "none" }
                                           : { color: onPage ? "var(--primary)" : "var(--hi)" };
        const off_ = C.style === "bold-box" ? { backgroundColor: "rgba(0,0,0,0)", color: rest.color, webkitTextStroke: rest.webkitTextStroke, textShadow: rest.textShadow } : { color: rest.color };
        tl.set(spans[k], on, q(w[1]));
        tl.set(spans[k], off_, q(Math.max(off, w[1] + 1 / FPS)));
      });
      tl.set(ph, { opacity: 0 }, q(t1));
    });
  }

  window.__timelines = window.__timelines || {};
  window.__timelines["reel"] = tl;
})();
