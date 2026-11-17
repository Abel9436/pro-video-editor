// Mirrors the JSON render.py writes to render/<mode>/remotion_props.json.
export type Word = { w: string; t_s: number; t_e: number; i?: number };
export type Card = { s_f: number; e_f: number; words: Word[]; y?: number };
export type Graphic = {
  component: "Title" | "Callout" | "LowerThird" | "ProgressBar" | "Title3D" | string;
  at_f: number;
  dur_f: number;
  props?: Record<string, unknown>;
};
export type CaptionTrack = {
  template?: "pop_3word" | "bold_1word" | "clean_line" | string;
  highlight?: "keyword" | "none" | "active_word";
  keywords?: string[];
  position?: string;
  safe_zone?: string;
  fix?: Record<string, number>;
} | null;
export type Brand = { primary: string; text: string; stroke: string; captionFont: string; headingFont: string; ethiopicFont: string };
export type OverlayProps = {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  cards: Card[];
  graphics: Graphic[];
  captions: CaptionTrack;
  brand?: Partial<Brand>;
};

export const DEFAULT_BRAND: Brand = {
  primary: "#FFD400",
  text: "#FFFFFF",
  stroke: "#000000",
  captionFont: "Poppins",
  headingFont: "Anton",
  ethiopicFont: "Noto Sans Ethiopic",
};

// Same caption baselines as scripts/lib/captions.py SAFE (fraction of frame height).
export const SAFE: Record<string, number> = {
  shorts: 0.7, youtube_shorts: 0.7, tiktok: 0.68, reels: 0.68, instagram_reels: 0.68,
  youtube: 0.88, instagram_feed: 0.85, linkedin: 0.85, podcast: 0.88,
};

export const ETHIOPIC = /[ሀ-፿ⶀ-⷟꬀-꬯]/;
