#!/usr/bin/env python3
"""Build a blind A/B page: two edits of the same footage side by side, unlabeled, in random order.

Usage:
  python evals/ab_page.py --a skill_edit.mp4 --b human_edit.mp4 [--name project] [--out ab/index.html]

The page copies both videos next to it as left.mp4/right.mp4 (which is which is stored only in
key.json, not in the page), lets each viewer pick "left is better / right is better / same",
with an optional reason, and keeps votes in the viewer's browser. "Export votes" downloads a
JSON file; collect those files and run with --tally DIR to count preferences against key.json.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Which edit is better?</title>
<style>
:root { --bg: #f6f6f4; --fg: #1d1d1b; --card: #fff; --line: #ddd; --accent: #2457d6; }
@media (prefers-color-scheme: dark) { :root { --bg: #151514; --fg: #ececea; --card: #20201f; --line: #3a3a38; --accent: #7aa2ff; } }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif; }
main { max-width: 1000px; margin: 0 auto; padding: 24px 16px; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 640px) { .pair { grid-template-columns: 1fr; } }
figure { margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
video { width: 100%; max-height: 70vh; background: #000; border-radius: 6px; }
.votes { display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0; }
button { font: inherit; padding: 10px 16px; border-radius: 8px; border: 1px solid var(--line); background: var(--card); color: var(--fg); cursor: pointer; }
button.on { border-color: var(--accent); outline: 2px solid var(--accent); }
textarea { width: 100%; box-sizing: border-box; min-height: 60px; font: inherit; background: var(--card); color: var(--fg); border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
.muted { opacity: .7; font-size: 14px; }
</style></head><body><main>
<h1>Which edit is better?</h1>
<p class="muted">Watch both with sound. They are in random order and unlabeled. Project: __NAME__</p>
<div class="pair">
  <figure><video src="left.mp4" controls playsinline preload="metadata"></video><figcaption>Left</figcaption></figure>
  <figure><video src="right.mp4" controls playsinline preload="metadata"></video><figcaption>Right</figcaption></figure>
</div>
<div class="votes">
  <button data-v="left">Left is better</button><button data-v="right">Right is better</button><button data-v="same">About the same</button>
</div>
<textarea id="why" placeholder="Why? (optional)"></textarea>
<p><button id="save">Save my vote</button> <button id="export">Export votes</button> <span id="msg" class="muted"></span></p>
</main>
<script>
const KEY = "ab_votes___NAME__";
let pick = null;
const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; } };
document.querySelectorAll("[data-v]").forEach(b => b.onclick = () => {
  pick = b.dataset.v; document.querySelectorAll("[data-v]").forEach(x => x.classList.toggle("on", x === b)); });
document.getElementById("save").onclick = () => {
  if (!pick) { document.getElementById("msg").textContent = "Pick one first."; return; }
  const v = load(); v.push({ project: "__NAME__", pick, why: document.getElementById("why").value, at: new Date().toISOString() });
  try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {}
  document.getElementById("msg").textContent = "Saved (" + v.length + " vote(s) in this browser).";
};
document.getElementById("export").onclick = () => {
  const blob = new Blob([JSON.stringify(load(), null, 2)], { type: "application/json" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "votes___NAME__.json"; a.click();
};
</script></body></html>
"""


def tally(folder: Path) -> dict:
    key = json.loads((folder / "key.json").read_text(encoding="utf-8"))
    c = Counter()
    for f in folder.glob("votes_*.json"):
        for v in json.loads(f.read_text(encoding="utf-8")):
            c[key.get(v["pick"], v["pick"])] += 1
    return dict(c)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a"); ap.add_argument("--b"); ap.add_argument("--name", default="project")
    ap.add_argument("--out", default="ab/index.html"); ap.add_argument("--tally")
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    if a.tally:
        print(json.dumps(tally(Path(a.tally)), indent=2)); return
    if not (a.a and a.b) or not Path(a.a).exists() or not Path(a.b).exists():
        print("error: --a and --b must be existing video files", file=sys.stderr); sys.exit(1)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    pair = [("A", Path(a.a)), ("B", Path(a.b))]
    random.Random(a.seed).shuffle(pair)
    shutil.copy2(pair[0][1], out.parent / "left.mp4"); shutil.copy2(pair[1][1], out.parent / "right.mp4")
    (out.parent / "key.json").write_text(json.dumps({"left": pair[0][0], "right": pair[1][0], "same": "same",
                                                     "A": str(a.a), "B": str(a.b)}, indent=2), encoding="utf-8")
    safe = "".join(ch for ch in a.name if ch.isalnum() or ch in "-_") or "project"
    out.write_text(PAGE.replace("__NAME__", safe), encoding="utf-8")
    print(f"wrote {out} (key in {out.parent / 'key.json'}; do not share the key with viewers)")


if __name__ == "__main__":
    main()
