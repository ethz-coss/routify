#!/usr/bin/env python3
"""
SlopeDistribution.py

Computes and plots the statistical distribution of per-edge slopes across
Routify's routing graph, consuming the JSON dump produced by the backend
endpoint  GET /status/graph/  (CustomGraph.exportJson).

Expected input shape:
    {
      "vertices": [{"id": <long>, "lat": <float>, "lon": <float>, "alt": <float>}, ...],
      "edges":    [{"source": <long>, "target": <long>, "distance": <float>,
                    "slope": <float>, "highway": <str>}, ...]
    }

The plot mirrors what would appear in a paper: a two-panel figure showing
the histogram of |slope| in percent grade and the empirical CDF, with
median and 95th-percentile markers. A machine-readable JSON summary is
written alongside.

Fetching the graph once the backend is running:
    curl -s http://localhost:8080/status/graph/ -o graph.json

Usage:
    python SlopeDistribution.py --graph graph.json [--out DIR] [--label NAME]
"""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load_edges(path: Path):
    with open(path, "r") as f:
        payload = json.load(f)
    edges = payload.get("edges", [])
    slopes = np.fromiter(
        (float(e["slope"]) for e in edges if e.get("distance", 0) > 0),
        dtype=float,
    )
    distances = np.fromiter(
        (float(e["distance"]) for e in edges if e.get("distance", 0) > 0),
        dtype=float,
    )
    highways = np.array(
        [e.get("highway") or "" for e in edges if e.get("distance", 0) > 0],
        dtype=object,
    )
    return slopes, distances, highways


def summarise(slopes_pct: np.ndarray, distances_m: np.ndarray) -> dict:
    abs_pct = np.abs(slopes_pct)
    total_len = float(distances_m.sum())
    if total_len > 0:
        weights = distances_m / total_len
        length_weighted_mean_abs = float((abs_pct * weights).sum())
    else:
        length_weighted_mean_abs = float("nan")

    return {
        "n_edges": int(len(slopes_pct)),
        "total_length_km": total_len / 1000.0,
        "mean_signed_pct": float(np.mean(slopes_pct)),
        "std_signed_pct": float(np.std(slopes_pct)),
        "mean_abs_pct": float(np.mean(abs_pct)),
        "median_abs_pct": float(np.median(abs_pct)),
        "length_weighted_mean_abs_pct": length_weighted_mean_abs,
        "percentiles_abs_pct": {
            f"p{p}": float(np.percentile(abs_pct, p)) for p in (50, 75, 90, 95, 99)
        },
        "max_abs_pct": float(np.max(abs_pct)),
        "share_gt_3pct": float(np.mean(abs_pct > 3.0)),
        "share_gt_6pct": float(np.mean(abs_pct > 6.0)),
        "share_gt_10pct": float(np.mean(abs_pct > 10.0)),
    }


def plot_distribution(slopes_pct: np.ndarray, stats: dict, out_png: Path,
                      title: str | None = None) -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.linewidth": 0.8,
        "figure.dpi": 100,
        "savefig.dpi": 300,
    })

    abs_pct = np.abs(slopes_pct)
    display_max = float(min(np.percentile(abs_pct, 99.5), 40.0))

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), constrained_layout=True)

    ax = axes[0]
    ax.hist(abs_pct, bins=60, range=(0.0, display_max),
            color="0.35", edgecolor="white", linewidth=0.3)
    ax.axvline(stats["median_abs_pct"], color="C0", linestyle="--", linewidth=0.9,
               label=f"median = {stats['median_abs_pct']:.2f}%")
    ax.axvline(stats["percentiles_abs_pct"]["p95"], color="C3", linestyle="--",
               linewidth=0.9,
               label=f"95th pct = {stats['percentiles_abs_pct']['p95']:.2f}%")
    ax.set_xlabel(r"Edge slope $|s|$ (%)")
    ax.set_ylabel("Number of edges")
    ax.set_xlim(0.0, display_max)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="upper right", frameon=False)
    ax.set_title("(a) Distribution")

    ax = axes[1]
    xs = np.sort(abs_pct)
    ys = np.arange(1, len(xs) + 1) / len(xs)
    ax.plot(xs, ys, color="0.15", linewidth=1.0)
    for pct, colour in ((50, "C0"), (95, "C3")):
        x = stats["median_abs_pct"] if pct == 50 else stats["percentiles_abs_pct"][f"p{pct}"]
        ax.axvline(x, color=colour, linestyle="--", linewidth=0.8)
        ax.axhline(pct / 100.0, color=colour, linestyle=":", linewidth=0.6)
    ax.set_xlabel(r"Edge slope $|s|$ (%)")
    ax.set_ylabel("Cumulative share of edges")
    ax.set_xlim(0.0, display_max)
    ax.set_ylim(0.0, 1.0)
    ax.grid(True, alpha=0.3)
    ax.set_title("(b) Empirical CDF")

    if title:
        fig.suptitle(title, fontsize=11)

    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--graph", type=Path, required=True,
                        help="Path to the JSON dump from GET /status/graph/.")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent,
                        help="Output directory for the PNG and summary JSON.")
    parser.add_argument("--label", type=str, default=None,
                        help="Optional short label included in the figure title "
                             "and in the output filenames (e.g., dataset name).")
    args = parser.parse_args()

    if not args.graph.exists():
        raise FileNotFoundError(f"graph JSON not found: {args.graph}")

    print(f"Loading graph: {args.graph}")
    slopes_frac, distances_m, _ = load_edges(args.graph)
    print(f"  {len(slopes_frac):,} edges with distance > 0")

    if len(slopes_frac) == 0:
        raise SystemExit("No usable edges in the graph JSON.")

    slopes_pct = slopes_frac * 100.0
    stats = summarise(slopes_pct, distances_m)

    print("\nSummary:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    args.out.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.label}" if args.label else ""
    stem = args.graph.stem
    png_path = args.out / f"slope_distribution_{stem}{suffix}.png"
    json_path = args.out / f"slope_distribution_{stem}{suffix}.json"

    title = f"Edge slope distribution (n = {stats['n_edges']:,})"
    if args.label:
        title = f"{args.label} — {title}"
    plot_distribution(slopes_pct, stats, png_path, title=title)

    with open(json_path, "w") as f:
        json.dump(
            {"config": {"graph": str(args.graph), "label": args.label},
             "stats": stats},
            f, indent=2,
        )

    print(f"\nWrote {png_path}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
