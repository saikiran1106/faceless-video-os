import React from "react";
import { CalculateMetadataFunction, Composition } from "remotion";
import { StoryVideo } from "./StoryVideo";
import { StoryProps } from "./types";
import { demoProps } from "./demo";

// Size and length come from the props file, so one composition renders any
// project, any format (9:16 or 16:9) and any duration.
const calculateMetadata: CalculateMetadataFunction<StoryProps> = ({ props }) => ({
  durationInFrames: Math.max(1, props.durationInFrames),
  fps: props.fps,
  width: props.width,
  height: props.height,
});

export const Root: React.FC = () => (
  <Composition
    id="StoryVideo"
    component={StoryVideo}
    defaultProps={demoProps}
    calculateMetadata={calculateMetadata}
    durationInFrames={demoProps.durationInFrames}
    fps={demoProps.fps}
    width={demoProps.width}
    height={demoProps.height}
  />
);
