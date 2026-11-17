// Premium design system: one accent on a dark stage, three type roles.
// - sans (Inter Tight 800): captions and UI
// - serif italic (Instrument Serif): emphasis words, the "editorial" voice
// - hand (Caveat): kickers and annotations, the "human" voice
// - display (Anton): rare, for numbers and slams
import { loadFont as loadInterTight } from "@remotion/google-fonts/InterTight";
import { loadFont as loadInstrument } from "@remotion/google-fonts/InstrumentSerif";
import { loadFont as loadCaveat } from "@remotion/google-fonts/Caveat";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";

export const sans = loadInterTight("normal", { weights: ["500", "700", "800", "900"] }).fontFamily;
export const serif = loadInstrument("italic", { weights: ["400"] }).fontFamily;
export const hand = loadCaveat("normal", { weights: ["600", "700"] }).fontFamily;
export const display = loadAnton().fontFamily;
export const mono = loadMono("normal", { weights: ["500"] }).fontFamily;

export type Brand = { accent: string; ink: string; paper: string; alert: string; glow: string };
export const DEFAULT: Brand = { accent: "#D4FF3F", ink: "#0B0A12", paper: "#F4F1EA", alert: "#FF4D3D", glow: "#7A5CFF" };
