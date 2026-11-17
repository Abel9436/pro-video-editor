#!/usr/bin/env python3
"""Run the eval benchmark and compare with the last run (regression gate).

Usage:
  python evals/run_benchmark.py [--projects evals/projects.json] [--only NAME] [--preview]
                                [--accept "reason"] [--out-dir evals/results]

Each benchmark project (evals/projects.json) is raw footage the user owns plus a FROZEN paper
edit, so a run measures the scripts, not Claude's judgement on the day:
  {"name": "...", "type": "talking_head", "footage": "path/to/folder", "paper": "path/to/paper.json",
   "platform": "shorts", "human_edit": "optional/path.mp4"}
Per project: ingest -> analyze -> detect_type -> plan_edit draft -> render -> qc (with fix loop)
-> retention_sim -> virality_score. Recorded: QC pass/warn/fail counts and failed ids, virality
score, style-distance fields outside range, render success, run time per stage.

Regression rule: the run fails (exit 2) if any project's QC fails count rises, its virality
score drops by more than VIRALITY_TOL, or a render that succeeded now fails, unless --accept
gives a reason, which is stored with the results.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
VIRALITY_TOL = 3


def run(name: str, *args: str) -> tuple[int, str, float]:
    t0 = time.time()
    r = subprocess.run([sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.returncode, (r.stdout + r.stderr)[-2000:], round(time.time() - t0, 1)


def bench(p: dict, work: Path, preview: bool) -> dict:
    proj = work / p["name"]
    res = {"name": p["name"], "type": p.get("type"), "stages": {}, "ok": False}
    paper = Path(p["paper"])
    steps = [
        ("ingest", "ingest.py", [p["footage"], "--project", str(proj), "--platform", p.get("platform", "shorts")]),
        ("analyze", "analyze.py", ["--project", str(proj)]),
        ("detect_type", "detect_type.py", ["--project", str(proj)]),
        ("plan", "plan_edit.py", ["draft", str(paper), "--project", str(proj), "--out", str(proj / "edl" / "bench.json")]),
        ("render", "render.py", ["--edl", str(proj / "edl" / "bench.json"), "--project", str(proj), "--graphics-engine", "ass"]
         + (["--preview"] if preview else [])),
    ]
    for key, script, args in steps:
        code, out, secs = run(script, *args)
        res["stages"][key] = {"ok": code == 0, "s": secs}
        if code:
            res["stages"][key]["log"] = out
            return res
    video = proj / "exports" / ("bench_preview.mp4" if preview else "bench.mp4")
    code, out, secs = run("qc.py", "--video", str(video), "--edl", str(proj / "edl" / "bench.json"), "--project", str(proj),
                          "--fix-loop", *(["--preview"] if preview else []))
    res["stages"]["qc"] = {"ok": code == 0, "s": secs}
    qc = json.loads((proj / "qc" / "qc_report.json").read_text(encoding="utf-8")) if (proj / "qc" / "qc_report.json").exists() else {}
    res["qc"] = {"summary": qc.get("summary"), "failed": [c["id"] for c in qc.get("checks", []) if c["status"] == "fail"],
                 "style_out": [c.get("detail") for c in qc.get("checks", []) if c["id"] == "style_distance"]}
    edl = proj / "edl" / "bench.json"
    code, _, secs = run("retention_sim.py", "--edl", str(edl), "--project", str(proj))
    res["stages"]["retention"] = {"ok": code == 0, "s": secs}
    code, _, secs = run("virality_score.py", "--edl", str(edl), "--project", str(proj))
    res["stages"]["virality"] = {"ok": code == 0, "s": secs}
    v = json.loads((proj / "virality.json").read_text(encoding="utf-8")) if (proj / "virality.json").exists() else {}
    res["virality"] = v.get("score")
    res["ok"] = True
    res["total_s"] = round(sum(s["s"] for s in res["stages"].values()), 1)
    return res


def compare(prev: dict, cur: dict) -> list[str]:
    old = {r["name"]: r for r in prev.get("projects", [])}
    drops = []
    for r in cur["projects"]:
        o = old.get(r["name"])
        if not o:
            continue
        if o.get("ok") and not r.get("ok"):
            drops.append(f"{r['name']}: pipeline now fails")
        of = ((o.get("qc") or {}).get("summary") or {}).get("fail", 0)
        nf = ((r.get("qc") or {}).get("summary") or {}).get("fail", 0)
        if nf > of:
            drops.append(f"{r['name']}: QC fails {of} -> {nf} ({', '.join((r.get('qc') or {}).get('failed', []))})")
        if o.get("virality") is not None and r.get("virality") is not None and r["virality"] < o["virality"] - VIRALITY_TOL:
            drops.append(f"{r['name']}: virality {o['virality']} -> {r['virality']}")
    return drops


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects", default=str(HERE / "projects.json")); ap.add_argument("--only")
    ap.add_argument("--preview", action="store_true"); ap.add_argument("--accept")
    ap.add_argument("--out-dir", default=str(HERE / "results")); ap.add_argument("--work", default=str(SKILL.parent / "work" / "evals"))
    a = ap.parse_args()
    try:
        projects = json.loads(Path(a.projects).read_text(encoding="utf-8"))["projects"]
    except FileNotFoundError:
        print(f"error: {a.projects} not found", file=sys.stderr); sys.exit(1)
    projects = [p for p in projects if not a.only or p["name"] == a.only]
    for p in projects:                              # relative paths are relative to the skill folder
        for k in ("footage", "paper", "human_edit"):
            if p.get(k) and not Path(p[k]).is_absolute():
                p[k] = str((SKILL / p[k]).resolve())
    missing = [p["name"] for p in projects if not Path(p["footage"]).exists() or not Path(p["paper"]).exists()]
    if missing:
        print(f"skipping (footage or paper edit not on this machine): {', '.join(missing)}", file=sys.stderr)
    projects = [p for p in projects if p["name"] not in missing]
    if not projects:
        print("error: no runnable benchmark projects", file=sys.stderr); sys.exit(1)
    out_dir = Path(a.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    cur = {"date": dt.datetime.now().isoformat(timespec="seconds"), "preview": a.preview,
           "projects": [bench(p, Path(a.work), a.preview) for p in projects]}
    prev_files = sorted(out_dir.glob("run_*.json"))
    drops = compare(json.loads(prev_files[-1].read_text(encoding="utf-8")), cur) if prev_files else []
    cur["regressions"] = drops
    cur["accepted"] = a.accept
    path = out_dir / f"run_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    for r in cur["projects"]:
        print(f"{r['name']:<28} ok={r['ok']} qc={((r.get('qc') or {}).get('summary'))} virality={r.get('virality')} "
              f"time={r.get('total_s')}s")
    for d in drops:
        print(f"REGRESSION: {d}")
    print(f"wrote {path}")
    if drops and not a.accept:
        sys.exit(2)


if __name__ == "__main__":
    main()
