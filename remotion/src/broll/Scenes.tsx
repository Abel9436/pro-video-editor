import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, random, spring, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import * as THREE from "three";
import { anton, poppins } from "../fonts";
import { ease, Label, PURPLE, RED, SceneFrame, shake, YELLOW } from "./Scene";
import { Gold, Lights } from "./Lights";

const Canvas3D: React.FC<{ children: React.ReactNode; z?: number; fov?: number; y?: number }> = ({ children, z = 8, fov = 38, y = 0 }) => {
  const { width, height } = useVideoConfig();
  return (
    <ThreeCanvas width={width} height={height} camera={{ position: [0, y, z], fov }} gl={{ alpha: true, antialias: true }}
      style={{ position: "absolute", inset: 0 }}>
      {children}
    </ThreeCanvas>
  );
};

const textTexture = (text: string, color: string, bg: string | null, w = 1024, h = 1024, font = "bold 520px Arial") => {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const g = c.getContext("2d")!;
  if (bg) { g.fillStyle = bg; g.fillRect(0, 0, w, h); }
  g.shadowColor = color; g.shadowBlur = 60;
  g.fillStyle = color; g.font = font; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(text, w / 2, h / 2 + 20);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
};

// 1. "secret AI technology that guarantees..." -------------------------------------------
const Chip: React.FC<{ frame: number }> = ({ frame }) => {
  const tex = useMemo(() => textTexture("AI", "#7CF7FF", "#0b0b14"), []);
  const pulse = 0.6 + 0.4 * Math.sin(frame / 3);
  const pins = [];
  for (let s = 0; s < 4; s++) for (let i = 0; i < 7; i++) {
    const o = -1.05 + i * 0.35;
    const pos: [number, number, number] = s === 0 ? [o, 1.45, 0] : s === 1 ? [o, -1.45, 0] : s === 2 ? [1.45, o, 0] : [-1.45, o, 0];
    const size: [number, number, number] = s < 2 ? [0.14, 0.32, 0.08] : [0.32, 0.14, 0.08];
    pins.push(<mesh key={`${s}${i}`} position={pos}><boxGeometry args={size} /><Gold /></mesh>);
  }
  return (
    <group rotation={[0.35 + Math.sin(frame / 20) * 0.05, -0.6 + frame * 0.012, 0.08]} position={[0, 0.9 + Math.sin(frame / 10) * 0.08, 0]}>
      <mesh>
        <boxGeometry args={[2.6, 2.6, 0.35]} />
        <meshStandardMaterial attach="material-0" color="#16161f" metalness={0.6} roughness={0.35} />
        <meshStandardMaterial attach="material-1" color="#16161f" metalness={0.6} roughness={0.35} />
        <meshStandardMaterial attach="material-2" color="#16161f" metalness={0.6} roughness={0.35} />
        <meshStandardMaterial attach="material-3" color="#16161f" metalness={0.6} roughness={0.35} />
        <meshStandardMaterial attach="material-4" map={tex} emissiveMap={tex} emissive="#ffffff" emissiveIntensity={pulse} />
        <meshStandardMaterial attach="material-5" color="#16161f" />
      </mesh>
      {pins}
    </group>
  );
};

const AdCard: React.FC<{ frame: number; at: number; x: number; y: number; rot: number; title: string; tag: string }> = ({ frame, at, x, y, rot, title, tag }) => {
  const { fps, height } = useVideoConfig();
  const s = spring({ frame: frame - at, fps, config: { damping: 10, stiffness: 260, mass: 0.5 } });
  if (frame < at) return null;
  const flicker = random(`f${frame}${title}`) > 0.93 ? 0.5 : 1;
  return (
    <div style={{ position: "absolute", left: `${x * 100}%`, top: y * height, transform: `translate(-50%,-50%) rotate(${rot}deg) scale(${s})`, opacity: flicker,
      background: "linear-gradient(180deg,#fff,#f1f1f1)", borderRadius: 22, padding: "22px 30px", width: 560, boxShadow: "0 30px 60px rgba(0,0,0,0.55)", border: `5px solid ${RED}` }}>
      <div style={{ fontFamily: poppins, fontWeight: 800, color: RED, fontSize: 26, letterSpacing: 2 }}>{tag}</div>
      <div style={{ fontFamily: anton, fontSize: 64, lineHeight: 1.0, color: "#111", textTransform: "uppercase", marginTop: 6 }}>{title}</div>
      <div style={{ marginTop: 14, display: "inline-block", background: "#19c35b", color: "#fff", fontFamily: poppins, fontWeight: 800, fontSize: 30, padding: "8px 26px", borderRadius: 40 }}>BUY NOW →</div>
    </div>
  );
};

export const AIScam: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <SceneFrame hue="#00C2FF">
      <Canvas3D z={12.5}><Lights rim="#00C2FF" /><Chip frame={frame} /></Canvas3D>
      <AdCard frame={frame} at={14} x={0.32} y={0.18} rot={-7} title="Secret AI system" tag="⚡ LIMITED OFFER" />
      <AdCard frame={frame} at={30} x={0.68} y={0.6} rot={6} title="Guaranteed $10K / day" tag="100% GUARANTEED" />
      <AdCard frame={frame} at={46} x={0.36} y={0.8} rot={-4} title="Become a millionaire" tag="NO EXPERIENCE NEEDED" />
    </SceneFrame>
  );
};

// 2. "become a millionaire and all this BS" -----------------------------------------------
const Coins: React.FC<{ frame: number; stop: number }> = ({ frame, stop }) => {
  const coins = useMemo(() => new Array(34).fill(0).map((_, i) => ({
    x: (random(`cx${i}`) - 0.5) * 7, z: (random(`cz${i}`) - 0.5) * 3, start: random(`cs${i}`) * 22, speed: 0.32 + random(`cv${i}`) * 0.2,
    rx: random(`r${i}`) * 6, spin: 0.2 + random(`sp${i}`) * 0.3 })), []);
  const t = Math.min(frame, stop + (frame - stop) * 0.15);
  return (
    <group>
      {coins.map((c, i) => {
        const k = t - c.start;
        if (k < 0) return null;
        const y = 6 - k * c.speed * (1 + k * 0.06);
        return (
          <mesh key={i} position={[c.x, Math.max(-6, y), c.z]} rotation={[c.rx + k * c.spin, k * c.spin * 0.7, 0]}>
            <cylinderGeometry args={[0.42, 0.42, 0.08, 40]} /><Gold />
          </mesh>
        );
      })}
    </group>
  );
};

export const Millionaire: React.FC<{ bsAt?: number }> = ({ bsAt = 25 }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const v = interpolate(frame, [0, bsAt - 3], [0, 1000000], { extrapolateRight: "clamp", easing: Easing.in(Easing.quad) });
  const stamp = spring({ frame: frame - bsAt, fps, config: { damping: 9, stiffness: 300, mass: 0.6 } });
  const grey = frame >= bsAt ? 0.85 : 0;
  return (
    <SceneFrame hue="#FFB800">
      <AbsoluteFill style={{ transform: shake(frame, bsAt, 26, 7), filter: `grayscale(${grey}) brightness(${frame >= bsAt ? 0.6 : 1})` }}>
        <Canvas3D z={12}><Lights rim="#FFB800" /><Coins frame={frame} stop={bsAt} /></Canvas3D>
        <div style={{ position: "absolute", top: 0.36 * height, width: "100%", textAlign: "center", fontFamily: anton, fontSize: 0.105 * height, color: YELLOW,
          textShadow: "0 10px 0 #7a5200, 0 0 60px rgba(255,200,0,0.5)" }}>
          ${Math.round(v).toLocaleString("en-US")}
        </div>
      </AbsoluteFill>
      {frame >= bsAt ? (
        <div style={{ position: "absolute", top: 0.36 * height, width: "100%", display: "flex", justifyContent: "center" }}>
          <div style={{ transform: `translateY(-30%) rotate(-12deg) scale(${interpolate(stamp, [0, 1], [2.6, 1])})`, opacity: Math.min(1, stamp * 2),
            border: `14px solid ${RED}`, borderRadius: 28, padding: "0 50px", fontFamily: anton, fontSize: 0.24 * height, color: RED,
            background: "rgba(20,0,0,0.35)", textShadow: "0 0 30px rgba(255,0,0,0.6)" }}>BS</div>
        </div>
      ) : null}
    </SceneFrame>
  );
};

// 4. "this knowledge is behind a wall" ------------------------------------------------------
const Wall: React.FC<{ frame: number; lockAt: number }> = ({ frame, lockAt }) => {
  const { fps } = useVideoConfig();
  const rows = 9, cols = 6, bw = 1.0, bh = 0.46;
  const bricks = [];
  for (let r = 0; r < rows; r++) {
    for (let c = -1; c < cols; c++) {
      const x = (c - cols / 2 + 0.5 + (r % 2 ? 0.5 : 0)) * bw;
      if (Math.abs(x) > cols * bw / 2) continue;
      const at = r * 3 + random(`b${r}${c}`) * 3;
      const s = spring({ frame: frame - at, fps, config: { damping: 14, stiffness: 200 } });
      if (frame < at) continue;
      const y = -2.1 + r * bh + (1 - s) * 5;
      const tint = 0.8 + random(`t${r}${c}`) * 0.25;
      bricks.push(
        <mesh key={`${r}_${c}`} position={[x, y, 0]} rotation={[0, 0, (1 - s) * (random(`rr${r}${c}`) - 0.5)]}>
          <boxGeometry args={[bw * 0.95, bh * 0.9, 0.5]} />
          <meshStandardMaterial color={new THREE.Color(0.62 * tint, 0.27 * tint, 0.18 * tint)} roughness={0.85} />
        </mesh>);
    }
  }
  const ls = spring({ frame: frame - lockAt, fps, config: { damping: 8, stiffness: 220 } });
  return (
    <group rotation={[0.08, -0.25, 0]}>
      {bricks}
      {frame >= lockAt ? (
        <group position={[0, 0.0 + (1 - ls) * 4, 0.55]} scale={1.15}>
          <mesh position={[0, 0.55, 0]}><torusGeometry args={[0.42, 0.11, 20, 40, Math.PI]} /><meshStandardMaterial color="#cfd3da" metalness={0.8} roughness={0.25} /></mesh>
          <mesh position={[-0.42, 0.35, 0]}><cylinderGeometry args={[0.11, 0.11, 0.4, 20]} /><meshStandardMaterial color="#cfd3da" metalness={0.8} roughness={0.25} /></mesh>
          <mesh position={[0.42, 0.35, 0]}><cylinderGeometry args={[0.11, 0.11, 0.4, 20]} /><meshStandardMaterial color="#cfd3da" metalness={0.8} roughness={0.25} /></mesh>
          <mesh position={[0, -0.15, 0]}><boxGeometry args={[1.25, 1.0, 0.45]} /><Gold /></mesh>
          <mesh position={[0, -0.12, 0.24]}><cylinderGeometry args={[0.1, 0.1, 0.05, 20]} /><meshStandardMaterial color="#222" /></mesh>
        </group>
      ) : null}
    </group>
  );
};

export const BrickWall: React.FC<{ lockAt?: number }> = ({ lockAt = 30 }) => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();
  const behind = ease(frame, 0, 8);
  return (
    <SceneFrame hue={PURPLE}>
      <div style={{ position: "absolute", top: 0.43 * height, width: "100%", textAlign: "center", fontFamily: anton, fontSize: 0.075 * height, lineHeight: 1,
        color: "#7CF7FF", opacity: behind, textShadow: "0 0 40px #00c2ff" }}>INSIDER<br />KNOWLEDGE</div>
      <AbsoluteFill style={{ transform: shake(frame, lockAt + 3, 12, 5) }}>
        <Canvas3D z={14} y={0.2}><Lights /><Wall frame={frame} lockAt={lockAt} /></Canvas3D>
      </AbsoluteFill>
      <Label text="behind a wall" y={0.13} delay={4} />
    </SceneFrame>
  );
};

// 5. "pay to play" ----------------------------------------------------------------------------
export const PayToPlay: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const gateS = spring({ frame, fps, config: { damping: 14, stiffness: 160 } });
  return (
    <SceneFrame hue="#19C35B">
      <Canvas3D z={14}>
        <Lights rim="#19C35B" />
        <group rotation={[0.25, -0.35, 0]} position={[0, -0.6, 0]} scale={gateS}>
          <mesh><boxGeometry args={[3.2, 2.2, 1.4]} /><meshStandardMaterial color="#1d1f2a" metalness={0.5} roughness={0.4} /></mesh>
          <mesh position={[0, 1.12, 0]}><boxGeometry args={[1.6, 0.06, 0.3]} /><meshStandardMaterial color="#000" /></mesh>
          <mesh position={[0, 0.2, 0.71]}><boxGeometry args={[2.6, 0.9, 0.02]} /><meshStandardMaterial color="#0b2a17" emissive="#19C35B" emissiveIntensity={0.25} /></mesh>
          {new Array(6).fill(0).map((_, i) => {
            const k = frame - 4 - i * 4;
            if (k < 0 || k > 10) return null;
            const y = 4.2 - k * 0.32;
            return <mesh key={i} position={[(i % 2 ? 0.25 : -0.25) * (1 - k / 10), y, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.45, 0.45, 0.09, 40]} /><Gold /></mesh>;
          })}
        </group>
      </Canvas3D>
      <Label text="pay to play" y={0.16} delay={2} />
      <Label text="ACCESS: $9,999" y={0.535} delay={10} size={0.035} color="#7CFFA8" />
    </SceneFrame>
  );
};

// 6. "join a company and work through the ranks" ----------------------------------------------
export const Ranks: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const steps = 6, hop = 6;
  const k = Math.min(steps - 1, Math.floor(frame / hop));
  const p = Math.min(1, (frame % hop) / hop);
  const sx = (i: number) => -2.5 + i * 1.0, sy = (i: number) => -2.4 + i * 0.75;
  const fx = k < steps - 1 ? sx(k) + (sx(k + 1) - sx(k)) * p : sx(k);
  const fy = (k < steps - 1 ? sy(k) + (sy(k + 1) - sy(k)) * p + Math.sin(p * Math.PI) * 0.6 : sy(k)) + 0.75;
  const year = Math.min(10, 1 + Math.floor(frame / 4.5));
  return (
    <SceneFrame>
      <Canvas3D z={15.5} y={0.4}>
        <Lights />
        <group rotation={[0.18, -0.45, 0]} position={[0.3, -0.6, 0]}>
          {new Array(steps).fill(0).map((_, i) => {
            const s = spring({ frame: frame - i * 2, fps, config: { damping: 15, stiffness: 200 } });
            return <mesh key={i} position={[sx(i), sy(i) - (1 - s) * 3, 0]}><boxGeometry args={[1.0, 0.75, 1.6]} />
              <meshStandardMaterial color={i === steps - 1 ? YELLOW : "#8a80c0"} roughness={0.5} metalness={0.2} emissive={i === steps - 1 ? "#5a4a00" : "#1a1440"} /></mesh>;
          })}
          <group position={[fx, fy, 0]}>
            <mesh position={[0, 0.0, 0]}><capsuleGeometry args={[0.22, 0.45, 8, 16]} /><meshStandardMaterial color="#ffffff" roughness={0.4} /></mesh>
            <mesh position={[0, 0.55, 0]}><sphereGeometry args={[0.2, 24, 24]} /><meshStandardMaterial color="#ffffff" roughness={0.4} /></mesh>
          </group>
        </group>
      </Canvas3D>
      <Label text="work through the ranks" y={0.14} delay={2} size={0.07} />
      <div style={{ position: "absolute", top: 0.29 * height, width: "100%", textAlign: "center", fontFamily: poppins, fontWeight: 800, fontSize: 0.04 * height, color: "#fff" }}>
        YEAR <span style={{ color: YELLOW }}>{year}</span>
      </div>
    </SceneFrame>
  );
};

// 7. "being an apprentice, soaking in as much information..." ---------------------------------
const Person: React.FC<{ x: number; color: string; scale: number; glow?: number }> = ({ x, color, scale, glow = 0 }) => (
  <group position={[x, -1.2, 0]} scale={scale}>
    <mesh position={[0, 0, 0]}><capsuleGeometry args={[0.55, 1.2, 8, 24]} /><meshStandardMaterial color={color} roughness={0.45} emissive={color} emissiveIntensity={glow} /></mesh>
    <mesh position={[0, 1.35, 0]}><sphereGeometry args={[0.48, 32, 32]} /><meshStandardMaterial color={color} roughness={0.45} emissive={color} emissiveIntensity={glow} /></mesh>
  </group>
);

export const Apprentice: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const glow = interpolate(frame, [10, durationInFrames], [0, 0.55], { extrapolateLeft: "clamp" });
  const parts = new Array(40).fill(0).map((_, i) => {
    const t = ((frame + i * 3.1) % 30) / 30;
    if (frame < 6 + i * 0.4) return null;
    const x = -1.45 + t * 2.9, y = 0.2 + Math.sin(t * Math.PI) * 1.4 + (random(`py${i}`) - 0.5) * 0.3;
    return <mesh key={i} position={[x, y, (random(`pz${i}`) - 0.5) * 0.6]}><sphereGeometry args={[0.07 + random(`ps${i}`) * 0.06, 12, 12]} />
      <meshStandardMaterial color={YELLOW} emissive={YELLOW} emissiveIntensity={2} /></mesh>;
  });
  return (
    <SceneFrame>
      <Canvas3D z={13}>
        <Lights />
        <group rotation={[0.1, 0, 0]} position={[0, -0.5, 0]}>
          <Person x={-1.45} color="#d9dbe6" scale={0.8} />
          <Person x={1.45} color={YELLOW} scale={0.62} glow={glow} />
          {parts}
        </group>
      </Canvas3D>
      <Label text="be an apprentice" y={0.14} delay={2} />
      <Label text="mentor → you" y={0.27} delay={10} size={0.04} color="#ffffff" />
    </SceneFrame>
  );
};

// 8. "a few years later" ---------------------------------------------------------------------
export const YearsLater: React.FC<{ from?: number }> = ({ from = 2026 }) => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();
  const per = 6;
  const idx = Math.floor(frame / per), p = (frame % per) / per;
  const card = (year: number, flip: number, z: number) => (
    <div key={`${year}-${z}`} style={{ position: "absolute", left: "50%", top: 0.45 * height, width: 560, height: 600, marginLeft: -280, marginTop: -300, zIndex: z,
      transformOrigin: "50% 0%", transform: `perspective(1600px) rotateX(${flip * 110}deg)`, opacity: 1 - flip * 0.8,
      background: "#fff", borderRadius: 30, boxShadow: "0 40px 80px rgba(0,0,0,0.6)", overflow: "hidden" }}>
      <div style={{ background: RED, height: 130, fontFamily: poppins, fontWeight: 800, color: "#fff", fontSize: 54, display: "flex", alignItems: "center", justifyContent: "center" }}>YEAR</div>
      <div style={{ fontFamily: anton, fontSize: 230, color: "#111", textAlign: "center", lineHeight: "450px" }}>{year}</div>
    </div>);
  return (
    <SceneFrame>
      {card(from + idx + 1, 0, 1)}
      {card(from + idx, Easing.in(Easing.cubic)(p), 2)}
      <Label text="a few years later" y={0.82} delay={2} size={0.07} />
    </SceneFrame>
  );
};

// ------------------------------------------------------------------ overlays on the speaker
export const XStamp: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 9, stiffness: 260 } });
  const a = ease(frame, 0, 4), b = ease(frame, 3, 7);
  const out = interpolate(frame, [durationInFrames - 4, durationInFrames], [1, 0], { extrapolateLeft: "clamp" });
  const L = 0.42 * width;
  return (
    <AbsoluteFill style={{ opacity: out, transform: shake(frame, 3, 14, 5) }}>
      <svg width={width} height={height} style={{ position: "absolute" }}>
        <g transform={`translate(${width / 2} ${0.5 * height}) scale(${0.7 + 0.3 * s})`} stroke={RED} strokeWidth={60} strokeLinecap="round"
          style={{ filter: "drop-shadow(0 12px 18px rgba(0,0,0,0.6))" }}>
          <line x1={-L / 2} y1={-L / 2} x2={-L / 2 + L * a} y2={-L / 2 + L * a} />
          <line x1={L / 2} y1={-L / 2} x2={L / 2 - L * b} y2={-L / 2 + L * b} />
        </g>
      </svg>
    </AbsoluteFill>
  );
};

export const WordSlam: React.FC<{ text: string; y?: number; dur: number }> = ({ text, y = 0.52, dur }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 10, stiffness: 320, mass: 0.6 } });
  const ring = ease(frame, 0, 8);
  const out = interpolate(frame, [dur - 3, dur], [1, 0], { extrapolateLeft: "clamp" });
  return (
    <AbsoluteFill style={{ opacity: out, transform: shake(frame, 1, 10, 4) }}>
      <div style={{ position: "absolute", left: "50%", top: y * height, width: 0.5 * height * ring, height: 0.5 * height * ring,
        marginLeft: -0.25 * height * ring, marginTop: -0.25 * height * ring, borderRadius: "50%", border: `${10 * (1 - ring) + 1}px solid rgba(255,212,0,${0.8 * (1 - ring)})` }} />
      <div style={{ position: "absolute", top: y * height, width: "100%", textAlign: "center", transform: `translateY(-50%) scale(${interpolate(s, [0, 1], [2.4, 1])})`,
        filter: `blur(${(1 - s) * 8}px)`, fontFamily: anton, fontSize: 0.11 * height, color: YELLOW, textTransform: "uppercase",
        textShadow: "0 10px 0 rgba(0,0,0,0.55), 0 0 50px rgba(0,0,0,0.6)" }}>{text}</div>
    </AbsoluteFill>
  );
};
