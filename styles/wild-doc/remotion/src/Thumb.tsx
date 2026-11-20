// Thumbnail: props {bg: "plates/P25.jpg", lines: [{text, color, size}], tag: "NO WEAPON", align: "center"|"right"}
// Text block is centred vertically (and horizontally by default) so feed/grid crops never cut it.
import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { loadFont as loadAnton } from '@remotion/google-fonts/Anton';
import { loadFont as loadBebas } from '@remotion/google-fonts/BebasNeue';
loadAnton('normal', { weights: ['400'], subsets: ['latin'] });
loadBebas('normal', { weights: ['400'], subsets: ['latin'] });

const st = (c: string) => ({ WebkitTextStroke: '10px #000', paintOrder: 'stroke fill' as const, color: c, textShadow: '0 8px 30px rgba(0,0,0,.9)' });

export const Thumb: React.FC<{ bg: string; lines: { text: string; color?: string; size?: number }[]; tag?: string; align?: string }> = ({ bg, lines, tag, align = 'center' }) =>
  <AbsoluteFill style={{ background: '#000' }}>
    {bg ? <Img src={staticFile(bg)} style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'contrast(1.12) saturate(1.1) brightness(0.95)' }} /> : null}
    <AbsoluteFill style={{ background: align === 'right' ? 'linear-gradient(90deg, rgba(0,0,0,0) 30%, rgba(0,0,0,.78) 68%)' : 'radial-gradient(ellipse at center, rgba(0,0,0,.55) 0%, rgba(0,0,0,.15) 70%)' }} />
    <AbsoluteFill style={{ alignItems: align === 'right' ? 'flex-end' : 'center', justifyContent: 'center', paddingRight: align === 'right' ? 80 : 0, textAlign: 'center' }}>
      {lines.map((l, i) => <div key={i} style={{ fontFamily: 'Anton', fontSize: l.size ?? 150, lineHeight: 1.0, ...st(l.color ?? '#ffffff') }}>{l.text}</div>)}
    </AbsoluteFill>
    {tag ? <div style={{ position: 'absolute', left: 50, top: 46, background: '#e8261b', color: '#fff', fontFamily: 'Bebas Neue', fontSize: 76, letterSpacing: 3, padding: '0 26px', borderRadius: 10 }}>{tag}</div> : null}
  </AbsoluteFill>;
