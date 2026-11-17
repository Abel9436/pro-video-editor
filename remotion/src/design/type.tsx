import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, pop, ramp } from "./fx";
import { Brand, hand, sans, serif } from "./theme";

export type CapWord = { w: string; s: number; emph?: boolean };
export type CapGroup = { s: number; e: number; words: CapWord[] };

// Phrase caption. Each word arrives on its own spoken frame with a blur-in rise; emphasis words
// switch to the serif italic in the accent colour at 1.3x with a soft glow. The group leaves with
// a quick blur-out. Not a word-pop template: 2-4 word phrases, two type voices.
export const PhraseCaption: React.FC<{ g: CapGroup; y: number; brand: Brand; size?: number; align?: "center" | "left" }> = ({ g, y, brand, size = 64, align = "center" }) => {
  const f = useCurrentFrame();
  const { height, width } = useVideoConfig();
  const out = ramp(f, g.e - 4, g.e, 0, 1);
  return (
    <div style={{ position: "absolute", top: y * height, left: width * 0.08, right: width * 0.08, transform: "translateY(-50%)", textAlign: align,
      opacity: 1 - out, filter: `blur(${out * 10}px)`, lineHeight: 1.08 }}>
      {g.words.map((w, i) => {
        const k = f - w.s;
        const a = ramp(k, -1, 5);
        const em = !!w.emph;
        return (
          <span key={i} style={{ display: "inline-block", marginRight: "0.24em", opacity: a, filter: `blur(${(1 - a) * 9}px)`,
            transform: `translateY(${(1 - a) * 16}px) scale(${em ? 0.9 + 0.1 * a : 1})`,
            fontFamily: em ? serif : sans, fontWeight: em ? 400 : 800, fontStyle: em ? "italic" : "normal",
            fontSize: em ? size * 1.32 : size, letterSpacing: em ? "-0.01em" : "-0.025em",
            color: em ? brand.accent : "#FFFFFF",
            textShadow: em ? `0 0 28px ${brand.accent}66, 0 4px 18px rgba(0,0,0,0.55)` : "0 4px 18px rgba(0,0,0,0.6), 0 1px 2px rgba(0,0,0,0.5)" }}>
            {w.w}
          </span>
        );
      })}
    </div>
  );
};

// Kicker (handwritten, typed) above a headline (heavy sans with one serif-italic accent word).
export const TitleStack: React.FC<{ kicker?: string; head: string; accentWord?: string; y: number; brand: Brand; size?: number; dur: number }> = ({ kicker, head, accentWord, y, brand, size = 110, dur }) => {
  const f = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const out = ramp(f, dur - 5, dur);
  const kn = kicker ? Math.floor(ramp(f, 0, Math.max(6, kicker.length * 1.1), 0, kicker.length, (x) => x)) : 0;
  const words = head.split(" ");
  return (
    <div style={{ position: "absolute", top: y * height, width: "100%", textAlign: "center", opacity: 1 - out, filter: `blur(${out * 12}px)` }}>
      {kicker ? <div style={{ fontFamily: hand, fontWeight: 700, fontSize: size * 0.42, color: "#fff", transform: "rotate(-3deg)", marginBottom: -size * 0.08,
        textShadow: "0 3px 10px rgba(0,0,0,0.55)" }}>{kicker.slice(0, kn)}</div> : null}
      <div style={{ lineHeight: 0.95 }}>
        {words.map((w, i) => {
          const s = pop(f - 4 - i * 3, fps, 13, 240, 0.6);
          const isA = accentWord && w.toLowerCase().replace(/[^a-z']/g, "") === accentWord.toLowerCase();
          return <span key={i} style={{ display: "inline-block", marginRight: "0.2em", transform: `translateY(${(1 - s) * 40}px) scale(${0.85 + 0.15 * s})`, opacity: Math.min(1, s * 1.6),
            filter: `blur(${(1 - Math.min(1, s)) * 8}px)`, fontFamily: isA ? serif : sans, fontStyle: isA ? "italic" : "normal", fontWeight: isA ? 400 : 900,
            fontSize: isA ? size * 1.18 : size, color: isA ? brand.accent : "#fff", letterSpacing: isA ? 0 : "-0.04em", textTransform: isA ? "none" : "uppercase",
            textShadow: isA ? `0 0 40px ${brand.accent}55, 0 6px 22px rgba(0,0,0,0.5)` : "0 6px 22px rgba(0,0,0,0.55)" }}>{w}</span>;
        })}
      </div>
    </div>
  );
};

// Three-step progress rail. The active node is a light orb that racks from blur to focus.
export const Stepper: React.FC<{ labels: string[]; active: number[]; y: number; brand: Brand; dur: number }> = ({ labels, active, y, brand, dur }) => {
  const f = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const inn = pop(f, fps, 16, 160);
  const out = ramp(f, dur - 6, dur);
  // active: [stepIndex, startFrame, stepIndex, startFrame...]
  let cur = -1, since = 0;
  for (let i = 0; i < active.length; i += 2) if (f >= active[i + 1]) { cur = active[i]; since = f - active[i + 1]; }
  const W = width * 0.7, x0 = (width - W) / 2;
  return (
    <div style={{ position: "absolute", top: y * height, left: x0, width: W, height: 120, opacity: inn * (1 - out), transform: `translateY(${(1 - inn) * -30}px)` }}>
      <div style={{ position: "absolute", top: 34, left: 34, right: 34, height: 4, background: "rgba(255,255,255,0.18)", borderRadius: 4 }} />
      <div style={{ position: "absolute", top: 34, left: 34, height: 4, borderRadius: 4, background: brand.accent, boxShadow: `0 0 16px ${brand.accent}`,
        width: cur < 0 ? 0 : `calc(${(Math.max(0, cur - 1) + ramp(since, 0, 12)) / (labels.length - 1)} * (100% - 68px))` }} />
      {labels.map((l, i) => {
        const on = i <= cur, isCur = i === cur;
        const focus = isCur ? ramp(since, 0, 12) : on ? 1 : 0;
        const left = `calc(${i / (labels.length - 1)} * (100% - 68px))`;
        return (
          <div key={i} style={{ position: "absolute", left, top: 0, width: 68, textAlign: "center" }}>
            <div style={{ width: 68, height: 68, borderRadius: 34, display: "flex", alignItems: "center", justifyContent: "center",
              background: on ? brand.accent : "rgba(20,18,30,0.75)", border: `3px solid ${on ? brand.accent : "rgba(255,255,255,0.35)"}`,
              boxShadow: isCur ? `0 0 ${30 + 20 * Math.sin(f / 5)}px ${brand.accent}` : "none",
              filter: isCur ? `blur(${(1 - focus) * 10}px)` : "none", transform: `scale(${isCur ? 1 + 0.25 * (1 - focus) : 1})`,
              fontFamily: sans, fontWeight: 900, fontSize: 32, color: on ? brand.ink : "rgba(255,255,255,0.8)" }}>{i + 1}</div>
            <div style={{ marginTop: 10, marginLeft: -60, width: 188, fontFamily: sans, fontWeight: 900, fontSize: 30, letterSpacing: "0.12em",
              color: on ? "#fff" : "rgba(255,255,255,0.5)", textShadow: "0 2px 8px rgba(0,0,0,0.6)" }}>{l}</div>
          </div>
        );
      })}
    </div>
  );
};

export const fadeInOut = (f: number, dur: number, a = 4, b = 4) => interpolate(f, [0, a, dur - b, dur], [0, 1, 1, 0], clamp);
