import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const eOut = Easing.bezier(0.16, 1, 0.3, 1); // expo-out: fast start, long settle
export const eInOut = Easing.bezier(0.65, 0, 0.35, 1);
export const ramp = (f: number, a: number, b: number, from = 0, to = 1, ease = eOut) =>
  interpolate(f, [a, b], [from, to], { ...clamp, easing: ease });
export const pop = (f: number, fps: number, damping = 14, stiffness = 220, mass = 0.7) =>
  spring({ frame: f, fps, config: { damping, stiffness, mass } });

// Film grain: animated fractal noise at low opacity, 4-frame cycle.
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.06 }) => {
  const f = useCurrentFrame() % 6;
  return (
    <AbsoluteFill style={{ opacity, mixBlendMode: "overlay", pointerEvents: "none" }}>
      <svg width="100%" height="100%">
        <filter id={`grain${f}`}><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} seed={f * 7 + 1} /><feColorMatrix type="saturate" values="0" /></filter>
        <rect width="100%" height="100%" filter={`url(#grain${f})`} />
      </svg>
    </AbsoluteFill>
  );
};

export const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.55 }) => (
  <AbsoluteFill style={{ background: `radial-gradient(ellipse 75% 60% at 50% 45%, transparent 55%, rgba(0,0,0,${strength}) 100%)`, pointerEvents: "none" }} />
);

// Warm light leak that sweeps across, screen-blended.
export const LightLeak: React.FC<{ dur: number; hue?: string }> = ({ dur, hue = "255,140,60" }) => {
  const f = useCurrentFrame();
  const p = f / dur;
  const x = interpolate(p, [0, 1], [-30, 130]);
  const o = interpolate(p, [0, 0.25, 0.7, 1], [0, 0.85, 0.6, 0]);
  return (
    <AbsoluteFill style={{ mixBlendMode: "screen", opacity: o, pointerEvents: "none",
      background: `radial-gradient(ellipse 45% 70% at ${x}% 40%, rgba(${hue},0.95) 0%, rgba(${hue},0.35) 35%, transparent 70%)` }} />
  );
};

// RGB split + horizontal slice displacement, for "glitch" accents.
export const Glitch: React.FC<{ children: React.ReactNode; active: boolean; seed?: string }> = ({ children, active, seed = "g" }) => {
  const f = useCurrentFrame();
  if (!active) return <>{children}</>;
  const dx = (random(`${seed}x${f}`) - 0.5) * 40;
  const slices = new Array(5).fill(0).map((_, i) => ({ y: random(`${seed}y${i}${f}`) * 100, h: 2 + random(`${seed}h${i}${f}`) * 10, d: (random(`${seed}d${i}${f}`) - 0.5) * 120 }));
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: `translateX(${dx}px)`, filter: "drop-shadow(8px 0 0 rgba(255,0,60,0.7)) drop-shadow(-8px 0 0 rgba(0,220,255,0.7))" }}>{children}</AbsoluteFill>
      {slices.map((s, i) => (
        <AbsoluteFill key={i} style={{ clipPath: `inset(${s.y}% 0 ${Math.max(0, 100 - s.y - s.h)}% 0)`, transform: `translateX(${s.d}px)` }}>{children}</AbsoluteFill>
      ))}
    </AbsoluteFill>
  );
};

// A 3D icon (CC0 render from 3dicons.co, kept in the project folder) with float, drop shadow and
// optional depth-of-field blur for foreground/background layers.
export const Icon3D: React.FC<{ name: string; x: number; y: number; size: number; at?: number; blur?: number; rot?: number;
  floatAmp?: number; variant?: "premium" | "color"; spin?: number }> = ({ name, x, y, size, at = 0, blur = 0, rot = 0, floatAmp = 10, variant = "color", spin = 0 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (f < at) return null;
  const s = pop(f - at, fps, 11, 200, 0.8);
  const fy = Math.sin((f + x) / 14) * floatAmp;
  const r = rot + Math.sin((f + y) / 22) * 4 + spin * (f - at);
  return (
    <Img src={staticFile(`icons3d/${name}_${variant}.png`)} style={{ position: "absolute", left: x - size / 2, top: y - size / 2 + fy, width: size, height: size,
      transform: `scale(${s}) rotate(${r}deg)`, filter: `blur(${blur}px) drop-shadow(0 ${size * 0.08}px ${size * 0.1}px rgba(0,0,0,0.45))`, opacity: Math.min(1, s * 1.4) }} />
  );
};

// Hand-drawn stroke: an SVG path that draws itself (stroke-dashoffset).
export const Scribble: React.FC<{ d: string; at: number; dur?: number; color: string; width?: number; vb: string; style?: React.CSSProperties }> = ({ d, at, dur = 8, color, width = 14, vb, style }) => {
  const f = useCurrentFrame();
  const p = ramp(f, at, at + dur, 0, 1, eInOut);
  if (f < at) return null;
  return (
    <svg viewBox={vb} style={{ position: "absolute", overflow: "visible", ...style }}>
      <path d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" pathLength={1}
        strokeDasharray={1} strokeDashoffset={1 - p} style={{ filter: "drop-shadow(0 4px 6px rgba(0,0,0,0.35))" }} />
    </svg>
  );
};

// Text typed character by character with a blinking caret.
export const Typed: React.FC<{ text: string; at: number; cps: number; caret?: boolean; style?: React.CSSProperties; caretColor?: string }> = ({ text, at, cps, caret = true, style, caretColor = "#fff" }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = Math.max(0, Math.min(text.length, Math.floor(((f - at) / fps) * cps)));
  const on = caret && (n < text.length || Math.floor(f / 8) % 2 === 0) && f >= at;
  return (
    <span style={{ whiteSpace: "pre-wrap", ...style }}>
      {text.slice(0, n)}
      {on ? <span style={{ display: "inline-block", width: "0.08em", height: "1em", background: caretColor, marginLeft: 2, verticalAlign: "-0.12em" }} /> : null}
    </span>
  );
};

export const Cursor: React.FC<{ x: number; y: number; press?: number }> = ({ x, y, press = 0 }) => (
  <svg width={56} height={56} viewBox="0 0 24 24" style={{ position: "absolute", left: x, top: y, transform: `scale(${1 - press * 0.15})`, filter: "drop-shadow(0 4px 8px rgba(0,0,0,0.5))" }}>
    <path d="M4 2 L4 19 L8.5 14.8 L11.5 21.5 L14.2 20.3 L11.3 13.8 L17.5 13.8 Z" fill="#fff" stroke="#111" strokeWidth={1.2} strokeLinejoin="round" />
  </svg>
);
