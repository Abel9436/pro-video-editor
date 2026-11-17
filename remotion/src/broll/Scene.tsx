import React from "react";
import { AbsoluteFill, interpolate, random, spring, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { anton, poppins } from "../fonts";

// Shared look for explainer B-roll: deep purple-black stage (matches a dark studio backdrop),
// moving key light, vignette, fine grain, and a punchy entrance (scale + blur settle) so a
// hard cut into the scene reads as intentional.
export const YELLOW = "#FFD400";
export const RED = "#FF3B3B";
export const PURPLE = "#7A5CFF";

export const SceneFrame: React.FC<{ children: React.ReactNode; hue?: string }> = ({ children, hue = PURPLE }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 18, stiffness: 180 } });
  const scale = interpolate(enter, [0, 1], [1.14, 1]);
  const blur = interpolate(frame, [0, 5], [10, 0], { extrapolateRight: "clamp" });
  const lx = 50 + Math.sin(frame / 18) * 12;
  return (
    <AbsoluteFill style={{ backgroundColor: "#06040c", overflow: "hidden" }}>
      <AbsoluteFill style={{ background: `radial-gradient(circle at ${lx}% 38%, ${hue}55 0%, #140c2a 38%, #06040c 75%)` }} />
      <AbsoluteFill style={{ transform: `scale(${scale})`, filter: `blur(${blur}px)` }}>{children}</AbsoluteFill>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.65) 100%)" }} />
      <Grain frame={frame} w={width} h={height} />
    </AbsoluteFill>
  );
};

const Grain: React.FC<{ frame: number; w: number; h: number }> = ({ frame }) => (
  <AbsoluteFill style={{ opacity: 0.07, mixBlendMode: "overlay" }}>
    <svg width="100%" height="100%">
      <filter id={`g${frame % 4}`}>
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={frame % 4} />
      </filter>
      <rect width="100%" height="100%" filter={`url(#g${frame % 4})`} />
    </svg>
  </AbsoluteFill>
);

// Big kinetic label: pops in word by word with overshoot.
export const Label: React.FC<{ text: string; y: number; delay?: number; size?: number; color?: string; sub?: string }> = ({
  text, y, delay = 0, size = 0.085, color = YELLOW, sub }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const words = text.split(" ");
  return (
    <div style={{ position: "absolute", top: y * height, left: "6%", right: "6%", transform: "translateY(-50%)", textAlign: "center" }}>
      <div style={{ fontFamily: anton, fontSize: size * height, lineHeight: 1.0, color, textTransform: "uppercase",
        textShadow: "0 8px 0 rgba(0,0,0,0.45), 0 0 40px rgba(0,0,0,0.6)" }}>
        {words.map((w, i) => {
          const s = spring({ frame: frame - delay - i * 2, fps, config: { damping: 11, stiffness: 240, mass: 0.6 } });
          return <span key={i} style={{ display: "inline-block", marginRight: "0.22em", transform: `translateY(${(1 - s) * 60}px) scale(${0.6 + 0.4 * s})`, opacity: Math.min(1, s * 1.5) }}>{w}</span>;
        })}
      </div>
      {sub ? <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 0.03 * height, color: "#fff", opacity: interpolate(frame - delay, [8, 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }), marginTop: 12 }}>{sub}</div> : null}
    </div>
  );
};

export const shake = (frame: number, at: number, amp = 18, dur = 6) => {
  const k = frame - at;
  if (k < 0 || k > dur) return "translate(0px,0px)";
  const d = (1 - k / dur) * amp;
  return `translate(${(random(`x${frame}`) - 0.5) * 2 * d}px, ${(random(`y${frame}`) - 0.5) * 2 * d}px)`;
};

export const ease = (frame: number, a: number, b: number, from = 0, to = 1) =>
  interpolate(frame, [a, b], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
