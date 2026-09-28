import React from "react";
import { AbsoluteFill, Audio, interpolate, Sequence, staticFile, useVideoConfig } from "remotion";
import { Captions } from "./components/Captions";
import { Ctas } from "./components/Ctas";
import { EndCard } from "./components/EndCard";
import { Overlays } from "./components/Overlays";
import { ShotLayer } from "./components/ShotLayer";
import { useThemeFont } from "./components/useThemeFont";
import { StoryProps } from "./types";

export const StoryVideo: React.FC<StoryProps> = (props) => {
  const fontFamily = useThemeFont(props.theme);
  const { durationInFrames } = useVideoConfig();
  const { shots, captions, endCard } = props;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000", fontFamily }}>
      {shots.map((shot, index) => (
        <ShotLayer key={shot.id} shot={shot} isFirst={index === 0} outTransition={shots[index + 1]?.transition} outFrames={shots[index + 1]?.transitionFrames ?? 0} />
      ))}

      {/* A soft vignette keeps captions legible on any image. */}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%)" }} />

      {props.narration.src ? <Audio src={staticFile(props.narration.src)} /> : null}
      {props.music ? (
        <Audio
          src={staticFile(props.music.src)}
          loop
          volume={(f) =>
            props.music!.volume *
            interpolate(f, [0, 30, durationInFrames - 45, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
          }
        />
      ) : null}

      <Overlays overlays={props.overlays} theme={props.theme} />
      {captions.enabled ? <Captions captions={captions} theme={props.theme} hideFrom={endCard ? endCard.from : Infinity} /> : null}
      <Ctas ctas={props.ctas} theme={props.theme} />
      {endCard && endCard.durationInFrames > 0 ? (
        <Sequence from={endCard.from} durationInFrames={endCard.durationInFrames}>
          <EndCard channelName={endCard.channelName} line={endCard.line} theme={props.theme} platform={props.platform} />
        </Sequence>
      ) : null}
    </AbsoluteFill>
  );
};
