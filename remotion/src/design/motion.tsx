import React from "react";
import { AbsoluteFill, interpolate, random, useCurrentFrame } from "remotion";
import { clamp, eOut } from "./fx";

// ---------------------------------------------------------------------------------------------
// After Effects expression equivalents, as pure functions of the frame (deterministic per seed).
// AE: wiggle(freq, amp)  -> smooth noise: sum of two sines with seeded phases (no per-frame jitter)
export const wiggle = (f: number, fps: number, freq: number, amp: number, seed = "w") => {
  const t = f / fps;
  const p1 = random(`${seed}a`) * 6.283, p2 = random(`${seed}b`) * 6.283;
  return amp * (0.6 * Math.sin(t * freq * 6.283 + p1) + 0.4 * Math.sin(t * freq * 2.71 * 6.283 + p2));
};
// AE "inertial bounce" (Dan Ebberts): v * amp * sin(freq*t*2pi) / exp(decay*t), after a keyframe.
// Here: overshoot of a move that ended `k` frames ago with arrival velocity v (units per second).
export const inertial = (k: number, fps: number, v: number, amp = 0.05, freq = 2.5, decay = 6) => {
  if (k <= 0) return 0;
  const t = k / fps;
  return (v * amp * Math.sin(freq * t * 2 * Math.PI)) / Math.exp(decay * t);
};
// Counter that slows into its target (AE: linear(easeOut) on a Slider + Math.round).
export const countTo = (f: number, start: number, dur: number, to: number, from = 0, power = 4) => {
  const p = Math.max(0, Math.min(1, (f - start) / dur));
  return from + (to - from) * (1 - Math.pow(1 - p, power));
};
export const fmtNum = (n: number, style: "en" | "in" = "en", decimals = 0) => {
  const v = Math.round(n * 10 ** decimals) / 10 ** decimals;
  if (style === "en") return v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  // Indian grouping: 1,00,00,000
  const s = Math.floor(v).toString();
  if (s.length <= 3) return s;
  const last = s.slice(-3), rest = s.slice(0, -3);
  return rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + last;
};

// ---------------------------------------------------------------------------------------------
// Transitions. Each one is a full-frame layer that covers a cut placed at its `at` frame; render.py
// puts the matching SFX (riser into, whoosh/impact on the cut). Durations are the measured ones
// from the 2026-11-15 set (see references/effects-catalog.md).

// Light-leak dip (vepro x7): warm leak blooms from the bottom over 6 f, 1-2 f pure white on the cut,
// leak decays over 8 f. hues: "warm" orange->magenta, or any two colours.
export const LeakDip: React.FC<{ at: number; c1?: string; c2?: string; pre?: number; post?: number }> = ({ at, c1 = "255,150,60", c2 = "200,40,120", pre = 7, post = 9 }) => {
  const f = useCurrentFrame();
  const k = f - at;
  if (k < -pre || k > post) return null;
  const a = k < 0 ? interpolate(k, [-pre, 0], [0, 1], clamp) : interpolate(k, [0, post], [1, 0], { ...clamp, easing: eOut });
  const white = k >= -1 && k <= 1 ? 1 - Math.abs(k) * 0.35 : 0;
  const y = interpolate(k, [-pre, 0, post], [120, 40, -20], clamp);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill style={{ mixBlendMode: "screen", opacity: a,
        background: `radial-gradient(ellipse 90% 70% at 30% ${y}%, rgba(${c1},1) 0%, rgba(${c2},0.85) 45%, rgba(${c2},0) 80%)` }} />
      <AbsoluteFill style={{ background: "#fff", opacity: white }} />
    </AbsoluteFill>
  );
};

// Smoke/fog flash (cozy x17): white smoke rolls in from a corner (6 f), near-white hold (4 f) with
// the cut inside, smoke thins (10 f) while god-ray beams sweep. Procedural: SVG turbulence masked
// by a growing radial gradient, so no stock element is needed.
export const SmokeFlash: React.FC<{ at: number; seed?: number; rays?: boolean }> = ({ at, seed = 3, rays = true }) => {
  const f = useCurrentFrame();
  const k = f - at;
  if (k < -8 || k > 16) return null;
  const cover = k < -2 ? interpolate(k, [-8, -2], [0, 1], { ...clamp, easing: eOut }) : k <= 2 ? 1 : interpolate(k, [2, 16], [1, 0], clamp);
  const r = interpolate(k, [-8, -2, 16], [10, 160, 220], clamp);
  const id = `smk${at}`;
  const rayO = rays ? interpolate(k, [2, 6, 16], [0, 0.55, 0], clamp) : 0;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg width="100%" height="100%" viewBox="0 0 100 178" preserveAspectRatio="none">
        <defs>
          <filter id={id} x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves={4} seed={seed + Math.floor(k / 2)} />
            <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1.6 -0.35" />
            <feGaussianBlur stdDeviation="1.2" />
          </filter>
          <radialGradient id={`${id}g`} cx="0" cy="1" r="1">
            <stop offset="0" stopColor="#fff" stopOpacity="1" />
            <stop offset={`${Math.min(0.95, r / 260)}`} stopColor="#fff" stopOpacity="0.9" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </radialGradient>
          <mask id={`${id}m`}><rect width="100" height="178" fill={`url(#${id}g)`} /></mask>
        </defs>
        <g mask={`url(#${id}m)`} opacity={cover}>
          <rect width="100" height="178" filter={`url(#${id})`} />
          <rect width="100" height="178" fill="#fff" opacity={k >= -2 && k <= 2 ? 0.92 : 0.35} />
        </g>
      </svg>
      <AbsoluteFill style={{ opacity: rayO, mixBlendMode: "screen",
        background: "repeating-linear-gradient(115deg, rgba(255,255,255,0) 0px, rgba(255,255,255,0) 60px, rgba(255,250,235,0.55) 90px, rgba(255,255,255,0) 150px)",
        transform: `translateX(${(k - 2) * 12}px)`, filter: "blur(18px)" }} />
    </AbsoluteFill>
  );
};

// Overexpose cut (sumit, marcel open): the picture blooms to white over 2 f, cut at the peak,
// decays in 2-3 f. Applied as brightness on the whole frame plus a white veil.
export const overexpose = (k: number) => (k < -2 || k > 3 ? 0 : k <= 0 ? (k + 3) / 3 : 1 - k / 3.5);

// Colour wash (sumit lime, pin1129 green): a gradient blob in the accent colour rises from a corner,
// fills the frame for 2-3 f, then reveals. Branded transition.
export const ColourWash: React.FC<{ at: number; color: string; from?: "bl" | "br" | "tl" | "tr" }> = ({ at, color, from = "bl" }) => {
  const f = useCurrentFrame();
  const k = f - at;
  if (k < -5 || k > 6) return null;
  const s = k < 0 ? interpolate(k, [-5, 0], [0, 260], { ...clamp, easing: eOut }) : 260;
  const o = k <= 1 ? 1 : interpolate(k, [1, 6], [1, 0], clamp);
  const pos = { bl: "0% 100%", br: "100% 100%", tl: "0% 0%", tr: "100% 0%" }[from];
  return <AbsoluteFill style={{ pointerEvents: "none", opacity: o, background: `radial-gradient(circle at ${pos}, ${color} 0%, ${color} ${s * 0.45}%, ${color}00 ${s * 0.8}%)` }} />;
};

// Film burn / light streaks (enginecy): rainbow streaks rush diagonally, 2 f overexposed to white
// around the cut. 10-12 f.
export const FilmBurn: React.FC<{ at: number }> = ({ at }) => {
  const f = useCurrentFrame();
  const k = f - at;
  if (k < -5 || k > 7) return null;
  const x = interpolate(k, [-5, 7], [-80, 120], clamp);
  const o = interpolate(k, [-5, -1, 1, 7], [0, 1, 1, 0], clamp);
  const w = k >= -1 && k <= 1 ? 0.85 : 0;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill style={{ opacity: o, mixBlendMode: "screen", transform: `translateX(${x}%) skewX(-25deg)`, filter: "blur(14px)",
        background: "linear-gradient(90deg, transparent 0%, rgba(40,255,140,0.9) 12%, rgba(255,170,40,1) 24%, rgba(255,255,255,1) 32%, rgba(60,200,255,0.9) 44%, rgba(255,60,160,0.8) 56%, transparent 70%)" }} />
      <AbsoluteFill style={{ background: "#fff", opacity: w }} />
    </AbsoluteFill>
  );
};

// Whole-frame treatments that are style changes rather than layers.
// bw: desaturate (vepro "DON'T EVER" beat, cozy flashbacks). defocus: push toward camera + blur so
// a front layer reads sharp (enginecy CTA handoff). whipblur: directional smear on a cut.
export const frameTreatment = (fx: { at: number; type: string; dur?: number; dir?: string }[], f: number) => {
  let gray = 0, blur = 0, scale = 1, bright = 1, tx = 0, ty = 0, veil = 0;
  for (const x of fx) {
    const k = f - x.at;
    const d = x.dur ?? 30;
    if (x.type === "bw" && k >= 0 && k < d) gray = 1;
    if (x.type === "defocus" && k >= 0 && k < d) {
      const p = interpolate(k, [0, 12], [0, 1], { ...clamp, easing: eOut });
      blur = Math.max(blur, 22 * p); scale *= 1 + 0.3 * p;
    }
    if (x.type === "overexpose") { const o = overexpose(k); bright = Math.max(bright, 1 + 2.5 * o); veil = Math.max(veil, o * 0.8); }
    if (x.type === "whip" && k >= -3 && k < 4) {
      const p = k < 0 ? (k + 3) / 3 : 1 - k / 4;
      const amt = 140 * p * p * Math.sign(k + 0.5);
      if ((x.dir ?? "left") === "up") ty = -amt; else tx = (x.dir === "right" ? 1 : -1) * amt;
      blur = Math.max(blur, 16 * p);
    }
  }
  return { gray, blur, scale, bright, tx, ty, veil };
};
