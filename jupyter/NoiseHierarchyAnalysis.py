#!/usr/bin/env python3
"""
NoiseHierarchyAnalysis.py

Relates the OSM street-type hierarchy to per-edge noise exposure, using the
routing_mode_noise sweep output as the source of per-edge noise values.

Noise is a static graph attribute (CustomEdge sets it to the mean of its two
vertices' raster values), so edges are de-duplicated by edge id: each physical
edge contributes one observation regardless of how often the router traversed
it. Edges with noise <= 0 are treated as missing and excluded.

Writes two CSVs -- per-class statistics and correlation coefficients -- and
prints the same tables. Interpretation of the results lives in
findings_noise_hierarchy.md; this script only produces numbers.

Usage:
    python NoiseHierarchyAnalysis.py
    python NoiseHierarchyAnalysis.py --in DIR --outdir DIR --cache FILE
"""

import argparse
import collections
import csv
import glob
import json
import math
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

IN_DIR = Path("/mnt/data/routify-sweep/results_splitted/routing_mode_noise")
CACHE = Path("/mnt/data/routify-sweep/logs/noise_edges.csv")

# Drive cost multiplier: config_features.json weight_modifiers[highway]["drive"],
# restricted to RoutifyConfig.allowedFeaturesDrive. Anything else is 10000.
DRIVE_MULT = {
    "motorway": 1.0, "motorway_link": 1.0, "trunk": 1.0, "trunk_link": 1.0,
    "primary": 1.0, "primary_link": 1.0, "secondary": 1.0,
    "secondary_link": 1.0, "tertiary": 1.0, "tertiary_link": 1.0, "road": 1.0,
    "residential": 1.5, "living_street": 2.0, "service": 2.5,
}
DEFAULT_MULT = 10000.0

# OSM road-importance rank, 1 = highest capacity. Non-road classes have none.
IMPORTANCE = {
    "motorway": 1, "motorway_link": 1, "trunk": 2, "trunk_link": 2,
    "primary": 3, "primary_link": 3, "secondary": 4, "secondary_link": 4,
    "tertiary": 5, "tertiary_link": 5, "unclassified": 6, "residential": 7,
    "living_street": 8, "service": 9,
}


# --------------------------------------------------------------------------
# statistics helpers
# --------------------------------------------------------------------------

def energy_mean(vals):
    """
    Mean of a set of dB values in the energy domain.

    Decibels are logarithmic, so the arithmetic mean of dB values has no
    physical meaning. This is the level of a signal carrying the same total
    acoustic energy, and is the correct summary for exposure.
    """
    return 10 * math.log10(sum(10 ** (v / 10) for v in vals) / len(vals))


def median(v):
    s = sorted(v)
    k = len(s)
    return s[k // 2] if k % 2 else (s[k // 2 - 1] + s[k // 2]) / 2


def stdev(v):
    if len(v) < 2:
        return 0.0
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    return num / (dx * dy) if dx and dy else float("nan")


def rankdata(v):
    """Ranks with ties averaged, as Spearman requires."""
    order = sorted(range(len(v)), key=lambda i: v[i])
    ranks = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x, y):
    return pearson(rankdata(x), rankdata(y))


# --------------------------------------------------------------------------
# data loading
# --------------------------------------------------------------------------

def scan_sweep(in_dir):
    """Streams the batch files, returns {edge_id: (highway, noise, distance)}
    plus a traversal counter."""
    edges = {}
    usage = collections.Counter()
    files = sorted(glob.glob(f"{in_dir}/routing_results_*.json"))
    if not files:
        raise SystemExit(f"no batch files in {in_dir}")
    print(f"scanning {len(files)} files ...", flush=True)

    for i, p in enumerate(files, 1):
        with open(p) as f:
            for line in f:
                line = line.strip().rstrip(",")
                if not line.startswith("{"):
                    continue
                for routes in json.loads(line)["responses"].values():
                    for route in routes:
                        for e in route["edges"]:
                            eid = e["id"]
                            usage[eid] += 1
                            if eid not in edges:
                                edges[eid] = (e.get("highway") or "(none)",
                                              e["noise"], e["distance"])
        if i % 20 == 0:
            print(f"  {i}/{len(files)}  {len(edges):,} unique edges", flush=True)
    return edges, usage


def write_cache(path, edges, usage):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "highway", "noise", "distance", "usage"])
        for eid, (h, n, d) in edges.items():
            w.writerow([eid, h, n, d, usage[eid]])
    print(f"cached {len(edges):,} edges -> {path}")


def read_cache(path):
    edges, usage = {}, {}
    with open(path) as f:
        for r in csv.DictReader(f):
            edges[r["id"]] = (r["highway"], float(r["noise"]),
                              float(r["distance"]))
            usage[r["id"]] = int(r["usage"])
    print(f"loaded {len(edges):,} edges from cache {path}")
    return edges, usage


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", type=Path, default=IN_DIR)
    ap.add_argument("--outdir", type=Path, default=SCRIPT_DIR)
    ap.add_argument("--cache", type=Path, default=CACHE,
                    help="per-edge CSV; reused if present, written if not")
    ap.add_argument("--rescan", action="store_true",
                    help="ignore an existing cache and re-read the sweep")
    args = ap.parse_args()

    if args.cache.exists() and not args.rescan:
        edges, usage = read_cache(args.cache)
    else:
        edges, usage = scan_sweep(args.in_dir)
        write_cache(args.cache, edges, usage)

    args.outdir.mkdir(parents=True, exist_ok=True)

    total = len(edges)
    rows = [(h, n, d, usage[k]) for k, (h, n, d) in edges.items()]
    missing = [r for r in rows if r[1] <= 0]
    valid = [r for r in rows if r[1] > 0]

    print(f"\nunique edges          : {total:,}")
    print(f"noise <= 0 (missing)  : {len(missing):,} "
          f"({100 * len(missing) / total:.1f}%)")
    print(f"usable                : {len(valid):,}")
    print(f"total traversals      : {sum(usage.values()):,}")

    missing_by_class = collections.Counter(r[0] for r in missing)
    total_by_class = collections.Counter(r[0] for r in rows)

    # ---- per-class table -------------------------------------------------
    byclass = collections.defaultdict(list)
    for h, n, d, u in valid:
        byclass[h].append((n, d, u))

    out = []
    for h, vals in byclass.items():
        ns = [x[0] for x in vals]
        ds = [x[1] for x in vals]
        us = [x[2] for x in vals]
        out.append({
            "highway": h,
            "importance_rank": IMPORTANCE.get(h, ""),
            "drive_multiplier": DRIVE_MULT.get(h, DEFAULT_MULT),
            "drive_eligible": int(h in DRIVE_MULT),
            "edges": len(vals),
            "length_km": round(sum(ds) / 1000, 3),
            "noise_mean_db": round(sum(ns) / len(ns), 3),
            "noise_energy_db": round(energy_mean(ns), 3),
            "noise_median_db": round(median(ns), 3),
            "noise_sd_db": round(stdev(ns), 3),
            "noise_min_db": round(min(ns), 3),
            "noise_max_db": round(max(ns), 3),
            "noise_length_weighted_db": round(
                sum(a * b for a, b, _ in vals) / sum(ds), 3),
            "noise_usage_weighted_db": round(
                sum(a * c for a, _, c in vals) / sum(us), 3),
            "traversals": sum(us),
            "edges_missing_noise": missing_by_class.get(h, 0),
            "missing_noise_pct": round(
                100 * missing_by_class.get(h, 0) / total_by_class[h], 3),
        })

    out.sort(key=lambda r: (r["importance_rank"] == "",
                            r["importance_rank"] or 0, -r["edges"]))

    p1 = args.outdir / "noise_hierarchy_by_street_type.csv"
    with open(p1, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"\nwrote {p1}")

    print(f"\n{'highway':<16}{'edges':>8}{'km':>7}{'mean':>8}{'energy':>8}"
          f"{'median':>8}{'sd':>7}{'len-wt':>8}{'drive_x':>9}")
    print("-" * 79)
    for r in out:
        print(f"{r['highway']:<16}{r['edges']:>8,}{r['length_km']:>7.0f}"
              f"{r['noise_mean_db']:>8.2f}{r['noise_energy_db']:>8.2f}"
              f"{r['noise_median_db']:>8.2f}{r['noise_sd_db']:>7.2f}"
              f"{r['noise_length_weighted_db']:>8.2f}"
              f"{r['drive_multiplier']:>9}")

    # ---- correlations ----------------------------------------------------
    corr = []

    xs = [IMPORTANCE[h] for h, n, d, u in valid if h in IMPORTANCE]
    ys = [n for h, n, d, u in valid if h in IMPORTANCE]
    corr.append({
        "relationship": "importance_rank_vs_noise",
        "level": "edge", "n": len(xs),
        "spearman_rho": round(spearman(xs, ys), 4),
        "pearson_r": round(pearson(xs, ys), 4),
        "note": "rank 1=motorway..9=service; negative => higher class is louder",
    })

    xs = [DRIVE_MULT[h] for h, n, d, u in valid if h in DRIVE_MULT]
    ys = [n for h, n, d, u in valid if h in DRIVE_MULT]
    corr.append({
        "relationship": "drive_multiplier_vs_noise_eligible_only",
        "level": "edge", "n": len(xs),
        "spearman_rho": round(spearman(xs, ys), 4),
        "pearson_r": round(pearson(xs, ys), 4),
        "note": "11 of 14 eligible classes share multiplier 1.0",
    })

    xs = [DRIVE_MULT.get(h, DEFAULT_MULT) for h, n, d, u in valid]
    ys = [n for h, n, d, u in valid]
    corr.append({
        "relationship": "drive_multiplier_vs_noise_all_classes",
        "level": "edge", "n": len(xs),
        "spearman_rho": round(spearman(xs, ys), 4),
        "pearson_r": "",
        "note": "Pearson meaningless with the 10000 sentinel; rank-based only",
    })

    cl = [(r["importance_rank"], r["noise_mean_db"])
          for r in out if r["importance_rank"] != ""]
    corr.append({
        "relationship": "class_mean_noise_vs_importance_rank",
        "level": "class", "n": len(cl),
        "spearman_rho": round(spearman([c[0] for c in cl],
                                       [c[1] for c in cl]), 4),
        "pearson_r": round(pearson([c[0] for c in cl],
                                   [c[1] for c in cl]), 4),
        "note": "one observation per street class",
    })

    p2 = args.outdir / "noise_hierarchy_correlations.csv"
    with open(p2, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(corr[0].keys()))
        w.writeheader()
        w.writerows(corr)
    print(f"\nwrote {p2}")

    print(f"\n{'relationship':<42}{'level':>7}{'n':>10}{'rho':>9}{'r':>9}")
    print("-" * 77)
    for c in corr:
        r = f"{c['pearson_r']}" if c["pearson_r"] != "" else "-"
        print(f"{c['relationship']:<42}{c['level']:>7}{c['n']:>10,}"
              f"{c['spearman_rho']:>9}{r:>9}")

    alln = [n for h, n, d, u in valid]
    print(f"\noverall (valid edges): mean {sum(alln)/len(alln):.2f} dB  "
          f"median {median(alln):.2f}  sd {stdev(alln):.2f}  "
          f"min {min(alln):.2f}  max {max(alln):.2f}")


if __name__ == "__main__":
    main()
