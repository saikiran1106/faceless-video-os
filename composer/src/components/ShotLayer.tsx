import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, Sequence, staticFile, useCurrentFrame } from "remotion";
import { Shot, Transition } from "../types";

// Every move decelerates: it starts with energy and settles, which reads as a
// camera operator easing off rather than a slideshow's constant crawl.
const settle = Easing.bezier(0.33, 0, 0.2, 1);

function cameraTransform(kind: Shot["camera"]["kind"], intensity: number, p: number): string {
  const amount = 0.06 + 0.1 * intensity; // 0.06 .. 0.16 scale travel
  const t = settle(Math.min(1, Math.max(0, p)));
  // CSS applies translate before scale, so a shift of x% moves the picture by
  // (1+amount)*x%. Keep that inside the (amount/2) overflow on each side, with a
  // small margin, so a pan never reveals the frame edge.
  const pan = ((amount / 2) / (1 + amount)) * 100 * 0.9;
  switch (kind) {
    case "push_in":
      return `scale(${1 + amount * t})`;
    case "pull_out":
      return `scale(${1 + amount * (1 - t)})`;
    case "pan_left":
      return `scale(${1 + amount}) translateX(${pan * (1 - 2 * t)}%)`;
    case "pan_right":
      return `scale(${1 + amount}) translateX(${-pan * (1 - 2 * t)}%)`;
    case "pan_up":
      return `scale(${1 + amount}) translateY(${pan * (1 - 2 * t)}%)`;
    case "pan_down":
      return `scale(${1 + amount}) translateY(${-pan * (1 - 2 * t)}%)`;
    case "drift":
      return `scale(${1 + amount * 0.6 * t + 0.03}) translate(${-pan * 0.4 * t}%, ${-pan * 0.25 * t}%)`;
    case "static":
    default:
      return "scale(1.02)";
  }
}

const Placeholder: React.FC<{ id: string }> = ({ id }) => (
  <AbsoluteFill style={{ background: "linear-gradient(160deg,#1d2b64,#f8cdda)", alignItems: "center", justifyContent: "center" }}>
    <div style={{ color: "white", fontSize: 64, fontWeight: 800, opacity: 0.6 }}>{id}</div>
  </AbsoluteFill>
);

const Inner: React.FC<{ shot: Shot; lead: number; total: number; outTransition?: Transition; outFrames: number }> = ({ shot, lead, total, outTransition, outFrames }) => {
  const frame = useCurrentFrame();
  const tf = shot.transitionFrames;
  let opacity = 1;
  if (shot.transition === "crossfade" && lead > 0) {
    opacity = interpolate(frame, [0, lead], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  }
  // Black dip: fade the outgoing shot to black, then the incoming shot up from black.
  let black = 0;
  if (shot.transition === "dip_to_black") {
    black = interpolate(frame, [0, tf / 2], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  }
  if (outTransition === "dip_to_black") {
    black = Math.max(black, interpolate(frame, [total - outFrames / 2, total], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  }
  const white = shot.transition === "flash" ? interpolate(frame, [0, tf], [0.9, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
  const transform = cameraTransform(shot.camera.kind, shot.camera.intensity ?? 0.5, frame / Math.max(1, total));

  return (
    <AbsoluteFill style={{ opacity, overflow: "hidden" }}>
      <AbsoluteFill style={{ transform, transformOrigin: "50% 50%" }}>
        {shot.src ? <Img src={staticFile(shot.src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <Placeholder id={shot.id} />}
      </AbsoluteFill>
      {black > 0 ? <AbsoluteFill style={{ backgroundColor: "#000", opacity: black }} /> : null}
      {white > 0 ? <AbsoluteFill style={{ backgroundColor: "#fff", opacity: white }} /> : null}
    </AbsoluteFill>
  );
};

export const ShotLayer: React.FC<{ shot: Shot; isFirst: boolean; outTransition?: Transition; outFrames: number }> = ({ shot, isFirst, outTransition, outFrames }) => {
  // A crossfade starts the incoming image `transitionFrames` early so it is fully
  // visible exactly when its narration line begins.
  const lead = !isFirst && shot.transition === "crossfade" ? Math.min(shot.transitionFrames, shot.from) : 0;
  const from = shot.from - lead;
  const total = shot.durationInFrames + lead;
  return (
    <Sequence from={from} durationInFrames={total} name={shot.id}>
      <Inner shot={shot} lead={lead} total={total} outTransition={outTransition} outFrames={outFrames} />
    </Sequence>
  );
};
