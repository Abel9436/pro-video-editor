import { Easing, interpolate, spring } from "remotion";

// Motion principles (references/craft-motion-type.md): ease in and out, overshoot and settle,
// staggered entrances, never linear movement.
export const popScale = (frame: number, fps: number) =>
  spring({ frame, fps, config: { damping: 12, stiffness: 220, mass: 0.6 }, from: 0.8, to: 1 });

export const fadeIn = (frame: number, dur = 4) =>
  interpolate(frame, [0, dur], [0, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });

export const fadeOut = (frame: number, total: number, dur = 4) =>
  interpolate(frame, [total - dur, total], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.cubic) });

export const slideIn = (frame: number, fps: number, distance: number, delay = 0) =>
  (1 - spring({ frame: frame - delay, fps, config: { damping: 16, stiffness: 160 } })) * distance;

export const strokeShadow = (stroke: string, px: number) =>
  [`${px}px ${px}px 0 ${stroke}`, `-${px}px ${px}px 0 ${stroke}`, `${px}px -${px}px 0 ${stroke}`, `-${px}px -${px}px 0 ${stroke}`,
   `0 ${px * 1.5}px ${px * 2}px rgba(0,0,0,0.45)`].join(", ");
