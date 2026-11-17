import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { fadeIn, fadeOut, popScale, slideIn, strokeShadow } from "./motion";
import { Brand } from "./types";

type P = { text?: string; sub?: string; y?: number; dur: number; brand: Brand };

// Title: the hook's text layer. Staggered word entrance, overshoot, then hold.
export const Title: React.FC<P> = ({ text = "", y = 0.5, dur, brand }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const words = text.split(" ");
  return (
    <AbsoluteFill style={{ opacity: fadeOut(frame, dur) }}>
      <div style={{ position: "absolute", top: y * height, left: width * 0.08, right: width * 0.08, transform: "translateY(-50%)",
        textAlign: "center", fontFamily: brand.headingFont, fontSize: 0.075 * height, lineHeight: 1.05, color: brand.text,
        textTransform: "uppercase", textShadow: strokeShadow(brand.stroke, 5) }}>
        {words.map((w, i) => (
          <span key={i} style={{ display: "inline-block", marginRight: "0.25em",
            transform: `scale(${popScale(frame - i * 2, fps)})`, opacity: fadeIn(frame - i * 2, 3) }}>{w}</span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// Callout: names the key idea as it is said. A brand-colour box that pops in and settles.
export const Callout: React.FC<P> = ({ text = "", y = 0.5, dur, brand }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  return (
    <AbsoluteFill style={{ alignItems: "center", opacity: fadeOut(frame, dur, 3) }}>
      <div style={{ position: "absolute", top: y * height, transform: `translateY(-50%) scale(${popScale(frame, fps)})`,
        background: brand.primary, color: "#111", padding: "0.25em 0.6em", borderRadius: 0.012 * height,
        fontFamily: brand.headingFont, fontSize: 0.05 * height, textTransform: "uppercase",
        boxShadow: "0 12px 30px rgba(0,0,0,0.35)" }}>{text}</div>
    </AbsoluteFill>
  );
};

// LowerThird: name and role. Slides in from the left, out the same way.
export const LowerThird: React.FC<P> = ({ text = "", sub = "", y = 0.78, dur, brand }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const out = interpolate(frame, [dur - 8, dur], [0, -width * 0.6], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.cubic) });
  const x = -slideIn(frame, fps, width * 0.6) + out;
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", top: y * height, left: width * 0.06, transform: `translateX(${x}px)` }}>
        <div style={{ background: brand.primary, height: 6, width: 0.12 * width, marginBottom: 8 }} />
        <div style={{ fontFamily: brand.headingFont, fontSize: 0.036 * height, color: brand.text, textShadow: strokeShadow(brand.stroke, 3) }}>{text}</div>
        {sub ? <div style={{ fontFamily: brand.captionFont, fontSize: 0.022 * height, color: brand.text, opacity: 0.9,
          transform: `translateX(${-slideIn(frame, fps, 60, 4)}px)` }}>{sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

// ProgressBar: a thin bar across the top that fills over the graphic's duration.
export const ProgressBar: React.FC<P> = ({ y = 0.02, dur, brand }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const p = interpolate(frame, [0, dur], [0, 1], { extrapolateRight: "clamp", easing: Easing.inOut(Easing.sin) });
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", top: y * height, left: 0, height: 0.006 * height, width: p * width, background: brand.primary }} />
    </AbsoluteFill>
  );
};
