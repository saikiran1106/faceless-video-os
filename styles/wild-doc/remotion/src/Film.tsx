// Wild-doc film: every shot, overlay, caption and transition comes from props.plan (built by `faceless wild-doc plan`).
// Shot kinds: stock (pre-graded footage segment), plate (AI still as 2.5D depth parallax), ref (real photo evidence card),
// mg (full-screen motion graphic). Every frame is a pure function of the frame number.
import React from 'react';
import { AbsoluteFill, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { LOOKS, MOVES, Plate25D, kickAmp } from './Plate25D';
import { Particles, TRANS_DUR, Transition, TransKind } from './Atmos';
import { Evidence, FULLS, OVERLAYS } from './Cards';

import { loadFont as loadAnton } from '@remotion/google-fonts/Anton';
import { loadFont as loadBebas } from '@remotion/google-fonts/BebasNeue';
import { loadFont as loadInter } from '@remotion/google-fonts/Inter';
import { loadFont as loadMukta } from '@remotion/google-fonts/Mukta';
loadAnton('normal', { weights: ['400'], subsets: ['latin'] });
loadBebas('normal', { weights: ['400'], subsets: ['latin'] });
loadInter('normal', { weights: ['600', '800'], subsets: ['latin'] });
loadInter('italic', { weights: ['600'], subsets: ['latin'] });
loadMukta('normal', { weights: ['800'], subsets: ['latin', 'devanagari'] });

type Shot = Record<string, any>;
export type Plan = { fps: number; durationInFrames: number; shots: Shot[]; overlays: any[]; captions: any[]; chapters: any[]; theme?: Record<string, string> };

const Stock: React.FC<{ s: Shot }> = ({ s }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const p = f / Math.max(1, s.dur);
  const dir = s.i % 2 ? 1 : -1;
  const ka = kickAmp(f, s.kicks ?? [], fps) + (s.trans === 'punch' ? 1.2 * Math.exp(-f / (0.25 * fps)) : 0);
  const z = (dir > 0 ? 1.06 + 0.08 * p : 1.14 - 0.08 * p) + 0.045 * ka;
  const hx = Math.sin(f * 0.071 + s.i) * 4 + Math.sin(f * 0.023 + s.i * 3) * 7;
  const hy = Math.cos(f * 0.063 + s.i * 2) * 3 + Math.sin(f * 0.019 + s.i) * 5;
  // grade, vignette, grain, blur and gray are baked into s.seg by `faceless wild-doc grade` (CSS filters cost ~2 s/frame)
  return <AbsoluteFill style={{ overflow: 'hidden', background: '#05070a' }}>
    <OffthreadVideo src={staticFile(s.seg)} muted
      style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `translate(${hx}px,${hy}px) scale(${z})` }} />
  </AbsoluteFill>;
};

const PlateShot: React.FC<{ s: Shot }> = ({ s }) => (
  <Plate25D src={s.img} depth={s.depth} durationInFrames={s.dur} move={MOVES[s.move] ?? MOVES.push} look={LOOKS[s.look] ?? LOOKS.neutral}
    seed={s.i} kicks={s.kicks ?? []} punch={s.trans === 'punch'} flicker={s.look === 'fire' ? 1 : 0} warm={s.look === 'fire' ? 1 : 0}
    sway={s.fx === 'snow' ? 0.6 : 0.25} gray={s.gray ? 0.85 : 0} cssFilter={s.blur ? 'blur(6px)' : undefined} />
);

const Captions: React.FC<{ caps: any[] }> = ({ caps }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const c = caps.find((c) => f >= c.from && f < c.to);
  if (!c) return null;
  const appear = Math.min(1, (f - c.from) / 4);
  return <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 64, pointerEvents: 'none' }}>
    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', maxWidth: 1560, opacity: appear, transform: `translateY(${(1 - appear) * 10}px)` }}>
      {c.w.map((w: any, i: number) => {
        const active = f >= w.from && f < w.to + 2;
        const bt = (f - w.from) / fps;
        const bump = active ? (bt < 0.09 ? bt / 0.09 : Math.max(0, 1 - (bt - 0.09) / 0.22)) : 0;
        const col = active ? (w.s ? 'var(--hot)' : 'var(--ice)') : '#ffffff';
        return <span key={i} style={{ fontFamily: 'Mukta, Inter', fontWeight: 800, fontSize: 56, lineHeight: 1.35, color: col, margin: '0 0.16em', display: 'inline-block',
          transform: `translateY(${-8 * bump}px) scale(${1 + 0.14 * bump})`, WebkitTextStroke: '6px rgba(0,0,0,0.9)', paintOrder: 'stroke fill',
          textShadow: '0 4px 16px rgba(0,0,0,0.9)' }}>{w.t}</span>;
      })}
    </div>
  </AbsoluteFill>;
};

// cut energy: every shot enters with a short camera hit keyed to its transition; auto-split pieces are punch-in jump cuts
const rnd = (i: number) => { const x = Math.sin(i * 77.7 + 1.3) * 43758.5453; return x - Math.floor(x); };
const Enter: React.FC<{ s: Shot; children: React.ReactNode }> = ({ s, children }) => {
  const f = useCurrentFrame();
  const ease = (t: number) => 1 - Math.pow(1 - Math.max(0, Math.min(1, t)), 3);
  let sc = 1, tx = 0, ty = 0, rot = 0;
  const k = s.trans;
  if (k === 'zoom') sc *= 1 + 0.24 * (1 - ease(f / 7));
  if (k === 'punch') sc *= 1 + 0.1 * (1 - ease(f / 5));
  if (k === 'whip' || k === 'slide') tx = (s.i % 2 ? 1 : -1) * 260 * (1 - ease(f / 6));
  if (k === 'glitch' && f < 5) { tx = (rnd(f + s.i) - 0.5) * 70; ty = (rnd(f + s.i + 9) - 0.5) * 18; sc *= 1.04; }
  if (k === 'flash') sc *= 1 + 0.06 * (1 - ease(f / 8));
  if (s.sub_i) { sc *= 1.16 + 0.04 * (s.sub_i % 2); tx += s.sub_i % 2 ? -60 : 60; }
  if (k === 'whip' && f < 6) rot = (s.i % 2 ? 1 : -1) * 1.2 * (1 - f / 6);
  if (sc === 1 && tx === 0 && ty === 0) return <>{children}</>;
  return <AbsoluteFill style={{ transform: `translate(${tx}px,${ty}px) scale(${sc}) rotate(${rot}deg)` }}>{children}</AbsoluteFill>;
};

const DEFAULT_THEME: Record<string, string> = { red: '#ff3b2f', ice: '#9fdcff', gold: '#ffc861', cream: '#fff6e6', hot: '#ff6b2c' };

export const Film: React.FC<{ plan: Plan }> = ({ plan }) => {
  const theme = { ...DEFAULT_THEME, ...(plan.theme ?? {}) };
  const vars = Object.fromEntries(Object.entries(theme).map(([k, v]) => [`--${k}`, v])) as React.CSSProperties;
  return <AbsoluteFill style={{ background: '#000', ...vars }}>
    {plan.shots.map((s) => <Sequence key={s.i} from={s.from} durationInFrames={s.dur} name={`${s.i} ${s.name ?? s.id ?? s.mg}`}>
      <Enter s={s}>{s.kind === 'stock' ? <Stock s={s} /> : s.kind === 'plate' ? <PlateShot s={s} /> : s.kind === 'ref' ? <Evidence s={s} />
        : React.createElement(FULLS[s.mg] ?? FULLS.black, { dur: s.dur, props: s.props ?? {} })}</Enter>
      {s.fx ? <Particles kind={s.fx} seed={s.i} amount={s.fx === 'snow' ? 1 : 0.9} /> : null}
    </Sequence>)}
    {plan.shots.filter((s) => s.trans && s.trans !== 'cut').map((s) => {
      const d = TRANS_DUR[s.trans as TransKind] ?? 8;
      return <Sequence key={'t' + s.i} from={Math.max(0, s.from - Math.floor(d / 2))} durationInFrames={d}><Transition kind={s.trans} dur={d} /></Sequence>;
    })}
    {plan.overlays.map((o, i) => <Sequence key={'o' + i} from={o.from} durationInFrames={o.dur}>
      {React.createElement(OVERLAYS[o.kind] ?? OVERLAYS.kw, { dur: o.dur, props: o.props, look: o.look })}
    </Sequence>)}
    {plan.captions?.length ? <Captions caps={plan.captions} /> : null}
  </AbsoluteFill>;
};
