// Mirrors the props written by `faceless compose props` (faceless/compose.py).
// Every number here is a FRAME, already computed in Python.

export type CameraKind =
  | "push_in"
  | "pull_out"
  | "pan_left"
  | "pan_right"
  | "pan_up"
  | "pan_down"
  | "drift"
  | "static";

export type Transition = "crossfade" | "cut" | "dip_to_black" | "flash";

export interface Shot {
  id: string;
  src: string;
  from: number;
  durationInFrames: number;
  camera: { kind: CameraKind; intensity?: number };
  transition: Transition;
  transitionFrames: number;
}

export interface CaptionWord {
  text: string;
  from: number;
  to: number;
}

export interface CaptionPage {
  from: number;
  to: number;
  words: CaptionWord[];
}

export type OverlayStyle = "title" | "stat" | "lower_third" | "quote" | "label";

export interface Overlay {
  text: string;
  style: OverlayStyle;
  from: number;
  to: number;
}

export interface Cta {
  kind: "subscribe" | "comment" | "follow";
  text: string;
  from: number;
  to: number;
}

export interface Theme {
  fontFamily: string;
  fontSrc: string;
  captionColor: string;
  highlightColor: string;
  accentColor: string;
}

export type StoryProps = {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  narrationFrames: number;
  platform: "youtube" | "instagram" | "tiktok";
  narration: { src: string };
  music: { src: string; volume: number } | null;
  shots: Shot[];
  captions: { enabled: boolean; yPercent: number; fontSize: number; pages: CaptionPage[] };
  overlays: Overlay[];
  ctas: Cta[];
  endCard: { from: number; durationInFrames: number; channelName: string; line: string } | null;
  theme: Theme;
};
