// The skill's default type system (two families + Ethiopic), loaded from Google Fonts (SIL OFL).
import { loadFont as loadPoppins } from "@remotion/google-fonts/Poppins";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { loadFont as loadEthiopic } from "@remotion/google-fonts/NotoSansEthiopic";

export const poppins = loadPoppins("normal", { weights: ["800"] }).fontFamily;
export const anton = loadAnton().fontFamily;
export const ethiopic = loadEthiopic("normal", { weights: ["700"] }).fontFamily;
