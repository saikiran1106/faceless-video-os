// Two compositions, both driven entirely by a props file written by `faceless wild-doc plan`:
//   Film  -> props {"plan": <08-compose/plan.json>}
//   Thumb -> props <08-compose/thumb.json>
import React from 'react';
import { Composition, registerRoot } from 'remotion';
import { Film } from './Film';
import { Thumb } from './Thumb';

const EMPTY = { fps: 24, width: 1920, height: 1080, durationInFrames: 48, shots: [], overlays: [], captions: [], chapters: [], theme: {} };

const Root: React.FC = () => <>
  <Composition id="Film" component={Film as any} fps={24} width={1920} height={1080} durationInFrames={48}
    defaultProps={{ plan: EMPTY }}
    calculateMetadata={({ props }: any) => ({
      durationInFrames: props.plan.durationInFrames, fps: props.plan.fps,
      width: props.plan.width ?? 1920, height: props.plan.height ?? 1080,
    })} />
  <Composition id="Thumb" component={Thumb as any} fps={24} width={1920} height={1080} durationInFrames={1}
    defaultProps={{ bg: '', lines: [{ text: 'TITLE', color: '#ffffff', size: 200 }], tag: '' }} />
</>;
registerRoot(Root);
