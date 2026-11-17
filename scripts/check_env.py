#!/usr/bin/env python3
"""Check every external tool the skill uses and report the fallbacks in effect.

Usage:
  python scripts/check_env.py [--out env.json] [--no-gpu-test]

Exits 1 when a required tool (FFmpeg, ffprobe, core Python packages) is missing.
Optional tools (GPU encoder, Node/Remotion, Blender, pyannote) only add fallbacks.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import write_json  # noqa: E402
from lib.env import check_all  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write the JSON report here (default: print to stdout)")
    ap.add_argument("--no-gpu-test", action="store_true", help="skip the GPU test-encode (faster)")
    args = ap.parse_args()

    report = check_all(test_gpu=not args.no_gpu_test)
    if args.out:
        write_json(args.out, report)
    else:
        print(json.dumps(report, indent=2))
    for line in report["fallbacks"]:
        print(f"fallback: {line}", file=sys.stderr)
    if report["fatal"]:
        for line in report["fatal"]:
            print(f"error: {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
