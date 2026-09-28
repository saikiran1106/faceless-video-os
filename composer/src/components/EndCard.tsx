import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Theme } from "../types";

export const EndCard: React.FC<{ channelName: string; line: string; theme: Theme; platform: string }> = ({ channelName, line, theme, platform }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const unit = width / (height > width ? 1080 : 1920);
  const dim = interpolate(frame, [0, 12], [0, 0.72], { extrapolateRight: "clamp" });
  const enter = spring({ frame: frame - 6, fps, config: { damping: 14 } });
  const button = platform === "youtube" ? "SUBSCRIBE" : "FOLLOW";
  return (
    <AbsoluteFill style={{ backgroundColor: `rgba(0,0,0,${dim})`, alignItems: "center", justifyContent: "center" }}>
      <div style={{ opacity: enter, transform: `translateY(${(1 - enter) * 40}px)`, textAlign: "center", color: "#fff" }}>
        <div style={{ fontSize: 88 * unit, fontWeight: 900, letterSpacing: 1 }}>{channelName}</div>
        <div style={{ fontSize: 46 * unit, fontWeight: 600, marginTop: 18 * unit, opacity: 0.92 }}>{line}</div>
        <div
          style={{
            display: "inline-block",
            marginTop: 40 * unit,
            padding: `${20 * unit}px ${56 * unit}px`,
            borderRadius: 999,
            background: theme.accentColor,
            fontSize: 48 * unit,
            fontWeight: 900,
            transform: `scale(${1 + 0.04 * Math.sin(frame / 6)})`,
          }}
        >
          {button}
        </div>
      </div>
    </AbsoluteFill>
  );
};
