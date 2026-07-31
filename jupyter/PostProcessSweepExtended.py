#!/usr/bin/env python3
"""
PostProcessSweepExtended.py

Extended reduction for the sensitivity sweep. Produces a strict SUPERSET of
PostProcessSweep.py / PostProcessDataFull.py output: every existing field is
reproduced with identical semantics, and additional noise-exposure fields are
added alongside.

Motivation -- see findings_noise_hierarchy.md
--------------------------------------------
The existing reduction summarises a route's noise as a length-weighted
ARITHMETIC mean of dB values. Decibels are logarithmic, so that quantity has
no physical meaning, and it understates true exposure in proportion to the
within-route variance. The gap reaches +16.6 dB on the heterogeneous quiet
classes (track, path) that noise-optimised routes shift onto -- i.e. it is
largest exactly where the routing appears to be helping most.

This script adds the energy-domain equivalent

    L_eq = 10 * log10( sum(d_i * 10^(L_i/10)) / sum(d_i) )

which is the level of a source carrying the same total acoustic energy over
the route, plus the exposure-share metrics used in noise policy (share of
route length above 55 / 65 / 70 dB) and a per-street-class length breakdown.

Zero-noise edges
----------------
About 0.7% of edges carry noise = 0, meaning "no data" rather than "silent".
The original `noise` field is reproduced exactly as before -- zeros included,
which drags it down -- so the two outputs stay comparable. All *_energy and
share_* fields are computed over valid edges only, and the coverage is
reported per route in noise_valid_length_share so any route with thin
coverage can be filtered out.

Usage:
    python PostProcessSweepExtended.py --in DIR --out DIR [--force]
"""

import argparse
import gc
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PostProcessDataFull import load_aggregated_file

IN_DIR = Path("/mnt/data/routify-sweep/results_splitted/routing_mode_noise")
OUT_DIR = Path("/mnt/data/routify-sweep/results_split_reduced_extended/routing_mode_noise")

# dB thresholds for exposure shares. 55 and 65 are the EU Environmental Noise
# Directive reporting bands; 70 is added as a high-exposure marker.
THRESHOLDS = (55.0, 65.0, 70.0)


def reduce_route_extended(route):
    """
    Reduces one route to metrics. The first six keys are byte-for-byte the
    same computation as PostProcessDataFull.reduce_route_single; everything
    after is new.
    """
    if not isinstance(route, dict):
        return None
    edges = route.get("edges", [])
    if not isinstance(edges, list) or not edges:
        return None
    edges = [e for e in edges if isinstance(e, dict)]

    total_distance = sum(e.get("distance", 0) for e in edges)
    if total_distance == 0:
        return None

    # ---- original fields, unchanged semantics (zeros included) ----------
    noise_sum = sum(e.get("noise", 0) * e.get("distance", 0) for e in edges)
    slope_sum = sum(e.get("slope", 0) * e.get("distance", 0) for e in edges)
    green_sum = sum(e.get("greenIndex", 0) * e.get("distance", 0) for e in edges)
    pm10_sum = sum(e.get("pm_10", 0) * e.get("distance", 0) for e in edges)

    out = {
        "transportMode": route.get("transportMode", "unknown"),
        "traveltime": route.get("traveltime", 0),
        "distance": total_distance,
        "noise": noise_sum / total_distance,
        "slope": slope_sum / total_distance,
        "greenIndex": green_sum / total_distance,
        "pm_10": pm10_sum / total_distance,
    }

    # ---- extended noise fields, valid edges only ------------------------
    valid = [(e.get("noise", 0), e.get("distance", 0)) for e in edges
             if e.get("noise", 0) > 0 and e.get("distance", 0) > 0]
    valid_len = sum(d for _, d in valid)

    out["noise_valid_length_m"] = valid_len
    out["noise_valid_length_share"] = valid_len / total_distance

    if valid_len > 0:
        energy = sum(d * 10 ** (n / 10) for n, d in valid) / valid_len
        l_eq = 10 * math.log10(energy)
        linear_valid = sum(n * d for n, d in valid) / valid_len

        out["noise_energy"] = l_eq
        out["noise_linear_valid"] = linear_valid
        # How much the arithmetic mean understates the energy mean.
        out["noise_energy_bias"] = l_eq - linear_valid
        out["noise_max"] = max(n for n, _ in valid)
        out["noise_min"] = min(n for n, _ in valid)

        # length-weighted percentiles
        ordered = sorted(valid)
        for label, q in (("noise_p50", 0.50), ("noise_p95", 0.95)):
            acc, val = 0.0, ordered[-1][0]
            for n, d in ordered:
                acc += d
                if acc >= q * valid_len:
                    val = n
                    break
            out[label] = val

        # exposure shares of valid length
        for t in THRESHOLDS:
            share = sum(d for n, d in valid if n > t) / valid_len
            out[f"share_above_{int(t)}db"] = share
    else:
        for k in ("noise_energy", "noise_linear_valid", "noise_energy_bias",
                  "noise_max", "noise_min", "noise_p50", "noise_p95"):
            out[k] = 0
        for t in THRESHOLDS:
            out[f"share_above_{int(t)}db"] = 0

    # ---- street-class length breakdown ----------------------------------
    # Quantifies which classes carry the route, so the "footway and cycleway
    # inherit arterial noise" effect can be checked per route.
    by_class = defaultdict(float)
    for e in edges:
        by_class[e.get("highway") or "(none)"] += e.get("distance", 0)
    out["length_by_highway"] = {k: round(v, 2) for k, v in
                                sorted(by_class.items(), key=lambda x: -x[1])}

    return out


def extract_candidate_routes(response_obj):
    """Same shape-tolerant extraction as PostProcessDataFull."""
    routes = []
    if isinstance(response_obj, dict) and "route" in response_obj:
        if isinstance(response_obj["route"], dict):
            routes.append(response_obj["route"])
        elif isinstance(response_obj["route"], list):
            routes.extend([r for r in response_obj["route"] if isinstance(r, dict)])
    elif isinstance(response_obj, dict) and "routes" in response_obj \
            and isinstance(response_obj["routes"], list):
        routes.extend([r for r in response_obj["routes"] if isinstance(r, dict)])
    elif isinstance(response_obj, dict) and "edges" in response_obj:
        routes.append(response_obj)
    elif isinstance(response_obj, list):
        routes.extend([r for r in response_obj if isinstance(r, dict)])
    return routes


def postprocess_extended(data):
    """Mirrors postprocess_aggregated_data, using the extended reducer."""
    results = []
    for i, entry in enumerate(data):
        try:
            if not (isinstance(entry, dict) and "responses" in entry):
                continue
            new_entry = {"data": entry.get("data", {}), "responses": {}}
            for routing_mode, mode_response in entry.get("responses", {}).items():
                per_transport = {}
                for route in extract_candidate_routes(mode_response):
                    reduced = reduce_route_extended(route)
                    if not reduced:
                        continue
                    # NOTE: the doubled prefix is intentional -- it matches the
                    # existing reduced output so the two can be joined 1:1.
                    key = f"transport_mode_{reduced['transportMode']}"
                    if key not in per_transport:
                        per_transport[key] = {k: v for k, v in reduced.items()
                                              if k != "transportMode"}
                if per_transport:
                    new_entry["responses"][routing_mode] = per_transport
            results.append(new_entry)
        except Exception as exc:
            print(f"  error on record {i}: {exc}")
            continue
    return results


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
    total_routes = skipped = 0
    failed = []

    for i, src in enumerate(batches, 1):
        dst = args.out_dir / f"{src.stem}_reduced_extended{src.suffix}"
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

        results = postprocess_extended(data)
        del data
        gc.collect()

        if not results:
            print(f"[{i:3}/{len(batches)}] {src.name}  FAILED (no output)")
            failed.append(src.name)
            continue

        with open(dst, "w") as f:
            json.dump(results, f, indent=4)

        total_routes += len(results)
        dt = time.perf_counter() - t0
        elapsed = time.perf_counter() - t_start
        eta = (elapsed / i) * (len(batches) - i) / 60
        print(f"[{i:3}/{len(batches)}] {src.name}  {len(results)} routes  "
              f"{dt:.0f}s  {dst.stat().st_size/1e6:.1f} MB  ETA {eta:.0f} min")

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
