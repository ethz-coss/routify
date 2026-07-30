#!/usr/bin/env python3
"""
ComputeSweepRouting.py

Parameter-sweep variant of ComputeFullRouting_v4.py for the sensitivity
analysis (see extended_experiment_setup.txt).

Differences from v4:
  - Sweeps 6 values per parameter instead of a single default set.
  - Distributes requests round-robin across several backend replicas
    and runs them concurrently.
  - Writes to the NVMe volume, streams batch files to disk, and
    checkpoints so an interrupted run can resume.

Output format is IDENTICAL to ComputeFullRouting_v4.py:
    [ {"index": <pair idx>, "data": <payload>, "responses": {mode: <route json>}}, ... ]
  written as routing_results_<date>_batch<NNN>_<start>-<end>.json with
  indent=4. PostProcessDataFull.py consumes it unchanged. Each sweep
  step is its own record; the swept value is visible in "data".

Usage:
    python ComputeSweepRouting.py                 # full run
    python ComputeSweepRouting.py --limit 8       # smoke test on 8 pairs
    python ComputeSweepRouting.py --bench 48      # throughput benchmark only
"""

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent

INPUT_PATH = SCRIPT_DIR / "coordinates.json"
OUTPUT_DIR = Path("/mnt/data/routify-sweep/results")
LOG_DIR = Path("/mnt/data/routify-sweep/logs")
CHECKPOINT = OUTPUT_DIR / "_checkpoint.json"

# Backend replicas to spread load across.
BACKENDS = [
    "http://localhost:8091",
    "http://localhost:8092",
    "http://localhost:8093",
    "http://localhost:8094",
]

WORKERS = 8          # concurrent in-flight requests across all replicas
BATCH_SIZE = 25      # O/D pairs per output file (25 * 24 records ~ 600 MB)
TIMEOUT = 180        # seconds per request
RETRIES = 3

# Parameter defaults, matching ComputeFullRouting_v4.py.
DEFAULTS = {"green_index": 50, "slope": 10, "noise": 50, "air": 50}

# Sweep A: slope threshold. Values are the Jenks class upper edges of the
# uphill slope distribution, with 10 (the existing default) at step 3.
SLOPE_VALUES = [30, 19, 10, 7, 3, 0]

# Sweep B: impact multiplier, applied to each of the three impact params.
IMPACT_VALUES = [0, 10, 25, 50, 75, 100]

IMPACT_PARAMS = {
    "green_index": "routing_mode_green",
    "noise": "routing_mode_noise",
    "air": "routing_mode_air",
}


def build_configs(only=None):
    """
    Returns the list of (param_name, value, routing_mode) tuples that make
    up one pair's worth of work: 6 slope + 6 x 3 impact = 24.

    `only` restricts the sweep to a single parameter (e.g. "air"), which
    yields 6 configs -- used to re-run one mode without touching the rest.
    """
    configs = [("slope", v, "routing_mode_slope") for v in SLOPE_VALUES]
    for param, mode in IMPACT_PARAMS.items():
        configs += [(param, v, mode) for v in IMPACT_VALUES]
    if only:
        configs = [c for c in configs if c[0] == only]
        if not configs:
            raise SystemExit(f"unknown sweep parameter: {only}")
    return configs


CONFIGS = build_configs()


def make_payload(item, param=None, value=None):
    o, d = item["origin"], item["destination"]
    if not (isinstance(o, (list, tuple)) and len(o) == 2
            and isinstance(d, (list, tuple)) and len(d) == 2):
        raise ValueError("origin/destination must be [lat, lon]")
    payload = {
        "fromLat": float(o[0]), "fromLon": float(o[1]),
        "toLat": float(d[0]), "toLon": float(d[1]),
        **DEFAULTS,
    }
    if param is not None:
        payload[param] = value
    return payload


_counter = threading.local()
_rr = threading.Lock()
_rr_state = {"i": 0}


def next_backend():
    with _rr:
        b = BACKENDS[_rr_state["i"] % len(BACKENDS)]
        _rr_state["i"] += 1
        return b


def fetch_one(task, session_map, errlog):
    """
    task = (pair_index, item, param, value, mode)
    Returns a v4-shaped record, or None on failure.
    """
    idx, item, param, value, mode = task
    payload = make_payload(item, param, value)
    base = next_backend()
    sess = session_map[threading.get_ident()]

    for attempt in range(RETRIES):
        try:
            r = sess.post(f"{base}/route/{mode}/", json=payload, timeout=TIMEOUT)
            if r.status_code == 200:
                return {"index": idx, "data": payload, "responses": {mode: r.json()}}
            reason = f"HTTP {r.status_code}"
        except Exception as exc:
            reason = repr(exc)
        if attempt == RETRIES - 1:
            errlog.write(f"{datetime.now().isoformat()}\tpair={idx}\t{param}={value}\t"
                         f"{mode}\t{base}\t{reason}\n")
            errlog.flush()
        else:
            time.sleep(1.5 * (attempt + 1))
    return None


def write_batch(path, records):
    """
    Writes a standard JSON array, one compact record per line.

    Identical data and identical parse result to v4's
    json.dump(records, indent=4) -- json.load() returns the same object --
    but without the pretty-printing whitespace, which accounts for ~5x of
    the file size on these deeply nested per-edge structures.
    Records are streamed so the serialised text is never held in memory.
    """
    with open(path, "w") as f:
        if not records:
            f.write("[]")
            return
        f.write("[\n")
        for i, rec in enumerate(records):
            f.write(json.dumps(rec, separators=(",", ":")))
            f.write(",\n" if i < len(records) - 1 else "\n")
        f.write("]")


def load_checkpoint():
    if CHECKPOINT.exists():
        try:
            return set(json.loads(CHECKPOINT.read_text())["done_batches"])
        except Exception:
            return set()
    return set()


def save_checkpoint(done):
    tmp = CHECKPOINT.with_suffix(".tmp")
    tmp.write_text(json.dumps({"done_batches": sorted(done)}, indent=2))
    tmp.replace(CHECKPOINT)


def check_backends():
    ok = []
    for b in BACKENDS:
        try:
            r = requests.get(f"{b}/status/", timeout=5)
            if r.status_code == 200:
                ok.append(b)
                print(f"  {b}  OK  ({r.json().get('edge_count', '?')} edges)")
                continue
        except Exception:
            pass
        print(f"  {b}  UNREACHABLE")
    return ok


def run_benchmark(coords, n):
    print(f"\nBenchmark: {n} requests, {len(BACKENDS)} replicas, {WORKERS} workers")
    tasks = []
    for i in range(n):
        item = coords[200 + (i % 48)]
        tasks.append((i, item, "slope", 10, "routing_mode_slope"))

    session_map = {}
    errlog = open(LOG_DIR / "bench_errors.tsv", "a")

    def worker(t):
        tid = threading.get_ident()
        if tid not in session_map:
            session_map[tid] = requests.Session()
        return fetch_one(t, session_map, errlog)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=globals()["WORKERS"]) as ex:
        res = list(ex.map(worker, tasks))
    dt = time.perf_counter() - t0
    errlog.close()

    good = sum(1 for r in res if r)
    rps = n / dt
    print(f"  wall {dt:.1f}s   {rps:.2f} req/s   ok {good}/{n}")
    total = 48000
    print(f"  -> {total:,} requests would take {total/rps/3600:.1f} h")
    return rps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="only process the first N O/D pairs")
    ap.add_argument("--bench", type=int, default=None,
                    help="run a throughput benchmark of N requests and exit")
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--param", type=str, default=None,
                    choices=["slope", "green_index", "noise", "air"],
                    help="sweep only this parameter (6 configs) instead of all 24")
    ap.add_argument("--outdir", type=Path, default=None,
                    help="write results here instead of the default results/ folder")
    args = ap.parse_args()

    globals()["WORKERS"] = args.workers
    if args.param:
        globals()["CONFIGS"] = build_configs(only=args.param)
    if args.outdir:
        globals()["OUTPUT_DIR"] = args.outdir
        globals()["CHECKPOINT"] = args.outdir / "_checkpoint.json"

    OUTPUT_DIR = globals()["OUTPUT_DIR"]
    CHECKPOINT = globals()["CHECKPOINT"]
    CONFIGS = globals()["CONFIGS"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    coords = json.loads(INPUT_PATH.read_text())

    print("Backends:")
    live = check_backends()
    if not live:
        sys.exit("No reachable backends.")
    if len(live) < len(BACKENDS):
        print(f"WARNING: only {len(live)}/{len(BACKENDS)} replicas reachable.")

    if args.bench:
        run_benchmark(coords, args.bench)
        return

    if args.limit:
        coords = coords[:args.limit]

    total_pairs = len(coords)
    total_reqs = total_pairs * len(CONFIGS)
    done = load_checkpoint()

    print(f"\nPairs: {total_pairs}   configs/pair: {len(CONFIGS)}   "
          f"requests: {total_reqs:,}")
    print(f"Output: {OUTPUT_DIR}")
    if done:
        print(f"Resuming: {len(done)} batches already complete.")

    run_date = datetime.now().strftime("%Y%m%d")
    session_map = {}
    errlog = open(LOG_DIR / f"errors_{run_date}.tsv", "a")

    def worker(t):
        tid = threading.get_ident()
        if tid not in session_map:
            session_map[tid] = requests.Session()
        return fetch_one(t, session_map, errlog)

    t_start = time.perf_counter()
    completed_reqs = 0
    batch_idx = 0

    for start in range(0, total_pairs, BATCH_SIZE):
        batch_idx += 1
        end = min(start + BATCH_SIZE, total_pairs)
        if batch_idx in done:
            print(f"batch {batch_idx:03d}  pairs {start}-{end-1}  SKIP (done)")
            continue

        tasks = []
        for i in range(start, end):
            for param, value, mode in CONFIGS:
                tasks.append((i, coords[i], param, value, mode))

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=globals()["WORKERS"]) as ex:
            results = list(ex.map(worker, tasks))
        dt = time.perf_counter() - t0

        records = [r for r in results if r]
        out = OUTPUT_DIR / (f"routing_results_{run_date}_batch{batch_idx:03d}_"
                            f"{start:06d}-{end-1:06d}.json")
        write_batch(out, records)

        done.add(batch_idx)
        save_checkpoint(done)

        completed_reqs += len(tasks)
        elapsed = time.perf_counter() - t_start
        rate = completed_reqs / elapsed
        remaining = (total_reqs - completed_reqs) / rate / 3600 if rate else 0
        size_mb = out.stat().st_size / 1e6
        print(f"batch {batch_idx:03d}  pairs {start}-{end-1}  "
              f"{len(records)}/{len(tasks)} ok  {dt:.0f}s  "
              f"{len(tasks)/dt:.2f} req/s  {size_mb:.0f} MB  "
              f"ETA {remaining:.1f} h")

    errlog.close()
    print(f"\nDone in {(time.perf_counter()-t_start)/3600:.2f} h")


if __name__ == "__main__":
    main()
