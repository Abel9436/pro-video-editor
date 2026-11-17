import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Cursor, Glitch, Icon3D, LightLeak, Scribble, Typed, clamp, eInOut, pop, ramp } from "./fx";
import { Brand, display, hand, mono, sans, serif } from "./theme";

export type SceneProps = { dur: number; h: number; brand: Brand; p: Record<string, any> };

// ------------------------------------------------------------------ stages
const Stage: React.FC<{ children: React.ReactNode; tone?: "dark" | "paper"; brand: Brand; h: number }> = ({ children, tone = "dark", brand, h }) => {
  const f = useCurrentFrame();
  const gx = 50 + Math.sin(f / 30) * 15;
  const bg = tone === "dark"
    ? `radial-gradient(ellipse 80% 55% at ${gx}% 30%, ${brand.glow}55 0%, #16122a 45%, #07060c 100%)`
    : `radial-gradient(ellipse 90% 70% at ${gx}% 20%, #ffffff 0%, ${brand.paper} 55%, #e2ddd2 100%)`;
  return (
    <AbsoluteFill style={{ height: h, background: bg, overflow: "hidden" }}>
      <AbsoluteFill style={{ opacity: tone === "dark" ? 0.07 : 0.05, backgroundImage: `radial-gradient(${tone === "dark" ? "#fff" : "#000"} 1.4px, transparent 1.4px)`, backgroundSize: "34px 34px" }} />
      {children}
    </AbsoluteFill>
  );
};

// Slow camera drift + a 3D tilt so flat UI reads as an object in space.
const Drift: React.FC<{ children: React.ReactNode; rx?: number; ry?: number; rz?: number; push?: number; dur: number }> = ({ children, rx = 10, ry = -14, rz = 0, push = 0.08, dur }) => {
  const f = useCurrentFrame();
  const k = f / Math.max(1, dur);
  return (
    <AbsoluteFill style={{ perspective: 2200, perspectiveOrigin: "50% 40%" }}>
      <AbsoluteFill style={{ transformStyle: "preserve-3d",
        transform: `scale(${1 + push * k}) rotateX(${rx * (1 - 0.4 * k)}deg) rotateY(${ry * (1 - 0.5 * k)}deg) rotateZ(${rz}deg)` }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

const Phone: React.FC<{ children: React.ReactNode; w: number; cx: number; cy: number; screen?: string }> = ({ children, w, cx, cy, screen = "#0d0d12" }) => {
  const h = w * 2.06;
  return (
    <div style={{ position: "absolute", left: cx - w / 2, top: cy - h / 2, width: w, height: h, borderRadius: w * 0.15, padding: w * 0.035,
      background: "linear-gradient(145deg,#5a5866,#1d1c24 40%,#3a3946)", boxShadow: "0 60px 120px rgba(0,0,0,0.55), inset 0 0 0 2px rgba(255,255,255,0.18)" }}>
      <div style={{ position: "relative", width: "100%", height: "100%", borderRadius: w * 0.12, background: screen, overflow: "hidden" }}>
        {children}
        <div style={{ position: "absolute", top: w * 0.03, left: "50%", width: w * 0.3, height: w * 0.085, marginLeft: -w * 0.15, borderRadius: w, background: "#000" }} />
      </div>
    </div>
  );
};

// ------------------------------------------------------------------ 1. scam notifications
export const ScamNotifs: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const items: { at: number; app: string; title: string; body: string; icon: string }[] = p.items;
  const pw = Math.min(width * 0.62, h * 0.43);
  return (
    <Stage brand={brand} h={h}>
      <Icon3D name="3d-coin" x={width * 0.12} y={h * 0.2} size={220} blur={10} floatAmp={18} />
      <Drift dur={dur} rx={8} ry={-16}>
        <Phone w={pw} cx={width / 2} cy={h / 2} screen="linear-gradient(180deg,#2b1f5c 0%,#5b2a6e 45%,#0e0b1a 100%)">
          <div style={{ position: "absolute", top: pw * 0.2, width: "100%", textAlign: "center", color: "#fff", fontFamily: sans }}>
            <div style={{ fontSize: pw * 0.055, fontWeight: 600, opacity: 0.85 }}>Friday, 15 November</div>
            <div style={{ fontSize: pw * 0.3, fontWeight: 700, letterSpacing: "-0.04em", lineHeight: 1 }}>9:41</div>
          </div>
          {items.map((n, i) => {
            const s = pop(f - n.at, fps, 15, 210, 0.8);
            if (f < n.at) return null;
            const order = items.filter((m) => f >= m.at && m.at > n.at).length; // newer ones push older down
            const y = pw * 0.78 + order * pw * 0.36;
            return (
              <div key={i} style={{ position: "absolute", left: pw * 0.05, right: pw * 0.05, top: y, transform: `translateY(${(1 - s) * -60}px) scale(${0.9 + 0.1 * s})`, opacity: Math.min(1, s * 1.5),
                transition: "none", background: "rgba(245,245,250,0.82)", backdropFilter: "blur(20px)", borderRadius: pw * 0.06, padding: `${pw * 0.035}px ${pw * 0.045}px`,
                display: "flex", gap: pw * 0.035, alignItems: "center", boxShadow: "0 10px 30px rgba(0,0,0,0.3)" }}>
                <Img src={staticFile(`icons3d/${n.icon}_color.png`)} style={{ width: pw * 0.13, height: pw * 0.13, borderRadius: pw * 0.03, background: "#111", padding: 4 }} />
                <div style={{ flex: 1, fontFamily: sans, color: "#111", minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: pw * 0.036, fontWeight: 600, opacity: 0.55 }}><span>{n.app.toUpperCase()}</span><span>now</span></div>
                  <div style={{ fontSize: pw * 0.048, fontWeight: 800, marginTop: 2 }}>{n.title}</div>
                  <div style={{ fontSize: pw * 0.042, fontWeight: 500, opacity: 0.8 }}>{n.body}</div>
                </div>
              </div>
            );
          })}
        </Phone>
      </Drift>
      <Icon3D name="money" x={width * 0.86} y={h * 0.78} size={260} blur={7} floatAmp={22} rot={-12} />
    </Stage>
  );
};

// ------------------------------------------------------------------ 2. the millionaire promise, then BS
export const MillionaireBS: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { width } = useVideoConfig();
  const bs: number = p.bsAt;
  const v = Math.round(interpolate(f, [0, bs - 4], [0, 1000000], { ...clamp, easing: (x) => x * x * x }));
  const glitch = f >= bs - 2 && f < bs + 4;
  const dead = f >= bs;
  return (
    <Stage brand={brand} h={h}>
      <Glitch active={glitch} seed="bs">
        <AbsoluteFill style={{ filter: dead ? "grayscale(0.9) brightness(0.55)" : "none" }}>
          <Icon3D name="money-bag" x={width * 0.26} y={h * 0.3} size={300} at={2} floatAmp={14} rot={-8} />
          <Icon3D name="crown" x={width * 0.76} y={h * 0.26} size={240} at={8} floatAmp={12} rot={12} />
          <div style={{ position: "absolute", top: h * 0.5, width: "100%", textAlign: "center", transform: "translateY(-50%)" }}>
            <div style={{ fontFamily: sans, fontWeight: 700, fontSize: 40, letterSpacing: "0.3em", color: "rgba(255,255,255,0.7)" }}>NET WORTH</div>
            <div style={{ fontFamily: display, fontSize: 190, lineHeight: 1.05, fontVariantNumeric: "tabular-nums",
              background: `linear-gradient(180deg,#fff 0%,${brand.accent} 100%)`, WebkitBackgroundClip: "text", color: "transparent",
              filter: `drop-shadow(0 0 30px ${brand.accent}55)` }}>${v.toLocaleString("en-US")}</div>
          </div>
          <Icon3D name="3d-coin" x={width * 0.18} y={h * 0.8} size={200} at={4} blur={6} floatAmp={20} />
          <Icon3D name="dollar" x={width * 0.84} y={h * 0.76} size={230} at={10} floatAmp={16} rot={-14} />
        </AbsoluteFill>
      </Glitch>
      {dead ? (
        <>
          <Scribble at={bs} dur={6} color={brand.alert} width={18} vb="0 0 1000 200"
            d="M20 120 C 200 60, 380 160, 520 90 S 820 60, 980 110" style={{ left: width * 0.04, top: h * 0.45, width: width * 0.92, height: h * 0.1 }} />
          <div style={{ position: "absolute", top: h * 0.62, width: "100%", textAlign: "center", fontFamily: hand, fontWeight: 700, fontSize: 220, color: brand.alert,
            transform: `rotate(-8deg) scale(${pop(f - bs - 3, 25, 9, 300, 0.6)})`, textShadow: "0 8px 20px rgba(0,0,0,0.5)" }}>BS.</div>
        </>
      ) : null}
    </Stage>
  );
};

// ------------------------------------------------------------------ 3. knowledge behind a paywall
export const Paywall: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const lockAt: number = p.lockAt;
  const cw = width * 0.8;
  const lines = new Array(9).fill(0);
  const lockS = pop(f - lockAt, fps, 9, 260, 0.8);
  return (
    <Stage brand={brand} h={h} tone="paper">
      <Drift dur={dur} rx={14} ry={10} push={0.06}>
        <div style={{ position: "absolute", left: (width - cw) / 2, top: h * 0.12, width: cw, height: h * 0.76, background: "#fff", borderRadius: 28,
          boxShadow: "0 50px 100px rgba(40,30,20,0.25)", padding: 54, overflow: "hidden", fontFamily: sans, color: "#15131c" }}>
          <div style={{ fontFamily: mono, fontSize: 24, color: "#8a8592", letterSpacing: "0.1em" }}>INDUSTRY  ·  INSIDERS ONLY</div>
          <div style={{ fontFamily: serif, fontStyle: "italic", fontSize: 84, lineHeight: 1.0, marginTop: 18 }}>How it actually works</div>
          {lines.map((_, i) => <div key={i} style={{ height: 20, borderRadius: 10, background: "#e6e2ea", marginTop: i === 0 ? 40 : 22, width: `${92 - (i * 13) % 35}%` }} />)}
          <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: "62%", background: "linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.92) 30%, #fff 60%)" }} />
          <div style={{ position: "absolute", left: 0, right: 0, bottom: 70, textAlign: "center" }}>
            <div style={{ fontWeight: 800, fontSize: 46, letterSpacing: "-0.02em" }}>Members only</div>
            <div style={{ fontWeight: 500, fontSize: 30, color: "#6d6876", marginTop: 6 }}>Subscribe to keep reading</div>
            <div style={{ display: "inline-block", marginTop: 26, background: "#15131c", color: "#fff", fontWeight: 800, fontSize: 30, padding: "20px 56px", borderRadius: 60 }}>Unlock access</div>
          </div>
        </div>
      </Drift>
      {f >= lockAt ? (
        <div style={{ position: "absolute", left: width / 2 - 170, top: h * 0.3 - (1 - lockS) * 400, width: 340, height: 340, transform: `rotate(${(1 - lockS) * -20}deg)` }}>
          <Img src={staticFile("icons3d/lock_color.png")} style={{ width: "100%", height: "100%", filter: "drop-shadow(0 30px 40px rgba(0,0,0,0.35))" }} />
        </div>
      ) : null}
      <Icon3D name="key" x={width * 0.1} y={h * 0.86} size={210} blur={8} floatAmp={20} rot={30} />
    </Stage>
  );
};

// ------------------------------------------------------------------ 4. pay to play: checkout
export const Checkout: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const click: number = p.clickAt;
  const cw = width * 0.78, ch = h * 0.72, x0 = (width - cw) / 2, y0 = (h - ch) / 2;
  const bx = x0 + cw / 2, by = y0 + ch * 0.8;
  const cx = interpolate(f, [0, click - 2], [width * 0.95, bx + 20], { ...clamp, easing: eInOut });
  const cy = interpolate(f, [0, click - 2], [h * 1.05, by + 10], { ...clamp, easing: eInOut });
  const press = f >= click && f < click + 4 ? 1 : 0;
  const paid = f >= click + 6;
  const enter = pop(f, fps, 16, 180);
  return (
    <Stage brand={brand} h={h}>
      <div style={{ position: "absolute", left: x0, top: y0, width: cw, height: ch, borderRadius: 34, padding: 40, transform: `translateY(${(1 - enter) * 80}px)`, opacity: enter,
        background: "linear-gradient(160deg,rgba(255,255,255,0.14),rgba(255,255,255,0.04))", border: "1.5px solid rgba(255,255,255,0.22)",
        backdropFilter: "blur(30px)", boxShadow: "0 40px 90px rgba(0,0,0,0.5)", fontFamily: sans, color: "#fff", boxSizing: "border-box" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <Img src={staticFile("icons3d/crown_color.png")} style={{ width: ch * 0.2, height: ch * 0.2 }} />
          <div>
            <div style={{ fontWeight: 800, fontSize: ch * 0.075, letterSpacing: "-0.02em" }}>Insider Mastermind</div>
            <div style={{ fontWeight: 500, fontSize: ch * 0.045, opacity: 0.65 }}>Lifetime access · 1 seat left</div>
          </div>
        </div>
        <div style={{ marginTop: ch * 0.06, fontFamily: display, fontSize: ch * 0.2, lineHeight: 1, color: brand.accent }}>$9,999</div>
        <div style={{ position: "absolute", left: 40, right: 40, top: ch * 0.68, height: ch * 0.2, borderRadius: ch * 0.1, display: "flex", alignItems: "center", justifyContent: "center",
          background: paid ? "#19C37D" : brand.accent, color: brand.ink, fontWeight: 900, fontSize: ch * 0.07, transform: `scale(${press ? 0.96 : 1})`,
          boxShadow: `0 0 ${paid ? 50 : 20}px ${paid ? "#19C37D" : brand.accent}88` }}>{paid ? "Paid ✓" : "Pay now"}</div>
      </div>
      {f < click + 14 ? <Cursor x={cx} y={cy} press={press} /> : null}
      <Icon3D name="wallet" x={width * 0.88} y={h * 0.16} size={180} blur={6} floatAmp={14} rot={10} />
    </Stage>
  );
};

// ------------------------------------------------------------------ 5. work through the ranks
export const Ranks: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const steps: { t: string; y: string }[] = p.steps;
  const per = (dur - 6) / steps.length;
  const n = Math.min(steps.length - 1, Math.floor(f / per));
  const fill = Math.min(1, f / (per * (steps.length - 0.4)));
  const top = h * 0.1, bot = h * 0.76, x = width * 0.22;
  return (
    <Stage brand={brand} h={h}>
      <div style={{ position: "absolute", left: x - 3, top, width: 6, height: bot - top, background: "rgba(255,255,255,0.15)", borderRadius: 3 }} />
      <div style={{ position: "absolute", left: x - 3, bottom: h - bot, width: 6, height: (bot - top) * fill, background: brand.accent, borderRadius: 3, boxShadow: `0 0 18px ${brand.accent}` }} />
      {steps.map((s, i) => {
        const yy = bot - (i / (steps.length - 1)) * (bot - top);
        const a = pop(f - i * per, fps, 14, 220);
        const on = i <= n;
        return (
          <React.Fragment key={i}>
            <div style={{ position: "absolute", left: x - 22, top: yy - 22, width: 44, height: 44, borderRadius: 22, background: on ? brand.accent : "#2a2638",
              border: "3px solid rgba(255,255,255,0.3)", transform: `scale(${on ? 1 + 0.2 * (i === n ? Math.sin(f / 4) * 0.5 + 0.5 : 0) : 0.8})` }} />
            <div style={{ position: "absolute", left: x + 60, top: yy - 52, opacity: on ? a : 0.25, transform: `translateX(${(1 - a) * 40}px)`,
              background: on ? "rgba(255,255,255,0.1)" : "transparent", border: "1.5px solid rgba(255,255,255,0.18)", borderRadius: 22, padding: "16px 30px", minWidth: width * 0.5 }}>
              <div style={{ fontFamily: mono, fontSize: 24, color: brand.accent, letterSpacing: "0.08em" }}>{s.y}</div>
              <div style={{ fontFamily: sans, fontWeight: 800, fontSize: 46, color: "#fff", letterSpacing: "-0.02em" }}>{s.t}</div>
            </div>
          </React.Fragment>
        );
      })}
      <Icon3D name="trophy" x={width * 0.83} y={top + 30} size={190} at={Math.round(per * (steps.length - 1))} floatAmp={10} />
    </Stage>
  );
};

// ------------------------------------------------------------------ 6. notes app typing (light)
export const Notes: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { width } = useVideoConfig();
  const lines: { t: string; at: number; em?: boolean }[] = p.lines;
  return (
    <Stage brand={brand} h={h} tone="paper">
      <Drift dur={dur} rx={6} ry={-8} push={0.1}>
        <div style={{ position: "absolute", left: width * 0.08, right: width * 0.08, top: h * 0.1, bottom: h * 0.1, background: "#fffdf7", borderRadius: 36,
          boxShadow: "0 50px 100px rgba(40,30,20,0.22)", padding: "50px 56px", fontFamily: sans, color: "#1b1922", boxSizing: "border-box" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 30, color: "#d29b16", fontWeight: 600 }}><span>‹ Notes</span><span>Done</span></div>
          <div style={{ fontWeight: 900, fontSize: 64, marginTop: 30, letterSpacing: "-0.03em" }}>The real path</div>
          <div style={{ fontFamily: mono, fontSize: 22, color: "#9a95a3", marginTop: 6 }}>15 November 2026 at 09:41</div>
          {lines.map((l, i) => (
            <div key={i} style={{ marginTop: 40, fontSize: l.em ? 104 : 66, fontWeight: l.em ? 400 : 700, fontFamily: l.em ? serif : sans, fontStyle: l.em ? "italic" : "normal",
              lineHeight: 1.1, color: l.em ? "#1b1922" : "#2b2933", letterSpacing: l.em ? 0 : "-0.02em" }}>
              {f >= l.at ? <Typed text={l.t} at={l.at} cps={22} caret={i === lines.filter((m) => f >= m.at).length - 1} caretColor="#d29b16" /> : null}
              {l.em && f >= l.at + (l.t.length / 22) * 25 ? (
                <Scribble at={Math.round(l.at + (l.t.length / 22) * 25)} dur={8} color={brand.accent} width={26} vb="0 0 600 40"
                  d="M5 28 C 150 14, 300 34, 595 18" style={{ position: "relative", display: "block", width: "85%", height: 34, marginTop: -6, mixBlendMode: "multiply" }} />
              ) : null}
            </div>
          ))}
        </div>
      </Drift>
      <Icon3D name="bulb" x={width * 0.86} y={h * 0.12} size={210} at={6} floatAmp={14} rot={10} />
    </Stage>
  );
};

// ------------------------------------------------------------------ 7. a few years later
export const YearFlip: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { width } = useVideoConfig();
  const from: number = p.from, to: number = p.to;
  const t = interpolate(f, [2, dur - 10], [0, 1], { ...clamp, easing: eInOut });
  const yv = from + (to - from) * t;
  const yi = Math.floor(yv), frac = yv - yi;
  const digit = (y: number, o: number, k: number) => (
    <div key={`${y}${k}`} style={{ position: "absolute", width: "100%", textAlign: "center", top: h * 0.5 - 150 + o * 260, opacity: 1 - Math.abs(o) * 0.9,
      filter: `blur(${Math.abs(o) * 14}px)`, fontFamily: display, fontSize: 300, lineHeight: "300px", color: "#fff", letterSpacing: "-0.02em",
      transform: `scale(${1 - Math.abs(o) * 0.25})` }}>{y}</div>
  );
  return (
    <Stage brand={brand} h={h}>
      <Icon3D name="calender" x={width * 0.5} y={h * 0.2} size={250} floatAmp={10} />
      {digit(yi, -frac, 0)}
      {digit(yi + 1, 1 - frac, 1)}
      <div style={{ position: "absolute", top: h * 0.72, width: "100%", textAlign: "center", fontFamily: hand, fontWeight: 700, fontSize: 90, color: brand.accent,
        transform: "rotate(-4deg)", opacity: ramp(f, 4, 10) }}>a few years later…</div>
      <LightLeak dur={dur} />
    </Stage>
  );
};

// ------------------------------------------------------------------ 8. real footage with an editorial headline
export const Footage: React.FC<SceneProps> = ({ dur, h, brand, p }) => {
  const f = useCurrentFrame();
  const { width, fps } = useVideoConfig();
  const s = pop(f - (p.headAt ?? 3), fps, 14, 200);
  return (
    <AbsoluteFill style={{ height: h, overflow: "hidden", background: "#000" }}>
      <OffthreadVideo src={staticFile(p.src)} startFrom={p.startFrom ?? 0} muted
        style={{ position: "absolute", height: h * 1.08, left: "50%", top: -h * 0.04, transform: `translateX(-50%) scale(${1 + 0.06 * f / dur})` }} />
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(0,0,0,0.55) 0%, transparent 35%, transparent 65%, rgba(0,0,0,0.6) 100%)" }} />
      <div style={{ position: "absolute", top: h * 0.12, width: "100%", textAlign: "center", opacity: Math.min(1, s * 1.5), transform: `translateY(${(1 - s) * 30}px)` }}>
        <div style={{ fontFamily: hand, fontWeight: 700, fontSize: 64, color: "#fff", transform: "rotate(-3deg)" }}>{p.kicker}</div>
        <div style={{ fontFamily: serif, fontStyle: "italic", fontSize: 170, lineHeight: 0.9, color: brand.accent, textShadow: `0 0 40px ${brand.accent}55, 0 8px 30px rgba(0,0,0,0.6)` }}>{p.head}</div>
      </div>
      <LightLeak dur={Math.min(dur, 18)} hue="255,180,90" />
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ 9. closing stack on the speaker
export const EndStack: React.FC<{ items: { at: number; t: string; icon: string; em?: boolean }[]; dur: number; brand: Brand }> = ({ items, dur, brand }) => {
  const f = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const out = ramp(f, dur - 3, dur);
  return (
    <div style={{ position: "absolute", left: width * 0.07, right: width * 0.07, top: height * 0.56, opacity: 1 - out }}>
      {items.map((it, i) => {
        if (f < it.at) return null;
        const s = pop(f - it.at, fps, 13, 230, 0.7);
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 22, marginTop: 18, transform: `translateX(${(1 - s) * -80}px)`, opacity: Math.min(1, s * 1.5),
            background: it.em ? `${brand.accent}` : "rgba(15,12,25,0.55)", backdropFilter: "blur(18px)", border: "1.5px solid rgba(255,255,255,0.2)",
            borderRadius: 30, padding: "14px 28px", boxShadow: "0 20px 40px rgba(0,0,0,0.35)" }}>
            <Img src={staticFile(`icons3d/${it.icon}_color.png`)} style={{ width: 120, height: 120, transform: `rotate(${Math.sin((f + i * 20) / 12) * 6}deg)` }} />
            <div style={{ fontFamily: sans, fontWeight: 800, fontSize: 60, letterSpacing: "-0.02em", color: it.em ? brand.ink : "#fff" }}>
              your own <span style={{ fontFamily: serif, fontStyle: "italic", fontWeight: 400, fontSize: 84, color: it.em ? brand.ink : brand.accent }}>{it.t}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export const SCENES: Record<string, React.FC<SceneProps>> = { ScamNotifs, MillionaireBS, Paywall, Checkout, Ranks, Notes, YearFlip, Footage };
