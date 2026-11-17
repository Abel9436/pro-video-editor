"""Speech features from a frame-timed word list.

Input words: [{"i": 0, "w": "Hello", "s_f": 12, "e_f": 20, "p": 0.97, "speaker": "S1"}, ...]
All outputs are in timeline frames. Thresholds marked STARTING DEFAULT are to be
replaced by values tuned in evals.
"""
from __future__ import annotations

import difflib
import re
from fractions import Fraction

import numpy as np

# Filler lexicons per language. Single tokens are "hard" fillers (safe to cut);
# phrases are "soft" (often fillers, sometimes meaningful - Claude decides).
FILLERS_HARD = {
    "en": {"um", "uh", "umm", "uhm", "erm", "er", "ah", "hmm", "mm", "mhm", "eh"},
    # Amharic hesitation sounds; unverified list, extend from real transcripts.
    "am": {"እ", "እእ", "ኧ", "ኧኧ", "ኤ"},
}
FILLERS_SOFT = {"en": ["you know", "i mean", "kind of", "sort of", "like,", "so,", "basically", "actually"]}

LAUGH_TOKENS = re.compile(r"\b(ha(ha)+|he(he)+|lol|laughs?|laughter|laughing)\b", re.I)

SILENCE_MIN_S = Fraction(1, 2)       # STARTING DEFAULT: gaps >= 0.5 s are candidate dead air
BREATH_MIN_S, BREATH_MAX_S = Fraction(15, 100), Fraction(8, 10)
RESTART_WINDOW_S = 3                 # a restart of the same phrase within 3 s = false start
RESTART_MAX_DIVERGE = 1              # abandoned attempt may hold 1 word the retry replaces ("go" -> "leave")
TERMINAL = re.compile(r"[.!?።፧]$")
CONJUNCTIONS = {"and", "or", "but", "nor", "then"}
# Doubled intensifiers are emphasis, not stutters: "never ever ever", "very very", "so so good".
INTENSIFIERS = {"ever", "very", "really", "so", "much", "more", "too", "way", "far", "long", "no", "never",
                "many", "big", "bigger", "again", "over", "on", "and", "go", "yeah", "yes", "please", "now", "hard"}
STOPWORDS = {"the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "at", "for", "is", "it", "that",
             "this", "you", "i", "we", "so", "be", "was", "are", "with", "as", "my", "your"}
RETAKE_WINDOW_S = 180                # look for repeated takes within 3 minutes of each other
RETAKE_MIN_WORDS = 4
RETAKE_SIMILARITY = 0.6              # STARTING DEFAULT token-sequence similarity for "same sentence"
EMPHASIS_Z = 1.5                     # STARTING DEFAULT: word louder/higher than speaker mean by 1.5 sd


def norm(w: str) -> str:
    return re.sub(r"[^\w']+", "", w.lower(), flags=re.UNICODE)


def find_fillers(words: list[dict], lang: str = "en") -> list[dict]:
    hard = FILLERS_HARD.get(lang, set())
    out = [{"i": w["i"], "s_f": w["s_f"], "e_f": w["e_f"], "text": w["w"], "kind": "hard"}
           for w in words if norm(w["w"]) in hard]
    toks = [w["w"].lower().strip() for w in words]
    for phrase in FILLERS_SOFT.get(lang, []):
        parts = phrase.split()
        n = len(parts)
        for k in range(len(words) - n + 1):
            window = toks[k:k + n]
            if all(window[j].rstrip(".!?") == parts[j] if parts[j].endswith(",") else norm(window[j]) == norm(parts[j])
                   for j in range(n)):
                out.append({"i": words[k]["i"], "s_f": words[k]["s_f"], "e_f": words[k + n - 1]["e_f"],
                            "text": " ".join(w["w"] for w in words[k:k + n]), "kind": "soft"})
    return sorted(out, key=lambda x: x["s_f"])


def find_false_starts(words: list[dict], fps: Fraction) -> list[dict]:
    out = []
    n = [norm(w["w"]) for w in words]
    for k in range(1, len(words)):
        # stutter repeat: "I I think", "we we" (not across a sentence end: "quality. Quality over")
        if n[k] and n[k] == n[k - 1] and words[k]["s_f"] - words[k - 1]["e_f"] < fps \
                and not TERMINAL.search(words[k - 1]["w"]) and n[k] not in INTENSIFIERS:
            out.append({"kind": "repeat", "s_f": words[k - 1]["s_f"], "e_f": words[k]["s_f"],
                        "i_from": words[k - 1]["i"], "i_to": words[k - 1]["i"], "text": words[k - 1]["w"]})
    for k, w in enumerate(words):
        # cut-off word: Whisper renders an abandoned word as "wh-" or "be--"
        if re.search(r"\w-{1,2}$", w["w"]):
            out.append({"kind": "cutoff", "s_f": w["s_f"], "e_f": w["e_f"], "i_from": w["i"], "i_to": w["i"],
                        "text": w["w"]})
    # Phrase restart: an opening of 2+ words is repeated within RESTART_WINDOW_S and the first
    # attempt was ABANDONED. Deliberate repetition ("I don't want X. I don't want Y.", "posting on
    # YouTube or posting on Instagram") is rhetoric and must never be flagged, so the attempt must:
    # contain no sentence end, not hand over with a conjunction, and diverge from the retry by at
    # most RESTART_MAX_DIVERGE words after their shared prefix.
    win = int(RESTART_WINDOW_S * fps)
    for a in range(len(words) - 3):
        if not (n[a] and n[a + 1]):
            continue
        if a > 0 and not TERMINAL.search(words[a - 1]["w"]) and not re.search(r",$", words[a - 1]["w"]) \
                and words[a]["s_f"] - words[a - 1]["e_f"] < fps // 5:
            continue  # attempts start at a phrase boundary, not mid-phrase
        for b in range(a + 2, min(len(words) - 1, a + 12)):
            if words[b]["s_f"] - words[a]["s_f"] > win:
                break
            if n[b] == n[a] and n[b + 1] == n[a + 1]:
                attempt = words[a:b]
                if any(TERMINAL.search(w["w"]) for w in attempt) or n[b - 1] in CONJUNCTIONS:
                    break
                prefix = 0
                while prefix < len(attempt) and b + prefix < len(words) and n[a + prefix] == n[b + prefix]:
                    prefix += 1
                if len(attempt) - prefix > RESTART_MAX_DIVERGE:
                    break
                out.append({"kind": "restart", "s_f": words[a]["s_f"], "e_f": words[b]["s_f"],
                            "i_from": words[a]["i"], "i_to": words[b - 1]["i"],
                            "text": " ".join(w["w"] for w in words[a:b])})
                break
    out.sort(key=lambda x: x["s_f"])
    # drop restarts fully covered by an earlier one
    dedup, last_end = [], -1
    for x in out:
        if x["kind"] == "restart" and x["e_f"] <= last_end:
            continue
        dedup.append(x)
        last_end = max(last_end, x["e_f"])
    return dedup


def sentences(words: list[dict]) -> list[dict]:
    """Split on terminal punctuation (Whisper punctuates) or long pauses."""
    out, cur = [], []
    for k, w in enumerate(words):
        cur.append(w)
        gap_next = words[k + 1]["s_f"] - w["e_f"] if k + 1 < len(words) else 10**9
        if re.search(r"[.!?።፧]$", w["w"]) or gap_next > 45:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [{"i_from": s[0]["i"], "i_to": s[-1]["i"], "s_f": s[0]["s_f"], "e_f": s[-1]["e_f"],
             "text": " ".join(w["w"] for w in s), "speaker": s[0].get("speaker"),
             "mean_p": round(float(np.mean([w["p"] for w in s])), 3),
             "complete": bool(re.search(r"[.!?።፧]$", s[-1]["w"]))} for s in out]


def find_retakes(sents: list[dict], fillers: list[dict], false_starts: list[dict], fps: Fraction) -> list[dict]:
    """Group sentences that say the same thing; recommend the best take with a reason."""
    toks = [[norm(t) for t in s["text"].split() if norm(t)] for s in sents]
    parent = list(range(len(sents)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    win = RETAKE_WINDOW_S * fps
    for a in range(len(sents)):
        if len(toks[a]) < RETAKE_MIN_WORDS:
            continue
        for b in range(a + 1, len(sents)):
            if sents[b]["s_f"] - sents[a]["e_f"] > win:
                break
            if len(toks[b]) < RETAKE_MIN_WORDS:
                continue
            if difflib.SequenceMatcher(None, toks[a], toks[b]).ratio() >= RETAKE_SIMILARITY:
                parent[find(b)] = find(a)
    groups: dict[int, list[int]] = {}
    for k in range(len(sents)):
        groups.setdefault(find(k), []).append(k)
    out = []
    for members in groups.values():
        if len(members) < 2:
            continue
        scored = []
        for order, k in enumerate(members):
            s = sents[k]
            nf = sum(1 for f in fillers if s["s_f"] <= f["s_f"] <= s["e_f"])
            nfs = sum(1 for f in false_starts if s["s_f"] <= f["s_f"] <= s["e_f"])
            # confidence minus disfluencies; complete sentences win; later takes win ties
            # (speakers repeat until they get it right)
            score = s["mean_p"] - 0.08 * nf - 0.1 * nfs + (0.1 if s["complete"] else 0) + 0.02 * order
            scored.append((round(score, 3), k, nf, nfs))
        best = max(scored)
        out.append({
            "takes": [{"sentence": k, "s_f": sents[k]["s_f"], "e_f": sents[k]["e_f"], "text": sents[k]["text"],
                       "score": sc, "fillers": nf, "false_starts": nfs} for sc, k, nf, nfs in scored],
            "recommended": best[1],
            "reason": (f"take {members.index(best[1]) + 1} of {len(members)}: highest score {best[0]} "
                       f"({best[2]} fillers, {best[3]} false starts"
                       f"{', complete sentence' if sents[best[1]]['complete'] else ''})"),
        })
    return out


def frame_rms_db(x: np.ndarray, sr: int, fps: Fraction) -> np.ndarray:
    """RMS level in dBFS per timeline frame."""
    spf = Fraction(sr) / fps
    n = int(Fraction(x.size) / spf)
    out = np.full(n, -120.0, dtype=np.float32)
    for f in range(n):
        a, b = int(f * spf), int((f + 1) * spf)
        seg = x[a:b]
        if seg.size:
            out[f] = 10 * np.log10(float(np.mean(seg.astype(np.float64) ** 2)) + 1e-12)
    return out


def find_gaps(words: list[dict], level_db: np.ndarray, noise_floor_db: float, fps: Fraction,
              total_f: int) -> tuple[list[dict], list[dict], list[dict]]:
    """Silences, breath candidates and non-speech vocal candidates in the gaps between words."""
    silences, breaths, nonspeech = [], [], []
    edges = [(0, words[0]["s_f"] if words else total_f)]
    edges += [(words[k]["e_f"], words[k + 1]["s_f"]) for k in range(len(words) - 1)]
    if words:
        edges.append((words[-1]["e_f"], total_f))
    speech_db = float(np.median([level_db[w["s_f"]:max(w["s_f"] + 1, w["e_f"])].mean()
                                 for w in words if w["s_f"] < level_db.size])) if words else -30.0
    quiet = noise_floor_db + 6
    for a, b in edges:
        if b - a <= 0 or a >= level_db.size:
            continue
        seg = level_db[a:min(b, level_db.size)]
        dur = Fraction(b - a) / fps
        loud = seg > quiet
        if dur >= SILENCE_MIN_S:
            silences.append({"s_f": a, "e_f": b, "dur_f": b - a,
                             "kind": "true_silence" if loud.mean() < 0.1 else "gap_with_sound",
                             "position": "lead" if a == 0 else ("tail" if b == total_f else "inner")})
        # contiguous above-floor runs inside the gap
        run_start = None
        for k, v in enumerate(list(loud) + [False]):
            if v and run_start is None:
                run_start = k
            elif not v and run_start is not None:
                rs, re_ = a + run_start, a + k
                rdur = Fraction(re_ - rs) / fps
                peak = float(seg[run_start:k].max())
                if BREATH_MIN_S <= rdur <= BREATH_MAX_S and peak < speech_db - 10:
                    breaths.append({"s_f": rs, "e_f": re_})
                elif rdur >= Fraction(4, 10) and peak >= speech_db - 6:
                    nonspeech.append({"s_f": rs, "e_f": re_, "note": "loud non-speech: laughter, reaction or noise"})
                run_start = None
    return silences, breaths, nonspeech


def find_laughter_tokens(words: list[dict]) -> list[dict]:
    return [{"s_f": w["s_f"], "e_f": w["e_f"], "text": w["w"], "source": "transcript"}
            for w in words if LAUGH_TOKENS.search(w["w"])]


def find_emphasis(words: list[dict], level_db: np.ndarray, pitch_hz: np.ndarray | None) -> list[dict]:
    """Words noticeably louder or higher than the same speaker's average. Ranked strongest first."""
    by_spk: dict = {}
    for w in words:
        if w["s_f"] >= level_db.size:
            continue
        seg = level_db[w["s_f"]:max(w["s_f"] + 1, w["e_f"])]
        p = None
        if pitch_hz is not None and w["s_f"] < pitch_hz.size:
            ps = pitch_hz[w["s_f"]:max(w["s_f"] + 1, w["e_f"])]
            ps = ps[ps > 0]
            p = float(np.median(ps)) if ps.size else None
        by_spk.setdefault(w.get("speaker") or "S1", []).append((w, float(seg.max()), p))
    out = []
    for rows in by_spk.values():
        if len(rows) < 8:
            continue
        lv = np.array([r[1] for r in rows])
        pv = np.array([r[2] if r[2] else np.nan for r in rows])
        lz = (lv - lv.mean()) / (lv.std() + 1e-6)
        pz = (pv - np.nanmean(pv)) / (np.nanstd(pv) + 1e-6) if np.isfinite(pv).sum() > 4 else np.zeros_like(lv)
        for (w, _, _), a, b in zip(rows, lz, np.nan_to_num(pz)):
            z = max(a, b)
            if z >= EMPHASIS_Z and len(norm(w["w"])) > 2 and norm(w["w"]) not in STOPWORDS:
                out.append({"i": w["i"], "w": w["w"], "s_f": w["s_f"], "z": round(float(z), 2),
                            "by": "loudness" if a >= b else "pitch"})
    return sorted(out, key=lambda x: -x["z"])
