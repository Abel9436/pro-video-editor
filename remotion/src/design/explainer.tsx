import React from "react";
import { AbsoluteFill, interpolate, random, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, eInOut, eOut, pop, ramp } from "./fx";
import { countTo, fmtNum } from "./motion";
import type { SceneProps } from "./scenes";
import { Brand, display, hand, sans, serif } from "./theme";

// Explainer scenes for "count it / weigh it / add it up" lines: a metrics dashboard with closing
// rings, a balance scale, a kinetic equation, a page being counted, an app reveal and an end card.
// All generic: labels, numbers, timings and line icons ({lineicon: name} -> paths, resolved by
// render.py) come from the EDL. Frames are relative to the scene's start.

const ARABIC = "'Traditional Arabic','Arabic Typesetting','Segoe UI','Noto Naskh Arabic',serif";

// Line icon drawn as a glowing stroke, inline (for use inside cards and chips).
export const Stroke: React.FC<{ paths?: string[]; size: number; color: string; at?: number; glow?: boolean; width?: number }> = ({ paths, size, color, at = 0, glow = true, width = 1.8 }) => {
  const f = useCurrentFrame();
  if (!paths || !paths.length) return null;
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} style={{ overflow: "visible", flex: "none", filter: glow ? `drop-shadow(0 0 6px ${color})` : "none" }}>
      {paths.map((d, i) => (
        <path key={i} d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1}
          strokeDashoffset={1 - ramp(f, at + i * 3, at + i * 3 + 10)} />
      ))}
    </svg>
  );
};

// Night stage: deep navy with a slow drifting glow and twinkling stars.
const Night: React.FC<{ h: number; brand: Brand; stars?: number; children: React.ReactNode; glowAt?: string }> = ({ h, brand, stars = 70, children, glowAt = "50% 35%" }) => {
  const f = useCurrentFrame();
  const { width } = useVideoConfig();
  return (
    <AbsoluteFill style={{ height: h, overflow: "hidden", background: `radial-gradient(ellipse 85% 60% at ${glowAt}, ${brand.glow}40 0%, #0d0b22 50%, #05040c 100%)` }}>
      {new Array(stars).fill(0).map((_, i) => {
        const x = random(`sx${i}`) * width, y = random(`sy${i}`) * h, r = 0.8 + random(`sr${i}`) * 2.2;
        const tw = 0.35 + 0.65 * Math.abs(Math.sin(f / (9 + random(`st${i}`) * 14) + i));
        return <div key={i} style={{ position: "absolute", left: x, top: y - f * 0.15 * r, width: r * 2, height: r * 2, borderRadius: "50%", background: "#fff", opacity: tw * 0.7,
          boxShadow: r > 2.2 ? "0 0 8px #fff" : "none" }} />;
      })}
      {children}
    </AbsoluteFill>
  );
};

const glass: React.CSSProperties = { background: "rgba(22,20,40,0.55)", backdropFilter: "blur(22px)", border: "1.5px solid rgba(255,255,255,0.16)",
  boxShadow: "0 24px 60px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.12)" };

// ------------------------------------------------------------------ metrics dashboard
// Concentric rings fill as each metric is named, then all close together (goal reached).
// p: {items: [{label, value, unit?, at, color, lineicon?}], closeAt, done?: "goal reached"}
export const RingsDash: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { width, fps } = useVideoConfig();
  const items: { label: string; value: number; unit?: string; at: number; color: string; paths?: string[] }[] = p.items;
  const closeAt: number = p.closeAt ?? dur - 20;
  const cx = width / 2, cy = h * 0.32, R0 = h * 0.19, sw = h * 0.032;
  const closed = ramp(f, closeAt, closeAt + 12, 0, 1, eInOut);
  const pulse = f >= closeAt + 12 ? Math.max(0, 1 - (f - closeAt - 12) / 14) : 0;
  const tilt = interpolate(f, [0, dur], [14, 4], clamp);
  return (
    <Night h={h} brand={brand} stars={40}>
      <AbsoluteFill style={{ perspective: 1800 }}>
        <AbsoluteFill style={{ transform: `rotateX(${tilt}deg) scale(${1 + 0.05 * f / dur})`, transformOrigin: "50% 40%" }}>
          <svg width={width} height={h} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
            {items.map((it, i) => {
              const r = R0 - i * (sw * 1.25);
              const grow = ramp(f, it.at, it.at + 18) * 0.72;
              const prog = Math.min(1, grow + closed * (1 - grow));
              return (
                <g key={i} transform={`rotate(-90 ${cx} ${cy})`}>
                  <circle cx={cx} cy={cy} r={r} fill="none" stroke={it.color} strokeOpacity={0.16} strokeWidth={sw} />
                  <circle cx={cx} cy={cy} r={r} fill="none" stroke={it.color} strokeWidth={sw} strokeLinecap="round" pathLength={1} strokeDasharray={1}
                    strokeDashoffset={1 - prog} style={{ filter: `drop-shadow(0 0 ${10 + 20 * pulse}px ${it.color})` }} />
                </g>
              );
            })}
          </svg>
          <div style={{ position: "absolute", left: 0, right: 0, top: cy - h * 0.05, textAlign: "center", fontFamily: hand, fontWeight: 700, fontSize: h * 0.06,
            color: "#fff", opacity: ramp(f, closeAt + 6, closeAt + 14), transform: `scale(${1 + 0.15 * pulse}) rotate(-4deg)` }}>{p.done ?? "goal reached"}</div>
        </AbsoluteFill>
      </AbsoluteFill>
      <div style={{ position: "absolute", left: width * 0.05, right: width * 0.05, top: h * 0.6, display: "flex", gap: width * 0.025, justifyContent: "center" }}>
        {items.map((it, i) => {
          const s = pop(f - it.at, fps, 13, 220, 0.7);
          const v = countTo(f, it.at + 2, 18, it.value, 0);
          return (
            <div key={i} style={{ ...glass, flex: 1, borderRadius: 30, padding: `${h * 0.022}px ${width * 0.02}px`, opacity: f < it.at ? 0 : Math.min(1, s * 1.5),
              transform: `translateY(${(1 - s) * 60}px) scale(${0.85 + 0.15 * s})`, textAlign: "center" }}>
              <div style={{ display: "flex", justifyContent: "center", height: h * 0.055 }}><Stroke paths={it.paths} size={h * 0.055} color={it.color} at={it.at} /></div>
              <div style={{ fontFamily: sans, fontWeight: 900, fontSize: h * 0.06, color: "#fff", letterSpacing: "-0.03em", fontVariantNumeric: "tabular-nums", marginTop: 6 }}>
                {fmtNum(v, "en")}<span style={{ fontSize: h * 0.028, fontWeight: 700, color: it.color, marginLeft: 6 }}>{it.unit ?? ""}</span>
              </div>
              <div style={{ fontFamily: sans, fontWeight: 600, fontSize: h * 0.024, color: "rgba(255,255,255,0.65)", letterSpacing: "0.12em", textTransform: "uppercase" }}>{it.label}</div>
            </div>
          );
        })}
      </div>
    </Night>
  );
};

// ------------------------------------------------------------------ balance scale
// The scale draws itself, then tips toward the right pan; labels hang under the pans.
// p: {drawAt, tipAt, tipDeg?, left: {t, at}, right: {t, at}, kicker?, kickerAt?}
export const BalanceScale: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { width, fps } = useVideoConfig();
  const draw = (a: number, b: number) => 1 - ramp(f - (p.drawAt ?? 0), a, b, 0, 1, eInOut);
  const tipS = f >= p.tipAt ? pop(f - p.tipAt, fps, 7, 90, 1.1) : 0;
  const th = (p.tipDeg ?? 9) * tipS * Math.PI / 180;      // positive: right side down
  const S = Math.min(width * 0.9, h * 1.1) / 600;          // svg units -> px
  const ox = width / 2 - 300 * S, oy = h * 0.53 - 260 * S;
  const bx = 300, by = 120, L = 200;
  const ends = [-1, 1].map((k) => ({ x: bx + k * L * Math.cos(th), y: by + k * L * Math.sin(th) }));
  const glowR = ramp(f, p.right?.at ?? dur, (p.right?.at ?? dur) + 10);
  const gold = brand.accent;
  const pan = (x: number, y: number, k: number, lit: number) => (
    <g key={k}>
      <path d={`M${x} ${y} L${x - 70} ${y + 150} M${x} ${y} L${x + 70} ${y + 150}`} stroke={gold} strokeWidth={3} fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={draw(14, 30)} />
      <path d={`M${x - 92} ${y + 150} Q ${x} ${y + 225} ${x + 92} ${y + 150} Z`} fill={lit ? `${gold}${Math.round(40 * lit).toString(16).padStart(2, "0")}` : "none"}
        stroke={gold} strokeWidth={4} pathLength={1} strokeDasharray={1} strokeDashoffset={draw(22, 38)} style={{ filter: lit ? `drop-shadow(0 0 ${30 * lit}px ${gold})` : "none" }} />
    </g>
  );
  const label = (x: number, y: number, it: { t: string; at: number } | undefined, lit: boolean) => it ? (
    <div style={{ position: "absolute", left: ox + x * S - 220, top: oy + (y + 240) * S, width: 440, textAlign: "center", opacity: ramp(f, it.at, it.at + 6),
      transform: `translateY(${(1 - ramp(f, it.at, it.at + 8)) * 20}px)`, fontFamily: lit ? serif : sans, fontStyle: lit ? "italic" : "normal", fontWeight: lit ? 400 : 700,
      fontSize: lit ? h * 0.075 : h * 0.036, color: lit ? gold : "rgba(255,255,255,0.55)", letterSpacing: lit ? 0 : "0.1em", textTransform: lit ? "none" : "uppercase",
      textShadow: lit ? `0 0 30px ${gold}88` : "none" }}>{it.t}</div>
  ) : null;
  return (
    <Night h={h} brand={brand} glowAt="50% 25%">
      {p.kicker ? <div style={{ position: "absolute", top: h * 0.06, width: "100%", textAlign: "center", fontFamily: hand, fontWeight: 700, fontSize: h * 0.05,
        color: "rgba(255,255,255,0.85)", opacity: ramp(f, p.kickerAt ?? 0, (p.kickerAt ?? 0) + 6) }}>{p.kicker}</div> : null}
      <svg width={width} height={h} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
        <g transform={`translate(${ox} ${oy}) scale(${S})`} style={{ filter: `drop-shadow(0 0 8px ${gold}aa)` }}>
          <path d="M300 120 L300 470 M220 470 L380 470 M250 470 Q300 430 350 470" stroke={gold} strokeWidth={5} fill="none" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={draw(0, 14)} />
          <circle cx={300} cy={100} r={14} fill="none" stroke={gold} strokeWidth={4} pathLength={1} strokeDasharray={1} strokeDashoffset={draw(4, 14)} />
          <line x1={ends[0].x} y1={ends[0].y} x2={ends[1].x} y2={ends[1].y} stroke={gold} strokeWidth={6} strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={draw(8, 20)} />
          {pan(ends[0].x, ends[0].y, 0, 0)}
          {pan(ends[1].x, ends[1].y, 1, glowR)}
        </g>
      </svg>
      {label(ends[0].x, ends[0].y, p.left, false)}
      {label(ends[1].x, ends[1].y, p.right, true)}
    </Night>
  );
};

// ------------------------------------------------------------------ kinetic equation
// Terms arrive on their spoken frames; the result counts up and lands with a glow.
// p: {terms: [{t, at, kind: "glyph"|"num"|"op"|"word", sub?}], result?: {to, at, label?, countDur?, prefix?},
//     glass?: true (frosted over the footage instead of the night stage), y?: fraction of h, size?: px}
export const Equation: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { width, fps } = useVideoConfig();
  const terms: { t: string; at: number; kind: string; sub?: string }[] = p.terms;
  const size: number = p.size ?? h * 0.12;
  const y = (p.y ?? 0.4) * h;
  const res = p.result;
  const gold = brand.accent;
  const inner = (
    <>
      <div style={{ position: "absolute", left: 0, right: 0, top: y, transform: "translateY(-50%)", display: "flex", justifyContent: "center", alignItems: "flex-start", gap: size * 0.22 }}>
        {terms.map((t, i) => {
          if (f < t.at) return null;
          const s = pop(f - t.at, fps, t.kind === "op" ? 14 : 10, 260, 0.7);
          const b = (1 - Math.min(1, s)) * 14;
          const body = t.kind === "glyph"
            ? <div style={{ width: size * 1.25, height: size * 1.25, borderRadius: size * 0.28, border: `3px solid ${gold}`, display: "flex", alignItems: "center", justifyContent: "center",
                background: `radial-gradient(circle at 50% 40%, ${gold}33, rgba(10,8,24,0.7))`, boxShadow: `0 0 40px ${gold}66, inset 0 0 30px ${gold}33`,
                fontFamily: ARABIC, fontSize: size * 0.95, color: "#fff", lineHeight: 1, paddingBottom: size * 0.12 }}>{t.t}</div>
            : <div style={{ fontFamily: t.kind === "num" ? display : t.kind === "word" ? serif : sans, fontStyle: t.kind === "word" ? "italic" : "normal",
                fontWeight: t.kind === "op" ? 300 : 400, fontSize: t.kind === "op" ? size * 0.75 : size, lineHeight: 1.25 / 1.0, color: t.kind === "op" ? "rgba(255,255,255,0.7)" : "#fff",
                textShadow: t.kind === "num" ? `0 0 26px ${gold}88` : "0 6px 20px rgba(0,0,0,0.5)", paddingTop: t.kind === "op" ? size * 0.12 : 0 }}>{t.t}</div>;
          return (
            <div key={i} style={{ textAlign: "center", transform: `translateY(${(1 - s) * 40}px) scale(${0.6 + 0.4 * s})`, opacity: Math.min(1, s * 1.6), filter: `blur(${b}px)` }}>
              {body}
              {t.sub ? <div style={{ fontFamily: hand, fontWeight: 700, fontSize: size * 0.3, color: gold, marginTop: size * 0.06, opacity: ramp(f, t.at + 4, t.at + 10), whiteSpace: "nowrap" }}>{t.sub}</div> : null}
            </div>
          );
        })}
      </div>
      {res && f >= res.at ? (() => {
        const s = pop(f - res.at, fps, 9, 240, 0.7);
        const cd = res.countDur ?? 14;
        const v = countTo(f, res.at, cd, res.to, res.from ?? 0);
        const land = f >= res.at + cd ? Math.max(0, 1 - (f - res.at - cd) / 12) : 0;
        return (
          <div style={{ position: "absolute", left: 0, right: 0, top: y + size * 1.15, textAlign: "center", transform: `scale(${0.7 + 0.3 * s + 0.08 * land})`, opacity: Math.min(1, s * 1.5) }}>
            <div style={{ fontFamily: display, fontSize: size * 1.7, lineHeight: 1, color: "#fff", fontVariantNumeric: "tabular-nums",
              textShadow: `0 0 8px #fff, 0 0 ${30 + 40 * land}px ${gold}, 0 0 90px ${gold}88` }}>{res.prefix ?? "= "}{fmtNum(v, "en")}</div>
            {res.label ? <div style={{ fontFamily: serif, fontStyle: "italic", fontSize: size * 0.55, color: gold, marginTop: size * 0.05, opacity: ramp(f, res.at + cd, res.at + cd + 8) }}>{res.label}</div> : null}
          </div>
        );
      })() : null}
    </>
  );
  if (p.glass) {
    const o = ramp(f, 0, 6);
    return (
      <AbsoluteFill style={{ height: h }}>
        <AbsoluteFill style={{ backdropFilter: `blur(${26 * o}px) brightness(${1 - 0.6 * o}) saturate(1.2)`, background: `rgba(8,6,20,${0.35 * o})` }} />
        {inner}
      </AbsoluteFill>
    );
  }
  return <Night h={h} brand={brand}>{inner}</Night>;
};

// ------------------------------------------------------------------ a page being counted
// A paper page of abstract text lines (right to left; no real script is imitated). A gold scanner
// passes over the lines while a letter counter ticks; then the multiplier and the result land.
// p: {scanAt, scanDur, letters, mult, multAt, resultAt, resultLabel, counterLabel?}
export const PageScan: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { width, fps } = useVideoConfig();
  const gold = brand.accent;
  const N = 11;
  const prog = ramp(f, p.scanAt, p.scanAt + p.scanDur, 0, 1, (x) => x);
  const letters = Math.round(prog * p.letters);
  const pw = width * 0.72, ph = h * 0.52, px = (width - pw) / 2, py = h * 0.14;
  const tilt = interpolate(f, [0, dur], [16, 6], clamp);
  const ms = pop(f - p.multAt, fps, 10, 260, 0.7);
  const rs = pop(f - p.resultAt, fps, 10, 200, 0.8);
  return (
    <Night h={h} brand={brand} stars={45} glowAt="50% 45%">
      <AbsoluteFill style={{ perspective: 2000 }}>
        <div style={{ position: "absolute", left: px, top: py, width: pw, height: ph, borderRadius: 26, background: "linear-gradient(170deg,#fbf7ec,#efe6d2)",
          boxShadow: `0 60px 120px rgba(0,0,0,0.6), 0 0 0 10px rgba(255,255,255,0.04), 0 0 80px ${gold}22`, transform: `rotateX(${tilt}deg) rotateZ(-2deg)`, overflow: "hidden" }}>
          <div style={{ position: "absolute", inset: 22, border: `3px double ${gold}`, borderRadius: 14 }} />
          {new Array(N).fill(0).map((_, i) => {
            const w = 0.82 - (random(`pw${i}`) * 0.18) - (i === N - 1 ? 0.35 : 0);
            const a = i / N, b = (i + 1) / N;
            const lp = Math.min(1, Math.max(0, (prog - a) / (b - a)));
            const top = 70 + i * ((ph - 140) / N);
            return (
              <div key={i} style={{ position: "absolute", right: 60, top, width: (pw - 120) * w, height: 16, borderRadius: 8, background: "#cfc4ad", overflow: "hidden" }}>
                <div style={{ position: "absolute", right: 0, top: 0, bottom: 0, width: `${lp * 100}%`, background: `linear-gradient(270deg, ${gold}, #f6d58a)` }} />
                {lp > 0 && lp < 1 ? <div style={{ position: "absolute", right: `${lp * 100}%`, top: -14, width: 6, height: 44, background: "#fff", boxShadow: `0 0 20px 6px ${gold}` }} /> : null}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
      <div style={{ ...glass, position: "absolute", left: width / 2, top: h * 0.025, transform: "translateX(-50%)", borderRadius: 60, padding: "16px 40px", whiteSpace: "nowrap",
        display: "flex", gap: 20, alignItems: "baseline", opacity: ramp(f, p.scanAt - 4, p.scanAt + 2) }}>
        <span style={{ fontFamily: sans, fontWeight: 700, fontSize: h * 0.026, color: "rgba(255,255,255,0.7)", letterSpacing: "0.14em" }}>{p.counterLabel ?? "LETTERS"}</span>
        <span style={{ fontFamily: display, fontSize: h * 0.05, color: "#fff", fontVariantNumeric: "tabular-nums", minWidth: h * 0.06, textAlign: "right" }}>{letters}</span>
        {f >= p.multAt ? <span style={{ fontFamily: display, fontSize: h * 0.05, color: gold, display: "inline-block", transform: `scale(${ms})` }}>× {p.mult}</span> : null}
      </div>
      {f >= p.resultAt ? (
        <div style={{ position: "absolute", left: 0, right: 0, top: py + ph + h * 0.035, textAlign: "center", opacity: Math.min(1, rs * 1.5), transform: `translateY(${(1 - rs) * 80}px)` }}>
          <span style={{ fontFamily: display, fontSize: h * 0.1, color: "#fff", textShadow: `0 0 10px #fff, 0 0 40px ${gold}, 0 0 90px ${gold}99` }}>
            = {fmtNum(countTo(f, p.resultAt, 14, p.letters * p.mult, 0), "en")}</span>
          <span style={{ fontFamily: serif, fontStyle: "italic", fontSize: h * 0.06, color: gold, marginLeft: 18 }}>{p.resultLabel}</span>
        </div>
      ) : null}
    </Night>
  );
};

// ------------------------------------------------------------------ app reveal
// A glowing app tile with a line icon draws on, the name types up letter by letter with a shine
// sweep, a serif-italic line underneath. Generic tile: no product logo is reproduced.
// p: {name, sub?, at?, paths?, tileFrom?, tileTo?}
export const AppReveal: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { width, fps } = useVideoConfig();
  const at = p.at ?? 2;
  const s = pop(f - at, fps, 10, 180, 0.8);
  const T = h * 0.17;
  const name: string = p.name;
  const shine = interpolate(f, [at + 14, at + 34], [-30, 130], clamp);
  return (
    <Night h={h} brand={brand} glowAt="50% 40%">
      <AbsoluteFill style={{ background: `conic-gradient(from ${f * 0.6}deg at 50% 38%, transparent 0deg, ${brand.glow}22 30deg, transparent 60deg, transparent 180deg, ${brand.accent}18 210deg, transparent 240deg)`,
        opacity: ramp(f, at, at + 10) }} />
      <div style={{ position: "absolute", left: width / 2 - T / 2, top: h * 0.38 - T / 2, width: T, height: T, borderRadius: T * 0.27,
        background: `linear-gradient(145deg, ${p.tileFrom ?? brand.glow}, ${p.tileTo ?? "#2b1b6e"})`, display: "flex", alignItems: "center", justifyContent: "center",
        boxShadow: `0 30px 80px rgba(0,0,0,0.5), 0 0 ${60 * s}px ${brand.glow}aa, inset 0 2px 0 rgba(255,255,255,0.35)`,
        transform: `scale(${s}) rotate(${(1 - s) * -25}deg)`, opacity: Math.min(1, s * 1.4) }}>
        <Stroke paths={p.paths} size={T * 0.58} color="#fff" at={at + 4} width={1.6} />
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: h * 0.53, textAlign: "center", fontFamily: sans, fontWeight: 900, fontSize: h * 0.11, letterSpacing: "-0.045em", color: "#fff",
        WebkitMaskImage: undefined }}>
        {name.split("").map((c, i) => {
          const k = ramp(f, at + 6 + i * 2, at + 14 + i * 2);
          return <span key={i} style={{ display: "inline-block", opacity: k, transform: `translateY(${(1 - k) * 50}px)`, filter: `blur(${(1 - k) * 10}px)`,
            backgroundImage: `linear-gradient(100deg, #fff ${shine - 20}%, ${brand.accent} ${shine}%, #fff ${shine + 20}%)`, WebkitBackgroundClip: "text", color: "transparent" }}>{c}</span>;
        })}
      </div>
      {p.sub ? <div style={{ position: "absolute", left: 0, right: 0, top: h * 0.53 + h * 0.13, textAlign: "center", fontFamily: serif, fontStyle: "italic", fontSize: h * 0.045,
        color: brand.accent, opacity: ramp(f, at + 18, at + 26), transform: `translateY(${(1 - ramp(f, at + 18, at + 26)) * 16}px)` }}>{p.sub}</div> : null}
    </Night>
  );
};

// ------------------------------------------------------------------ end card
// Name, store pills that pop on their spoken frames, a hand-written "link in bio" with an arrow.
// p: {name, sub?, pills: [{t, at, paths?}], bioAt, bio?}
export const EndCard: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { width, fps } = useVideoConfig();
  const ns = pop(f, fps, 12, 180, 0.8);
  const pills: { t: string; at: number; paths?: string[] }[] = p.pills ?? [];
  return (
    <Night h={h} brand={brand} glowAt="50% 30%">
      <div style={{ position: "absolute", left: 0, right: 0, top: h * 0.2, textAlign: "center", transform: `scale(${0.8 + 0.2 * ns})`, opacity: Math.min(1, ns * 1.5) }}>
        {p.kicker ? <div style={{ fontFamily: hand, fontWeight: 700, fontSize: h * 0.04, color: "rgba(255,255,255,0.8)" }}>{p.kicker}</div> : null}
        <div style={{ fontFamily: sans, fontWeight: 900, fontSize: h * 0.095, letterSpacing: "-0.045em", color: "#fff", textShadow: `0 0 50px ${brand.glow}` }}>{p.name}</div>
        {p.sub ? <div style={{ fontFamily: serif, fontStyle: "italic", fontSize: h * 0.04, color: brand.accent }}>{p.sub}</div> : null}
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: h * 0.47, display: "flex", flexDirection: "column", alignItems: "center", gap: h * 0.022 }}>
        {pills.map((pl, i) => {
          const s = pop(f - pl.at, fps, 11, 240, 0.7);
          return (
            <div key={i} style={{ ...glass, display: "flex", alignItems: "center", gap: 26, borderRadius: 80, padding: `${h * 0.016}px ${h * 0.035}px`, minWidth: width * 0.56,
              justifyContent: "center", opacity: f < pl.at ? 0 : Math.min(1, s * 1.5), transform: `translateX(${(1 - s) * (i % 2 ? 140 : -140)}px)`,
              background: i === 0 ? "rgba(255,255,255,0.95)" : "rgba(22,20,40,0.6)" }}>
              <Stroke paths={pl.paths} size={h * 0.04} color={i === 0 ? "#120f24" : "#fff"} at={pl.at} glow={i !== 0} />
              <span style={{ fontFamily: sans, fontWeight: 800, fontSize: h * 0.036, color: i === 0 ? "#120f24" : "#fff", letterSpacing: "-0.01em" }}>{pl.t}</span>
            </div>
          );
        })}
      </div>
      {f >= p.bioAt ? (
        <div style={{ position: "absolute", left: 0, right: 0, top: h * 0.74, textAlign: "center" }}>
          <div style={{ fontFamily: hand, fontWeight: 700, fontSize: h * 0.055, color: brand.accent, transform: `rotate(-4deg) scale(${pop(f - p.bioAt, fps, 9, 260, 0.6)})` }}>{p.bio ?? "link in bio"}</div>
          <svg width={120} height={140} viewBox="0 0 120 140" style={{ overflow: "visible", marginTop: 6 }}>
            <path d="M60 6 C 40 50, 80 80, 60 128 M36 104 L60 130 L84 104" fill="none" stroke={brand.accent} strokeWidth={7} strokeLinecap="round" strokeLinejoin="round"
              pathLength={1} strokeDasharray={1} strokeDashoffset={1 - ramp(f, p.bioAt + 3, p.bioAt + 14)} style={{ filter: `drop-shadow(0 0 10px ${brand.accent})` }} />
          </svg>
        </div>
      ) : null}
    </Night>
  );
};

// ------------------------------------------------------------------ overlay: floating metric chips
// Glass chips (icon + text) pop in on their frames and float gently; meant to sit behind the matted
// speaker (behind: true) or in empty parts of the frame. p: {items: [{t, x, y, at, color?, paths?}]}
export const FloatChips: React.FC<{ items: { t: string; x: number; y: number; at: number; color?: string; paths?: string[]; size?: number }[]; brand: Brand; dur: number }> = ({ items, brand, dur }) => {
  const f = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const out = ramp(f, dur - 6, dur);
  return (
    <AbsoluteFill style={{ opacity: 1 - out, pointerEvents: "none" }}>
      {items.map((it, i) => {
        if (f < it.at) return null;
        const s = pop(f - it.at, fps, 12, 220, 0.7);
        const fy = Math.sin((f + i * 17) / 16) * 10, fx = Math.cos((f + i * 11) / 21) * 6;
        const c = it.color ?? brand.accent;
        const sz = it.size ?? 46;
        return (
          <div key={i} style={{ ...glass, position: "absolute", left: it.x * width + fx, top: it.y * height + fy, transform: `translate(-50%,-50%) scale(${0.6 + 0.4 * s})`,
            opacity: Math.min(1, s * 1.5), display: "flex", alignItems: "center", gap: sz * 0.35, borderRadius: sz, padding: `${sz * 0.32}px ${sz * 0.55}px`, whiteSpace: "nowrap" }}>
            <Stroke paths={it.paths} size={sz * 1.05} color={c} at={it.at} />
            <span style={{ fontFamily: sans, fontWeight: 800, fontSize: sz, color: "#fff", letterSpacing: "-0.02em" }}>{it.t}</span>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

export const EXPLAINER: Record<string, React.FC<SceneProps>> = { RingsDash, BalanceScale, Equation, PageScan, AppReveal, EndCard };
