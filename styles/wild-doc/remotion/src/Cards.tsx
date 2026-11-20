// Wild-doc motion graphics. English on-screen text by default; every string is a prop.
// OVERLAYS sit on top of a shot (shotlist `O` rows). FULLS replace the shot (shotlist `M:<name>` with props from graphics.json).
// Palette comes from CSS variables set by Film (style.json "theme"). Fonts: Anton (headlines), Bebas Neue (labels), Inter (small).
import React from 'react';
import { AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

const cl = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
const E = (t: number) => 1 - Math.pow(1 - Math.max(0, Math.min(1, t)), 3);
const EB = (t: number) => { t = Math.max(0, Math.min(1, t)); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
const ICE = 'var(--ice)', RED = 'var(--red)', GOLD = 'var(--gold)', CREAM = 'var(--cream)';
const H = 'Anton', L = 'Bebas Neue', T = 'Inter';
const shadow = '0 4px 18px rgba(0,0,0,.85)';
const TONE: Record<string, string> = { red: RED, ice: ICE, gold: GOLD, white: '#ffffff' };
const rnd = (i: number) => { const x = Math.sin(i * 91.7 + 13.3) * 43758.5453; return x - Math.floor(x); };
// chroma split that decays: the "glitch-in" every text element uses
const chroma = (f: number, amt = 14, dur = 6) => {
  const k = Math.max(0, 1 - f / dur); const j = f < dur ? (rnd(f) - 0.5) * 2 : 0;
  return k > 0 ? `${(amt * k + j * 6).toFixed(1)}px 0 0 rgba(255,40,80,.85), ${(-amt * k - j * 6).toFixed(1)}px 0 0 rgba(40,220,255,.85), ${shadow}` : `0 6px 24px rgba(0,0,0,.9)`;
};
const useIO = (dur: number, inF = 6, outF = 7) => {
  const f = useCurrentFrame();
  return { f, a: Math.min(interpolate(f, [0, inF], [0, 1], cl), interpolate(f, [dur - outF, dur], [1, 0], cl)) };
};
type P = { dur: number; props: any; look?: string };
const num = (v: number) => Math.round(v).toLocaleString('en-US');

// ---------------- overlays ----------------
const KW: React.FC<P> = ({ dur, props }) => {
  const f = useCurrentFrame();
  const col = TONE[props.tone ?? 'white'] ?? '#fff';
  const s = interpolate(f, [0, 4, 7], [1.45, 0.96, 1], cl) * interpolate(f, [dur - 5, dur], [1, 1.08], cl);
  const a = Math.min(interpolate(f, [0, 2], [0, 1], cl), interpolate(f, [dur - 4, dur], [1, 0], cl));
  const jx = f < 5 ? (rnd(f + 3) - 0.5) * 30 : f > dur - 4 ? (rnd(f + 7) - 0.5) * 24 : 0;
  const len = String(props.text ?? '').length;
  const size = len <= 8 ? 150 : len <= 14 ? 120 : len <= 20 ? 96 : 80;
  const x = props.pos === 'l' ? -600 : props.pos === 'r' ? 600 : 0;
  const bar = E((f - 2) / 8);
  return <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', opacity: a, paddingTop: 260 }}>
    <div style={{ transform: `translate(${x + jx}px,0) scale(${s})`, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ fontFamily: H, fontSize: size, lineHeight: 1, color: '#fff', textTransform: 'uppercase', WebkitTextStroke: `3px ${col}`, paintOrder: 'stroke fill', textShadow: chroma(f), whiteSpace: 'nowrap' }}>
        {props.x ? <span style={{ color: RED, marginRight: 22 }}>✕</span> : null}{props.text}</div>
      <div style={{ height: 8, width: `${bar * 100}%`, background: col, marginTop: 10, boxShadow: `0 0 24px ${col}` }} />
      {props.sub ? <div style={{ fontFamily: T, fontWeight: 800, fontSize: 40, color: CREAM, marginTop: 12, letterSpacing: 2, textShadow: shadow, opacity: interpolate(f, [5, 10], [0, 1], cl) }}>{props.sub}</div> : null}
    </div>
  </AbsoluteFill>;
};

// counter: {to: 10000, from: 0, label: "YEARS AGO", suffix: ""}
const Year: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 3, 8);
  const p = E(f / (dur * 0.55));
  const from = props.from ?? 0, to = props.to ?? 10000;
  const step = Math.abs(to - from) >= 1000 ? 10 : 1;
  return <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', opacity: a }}>
    <div style={{ fontFamily: H, fontSize: 190, lineHeight: 0.95, color: CREAM, textShadow: chroma(f, 18, 8), transform: `scale(${1 + (1 - p) * 0.12})` }}>{num(Math.round((from + (to - from) * p) / step) * step)}{props.suffix ?? ''}</div>
    <div style={{ fontFamily: L, fontSize: 84, letterSpacing: 18, color: ICE, textShadow: shadow, opacity: interpolate(f, [6, 12], [0, 1], cl) }}>{props.label ?? 'YEARS AGO'}</div>
  </AbsoluteFill>;
};

// {n: "12", label: "HOURS UNTIL DAWN"}
const Clock: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur);
  const p = E(f / 22);
  const R = 120, C = 2 * Math.PI * R;
  return <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'flex-end', paddingRight: 150, opacity: a }}>
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', transform: `scale(${0.85 + 0.15 * EB(f / 8)})` }}>
      <svg width={300} height={300}><circle cx={150} cy={150} r={R} stroke="rgba(255,255,255,.18)" strokeWidth={10} fill="rgba(5,10,20,.45)" />
        <circle cx={150} cy={150} r={R} style={{ stroke: GOLD }} strokeWidth={10} fill="none" strokeDasharray={C} strokeDashoffset={C * (1 - p)} transform="rotate(-90 150 150)" strokeLinecap="round" />
        {Array.from({ length: 12 }, (_, i) => <line key={i} x1={150} y1={40} x2={150} y2={52} stroke="#fff" strokeWidth={3} transform={`rotate(${i * 30} 150 150)`} opacity={0.7} />)}
        <line x1={150} y1={150} x2={150} y2={70} style={{ stroke: CREAM }} strokeWidth={6} strokeLinecap="round" transform={`rotate(${f * 9} 150 150)`} />
        <text x={150} y={180} textAnchor="middle" fontFamily={H} fontSize={96} style={{ fill: CREAM }}>{props.n ?? '12'}</text></svg>
      <div style={{ fontFamily: L, fontSize: 56, letterSpacing: 4, color: CREAM, textShadow: shadow, marginTop: -6 }}>{props.label ?? 'HOURS UNTIL DAWN'}</div>
    </div>
  </AbsoluteFill>;
};

// lower-third threat tag: {n: 1, name: "WOLVES", sci: "Canis lupus", label: "THREAT"}
const Threat: React.FC<P> = ({ dur, props }) => {
  const f = useCurrentFrame();
  const x = interpolate(f, [0, 5], [-560, 0], { ...cl, easing: E }), out = interpolate(f, [dur - 4, dur], [1, 0], cl);
  return <AbsoluteFill style={{ justifyContent: 'flex-end', padding: '0 0 170px 110px', opacity: out }}>
    <div style={{ transform: `translateX(${x}px) skewX(-8deg)`, background: 'linear-gradient(90deg, rgba(10,4,4,.9), rgba(10,4,4,.2))', borderLeft: `10px solid ${RED}`, padding: '12px 44px 16px 28px', width: 700 }}>
      <div style={{ fontFamily: L, fontSize: 44, letterSpacing: 6, color: RED }}>{`${props.label ?? 'THREAT'} ${String(props.n ?? 1).padStart(2, '0')}`}</div>
      <div style={{ fontFamily: H, fontSize: 92, lineHeight: 1.0, color: CREAM, textShadow: chroma(f, 10, 5) }}>{props.name}</div>
      <div style={{ fontFamily: T, fontWeight: 600, fontStyle: 'italic', fontSize: 30, color: '#d9c7b0' }}>{props.sci}</div>
    </div>
  </AbsoluteFill>;
};

// big chapter-danger card: {n, name, sci, label}
const Danger: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 4, 8);
  const w = E(f / 10), s = EB(f / 8);
  return <AbsoluteFill style={{ justifyContent: 'center', paddingLeft: 120, opacity: a }}>
    <div style={{ transform: `scale(${0.88 + 0.12 * s})`, transformOrigin: 'left center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <div style={{ fontFamily: H, fontSize: 64, color: '#111', background: RED, padding: '0 20px', lineHeight: 1.2 }}>{`#${props.n ?? 1}`}</div>
        <div style={{ fontFamily: L, fontSize: 72, letterSpacing: 10, color: RED, textShadow: shadow }}>{props.label ?? 'THREAT'}</div>
      </div>
      <div style={{ height: 5, width: 620 * w, background: `linear-gradient(90deg, ${RED}, transparent)`, margin: '10px 0 6px' }} />
      <div style={{ fontFamily: H, fontSize: 168, lineHeight: 1.0, color: CREAM, textShadow: chroma(f, 18, 7) }}>{props.name}</div>
      <div style={{ fontFamily: T, fontWeight: 600, fontStyle: 'italic', fontSize: 38, color: '#e3d2bb', textShadow: shadow }}>{props.sci}</div>
    </div>
  </AbsoluteFill>;
};

const Stamp: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 2, 8);
  const s = interpolate(f, [0, 4], [2, 1], cl);
  return <AbsoluteFill style={{ justifyContent: 'flex-start', alignItems: 'flex-end', padding: '110px 130px 0 0', opacity: a }}>
    <div style={{ transform: `rotate(-7deg) scale(${s})`, border: `7px solid ${RED}`, padding: '6px 30px', fontFamily: H, fontSize: 66, letterSpacing: 2, color: RED, background: 'rgba(0,0,0,.4)' }}>{props.text}</div>
  </AbsoluteFill>;
};

// {t: "6:00 PM", sub: "SUNSET"}
const Time: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 3, 10);
  const tx = E((f - 1) / 10);
  return <AbsoluteFill style={{ padding: '64px 0 0 90px', opacity: a }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 22 }}>
      <div style={{ width: 8, height: 120 * E(f / 6), background: GOLD, boxShadow: `0 0 20px ${GOLD}` }} />
      <div>
        <div style={{ fontFamily: H, fontSize: 104, color: CREAM, lineHeight: 1, textShadow: chroma(f, 16, 7), opacity: tx, transform: `translateX(${(1 - tx) * -30}px)` }}>{props.t}</div>
        <div style={{ fontFamily: L, fontSize: 46, letterSpacing: 8, color: GOLD, opacity: interpolate(f, [8, 14], [0, 1], cl), textShadow: shadow }}>{props.sub}</div>
      </div>
    </div>
  </AbsoluteFill>;
};

// {from: 5, to: -30, unit: "°C", label: "TEMPERATURE"}
const Thermo: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur);
  const p = E(f / (dur * 0.75));
  const from = props.from ?? 5, to = props.to ?? -30;
  const cold = to < from;
  const lvl = cold ? 0.78 - 0.62 * p : 0.16 + 0.62 * p;
  const q = cold ? p : 1 - p;
  const col = `rgb(${Math.round(255 - 170 * q)},${Math.round(120 + 90 * q)},${Math.round(60 + 195 * q)})`;
  return <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'flex-end', paddingRight: 170, opacity: a }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 22 }}>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontFamily: L, fontSize: 50, letterSpacing: 4, color: CREAM, textShadow: shadow }}>{props.label ?? 'TEMPERATURE'}</div>
        <div style={{ fontFamily: H, fontSize: 120, color: cold ? ICE : RED, lineHeight: 1, textShadow: shadow }}>{Math.round(from + (to - from) * p)}{props.unit ?? '°C'}</div>
      </div>
      <svg width={90} height={420}><rect x={30} y={10} width={30} height={340} rx={15} fill="rgba(255,255,255,.15)" stroke="rgba(255,255,255,.6)" strokeWidth={3} />
        <rect x={36} y={16 + 330 * (1 - lvl)} width={18} height={330 * lvl} rx={9} fill={col} />
        <circle cx={45} cy={375} r={36} fill={col} stroke="rgba(255,255,255,.6)" strokeWidth={3} /></svg>
    </div>
  </AbsoluteFill>;
};

// body silhouette draining: {label: "BODY HEAT", from: 100, to: 40, unit: "%"}
const BodyHeat: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur);
  const p = E(f / (dur * 0.85));
  const warm = `rgba(255,${Math.round(110 + 60 * p)},${Math.round(50 + 200 * p)},.85)`;
  const from = props.from ?? 100, to = props.to ?? 40;
  return <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'flex-end', paddingRight: 150, opacity: a }}>
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width={220} height={420} viewBox="0 0 220 420">
        <defs><linearGradient id="bh" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor="#5fb6ff" /><stop offset={`${p}`} stopColor="#5fb6ff" /><stop offset={`${Math.min(1, p + 0.06)}`} stopColor={warm} /><stop offset="1" stopColor={warm} /></linearGradient></defs>
        <g fill="url(#bh)" stroke="rgba(255,255,255,.7)" strokeWidth={3}>
          <circle cx={110} cy={52} r={38} />
          <path d="M60 104 Q110 92 160 104 L176 250 L150 254 L146 170 L140 260 L146 410 L118 410 L110 286 L102 410 L74 410 L80 260 L74 170 L70 254 L44 250 Z" />
        </g></svg>
      <div style={{ fontFamily: L, fontSize: 52, letterSpacing: 4, color: CREAM, textShadow: shadow }}>{props.label ?? 'BODY HEAT'}</div>
      <div style={{ fontFamily: H, fontSize: 64, color: ICE, textShadow: shadow }}>{`${Math.round(from + (to - from) * p)}${props.unit ?? '%'}`}</div>
    </div>
  </AbsoluteFill>;
};

const BigWord: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 2, 7);
  const s = EB(f / 7);
  return <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', opacity: a }}>
    <div style={{ fontFamily: H, fontSize: props.size ?? 210, color: '#fff3d6', transform: `scale(${0.7 + 0.3 * s})`, textShadow: `0 0 50px rgba(255,140,40,.9), 0 0 120px rgba(255,90,20,.6), ${chroma(f, 16, 6)}` }}>{props.text}</div>
  </AbsoluteFill>;
};

// engagement poll: {q, a, b, cta, commentAt (frames, set by the plan builder from the anchor word "Comment")}
const Poll: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 6, 10);
  const card = (i: number, label: string, txt: string) => {
    const s = EB((f - 14 - i * 6) / 10);
    return <div style={{ transform: `scale(${Math.max(0, s)})`, background: 'rgba(8,10,16,.85)', border: `4px solid ${i ? ICE : GOLD}`, borderRadius: 22, padding: '22px 54px', minWidth: 500, textAlign: 'center' }}>
      <div style={{ fontFamily: H, fontSize: 88, color: i ? ICE : GOLD, lineHeight: 1 }}>{label}</div>
      <div style={{ fontFamily: H, fontSize: 60, color: CREAM, letterSpacing: 1 }}>{txt}</div></div>;
  };
  const ca = props.commentAt ?? dur - 34;
  const pulse = 1 + 0.05 * Math.sin(f * 0.3);
  return <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', opacity: a, background: 'radial-gradient(ellipse at center, rgba(0,0,0,.55), rgba(0,0,0,.2))' }}>
    <div style={{ fontFamily: H, fontSize: 84, color: CREAM, marginBottom: 30, textShadow: chroma(f, 14, 6) }}>{props.q ?? 'WHAT WOULD YOU DO?'}</div>
    <div style={{ display: 'flex', gap: 60 }}>{card(0, 'A', props.a ?? 'OPTION A')}{card(1, 'B', props.b ?? 'OPTION B')}</div>
    <div style={{ marginTop: 44, fontFamily: H, fontSize: 64, color: '#111', background: GOLD, padding: '4px 40px', borderRadius: 40, transform: `scale(${Math.max(0.0001, EB((f - ca) / 7)) * (f > ca + 7 ? pulse : 1)})` }}>{props.cta ?? 'COMMENT BELOW ↓'}</div>
  </AbsoluteFill>;
};

// {kicker, title, body}
const Fact: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 6, 10);
  const x = interpolate(f, [0, 9], [90, 0], { ...cl, easing: E });
  return <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'flex-end', paddingRight: 110, opacity: a }}>
    <div style={{ transform: `translateX(${x}px)`, width: 700, background: 'rgba(8,8,10,.84)', borderTop: `6px solid ${GOLD}`, padding: '26px 42px 34px' }}>
      <div style={{ fontFamily: L, fontSize: 44, letterSpacing: 5, color: GOLD }}>{props.kicker ?? 'FACT'}</div>
      <div style={{ fontFamily: H, fontSize: 72, lineHeight: 1.08, color: CREAM, margin: '8px 0 14px', textShadow: chroma(f, 10, 6) }}>{props.title}</div>
      {props.body ? <div style={{ fontFamily: H, fontSize: 54, color: RED, opacity: interpolate(f, [26, 34], [0, 1], cl), transform: `scale(${0.9 + 0.1 * EB((f - 26) / 8)})`, transformOrigin: 'left' }}>→ {props.body}</div> : null}
    </div>
  </AbsoluteFill>;
};

// "watch next" card: {text, sub, img: "plates/P42.jpg"}
const VideoCard: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 6, 10);
  const y = interpolate(f, [0, 9], [-50, 0], { ...cl, easing: E });
  return <AbsoluteFill style={{ alignItems: 'flex-end', padding: '80px 100px 0 0', opacity: a }}>
    <div style={{ transform: `translateY(${y}px)`, display: 'flex', gap: 20, alignItems: 'center', background: 'rgba(10,10,12,.88)', padding: 16, borderRadius: 14, width: 700 }}>
      <div style={{ position: 'relative', width: 260, height: 146, borderRadius: 8, overflow: 'hidden', background: '#222' }}>
        {props.img ? <Img src={staticFile(props.img)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : null}
        <div style={{ position: 'absolute', inset: 0, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 64, height: 44, background: '#ff0033', borderRadius: 12, display: 'flex', justifyContent: 'center', alignItems: 'center' }}><div style={{ width: 0, height: 0, borderLeft: '18px solid #fff', borderTop: '11px solid transparent', borderBottom: '11px solid transparent', marginLeft: 4 }} /></div></div>
      </div>
      <div><div style={{ fontFamily: H, fontSize: 46, color: CREAM, lineHeight: 1.1 }}>{props.text}</div>
        <div style={{ fontFamily: L, fontSize: 34, letterSpacing: 4, color: GOLD }}>{props.sub}</div></div>
    </div>
  </AbsoluteFill>;
};

// measuring ruler: {text: "1 METRE+"}
const Measure: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 6, 10);
  const w = E((f - 3) / 14) * 760;
  return <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 200, opacity: a }}>
    <svg width={900} height={140} style={{ stroke: GOLD }}>
      <line x1={70} y1={70} x2={70 + w} y2={70} strokeWidth={6} />
      <line x1={70} y1={40} x2={70} y2={100} strokeWidth={6} />
      {w > 740 ? <line x1={830} y1={40} x2={830} y2={100} strokeWidth={6} /> : null}
      {Array.from({ length: 10 }, (_, i) => 70 + i * 76 < 70 + w ? <line key={i} x1={70 + i * 76} y1={58} x2={70 + i * 76} y2={82} strokeWidth={3} /> : null)}
    </svg>
    <div style={{ fontFamily: H, fontSize: 120, color: CREAM, textShadow: chroma(f - 14, 14, 6), marginTop: -20, opacity: interpolate(f, [14, 18], [0, 1], cl) }}>{props.text}</div>
  </AbsoluteFill>;
};

// {title, sub}
const NameCard: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 5, 10);
  const w = E(f / 10);
  return <AbsoluteFill style={{ justifyContent: 'flex-end', padding: '0 0 180px 120px', opacity: a }}>
    <div style={{ height: 6, width: 480 * w, background: `linear-gradient(90deg, ${GOLD}, transparent)`, marginBottom: 12 }} />
    <div style={{ fontFamily: H, fontSize: 140, color: CREAM, lineHeight: 1, textShadow: chroma(f, 16, 7) }}>{props.title}</div>
    <div style={{ fontFamily: T, fontWeight: 600, fontStyle: 'italic', fontSize: 40, color: GOLD, textShadow: shadow }}>{props.sub}</div>
  </AbsoluteFill>;
};

const YearTag: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 4, 8);
  return <AbsoluteFill style={{ alignItems: 'center', paddingTop: 80, opacity: a }}>
    <div style={{ fontFamily: H, fontSize: 76, color: CREAM, background: 'rgba(0,0,0,.5)', padding: '0 34px', borderBottom: `6px solid ${GOLD}`, textShadow: chroma(f, 12, 6) }}>{props.text}</div>
  </AbsoluteFill>;
};

// three words in a row, one O row each: {text, i: 0|1|2}
const Word3: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 2, 6);
  const s = EB(f / 7);
  const x = [-580, 0, 580][props.i ?? 1];
  const len = String(props.text ?? '').length;
  return <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', opacity: a }}>
    <div style={{ transform: `translateX(${x}px) scale(${0.6 + 0.4 * s})`, fontFamily: H, fontSize: len > 7 ? 120 : 170, color: '#fff3d6', textShadow: `0 0 40px rgba(255,150,60,.85), ${chroma(f, 14, 6)}` }}>{props.text}</div>
  </AbsoluteFill>;
};

const Question: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 6, 10);
  return <AbsoluteFill style={{ justifyContent: 'flex-start', alignItems: 'center', paddingTop: 100, opacity: a }}>
    <div style={{ fontFamily: H, fontSize: 96, color: CREAM, textTransform: 'uppercase', textAlign: 'center', maxWidth: 1600, lineHeight: 1.05, textShadow: chroma(f, 14, 7), transform: `translateY(${(1 - E(f / 10)) * 24}px)` }}>{props.text}</div>
  </AbsoluteFill>;
};

export const OVERLAYS: Record<string, React.FC<P>> = {
  kw: KW, year: Year, counter: Year, clock: Clock, threat: Threat, danger: Danger, stamp: Stamp, time: Time, thermo: Thermo,
  bodyheat: BodyHeat, bigword: BigWord, poll: Poll, fact: Fact, videocard: VideoCard, measure: Measure, horn: Measure,
  namecard: NameCard, yeartag: YearTag, word3: Word3, question: Question,
};

// ---------------- real photo / fossil evidence card (a shot, not an overlay) ----------------
// s.img (contain), s.bg (blurred cover), s.label, s.sub, s.badge ("REAL FOSSIL", "RECONSTRUCTION", "REAL PHOTO" ...)
export const Evidence: React.FC<{ s: any }> = ({ s }) => {
  const f = useCurrentFrame();
  const p = f / Math.max(1, s.dur);
  const sub = s.sub_i ?? 0;
  const z = (sub ? 1.32 : 1.0) + 0.07 * p;
  const ox = sub ? (sub % 2 ? 30 : 70) : 50, oy = sub ? 42 : 50;
  const lab = E((f - 3) / 7);
  const brk = (x: number, y: number, r: number) => <div style={{ position: 'absolute', left: x, top: y, width: 70, height: 70, borderLeft: '5px solid rgba(255,255,255,.85)', borderTop: '5px solid rgba(255,255,255,.85)', transform: `rotate(${r}deg)` }} />;
  const scan = ((f * 22) % 1300) - 110;
  return <AbsoluteFill style={{ background: '#07080a', overflow: 'hidden' }}>
    <Img src={staticFile(s.bg)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${1.1 + 0.05 * p})` }} />
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', transform: `scale(${z})`, transformOrigin: `${ox}% ${oy}%` }}>
      <Img src={staticFile(s.img)} style={{ maxWidth: 1640, maxHeight: 900, objectFit: 'contain', boxShadow: '0 30px 80px rgba(0,0,0,.8)', filter: 'contrast(1.08) saturate(0.92)' }} />
    </AbsoluteFill>
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,.7) 100%)' }} />
    <div style={{ position: 'absolute', left: 0, right: 0, top: scan, height: 110, background: 'linear-gradient(180deg, rgba(160,220,255,0), rgba(160,220,255,.10), rgba(160,220,255,0))' }} />
    {brk(70, 60, 0)}{brk(1780, 60, 90)}{brk(1780, 950, 180)}{brk(70, 950, 270)}
    {s.label ? <>
      {s.badge ? <div style={{ position: 'absolute', left: 110, top: 92, fontFamily: L, fontSize: 40, letterSpacing: 6, color: '#111', background: RED, padding: '2px 18px', opacity: lab }}>{s.badge}</div> : null}
      <div style={{ position: 'absolute', left: 110, bottom: 96, opacity: lab, transform: `translateX(${(1 - lab) * -40}px)` }}>
        <div style={{ fontFamily: H, fontSize: 84, color: CREAM, lineHeight: 1, textShadow: chroma(f - 3, 12, 6) }}>{s.label}</div>
        {s.sub ? <div style={{ fontFamily: T, fontWeight: 600, fontSize: 32, color: GOLD, textShadow: shadow, marginTop: 6 }}>{s.sub}</div> : null}
      </div></> : null}
  </AbsoluteFill>;
};

// ---------------- full-screen graphics ----------------
// props.bgFile / props.bgFrom are resolved by the plan builder from graphics.json "bg": "<stock name>@<seconds>"
const BgVideo: React.FC<{ props: any; dim?: number; blur?: number }> = ({ props, dim = 0.45, blur = 8 }) => {
  const { fps } = useVideoConfig();
  return <AbsoluteFill style={{ background: props.bgColor ?? '#05070b' }}>
    {props.bgFile ? <OffthreadVideo src={staticFile(props.bgFile)} startFrom={Math.round((props.bgFrom ?? 0) * fps)} muted
      style={{ width: '100%', height: '100%', objectFit: 'cover', filter: `blur(${props.blur ?? blur}px) brightness(${props.dim ?? dim}) saturate(0.7)`, transform: 'scale(1.08)' }} /> : null}
    {props.bgImg ? <Img src={staticFile(props.bgImg)} style={{ width: '100%', height: '100%', objectFit: 'cover', filter: `blur(${props.blur ?? blur}px) brightness(${props.dim ?? dim})` }} /> : null}
    {props.hue ? <AbsoluteFill style={{ background: props.hue, mixBlendMode: 'soft-light' }} /> : null}
  </AbsoluteFill>;
};

// {kicker: "CHANNEL NAME", lines: ["COULD YOU SURVIVE", "ONE NIGHT ON THE", "SAVANNA?"], bg, hue}; the last line is the big one
const Title: React.FC<P> = ({ dur, props }) => {
  const f = useCurrentFrame();
  const a = interpolate(f, [0, 6, dur - 8, dur], [0, 1, 1, 0], cl);
  const lines: string[] = props.lines ?? ['TITLE'];
  const k = E((f - 2) / 9);
  return <AbsoluteFill>
    <BgVideo props={props} dim={0.5} blur={3} />
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', opacity: a }}>
      {props.kicker ? <div style={{ fontFamily: L, fontSize: 46, letterSpacing: 22, color: ICE, opacity: k }}>{props.kicker}</div> : null}
      {lines.map((t, i) => {
        const last = i === lines.length - 1, d = 2 + i * 5, p = E((f - d) / 9);
        return <div key={i} style={{ fontFamily: H, fontSize: last ? 190 : 112, color: last ? '#fff' : CREAM, lineHeight: last ? 1.0 : 1.05, letterSpacing: last ? 4 : 0,
          transform: last ? `scale(${0.8 + 0.2 * EB(p)})` : `translateY(${(1 - p) * 24}px)`, opacity: p,
          textShadow: last ? `0 0 50px rgba(140,200,255,.7), ${chroma(f - d, 22, 8)}` : chroma(f - d, 16, 7) }}>{t}</div>;
      })}
    </AbsoluteFill>
  </AbsoluteFill>;
};

// two bars: {a: {label, value}, b: {label, value}, verdict: "MANY TIMES HARSHER", bg}
const Compare: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 6, 10);
  const A = props.a ?? { label: 'TODAY', value: 1 }, B = props.b ?? { label: 'THEN', value: 6 };
  const mx = Math.max(A.value, B.value, 1e-6);
  const b1 = E((f - 5) / 12), b2 = E((f - 18) / 24);
  const bar = (w: number, col: string) => <div style={{ height: 74, width: w, background: col, borderRadius: 6, boxShadow: `0 0 30px ${col}` }} />;
  return <AbsoluteFill>
    <BgVideo props={props} dim={0.35} />
    <AbsoluteFill style={{ justifyContent: 'center', padding: '0 180px', opacity: a, gap: 50 }}>
      <div><div style={{ fontFamily: L, fontSize: 60, letterSpacing: 4, color: CREAM, marginBottom: 10 }}>{A.label}</div>{bar(1450 * (A.value / mx) * b1, '#ffb15e')}</div>
      <div><div style={{ fontFamily: L, fontSize: 60, letterSpacing: 4, color: CREAM, marginBottom: 10 }}>{B.label}</div>{bar(1450 * (B.value / mx) * b2, '#7cc8ff')}
        {props.verdict ? <div style={{ fontFamily: H, fontSize: 96, color: ICE, marginTop: 14, opacity: interpolate(f, [40, 46], [0, 1], cl), textShadow: chroma(f - 40, 14, 6) }}>{props.verdict}</div> : null}</div>
    </AbsoluteFill>
  </AbsoluteFill>;
};

// size comparison with two cut-outs (PNG with alpha in public/): {big: "~1.5 TONNES", left: {img, label, h}, right: {img, label, h}}
const Scale: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 6, 10);
  const r = E((f - 3) / 14), m = E((f - 11) / 11);
  const Lf = props.left ?? {}, R = props.right ?? {};
  return <AbsoluteFill style={{ background: 'radial-gradient(ellipse at 50% 60%, #12233d 0%, #05080f 75%)', opacity: a }}>
    <div style={{ position: 'absolute', left: 0, right: 0, top: 860, height: 3, background: 'rgba(159,220,255,.4)' }} />
    {Lf.img ? <Img src={staticFile(Lf.img)} style={{ position: 'absolute', left: 140, bottom: 218, height: Lf.h ?? 430, opacity: r, transform: `translateX(${(1 - r) * -60}px)`, filter: 'drop-shadow(0 0 30px rgba(120,190,255,.35))' }} /> : null}
    {R.img ? <Img src={staticFile(R.img)} style={{ position: 'absolute', right: 180, bottom: 222, height: R.h ?? 375, opacity: m, transform: `translateY(${(1 - m) * 30}px)` }} /> : null}
    <div style={{ position: 'absolute', left: 300, top: 110, fontFamily: H, fontSize: 150, color: CREAM, opacity: interpolate(f, [14, 18], [0, 1], cl), textShadow: chroma(f - 14, 16, 6) }}>{props.big}</div>
    {Lf.label ? <div style={{ position: 'absolute', left: 160, top: 300, fontFamily: H, fontSize: 64, color: GOLD, opacity: r }}>{Lf.label}</div> : null}
    {R.label ? <div style={{ position: 'absolute', right: 200, top: 410, fontFamily: H, fontSize: 64, color: ICE, opacity: m }}>{R.label}</div> : null}
  </AbsoluteFill>;
};

// generic time ranges: {title: "YEARS AGO", from: 400000, to: 0, todayLabel: "TODAY", ticks: [400000, 300000, 200000, 100000, 0],
//   bars: [{label, from, to, color, row}], highlight: {from, to, label}}
const Timeline: React.FC<P> = ({ dur, props }) => {
  const f = useCurrentFrame();
  const a = interpolate(f, [0, 6, dur - 6, dur], [0, 1, 1, 0], cl);
  const lo = props.from ?? 100, hi = props.to ?? 0;
  const X = (y: number) => 160 + ((lo - y) / (lo - hi || 1)) * 1600;
  const ticks: number[] = props.ticks ?? [lo, (lo + hi) / 2, hi];
  const bars: any[] = props.bars ?? [];
  const lbl = (x: number, y: number, t: string, c: string, o = 1, size = 44) => <div style={{ position: 'absolute', left: x, top: y, transform: 'translateX(-50%)', fontFamily: L, fontSize: size, letterSpacing: 2, color: c, opacity: o, whiteSpace: 'nowrap', textShadow: shadow }}>{t}</div>;
  const hl = props.highlight, ho = E((f - 10 - bars.length * 8) / 12);
  return <AbsoluteFill style={{ opacity: a }}>
    <BgVideo props={props} dim={0.28} />
    <div style={{ position: 'absolute', left: 160, top: 110, fontFamily: H, fontSize: 72, color: GOLD }}>{props.title ?? ''}</div>
    <div style={{ position: 'absolute', left: 160, width: 1600, top: 640, height: 3, background: 'rgba(255,255,255,.55)' }} />
    {ticks.map((y) => <React.Fragment key={y}>
      <div style={{ position: 'absolute', left: X(y), top: 630, width: 3, height: 22, background: '#fff' }} />
      {lbl(X(y), 660, y === 0 && props.todayLabel !== '' ? (props.todayLabel ?? 'TODAY') : num(y), '#ddd', 1, 40)}</React.Fragment>)}
    {bars.map((b, i) => {
      const g = E((f - 4 - i * 8) / 18), x0 = X(b.from), x1 = x0 + (X(b.to) - x0) * g, top = 470 + (b.row ?? i) * 82 - 80 * ((bars.length - 1) / 2);
      return <React.Fragment key={i}>
        <div style={{ position: 'absolute', left: Math.min(x0, x1), width: Math.abs(x1 - x0), top, height: 64, background: b.color ?? 'rgba(255,170,80,.85)', borderRadius: 6 }} />
        {lbl((x0 + x1) / 2, top - 52, b.label, b.color ?? GOLD, g, 40)}</React.Fragment>;
    })}
    {hl ? <>
      <div style={{ position: 'absolute', left: X(hl.from), width: X(hl.to) - X(hl.from), top: 400, height: 240, border: `4px dashed ${CREAM}`, borderRadius: 10, opacity: ho, background: 'rgba(255,255,255,.08)' }} />
      {lbl((X(hl.from) + X(hl.to)) / 2, 320, hl.label ?? '', CREAM, ho, 60)}</> : null}
  </AbsoluteFill>;
};

// route on any map image: {img: "ref/map.jpg", points: [{x: 0.42, y: 0.71, label: "AFRICA"}, ...] (fractions of the frame), note}
const MapG: React.FC<P> = ({ dur, props }) => {
  const f = useCurrentFrame();
  const a = interpolate(f, [0, 8, dur - 6, dur], [0, 1, 1, 0], cl);
  const pts: any[] = (props.points ?? []).map((p: any) => ({ ...p, X: p.x * 1920, Y: p.y * 1080 }));
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p.X},${p.Y}`).join(' ');
  const p = E((f - 6) / 36);
  const z = 1 + 0.06 * (f / dur);
  return <AbsoluteFill style={{ background: '#081019', opacity: a, overflow: 'hidden' }}>
    {props.img ? <Img src={staticFile(props.img)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${z})`, filter: 'saturate(0.6) brightness(0.7)' }} /> : null}
    <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, transform: `scale(${z})` }}>
      <defs><filter id="gl"><feGaussianBlur stdDeviation="6" /></filter></defs>
      {pts.length > 1 ? <>
        <path d={d} fill="none" style={{ stroke: GOLD }} strokeWidth={8} strokeDasharray="4000" strokeDashoffset={4000 * (1 - p)} strokeLinecap="round" filter="url(#gl)" opacity={0.6} />
        <path d={d} fill="none" style={{ stroke: GOLD }} strokeWidth={5} strokeDasharray="4000" strokeDashoffset={4000 * (1 - p)} strokeLinecap="round" /></> : null}
      {pts.map((q, i) => { const o = pts.length > 1 ? E((p * (pts.length - 1) - i + 1) * 2) : 1; return <g key={i} opacity={o}>
        <circle cx={q.X} cy={q.Y} r={14} style={{ fill: i ? ICE : GOLD }} />
        <text x={q.X + 30} y={q.Y + 14} fontFamily={H} fontSize={64} style={{ fill: CREAM }}>{q.label}</text></g>; })}
    </svg>
    {props.note ? <div style={{ position: 'absolute', left: 120, top: 90, fontFamily: L, fontSize: 52, letterSpacing: 6, color: '#dff3ff' }}>{props.note}</div> : null}
  </AbsoluteFill>;
};

// big percentage with a 100-cell grid: {value: 2, label: "OF CUBS REACH ADULTHOOD", punch: "THE REST NEVER DO", punchAt: frames, bg}
const Percent: React.FC<P> = ({ dur, props }) => {
  const f = useCurrentFrame();
  const a = interpolate(f, [0, 6, dur - 8, dur], [0, 1, 1, 0], cl);
  const v = props.value ?? 2;
  const n = Math.min(v, Math.round(E(f / 16) * v * 10) / 10);
  const at = props.punchAt ?? Math.round(dur * 0.55);
  const y = E((f - at) / 9);
  return <AbsoluteFill style={{ opacity: a }}>
    <BgVideo props={props} dim={0.4} blur={4} />
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ fontFamily: H, fontSize: 300, lineHeight: 0.95, color: GOLD, textShadow: `0 0 60px rgba(255,190,90,.6), ${chroma(f, 20, 8)}` }}>{n.toFixed(n < v || v % 1 ? 1 : 0)}%</div>
      <div style={{ fontFamily: L, fontSize: 80, letterSpacing: 8, color: CREAM, textShadow: shadow }}>{props.label}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(50, 22px)', gap: 6, marginTop: 30 }}>
        {Array.from({ length: 100 }, (_, i) => <div key={i} style={{ width: 22, height: 22, borderRadius: 4, background: i < Math.round(v) ? GOLD : 'rgba(255,255,255,.18)', opacity: E((f - i * 0.2) / 5) }} />)}
      </div>
      {props.punch ? <div style={{ marginTop: 36, fontFamily: H, fontSize: 110, color: '#fff', opacity: y, transform: `scale(${0.8 + 0.2 * EB(y)})`, textShadow: `0 0 40px rgba(255,190,90,.7), ${chroma(f - at, 16, 6)}` }}>{props.punch}</div> : null}
    </AbsoluteFill>
  </AbsoluteFill>;
};

// generic full-screen text card: {kicker, title, sub, bg}
const Card: React.FC<P> = ({ dur, props }) => {
  const { f, a } = useIO(dur, 6, 8);
  const p = E((f - 3) / 10);
  return <AbsoluteFill>
    <BgVideo props={props} dim={0.38} />
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', opacity: a, textAlign: 'center', padding: '0 160px' }}>
      {props.kicker ? <div style={{ fontFamily: L, fontSize: 52, letterSpacing: 14, color: GOLD }}>{props.kicker}</div> : null}
      <div style={{ fontFamily: H, fontSize: 140, lineHeight: 1.02, color: CREAM, opacity: p, transform: `scale(${0.9 + 0.1 * EB(p)})`, textShadow: chroma(f - 3, 18, 7) }}>{props.title}</div>
      {props.sub ? <div style={{ fontFamily: T, fontWeight: 800, fontSize: 44, color: ICE, marginTop: 18, opacity: E((f - 10) / 8) }}>{props.sub}</div> : null}
    </AbsoluteFill>
  </AbsoluteFill>;
};

// {name: "CHANNEL", tagline, cta: "SUBSCRIBE", next: "SEE YOU IN THE NEXT VIDEO", bg}
const EndCard: React.FC<P> = ({ dur, props }) => {
  const f = useCurrentFrame();
  const a = interpolate(f, [0, 8, dur - 20, dur], [0, 1, 1, 0], cl);
  const b = EB((f - 14) / 10);
  const click = f > 52 && f < 60 ? 0.92 : 1;
  const subbed = f >= 56;
  return <AbsoluteFill style={{ opacity: a }}>
    <BgVideo props={props} dim={0.45} blur={2} />
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ fontFamily: H, fontSize: 170, letterSpacing: 14, color: CREAM, textShadow: `0 0 50px rgba(255,150,60,.6), ${chroma(f, 20, 8)}` }}>{props.name ?? ''}</div>
      {props.tagline ? <div style={{ fontFamily: L, fontSize: 56, letterSpacing: 10, color: GOLD, marginTop: -10 }}>{props.tagline}</div> : null}
      <div style={{ marginTop: 50, transform: `scale(${Math.max(0, b) * click})`, background: subbed ? '#3a3a3a' : '#ff0033', color: '#fff', fontFamily: H, fontSize: 64, padding: '6px 64px', borderRadius: 50 }}>{subbed ? `${props.cta ?? 'SUBSCRIBE'}D ✓` : (props.cta ?? 'SUBSCRIBE')}</div>
      <div style={{ marginTop: 30, fontFamily: L, fontSize: 56, letterSpacing: 6, color: CREAM, opacity: interpolate(f, [24, 30], [0, 1], cl) }}>{props.next ?? 'SEE YOU IN THE NEXT VIDEO'}</div>
    </AbsoluteFill>
  </AbsoluteFill>;
};

const Black: React.FC<P> = () => <AbsoluteFill style={{ background: '#000' }} />;

export const FULLS: Record<string, React.FC<P>> = {
  title: Title, compare: Compare, scale: Scale, timeline: Timeline, map: MapG, percent: Percent, dna: Percent,
  card: Card, endcard: EndCard, black: Black,
};
