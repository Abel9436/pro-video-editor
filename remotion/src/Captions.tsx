import React from "react";
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { popScale, strokeShadow } from "./motion";
import { Brand, Card, CaptionTrack, ETHIOPIC, SAFE } from "./types";

// Caption cards timed to the spoken word (cards come from render.py caption_cards.json).
// pop_3word: 1-3 words, uppercase, keyword in the brand colour, pop-in with overshoot.
// bold_1word: one big word. clean_line: sentence case, full readable line, no animation beyond a fade.
const CardView: React.FC<{ card: Card; track: CaptionTrack; brand: Brand; baseY: number }> = ({ card, track, brand, baseY }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const template = track?.template ?? "pop_3word";
  const keys = new Set((track?.keywords ?? []).map((k) => k.toLowerCase()));
  const text = card.words.map((w) => w.w).join(" ");
  const eth = ETHIOPIC.test(text);
  const size = (template === "bold_1word" ? 0.075 : template === "clean_line" ? 0.04 : 0.058) * height;
  const scale = template === "clean_line" ? 1 : popScale(frame, fps);
  const y = (track?.fix?.[String(card.s_f)] ?? card.y ?? baseY) * height;
  return (
    <div style={{ position: "absolute", left: width * 0.08, right: width * 0.08, top: y, transform: `translateY(-50%) scale(${scale})`,
      textAlign: "center", fontFamily: eth ? brand.ethiopicFont : brand.captionFont, fontWeight: 800, fontSize: size,
      lineHeight: 1.1, color: brand.text, textShadow: strokeShadow(brand.stroke, Math.max(2, size * 0.06)) }}>
      {card.words.map((w, i) => {
        const clean = w.w.replace(/[^\p{L}\p{N}']/gu, "").toLowerCase();
        const key = track?.highlight === "keyword" && keys.has(clean);
        const shown = template === "clean_line" || eth ? w.w : w.w.toUpperCase();
        return <span key={i} style={{ color: key ? brand.primary : brand.text }}>{shown}{i < card.words.length - 1 ? " " : ""}</span>;
      })}
    </div>
  );
};

export const Captions: React.FC<{ cards: Card[]; track: CaptionTrack; brand: Brand; platform?: string }> = ({ cards, track, brand, platform }) => {
  const pos = track?.position;
  const baseY = pos === "center" ? 0.5 : pos === "bottom" ? 0.82 : pos === "top" ? 0.2 : SAFE[platform ?? track?.safe_zone ?? "shorts"] ?? 0.8;
  return (
    <AbsoluteFill>
      {cards.map((c, i) => (
        <Sequence key={i} from={c.s_f} durationInFrames={Math.max(1, c.e_f - c.s_f)} layout="none">
          <CardView card={c} track={track} brand={brand} baseY={baseY} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
