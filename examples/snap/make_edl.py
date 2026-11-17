"""Worked example: the accepted design for an Amharic gym-coach short (27 s, 2026-11-17).

Usage (after ingest, analyze and the Amharic transcript are done, and the paper edit drafted v1):
  python examples/snap/make_edl.py PROJECT_DIR      # writes PROJECT_DIR/edl/v4.json

Story (his order, nothing cut): 'if anyone says BSS is useless, it's one of two reasons' -> 01 they
don't like leg day -> 02 they can't do it properly (over his own demo) -> 'besides squats and leg
extensions, the most beneficial leg exercise is BSS' -> one-leg focus -> knee flexion + line of action
-> 'so please do them'.

How the design follows references/craft-motion-design.md:
- the demo folds into a 3D card over a studio set: the claim is struck, '2 reasons' lands, two cards
  flip in with 3D icons (Stage3D + camera card);
- he folds into a card at the top while a podium rises and BSS overtakes to #1 (Podium3D);
- extruded 3D titles behind him (Title3D), 3D flips where the picture source changes;
- the hero beat: his own rep slowed into the bottom, frozen, with the knee angle and line of action
  drawn on it (Telestrate, cutaway + freeze_f);
- pop captions in Menbere with Bela Bereka emphasis (fetch_fontet.py), brand dark green.

Every timing comes from the word timings (W[i] = timeline frame of word i), so the graphics land on
the words. The word indices and joint positions are specific to this footage: copy the structure,
not the numbers.

Assets this script expects in the project, all fetched with their licences:
  fetch_fontet.py get --project P Menbere Zemach "Bela Bereka"
  fetch_fonts.py (Anton, JetBrains Mono)       fetch_3dicons.py get --project P gym target thumb-down trophy
  fetch_sfx.py --project P --plan plan.json  with {"whoosh": "fast whoosh", "marker": "marker pen", "tick": "ui tick",
      "impact": "impact hit", "shutter": "camera shutter", "thud": "thud"}
  music: any licensed 90-100 bpm bed saved as music/bed.mp3 (fetch_music.py get --project P --query workout --pick 0)
The SFX lines name the sounds used on the delivered video; when a fresh fetch returned other sounds,
each line takes a sound of the same role from P/sfx/catalog.json instead.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
P = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "project"
FPS = 30
e = json.loads((P / "edl/v1.json").read_text(encoding="utf-8"))
T = e["tracks"]
words = json.loads((P / "analysis.json").read_text(encoding="utf-8"))["files"]["snap"]["transcript"]["words"]

# ---- merge the 7-frame 'ሶ' event into the last one (a 0.23 s event reads as a flash frame) ----------
for k in ("video", "dialogue"):
    a, b = T[k][-2], T[k][-1]
    a["out_f"] = b["out_f"]
    T[k].pop()
D = T["dialogue"]


def tl(src_f):
    for d in D:
        if d["in_f"] <= src_f < d["out_f"]:
            return d["at_f"] + (src_f - d["in_f"])
    best = min(D, key=lambda d: min(abs(d["in_f"] - src_f), abs(d["out_f"] - src_f)))
    return best["at_f"] + max(0, min(src_f, best["out_f"] - 1) - best["in_f"])


W = {w["i"]: tl(w["s_f"]) for w in words}
END = max(d["at_f"] + d["out_f"] - d["in_f"] for d in D)
r = lambda s, f: f - s  # noqa: E731
RED, INK, WHITE = "#FF4438", "#0B0B0D", "#FFFFFF"

# ---- picture: the 'why' section cuts to his own rep, slows into the bottom and freezes -------------
V = T["video"]
ids = [v["id"] for v in V]
i8 = ids.index("v8")
F0 = V[i8]["at_f"]                         # 'in the meantime' - the cut to the demo
F1 = V[i8 + 2]["at_f"] if i8 + 2 < len(V) else END    # the call to action comes back to him
DESC0, BOTTOM, SP = 136, 166, 0.5          # source frames: the descent of one rep, its deepest frame (viewed)
slow = round((BOTTOM - DESC0 + 1) / SP)
Z, CXF, CYF = 1.3, 0.47, 0.6               # static reframe of the frozen rep (fixed crop, centre in source fractions)
freeze = {"id": "v8f", "src": "snap", "in_f": DESC0, "out_f": BOTTOM + 1, "at_f": F0, "speed": SP,
          "freeze_f": (F1 - F0) - slow, "role": "body", "transition_in": "cut",
          "reframe": {"mode": "fixed", "x": CXF, "y": CYF, "zoom": Z}, "cutaway": True,
          "reason": "show what he describes: his own rep slowed into the bottom and frozen while knee flexion and the line of action are drawn on it"}
V[i8:i8 + 2] = [freeze]
V[-1]["reframe"] = {"mode": "face_track", "zoom": 1.0}
for v in V:
    v["transform"] = []
FREEZE_AT = F0 + slow


def scr(x, y):
    """Source-frame fraction -> screen fraction inside the fixed Z crop (render.crop_window, same aspect)."""
    w = 1 / Z
    x0 = min(max(0.0, CXF - w / 2), 1 - w)
    y0 = min(max(0.0, CYF - w / 2), 1 - w)
    return round((x - x0) * Z, 3), round((y - y0) * Z, 3)


KNEE, BAR, FOOT = scr(0.41, 0.77), scr(0.5, 0.54), scr(0.445, 0.885)
print("END", END, "freeze", F0, FREEZE_AT, F1, "knee", KNEE, "bar", BAR, "foot", FOOT,
      {k: W[k] for k in (3, 8, 13, 18, 27, 31, 36, 37, 41, 45, 52, 59, 64, 68, 72)})

# ---- graphics (v4): explainer stages in 3D, extruded titles, 3D icons, 3D flip transitions ---------
# brand: dark green (user, 2026-11-17), taken from the emerald plates in his gym; near-black green ink
RED = "#0E7A43"                              # accent (name kept for the code below)
INK = "#06120B"
INTRO_END = 51                              # the creator's own cut from the intro to the demo
ANTON = "'Anton', 'Montserrat', sans-serif"
W60 = W[60]                                  # 'ፍሌክሽንም'
JOINTS = {"bar": [0.537, 0.408], "hip": [0.6, 0.6], "knee": [0.36, 0.665], "ankle": [0.5, 0.85], "rknee": [0.86, 0.68],
          "lo": [0.535, 0.72]}                # measured on the rendered freeze frame (screen fractions)
FR = FREEZE_AT - F0
R0, R1 = INTRO_END, W[27]                    # reasons stage: the demo folds into a card
P0, P1 = W[36] - 4, W[45] - 1                # podium stage: he folds into a card at the top
STRIKE = W[8]
overlays = [
    {"s": 0, "e": INTRO_END, "type": "Title3D", "behind": True, "p": {"items": [
        {"t": "ቡልጋሪያን", "at": 1, "y": 0.11, "size": 150, "color": WHITE, "depth": 16},
        {"t": "ስፕሊት ስኳት", "at": max(3, W[1] - 1), "y": 0.195, "size": 160, "color": RED, "depth": 20}]}},
    {"s": P1, "e": F0, "type": "Title3D", "behind": True, "p": {"items": [
        {"t": "1", "at": max(1, r(P1, W[46]) - 1), "x": 0.76, "y": 0.27, "size": 620, "color": RED, "depth": 34, "font": ANTON, "enter": "spin", "drift": 14}]}},
    {"s": F0, "e": F1, "type": "Telestrate", "p": {
        "joints": JOINTS,
        "spotlight": {"x": 0.55, "y": 0.62, "rx": 0.62, "ry": 0.4, "at": 2, "dim": 0.62},
        "kicker": {"t": "ቴክኒክ  //  BSS", "at": 6},
        "dots": [["bar", FR + 2], ["hip", FR + 5], ["knee", FR + 8], ["ankle", FR + 11], ["rknee", FR + 14]],
        "bones": [["bar", "hip", FR + 4], ["hip", "knee", FR + 7], ["knee", "ankle", FR + 10], ["hip", "rknee", FR + 13]],
        "angle": {"j": "knee", "a": "hip", "b": "ankle", "r": 90, "at": max(FR + 18, r(F0, W60))},
        "force": {"x0": 0.537, "y0": 0.36, "x1": 0.53, "y1": 0.865, "at": r(F0, W[64]) - 2},
        "tags": [{"t": "ኒ ፍሌክሽን", "x": 0.44, "y": 0.52, "anchor": "knee", "side": "l", "at": max(FR + 20, r(F0, W60) + 4)},
                 {"t": "ላይን ኦፍ አክሽን", "x": 0.6, "y": 0.775, "anchor": "lo", "side": "r", "at": r(F0, W[64]) + 8}]}},
    {"s": W[72] - 1, "e": END, "type": "Title3D", "behind": True, "p": {"items": [
        {"t": "ስሩ", "at": 1, "y": 0.15, "size": 330, "color": RED, "depth": 28, "enter": "spin", "drift": 10}]}},
]
scenes = [
    {"s": R0, "e": R1, "type": "Stage3D", "p": {"under": True,
        "kicker": {"t": "ቡልጋሪያን ስፕሊት ስኳት"},
        "claim": {"t": "አይጠቅምም?", "icon": "thumb-down", "at": 0, "strikeAt": r(R0, STRIKE), "out": r(R0, STRIKE) + 12, "y": 0.16},
        "head": {"n": "2", "t": "ምክንያቶች", "at": r(R0, STRIKE) + 14, "out": r(R0, W[13]) - 8, "y": 0.13},
        "cards": [{"n": "01", "t": "ሌግ መስራት አይወድም", "icon": "gym", "at": r(R0, W[13]) - 2, "y": 0.09},
                  {"n": "02", "t": "በትክክል መስራት አይችልም", "icon": "target", "at": r(R0, W[18]) - 2, "y": 0.235}]}},
    {"s": P0, "e": P1, "type": "Podium3D", "p": {"under": True, "base": 0.95, "hero": 2,
        "pillars": [{"t": "ስኳት", "rank": 2, "slot": 0, "h": 270, "at": r(P0, W[36])},
                    {"t": "ሌግ ኤክስቴንሽን", "rank": 3, "slot": 2, "h": 200, "at": r(P0, W[37])},
                    {"t": "ቡልጋሪያን ስፕሊት ስኳት", "rank": 1, "slot": 1, "h": 380, "at": r(P0, W[41]) - 2}],
        "trophy": {"icon": "trophy", "at": r(P0, W[41]) + 8}}},
]
TROPHY_LAND = W[41] + 8 + 8                  # bounce.out first contact ~0.36 of 0.7 s

camera = [
    {"s": R0, "e": R1, "card": {"scale": 0.5, "x": 0.0, "y": 0.2, "ry": -12, "ry1": -4, "rx": 5, "radius": 46, "inn": 0.5, "out": 0.45}},
    {"s": P0, "e": P1, "card": {"scale": 0.44, "x": 0.0, "y": -0.22, "ry": 10, "ry1": 4, "rx": -4, "radius": 42, "inn": 0.5, "out": 0.45}},
    {"s": W[72] - 1, "e": END, "z0": 1.16, "z1": 1.18, "ease": "power2.out"},
]

e["design"] = {
    "brand": {"accent": RED, "glow": RED, "ink": INK},
    "face_y": 0.2, "matte": True, "engine": "hyperframes",
    "caption_style": "pop", "caption_size": 84, "caption_y": 0.74, "max_words": 3,
    "caption_font": "'Menbere', 'Noto Sans Ethiopic', sans-serif",
    "caption_font_emph": "'Bela Bereka', 'Menbere', 'Noto Sans Ethiopic', sans-serif",
    "caption_y_at": [{"s": R0, "e": R1, "y": 0.885}, {"s": P0, "e": P1, "y": 0.385}, {"s": F0, "e": F1, "y": 0.13}],
    "caption_hide": [[0, W[3] - 1]],
    "emphasis": ["አይጠቅምም", "በትክክል", "ቤኔፊሻል", "አንድ", "ስሩ"],
    "layout": [{"s": 0, "e": END, "mode": "full"}], "scenes": scenes, "overlays": overlays, "camera": camera,
    "finish": {"grain": 0.06, "vignette": 0.55},
    "fx": [{"at": INTRO_END, "type": "flip3d", "dir": "left"}, {"at": F0, "type": "flip3d", "dir": "right"}, {"at": FREEZE_AT, "type": "flash"}],
}
GRADE = json.loads((HERE / "grade.json").read_text())
e["color"] = {"correction": "auto", "match_shots": True, "look": GRADE, "strength": 0.9, "halation": 0.22}
T["captions"] = None
T["graphics"], T["broll"] = [], []

# ---- music: a 92 bpm percussive bed, from its loudest section ----------------------------------
try:  # start on the delivered bed's loudest section, if this bed is long enough for it
    BED_S = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(P / "music/bed.mp3")], capture_output=True, text=True).stdout.strip())
except (OSError, ValueError):
    BED_S = 0.0
T["music"] = [{"asset": "file:music/bed.mp3", "at_f": 0, "in_f": round(19.7 * FPS) if BED_S >= 19.7 + END / FPS else 0, "dur_f": END, "gain_db": -17, "end": "hit",
               "duck": {"under": "dialogue", "depth_db": -20, "attack_ms": 60, "release_ms": 300},
               "reason": "a 92 bpm percussive bed for a gym coach, started on its loudest section"}]

cat = {s["file"]: s for s in json.loads((P / "sfx/catalog.json").read_text(encoding="utf-8"))["sounds"]}
pk = lambda f: round((cat.get(f, {}).get("peak_s") or 0) * FPS)  # noqa: E731
sfx = []
_used: dict[str, int] = {}


def snd(f: str) -> str:
    """The named sound if the project has it, else the next unused sound of the same role (the name's prefix)."""
    if (P / "sfx" / f).exists():
        return f"sfx/{f}"
    role = f.split("_")[0]
    alts = sorted(k for k in cat if Path(k).name.startswith(role + "_"))
    if not alts:
        raise SystemExit(f"no '{role}' sound in sfx/catalog.json: run fetch_sfx.py --project P --role {role} --query ...")
    n = _used.get(role, 0)
    _used[role] = n + 1
    return alts[n % len(alts)]


def S(f, at, db, role, why, dur=None):
    f = snd(f)
    x = {"asset": f"file:{f}", "at_f": max(0, at - pk(f)), "gain_db": db, "role": role, "reason": why}
    if dur:
        x["dur_f"] = dur
    sfx.append(x)


S("whoosh_ves-fast-whoosh.mp3", INTRO_END - 4, -16, "transition_whoosh", "3D flip into the demo; the footage folds into a card", 18)
S("marker_211247.mp3", STRIKE, -16, "marker", "the claim is struck through", 12)
S("tick_320181.mp3", W[13] - 2, -17, "pop", "card 01 flips in")
S("tick_249300.mp3", W[18] - 2, -17, "pop", "card 02 flips in")
S("impact_ves-impact-hit-2.mp3", TROPHY_LAND, -15, "impact_hit", "the trophy lands on the BSS pillar")
S("whoosh_ves-fast-whoosh.mp3", F0 - 4, -17, "transition_whoosh", "3D flip to his rep", 18)
S("shutter_232130.mp3", FREEZE_AT, -15, "shutter", "the rep freezes at the bottom (flash)")
S("marker_257518.mp3", W[64] - 2, -16, "marker", "the line of action draws down", 14)
S("thud_191292.mp3", W[72] - 1, -15, "impact_hit", "punch-in on 'do them'")
T["sfx"] = sorted(sfx, key=lambda s: s["at_f"])

e["notes"] = [n for n in e.get("notes", [])] + [
    "v4 2026-11-17: explainer stages - demo folds into a 3D card over a studio set (claim struck, 2 reasons, 01/02 cards with 3D icons), 3D podium with a trophy, extruded 3D titles, 3D flip transitions; Menbere captions, Bela Bereka emphasis (font.et, OFL); brand dark green #0E7A43 at the user's request. restraint_fx accepted: two flips mark the two changes of picture source, the flash marks the freeze.",
    "v3 2026-11-17: broadcast motion design - ReasonPanel (claim struck through, odometer 01->02), Standings (BSS overtakes to #1), telestrator on the frozen rep (joints, skeleton, knee arc, line of action), kinetic '1' and 'ስሩ'. restraint_fx warning accepted: the whip covers the creator's own cut into the demo and the flash marks the freeze.",
    "v2 2026-11-17: restraint edit - one hero beat (slow-motion into a frozen rep with knee flexion and the line of action drawn on), "
    "pop captions with five emphasis words, red/near-black from the location, deep grade + vignette + grain, Mixkit 369, 8 SFX (CC0)."]
(P / "edl/v4.json").write_text(json.dumps(e, indent=2, ensure_ascii=False), encoding="utf-8")

# licences: every fetch_*.py script writes its own entry to P/licenses.json; add one for the music you choose.
print(f"v4: {END} f ({END / FPS:.1f} s), {len(overlays)} overlays, {len(sfx)} sfx")
