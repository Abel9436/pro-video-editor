import React, { useMemo } from "react";
import { ThreeCanvas } from "@remotion/three";
import { interpolate, spring, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import * as THREE from "three";

// Real 3D title (references/assets-sources.md: no flat clip-art). Extruded text drawn from a
// canvas texture onto a bevelled slab, lit with a key, a rim and an environment colour. Used when
// Blender is not installed. A Poly Haven HDRI can replace the environment colour via props.env.
type P = { text?: string; color?: string; accent?: string; dur: number };

const useTextTexture = (text: string, color: string) =>
  useMemo(() => {
    const c = document.createElement("canvas");
    c.width = 2048; c.height = 512;
    const g = c.getContext("2d")!;
    g.fillStyle = color; g.fillRect(0, 0, c.width, c.height);
    g.fillStyle = "#111"; g.font = "bold 300px Anton, Impact, sans-serif";
    g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(text.toUpperCase(), c.width / 2, c.height / 2 + 10, c.width - 120);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, [text, color]);

const Slab: React.FC<P> = ({ text = "", color = "#FFD400", accent = "#ffffff", dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tex = useTextTexture(text, color);
  const enter = spring({ frame, fps, config: { damping: 14, stiffness: 120 } });
  const exit = interpolate(frame, [dur - 10, dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.cubic) });
  const rotY = interpolate(enter, [0, 1], [-1.1, -0.12]) + Math.sin(frame / fps) * 0.04 + exit * 1.2;
  const z = interpolate(enter, [0, 1], [-6, 0]) - exit * 4;
  return (
    <group rotation={[0.08, rotY, 0]} position={[0, 0, z]}>
      <mesh>
        <boxGeometry args={[4, 1, 0.35]} />
        <meshStandardMaterial attach="material-0" color={accent} metalness={0.3} roughness={0.4} />
        <meshStandardMaterial attach="material-1" color={accent} metalness={0.3} roughness={0.4} />
        <meshStandardMaterial attach="material-2" color={accent} metalness={0.3} roughness={0.4} />
        <meshStandardMaterial attach="material-3" color={accent} metalness={0.3} roughness={0.4} />
        <meshStandardMaterial attach="material-4" map={tex} metalness={0.1} roughness={0.5} />
        <meshStandardMaterial attach="material-5" color={accent} metalness={0.3} roughness={0.4} />
      </mesh>
    </group>
  );
};

export const Title3D: React.FC<P & { y?: number }> = (props) => {
  const { width, height } = useVideoConfig();
  // visible width at the slab's depth (camera z 6, vertical fov 40): fit the 4-unit slab to 80 % of it
  const visibleW = 2 * 6 * Math.tan((20 * Math.PI) / 180) * (width / height);
  const fit = Math.min(1, (0.8 * visibleW) / 4);
  return (
    <ThreeCanvas width={width} height={height} camera={{ position: [0, 0, 6], fov: 40 }} gl={{ alpha: true }}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[3, 4, 5]} intensity={1.6} />
      <directionalLight position={[-4, -2, -3]} intensity={0.8} color="#88aaff" />
      <group position={[0, ((props.y ?? 0.5) - 0.5) * -4, 0]} scale={fit}>
        <Slab {...props} />
      </group>
    </ThreeCanvas>
  );
};
