import { StoryProps } from "./types";

// Asset-free demo so `npm run studio` shows something before any project exists.
export const demoProps: StoryProps = {
  fps: 30,
  width: 1080,
  height: 1920,
  durationInFrames: 300,
  narrationFrames: 240,
  platform: "youtube",
  narration: { src: "" },
  music: null,
  shots: [
    { id: "KF001", src: "", from: 0, durationInFrames: 90, camera: { kind: "push_in", intensity: 0.6 }, transition: "cut", transitionFrames: 0 },
    { id: "KF002", src: "", from: 90, durationInFrames: 80, camera: { kind: "pan_left", intensity: 0.5 }, transition: "crossfade", transitionFrames: 10 },
    { id: "KF003", src: "", from: 170, durationInFrames: 130, camera: { kind: "pull_out", intensity: 0.5 }, transition: "dip_to_black", transitionFrames: 14 },
  ],
  captions: {
    enabled: true,
    yPercent: 62,
    fontSize: 78,
    pages: [
      { from: 0, to: 45, words: [{ text: "Did", from: 0, to: 12 }, { text: "you", from: 12, to: 22 }, { text: "know?", from: 22, to: 45 }] },
      { from: 45, to: 120, words: [{ text: "This", from: 45, to: 60 }, { text: "changes", from: 60, to: 85 }, { text: "everything.", from: 85, to: 120 }] },
    ],
  },
  overlays: [{ text: "Chapter 1", style: "label", from: 95, to: 160 }],
  ctas: [{ kind: "comment", text: "What would you do?", from: 180, to: 235 }],
  endCard: { from: 240, durationInFrames: 60, channelName: "My Channel", line: "Subscribe for more" },
  theme: { fontFamily: "Inter", fontSrc: "", captionColor: "#FFFFFF", highlightColor: "#FFD400", accentColor: "#E53935" },
};
