// Seeded atmosphere particles and motivated transitions. Pure functions of the frame: deterministic renders.
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';

const rnd = (i: number, s: number) => { const x = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return x - Math.floor(x); };

export type FxKind = 'snow' | 'embers' | 'dust';
const SPEC: Record<FxKind, { n: number; size: [number, number]; color: string; glow: number; vy: number; vx: number; wobble: number }> = {
  snow: { n: 140, size: [1.4, 4.2], color: '235,242,255', glow: 3, vy: 85, vx: -55, wobble: 26 },
  embers: { n: 60, size: [1.6, 4.5], color: '255,150,60', glow: 12, vy: -42, vx: 10, wobble: 24 },
  dust: { n: 70, size: [1.2, 3.0], color: '230,215,190', glow: 3, vy: -5, vx: 10, wobble: 18 },
};

export const Particles: React.FC<{ kind: FxKind; seed?: number; amount?: number }> = ({ kind, seed = 1, amount = 1 }) => {
  const f = useCurrentFrame();
  const { width: W, height: H, fps } = useVideoConfig();
  const sp = SPEC[kind] ?? SPEC.dust;
  const t = f / fps;
  const n = Math.round(sp.n * amount);
  return <AbsoluteFill style={{ pointerEvents: 'none' }}>
    <svg width={W} height={H}>
      {Array.from({ length: n }, (_, i) => {
        const a = rnd(i, seed), b = rnd(i + 99, seed), c = rnd(i + 199, seed);
        const life = 4 + c * 5;
        const ph = ((t + a * life) % life) / life;
        const depth = 0.4 + c * 0.9;                                   // near flakes fall faster and are bigger
        const x = ((a * W + sp.vx * depth * ph * life + Math.sin(t * (0.6 + b) + i) * sp.wobble) % W + W) % W;
        const y = (((b * H) + sp.vy * depth * ph * life) % H + H) % H;
        const fade = Math.sin(Math.PI * ph);
        const r = (sp.size[0] + c * (sp.size[1] - sp.size[0])) * (kind === 'snow' ? depth : 1);
        return <g key={i}>
          {sp.glow > 4 ? <circle cx={x} cy={y} r={r * 2.6} fill={`rgba(${sp.color},${0.25 * fade})`} /> : null}
          <circle cx={x} cy={y} r={r} fill={`rgba(${sp.color},${(kind === 'snow' ? 0.75 : 0.9) * fade})`} />
        </g>;
      })}
    </svg>
  </AbsoluteFill>;
};

export type TransKind = 'whip' | 'dip' | 'flash' | 'leak' | 'punch' | 'ice' | 'cut' | 'zoom' | 'glitch' | 'slide';
export const TRANS_DUR: Record<TransKind, number> = { whip: 8, dip: 10, flash: 8, leak: 16, punch: 6, ice: 10, cut: 1, zoom: 8, glitch: 8, slide: 8 };

export const Transition: React.FC<{ kind: TransKind; dur: number }> = ({ kind, dur }) => {
  const f = useCurrentFrame();
  const half = dur / 2;
  const cl = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
  if (kind === 'cut' || kind === 'slide') return null;
  if (kind === 'zoom') {
    const a = interpolate(f, [0, half, dur], [0, 0.55, 0], cl);
    return <AbsoluteFill style={{ background: 'radial-gradient(circle at 50% 50%, rgba(255,255,255,0) 20%, rgba(255,255,255,.9) 100%)', opacity: a, mixBlendMode: 'screen' }} />;
  }
  if (kind === 'glitch') {
    // horizontal tear bars + colour fringes for a few frames around the cut (rgb shift itself is baked by ffmpeg in assembly)
    const seed = Math.floor(f / 1);
    const bars = Array.from({ length: 9 }, (_, i) => {
      const r1 = rnd(i, seed + 3), r2 = rnd(i + 40, seed), r3 = rnd(i + 80, seed + 1);
      return <div key={i} style={{ position: 'absolute', left: `${(r2 - 0.5) * 30}%`, top: `${r1 * 100}%`, width: '100%', height: 6 + r3 * 46,
        background: i % 3 === 0 ? 'rgba(255,40,90,.55)' : i % 3 === 1 ? 'rgba(40,230,255,.5)' : 'rgba(255,255,255,.35)', mixBlendMode: 'screen' }} />;
    });
    const on = f < dur - 1;
    return on ? <AbsoluteFill style={{ overflow: 'hidden' }}>{bars}<AbsoluteFill style={{ background: 'repeating-linear-gradient(0deg, rgba(0,0,0,.25) 0 2px, rgba(0,0,0,0) 2px 5px)' }} /></AbsoluteFill> : null;
  }
  if (kind === 'dip') {
    const a = interpolate(f, [0, half, dur], [0, 1, 0], cl);
    return <AbsoluteFill style={{ background: '#000', opacity: a }} />;
  }
  if (kind === 'flash') {
    const a = interpolate(f, [0, half - 1, half + 1, dur], [0, 0.9, 0.9, 0], cl);
    return <AbsoluteFill style={{ background: 'radial-gradient(circle at 50% 55%, #fff6dc 0%, #ffb04a 35%, rgba(255,140,40,0) 78%)', opacity: a, mixBlendMode: 'screen' }} />;
  }
  if (kind === 'ice') {
    const a = interpolate(f, [0, half, dur], [0, 0.85, 0], cl);
    return <AbsoluteFill style={{ background: 'radial-gradient(circle at 50% 50%, rgba(235,248,255,0.95) 0%, rgba(150,200,255,0.55) 45%, rgba(40,80,140,0) 80%)', opacity: a, mixBlendMode: 'screen', backdropFilter: `blur(${a * 10}px)` }} />;
  }
  if (kind === 'punch') {
    const a = interpolate(f, [0, 1, dur], [0, 0.7, 0], cl);
    return <AbsoluteFill style={{ background: '#fff', opacity: a * 0.55, mixBlendMode: 'screen' }} />;
  }
  if (kind === 'leak') {
    const p = interpolate(f, [0, dur], [0, 1], cl);
    const a = Math.sin(Math.PI * p) * 0.75;
    return <AbsoluteFill style={{ background: `linear-gradient(${100 + p * 40}deg, rgba(255,120,40,0) ${10 + p * 30}%, rgba(255,170,80,.9) ${35 + p * 30}%, rgba(255,230,180,.6) ${45 + p * 30}%, rgba(255,120,40,0) ${70 + p * 30}%)`, opacity: a, mixBlendMode: 'screen' }} />;
  }
  const p = interpolate(f, [0, dur], [0, 1], cl);
  const a = Math.sin(Math.PI * p);
  return <AbsoluteFill style={{ backdropFilter: `blur(${a * 30}px)`, background: `linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(220,235,255,${a * 0.3}) ${p * 100}%, rgba(255,255,255,0) 100%)` }} />;
};
