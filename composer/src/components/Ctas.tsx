import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Cta, Theme } from "../types";

// CTAs sit at the vertical centre: bottom-pinned text collides with platform UI
// and captions, and the centre is where the viewer is already looking.
const CtaItem: React.FC<{ cta: Cta; theme: Theme }> = ({ cta, theme }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const unit = width / (height > width ? 1080 : 1920);
  const enter = spring({ frame: frame - cta.from, fps, config: { damping: 12, stiffness: 160 } });
  const opacity = interpolate(frame, [cta.from, cta.from + 6, cta.to - 8, cta.to], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const pulse = 1 + 0.03 * Math.sin((frame - cta.from) / 5);
  const isButton = cta.kind !== "comment";
  return (
    <div
      style={{
        position: "absolute",
        top: "50%",
        left: "50%",
        opacity,
        transform: `translate(-50%, -50%) scale(${(0.7 + 0.3 * enter) * pulse})`,
        padding: `${22 * unit}px ${44 * unit}px`,
        borderRadius: isButton ? 999 : 28 * unit,
        background: isButton ? theme.accentColor : "rgba(255,255,255,0.96)",
        color: isButton ? "#fff" : "#111",
        fontSize: 52 * unit,
        fontWeight: 800,
        textAlign: "center",
        maxWidth: "84%",
        boxShadow: "0 12px 40px rgba(0,0,0,0.45)",
      }}
    >
      {cta.text}
    </div>
  );
};

export const Ctas: React.FC<{ ctas: Cta[]; theme: Theme }> = ({ ctas, theme }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {ctas.filter((c) => frame >= c.from && frame < c.to).map((c, i) => (
        <CtaItem key={`${c.from}-${i}`} cta={c} theme={theme} />
      ))}
    </AbsoluteFill>
  );
};
