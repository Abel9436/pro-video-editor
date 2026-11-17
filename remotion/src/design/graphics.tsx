import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, interpolate, random, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, eOut, pop, ramp } from "./fx";
import { countTo, fmtNum, wiggle } from "./motion";
import { Brand, display, hand, sans, serif } from "./theme";
import { CapGroup } from "./type";

// =============================================================================================
// CAPTION STYLES (all take the same CapGroup: words with their spoken frame, relative to group)
// Measured on the 2026-11-15 set; which reference each comes from is in effects-catalog.md.
// =============================================================================================

// "slam" (marcel): one word at a time, huge, white, top third. The new word arrives ghosted
// (40 % opacity, 1.25x, blurred) and solidifies in 4 f; the previous word is gone on the same frame.
export const SlamCaption: React.FC<{ g: CapGroup; y: number; brand: Brand; size?: number }> = ({ g, y, brand, size = 210 }) => {
  const f = useCurrentFrame();
  const { height, width } = useVideoConfig();
  let i = -1;
  g.words.forEach((w, j) => { if (f >= w.s - 1) i = j; });
  if (i < 0) return null;
  const w = g.words[i];
  const k = f - (w.s - 1);
  const a = ramp(k, 0, 4);
  const txt = w.w.replace(/[.,!?;:]+$/, "");
  const fit = Math.min(size, (width * 0.92) / Math.max(1, txt.length * 0.56));
  return (
    <div style={{ position: "absolute", top: y * height, left: 0, width, textAlign: "center", transform: `translateY(-50%) scale(${1.25 - 0.25 * a})`,
      opacity: 0.4 + 0.6 * a, filter: `blur(${(1 - a) * 14}px)`, fontFamily: sans, fontWeight: 800, fontSize: fit, letterSpacing: "-0.045em",
      color: w.emph ? brand.accent : "#fff", lineHeight: 1, textShadow: "0 8px 30px rgba(0,0,0,0.35)" }}>{txt}</div>
  );
};

// "neon" (pin1129, sumit): small white helper words + the emphasis word in the accent colour with a
// three-layer bloom; the key word switches on letter by letter like a neon tube (1 letter / frame,
// random flicker on the first frames of each letter).
export const NeonCaption: React.FC<{ g: CapGroup; y: number; brand: Brand; size?: number; serifKey?: boolean }> = ({ g, y, brand, size = 64, serifKey = false }) => {
  const f = useCurrentFrame();
  const { height, width } = useVideoConfig();
  const out = ramp(f, g.e - g.s - 4, g.e - g.s);
  const c = brand.accent;
  // helpers are small only when a key word carries the line; a phrase without one stays readable
  const hasKey = g.words.some((w) => w.emph);
  const hs = hasKey ? 0.6 : 0.9;
  return (
    <div style={{ position: "absolute", top: y * height, left: width * 0.06, right: width * 0.06, transform: "translateY(-50%)", textAlign: "center",
      opacity: 1 - out, filter: `blur(${out * 8}px)`, lineHeight: 1.05 }}>
      {g.words.map((w, i) => {
        const k = f - w.s;
        if (k < -1) return null;
        if (!w.emph) {
          const a = ramp(k, -1, 3);
          return <span key={i} style={{ display: "inline-block", marginRight: "0.25em", opacity: a, filter: `blur(${(1 - a) * 6}px)`, fontFamily: sans, fontWeight: hasKey ? 600 : 800,
            fontSize: size * hs, color: "#fff", textShadow: "0 0 12px rgba(255,255,255,0.45), 0 2px 8px rgba(0,0,0,0.6)", verticalAlign: "middle" }}>{w.w}</span>;
        }
        return (
          <span key={i} style={{ display: "inline-block", marginRight: "0.2em", verticalAlign: "middle", fontFamily: serifKey ? serif : sans,
            fontStyle: serifKey ? "italic" : "normal", fontWeight: serifKey ? 400 : 800, fontSize: size * (serifKey ? 1.7 : 1.45), letterSpacing: serifKey ? 0 : "-0.03em" }}>
            {w.w.split("").map((ch, j) => {
              const on = k - j;
              const flick = on < 0 ? 0 : on < 3 ? (random(`n${i}${j}${f}`) > 0.35 ? 1 : 0.25) : 1;
              return <span key={j} style={{ color: on < 0 ? "transparent" : "#f6fff8", opacity: flick,
                textShadow: on < 0 ? "none" : `0 0 4px #fff, 0 0 14px ${c}, 0 0 34px ${c}, 0 0 70px ${c}aa` }}>{ch}</span>;
            })}
          </span>
        );
      })}
    </div>
  );
};

// "keyword" (foysal): the emphasis word is huge and each one takes the next colour of a palette;
// non-emphasis words sit small above it. Entry: blur + scale-down 5 f. Optional jittery glow (wiggle).
const KEY_PALETTE = ["#8B3DFF", "#FFC21A", "#FF3B3B", "#2E6BFF", "#19C37D", "#E83FD0"];
export const KeywordCaption: React.FC<{ g: CapGroup; y: number; brand: Brand; size?: number; index: number; palette?: string[] }> = ({ g, y, size = 150, index, palette = KEY_PALETTE }) => {
  const f = useCurrentFrame();
  const { height, width, fps } = useVideoConfig();
  const out = ramp(f, g.e - g.s - 5, g.e - g.s);
  const key = g.words.find((w) => w.emph) ?? g.words[g.words.length - 1];
  const helpers = g.words.filter((w) => w !== key);
  const col = palette[index % palette.length];
  const k = f - key.s;
  const a = ramp(k, -1, 5);
  const txt = key.w.replace(/[.,!?;:]+$/, "");
  const fit = Math.min(size, (width * 0.9) / Math.max(1, txt.length * 0.6));
  const jx = wiggle(f, fps, 9, 2, `k${index}`), jy = wiggle(f + 7, fps, 9, 2, `k${index}y`);
  return (
    <div style={{ position: "absolute", top: y * height, left: 0, width, transform: "translateY(-50%)", textAlign: "center", opacity: 1 - out, filter: `blur(${out * 10}px)` }}>
      <div style={{ fontFamily: sans, fontWeight: 600, fontSize: 44, color: "#fff", textShadow: "0 2px 10px rgba(0,0,0,0.6)", marginBottom: -fit * 0.12,
        transform: `translateX(${-fit * 0.4}px)` }}>
        {helpers.map((w, i) => <span key={i} style={{ opacity: ramp(f - w.s, -1, 3), marginRight: 10 }}>{w.w}</span>)}
      </div>
      {k >= -1 ? <div style={{ fontFamily: display, fontSize: fit, lineHeight: 1, color: col, letterSpacing: "-0.01em", opacity: a, filter: `blur(${(1 - a) * 12}px)`,
        transform: `scale(${1.15 - 0.15 * a}) translate(${jx}px, ${jy}px)`, textShadow: `0 0 26px ${col}aa, 0 6px 18px rgba(0,0,0,0.35)` }}>{txt}</div> : null}
    </div>
  );
};

// "tier" (vepro): 2 lines, heavy italic display; line 1 white small, line 2 accent with glow; each
// word blurs in on its frame.
export const TierCaption: React.FC<{ g: CapGroup; y: number; brand: Brand; size?: number }> = ({ g, y, brand, size = 74 }) => {
  const f = useCurrentFrame();
  const { height, width } = useVideoConfig();
  const out = ramp(f, g.e - g.s - 3, g.e - g.s);
  const split = Math.max(1, g.words.findIndex((w) => w.emph));
  const lines = [g.words.slice(0, split), g.words.slice(split)];
  return (
    <div style={{ position: "absolute", top: y * height, left: width * 0.06, right: width * 0.06, transform: "translateY(-50%) skewX(-8deg)", textAlign: "center",
      opacity: 1 - out, lineHeight: 0.98, fontFamily: display, textTransform: "uppercase" }}>
      {lines.map((ln, li) => (
        <div key={li} style={{ fontSize: li === 0 ? size * 0.62 : size, color: li === 0 ? "#fff" : brand.accent,
          textShadow: li === 0 ? "0 3px 10px rgba(0,0,0,0.6)" : `0 0 22px ${brand.accent}88, 0 4px 12px rgba(0,0,0,0.5)` }}>
          {ln.map((w, i) => { const a = ramp(f - w.s, -1, 2); return <span key={i} style={{ opacity: a, filter: `blur(${(1 - a) * 6}px)`, marginRight: "0.22em" }}>{w.w}</span>; })}
        </div>
      ))}
    </div>
  );
};

// =============================================================================================
// OVERLAYS (each gets dur = its span in frames; positions are fractions of the frame)
// =============================================================================================

// Number counter with an icon above (sumit "eye 10,000", "$10,000", "1,00,00,000 Views+").
export const Counter: React.FC<{ to: number; from?: number; prefix?: string; suffix?: string; label?: string; x?: number; y: number; style?: "en" | "in";
  countDur?: number; size?: number; icon?: string; brand: Brand; dur: number; serifNum?: boolean }> =
  ({ to, from = 0, prefix = "", suffix = "", label, x = 0.5, y, style = "en", countDur = 40, size = 150, icon, brand, dur, serifNum = true }) => {
  const f = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const s = pop(f, fps, 12, 200, 0.7);
  const out = ramp(f, dur - 5, dur);
  const v = countTo(f, 4, countDur, to, from);
  const landed = f >= 4 + countDur;
  const pulse = landed ? Math.max(0, 1 - (f - 4 - countDur) / 10) : 0;
  return (
    <div style={{ position: "absolute", left: x * width, top: y * height, transform: `translate(-50%,-50%) scale(${0.7 + 0.3 * s + 0.06 * pulse})`, opacity: (1 - out) * Math.min(1, s * 1.5),
      textAlign: "center", filter: `blur(${out * 10}px)` }}>
      {icon ? <div style={{ fontSize: size * 0.5, lineHeight: 1, marginBottom: 6 }}>{icon}</div> : null}
      <div style={{ fontFamily: serifNum ? serif : sans, fontStyle: serifNum ? "italic" : "normal", fontWeight: serifNum ? 400 : 900, fontSize: size, lineHeight: 1,
        color: "#f7ffef", whiteSpace: "nowrap", textShadow: `0 0 6px #fff, 0 0 ${24 + 30 * pulse}px ${brand.accent}, 0 0 60px ${brand.accent}99` }}>
        {prefix}{fmtNum(v, style)}{suffix}
      </div>
      {label ? <div style={{ fontFamily: sans, fontWeight: 600, fontSize: size * 0.24, color: "#fff", opacity: ramp(f, 4 + countDur, 10 + countDur) }}>{label}</div> : null}
    </div>
  );
};

// Figma-style selection frame around a caption zone (sumit): guide lines run out to the frame edges,
// then a rectangle with 8 handles draws on (10 f).
export const SelectionBox: React.FC<{ x: number; y: number; w: number; h: number; brand: Brand; dur: number; guides?: boolean }> = ({ x, y, w, h, brand, dur, guides = true }) => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const p = ramp(f, 0, 10);
  const g = ramp(f, 0, 6);
  const out = ramp(f, dur - 5, dur);
  const L = (x - w / 2) * width, T = (y - h / 2) * height, W = w * width, H = h * height;
  const c = brand.accent;
  const handles = [[0, 0], [0.5, 0], [1, 0], [0, 0.5], [1, 0.5], [0, 1], [0.5, 1], [1, 1]];
  return (
    <AbsoluteFill style={{ opacity: 1 - out, pointerEvents: "none" }}>
      {guides ? <>
        <div style={{ position: "absolute", top: T, left: 0, width: width * g, height: 1.5, background: `${c}aa` }} />
        <div style={{ position: "absolute", top: T + H, right: 0, width: width * g, height: 1.5, background: `${c}aa` }} />
        <div style={{ position: "absolute", left: L, top: 0, height: height * g, width: 1.5, background: `${c}aa` }} />
        <div style={{ position: "absolute", left: L + W, bottom: 0, height: height * g, width: 1.5, background: `${c}aa` }} />
      </> : null}
      <svg style={{ position: "absolute", left: L, top: T, overflow: "visible" }} width={W} height={H}>
        <rect x={0} y={0} width={W} height={H} fill="none" stroke={c} strokeWidth={3} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} />
        {handles.map(([hx, hy], i) => (
          <circle key={i} cx={hx * W} cy={hy * H} r={9 * ramp(f, 6 + i, 10 + i)} fill="#fff" stroke={c} strokeWidth={3} />
        ))}
      </svg>
    </AbsoluteFill>
  );
};

// Glowing halo behind the head (sumit). Needs the person matte to sit BEHIND the subject
// (render it in the `behind` layer).
export const Halo: React.FC<{ x: number; y: number; r: number; brand: Brand; dur: number }> = ({ x, y, r, brand, dur }) => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const s = ramp(f, 0, 5, 0.6, 1);
  const o = Math.min(ramp(f, 0, 4), 1 - ramp(f, dur - 8, dur));
  const R = r * width;
  return <div style={{ position: "absolute", left: x * width - R, top: y * height - R, width: 2 * R, height: 2 * R, borderRadius: "50%", opacity: o, transform: `scale(${s})`,
    border: `${R * 0.05}px solid ${brand.accent}`, boxShadow: `0 0 ${R * 0.25}px ${brand.accent}, inset 0 0 ${R * 0.25}px ${brand.accent}`,
    background: `radial-gradient(circle, ${brand.accent}55 0%, ${brand.accent}00 70%)` }} />;
};

// Chapter badge (vepro): glowing numbered circle pops (0 -> 1.2 -> 1, 4 f), title types beside it.
export const ChapterBadge: React.FC<{ n: number | string; title: string; x?: number; y: number; brand: Brand; dur: number; cps?: number }> = ({ n, title, x = 0.1, y, brand, dur, cps = 15 }) => {
  const f = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const s = pop(f, fps, 9, 260, 0.6);
  const out = ramp(f, dur - 4, dur);
  const nch = Math.max(0, Math.min(title.length, Math.floor(((f - 8) / fps) * cps)));
  const D = 92;
  return (
    <div style={{ position: "absolute", left: x * width, top: y * height, display: "flex", alignItems: "center", gap: 18, opacity: 1 - out, transform: "translateY(-50%)" }}>
      <div style={{ width: D, height: D, borderRadius: D, background: brand.accent, transform: `scale(${s})`, display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: display, fontSize: D * 0.62, color: brand.ink, boxShadow: `0 0 ${20 + 30 * Math.max(0, 1 - f / 10)}px ${brand.accent}, 0 0 60px ${brand.accent}88`,
        border: `4px solid #fff8` }}>{n}</div>
      <div style={{ fontFamily: display, fontSize: 58, color: "#fff", textTransform: "uppercase", transform: "skewX(-8deg)", maxWidth: width * 0.6, lineHeight: 0.95,
        textShadow: "0 3px 12px rgba(0,0,0,0.6)" }}>{title.slice(0, nch)}</div>
    </div>
  );
};

// Countdown ring (vepro "60s"): a glowing ring at chest that ticks down on real seconds.
export const Countdown: React.FC<{ from: number; x?: number; y: number; brand: Brand; dur: number; size?: number }> = ({ from, x = 0.5, y, brand, dur, size = 150 }) => {
  const f = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const s = pop(f, fps, 10, 240, 0.6);
  const flash = Math.max(0, 1 - f / 6);
  const out = ramp(f, dur - 5, dur);
  const n = Math.max(0, from - Math.floor(f / fps));
  const frac = (f % fps) / fps;
  return (
    <div style={{ position: "absolute", left: x * width - size / 2, top: y * height - size / 2, width: size, height: size, transform: `scale(${s})`, opacity: 1 - out }}>
      <svg width={size} height={size} style={{ position: "absolute", filter: `drop-shadow(0 0 ${10 + 20 * flash}px ${brand.accent})` }}>
        <circle cx={size / 2} cy={size / 2} r={size / 2 - 6} fill={`rgba(10,10,14,${0.55 + 0.4 * flash})`} stroke={brand.accent} strokeWidth={5}
          pathLength={1} strokeDasharray={1} strokeDashoffset={frac * 0.08} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: display, fontSize: size * 0.32,
        color: "#fff", transform: "skewX(-8deg)" }}>{n}s</div>
    </div>
  );
};

// Tile row (vepro 1|2|3 -> app logos): rounded tiles pop left to right 4 f apart with overshoot; each
// tile can flip (scaleX squeeze, 4 f) at `flipAt[i]` to show an image (icons3d/<name>_color.png or
// any project-relative path) or a word.
export const TileRow: React.FC<{ items: { label: string; flipAt?: number; img?: string; text?: string }[]; y: number; brand: Brand; dur: number; size?: number; note?: string }> =
  ({ items, y, brand, dur, size = 150, note }) => {
  const f = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const out = ramp(f, dur - 5, dur);
  const gap = 22, total = items.length * size + (items.length - 1) * gap;
  return (
    <div style={{ position: "absolute", top: y * height, left: (width - total) / 2, display: "flex", gap, opacity: 1 - out, transform: "translateY(-50%)" }}>
      {items.map((it, i) => {
        const s = pop(f - i * 4, fps, 10, 240, 0.6);
        const fk = it.flipAt !== undefined ? f - it.flipAt : -99;
        const flipped = fk >= 2;
        const sx = fk >= 0 && fk < 4 ? Math.abs(1 - fk / 2) : 1;
        return (
          <div key={i} style={{ width: size, height: size, borderRadius: size * 0.22, transform: `scale(${s}) scaleX(${sx})`, display: "flex", alignItems: "center", justifyContent: "center",
            background: flipped ? "#14121c" : brand.accent, border: `5px solid ${brand.accent}`, boxShadow: `0 0 26px ${brand.accent}99`,
            fontFamily: display, fontSize: size * 0.55, color: brand.ink, overflow: "hidden" }}>
            {flipped && it.img ? <Img src={staticFile(it.img)} style={{ width: "78%", height: "78%", objectFit: "contain" }} />
              : flipped && it.text ? <span style={{ color: "#fff", fontSize: size * 0.24, fontFamily: sans, fontWeight: 900, textAlign: "center" }}>{it.text}</span>
              : it.label}
          </div>
        );
      })}
      {note ? <div style={{ position: "absolute", right: -40, top: -70, fontFamily: hand, fontSize: 46, color: "#fff", transform: "rotate(-6deg)", opacity: ramp(f, 14, 20) }}>{note}</div> : null}
    </div>
  );
};

// Label stack (vepro source lists): white rounded labels with an icon, each grows from a thin line
// (3 f) one after another, stacked at chest.
export const LabelStack: React.FC<{ items: { text: string; icon?: string; at?: number }[]; y: number; dur: number; brand: Brand }> = ({ items, y, dur }) => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const out = ramp(f, dur - 4, dur);
  return (
    <div style={{ position: "absolute", top: y * height, left: 0, width, display: "flex", flexDirection: "column", alignItems: "center", gap: 14, opacity: 1 - out }}>
      {items.map((it, i) => {
        const at = it.at ?? i * 8;
        const p = ramp(f, at, at + 4);
        if (f < at) return null;
        return (
          <div key={i} style={{ background: "#fff", borderRadius: 16, padding: "14px 30px", display: "flex", alignItems: "center", gap: 14, transform: `scaleY(${0.08 + 0.92 * p}) scaleX(${0.6 + 0.4 * p})`,
            boxShadow: "0 10px 30px rgba(0,0,0,0.35)", fontFamily: sans, fontWeight: 700, fontSize: 40, color: "#111" }}>
            {it.icon ? <span style={{ fontSize: 40 }}>{it.icon}</span> : null}<span style={{ opacity: p }}>{it.text}</span>
          </div>
        );
      })}
    </div>
  );
};

// Search-bar CTA (vepro "CHEAT CODE", enginecy search): a white pill grows from a short line (6 f),
// placeholder types, then the keyword replaces it.
export const SearchCTA: React.FC<{ placeholder?: string; keyword: string; keyAt?: number; y: number; brand: Brand; dur: number; gradient?: boolean }> = ({ placeholder = "comment", keyword, keyAt = 30, y, brand, dur, gradient = false }) => {
  const f = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const w = ramp(f, 0, 6, 0.08, 0.86);
  const out = ramp(f, dur - 5, dur);
  const t = f < keyAt ? placeholder.slice(0, Math.floor(((f - 6) / fps) * 18)) : keyword;
  const ks = f >= keyAt ? pop(f - keyAt, fps, 10, 260, 0.6) : 1;
  return (
    <div style={{ position: "absolute", top: y * height, left: (width * (1 - w)) / 2, width: width * w, height: 96, borderRadius: 48, transform: "translateY(-50%)", opacity: 1 - out,
      background: gradient ? `linear-gradient(90deg, #2bb4e0, ${brand.glow}, #e63fa0)` : "#fff", padding: gradient ? 5 : 0, boxShadow: `0 0 40px ${brand.glow}66` }}>
      <div style={{ width: "100%", height: "100%", borderRadius: 48, background: "#fff", display: "flex", alignItems: "center", paddingLeft: 40, gap: 20 }}>
        <svg width={40} height={40} viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth={2.4} strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
        <span style={{ fontFamily: sans, fontWeight: f >= keyAt ? 900 : 500, fontSize: 44, color: f >= keyAt ? "#111" : "#888", transform: `scale(${ks})`, transformOrigin: "left center",
          letterSpacing: f >= keyAt ? "0.04em" : 0 }}>{t}</span>
      </div>
    </div>
  );
};

// Full-frame colour word card (marcel): solid colour, one word at a time in the opposite colour.
// The first word arrives with a horizontal motion-blur slam; the whole card keeps dollying out
// (text scale 1 -> 0.45 over the card) so the frame never sits still.
export const ColorCard: React.FC<{ words: { w: string; at: number }[]; bg: string; fg: string; dur: number; size?: number }> = ({ words, bg, fg, dur, size = 220 }) => {
  const f = useCurrentFrame();
  const { width } = useVideoConfig();
  let i = -1;
  words.forEach((w, j) => { if (f >= w.at) i = j; });
  const dolly = interpolate(f, [0, dur], [1, 0.45], { ...clamp, easing: (x) => 1 - Math.pow(1 - x, 1.6) });
  const k = f - (words[0]?.at ?? 0);
  const slam = i === 0 ? ramp(k, 0, 5) : 1;
  const txt = i >= 0 ? words[i].w : "";
  const fit = Math.min(size, (width * 0.9) / Math.max(1, txt.length * 0.55));
  return (
    <AbsoluteFill style={{ background: bg, alignItems: "center", justifyContent: "center" }}>
      <div style={{ fontFamily: sans, fontWeight: 800, fontSize: fit, color: fg, letterSpacing: "-0.045em", transform: `scale(${dolly * (2 - slam)}) translateX(${(1 - slam) * 200}px)`,
        filter: `blur(${(1 - slam) * 18}px)`, textShadow: `0 0 30px ${fg}55` }}>{txt}</div>
    </AbsoluteFill>
  );
};

// Line icon that draws itself with a neon glow (enginecy): any SVG path data (e.g. a Lucide icon,
// ISC licence, copied into the project). Each path draws in turn, `stagger` frames apart.
export const LineIcon: React.FC<{ paths: string[]; x: number; y: number; size: number; brand: Brand; dur: number; stagger?: number; color?: string; vb?: string }> =
  ({ paths, x, y, size, brand, dur, stagger = 4, color, vb = "0 0 24 24" }) => {
  const f = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const c = color ?? brand.accent;
  const out = ramp(f, dur - 5, dur);
  const s = pop(f, fps, 12, 180, 0.7);
  return (
    <svg viewBox={vb} width={size} height={size} style={{ position: "absolute", left: x * width - size / 2, top: y * height - size / 2, overflow: "visible", opacity: 1 - out,
      transform: `scale(${0.9 + 0.1 * s})`, filter: `drop-shadow(0 0 3px #fff) drop-shadow(0 0 10px ${c}) drop-shadow(0 0 24px ${c})` }}>
      {paths.map((d, i) => (
        <path key={i} d={d} fill="none" stroke={c} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1}
          strokeDashoffset={1 - ramp(f, i * stagger, i * stagger + 8, 0, 1, eOut)} />
      ))}
    </svg>
  );
};

// Card that grows out of the subject (marcel f739-767): rounded media card scales 0.3 -> 1.3 with
// blur -> sharp, keeps pushing past full frame. Media: an image or video in the project folder.
export const GrowCard: React.FC<{ src: string; video?: boolean; x?: number; y?: number; dur: number; startFrom?: number }> = ({ src, video = false, x = 0.5, y = 0.6, dur, startFrom = 0 }) => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const s = interpolate(f, [0, 10, dur], [0.3, 0.95, 1.3], { ...clamp, easing: eOut });
  const b = ramp(f, 0, 8, 14, 0);
  const r = interpolate(f, [0, 10], [40, 28], clamp);
  const style: React.CSSProperties = { width: "100%", height: "100%", objectFit: "cover" };
  return (
    <div style={{ position: "absolute", left: x * width - width * 0.42, top: y * height - height * 0.24, width: width * 0.84, height: height * 0.48, borderRadius: r, overflow: "hidden",
      transform: `scale(${s})`, filter: `blur(${b}px)`, boxShadow: "0 30px 80px rgba(0,0,0,0.5)" }}>
      {video ? <OffthreadVideo src={staticFile(src)} muted startFrom={startFrom} style={style} /> : <Img src={staticFile(src)} style={style} />}
    </div>
  );
};
