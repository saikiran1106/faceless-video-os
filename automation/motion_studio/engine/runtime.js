// Motion runtime. Everything visible is a pure function of t (seek-able):
// render(t) reads only window.IM_DATA and t, never previous frames, timers or randomness.
(() => {
  const D = window.IM_DATA;
  const $ = (id) => document.getElementById(id);
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const lerp = (a, b, k) => a + (b - a) * k;
  const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 4); // long-tailed arrival
  const easeInOut = (x) => { x = clamp(x); return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; };

  // Closed-form step response of a damped spring (0 -> 1). zeta 1 never bounces, 0.7-0.85 reads premium.
  function spring(tau, zeta, freq) {
    if (tau <= 0) return 0;
    const w0 = 2 * Math.PI * freq;
    if (zeta >= 1) return 1 - Math.exp(-w0 * tau) * (1 + w0 * tau);
    const wd = w0 * Math.sqrt(1 - zeta * zeta);
    return 1 - Math.exp(-zeta * w0 * tau) * (Math.cos(wd * tau) + (zeta * w0 / wd) * Math.sin(wd * tau));
  }
  // A value that changes target many times = initial + sum(change * spring(t - changeTime)).
  function track(keys, get, t, zeta, freq, perKey) {
    let v = get(keys[0]);
    for (let i = 1; i < keys.length; i++) {
      const d = get(keys[i]) - get(keys[i - 1]);
      if (!d) continue;
      const p = perKey ? perKey(keys[i], keys[i - 1], i) : [zeta, freq];
      v += d * spring(t - keys[i].t, p[0], p[1]);
    }
    return v;
  }
  const rgba = (c) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${clamp(c[3]).toFixed(3)})`;

  // ---------- hero: one shape, never cut ----------
  // Edges ride separate springs: the edge facing the direction of travel leads, the other trails, so the
  // shape stretches ahead of itself and settles.
  const H = D.hero;
  function edge(name, axisSign) {
    return (t) => track(H.keys, (k) => k[name], t, 0, 0, (k, prev) => {
      const dc = (k.c[axisSign.axis] - prev.c[axisSign.axis]) * axisSign.dir;
      const lead = k.lead || H.lead, trail = k.trail || H.trail;
      if (Math.abs(dc) < 2) return [H.zeta, (lead[1] + trail[1]) / 2];
      return dc > 0 ? [lead[0], lead[1]] : [trail[0], trail[1]];
    });
  }
  const eL = edge("l", { axis: 0, dir: -1 }), eR = edge("r", { axis: 0, dir: 1 });
  const eT = edge("tp", { axis: 1, dir: -1 }), eB = edge("b", { axis: 1, dir: 1 });
  function drawHero(t) {
    const el = $("hero");
    const l = eL(t), r = eR(t), tp = eT(t), b = eB(t);
    const w = Math.max(0, r - l), h = Math.max(0, b - tp);
    const rad = Math.min(track(H.keys, (k) => k.rad, t, 0.9, 2.4), w / 2, h / 2);
    const col = (key) => [0, 1, 2, 3].map((i) => track(H.keys, (k) => k[key][i], t, 1, 3.2));
    el.style.transform = `translate(${l.toFixed(2)}px,${tp.toFixed(2)}px)`;
    el.style.width = w.toFixed(2) + "px";
    el.style.height = h.toFixed(2) + "px";
    el.style.borderRadius = rad.toFixed(2) + "px";
    el.style.background = rgba(col("fill"));
    el.style.boxShadow = `inset 0 0 0 ${track(H.keys, (k) => k.sw, t, 1, 3.2).toFixed(2)}px ${rgba(col("stroke"))}`;
  }

  // ---------- cursor ----------
  const C = D.cursor;
  function cursorAt(t) {
    if (!C.keys.length) return null;
    return [track(C.keys, (k) => k.x, t, 0.92, 1.7), track(C.keys, (k) => k.y, t, 0.92, 1.7)];
  }
  function drawCursor(t) {
    const el = $("cursor");
    const p = cursorAt(t);
    let vis = 0;
    for (const [a, b] of C.show) vis = Math.max(vis, clamp((t - a) / 0.2) * clamp((b - t) / 0.2));
    if (!p || vis <= 0) { el.style.opacity = 0; return; }
    let press = 0;
    for (const c of C.clicks) press = Math.max(press, clamp(1 - Math.abs(t - c) / 0.09));
    for (const [a, b] of C.holds) if (t >= a && t <= b) press = 1;
    el.style.opacity = vis.toFixed(3);
    el.style.transform = `translate(${p[0].toFixed(2)}px,${p[1].toFixed(2)}px) scale(${(1 - 0.14 * press).toFixed(3)})`;
  }

  // ---------- camera ----------
  const SHAKES = D.items.filter((it) => it.kind === "shake");
  function shakeAt(t) {
    let x = 0, y = 0, r = 0;
    for (const sh of SHAKES) {
      const age = t - sh.in;
      if (age < 0 || t > sh.out) continue;
      const e = Math.exp(-sh.decay * age) * clamp((sh.out - t) / 0.08);
      x += sh.amp * e * Math.sin(age * 71.3 + 0.4);
      y += sh.amp * 0.8 * e * Math.sin(age * 57.1 + 1.9);
      r += sh.rot * e * Math.sin(age * 43.7 + 0.9);
    }
    return [x, y, r];
  }
  function drawCam(t) {
    const K = D.cam;
    const [sx, sy, sr] = shakeAt(t);
    if (!K.length && !SHAKES.length) return;
    const s = K.length ? track(K, (k) => k.s, t, 1, 0.9) : 1, x = K.length ? track(K, (k) => k.x, t, 1, 0.9) : 0, y = K.length ? track(K, (k) => k.y, t, 1, 0.9) : 0;
    $("cam").style.transform = `translate(${(x + sx).toFixed(2)}px,${(y + sy).toFixed(2)}px) rotate(${sr.toFixed(3)}deg) scale(${s.toFixed(4)})`;
  }

  // ---------- items ----------
  // Entrance and exit factors: 0 hidden, 1 settled. Exits are ~half as long as entrances.
  const inK = (it, t, dur = 0.3) => clamp((t - it.in) / dur);
  const outK = (it, t, dur = 0.2) => clamp((it.out - t) / dur);

  function drawText(it, t) {
    const box = $(it.id);
    box.style.opacity = 1;
    if (it.fx === "hold") { box.style.opacity = t >= it.in && t < it.out ? 1 : 0; return; }  // credits: no motion
    if (it.fx === "kara") {
      // karaoke caption: the card pops in, then the word being spoken lights up in an orange chip
      const sc = lerp(0.88, 1, spring(t - it.in, 0.75, 3.6));
      box.style.opacity = (clamp((t - it.in) / 0.06) * outK(it, t, 0.12)).toFixed(3);
      box.style.transform = `translate(${it.tx},-50%) scale(${(t < it.in ? 0.88 : sc).toFixed(4)})`;
      const ws = it._w || (it._w = [...box.querySelectorAll(".w")]);
      ws.forEach((w, i) => {
        const on = t >= it.ws[i] && (i + 1 >= it.ws.length ? t < it.out : t < it.ws[i + 1]);
        const k = on ? spring(t - it.ws[i], 0.6, 4.2) : 0;
        w.classList.toggle("on", on);
        w.style.transform = `scale(${(1 + 0.1 * k).toFixed(3)})`;
        w.style.opacity = t >= it.ws[i] ? 1 : 0.55;
      });
      return;
    }
    if (it.fx === "slam") {
      // lands from 3x with a hard spring, an RGB split that collapses, and a small counter-rotation
      const k = spring(t - it.in, 0.5, 3.4);
      const sc = t < it.in ? 3 : lerp(3, 1, k);
      const a = clamp((t - it.in) / 0.05) * outK(it, t, 0.14);
      const d = Math.max(0, 16 * (1 - clamp((t - it.in) / 0.32)));
      box.style.opacity = a.toFixed(3);
      box.style.transform = `translate(${it.tx},-50%) scale(${sc.toFixed(4)}) rotate(${(-5 * (1 - k)).toFixed(2)}deg)`;
      box.style.textShadow = d > 0.2 ? `${d.toFixed(1)}px 0 0 rgba(255,40,90,.85), ${(-d).toFixed(1)}px 0 0 rgba(0,220,255,.85), 0 6px 24px rgba(0,0,0,.7)` : "";
      box.style.filter = t - it.in < 0.08 ? `blur(${(10 * (1 - (t - it.in) / 0.08)).toFixed(2)}px)` : "none";
      return;
    }
    if (it.fx === "glitch") {
      // arrives broken: stepped flicker, horizontal tearing and colour split for 0.4 s, then locks
      const age = t - it.in, g = clamp(1 - age / 0.4);
      const step = Math.floor(age * 30);
      const on = age >= 0 && (g === 0 || step % 4 !== 1);
      const jx = g * 26 * Math.sin(step * 2.399 + 0.7), sk = g * 14 * Math.sin(step * 1.618 + 2.1);
      box.style.opacity = ((on ? 1 : 0.15) * clamp(age / 0.03) * outK(it, t, 0.14)).toFixed(3);
      box.style.transform = `translate(calc(${it.tx} + ${jx.toFixed(1)}px),-50%) skewX(${sk.toFixed(2)}deg)`;
      const d = 9 * g;
      box.style.textShadow = d > 0.2 ? `${d.toFixed(1)}px 0 0 rgba(255,40,90,.9), ${(-d).toFixed(1)}px 0 0 rgba(0,220,255,.9)` : "";
      return;
    }
    if (it.fx === "track") {
      // zooms through the screen: huge, blurred and wide-tracked, then snaps tight
      const k = spring(t - it.in, 0.78, 2.6);
      const sc = t < it.in ? 2.6 : lerp(2.6, 1, k);
      const a = clamp((t - it.in) / 0.12) * outK(it, t, 0.14);
      box.style.opacity = a.toFixed(3);
      box.style.letterSpacing = `${lerp(0.45, -0.02, k).toFixed(3)}em`;
      box.style.transform = `translate(${it.tx},-50%) scale(${sc.toFixed(4)})`;
      box.style.filter = k < 0.97 ? `blur(${(14 * (1 - k)).toFixed(2)}px)` : "none";
      return;
    }
    if (it.fx === "stamp" || it.fx === "pop") {
      // the whole line lands at once: scales down onto the frame (stamp) or rises a touch (pop)
      const k0 = it.fx === "stamp" ? 1.45 : 0.86;
      const sc = lerp(k0, 1, spring(t - it.in, it.fx === "stamp" ? 0.62 : 0.75, it.fx === "stamp" ? 3.2 : 3.6));
      const a = clamp((t - it.in) / 0.08) * outK(it, t, 0.14);
      box.style.opacity = a.toFixed(3);
      box.style.transform = `translate(${it.tx},-50%) scale(${(t < it.in ? k0 : sc).toFixed(4)})`;
      box.style.filter = a < 1 && t > it.in + 0.05 ? `blur(${(6 * (1 - a)).toFixed(2)}px)` : "none";
      return;
    }
    const words = it._w || (it._w = [...box.querySelectorAll(".w")]);
    const n = words.length;
    words.forEach((w, i) => {
      let a = 1, blur = 0, ink = 1;
      if (it.fx === "words") { const k = easeOut((t - it.in - i * 0.067) / 0.16); a = k; blur = 6 * (1 - k); }
      else if (it.fx === "ink") { const k = easeOut((t - it.in - i * 0.085) / 0.2); a = 0.25 + 0.75 * k; ink = k; }
      else if (it.fx === "line") { const k = easeOut((t - it.in) / 0.2); a = k; blur = 8 * (1 - k); }
      else if (it.fx === "drop") {
        // each word falls in from above with a tilt and lands with a little overshoot
        const k = spring(t - it.in - i * 0.07, 0.48, 3.0); a = clamp((t - it.in - i * 0.07) / 0.06);
        w.style.transform = `translateY(${(-140 * (1 - k)).toFixed(1)}px) rotate(${((i % 2 ? -14 : 14) * (1 - k)).toFixed(2)}deg)`;
      }
      else if (it.fx === "rise") { const k = easeOut((t - it.in - i * 0.05) / 0.35); a = k; blur = 4 * (1 - k); }
      else a = t >= it.in ? 1 : 0;
      // exit word by word, blur-out
      const ko = clamp((it.out - t - (n - 1 - i) * 0.03) / 0.16);
      a *= ko; blur += 8 * (1 - ko);
      w.style.opacity = a.toFixed(3);
      w.style.filter = blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : "none";
      if (it.fx === "ink") w.style.color = w.classList.contains("acc") ? "" : `rgba(255,255,255,${(0.3 + 0.7 * ink).toFixed(3)})`;
    });
  }

  function drawCode(it, t) {
    const el = $(it.id);
    const chars = it._c || (it._c = [...el.querySelectorAll(".ch")]);
    const shown = Math.floor(Math.max(0, t - it.in) * it.cps);
    const ko = outK(it, t);
    el.style.opacity = (ko * clamp((t - it.in + 0.15) / 0.15)).toFixed(3);
    el.style.filter = ko < 1 ? `blur(${(8 * (1 - ko)).toFixed(2)}px)` : "none";
    chars.forEach((c, i) => { c.style.opacity = i < shown ? 1 : 0; });
    const caret = $(it.id + "-caret");
    const last = chars[Math.min(shown, chars.length) - 1];
    if (caret) {
      const typing = shown < chars.length;
      caret.style.opacity = typing && t >= it.in ? 1 : 0;
      if (last) caret.style.transform = `translate(${(last.offsetLeft + last.offsetWidth).toFixed(1)}px,${last.offsetTop}px)`;
    }
  }

  // Number roll: eases from->to; digits blur slightly while rolling.
  function drawCount(it, t) {
    const el = $(it.id);
    const k = easeOut((t - it.roll[0]) / it.roll[1]);
    const v = lerp(it.from, it.to, k);
    el.querySelector(".num").textContent = v.toFixed(it.dec);
    const ki = inK(it, t, 0.2), ko = outK(it, t);
    el.style.opacity = (ki * ko).toFixed(3);
    const moving = k > 0 && k < 1 ? 1 - k : 0;
    el.style.filter = moving > 0.02 || ko < 1 ? `blur(${(2.5 * moving + 8 * (1 - ko)).toFixed(2)}px)` : "none";
  }

  // Scrubber: the knob is direct manipulation. While the cursor is held it follows the cursor's x;
  // after release it stays where it was let go.
  function scrubValue(it, t) {
    let v = it.v0;
    for (const [a, b] of C.holds) {
      if (b < it.in || a > it.out) continue;
      const tt = Math.min(t, b);
      if (t < a) break;
      const p = cursorAt(tt);
      v = clamp((p[0] - it.track[0]) / it.track[2]);
    }
    return v;
  }
  function drawScrub(it, t) {
    const el = $(it.id);
    const ki = easeOut(inK(it, t, 0.3)), ko = outK(it, t);
    el.style.opacity = (ki * ko).toFixed(3);
    el.style.filter = ko < 1 ? `blur(${(8 * (1 - ko)).toFixed(2)}px)` : "none";
    const v = scrubValue(it, t);
    $(it.id + "-fill").style.width = (v * it.track[2]).toFixed(2) + "px";
    $(it.id + "-knob").style.transform = `translate(${(v * it.track[2]).toFixed(2)}px,0)`;
    const sec = v * it.span;
    $(it.id + "-read").innerHTML = `t = <b>${sec.toFixed(2)}</b> s &nbsp;·&nbsp; frame ${Math.round(sec * D.fps)}`;
    // The preview is itself a function of v: same t, same picture.
    const pv = $(it.id + "-pv");
    if (pv) {
      const ang = v * 300, rad = it.pv.r * (0.35 + 0.65 * Math.sin(v * Math.PI * 0.5 + 0.2));
      const x = it.pv.cx + Math.cos((v * 1.6 - 0.25) * Math.PI) * rad, y = it.pv.cy + Math.sin((v * 1.6 - 0.25) * Math.PI) * rad * 0.8;
      pv.style.transform = `translate(${(x - it.pv.s / 2).toFixed(2)}px,${(y - it.pv.s / 2).toFixed(2)}px) rotate(${ang.toFixed(1)}deg)`;
      pv.style.borderRadius = (it.pv.s * (0.12 + 0.38 * v)).toFixed(1) + "px";
      pv.style.opacity = ki * ko;
    }
  }

  function drawFade(it, t) {
    const el = $(it.id);
    const ki = easeOut(inK(it, t, it.inDur || 0.3)), ko = outK(it, t);
    el.style.opacity = (ki * ko).toFixed(3);
    const blur = 8 * (1 - ki) + 8 * (1 - ko);
    el.style.filter = blur > 0.05 ? `blur(${blur.toFixed(2)}px)` : "none";
    if (it.scaleIn) el.style.transform = `scale(${lerp(it.scaleIn, 1, spring(t - it.in, 0.8, 2.2)).toFixed(4)})`;
  }

  // Waveform: bar heights follow the real audio envelope (sampled per frame at build time), each bar
  // shaped by a fixed function of its index and t, so the same t always draws the same bars.
  function drawWave(it, t) {
    const el = $(it.id);
    const ki = easeOut(inK(it, t, 0.25)), ko = outK(it, t);
    el.style.opacity = (ki * ko).toFixed(3);
    const bars = it._b || (it._b = [...el.querySelectorAll(".bar")]);
    const f = Math.max(0, Math.min(it.env.length - 1, Math.round((t - it.env0) * D.fps)));
    const e = it.env[f] || 0;
    bars.forEach((b, i) => {
      const shape = 0.3 + 0.7 * Math.abs(Math.sin(i * 1.7 + t * 7.3 + i * i * 0.31));
      b.style.transform = `scaleY(${Math.max(0.08, e * shape).toFixed(3)})`;
    });
  }

  // Punch-ins on footage: the wrapper (never the timed video) scales on its own spring.
  function drawZoom(it, t) {
    const s = track(it.keys, (k) => k.s, t, 0.72, 2.4);
    $(it.id).style.transform = `scale(${s.toFixed(4)})`;
  }
  // Flash frame: full brightness on the cut, gone in 0.18 s.
  function drawFlash(it, t) {
    $(it.id).style.opacity = t >= it.in ? Math.max(0, 1 - (t - it.in) / 0.18).toFixed(3) : 0;
  }

  // Sound rings: each burst sends n rings outward; radius and fade are functions of the ring's age.
  function drawRings(it, t) {
    const el = $(it.id);
    el.style.opacity = (clamp((t - it.in) / 0.05) * outK(it, t, 0.2)).toFixed(3);
    const rs = it._r || (it._r = [...el.querySelectorAll(".ring")]);
    rs.forEach((ring, i) => {
      let best = null;
      for (const b of it.bursts) { const age = t - b - i * it.gap; if (age >= 0 && age <= it.life) best = age; }
      if (best === null) { ring.style.opacity = 0; return; }
      const k = easeOut(best / it.life), r = it.rmax * k;
      ring.style.width = ring.style.height = (2 * r).toFixed(1) + "px";
      ring.style.transform = `translate(${(-r).toFixed(1)}px,${(-r).toFixed(1)}px)`;
      ring.style.borderWidth = Math.max(1, it.sw * (1 - k)).toFixed(2) + "px";
      ring.style.opacity = (0.95 * (1 - k)).toFixed(3);
    });
  }

  // Connector lines draw on with the nodes they join.
  function drawLine(it, t) {
    const el = $(it.id);
    const k = easeInOut((t - it.in) / 0.35), ko = outK(it, t);
    el.style.opacity = ko.toFixed(3);
    el.style.transform = it.vertical ? `scaleY(${k.toFixed(4)})` : `scaleX(${k.toFixed(4)})`;
  }

  // Swap: two labels share one container; the old leaves before the new arrives.
  const DRAW = { shake: () => {}, rings: drawRings, text: drawText, code: drawCode, count: drawCount, scrub: drawScrub, fade: drawFade, line: drawLine, wave: drawWave, zoom: drawZoom, flash: drawFlash };

  function render(t) {
    drawCam(t);
    drawHero(t);
    for (const it of D.items) {
      if (it.kind === "zoom") { DRAW.zoom(it, t); continue; }
      if (it.kind === "shake") continue;  // folded into the camera
      if (t < it.in - 0.5 || t > it.out + 0.5) { const el = $(it.id); if (el.style.opacity !== "0") el.style.opacity = 0; continue; }
      DRAW[it.kind](it, t);
    }
    drawCursor(t);
  }

  window.IM = { render, spring, track };
  const fonts = document.fonts ? document.fonts.ready : Promise.resolve();
  window.__timelines = window.__timelines || {};
  const tl = gsap.timeline({ paused: true });
  const clock = { t: 0 };
  tl.to(clock, { t: D.dur, duration: D.dur, ease: "none", onUpdate: () => render(tl.time()) }, 0);
  window.__timelines[D.id] = tl;
  fonts.then(() => render(tl.time()));
  render(0);
})();
