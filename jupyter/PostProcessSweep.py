#!/usr/bin/env python3
"""
PostProcessSweep.py

Runs PostProcessDataFull.py's reduction over every batch file of the
sensitivity sweep, writing the results into a separate folder.

This is a driver only: it imports load_aggregated_file() and
postprocess_aggregated_data() from PostProcessDataFull and applies them
unchanged, so the output is identical to running

    python PostProcessDataFull.py <batch file>

on each file individually -- the only difference is that output lands in
reduced/ instead of next to the input, leaving results/ untouched.

Usage:
    python PostProcessSweep.py [--in DIR] [--out DIR] [--force]
"""

import argparse
import gc
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PostProcessDataFull import load_aggregated_file, postprocess_aggregated_data

IN_DIR = Path("/mnt/data/routify-sweep/results")
OUT_DIR = Path("/mnt/data/routify-sweep/reduced")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", type=Path, default=IN_DIR)
    ap.add_argument("--out", dest="out_dir", type=Path, default=OUT_DIR)
    ap.add_argument("--force", action="store_true",
                    help="reprocess files whose output already exists")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    batches = sorted(args.in_dir.glob("routing_results_*.json"))
    batches = [b for b in batches if not b.name.endswith("_reduced.json")]

    if not batches:
        sys.exit(f"No batch files found in {args.in_dir}")

    print(f"Input : {args.in_dir}  ({len(batches)} batch files)")
    print(f"Output: {args.out_dir}\n")

    t_start = time.perf_counter()
    total_routes = 0
    skipped = 0
    failed = []

    for i, src in enumerate(batches, 1):
        dst = args.out_dir / f"{src.stem}_reduced{src.suffix}"

        if dst.exists() and not args.force:
            print(f"[{i:3}/{len(batches)}] {src.name}  SKIP (exists)")
            skipped += 1
            continue

        t0 = time.perf_counter()
        data = load_aggregated_file(str(src))
        if data is None:
            print(f"[{i:3}/{len(batches)}] {src.name}  FAILED to load")
            failed.append(src.name)
            continue

        results = postprocess_aggregated_data(data)
        del data
        gc.collect()

        if not results:
            print(f"[{i:3}/{len(batches)}] {src.name}  FAILED (no output)")
            failed.append(src.name)
            continue

        # Same serialisation as PostProcessDataFull.main()
        with open(dst, "w") as f:
            json.dump(results, f, indent=4)

        n = len(results)
        total_routes += n
        dt = time.perf_counter() - t0
        elapsed = time.perf_counter() - t_start
        eta = (elapsed / i) * (len(batches) - i) / 60
        print(f"[{i:3}/{len(batches)}] {src.name}  "
              f"{n} routes  {dt:.0f}s  {dst.stat().st_size/1e6:.1f} MB  "
              f"ETA {eta:.0f} min")

        del results
        gc.collect()

    mins = (time.perf_counter() - t_start) / 60
    print(f"\nDone in {mins:.1f} min")
    print(f"  processed : {len(batches) - skipped - len(failed)} files")
    print(f"  skipped   : {skipped}")
    print(f"  failed    : {len(failed)}  {failed if failed else ''}")
    print(f"  routes    : {total_routes:,}")


if __name__ == "__main__":
    main()
