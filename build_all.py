#!/usr/bin/env python3
"""Master script: fetch library, generate cards, indexes, and cover.

Usage:
    python build_all.py                # Full build (fetch + generate everything)
    python build_all.py --skip-fetch   # Use existing library.json, just generate PDFs
    python build_all.py --preview N    # Quick test: N pages of cards + index subset
"""

import argparse
import os
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIBRARY_PATH = os.path.join(BASE_DIR, "library.json")
PREV_PATH = os.path.join(BASE_DIR, "library.prev.json")


def run(script, args=None):
    cmd = [sys.executable, os.path.join(BASE_DIR, script)]
    if args:
        cmd.extend(args)
    print(f"\n=== Running: {' '.join(cmd)} ===")
    r = subprocess.run(cmd, cwd=BASE_DIR)
    if r.returncode != 0:
        print(f"[ERROR] {script} failed with exit code {r.returncode}", file=sys.stderr)
        sys.exit(r.returncode)
    return r.returncode


def main():
    parser = argparse.ArgumentParser(description="Full catalog build pipeline")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip API fetch, reuse library.json")
    parser.add_argument("--preview", type=int, metavar="N", help="Quick build: only N pages / movies")
    args = parser.parse_args()

    steps = []
    if not args.skip_fetch:
        # Snapshot the previous library so we can diff new arrivals afterwards
        if os.path.exists(LIBRARY_PATH):
            shutil.copy(LIBRARY_PATH, PREV_PATH)
            print(f"[snapshot] current library saved to {PREV_PATH}")
        steps.append(("fetch_library.py", ["--force"]))

    steps.append(("generate_cards.py", ["--preview", str(args.preview)] if args.preview else []))
    if args.preview:
        steps.append(("generate_index.py", ["--preview", str(args.preview)]))
    else:
        steps.append(("generate_index.py", []))
        # Delta mode: card sheet only for movies added since the last build
        if not args.skip_fetch and os.path.exists(PREV_PATH):
            steps.append(("generate_cards.py", ["--new-only", "--movies-only"]))
    steps.append(("generate_cover.py", []))

    for script, extra in steps:
        if script:
            run(script, extra)

    outdir = os.path.join(BASE_DIR, "output")
    print("\n" + "=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    for f in sorted(os.listdir(outdir)):
        size = os.path.getsize(os.path.join(outdir, f)) / 1024 / 1024
        print(f"  {f:20s} {size:6.1f} MB")
    print("\nOutput: ", outdir)


if __name__ == "__main__":
    main()