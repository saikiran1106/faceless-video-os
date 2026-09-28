import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { StoryProps, Theme } from "../types";

const outline = (px: number) =>
  [
    `${px}px ${px}px 0 #000`,
    `-${px}px ${px}px 0 #000`,
    `${px}px -${px}px 0 #000`,
    `-${px}px -${px}px 0 #000`,
    `0 ${px * 2}px ${px * 4}px rgba(0,0,0,0.6)`,
  ].join(", ");

export const Captions: React.FC<{ captions: StoryProps["captions"]; theme: Theme; hideFrom: number }> = ({ captions, theme, hideFrom }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  if (frame >= hideFrom) return null;
  const page = captions.pages.find((p) => frame >= p.from && frame < p.to);
  if (!page) return null;
  const pop = spring({ frame: frame - page.from, fps, config: { damping: 14, stiffness: 180 }, durationInFrames: 8 });
  const scale = interpolate(pop, [0, 1], [0.88, 1]);
  const size = captions.fontSize * (width / (width > 1400 ? 1920 : 1080));

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          top: `${captions.yPercent}%`,
          left: "50%",
          width: "88%",
          transform: `translate(-50%, -50%) scale(${scale})`,
          textAlign: "center",
          fontSize: size,
          fontWeight: 800,
          lineHeight: 1.18,
          color: theme.captionColor,
          textShadow: outline(Math.max(2, size / 22)),
        }}
      >
        {page.words.map((w, i) => {
          const active = frame >= w.from && frame < w.to;
          return (
            <span
              key={`${page.from}-${i}`}
              style={{
                color: active ? theme.highlightColor : theme.captionColor,
                display: "inline-block",
                transform: active ? "scale(1.07)" : "none",
                marginRight: "0.28em",
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
