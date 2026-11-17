# Evals

| File | What it does |
|---|---|
| `triggers.json` | prompts that should and should not load the skill; re-run after any change to the SKILL.md description |
| `projects.json` | the benchmark: raw footage the user owns + a frozen paper edit per project |
| `papers/` | the frozen paper edits (the benchmark measures the scripts, not the day's judgement) |
| `run_benchmark.py` | runs every project end to end, records QC, virality, style distance, render success and run time, and compares with the last run |
| `results/run_*.json` | one file per run |
| `ab_page.py` | builds a blind A/B page (skill edit vs human edit), collects and tallies votes |

## Regression rule
`python evals/run_benchmark.py` exits 2 when a project's QC fail count rises, its virality score drops by more than 3, or a render that worked now fails. A change merges only if the run passes, or with `--accept "reason"`, which is stored with the results.

## Status (2026-11-15)
One project is defined and was run during the build: `talking_head_business_short`, the user's 60 s clip. The spec asks for 5 to start, growing to 30-50 across every type. The other types are listed under `needed` in `projects.json`: they need footage the user owns. No eval scores exist for those types yet, and their styles are STARTING DEFAULTS.

## Unit and integration tests
`python -m pytest tests -q` runs on synthetic media in under 2 minutes: ingest, analyze, plan, render, QC, viral scores, timeline round trip, package, profiles and localization.
