// A painted/AI keyframe brought to life as 2.5D: depth-parallax camera, layers that open and snap together on the cut,
// word-locked camera kicks, handheld breath, flame flicker on warm highlights, wind sway, and a chapter grade.
// Every frame is a pure function of the frame number, so renders are deterministic.
import React, { useEffect, useRef, useState } from 'react';
import { continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

export type Cam = { z: number; x: number; y: number; ox: number; oy: number; k: number; r: number; f: number };
export type Move = { from: Cam; to: Cam; ease?: 'inOut' | 'out' | 'linear' };

const VS = `attribute vec2 p; varying vec2 v; void main(){ v = p*0.5+0.5; gl_Position = vec4(p,0.,1.); }`;
const FS = `precision highp float; varying vec2 v;
uniform sampler2D img, dep; uniform float z, k, r, f, aspect, frame, flick, warm, sway, tint, gray;
uniform vec3 lift, gam, gain, shadowTone, highTone;
uniform vec2 pan, off, crop;
float D(vec2 q){ return texture2D(dep, q).r; }
vec2 toImg(vec2 s){ return vec2(0.5 + (s.x-0.5)*crop.x, 0.5 + (s.y-0.5)*crop.y); }
vec2 src(vec2 uv){
  vec2 c = vec2(0.5);
  vec2 s = uv - c - pan;
  s.x *= aspect; float cr = cos(r), sr = sin(r); s = mat2(cr, -sr, sr, cr) * s; s.x /= aspect;
  vec2 p = uv;
  for (int i = 0; i < 8; i++) { float d = D(toImg(p)) - f; p = c + s / (z * (1.0 + k * d)) - off * d; }
  return toImg(p);
}
float flameMask(vec3 c){ float l = max(c.r, max(c.g, c.b)); return smoothstep(0.80, 0.97, l) * smoothstep(0.45, 0.80, c.g) * smoothstep(0.12, 0.35, c.r - c.b); }
float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(h(i), h(i+vec2(1.,0.)), f.x), mix(h(i+vec2(0.,1.)), h(i+vec2(1.,1.)), f.x), f.y); }
void main(){
  vec2 uv = vec2(v.x, 1.0 - v.y);
  vec2 q = src(uv);
  if (sway > 0.0) {
    float dd = texture2D(dep, q).r;
    float w = sin(q.y * 38.0 + frame * 0.11) * cos(q.x * 21.0 + frame * 0.07);
    q += vec2(w, w * 0.4) * sway * 0.0014 * (1.0 - dd * 0.7) * smoothstep(0.85, 0.2, q.y + 0.25);
  }
  vec3 col = texture2D(img, q).rgb;
  float fm = flameMask(col);
  if (flick > 0.0 && fm > 0.0) {
    float ph = vnoise(q * vec2(60.0, 34.0)) * 6.2831;
    float fl = 0.5 + 0.3 * sin(frame * 0.37 + ph) + 0.2 * sin(frame * 0.91 + ph * 2.3);
    col += fm * (fl - 0.5) * flick * 0.35;
  }
  if (warm > 0.0) {
    vec3 bloom = vec3(0.0);
    for (int i = 0; i < 8; i++) { float a = float(i) * 0.7854; vec2 o = vec2(cos(a), sin(a)) * 0.007; vec3 c2 = texture2D(img, q + o).rgb; bloom += c2 * flameMask(c2); }
    col += bloom / 8.0 * 0.32 * warm * (0.85 + 0.15 * sin(frame * 0.29));
  }
  col = pow(max(gain * (col + lift * (1.0 - col)), 0.0), 1.0 / gam);
  float lum = dot(col, vec3(0.299, 0.587, 0.114));
  col = mix(col, col * mix(shadowTone, highTone, smoothstep(0.15, 0.85, lum)), tint);
  col = mix(col, vec3(lum), gray);
  float vg = smoothstep(1.25, 0.35, length((uv - 0.5) * vec2(1.0, 0.85)));
  col *= mix(0.62, 1.0, vg);
  float g = fract(sin(dot(uv * vec2(1920., 1080.) + frame * 17.13, vec2(12.9898, 78.233))) * 43758.5453) - 0.5;
  col += g * 0.03;
  gl_FragColor = vec4(col, 1.0);
}`;

const ease = (t: number, kind: Move['ease']) => {
  t = Math.max(0, Math.min(1, t));
  if (kind === 'linear') return t;
  if (kind === 'out') return 1 - Math.pow(1 - t, 3);
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
};
const expoOut = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * Math.max(0, t)));

export const kickAmp = (f: number, kicks: number[], fps: number) => {
  let a = 0;
  for (const k of kicks) if (f >= k) a += Math.exp(-((f - k) / fps) / 0.38) * Math.min(1, (f - k + 1) / 3);
  return Math.min(a, 1.3);
};

export type V3 = [number, number, number];
export type Look = { lift: V3; gamma: V3; gain: V3; shadow: V3; high: V3; tint: number };
export const LOOKS: Record<string, Look> = {
  neutral: { lift: [0, 0, 0], gamma: [1, 1, 1], gain: [1, 1, 1], shadow: [1, 1, 1], high: [1, 1, 1], tint: 0 },
  dusk: { lift: [0.01, 0.015, 0.03], gamma: [1.0, 1.0, 1.02], gain: [1.04, 0.98, 0.95], shadow: [0.85, 0.92, 1.1], high: [1.1, 1.0, 0.88], tint: 0.6 },
  ice: { lift: [0.0, 0.01, 0.03], gamma: [0.97, 1.0, 1.04], gain: [0.92, 0.98, 1.06], shadow: [0.82, 0.95, 1.12], high: [0.98, 1.02, 1.06], tint: 0.7 },
  night: { lift: [0.0, 0.008, 0.03], gamma: [0.93, 0.96, 1.02], gain: [0.8, 0.88, 1.02], shadow: [0.7, 0.85, 1.2], high: [0.92, 0.98, 1.08], tint: 0.8 },
  fire: { lift: [0.0, 0.005, 0.025], gamma: [0.97, 0.97, 1.0], gain: [1.03, 0.96, 0.87], shadow: [0.72, 0.82, 1.15], high: [1.14, 1.0, 0.8], tint: 0.85 },
  dawn: { lift: [0.03, 0.02, 0.02], gamma: [1.05, 1.02, 0.98], gain: [1.06, 1.0, 0.9], shadow: [0.95, 0.9, 1.0], high: [1.1, 1.0, 0.86], tint: 0.6 },
  jungle: { lift: [0.0, 0.015, 0.005], gamma: [0.98, 1.03, 0.98], gain: [0.95, 1.04, 0.9], shadow: [0.8, 1.0, 0.9], high: [1.05, 1.04, 0.88], tint: 0.6 },
  desert: { lift: [0.03, 0.02, 0.0], gamma: [1.04, 1.0, 0.95], gain: [1.08, 1.0, 0.86], shadow: [0.95, 0.88, 0.85], high: [1.12, 1.02, 0.82], tint: 0.65 },
  ocean: { lift: [0.0, 0.015, 0.03], gamma: [0.96, 1.0, 1.04], gain: [0.86, 1.0, 1.06], shadow: [0.75, 0.95, 1.1], high: [0.95, 1.05, 1.06], tint: 0.7 },
};

export const C = (o: Partial<Cam> = {}): Cam => ({ z: 1.06, x: 0, y: 0, ox: 0, oy: 0, k: 0.0, r: 0, f: 0.5, ...o });
export const MOVES: Record<string, Move> = {
  push: { from: C({ z: 1.05 }), to: C({ z: 1.17, k: 0.12 }) },
  pull: { from: C({ z: 1.19, k: 0.14 }), to: C({ z: 1.05 }) },
  panl: { from: C({ z: 1.15, x: 0.035, ox: 0.012 }), to: C({ z: 1.15, x: -0.035, ox: -0.012 }) },
  panr: { from: C({ z: 1.15, x: -0.035, ox: -0.012 }), to: C({ z: 1.15, x: 0.035, ox: 0.012 }) },
  rise: { from: C({ z: 1.13, y: 0.035, oy: 0.01 }), to: C({ z: 1.15, y: -0.03, oy: -0.01 }) },
  drop: { from: C({ z: 1.15, y: -0.03, oy: -0.01 }), to: C({ z: 1.13, y: 0.035, oy: 0.01 }) },
  dolly: { from: C({ z: 1.04, k: -0.15 }), to: C({ z: 1.21, k: 0.35 }) },
  orbit: { from: C({ z: 1.13, ox: -0.02, oy: 0.006, r: -0.6 }), to: C({ z: 1.16, ox: 0.02, oy: -0.006, r: 0.6 }) },
  hold: { from: C({ z: 1.08 }), to: C({ z: 1.1 }) },
  crash: { from: C({ z: 1.0 }), to: C({ z: 1.24, k: 0.2 }), ease: 'out' },
};

export const Plate25D: React.FC<{
  src: string; depth: string; durationInFrames: number; move: Move; look?: Look; seed?: number;
  kicks?: number[]; punch?: boolean; flicker?: number; warm?: number; sway?: number; gray?: number; cssFilter?: string;
}> = ({ src, depth, durationInFrames, move, look = LOOKS.neutral, seed = 1, kicks = [], punch = false, flicker = 0, warm = 0, sway = 0, gray = 0, cssFilter }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const ref = useRef<HTMLCanvasElement>(null);
  const gl = useRef<{ g: WebGLRenderingContext; U: Record<string, WebGLUniformLocation | null>; iw: number; ih: number } | null>(null);
  const [handle] = useState(() => delayRender(`plate ${src}`, { timeoutInMilliseconds: 120000 }));
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const load = (u: string) => new Promise<HTMLImageElement>((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = staticFile(u); });
    Promise.all([load(src), load(depth)]).then(([im, dp]) => {
      const c = ref.current!;
      const g = c.getContext('webgl', { preserveDrawingBuffer: true, antialias: false })!;
      const sh = (t: number, s: string) => { const o = g.createShader(t)!; g.shaderSource(o, s); g.compileShader(o); return o; };
      const prog = g.createProgram()!;
      g.attachShader(prog, sh(g.VERTEX_SHADER, VS)); g.attachShader(prog, sh(g.FRAGMENT_SHADER, FS)); g.linkProgram(prog); g.useProgram(prog);
      const b = g.createBuffer(); g.bindBuffer(g.ARRAY_BUFFER, b);
      g.bufferData(g.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), g.STATIC_DRAW);
      const loc = g.getAttribLocation(prog, 'p'); g.enableVertexAttribArray(loc); g.vertexAttribPointer(loc, 2, g.FLOAT, false, 0, 0);
      const U: Record<string, WebGLUniformLocation | null> = {};
      for (const n of ['img', 'dep', 'z', 'k', 'r', 'f', 'aspect', 'frame', 'flick', 'warm', 'pan', 'off', 'crop', 'sway', 'tint', 'gray', 'lift', 'gam', 'gain', 'shadowTone', 'highTone']) U[n] = g.getUniformLocation(prog, n);
      [im, dp].forEach((el, i) => {
        const t = g.createTexture(); g.activeTexture(i ? g.TEXTURE1 : g.TEXTURE0); g.bindTexture(g.TEXTURE_2D, t);
        g.texParameteri(g.TEXTURE_2D, g.TEXTURE_WRAP_S, g.CLAMP_TO_EDGE); g.texParameteri(g.TEXTURE_2D, g.TEXTURE_WRAP_T, g.CLAMP_TO_EDGE);
        g.texParameteri(g.TEXTURE_2D, g.TEXTURE_MIN_FILTER, g.LINEAR); g.texParameteri(g.TEXTURE_2D, g.TEXTURE_MAG_FILTER, g.LINEAR);
        g.texImage2D(g.TEXTURE_2D, 0, g.RGBA, g.RGBA, g.UNSIGNED_BYTE, el);
      });
      g.uniform1i(U.img, 0); g.uniform1i(U.dep, 1);
      gl.current = { g, U, iw: im.naturalWidth, ih: im.naturalHeight };
      setReady(true);
      continueRender(handle);
    }).catch((e) => { console.error('plate load failed', src, e); continueRender(handle); });
  }, []);

  useEffect(() => {
    const s = gl.current; if (!s) return;
    const { g, U, iw, ih } = s;
    const t = ease(frame / Math.max(1, durationInFrames - 1), move.ease);
    const L = (a: number, b: number) => a + (b - a) * t;
    const a = move.from, b = move.to;
    const ka = kickAmp(frame, kicks, fps) + (punch ? 1.2 * Math.exp(-frame / (0.25 * fps)) : 0);
    const open = 1 - expoOut(frame / (0.7 * fps));          // layers open apart on the cut, then snap together
    const hx = 0.0018 * Math.sin(frame * 0.07 + seed) + 0.0012 * Math.sin(frame * 0.031 + seed * 2.1);
    const hy = 0.0014 * Math.cos(frame * 0.061 + seed * 1.3) + 0.0010 * Math.sin(frame * 0.027 + seed);
    const hr = 0.12 * Math.sin(frame * 0.05 + seed * 0.7);
    const ia = iw / ih, sa = width / height;
    g.viewport(0, 0, width, height);
    g.uniform2f(U.crop, ia > sa ? sa / ia : 1, ia > sa ? 1 : ia / sa);
    g.uniform1f(U.z, L(a.z, b.z) + 0.035 * ka);
    g.uniform1f(U.k, L(a.k, b.k) + 0.22 * ka + 0.28 * open);
    g.uniform1f(U.r, ((L(a.r, b.r) + hr) * Math.PI) / 180);
    g.uniform1f(U.f, L(a.f, b.f)); g.uniform1f(U.aspect, sa);
    g.uniform2f(U.pan, L(a.x, b.x) + hx, L(a.y, b.y) + hy);
    g.uniform2f(U.off, L(a.ox, b.ox) + 0.012 * open, L(a.oy, b.oy) + 0.004 * open);
    g.uniform1f(U.sway, sway); g.uniform1f(U.tint, look.tint); g.uniform1f(U.gray, gray);
    g.uniform3f(U.lift, ...look.lift); g.uniform3f(U.gam, ...look.gamma); g.uniform3f(U.gain, ...look.gain);
    g.uniform3f(U.shadowTone, ...look.shadow); g.uniform3f(U.highTone, ...look.high);
    g.uniform1f(U.frame, frame); g.uniform1f(U.flick, flicker); g.uniform1f(U.warm, warm);
    g.drawArrays(g.TRIANGLE_STRIP, 0, 4);
  }, [frame, ready]);

  return <canvas ref={ref} width={width} height={height} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', filter: cssFilter }} />;
};
