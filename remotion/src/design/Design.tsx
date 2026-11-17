import React from "react";
import { AbsoluteFill, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Glitch, Grain, Icon3D, LightLeak, Vignette, clamp, eOut, ramp } from "./fx";
import { EndStack, SCENES } from "./scenes";
import { Brand, DEFAULT } from "./theme";
import { CapGroup, PhraseCaption, Stepper, TitleStack } from "./type";
import { ChapterBadge, ColorCard, Countdown, Counter, GrowCard, Halo, KeywordCaption, LabelStack, LineIcon, NeonCaption, SearchCTA, SelectionBox, SlamCaption, TierCaption, TileRow } from "./graphics";
import { ColourWash, FilmBurn, LeakDip, SmokeFlash, frameTreatment } from "./motion";
import { EXPLAINER, FloatChips } from "./explainer";

// The design compositor: takes the clean speaker cut (picture only) and builds the finished
// picture around it. Everything is data from the EDL's `design` block (see references/design-system.md).
type Span = { s: number; e: number };
export type Layout = Span & { mode: "full" | "split" | "hidden"; zoom?: number };
export type SceneSpec = Span & { type: string; p: Record<string, any> };
export type Overlay = Span & { type: string; p: Record<string, any>; behind?: boolean };
export type Fx = { at: number; type: string; dur?: number; color?: string; dir?: string; from?: string };
export type CapStyle = "phrase" | "slam" | "neon" | "keyword" | "tier";
// background treatment behind the matted speaker: "bw" or a CSS colour (vepro red room)
export type BgSpan = Span & { color: string };
export type DesignProps = {
  fps: number; width: number; height: number; durationInFrames: number;
  base: string; faceY: number; brand?: Partial<Brand>;
  layout: Layout[]; scenes: SceneSpec[]; captions: CapGroup[]; overlays: Overlay[]; fx: Fx[];
  capStyle?: CapStyle; capSize?: number; capPalette?: string[]; capY?: number; matte?: string | null; bg?: BgSpan[];
};

const SPLIT_FACE_AT = 0.62; // STARTING DEFAULT: face centre as a fraction of the lower half (QC caught captions over the head at 0.5)
const SPLIT_SCALE = 0.62;   // STARTING DEFAULT: the cut arrives punched in; at 1.0 only part of the face fit the half

// caption centre per layout; render.py mirrors these in DESIGN_CAP_Y for QC
const FEATHER = "linear-gradient(90deg, transparent 0%, #000 12%, #000 88%, transparent 100%), linear-gradient(180deg, transparent 0%, #000 14%, #000 100%)";
export const CAP_Y = { full: 0.7, split: 0.45, hidden: 0.86 };
export const CAP_Y_SLAM = 0.2; // STARTING DEFAULT: one-word slams sit in the top third, above or behind the head (marcel)

const at = <T extends Span>(xs: T[], f: number) => xs.find((x) => f >= x.s && f < x.e);

// Whole-frame transition treatment around fx markers.
const fxStyle = (fx: Fx[], f: number): { transform: string; filter: string; flash: number; glitch: boolean } => {
  let scale = 1, blur = 0, flash = 0, glitch = false, bright = 1;
  for (const x of fx) {
    const k = f - x.at;
    if (x.type === "zoomblur" && k >= -4 && k < 6) {
      if (k < 0) { const p = (k + 4) / 4; scale *= 1 + 0.12 * p * p; blur = Math.max(blur, 18 * p * p); }
      else { const p = 1 - k / 6; scale *= 1 + 0.14 * p * p; blur = Math.max(blur, 22 * p * p); }
    }
    if (x.type === "flash" && k >= 0 && k < 6) flash = Math.max(flash, 1 - k / 6);
    if (x.type === "glitch" && k >= 0 && k < (x.dur ?? 4)) glitch = true;
    if (x.type === "matte" && k >= 0 && k < 6) {
      // hook reveal: crushed blur -> white matte -> soft -> matte -> sharp
      const seq = [[28, 0.45, 0], [0, 1, 0.95], [12, 1, 0], [0, 1, 0.7], [4, 1, 0], [0, 1, 0]];
      blur = Math.max(blur, seq[k][0]); bright = seq[k][1]; flash = Math.max(flash, seq[k][2]);
      scale *= 1 + 0.12 * (1 - k / 6);
    }
  }
  return { transform: `scale(${scale})`, filter: `blur(${blur}px) brightness(${bright})`, flash, glitch };
};

// The matted speaker (VP9 with alpha from scripts/matte.py), drawn over the behind-layers with the
// same transform as the full-mode speaker. Split and hidden spans draw nothing.
const SpeakerFG: React.FC<{ src: string; layout: Layout[]; faceY: number }> = ({ src, layout, faceY }) => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const L = at(layout, f) ?? { s: 0, e: 0, mode: "full" as const };
  const z = L.zoom ?? 1;
  const zk = z === 1 ? 1 : interpolate(f, [L.s, L.s + 6], [1, z], { ...clamp, easing: eOut });
  return <OffthreadVideo src={staticFile(src)} muted transparent style={{ position: "absolute", width, height, transform: `scale(${zk})`,
    transformOrigin: `50% ${faceY * 100}%`, opacity: L.mode === "full" ? 1 : 0 }} />;
};

const Speaker: React.FC<{ src: string; layout: Layout[]; faceY: number }> = ({ src, layout, faceY }) => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const L = at(layout, f) ?? { s: 0, e: 0, mode: "full" as const };
  if (L.mode === "hidden") return <OffthreadVideo src={staticFile(src)} muted style={{ display: "none" }} />;
  const z = L.zoom ?? 1;
  const zk = z === 1 ? 1 : interpolate(f, [L.s, L.s + 6], [1, z], { ...clamp, easing: eOut });
  if (L.mode === "split") {
    // speaker shrunk into the lower half (the cut is often already punched in), sides filled with a
    // blurred, darkened copy of the same frame; face 60% down for headroom
    const sc = SPLIT_SCALE * zk;
    const top = SPLIT_FACE_AT * (height / 2) - faceY * height * sc;
    return (
      <div style={{ position: "absolute", left: 0, top: height / 2, width, height: height / 2, overflow: "hidden", background: "#07060c" }}>
        <OffthreadVideo src={staticFile(src)} muted style={{ position: "absolute", left: -width * 0.1, top: -height * 0.25, width: width * 1.2, height: height * 1.2,
          filter: "blur(40px) brightness(0.45) saturate(1.2)" }} />
        <OffthreadVideo src={staticFile(src)} muted style={{ position: "absolute", left: (width - width * sc) / 2, top, width: width * sc, height: height * sc,
          WebkitMaskImage: FEATHER, maskImage: FEATHER, WebkitMaskComposite: "source-in", maskComposite: "intersect" } as React.CSSProperties} />
        <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 6, background: "rgba(0,0,0,0.6)" }} />
      </div>
    );
  }
  return <OffthreadVideo src={staticFile(src)} muted style={{ position: "absolute", width, height, transform: `scale(${zk})`, transformOrigin: `50% ${faceY * 100}%` }} />;
};

const renderOverlay = (o: Overlay, brand: Brand) => {
  const d = o.e - o.s, p = o.p as any;
  switch (o.type) {
    case "TitleStack": return <TitleStack {...p} brand={brand} dur={d} />;
    case "Stepper": return <Stepper {...p} brand={brand} dur={d} />;
    case "EndStack": return <EndStack {...p} brand={brand} dur={d} />;
    case "Icon": return <Icon3D {...p} />;
    case "Counter": return <Counter {...p} brand={brand} dur={d} />;
    case "SelectionBox": return <SelectionBox {...p} brand={brand} dur={d} />;
    case "Halo": return <Halo {...p} brand={brand} dur={d} />;
    case "ChapterBadge": return <ChapterBadge {...p} brand={brand} dur={d} />;
    case "Countdown": return <Countdown {...p} brand={brand} dur={d} />;
    case "TileRow": return <TileRow {...p} brand={brand} dur={d} />;
    case "LabelStack": return <LabelStack {...p} brand={brand} dur={d} />;
    case "SearchCTA": return <SearchCTA {...p} brand={brand} dur={d} />;
    case "ColorCard": return <ColorCard {...p} dur={d} />;
    case "LineIcon": return <LineIcon {...p} brand={brand} dur={d} />;
    case "GrowCard": return <GrowCard {...p} dur={d} />;
    case "FloatChips": return <FloatChips {...p} brand={brand} dur={d} />;
    default: return null;
  }
};

export const Design: React.FC<DesignProps> = (props) => {
  const f = useCurrentFrame();
  const { height } = useVideoConfig();
  const brand: Brand = { ...DEFAULT, ...(props.brand ?? {}) };
  const st = fxStyle(props.fx, f);
  const tr = frameTreatment(props.fx, f);
  const capIdx = props.captions.findIndex((c) => f >= c.s && f < c.e);
  const cap = capIdx >= 0 ? props.captions[capIdx] : undefined;
  // a caption keeps one position for its whole life: the layout at its midpoint (render.py does the same for QC)
  const mode = cap ? (at(props.layout, Math.floor((cap.s + cap.e) / 2))?.mode ?? "full") : "full";
  const style = props.capStyle ?? "phrase";
  const capY = props.capY && mode === "full" ? props.capY : style === "slam" && mode === "full" ? CAP_Y_SLAM : mode === "split" ? CAP_Y.split : mode === "hidden" ? CAP_Y.hidden : CAP_Y.full;
  const bg = props.bg ? at(props.bg, f) : undefined;
  // without a matte, "behind" overlays are drawn in front (there is nothing to hide them behind)
  const layer = (behind: boolean) => props.overlays.filter((o) => (props.matte ? !!o.behind === behind : !behind)).map((o, i) => (
    <Sequence key={`o${behind ? "b" : "f"}${i}`} from={o.s} durationInFrames={o.e - o.s} layout="none">{renderOverlay(o, brand)}</Sequence>
  ));
  const body = (
    <AbsoluteFill style={{ backgroundColor: "#07060c" }}>
      <Speaker src={props.base} layout={props.layout} faceY={props.faceY} />
      {props.scenes.map((sc, i) => {
        const C = SCENES[sc.type] ?? EXPLAINER[sc.type];
        const lm = at(props.layout, sc.s)?.mode ?? "hidden";
        const h = lm === "split" ? height / 2 : height;
        return C ? (
          <Sequence key={i} from={sc.s} durationInFrames={sc.e - sc.s} layout="none">
            <div style={{ position: "absolute", left: 0, top: 0, right: 0, height: h, overflow: "hidden" }}>
              <C dur={sc.e - sc.s} h={h} brand={brand} p={sc.p} />
            </div>
          </Sequence>
        ) : null;
      })}
      {bg && props.matte ? <AbsoluteFill style={bg.color === "bw" ? { backdropFilter: "grayscale(1) contrast(1.15)" } : { background: bg.color, mixBlendMode: "color", opacity: 0.85 }} /> : null}
      <Vignette strength={0.45} />
    </AbsoluteFill>
  );
  return (
    <AbsoluteFill style={{ backgroundColor: "#000", overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `${st.transform} translate(${tr.tx}px, ${tr.ty}px)`, filter: `${st.filter} brightness(${tr.bright})` }}>
        <AbsoluteFill style={{ filter: `grayscale(${tr.gray}) blur(${tr.blur}px)`, transform: `scale(${tr.scale})` }}>
          <Glitch active={st.glitch} seed="fx">{body}</Glitch>
          {props.matte ? layer(true) : null}
          {props.matte ? <SpeakerFG src={props.matte} layout={props.layout} faceY={props.faceY} /> : null}
        </AbsoluteFill>
        {layer(false)}
        {cap ? <Sequence from={cap.s} durationInFrames={cap.e - cap.s} layout="none"><CapAbs g={cap} y={capY} brand={brand} style={style} size={props.capSize} index={capIdx} palette={props.capPalette} /></Sequence> : null}
      </AbsoluteFill>
      {props.fx.filter((x) => x.type === "leak").map((x, i) => (
        <Sequence key={`l${i}`} from={x.at} durationInFrames={x.dur ?? 14} layout="none"><LightLeak dur={x.dur ?? 14} /></Sequence>
      ))}
      {props.fx.map((x, i) => x.type === "leakdip" ? <LeakDip key={`d${i}`} at={x.at} />
        : x.type === "smoke" ? <SmokeFlash key={`s${i}`} at={x.at} seed={i + 2} />
        : x.type === "wash" ? <ColourWash key={`w${i}`} at={x.at} color={x.color ?? brand.accent} from={(x.from as any) ?? "bl"} />
        : x.type === "burn" ? <FilmBurn key={`b${i}`} at={x.at} /> : null)}
      <AbsoluteFill style={{ background: "#fff", opacity: Math.max(st.flash, tr.veil), pointerEvents: "none" }} />
      <Grain opacity={0.07} />
    </AbsoluteFill>
  );
};

// Captions use absolute timeline frames; inside a Sequence the frame is relative, so shift back.
const CapAbs: React.FC<{ g: CapGroup; y: number; brand: Brand; style: CapStyle; size?: number; index: number; palette?: string[] }> = ({ g, y, brand, style, size, index, palette }) => {
  const rel: CapGroup = { s: 0, e: g.e - g.s, words: g.words.map((w) => ({ ...w, s: w.s - g.s })) };
  if (style === "slam") return <SlamCaption g={rel} y={y} brand={brand} size={size} />;
  if (style === "neon") return <NeonCaption g={rel} y={y} brand={brand} size={size} />;
  if (style === "keyword") return <KeywordCaption g={rel} y={y} brand={brand} size={size} index={index} palette={palette && palette.length ? palette : undefined} />;
  if (style === "tier") return <TierCaption g={rel} y={y} brand={brand} size={size} />;
  return <PhraseCaption g={rel} y={y} brand={brand} size={size ?? 70} />;
};

export const designDefaults: DesignProps = {
  fps: 25, width: 1080, height: 1920, durationInFrames: 100, base: "design/base.mp4", faceY: 0.3,
  layout: [], scenes: [], captions: [], overlays: [], fx: [], capStyle: "phrase", matte: null, bg: [],
};
