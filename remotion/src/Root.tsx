import React from "react";
import { AbsoluteFill, Composition, Sequence } from "remotion";
import { Captions } from "./Captions";
import { Callout, LowerThird, ProgressBar, Title } from "./Graphics";
import { Title3D } from "./Title3D";
import { DEFAULT_BRAND, OverlayProps } from "./types";
import { anton, ethiopic, poppins } from "./fonts";
import { Design, designDefaults, DesignProps } from "./design/Design";
import { AIScam, Apprentice, BrickWall, Millionaire, PayToPlay, Ranks, WordSlam, XStamp, YearsLater } from "./broll/Scenes";

// One transparent composition: captions + graphics from the EDL, rendered as ProRes 4444 with
// alpha and laid over the picture by render.py (graphics engine "remotion").
const Overlay: React.FC<OverlayProps> = ({ cards, graphics, captions, brand }) => {
  const b = { ...DEFAULT_BRAND, captionFont: poppins, headingFont: anton, ethiopicFont: ethiopic, ...(brand ?? {}) };
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {graphics.map((g, i) => {
        const p = (g.props ?? {}) as Record<string, never>;
        const common = { ...p, dur: g.dur_f, brand: b };
        const el = g.component === "Title" ? <Title {...common} />
          : g.component === "Callout" ? <Callout {...common} />
          : g.component === "LowerThird" ? <LowerThird {...common} />
          : g.component === "ProgressBar" ? <ProgressBar {...common} />
          : g.component === "XStamp" ? <XStamp />
          : g.component === "WordSlam" ? <WordSlam text={String((p as Record<string, unknown>).text ?? "")} dur={g.dur_f} />
          : g.component === "Title3D" ? <Title3D {...p} dur={g.dur_f} color={b.primary} />
          : null;
        return el ? <Sequence key={i} from={g.at_f} durationInFrames={g.dur_f}>{el}</Sequence> : null;
      })}
      {captions ? <Captions cards={cards} track={captions} brand={b} /> : null}
    </AbsoluteFill>
  );
};

const defaults: OverlayProps = { fps: 30, width: 1080, height: 1920, durationInFrames: 150, cards: [], graphics: [], captions: null };

// Explainer B-roll scenes, rendered opaque to MP4 and cut in on the broll track.
const SCENES: Record<string, React.FC<Record<string, unknown>>> = {
  AIScam, Millionaire, BrickWall, PayToPlay, Ranks, Apprentice, YearsLater,
} as unknown as Record<string, React.FC<Record<string, unknown>>>;
type BRollProps = { scene: string; fps: number; width: number; height: number; durationInFrames: number; params?: Record<string, unknown> };
const BRoll: React.FC<BRollProps> = ({ scene, params }) => {
  const C = SCENES[scene];
  return C ? <C {...(params ?? {})} /> : <AbsoluteFill style={{ background: "#000" }} />;
};
const brollDefaults: BRollProps = { scene: "AIScam", fps: 25, width: 1080, height: 1920, durationInFrames: 75 };

export const RemotionRoot: React.FC = () => (
  <>
  <Composition
    id="Design"
    component={Design}
    defaultProps={designDefaults}
    durationInFrames={100}
    fps={25}
    width={1080}
    height={1920}
    calculateMetadata={({ props }: { props: DesignProps }) => ({
      durationInFrames: Math.max(1, Math.round(props.durationInFrames)),
      fps: props.fps, width: props.width, height: props.height,
    })}
  />
  <Composition
    id="BRoll"
    component={BRoll}
    defaultProps={brollDefaults}
    durationInFrames={75}
    fps={25}
    width={1080}
    height={1920}
    calculateMetadata={({ props }) => ({
      durationInFrames: Math.max(1, Math.round(props.durationInFrames)),
      fps: props.fps, width: props.width, height: props.height,
    })}
  />
  <Composition
    id="Overlay"
    component={Overlay}
    defaultProps={defaults}
    durationInFrames={defaults.durationInFrames}
    fps={defaults.fps}
    width={defaults.width}
    height={defaults.height}
    calculateMetadata={({ props }) => ({
      durationInFrames: Math.max(1, Math.round(props.durationInFrames)),
      fps: props.fps, width: props.width, height: props.height,
    })}
  />
  </>
);
