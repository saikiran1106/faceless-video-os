import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Overlay, Theme } from "../types";

const fade = (frame: number, from: number, to: number) =>
  interpolate(frame, [from, from + 8, to - 8, to], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const OverlayItem: React.FC<{ overlay: Overlay; theme: Theme }> = ({ overlay, theme }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const vertical = height > width;
  const unit = width / (vertical ? 1080 : 1920);
  const opacity = fade(frame, overlay.from, overlay.to);
  const enter = spring({ frame: frame - overlay.from, fps, config: { damping: 16 } });
  const base: React.CSSProperties = { position: "absolute", opacity, color: "#fff", fontWeight: 800, textAlign: "center" };

  switch (overlay.style) {
    case "title":
      return (
        <div style={{ ...base, top: vertical ? "12%" : "10%", left: "50%", width: "86%", transform: `translate(-50%, ${(1 - enter) * -30}px)`, fontSize: 84 * unit, lineHeight: 1.08, textShadow: "0 6px 24px rgba(0,0,0,0.7)" }}>
          {overlay.text}
          <div style={{ margin: `${14 * unit}px auto 0`, width: `${220 * enter * unit}px`, height: 8 * unit, background: theme.accentColor, borderRadius: 4 }} />
        </div>
      );
    case "stat":
      return (
        <div style={{ ...base, top: "50%", left: "50%", transform: `translate(-50%, -50%) scale(${0.85 + 0.15 * enter})`, fontSize: 120 * unit, padding: `${24 * unit}px ${48 * unit}px`, background: "rgba(0,0,0,0.62)", borderRadius: 28 * unit, border: `${4 * unit}px solid ${theme.accentColor}` }}>
          {overlay.text}
        </div>
      );
    case "lower_third":
      return (
        <div style={{ ...base, textAlign: "left", left: "6%", top: vertical ? "24%" : "72%", transform: `translateX(${(1 - enter) * -60}px)`, fontSize: 46 * unit, padding: `${12 * unit}px ${26 * unit}px`, background: "rgba(0,0,0,0.7)", borderLeft: `${10 * unit}px solid ${theme.accentColor}` }}>
          {overlay.text}
        </div>
      );
    case "quote":
      return (
        <AbsoluteFill style={{ opacity, background: "rgba(0,0,0,0.55)", alignItems: "center", justifyContent: "center" }}>
          <div style={{ width: "80%", color: "#fff", fontSize: 64 * unit, fontStyle: "italic", fontWeight: 700, textAlign: "center", lineHeight: 1.2 }}>
            <span style={{ color: theme.accentColor }}>“</span>
            {overlay.text}
            <span style={{ color: theme.accentColor }}>”</span>
          </div>
        </AbsoluteFill>
      );
    case "label":
    default:
      return (
        <div style={{ ...base, left: "5%", top: vertical ? "8%" : "6%", fontSize: 36 * unit, padding: `${8 * unit}px ${22 * unit}px`, background: theme.accentColor, borderRadius: 999 }}>
          {overlay.text}
        </div>
      );
  }
};

export const Overlays: React.FC<{ overlays: Overlay[]; theme: Theme }> = ({ overlays, theme }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {overlays.filter((o) => frame >= o.from && frame < o.to).map((o, i) => (
        <OverlayItem key={`${o.from}-${i}`} overlay={o} theme={theme} />
      ))}
    </AbsoluteFill>
  );
};
