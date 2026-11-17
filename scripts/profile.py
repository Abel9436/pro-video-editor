#!/usr/bin/env python3
"""Create, read and update creator profiles (profiles/<name>.json).

Usage:
  python scripts/profile.py create NAME [--from FILE.json]
  python scripts/profile.py show NAME
  python scripts/profile.py set NAME KEY=VALUE [KEY=VALUE ...]     dotted keys, JSON values
        e.g. colors.primary='"#FF5A00"'  caption_template='"bold_1word"'  names='["Abebe","Addis"]'
  python scripts/profile.py add NAME LIST VALUE [VALUE ...]         append to a list (names, never_cut, ...)
  python scripts/profile.py learn NAME --from P/edl/v1.json --to P/edl/v2.json [--note "client said punchier"]
  python scripts/profile.py analytics NAME --video ID --retention CURVE.csv --predicted P/retention.json
  python scripts/profile.py list

A profile is what makes the tenth edit match the first: fonts, colours, caption template, logo
placement, intro/outro rules, music taste, names and terms to spell correctly, segments never
to cut, default styles per platform, and learned preferences. plan_edit.py reads caption
template, never_cut and default style; render.py reads fonts, colours and logo; qc.py reads names.

learn: compares two EDL versions after a revision and records what moved (cuts per minute,
zooms, SFX, music, look...) with the note that caused it. Repeated moves in the same direction
(2 or more) become a learned preference that the next paper edit should apply.
analytics: stores a real audience-retention curve (CSV of seconds,percent watched) next to the
predicted risk from retention_sim.py and reports whether predicted dips matched real drops,
so the rules can be tuned per channel.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.common import fail, log, read_json, write_json  # noqa: E402
from lib.edl import edl_diff, edl_metrics  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
PROFILES = SKILL / "profiles"
TEMPLATE = {
    "version": 1,
    "name": "",
    "fonts": {"caption": "Poppins ExtraBold", "heading": "Anton", "ethiopic": "Noto Sans Ethiopic"},
    "colors": {"primary": "#FFD400", "text": "#FFFFFF", "stroke": "#000000"},
    "caption_template": None,
    "logo": {"path": None, "position": "top_right", "size_pct": 8, "opacity": 0.85, "when": "never"},
    "intro": {"allowed": False, "max_s": 0}, "outro": {"allowed": False, "max_s": 0, "cta": None},
    "music_taste": {"moods": [], "avoid": [], "max_bpm": None},
    "names": [], "terms": [], "never_cut": [],
    "default_styles": {},
    "learned": [], "preferences": {}, "analytics": [],
}
LEARN_KEYS = ("cuts_per_min", "zooms_per_min", "sfx", "music", "graphics", "shot_len_med_s", "duration_s")
LEARN_MIN_REPEATS = 2
DROP_PCT = 3.0        # a real drop: retention falls this many points within 2 s (STARTING DEFAULT)


def ppath(name: str) -> Path:
    if not name.replace("_", "").replace("-", "").isalnum():
        fail(f"profile name '{name}' must be letters, digits, - or _")
    return PROFILES / f"{name}.json"


def load(name: str) -> dict:
    p = ppath(name)
    if not p.exists():
        fail(f"no profile '{name}' (create it with: profile.py create {name})")
    return read_json(p)


def set_key(d: dict, key: str, value) -> None:
    parts = key.split(".")
    for k in parts[:-1]:
        d = d.setdefault(k, {})
        if not isinstance(d, dict):
            fail(f"{key}: {k} is not an object")
    d[parts[-1]] = value


def parse_value(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw          # bare words are strings


def learn(prof: dict, a_path: str, b_path: str, note: str | None) -> list[str]:
    a, b = read_json(a_path), read_json(b_path)
    ma, mb = edl_metrics(a), edl_metrics(b)
    moves = {}
    for k in LEARN_KEYS:
        if isinstance(ma[k], (int, float)) and ma[k] != mb[k]:
            moves[k] = "up" if mb[k] > ma[k] else "down"
    for k in ("caption_template", "look"):
        if ma[k] != mb[k]:
            moves[k] = mb[k]
    prof["learned"].append({"date": dt.date.today().isoformat(), "from": a_path, "to": b_path, "note": note,
                            "moves": moves, "changes": edl_diff(a, b)[:20]})
    out = []
    for k, v in moves.items():
        same = sum(1 for e in prof["learned"] if e["moves"].get(k) == v)
        if same >= LEARN_MIN_REPEATS:
            pref = {"value": v, "seen": same, "since": prof["learned"][0]["date"]}
            if prof["preferences"].get(k, {}).get("value") != v or prof["preferences"][k]["seen"] != same:
                prof["preferences"][k] = pref
                out.append(f"preference: {k} {v} (seen in {same} revisions)")
    return out


def analytics(prof: dict, video: str, curve_csv: str, predicted: str | None) -> dict:
    pts = []
    with open(curve_csv, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            try:
                pts.append((float(row[0]), float(row[1])))
            except (ValueError, IndexError):
                continue          # header or blank
    if len(pts) < 3:
        fail(f"{curve_csv}: need rows of seconds,percent")
    drops = []
    for i in range(len(pts)):
        j = next((k for k in range(i + 1, len(pts)) if pts[k][0] - pts[i][0] >= 2), None)
        if j is not None and pts[i][1] - pts[j][1] >= DROP_PCT and pts[i][0] > 1:
            if not drops or pts[i][0] - drops[-1] > 2:
                drops.append(pts[i][0])
    rec = {"video": video, "date": dt.date.today().isoformat(), "real_drops_s": drops,
           "final_pct": pts[-1][1], "curve": curve_csv}
    if predicted:
        pr = read_json(predicted)
        dips = [d["t"] for d in pr.get("dips", [])]
        hit = [d for d in drops if any(abs(d - p) <= 2 for p in dips)]
        rec.update(predicted_dips_s=dips, matched=len(hit), missed=len(drops) - len(hit),
                   false_alarms=sum(1 for p in dips if not any(abs(d - p) <= 2 for d in drops)))
    prof["analytics"].append(rec)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("name"); c.add_argument("--from", dest="src")
    s = sub.add_parser("show"); s.add_argument("name")
    st = sub.add_parser("set"); st.add_argument("name"); st.add_argument("pairs", nargs="+")
    ad = sub.add_parser("add"); ad.add_argument("name"); ad.add_argument("list"); ad.add_argument("values", nargs="+")
    le = sub.add_parser("learn"); le.add_argument("name"); le.add_argument("--from", dest="a", required=True)
    le.add_argument("--to", dest="b", required=True); le.add_argument("--note")
    an = sub.add_parser("analytics"); an.add_argument("name"); an.add_argument("--video", required=True)
    an.add_argument("--retention", required=True); an.add_argument("--predicted")
    sub.add_parser("list")
    a = ap.parse_args()
    if a.cmd == "list":
        names = sorted(p.stem for p in PROFILES.glob("*.json"))
        print(json.dumps(names)); return
    p = ppath(a.name)
    if a.cmd == "create":
        if p.exists():
            fail(f"profile '{a.name}' exists; use set/add to change it")
        prof = json.loads(json.dumps(TEMPLATE))
        if a.src:
            try:
                for k, v in read_json(a.src).items():
                    prof[k] = v
            except FileNotFoundError as e:
                fail(str(e))
        prof["name"] = a.name
        write_json(p, prof); log(f"created {p}"); return
    prof = load(a.name)
    try:
        if a.cmd == "show":
            print(json.dumps(prof, indent=2, ensure_ascii=False)); return
        if a.cmd == "set":
            for pair in a.pairs:
                if "=" not in pair:
                    fail(f"'{pair}' is not KEY=VALUE")
                k, v = pair.split("=", 1)
                set_key(prof, k, parse_value(v))
        elif a.cmd == "add":
            lst = prof.setdefault(a.list, [])
            if not isinstance(lst, list):
                fail(f"{a.list} is not a list")
            lst += [v for v in a.values if v not in lst]
        elif a.cmd == "learn":
            for line in learn(prof, a.a, a.b, a.note) or ["recorded; no repeated preference yet"]:
                log(f"  {line}")
        elif a.cmd == "analytics":
            rec = analytics(prof, a.video, a.retention, a.predicted)
            log(f"  real drops at {rec['real_drops_s']} s" + (f"; predicted matched {rec['matched']}, missed {rec['missed']}, "
                                                            f"false alarms {rec['false_alarms']}" if a.predicted else ""))
    except FileNotFoundError as e:
        fail(str(e))
    write_json(p, prof)
    log(f"updated {p}")


if __name__ == "__main__":
    main()
