"""
Routes Analysis — Spatial Inequality & Comparison Pipeline
Converted from routes_analysis_v13_clean.ipynb

Pipeline:
1. Data Loading         — Load preprocessed routes from processing_json_files_v4
2. Hex Grid Aggregation — Generate hexagonal grids and count routes per cell
3. Metrics Computation  — Pairwise divergence, inequality (Gini/entropy), Moran's I, variograms
4. Spatial Analysis     — Absolute counts, ratio maps, LISA clusters
5. Pairwise Comparison  — Discrete Fréchet Distance heatmaps
6. Inequality Analysis  — Lorenz curves (deterministic + bootstrap)

Cache behaviour:
  - If data/all_results_hex_grids_v4.pkl exists, metrics are loaded (not recomputed).
  - If data/route_counts_dict.pkl exists, hex aggregation is loaded (not recomputed).
  - If data/zurich_network.graphml exists, the OSM road network is loaded (not re-downloaded).
"""

# =============================================================================
# 1. IMPORTS & CONFIGURATION
# =============================================================================

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patches as mpatches
import seaborn as sns
import contextily as cx
import osmnx as ox
import math
import re
import pickle
import time
import itertools
import warnings
import sys
import os

from shapely.geometry import Polygon, LineString
from scipy.spatial.distance import jensenshannon, cosine, euclidean, cdist
from scipy.stats import wasserstein_distance
from scipy import interpolate, sparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from sklearn.linear_model import LinearRegression
from matplotlib.colors import LogNorm, Normalize, TwoSlopeNorm
from matplotlib.patches import Patch
from matplotlib_scalebar.scalebar import ScaleBar
from skgstat import Variogram
from esda.moran import Moran
from esda import Moran_Local
from libpysal.weights import Queen
import libpysal
import statsmodels.api as sm
from joblib import Parallel, delayed
from numba import jit
from typing import Dict, Tuple, Any
from mgwr.gwr import GWR
from mgwr.sel_bw import Sel_BW

# --- Font & Style ---
from matplotlib import font_manager

# Helvetica is proprietary and cannot be redistributed.
# If you have a licensed copy, place it at data/Helvetica.ttc and it will be
# loaded automatically. Otherwise the fallback chain below is used instead,
# which produces visually identical output on most systems.
font_path = "data/Helvetica.ttc"
if os.path.exists(font_path):
    font_manager.fontManager.addfont(font_path)
    sans_serif_fonts = ["Helvetica"]
else:
    sans_serif_fonts = ["Helvetica Neue", "Arial", "Liberation Sans", "DejaVu Sans"]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": sans_serif_fonts,
    "figure.dpi": 450,
})

# --- Color Palette & Visual Constants ---
hex_colors = {
    'routing_mode_distance': '#bc1530',
    'routing_mode_slope':    '#236bbf',
    'routing_mode_green':    '#1bd39b',
    'routing_mode_noise':    '#840087',
    'routing_mode_air':      '#feb40a',
    'routing_mode_ors':      '#8e8071',
    'combined_alt':          '#000000'
}

linestyles = {
    "routing_mode_air":      "solid",
    "routing_mode_distance": "dashed",
    "routing_mode_green":    "dashdot",
    "routing_mode_noise":    "dotted",
    "routing_mode_slope":    (0, (3, 5, 1, 5)),
    "routing_mode_ors":      "solid",
    "combined_alt":          "--"
}

markers = {
    "routing_mode_air":      "X",
    "routing_mode_distance": "s",
    "routing_mode_green":    "^",
    "routing_mode_noise":    "D",
    "routing_mode_slope":    "v",
    "routing_mode_ors":      "o"
}

# --- Module-level constants used across LISA and plot functions ---
TRANSPORT_MODES = ['cycle', 'drive', 'walk']
ROUTING_MODES   = ['air', 'distance', 'green', 'noise', 'slope']
ALL_METRICS     = ROUTING_MODES + ['ors']


# =============================================================================
# 2. HEX GRID AGGREGATION
# =============================================================================

def create_hexagon(center, size):
    angle = math.pi / 3
    return Polygon([
        (center[0] + size * math.cos(i * angle),
         center[1] + size * math.sin(i * angle))
        for i in range(6)
    ])


def create_hexagonal_grid(bounds, cell_diameter):
    side_length = cell_diameter / math.sqrt(3)
    horiz_spacing = 1.5 * side_length
    vert_spacing = math.sqrt(3) * side_length
    min_x, min_y, max_x, max_y = bounds
    num_columns = int(math.ceil((max_x - min_x) / horiz_spacing)) + 1
    num_rows    = int(math.ceil((max_y - min_y) / vert_spacing)) + 1
    hexagons = []
    for row in range(num_rows):
        for col in range(num_columns):
            x_offset = min_x + horiz_spacing * col
            y_offset = min_y + vert_spacing * (row + 0.5 * (col % 2))
            hexagons.append(create_hexagon((x_offset, y_offset), side_length))
    return gpd.GeoDataFrame(geometry=hexagons, crs="EPSG:2056")


def crop_hex_grid_to_roads(hex_grid, gdf_links):
    gdf_links_projected = gdf_links.to_crs(hex_grid.crs)
    hex_with_links = gpd.sjoin(hex_grid, gdf_links_projected, how='inner', predicate='intersects')
    cols_to_drop = [col for col in ['u', 'v', 'key', 'index_right'] if col in hex_with_links.columns]
    hex_with_links = hex_with_links.drop(columns=cols_to_drop, errors='ignore')
    return hex_with_links.drop_duplicates(subset=['geometry'])


def generate_hex_grids_for_sizes(gdf_routes, gdf_links, size_range):
    gdf_routes_projected = gdf_routes.to_crs(epsg=2056)
    bounds_projected = gdf_routes_projected.total_bounds
    hex_grids = {}
    for size in size_range:
        print(f"  Generating grid for cell size: {size} m")
        hex_grid = create_hexagonal_grid(bounds_projected, size)
        hex_grid_filtered = crop_hex_grid_to_roads(hex_grid, gdf_links)
        hex_grid_filtered = hex_grid_filtered.to_crs(gdf_routes_projected.crs)
        hex_grids[size] = hex_grid_filtered
    return hex_grids


def count_routes_per_cell(gdf_routes, hex_grid):
    gdf_routes_proj = gdf_routes.to_crs(hex_grid.crs).copy()
    joined = gpd.sjoin(gdf_routes_proj, hex_grid, predicate='intersects')
    counts = (
        joined
        .groupby([
            joined.index.get_level_values('transport_mode'),
            joined.index.get_level_values('routing_mode'),
            'index_right'
        ])
        .size()
        .reset_index(name='count')
    )
    pivot_df = counts.pivot(
        index='index_right',
        columns=['transport_mode', 'routing_mode'],
        values='count'
    ).fillna(0)
    pivot_df.columns = ['_'.join(col).strip() for col in pivot_df.columns.values]
    pivot_df.sort_index(axis=1, inplace=True)
    result_gdf = hex_grid.merge(pivot_df, left_index=True, right_index=True, how='left')
    result_gdf.fillna(0, inplace=True)
    return result_gdf


def _count_for_size(size, gdf_routes, grid):
    print(f"  → Processing {size} m grid...")
    result = count_routes_per_cell(gdf_routes, grid)
    print(f"  ✓ Done with {size} m grid.")
    return size, result


def count_routes_for_all_sizes_parallel(gdf_routes, hex_grid_dict, max_workers=None):
    results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_count_for_size, size, gdf_routes, grid): size
            for size, grid in hex_grid_dict.items()
        }
        for future in as_completed(futures):
            size, result = future.result()
            results[size] = result
    return results


# =============================================================================
# 3. PROCESSING & ANALYSIS FUNCTIONS
# =============================================================================

# --- 3.1 Distribution Comparison & Inequality Metrics ---

def normalize_distribution(values):
    arr = np.array(values, dtype=float)
    total = arr.sum()
    return arr / total if total > 0 else np.zeros_like(arr, dtype=float)


def compute_hotspot_overlap(p, q, topk=0.01):
    n = len(p)
    k = max(1, int(n * topk))
    topA = set(np.argpartition(p, -k)[-k:])
    topB = set(np.argpartition(q, -k)[-k:])
    inter = len(topA & topB)
    union = len(topA | topB)
    jaccard = inter / union if union > 0 else 0.0
    overlap_pct = inter / len(topA) if len(topA) > 0 else 0.0
    return jaccard, overlap_pct


def compare_two_distributions(p, q, coords=None, hotspot_levels=(0.01, 0.05)):
    jsd     = jensenshannon(p, q)
    cos     = 1 - cosine(p, q)
    l1      = np.sum(np.abs(p - q))
    l2      = euclidean(p, q)
    overlap = np.sum(np.minimum(p, q))
    if coords is None:
        emd = wasserstein_distance(np.arange(len(p)), np.arange(len(p)), p, q)
    else:
        emd = wasserstein_distance(coords, coords, p, q)
    hotspot_results = {}
    for frac in hotspot_levels:
        jaccard, overlap_pct = compute_hotspot_overlap(p, q, topk=frac)
        hotspot_results[f"hotspot_jaccard_top{int(frac*100)}"] = jaccard
        hotspot_results[f"hotspot_overlap_top{int(frac*100)}"]  = overlap_pct
    return {
        "js_divergence": jsd, "cosine_similarity": cos,
        "l1_distance": l1,    "l2_distance": l2,
        "wasserstein_distance": emd, "overlap_share": overlap,
        **hotspot_results
    }


def gini_coefficient(x):
    x = np.array(x, dtype=np.float64)
    if np.any(x < 0): raise ValueError("Values cannot be negative")
    if np.all(x == 0): return 0.0
    sorted_x = np.sort(x)
    n = len(x)
    cumx = np.cumsum(sorted_x)
    return (n + 1 - 2 * np.sum(cumx) / cumx[-1]) / n


def shannon_entropy(x):
    x = np.array(x, dtype=np.float64)
    if np.any(x < 0): raise ValueError("Values cannot be negative")
    total = np.sum(x)
    if total == 0: return 0.0
    p = x / total
    p = p[p > 0]
    return -np.sum(p * np.log2(p))


def compare_routing_methods(gdf_counts, coords=None):
    results = []
    cols   = gdf_counts.columns.drop("geometry") if "geometry" in gdf_counts else gdf_counts.columns
    parsed = [c.split("_routing_mode_") for c in cols]
    tm_to_cols = {}
    for tmode, rmode in parsed:
        tm_to_cols.setdefault(tmode.replace("transport_mode_", ""), []).append(
            (rmode, f"{tmode}_routing_mode_{rmode}")
        )
    for tmode, rcols in tm_to_cols.items():
        for i in range(len(rcols)):
            rmodeA, colA = rcols[i]
            pA = normalize_distribution(gdf_counts[colA].values)
            for j in range(i + 1, len(rcols)):
                rmodeB, colB = rcols[j]
                pB = normalize_distribution(gdf_counts[colB].values)
                metrics = compare_two_distributions(pA, pB, coords=coords)
                results.append({"transport_mode": tmode, "routing_mode_A": rmodeA,
                                 "routing_mode_B": rmodeB, **metrics})
    return pd.DataFrame(results)


def compute_gini_entropy_with_ors_diff(df):
    pattern = re.compile(r"transport_mode_(\w+)_routing_mode_(\w+)$")
    results = []
    target_cols = [col for col in df.columns if pattern.match(col)]
    for col in target_cols:
        match = pattern.match(col)
        transport_mode, routing_mode = match.groups()
        values = df[col].fillna(0).to_numpy()
        results.append({
            "transport_mode": transport_mode,
            "routing_mode":   routing_mode,
            "gini":           gini_coefficient(values),
            "entropy":        shannon_entropy(values)
        })
    metrics_df = pd.DataFrame(results)
    ors_baseline_gini    = metrics_df[metrics_df["routing_mode"] == "ors"].set_index("transport_mode")["gini"]
    ors_baseline_entropy = metrics_df[metrics_df["routing_mode"] == "ors"].set_index("transport_mode")["entropy"]
    metrics_df["gini_diff_vs_ors"]    = metrics_df.apply(
        lambda row: row["gini"]    - ors_baseline_gini.get(row["transport_mode"], np.nan), axis=1)
    metrics_df["entropy_diff_vs_ors"] = metrics_df.apply(
        lambda row: row["entropy"] - ors_baseline_entropy.get(row["transport_mode"], np.nan), axis=1)
    return metrics_df


def compute_moran(gdf_counts, col, max_dist=3000, crs=2056, permutations=999):
    gdf_proj = gdf_counts.to_crs(crs)
    coords = np.column_stack((gdf_proj.geometry.centroid.x, gdf_proj.geometry.centroid.y))
    w = libpysal.weights.DistanceBand(coords, threshold=max_dist, binary=False, alpha=-1)
    w.transform = "r"
    y = gdf_proj[col].values
    mi = Moran(y, w, permutations=permutations)
    return {"I": mi.I, "p_sim": mi.p_sim}


def compute_moran_for_all_modes(gdf, n_lags=10, max_dist=None, permutations=99):
    results = []
    cols = [c for c in gdf.columns if c != "geometry"]
    w = libpysal.weights.DistanceBand.from_dataframe(gdf, threshold=max_dist or 3000, silence_warnings=True)
    for col in cols:
        values = gdf[col].fillna(0).values
        mi = Moran(values, w, permutations=permutations)
        results.append({
            "column": col, "moran_I": mi.I, "p_value": mi.p_sim,
            "expected_I": mi.EI, "z_score": mi.z_sim, "permutations": permutations
        })
    return pd.DataFrame(results)


def compute_variogram_for_all_modes(gdf, n_lags=10, max_dist=None):
    results = []
    coords = np.array(list(zip(gdf.geometry.centroid.x, gdf.geometry.centroid.y)))
    cols   = [c for c in gdf.columns if c != "geometry"]
    for col in cols:
        values = gdf[col].fillna(0).values
        V = Variogram(coords, values, n_lags=n_lags, maxlag=max_dist, normalize=True, use_nugget=True)
        df = pd.DataFrame({"lag": V.bins, "semivariance": V.experimental,
                           "model": V.model, "column": col})
        results.append(df)
    return pd.concat(results, ignore_index=True)


def compute_spatial_autocorrelation_metrics_for_all_sizes(
        route_counts_dict, method="moran", n_lags=10, max_dist=None,
        permutations=99, crs=2056):
    results = {}
    for size, gdf in route_counts_dict.items():
        print(f"  → Computing {method} for {size} m grid...")
        gdf_proj = gdf.to_crs(crs)
        if method == "moran":
            results[size] = compute_moran_for_all_modes(
                gdf_proj, n_lags=n_lags, max_dist=max_dist, permutations=permutations)
        elif method == "variogram":
            results[size] = compute_variogram_for_all_modes(gdf_proj, n_lags=n_lags, max_dist=max_dist)
        else:
            raise ValueError("method must be 'moran' or 'variogram'")
        print(f"  ✓ Done with {size} m grid.")
    return results


def run_spatial_autocorrelation_parallel(route_counts_dict, method, **kwargs):
    results = {}
    with ProcessPoolExecutor() as executor:
        futures = {
            executor.submit(
                compute_spatial_autocorrelation_metrics_for_all_sizes,
                {size: gdf}, method=method, **kwargs
            ): size for size, gdf in route_counts_dict.items()
        }
        for future in as_completed(futures):
            size = futures[future]
            try:
                result = future.result()
                results[size] = result[size]
            except Exception as e:
                print(f"  ⚠️ Error computing {method} for {size}: {e}")
    return results


def compute_all_metrics_for_size(size, gdf_counts, crs=2056):
    gdf_proj = gdf_counts.to_crs(crs)
    coords   = gdf_proj.geometry.centroid.x.values
    pairwise   = compare_routing_methods(gdf_proj, coords=coords)
    inequality = compute_gini_entropy_with_ors_diff(gdf_proj)
    return {"pairwise": pairwise, "inequality": inequality}


def compute_all_metrics_master(
        route_counts_dict, crs=2056, max_workers=None, use_gpu=False,
        gpu_kwargs=None, moran_kwargs=None, variogram_kwargs=None):
    moran_kwargs     = moran_kwargs     or {"max_dist": 3000, "permutations": 999, "crs": crs}
    variogram_kwargs = variogram_kwargs or {"n_lags": 12, "max_dist": 3000, "crs": crs}
    gpu_kwargs       = gpu_kwargs       or {"max_dist": 3000, "n_lags": 12, "crs": crs}

    print("🔹 Running pairwise, inequality, Moran, and variogram analyses...")
    results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(compute_all_metrics_for_size, size, gdf, crs): size
                   for size, gdf in route_counts_dict.items()}
        for future in as_completed(futures):
            size = futures[future]
            results[size] = future.result()
            print(f"  ✓ Base metrics done for {size} m")

    print("⚙️ Running CPU-based spatial autocorrelation...")
    moran_results     = run_spatial_autocorrelation_parallel(route_counts_dict, method="moran",     **moran_kwargs)
    variogram_results = run_spatial_autocorrelation_parallel(route_counts_dict, method="variogram", **variogram_kwargs)

    full_results = {
        size: {
            "pairwise":   results[size]["pairwise"],
            "inequality": results[size]["inequality"],
            "moran":      moran_results.get(size, []),
            "variogram":  variogram_results.get(size, [])
        }
        for size in route_counts_dict.keys()
    }
    print("✅ All metrics computed.")
    return full_results


# --- 3.4 Hex Metrics: Differences & Ratios vs ORS ---

def calculate_hex_metrics_diffs(gdf, epsilon=1):
    gdf = gdf.copy()
    transport_modes = ['cycle', 'drive', 'walk']
    routing_modes   = ['air', 'distance', 'green', 'noise', 'slope']
    baseline        = 'ors'
    for tmode in transport_modes:
        base_col = f'transport_mode_{tmode}_routing_mode_{baseline}'
        if base_col not in gdf.columns:
            print(f"Warning: Missing baseline column {base_col}. Skipping.")
            continue
        for rmode in routing_modes:
            alt_col = f'transport_mode_{tmode}_routing_mode_{rmode}'
            if alt_col not in gdf.columns:
                print(f"Warning: Missing comparison column {alt_col}. Skipping.")
                continue
            gdf[f'{alt_col}_diff_vs_{baseline}']  = gdf[alt_col] - gdf[base_col]
            gdf[f'{alt_col}_ratio_vs_{baseline}'] = (gdf[alt_col] + epsilon) / (gdf[base_col] + epsilon)
    return gdf


# =============================================================================
# 4. VISUALIZATION FUNCTIONS
# =============================================================================

# --- 4.1 Pairwise Metrics Evolution ---

def prepare_pairwise_summary(pairwise_metrics_dict, metrics, transport_modes, baseline="ors"):
    records = []
    for cell_size, df in sorted(pairwise_metrics_dict.items()):
        for metric in metrics:
            for tmode in transport_modes:
                df_tm = df[df["transport_mode"] == tmode]
                df_tm = df_tm[(df_tm["routing_mode_A"] == baseline) | (df_tm["routing_mode_B"] == baseline)]
                for _, row in df_tm.iterrows():
                    other = row["routing_mode_B"] if row["routing_mode_A"] == baseline else row["routing_mode_A"]
                    records.append({
                        "cell_size": cell_size, "transport_mode": tmode,
                        "other_mode": other, "metric": metric, "value": row[metric]
                    })
    return pd.DataFrame(records)


def plot_pairwise_metrics(pairwise_metrics_dict, transport_modes=["walk", "cycle", "drive"],
                          hex_colors=None, log=False, set_xlim=None, baseline="ors"):
    sample_df  = next(iter(pairwise_metrics_dict.values()))
    metric_cols = [c for c in sample_df.columns
                   if c not in ["transport_mode", "routing_mode_A", "routing_mode_B"]]
    if hex_colors is None:
        hex_colors = {
            'routing_mode_distance': '#bc1530', 'routing_mode_slope': '#236bbf',
            'routing_mode_green': '#1bd39b',    'routing_mode_noise': '#840087',
            'routing_mode_air': '#feb40a',       'routing_mode_ors': '#8e8071'
        }
    df_long = prepare_pairwise_summary(pairwise_metrics_dict, metric_cols, transport_modes, baseline)
    fig, axes = plt.subplots(len(transport_modes), len(metric_cols),
                              figsize=(5 * len(metric_cols), 4 * len(transport_modes)), sharex=True)
    if len(transport_modes) == 1: axes = np.expand_dims(axes, 0)
    if len(metric_cols) == 1:     axes = np.expand_dims(axes, 1)
    for i, tmode in enumerate(transport_modes):
        for j, metric in enumerate(metric_cols):
            ax = axes[i, j]
            df_plot = df_long[(df_long["transport_mode"] == tmode) & (df_long["metric"] == metric)].sort_values("cell_size")
            palette = {mode: hex_colors.get(f"routing_mode_{mode}", "#333333") for mode in df_plot["other_mode"].unique()}
            sns.lineplot(data=df_plot, x="cell_size", y="value", hue="other_mode",
                         palette=palette, marker="o", ax=ax, legend=False)
            ax.set_title(f"{tmode.capitalize()} — {metric.replace('_', ' ')}")
            ax.set_xlabel("Hex cell size (m)")
            ax.set_ylabel(metric.replace("_", " ").capitalize())
            if log: ax.set_xscale("log")
            if set_xlim is not None: ax.set_xlim(set_xlim)
    unique_modes = df_long["other_mode"].unique()
    handles = [plt.Line2D([0], [0], color=hex_colors.get(f"routing_mode_{mode}", "#333333"), marker='o', linestyle='-')
               for mode in unique_modes]
    fig.legend(handles, unique_modes, loc='lower center', ncol=len(unique_modes),
               frameon=False, title=f"Routing mode vs {baseline.upper()}")
    plt.tight_layout(rect=[0, 0.08, 1, 1])
    plt.savefig("figs/pairwise_metrics.png", dpi=450, bbox_inches="tight")
    plt.show()


# --- 4.2 Inequality, Moran's I, and Variogram Plots ---

def plot_inequality_metrics(inequality_metrics_dict, transport_modes,
                            metrics=["gini_diff_vs_ors", "entropy_diff_vs_ors"],
                            hex_colors=None, log=True, set_xlim=None):
    df_list = []
    for cell_size, df in sorted(inequality_metrics_dict.items()):
        df_ = df.copy(); df_["cell_size"] = cell_size; df_list.append(df_)
    df_long = pd.concat(df_list)
    fig, axes = plt.subplots(len(transport_modes), len(metrics),
                              figsize=(5 * len(metrics), 4 * len(transport_modes)), sharex=True)
    if len(transport_modes) == 1: axes = np.expand_dims(axes, 0)
    if len(metrics) == 1:         axes = np.expand_dims(axes, 1)
    for i, tmode in enumerate(transport_modes):
        for j, metric in enumerate(metrics):
            ax = axes[i, j]
            df_plot = df_long[df_long["transport_mode"] == tmode]
            palette = ({row["routing_mode"]: hex_colors.get(f"routing_mode_{row['routing_mode']}", "#333333")
                        for _, row in df_plot.iterrows()} if hex_colors else None)
            sns.lineplot(data=df_plot, x="cell_size", y=metric, hue="routing_mode",
                         palette=palette, marker="o", ax=ax, legend=False)
            ax.set_title(f"{tmode.capitalize()} — {metric.replace('_', ' ')}")
            ax.set_xlabel("Hex cell size (m)")
            ax.set_ylabel(metric.replace("_", " ").capitalize())
        if log: ax.set_xscale("log")
        if set_xlim is not None: ax.set_xlim(set_xlim)
    if hex_colors:
        unique_modes = df_long["routing_mode"].unique()
        handles = [plt.Line2D([0], [0], color=hex_colors[f"routing_mode_{mode}"], marker='o', linestyle='-')
                   for mode in unique_modes]
        fig.legend(handles, unique_modes, loc='lower center', ncol=len(unique_modes), frameon=False)
    plt.tight_layout(rect=[0, 0.08, 1, 1])
    plt.savefig("figs/inequality_metrics.png", dpi=450, bbox_inches="tight")
    plt.show()


def plot_moran_metrics_dual(moran_results_dict, transport_modes=["walk", "cycle", "drive"],
                             hex_colors=None, log=False, set_xlim=None, baseline="ors"):
    df_list = []
    for cell_size, df in sorted(moran_results_dict.items()):
        if not isinstance(df, pd.DataFrame): continue
        df_ = df.copy(); df_["cell_size"] = cell_size
        if "column" in df_.columns:
            parts = df_["column"].str.extract(
                r"transport_mode_(?P<transport_mode>\w+)_routing_mode_(?P<routing_mode>\w+)")
            df_ = pd.concat([df_, parts], axis=1)
        if "moran_I" in df_.columns: df_.rename(columns={"moran_I": "I"}, inplace=True)
        df_list.append(df_)
    if not df_list:
        raise ValueError("No valid Moran's I results found.")
    df_long = pd.concat(df_list, ignore_index=True)
    if hex_colors is None:
        hex_colors = {
            "routing_mode_distance": "#bc1530", "routing_mode_slope": "#236bbf",
            "routing_mode_green": "#1bd39b",    "routing_mode_noise": "#840087",
            "routing_mode_air": "#feb40a",       "routing_mode_ors": "#8e8071"
        }
    fig, axes = plt.subplots(len(transport_modes), 2, figsize=(12, 4 * len(transport_modes)), sharex=True)
    if len(transport_modes) == 1: axes = np.expand_dims(axes, 0)
    for i, tmode in enumerate(transport_modes):
        df_plot = df_long[df_long["transport_mode"] == tmode].sort_values("cell_size")
        if df_plot.empty: continue
        unique_modes = df_plot["routing_mode"].unique()
        palette = {mode: hex_colors.get(f"routing_mode_{mode}", "#333333") for mode in unique_modes}
        for col_idx, (metric, ylabel) in enumerate([("I", "Moran's I"), ("z_score", "z-score (significance)")]):
            sns.lineplot(data=df_plot, x="cell_size", y=metric, hue="routing_mode",
                         palette=palette, marker="o", ax=axes[i, col_idx], legend=False)
            axes[i, col_idx].set_title(f"{tmode.capitalize()} — {ylabel}")
            axes[i, col_idx].set_ylabel(ylabel)
            axes[i, col_idx].set_xlabel("Hex cell size (m)")
            if log: axes[i, col_idx].set_xscale("log")
            if set_xlim is not None: axes[i, col_idx].set_xlim(set_xlim)
        axes[i, 1].axhline(0,    color="grey",  lw=1, linestyle="--")
        axes[i, 1].axhline(1.96, color="green", lw=1, linestyle=":", label="p<0.05")
        axes[i, 1].axhline(-1.96, color="green", lw=1, linestyle=":")
    handles = [plt.Line2D([0], [0], color=hex_colors.get(f"routing_mode_{mode}", "#333333"), marker="o", linestyle="-")
               for mode in unique_modes]
    fig.legend(handles, unique_modes, loc="lower center", ncol=len(unique_modes),
               frameon=False, title=f"Routing mode vs {baseline.upper()}")
    plt.tight_layout(rect=[0, 0.08, 1, 1])
    plt.savefig("figs/moran_metrics.png", dpi=450, bbox_inches="tight")
    plt.show()


# --- 4.3 Map Visualization Functions ---

def plot_absolute_counts(gdf, figsize=(18, 30), cmap='viridis', log_scale=True,
                         water_gdf=None, add_basemap=True,
                         basemap_provider=cx.providers.CartoDB.Positron, add_scalebar=True):
    if water_gdf is not None: water_gdf = water_gdf.to_crs(gdf.crs)
    transport_modes = ['cycle', 'drive', 'walk']
    routing_modes   = ['ors', 'air', 'distance', 'green', 'noise', 'slope']
    all_values = []
    for tmode in transport_modes:
        for rmode in routing_modes:
            col = f'transport_mode_{tmode}_routing_mode_{rmode}'
            if col in gdf.columns:
                vals = gdf[col].replace([np.inf, -np.inf], np.nan).dropna()
                if log_scale: vals = vals[vals > 0]
                all_values.append(vals)
    if not all_values: raise ValueError("No valid routing columns found in GeoDataFrame.")
    all_values = pd.concat(all_values)
    norm = LogNorm(vmin=all_values.min(), vmax=all_values.max()) if log_scale \
        else Normalize(vmin=0, vmax=all_values.max())
    fig, axes = plt.subplots(nrows=6, ncols=3, figsize=figsize)
    fig.subplots_adjust(hspace=0.1, wspace=0.05)
    for i, routing_mode in enumerate(routing_modes):
        for j, transport_mode in enumerate(transport_modes):
            col_name = f'transport_mode_{transport_mode}_routing_mode_{routing_mode}'
            ax = axes[i, j]
            if col_name in gdf.columns:
                gdf.plot(column=col_name, ax=ax, cmap=cmap, norm=norm, legend=False, alpha=0.8)
                if add_basemap:
                    cx.add_basemap(ax, crs=gdf.crs.to_string(), source=basemap_provider, attribution='')
                if water_gdf is not None:
                    water_gdf.plot(ax=ax, color="grey", edgecolor='none', alpha=0.5)
                if add_scalebar:
                    ax.add_artist(ScaleBar(0.001, 'km', fixed_value=1, location='lower center',
                                           pad=0.5, frameon=False, color='black',
                                           font_properties={'size': 8}))
            else:
                ax.set_facecolor('lightgray')
                ax.text(0.5, 0.5, 'N/A', ha='center', va='center', transform=ax.transAxes)
            ax.set_axis_off()
            if i == 0: ax.set_title(transport_mode.capitalize(), fontsize=16, pad=20)
            if j == 0:
                ax.annotate(
                    routing_mode.capitalize() if routing_mode != 'ors' else 'ORS (Baseline)',
                    xy=(0, 0.5), xycoords='axes fraction', fontsize=14, ha='right', va='center',
                    rotation=90, xytext=(-15, 0), textcoords='offset points', fontweight='bold')
    cax = fig.add_axes([0.92, 0.2, 0.02, 0.6])
    sm  = plt.cm.ScalarMappable(cmap=cmap, norm=norm); sm._A = []
    cbar = fig.colorbar(sm, cax=cax, orientation='vertical')
    cbar.set_label('Count of Routes (Log Scale)' if log_scale else 'Count of Routes',
                   labelpad=10, fontsize=12)
    plt.subplots_adjust(bottom=0.12); plt.tight_layout()
    plt.savefig("figs/absolute_counts.png", dpi=450, bbox_inches="tight")
    plt.show()


def plot_ratios_vs_ors(gdf, column_suffix='ratio_vs_ors', figsize=(18, 25), cmap='bwr',
                       log_scale=False, water_gdf=None, add_basemap=True,
                       basemap_provider=cx.providers.CartoDB.Positron, add_scalebar=True):
    if water_gdf is not None: water_gdf = water_gdf.to_crs(gdf.crs)
    transport_modes = ['cycle', 'drive', 'walk']
    routing_modes   = ['air', 'distance', 'green', 'noise', 'slope']
    all_values = []
    for tmode in transport_modes:
        for rmode in routing_modes:
            col = f'transport_mode_{tmode}_routing_mode_{rmode}_{column_suffix}'
            if col in gdf.columns:
                vals = gdf[col].replace([np.inf, -np.inf], np.nan)
                if log_scale: vals = np.log10(vals[vals > 0])
                all_values.append(vals.dropna())
    if not all_values: raise ValueError("No valid ratio columns found.")
    all_values = pd.concat(all_values)
    if log_scale:
        vmin = np.floor(all_values.min()); vmax = np.ceil(all_values.max())
        norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)
    else:
        vmin = max(0, all_values.min()); vmax = all_values.max()
        norm = TwoSlopeNorm(vmin=vmin, vcenter=1, vmax=vmax)
    fig, axes = plt.subplots(nrows=5, ncols=3, figsize=figsize)
    fig.subplots_adjust(hspace=0.05, wspace=0.05)
    for i, routing_mode in enumerate(routing_modes):
        for j, transport_mode in enumerate(transport_modes):
            col_name = f'transport_mode_{transport_mode}_routing_mode_{routing_mode}_{column_suffix}'
            ax = axes[i, j]
            if col_name in gdf.columns:
                values = gdf[col_name].replace([np.inf, -np.inf], np.nan)
                if log_scale:
                    gdf_tmp = gdf.copy(); gdf_tmp[col_name + '_log'] = np.log10(values.where(values > 0))
                    plot_col = col_name + '_log'
                else:
                    gdf_tmp = gdf.copy(); plot_col = col_name
                gdf_tmp.plot(column=plot_col, ax=ax, cmap=cmap, norm=norm, legend=False, alpha=0.7)
                if add_basemap:
                    cx.add_basemap(ax, crs=gdf.crs.to_string(), source=basemap_provider, attribution='')
                if water_gdf is not None:
                    water_gdf.plot(ax=ax, color="grey", edgecolor='none', alpha=0.5)
                if add_scalebar:
                    ax.add_artist(ScaleBar(0.001, 'km', fixed_value=1, location='lower center',
                                           pad=0.5, frameon=False, color='black',
                                           font_properties={'size': 8}))
            else:
                ax.set_facecolor('lightgray')
                ax.text(0.5, 0.5, 'N/A', ha='center', va='center', transform=ax.transAxes)
            ax.set_axis_off()
            if i == 0: ax.set_title(transport_mode.capitalize(), fontsize=12)
            if j == 0:
                ax.annotate(routing_mode.capitalize(), xy=(0, 0.5), xycoords='axes fraction',
                            fontsize=12, ha='right', va='center', rotation=90,
                            xytext=(-10, 0), textcoords='offset points')
    cax = fig.add_axes([0.25, -0.01, 0.5, 0.015])
    sm  = plt.cm.ScalarMappable(cmap=cmap, norm=norm); sm._A = []
    cbar = fig.colorbar(sm, cax=cax, orientation='horizontal')
    cbar.set_label(f'Log-scaled {column_suffix.replace("_", " ").title()}', labelpad=10)
    plt.tight_layout()
    plt.savefig("figs/ratios_vs_ors.png", dpi=450, bbox_inches="tight")
    plt.show()


# --- 4.4 LISA Cluster Analysis ---

def compute_lisa_results(gdf, column_suffix, log_transform=False):
    TRANSPORT_MODES = ['cycle', 'drive', 'walk']
    ROUTING_MODES   = ['air', 'distance', 'green', 'noise', 'slope']
    ALL_METRICS     = ROUTING_MODES + ['ors']
    computed_data   = {}
    summary_results = []
    for transport_mode in TRANSPORT_MODES:
        cols_for_tmode = {
            metric: f'transport_mode_{transport_mode}_routing_mode_{metric}{column_suffix}'
            for metric in ALL_METRICS
        }
        if not all(col in gdf.columns for col in cols_for_tmode.values()):
            computed_data[transport_mode] = {"status": f"Missing Columns for {transport_mode}"}
            continue
        df_temp     = gdf[[gdf.geometry.name] + list(cols_for_tmode.values())].copy()
        master_mask = pd.Series(True, index=df_temp.index)
        for col_name in cols_for_tmode.values():
            data_series = df_temp[col_name].replace([np.inf, -np.inf], np.nan)
            if log_transform: data_series = np.log10(data_series)
            df_temp[col_name] = data_series
            master_mask &= np.isfinite(data_series)
        gdf_common_base = df_temp[master_mask].copy()
        if gdf_common_base.empty:
            computed_data[transport_mode] = {"status": "Empty Data"}
            continue
        try:
            w_common = Queen.from_dataframe(gdf_common_base); w_common.transform = 'r'
        except ValueError as e:
            computed_data[transport_mode] = {"status": "W Error"}
            continue
        for rmode, col_name in ((m, cols_for_tmode[m]) for m in ALL_METRICS):
            y = gdf_common_base[col_name]
            moran_loc = Moran_Local(y, w_common)
            gdf_common_base[f'q_{rmode}']     = moran_loc.q
            gdf_common_base[f'p_sig_{rmode}'] = moran_loc.p_sim < 0.05
            summary_results.append({
                "metric":        col_name,
                "mean_local_I":  np.mean(moran_loc.Is),
                "p_value_min":   np.min(moran_loc.p_sim),
                "high-high":     np.sum(moran_loc.q == 1),
                "low-low":       np.sum(moran_loc.q == 3)
            })
        computed_data[transport_mode] = {"status": "OK", "gdf": gdf_common_base, "w": w_common}
    return computed_data, pd.DataFrame(summary_results)


def compute_lisa_on_residuals(
    gdf: gpd.GeoDataFrame,
    column_suffix: str,
    log_transform: bool = False
) -> Tuple[Dict[str, Dict[str, Any]], pd.DataFrame]:
    """
    Computes LISA (Local Moran's I) on the RESIDUALS of 15 regressions 
    (e.g., Air ~ ORS, Distance ~ ORS) to find "hotspots of unexpected change".
    
    The function now uses statsmodels.api.OLS to calculate and return 
    the full regression summary statistics, including P-values, in the 
    returned DataFrame.
    """
    
    computed_data = {}
    summary_results = []
    
    print(f"Starting LISA on Residuals computation (log_transform={log_transform})...")

    # --- Loop by Transport Mode (e.g., 'cycle', 'drive', 'walk') ---
    for transport_mode in TRANSPORT_MODES:
        
        # 1. Prepare data and find the "master mask" for this transport mode
        cols_for_tmode = {
            metric: f'transport_mode_{transport_mode}_routing_mode_{metric}{column_suffix}'
            for metric in ALL_METRICS
        }
        
        if not all(col in gdf.columns for col in cols_for_tmode.values()):
            print(f"Warning: Missing columns for {transport_mode}. Skipping.")
            computed_data[transport_mode] = {"status": f"Missing Columns"}
            continue

        df_temp = gdf[[gdf.geometry.name] + list(cols_for_tmode.values())].copy()
        master_mask = pd.Series(True, index=df_temp.index)

        # Apply log transform (if requested) and build the master mask
        for col_name in cols_for_tmode.values():
            data_series = df_temp[col_name].replace([np.inf, -np.inf], np.nan)
            if log_transform:
                # FIX: Use log10(x + 1) for numerical stability with zero counts
                data_series = np.log10(data_series + 1)
            
            df_temp[col_name] = data_series # Store transformed data
            master_mask &= np.isfinite(data_series) # Add to master mask
        
        # 2. Create the single, common-support GDF and W matrix
        gdf_common_base = df_temp[master_mask].copy()

        if gdf_common_base.empty:
            print(f"Warning: No valid data for {transport_mode} after filtering. Skipping.")
            computed_data[transport_mode] = {"status": "Empty Data"}
            continue

        try:
            w_common = Queen.from_dataframe(gdf_common_base)
            w_common.transform = 'r'
        except ValueError as e:
            print(f"W Matrix Error for {transport_mode}: {e}")
            computed_data[transport_mode] = {"status": "W Error"}
            continue

        # 3. Run Regressions (New Rmode ~ ORS) and get Residuals
        
        # X is the baseline (ORS), must be 2D 
        X_ors = gdf_common_base[[cols_for_tmode['ors']]] 
        # Add a constant term for the intercept (required by statsmodels OLS)
        X_ors_const = sm.add_constant(X_ors) 

        for rmode in ROUTING_MODES: # Loop through the 5 comparison modes
            col_name_rmode = cols_for_tmode[rmode]
            y_rmode = gdf_common_base[col_name_rmode] # The dependent variable (e.g., Air)
            
            # Fit model (e.g., Air ~ ORS)
            ols_model = sm.OLS(y_rmode, X_ors_const)
            ols_results = ols_model.fit()
            
            # Residual = Actual - Predicted
            residuals = ols_results.resid
            gdf_common_base[f'resid_{rmode}'] = residuals

            # 4. Run LISA on each of the 5 residual columns
            y_resid = gdf_common_base[f'resid_{rmode}']
            moran_loc = Moran_Local(y_resid, w_common)
            
            # Store LISA results in GDF
            gdf_common_base[f'q_resid_{rmode}'] = moran_loc.q
            gdf_common_base[f'p_sig_resid_{rmode}'] = moran_loc.p_sim < 0.05
            
            # Append to summary table - ADDING REGRESSION AND LISA RESULTS HERE
            
            # Find the p-value for the ORS coefficient (index 1 after the constant)
            ors_p_value = ols_results.pvalues[cols_for_tmode['ors']] 
            
            # Find the p-value for the F-statistic (Overall model significance)
            f_p_value = ols_results.f_pvalue

            summary_results.append({
                "transport_mode": transport_mode,
                "routing_mode": rmode,
                "metric": col_name_rmode, # The name of the dependent variable column
                "R_squared": ols_results.rsquared,
                "Adj_R_squared": ols_results.rsquared_adj,
                "F_P_value": f_p_value,
                "ORS_Coeff_P_value": ors_p_value,
                "mean_local_I_resid": np.mean(moran_loc.Is),
                "p_value_min_resid": np.min(moran_loc.p_sim),
                "resid_high-high": np.sum(moran_loc.q == 1),
                "resid_low-low": np.sum(moran_loc.q == 3),
            })
            
        # 5. Store the single, computed GeoDataFrame for this transport mode
        computed_data[transport_mode] = {
            "status": "OK",
            "gdf": gdf_common_base,
            "w": w_common
        }
        print(f"Successfully computed residuals and LISA for {transport_mode}.")

    print("--- Computation complete ---")
    return computed_data, pd.DataFrame(summary_results)


# --- 4.5 Pairwise Route Comparison (Trajectory Metrics) ---

def get_coords(geometry):
    return np.array(geometry.coords)

@jit(nopython=True)
def calc_dfd_numba(p, q):
    n = p.shape[0]; m = q.shape[0]
    ca = np.ones((n, m), dtype=np.float64) * -1.0
    dist_matrix = np.empty((n, m), dtype=np.float64)
    for i in range(n):
        for j in range(m):
            dist_matrix[i, j] = np.sqrt((p[i, 0]-q[j, 0])**2 + (p[i, 1]-q[j, 1])**2)
    for i in range(n):
        for j in range(m):
            d = dist_matrix[i, j]
            if i == 0 and j == 0: ca[i, j] = d
            elif i > 0 and j == 0: ca[i, j] = max(d, ca[i-1, 0])
            elif i == 0 and j > 0: ca[i, j] = max(d, ca[0, j-1])
            elif i > 0 and j > 0:
                ca[i, j] = max(d, min(ca[i-1, j], ca[i-1, j-1], ca[i, j-1]))
            else: ca[i, j] = np.inf
    return ca[n-1, m-1]

@jit(nopython=True)
def calc_dtw_numba(p, q):
    n = p.shape[0]; m = q.shape[0]
    dtw_matrix = np.zeros((n + 1, m + 1))
    dtw_matrix[:, :] = np.inf; dtw_matrix[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dist = np.sqrt((p[i-1, 0]-q[j-1, 0])**2 + (p[i-1, 1]-q[j-1, 1])**2)
            dtw_matrix[i, j] = dist + min(dtw_matrix[i-1, j], dtw_matrix[i, j-1], dtw_matrix[i-1, j-1])
    return np.sqrt(dtw_matrix[n, m] / max(n, m))


_ROUTING_MODES  = ['routing_mode_air', 'routing_mode_distance', 'routing_mode_green',
                   'routing_mode_noise', 'routing_mode_ors', 'routing_mode_slope']
_TRANSPORT_MODES = ['transport_mode_cycle', 'transport_mode_drive', 'transport_mode_walk']


def preprocess_data(gdf):
    print("Preprocessing geometries into Numpy arrays...")
    data_dict = {}
    df_flat   = gdf.reset_index()
    for _, row in df_flat.iterrows():
        c_id = row['coords']; tm = row['transport_mode']; rm = row['routing_mode']
        geom = row['geometry']
        if pd.isna(geom): continue
        coords_arr = np.array(geom.coords, dtype=np.float64)
        if c_id not in data_dict:       data_dict[c_id] = {}
        if tm not in data_dict[c_id]:   data_dict[c_id][tm] = {}
        data_dict[c_id][tm][rm] = coords_arr
    return data_dict


def process_single_od_pair_raw(od_data, metric_func):
    partial_results = {}
    rm_to_idx = {rm: i for i, rm in enumerate(_ROUTING_MODES)}
    for tm in _TRANSPORT_MODES:
        if tm not in od_data: continue
        routes          = od_data[tm]
        available_modes = [rm for rm in _ROUTING_MODES if rm in routes]
        if len(available_modes) < 2: continue
        values = []
        for r1_name, r2_name in itertools.combinations(available_modes, 2):
            idx1, idx2 = rm_to_idx[r1_name], rm_to_idx[r2_name]
            val = metric_func(routes[r1_name], routes[r2_name])
            values.append((idx1, idx2, val))
        partial_results[tm] = values
    return partial_results


def run_parallel_comparison_full_stats(gdf, metric_func_numba, n_jobs=-1):
    start     = time.time()
    data_dict = preprocess_data(gdf)
    od_keys   = list(data_dict.keys())
    print(f"Launching jobs for {len(od_keys)} pairs...")
    results = Parallel(n_jobs=n_jobs)(
        delayed(process_single_od_pair_raw)(data_dict[od_key], metric_func_numba)
        for od_key in od_keys
    )
    print("Aggregating raw data...")
    raw_storage_tm  = {tm: [[[] for _ in range(6)] for _ in range(6)] for tm in _TRANSPORT_MODES}
    raw_storage_all = [[[] for _ in range(6)] for _ in range(6)]
    for res in results:
        if not res: continue
        for tm, value_list in res.items():
            for (r, c, val) in value_list:
                raw_storage_tm[tm][r][c].append(val); raw_storage_tm[tm][c][r].append(val)
                raw_storage_all[r][c].append(val);    raw_storage_all[c][r].append(val)
    final_data = {}
    for tm in _TRANSPORT_MODES:
        if len(raw_storage_tm[tm][0][1]) == 0: final_data[tm] = None; continue
        mean_mat, std_mat, med_mat = np.zeros((6, 6)), np.zeros((6, 6)), np.zeros((6, 6))
        for i in range(6):
            for j in range(6):
                vals = raw_storage_tm[tm][i][j]
                if len(vals) > 0 and i != j:
                    mean_mat[i, j] = np.mean(vals); std_mat[i, j] = np.std(vals); med_mat[i, j] = np.median(vals)
        final_data[tm] = {
            'mean':   pd.DataFrame(mean_mat, index=_ROUTING_MODES, columns=_ROUTING_MODES),
            'std':    pd.DataFrame(std_mat,  index=_ROUTING_MODES, columns=_ROUTING_MODES),
            'median': pd.DataFrame(med_mat,  index=_ROUTING_MODES, columns=_ROUTING_MODES)
        }
    if len(raw_storage_all[0][1]) > 0:
        mean_mat_all, std_mat_all, med_mat_all = np.zeros((6, 6)), np.zeros((6, 6)), np.zeros((6, 6))
        for i in range(6):
            for j in range(6):
                vals = raw_storage_all[i][j]
                if len(vals) > 0 and i != j:
                    mean_mat_all[i, j] = np.mean(vals); std_mat_all[i, j] = np.std(vals)
                    med_mat_all[i, j]  = np.median(vals)
        final_data['All Transport Modes'] = {
            'mean':   pd.DataFrame(mean_mat_all, index=_ROUTING_MODES, columns=_ROUTING_MODES),
            'std':    pd.DataFrame(std_mat_all,  index=_ROUTING_MODES, columns=_ROUTING_MODES),
            'median': pd.DataFrame(med_mat_all,  index=_ROUTING_MODES, columns=_ROUTING_MODES)
        }
    else:
        final_data['All Transport Modes'] = None
    print(f"Done in {time.time() - start:.2f}s")
    return final_data


# --- 4.6 Lorenz Curve Analysis ---

def lorenz_curve(values):
    values = np.array(values); values = values[np.isfinite(values)]; values = values[values >= 0]
    if len(values) == 0: return None, None, None
    sorted_vals = np.sort(values); cum_vals = np.cumsum(sorted_vals); total = cum_vals[-1]
    x = np.linspace(0, 1, len(values) + 1)
    y = np.concatenate(([0], cum_vals / total))
    gini = 1 - 2 * np.trapezoid(y, x)
    return x, y, gini


def lorenz_curve_interpolated(data, grid_resolution=100):
    X = np.sort(data.values if isinstance(data, pd.Series) else data)
    if len(X) == 0 or np.sum(X) == 0:
        return np.linspace(0, 1, grid_resolution), np.linspace(0, 1, grid_resolution), 0.0
    X = np.insert(X, 0, 0); X_cum = np.cumsum(X); Y_cum = X_cum / X_cum[-1]
    X_axis_raw = np.linspace(0, 1, len(Y_cum))
    gini = 1 - 2 * np.trapezoid(Y_cum, X_axis_raw)
    common_x = np.linspace(0, 1, grid_resolution)
    f = interpolate.interp1d(X_axis_raw, Y_cum, kind='linear', bounds_error=False, fill_value=(0, 1))
    return common_x, f(common_x), gini


def plot_lorenz_single_row(gdf, hex_colors, figsize=(18, 6)):
    transport_modes = ["cycle", "drive", "walk"]
    routing_modes   = ["air", "distance", "green", "noise", "slope"]
    fig, axes = plt.subplots(nrows=1, ncols=len(transport_modes), figsize=figsize, sharey=True)
    if len(transport_modes) == 1: axes = [axes]
    for j, tmode in enumerate(transport_modes):
        ax = axes[j]
        ors_col = f"transport_mode_{tmode}_routing_mode_ors"
        x_ors, y_ors, gini_ors = lorenz_curve(gdf[ors_col].fillna(0))
        ax.plot(x_ors, y_ors, color=hex_colors["routing_mode_ors"],
                label=f"ORS (G={gini_ors:.2f})", linewidth=2)
        for rmode in routing_modes:
            alt_col = f"transport_mode_{tmode}_routing_mode_{rmode}"
            if alt_col not in gdf.columns: continue
            x_alt, y_alt, gini_alt = lorenz_curve(gdf[alt_col].fillna(0))
            ax.plot(x_alt, y_alt, color=hex_colors[f"routing_mode_{rmode}"],
                    label=f"{rmode.capitalize()} (G={gini_alt:.2f})", linewidth=2,
                    linestyle=linestyles[f"routing_mode_{rmode}"])
        ax.plot([0, 1], [0, 1], color="black", linestyle="--", linewidth=1)
        ax.set_title(tmode.capitalize(), fontsize=14)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.set_xlabel("Cumulative share of cells")
        if j == 0: ax.set_ylabel("Cumulative share of usage")
        ax.legend(fontsize=8, loc="upper left")
    fig.suptitle("Lorenz Curves of Route Usage Inequality (ORS vs Alternatives)", fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig("figs/lorenz_single_row.png", dpi=450, bbox_inches="tight")
    plt.show()


def plot_lorenz_combined_alternatives_per_mode(gdf, hex_colors, figsize=(18, 6)):
    transport_modes = ["cycle", "drive", "walk"]
    routing_modes   = ["air", "distance", "green", "noise", "slope"]
    fig, axes = plt.subplots(nrows=1, ncols=len(transport_modes), figsize=figsize, sharey=True)
    if len(transport_modes) == 1: axes = [axes]
    for j, tmode in enumerate(transport_modes):
        ax = axes[j]
        ors_col = f"transport_mode_{tmode}_routing_mode_ors"
        x_ors, y_ors, gini_ors = lorenz_curve(gdf[ors_col].fillna(0))
        ax.plot(x_ors, y_ors, color=hex_colors.get("routing_mode_ors", "blue"),
                label=f"ORS Baseline (G={gini_ors:.2f})", linewidth=2)
        alt_cols = [f"transport_mode_{tmode}_routing_mode_{rmode}" for rmode in routing_modes
                    if f"transport_mode_{tmode}_routing_mode_{rmode}" in gdf.columns]
        if alt_cols:
            combined_alt_data = gdf[alt_cols].fillna(0).sum(axis=1)
            x_alt, y_alt, gini_alt = lorenz_curve(combined_alt_data)
            ax.plot(x_alt, y_alt, color=hex_colors.get("combined_alt", "red"),
                    label=f"Combined Alts (G={gini_alt:.2f})", linewidth=2, linestyle="--")
        ax.plot([0, 1], [0, 1], color="black", linestyle=":", linewidth=1)
        ax.set_title(tmode.capitalize(), fontsize=14)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.set_xlabel("Cumulative share of cells", fontsize=16)
        if j == 0: ax.set_ylabel("Cumulative share of usage", fontsize=16)
        ax.legend(fontsize=16, loc="upper left")
    fig.suptitle("Lorenz Curves: ORS Baseline vs. Aggregated Alternative Strategies", fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig("figs/lorenz_combined_alternatives.png", dpi=450, bbox_inches="tight")
    plt.show()


# --- 4.7 Bootstrap Simulation ---

def get_sparse_matrix(df, n_cells):
    df['route_int_id'] = df.groupby(['coords', 'routing_mode', 'transport_mode']).ngroup()
    sparse_mat = sparse.coo_matrix(
        (np.ones(len(df)), (df['route_int_id'].values, df['cell_int_id'].values)),
        shape=(df['route_int_id'].max() + 1, n_cells)
    ).tocsr()
    return sparse_mat, df['route_int_id'].max() + 1


def bootstrap_iteration(sparse_matrix, n_to_sample, grid_resolution, n_total_cells):
    indices       = np.random.choice(sparse_matrix.shape[0], size=n_to_sample, replace=True)
    counts_subset = np.array(sparse_matrix[indices, :].sum(axis=0)).flatten()
    return lorenz_curve_interpolated(counts_subset, grid_resolution)


def run_combined_simulation_2(gdf_routes, hex_grid, n_iterations=1000):
    if gdf_routes.crs != hex_grid.crs:
        gdf_routes = gdf_routes.to_crs(hex_grid.crs)
    joined = gpd.sjoin(gdf_routes.reset_index(), hex_grid[['geometry']], predicate='intersects')
    all_cell_ids    = hex_grid.index.tolist()
    cell_id_to_int  = {cell_id: i for i, cell_id in enumerate(all_cell_ids)}
    n_total_cells   = len(all_cell_ids)
    joined['cell_int_id'] = joined['index_right'].map(cell_id_to_int)
    tmodes   = ['transport_mode_cycle', 'transport_mode_drive', 'transport_mode_walk']
    rmodes   = ['routing_mode_air', 'routing_mode_distance', 'routing_mode_green',
                'routing_mode_noise', 'routing_mode_slope']
    grid_res = 100
    results  = {}
    for tmode in tmodes:
        mode_data = joined[joined['transport_mode'] == tmode]
        results[tmode] = {}
        for rmode in rmodes + ['routing_mode_ors']:
            counts      = mode_data[mode_data['routing_mode'] == rmode].groupby('cell_int_id').size()
            full_counts = counts.reindex(range(n_total_cells), fill_value=0)
            if not full_counts.empty:
                _, y, g = lorenz_curve_interpolated(full_counts, grid_res)
                results[tmode][rmode] = {'y_mean': y, 'g_mean': g}
        alt_df = mode_data[mode_data['routing_mode'] != 'routing_mode_ors'].copy()
        if not alt_df.empty:
            alt_mat, _ = get_sparse_matrix(alt_df, n_total_cells)
            alt_boot   = Parallel(n_jobs=-1)(
                delayed(bootstrap_iteration)(alt_mat, 2000, grid_res, n_total_cells)
                for _ in range(n_iterations)
            )
            y_vals = np.array([r[1] for r in alt_boot])
            g_vals = np.array([r[2] for r in alt_boot])
            results[tmode]['aggregated'] = {
                'y_mean':  np.mean(y_vals, axis=0),
                'y_lower': np.percentile(y_vals, 2.5,  axis=0),
                'y_upper': np.percentile(y_vals, 97.5, axis=0),
                'g_mean':  np.mean(g_vals),
                'g_lower': np.percentile(g_vals, 2.5),
                'g_upper': np.percentile(g_vals, 97.5)
            }
    return results


# --- Water body helper ---



def compute_ols_comparison_data(
    gdf: gpd.GeoDataFrame,
    column_suffix: str,
    log_transform: bool = False
) -> Tuple[Dict[str, Dict[str, Any]], pd.DataFrame]:
    """
    Computes LISA (Local Moran's I) on the RESIDUALS of 15 Ordinary Least Squares 
    (OLS) regressions (e.g., Air ~ ORS) and extracts the **AICc** for direct comparison 
    with the GWR model.
    """
    
    computed_data = {}
    summary_results = []
    
    model_name = "OLS"
    print(f"Starting LISA on {model_name} Residuals computation (log_transform={log_transform})...")

    # --- Loop by Transport Mode (e.g., 'cycle', 'drive', 'walk') ---
    for transport_mode in TRANSPORT_MODES:
        
        # 1. Prepare data and find the "master mask" for this transport mode
        cols_for_tmode = {
            metric: f'transport_mode_{transport_mode}_routing_mode_{metric}{column_suffix}'
            for metric in ALL_METRICS
        }
        
        if not all(col in gdf.columns for col in cols_for_tmode.values()):
            print(f"Warning: Missing columns for {transport_mode}. Skipping.")
            computed_data[transport_mode] = {"status": f"Missing Columns"}
            continue

        df_temp = gdf[[gdf.geometry.name] + list(cols_for_tmode.values())].copy()
        master_mask = pd.Series(True, index=df_temp.index)

        # Apply log transform (if requested) and build the master mask
        for col_name in cols_for_tmode.values():
            data_series = df_temp[col_name].replace([np.inf, -np.inf], np.nan)
            if log_transform:
                # Use log10(x + 1) for numerical stability with zero counts
                data_series = np.log10(data_series + 1)
            
            df_temp[col_name] = data_series # Store transformed data
            master_mask &= np.isfinite(data_series) # Add to master mask
        
        # 2. Create the single, common-support GDF and W matrix
        gdf_common_base = df_temp[master_mask].copy()

        if gdf_common_base.empty:
            print(f"Warning: No valid data for {transport_mode} after filtering. Skipping.")
            computed_data[transport_mode] = {"status": "Empty Data"}
            continue

        try:
            # Setting use_index=False to silence the FutureWarning
            w_common = Queen.from_dataframe(gdf_common_base, use_index=False)
            w_common.transform = 'r'
        except ValueError as e:
            print(f"W Matrix Error for {transport_mode}: {e}")
            computed_data[transport_mode] = {"status": "W Error"}
            continue

        # Prepare OLS inputs
        y_ors_col = cols_for_tmode['ors']
        X_ors = gdf_common_base[[y_ors_col]].values
        X_ors_const = sm.add_constant(X_ors, prepend=False) # Add a constant term (the intercept)

        for rmode in ROUTING_MODES: # Loop through the 5 comparison modes
            col_name_rmode = cols_for_tmode[rmode]
            y_rmode = gdf_common_base[col_name_rmode].values # The dependent variable (e.g., Air)
            
            ols_status = "OK"
            
            try:
                # 3a. Fit OLS model
                ols_model = sm.OLS(y_rmode, X_ors_const)
                ols_results = ols_model.fit()
                
                # Residual = Actual - Predicted
                n = len(y_rmode)
                k = ols_results.df_model + 1 # num_params = num_predictors (1) + intercept (1) = 2
                
                # AICc = AIC + (2*K*(K+1))/(N-K-1)
                ols_aicc = ols_results.aic + (2 * k * (k + 1)) / (n - k - 1)
                
                residuals = pd.Series(ols_results.resid, index=gdf_common_base.index)
                
                # OLS Summary Metrics
                ols_r2 = ols_results.rsquared
                ols_adj_r2 = ols_results.rsquared_adj
                ols_aic = ols_results.aic # Standard AIC

            except Exception as e:
                # Fallback/Error handling if OLS fails (rare, but possible)
                print(f"OLS Error for {transport_mode}/{rmode}: {e}")
                residuals = pd.Series(np.nan, index=gdf_common_base.index)
                ols_r2, ols_adj_r2, ols_aicc = np.nan, np.nan, np.nan
                ols_status = f"OLS Failed: {str(e)[:50]}..."
                
            gdf_common_base[f'resid_{rmode}'] = residuals

            # 4. Run LISA on each of the 5 residual columns
            y_resid = gdf_common_base[f'resid_{rmode}'].dropna()
            
            # Ensure there is enough data remaining after potential failure
            if not y_resid.empty and ols_status == "OK":
                moran_loc = Moran_Local(y_resid, w_common)
                
                # Store LISA results in GDF
                gdf_common_base[f'q_resid_{rmode}'] = moran_loc.q
                gdf_common_base[f'p_sig_resid_{rmode}'] = moran_loc.p_sim < 0.05
                
                # Append to summary table
                summary_results.append({
                    "transport_mode": transport_mode,
                    "routing_mode": rmode,
                    "metric": col_name_rmode, 
                    "Model_Type": model_name,
                    "Model_Status": ols_status,
                    "R_squared": ols_r2,
                    "Adj_R_squared": ols_adj_r2,
                    "AIC": ols_aic,
                    "AICc": ols_aicc, # Crucial metric for comparison
                    "mean_local_I_resid": np.mean(moran_loc.Is),
                    "resid_high-high": np.sum(moran_loc.q == 1),
                    "resid_low-low": np.sum(moran_loc.q == 3),
                })
            
        # 5. Store the single, computed GeoDataFrame for this transport mode
        computed_data[transport_mode] = {
            "status": "OK",
            "gdf": gdf_common_base,
            "w": w_common
        }
        print(f"Successfully computed OLS residuals and LISA for {transport_mode}.")

    print("--- OLS Computation complete ---")
    return computed_data, pd.DataFrame(summary_results)


def compute_lisa_on_residuals_GWR(
    gdf: gpd.GeoDataFrame,
    column_suffix: str,
    log_transform: bool = False
) -> Tuple[Dict[str, Dict[str, Any]], pd.DataFrame]:
    """
    Computes LISA (Local Moran's I) on the RESIDUALS of 15 Geographically Weighted 
    Regressions (GWR). Includes ultra-robust coordinate and data cleaning to prevent 
    'invalid index to scalar variable' errors.
    """
    
    computed_data = {}
    summary_results = []
    
    model_name = "GWR"
    print(f"Starting LISA on {model_name} Residuals computation (log_transform={log_transform})...")

    # --- Loop by Transport Mode (e.g., 'cycle', 'drive', 'walk') ---
    for transport_mode in TRANSPORT_MODES:
        
        # 1. Prepare data and find the "master mask" for this transport mode
        cols_for_tmode = {
            metric: f'transport_mode_{transport_mode}_routing_mode_{metric}{column_suffix}'
            for metric in ALL_METRICS
        }
        
        if not all(col in gdf.columns for col in cols_for_tmode.values()):
            print(f"Warning: Missing columns for {transport_mode}. Skipping.")
            computed_data[transport_mode] = {"status": f"Missing Columns"}
            continue

        df_temp = gdf[[gdf.geometry.name] + list(cols_for_tmode.values())].copy()
        master_mask = pd.Series(True, index=df_temp.index)

        # Apply log transform (if requested) and build the master mask
        for col_name in cols_for_tmode.values():
            data_series = df_temp[col_name].replace([np.inf, -np.inf], np.nan)
            if log_transform:
                # Use log10(x + 1) for numerical stability with zero counts
                data_series = np.log10(data_series + 1)
            
            df_temp[col_name] = data_series # Store transformed data
            master_mask &= np.isfinite(data_series) # Add to master mask
        
        # 2. Create the single, common-support GDF and W matrix
        gdf_common_base = df_temp[master_mask].copy()

        if gdf_common_base.empty:
            print(f"Warning: No valid data for {transport_mode} after filtering. Skipping.")
            computed_data[transport_mode] = {"status": "Empty Data"}
            continue

        try:
            # Setting use_index=False to silence the FutureWarning
            w_common = Queen.from_dataframe(gdf_common_base, use_index=False)
            w_common.transform = 'r'
        except ValueError as e:
            print(f"W Matrix Error for {transport_mode}: {e}")
            computed_data[transport_mode] = {"status": "W Error"}
            continue

        # Prepare GWR inputs (independent variable X and coordinates)
        
        # 3. COORDINATE GENERATION AND CLEANING
        
        # Check for valid geometries before centroid extraction
        valid_geom_mask = gdf_common_base.geometry.is_valid & ~gdf_common_base.geometry.is_empty & ~gdf_common_base.geometry.isna()
        
        # Filter the base GDF to only include rows with valid geometries
        gdf_valid_geom = gdf_common_base[valid_geom_mask].copy()
        
        if gdf_valid_geom.empty:
            print(f"Warning: No valid geometries for {transport_mode} after filtering. Skipping.")
            computed_data[transport_mode] = {"status": "No Valid Geometries"}
            continue
            
        # Get coordinates for GWR from the clean subset
        coords_raw = np.array([(p.x, p.y) for p in gdf_valid_geom.geometry.centroid]) # (n_valid, 2)
        
        # Check coordinates themselves for non-finite values (NaN, Inf)
        coord_finite_mask = np.all(np.isfinite(coords_raw), axis=1)
        
        # Apply the final coordinate mask
        coords_base = coords_raw[coord_finite_mask, :]
        gdf_gwr_base = gdf_valid_geom[coord_finite_mask].copy() # Final GDF subset for GWR inputs
        
        if gdf_gwr_base.empty:
            print(f"Warning: Data was filtered down to zero points after coordinate check for {transport_mode}. Skipping.")
            computed_data[transport_mode] = {"status": "Empty Data After Coord Check"}
            continue

        # Recalculate X_ors based on the final, cleaned GDF subset
        # NOTE: We do NOT add a constant manually here. MGWR adds it by default.
        # Adding it here would create a double constant (singular matrix).
        X_ors = gdf_gwr_base[[cols_for_tmode['ors']]].values 
        
        # Get the index for later mapping of results
        base_index = gdf_gwr_base.index


        for rmode in ROUTING_MODES: # Loop through the 5 comparison modes
            col_name_rmode = cols_for_tmode[rmode]
            y_rmode_base = gdf_gwr_base[col_name_rmode].values # (n_gwr_base,)
            
            # --- GWR Data Cleaning and Structuring ---
            # Create a final, perfect mask for the GWR inputs based on the dependent variable
            gwr_mask = np.isfinite(y_rmode_base) & np.all(np.isfinite(X_ors), axis=1)
            
            # FIX 1: Shape y to (n, 1) for MGWR
            y_rmode = y_rmode_base[gwr_mask].reshape((-1, 1)).astype(np.float64)
            
            # FIX 2: Ensure X and coords are filtered and float type
            X_ors_in = X_ors[gwr_mask, :].astype(np.float64) # (n_filtered, 1)
            coords = coords_base[gwr_mask, :].astype(np.float64) # (n_filtered, 2)
            
            # Store the filtered index to align residuals back to the base GDF
            filtered_index = base_index[gwr_mask]
            
            gwr_status = "OK"
            bw = np.nan # Initialize bandwidth
            
            # Check for minimum data points (k=2: slope + intercept. Need at least 3 points, 5 is safer)
            if len(y_rmode) < 5:
                gwr_status = "Data Insufficient (< 5 points)"
                print(f"Skipping {transport_mode}/{rmode}: {gwr_status}")
                continue
            
            # --- GWR Logic Start ---
            try:
                # 3a. Select the optimal adaptive bandwidth using AICc
                # constant=True is default, so it will add the intercept column to X_ors_in
                bw_selector = Sel_BW(coords, y_rmode, X_ors_in, kernel='gaussian')
                bw = bw_selector.search(verbose=False)
                
                # 3b. Fit GWR model
                # Removed 'verbose' from fit call based on the first error
                gwr_model = GWR(coords, y_rmode, X_ors_in, bw, kernel='gaussian')
                gwr_results = gwr_model.fit()
                
                # *** THE CRUCIAL FIX: Use 'resid_response' as confirmed by mgwr docs ***
                residuals_filtered = gwr_results.resid_response.flatten() # Flatten back to 1D Series
                
                # GWR Summary Metrics
                gwr_r2 = gwr_results.R2
                gwr_adj_r2 = gwr_results.adj_R2
                gwr_aicc = gwr_results.aicc

            except Exception as e:
                # Fallback/Error handling if GWR fails
                print(f"GWR Error for {transport_mode}/{rmode}: {e}")
                residuals_filtered = np.full(len(filtered_index), np.nan)
                gwr_r2, gwr_adj_r2, gwr_aicc = np.nan, np.nan, np.nan
                gwr_status = f"GWR Failed: {str(e)[:50]}..."
                
            # --- GWR Logic End ---

            # Map the residuals back to the common base GDF using the filtered index
            residuals_full = pd.Series(np.nan, index=gdf_common_base.index) # Initialize full series using original index
            
            # Find the index intersection between the GWR results (filtered_index) and the common base GDF (gdf_common_base)
            # and map results back to the original index
            
            # 1. Create a Series with results aligned to the GWR base index
            residuals_temp = pd.Series(residuals_filtered, index=filtered_index)
            
            # 2. Assign these results to the appropriate indices in the full series
            residuals_full.loc[filtered_index] = residuals_temp
            
            # Assign results back to the original large gdf_common_base (not the smaller gdf_gwr_base)
            gdf_common_base[f'resid_{rmode}'] = residuals_full
            
            
            # 4. Run LISA on the residuals
            y_resid = residuals_full.dropna()
            
            # If the GWR succeeded and we have residuals to analyze
            if not y_resid.empty and gwr_status.startswith("OK"):
                
                try:
                    # Create a new W matrix only for the data points with residuals
                    w_resid = Queen.from_dataframe(gdf_common_base.loc[y_resid.index], use_index=False)
                    w_resid.transform = 'r'
                    
                    moran_loc = Moran_Local(y_resid, w_resid)
                except Exception as e:
                    print(f"LISA Error for {transport_mode}/{rmode} (W matrix failure): {e}. Skipping LISA results.")
                    continue

                # Store LISA results in GDF
                moran_q = pd.Series(np.nan, index=gdf_common_base.index, dtype=object)
                moran_p_sig = pd.Series(False, index=gdf_common_base.index, dtype=bool)
                
                moran_q.loc[y_resid.index] = moran_loc.q
                moran_p_sig.loc[y_resid.index] = moran_loc.p_sim < 0.05
                
                gdf_common_base[f'q_resid_{rmode}'] = moran_q
                gdf_common_base[f'p_sig_resid_{rmode}'] = moran_p_sig

                
                # Append to summary table
                summary_results.append({
                    "transport_mode": transport_mode,
                    "routing_mode": rmode,
                    "metric": col_name_rmode, 
                    "Model_Type": model_name,
                    "Model_Status": gwr_status,
                    "R_squared": gwr_r2,
                    "Adj_R_squared": gwr_adj_r2,
                    "AICc": gwr_aicc,
                    "Bandwidth": bw, # The calculated optimal bandwidth
                    "mean_local_I_resid": np.mean(moran_loc.Is),
                    "resid_high-high": np.sum(moran_loc.q == 1),
                    "resid_low-low": np.sum(moran_loc.q == 3),
                })
            
        # 5. Store the single, computed GeoDataFrame for this transport mode
        computed_data[transport_mode] = {
            "status": "OK" if "OK" in gwr_status else gwr_status,
            "gdf": gdf_common_base,
            "w": w_common
        }
        print(f"Successfully computed GWR residuals and LISA for {transport_mode}.")

    print("--- GWR Computation complete ---")
    return computed_data, pd.DataFrame(summary_results)


def _calculate_plot_ratios(gdf_original: gpd.GeoDataFrame, tmode: str, rmode: str, column_suffix: str, log_scale: bool) -> Tuple[pd.Series, str]:
    """Helper to calculate ratios, handling pre-calculated ratio inputs."""
    rmode_col = f'transport_mode_{tmode}_routing_mode_{rmode}{column_suffix}'
    ors_col = f'transport_mode_{tmode}_routing_mode_ors{column_suffix}'
    
    if rmode_col not in gdf_original.columns:
        # Returns empty series if the Rmode column itself is missing
        return pd.Series([], dtype=float), f"Missing RMode column: {rmode_col}"

    # Check if we need to calculate the ratio (i.e., if ORS column exists)
    if ors_col in gdf_original.columns:
        # Standard case: Ratios = Rmode_Raw / ORS_Raw (e.g., concentration/concentration)
        ratios = gdf_original[rmode_col] / gdf_original[ors_col]
        calculation_type = "Calculated Ratio (RMode/ORS)"
    else:
        # ASSUMPTION: The Rmode column itself is the pre-calculated ratio 
        # (e.g., if column_suffix is '_ratio_vs_ors', we use that column directly)
        ratios = gdf_original[rmode_col]
        calculation_type = "Pre-calculated Ratio (RMode)"

    vals = ratios.replace([np.inf, -np.inf], np.nan)
    
    if log_scale:
        # Apply log10 to ratios (only for positive ratios)
        # log10(x) where x > 0
        vals = np.log10(vals.where(vals > 0))
    
    return vals, calculation_type


def plot_lisa_residuals(
    computed_results: Dict[str, Dict[str, Any]], 
    gdf_original: gpd.GeoDataFrame, 
    column_suffix: str, 
    model_type: str = "OLS", # OLS or GWR — controls filename and title
    figsize: Tuple[int, int] = (18, 25),
    log_transform: bool = False, 
    water_gdf: gpd.GeoDataFrame = None,
    add_scalebar: bool = True,
    cmap: str = 'bwr', 
    log_scale: bool = True, 
    plot_ratio_background: bool = True
) -> None:
    """
    Plots the precomputed LISA clusters found on the *regression residuals*. 
    
    Optionally overlays them on an opaque heatmap of the underlying 
    performance ratio (RMode / ORS) if plot_ratio_background is True.
    """

    norm = None
    ratio_calc_type = "N/A"
    
    # Standardize model_type text for title
    model_type_abbr = "OLS" if model_type.upper() == "OLS" else "GWR"
    model_type_label = f"{model_type_abbr} (New ~ ORS)"

    # ------------------------------------------------------------------
    # 1. SETUP: Conditional Ratio Calculation for Heatmap Background
    # ------------------------------------------------------------------
    if plot_ratio_background:
        if water_gdf is not None:
            # Ensure water_gdf is in the same CRS as the main gdf
            water_gdf = water_gdf.to_crs(gdf_original.crs)

        all_values = []
        
        # Calculate all 15 ratios across the original data
        for tmode in TRANSPORT_MODES:
            for rmode in ROUTING_MODES:
                
                vals, calc_type = _calculate_plot_ratios(
                    gdf_original, tmode, rmode, column_suffix, log_scale
                )
                ratio_calc_type = calc_type
                
                if isinstance(vals, pd.Series) and not vals.empty:
                    # Append only the non-NaN values for global normalization
                    all_values.append(vals.dropna())

        if not all_values:
            print(f"Warning: No valid ratio columns found based on suffix '{column_suffix}'. Disabling ratio background plot.")
            plot_ratio_background = False # Disable if data is missing

        if plot_ratio_background:
            # Combine all valid ratio values for global normalization
            all_values = pd.concat(all_values)
            
            if all_values.empty:
                 print(f"Warning: All ratio values were NaN/Inf. Disabling ratio background plot.")
                 plot_ratio_background = False
            else:
                # Define common normalization based on all ratios
                vmin = np.floor(all_values.min())
                vmax = np.ceil(all_values.max())
                
                # Ensure vmin < vmax for the TwoSlopeNorm to work
                if vmin == vmax:
                    vmin -= 1
                    vmax += 1

                norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)


    # Standard 4-quadrant cluster map
    cluster_map = {
        1: {"label": "HH (Unexpectedly High)", "color": '#e41a1c'}, # Red
        2: {"label": "HL (Outlier)", "color": '#4daf4a'}, # Green
        3: {"label": "LL (Unexpectedly Low)", "color": '#377eb8'}, # Blue
        4: {"label": "LH (Outlier)", "color": '#984ea3'}, # Purple
    }

    # Setup figure
    fig, axes = plt.subplots(nrows=5, ncols=3, figsize=figsize) 
    fig.subplots_adjust(hspace=0.05, wspace=0.05)

    # ------------------------------------------------------------------
    # 2. LOOP THROUGH SUBPLOTS AND PLOT PRECOMPUTED DATA
    # ------------------------------------------------------------------

    for i, routing_mode in enumerate(ROUTING_MODES):
        for j, transport_mode in enumerate(TRANSPORT_MODES):
            
            ax = axes[i, j] 
            data = computed_results.get(transport_mode)

            # --- Handle N/A or Error states ---
            if data is None or data['status'] != "OK":
                status_text = data['status'] if data else "N/A"
                ax.set_facecolor('lightgray')
                ax.text(0.5, 0.5, status_text, ha='center', va='center', transform=ax.transAxes)
                ax.set_axis_off()
                continue
            
            gdf_common_base = data['gdf'] # The subset GDF used for LISA
            
            if plot_ratio_background and norm is not None:
                # Calculate the ratio for this specific subplot
                ratios, _ = _calculate_plot_ratios(
                    gdf_original, transport_mode, routing_mode, column_suffix, log_scale
                )
                
                # Check if we got valid ratio values back
                if not ratios.empty:
                    # Create a temporary GDF with the ratio aligned to the common base (used for LISA)
                    gdf_ratio_tmp = gdf_original.loc[gdf_common_base.index].copy()
                    
                    # Ensure alignment: use the index loc for reliable mapping
                    gdf_ratio_tmp['plot_ratio_value'] = ratios.loc[gdf_common_base.index]


                    # --- Plot 1: Background Ratio Heatmap FILL (Near Opaque) ---
                    # This creates the solid, color-mapped background.
                    gdf_ratio_tmp.plot(
                        column='plot_ratio_value',
                        ax=ax, 
                        cmap=cmap, 
                        norm=norm, 
                        legend=False, 
                        alpha=0.9, # <-- Near opaque fill
                        hatch=' ', # No hatch on the fill layer
                        zorder=1
                    )
                    
                    # --- Plot 2: Background Ratio Hatch (Uniform White) ---
                    # This layer provides a uniform white hatch mask over the ratio fill.
                    gdf_ratio_tmp.plot(
                        ax=ax, 
                        facecolor='none', # Crucially, no face fill
                        edgecolor='white', # <-- Uniform white hatch
                        linewidth=0, # Hide the regular polygon outline
                        hatch='ooo', 
                        alpha=1.0, # Fully opaque hatch lines
                        zorder=1.5 
                    )
                else:
                    # If ratio calculation failed for this subplot, use light grey background
                    gdf_common_base.plot(
                        ax=ax, 
                        color='lightgrey', 
                        edgecolor='lightgray', 
                        linewidth=0.1, 
                        alpha=0.7, 
                        zorder=1
                    )
            else:
                # Plot the entire base GDF as a light background when no ratio heatmap is used
                gdf_common_base.plot(
                    ax=ax, 
                    color='lightgrey', 
                    edgecolor='lightgray', 
                    linewidth=0.1, 
                    alpha=0.7, 
                    zorder=1
                )

            
            # --- Plot 3: Significant Residual Clusters (Solid) ---
            q_col = f'q_resid_{routing_mode}'
            p_sig_col = f'p_sig_resid_{routing_mode}'
            
            for code in sorted(cluster_map.keys()):
                cluster_info = cluster_map[code]
                gdf_cluster = gdf_common_base[gdf_common_base[p_sig_col] & (gdf_common_base[q_col] == code)]
                
                if not gdf_cluster.empty:
                    gdf_cluster.plot(
                        ax=ax,
                        color=cluster_info["color"],
                        edgecolor='black', 
                        linewidth=0.1,
                        alpha=0.75, # Higher alpha for foreground clusters
                        zorder=2
                    )

            # Optional overlay of waterbodies
            if water_gdf is not None:
                water_gdf.plot(ax=ax, color="dimgrey", edgecolor='none', alpha=1, zorder=3)

            
            # --- Add Scalebar ---
            if add_scalebar:
                scalebar = ScaleBar(
                    1, # dx=1: Assumes 1 map unit = 1 meter (for Projected CRS)
                    'm', # Specify base unit as meters
                    location='lower center',
                    pad=0.5,
                    frameon=False,
                    color='black',
                    font_properties={'size': 8},
                    length_fraction=0.1
                )
                ax.add_artist(scalebar)


            ax.set_axis_off()

            # --- Add Titles/Labels ---
            if i == 0:
                ax.set_title(transport_mode.capitalize(), fontsize=12)
            if j == 0:
                ax.annotate(
                    routing_mode.capitalize(),
                    xy=(0, 0.5), xycoords='axes fraction', fontsize=12, ha='right',
                    va='center', rotation=90, xytext=(-10, 0), textcoords='offset points'
                )

    # ------------------------------------------------------------------
    # 3. FINALIZING FIGURE (LEGEND and COLORBAR for RATIO)
    # ------------------------------------------------------------------

    # --- LISA Legend ---
    handles = []
    labels = []

    # Conditionally add the Ratio Context entry
    if plot_ratio_background and norm is not None:
        handles.append(Patch(facecolor='white', edgecolor='none')) # Placeholder for ratio
        labels.append(f'Ratio Context ({cmap})') 
        
        # Add entry for non-significant background covered by heatmap
        # Use a placeholder (light grey fill, alpha 0.9) and a placeholder for the white hatch
        handles.append(Patch(facecolor='lightgrey', edgecolor='white', alpha=0.9, hatch='ooo', linewidth=0.5))
        labels.append('Not Significant (White Hatched Ratio Background)')
    else:
        # Add entry for non-significant background when ratio heatmap is absent
        handles.append(Patch(facecolor='lightgrey', edgecolor='lightgray', alpha=0.7))
        labels.append('Not Significant')


    # Add standard 4 cluster types
    for code in sorted(cluster_map.keys()):
        cluster_info = cluster_map[code]
        handles.append(Patch(facecolor=cluster_info["color"], edgecolor='black', alpha=0.75))
        labels.append(cluster_info["label"])

    # Update title based on whether background is present
    if plot_ratio_background and norm is not None:
        title_suffix = f"(Residuals of {model_type_label} Over White-Hatched Ratio Heatmap)"
        legend_y_pos = 0.05
    else:
        title_suffix = f"(Residuals of {model_type_label} Only)"
        legend_y_pos = 0.02 # Lower position since colorbar is absent

        
    # New flag for the title
    log_tag = " (Log-Transformed Data)" if log_transform else ""
    
    # ... Inside Finalizing Figure ...
    fig.suptitle(
        f"LISA Clusters on {model_type_abbr} Regression Residuals{log_tag} {title_suffix}", 
        fontsize=16,
        y=0.95 
    )

    fig.legend(
        handles, 
        labels, 
        title="Significant LISA Cluster Type",
        loc='lower center', 
        bbox_to_anchor=(0.5, legend_y_pos), # Adjust position if no colorbar is present
        ncol=5, 
        fontsize=14
    )
    
    # --- Conditional Ratio Heatmap Colorbar ---
    if plot_ratio_background and norm is not None:
        cax = fig.add_axes([0.25, 0.01, 0.5, 0.015]) # Position for colorbar
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm._A = []

        # Define standard log ticks relative to the center (log10(1) = 0)
        raw_ticks = np.log10(np.array([1/1000, 1/100, 1/10, 0.5, 1, 2, 10, 100, 1000]))
        raw_ticks = raw_ticks[~np.isinf(raw_ticks)] 

        # Filter ticks to only show what falls within the calculated vmin/vmax
        tick_mask = (raw_ticks >= vmin) & (raw_ticks <= vmax)
        log_ticks = raw_ticks[tick_mask]

        sci_labels = []
        for val in log_ticks:
            if np.isclose(val, 0, atol=1e-2):
                sci_labels.append('1')
            else:
                sci_labels.append(f'$10^{{{val:.1f}}}$') 

        interp_labels = []
        for val in log_ticks:
            real_val = 10**val
            if np.isclose(real_val, 1, atol=0.01):
                interp_labels.append("same")
            elif np.isclose(real_val, 2, atol=0.1):
                interp_labels.append("×2 more")
            elif np.isclose(real_val, 0.5, atol=0.05):
                interp_labels.append("×2 less")
            elif real_val > 1:
                interp_labels.append(f"×{int(round(real_val))} more")
            else:
                interp_labels.append(f"×{int(round(1/real_val))} less")

        cbar = fig.colorbar(sm, cax=cax, orientation='horizontal', ticks=log_ticks)
        cbar.ax.set_xticklabels(sci_labels)
        cbar.set_label(f'Log-scaled Ratio (RMode / ORS) | Source: {ratio_calc_type}',
                      labelpad=10)

        for xtick, interp in zip(cbar.ax.get_xticks(), interp_labels):
            cbar.ax.text(
                xtick,
                -0.8,
                interp,
                ha='center',
                va='top',
                fontsize=8,
                rotation=0,
                transform=cbar.ax.get_xaxis_transform()
            )


    fig.subplots_adjust(top=0.93, bottom=0.12 if plot_ratio_background else 0.08)
    
    plt.savefig(f"figs/lisa_residuals_{model_type_abbr.lower()}.png", dpi=450, bbox_inches="tight")
    plt.show()


def plot_heatmaps_full_stats(stats_dict, metric_name):
    """
    Expects stats_dict = { 'transport_mode': {'mean': df, 'std': df, 'median': df} }
    Plots 3 heatmaps with a SHARED color scale and specific ORS highlighting.
    """
    # 1. DEFINE ORDER
    base_modes = [r for r in _ROUTING_MODES if 'ors' not in r]
    new_order = base_modes + ['routing_mode_ors']
    
    full_labels = [r.replace('routing_mode_', '') for r in new_order]
    y_labels = full_labels[1:]  # Start from 'Distance'
    x_labels = full_labels[:-1] # End at 'Slope'

    # 2. CALCULATE GLOBAL MIN/MAX FOR COLOR SCALING
    all_values = []
    for tm in _TRANSPORT_MODES:
        data = stats_dict.get(tm)
        if data is None: continue
        
        mean_full = data['mean'].reindex(index=new_order, columns=new_order)
        mean_sliced = mean_full.iloc[1:, :-1] 
        all_values.append(mean_sliced.values.max())
        all_values.append(mean_sliced.values.min())

    g_vmin = np.min(all_values)
    g_vmax = np.max(all_values)

    # 3. SETUP PLOT (Removed sharey=True to prevent auto-hiding labels)
    fig, axes = plt.subplots(1, 3, figsize=(30, 9))

    for i, tm in enumerate(_TRANSPORT_MODES):
        data = stats_dict.get(tm)
        ax = axes[i]
        
        if data is None:
            ax.text(0.5, 0.5, "No Data", ha='center', fontsize=16)
            continue
            
        # --- PREPARE MATRICES ---
        mean_full = data['mean'].reindex(index=new_order, columns=new_order)
        std_full = data['std'].reindex(index=new_order, columns=new_order)
        med_full = data['median'].reindex(index=new_order, columns=new_order)
        
        # Annotations
        annot_full = mean_full.copy().astype(object)
        for r in range(len(new_order)):
            for c in range(len(new_order)):
                if r == c: annot_full.iloc[r, c] = "-"
                else:
                    m = mean_full.iloc[r, c]
                    s = std_full.iloc[r, c]
                    md = med_full.iloc[r, c]
                    annot_full.iloc[r, c] = f"{m:.0f}\n[{md:.0f}]\n({s:.0f})"

        # Slice
        mask_full = np.triu(np.ones_like(mean_full, dtype=bool))
        mean_df = mean_full.iloc[1:, :-1]
        mask = mask_full[1:, :-1]
        annot_labels = annot_full.iloc[1:, :-1]

        # LOGIC: Only show y_labels if it is the first plot (i == 0)
        show_y_labels = (i == 0)
        current_y_labels = y_labels if show_y_labels else False

        # --- DRAW HEATMAP ---
        sns.heatmap(mean_df, 
                    annot=annot_labels.values, 
                    fmt="", 
                    cmap="Reds", 
                    vmin=g_vmin, 
                    vmax=g_vmax, 
                    xticklabels=x_labels, 
                    yticklabels=current_y_labels, # Explicitly passed here
                    mask=mask,
                    ax=ax,
                    cbar=False, 
                    annot_kws={"size": 24, "weight": "bold"})
        
        # --- HIGHLIGHT BASELINE ---
        last_row_idx = mean_df.shape[0] - 1
        for col_idx in range(mean_df.shape[1]):
            rect = patches.Rectangle((col_idx, last_row_idx), 1, 1, 
                                     linewidth=4, edgecolor='black', facecolor='none')
            ax.add_patch(rect)

        # Styling
        clean_tm = tm.replace('transport_mode_', '').capitalize()
        ax.set_title(f"{clean_tm}", fontsize=32, fontweight='bold', pad=20)
        
        # Force X labels
        ax.set_xticklabels(x_labels, rotation=0, ha='center', fontsize=20)
        
        # Force Y labels ONLY for the first plot
        if show_y_labels:
            ax.set_yticklabels(y_labels, fontsize=20, rotation=0)
        else:
            ax.set_yticklabels([]) # Explicitly clear others just in case

    # 4. ADD GLOBAL COLORBAR
    cbar_ax = fig.add_axes([0.3, 0.05, 0.4, 0.03]) 
    norm = plt.Normalize(g_vmin, g_vmax)
    sm = plt.cm.ScalarMappable(cmap="Reds", norm=norm)
    sm.set_array([])
    
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation='horizontal')
    cbar.ax.tick_params(labelsize=20)
    cbar.set_label(f"Mean {metric_name}", size=24)

    plt.suptitle(f"Comparative Analysis vs ORS ({metric_name})", 
                 fontsize=36, y=1, fontweight='bold')
    
    plt.subplots_adjust(bottom=0.15, wspace=0.05) 
    
    plt.savefig("figs/dfd_heatmaps.png", dpi=450, bbox_inches="tight")
    plt.show()


def plot_lorenz_grid(gdf, hex_colors, figsize=(15, 20)):
    """
    Plot Lorenz curves: ORS baseline vs alternative routing for each
    transport mode (columns) and routing mode (rows).
    """
    transport_modes = ["cycle", "drive", "walk"]
    routing_modes = ["air", "distance", "green", "noise", "slope"]

    fig, axes = plt.subplots(
        nrows=len(routing_modes), ncols=len(transport_modes),
        figsize=figsize, sharex=True, sharey=True
    )

    for i, rmode in enumerate(routing_modes):
        for j, tmode in enumerate(transport_modes):
            ax = axes[i, j]

            ors_col = f"transport_mode_{tmode}_routing_mode_ors"
            alt_col = f"transport_mode_{tmode}_routing_mode_{rmode}"

            if ors_col not in gdf.columns or alt_col not in gdf.columns:
                ax.set_axis_off()
                continue

            # ORS curve
            x_ors, y_ors, gini_ors = lorenz_curve(gdf[ors_col].fillna(0))
            ax.plot(x_ors, y_ors, color=hex_colors["routing_mode_ors"],
                    label=f"ORS (G={gini_ors:.2f})", linewidth=2)

            # Alternative curve
            x_alt, y_alt, gini_alt = lorenz_curve(gdf[alt_col].fillna(0))
            ax.plot(x_alt, y_alt, color=hex_colors[f"routing_mode_{rmode}"],
                    label=f"{rmode.capitalize()} (G={gini_alt:.2f})", linewidth=2)

            # Equality diagonal
            ax.plot([0, 1], [0, 1], color="black", linestyle="--", linewidth=1)

            # Titles and labels
            if i == 0:
                ax.set_title(tmode.capitalize(), fontsize=16)
            if j == 0:
                ax.set_ylabel(rmode.capitalize(), fontsize=16)

            # Make tick labels larger
            ax.tick_params(axis='both', which='major', labelsize=16)

            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)

            ax.legend(fontsize=16, loc="upper left")

    fig.suptitle("Lorenz Curves of Route Usage Inequality (ORS vs Alternatives)", fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig("figs/lorenz_grid.png", dpi=450, bbox_inches="tight")
    plt.show()

import matplotlib.pyplot as plt
import numpy as np


def plot_lorenz_aggregated_with_air(gdf, hex_colors, figsize=(18, 6)):
    """
    Plot Lorenz curves per transport mode showing:
    - ORS Baseline
    - Disaggregated 'Air' alternative
    - Aggregated Alternatives (Sum of Air + Distance + Green + Noise + Slope)
    """
    transport_modes = ["cycle", "drive", "walk"]
    routing_modes = ["air", "distance", "green", "noise", "slope"]

    fig, axes = plt.subplots(
        nrows=1, ncols=len(transport_modes),
        figsize=figsize, sharey=True
    )

    if len(transport_modes) == 1:
        axes = [axes]

    for j, tmode in enumerate(transport_modes):
        ax = axes[j]

        # 1. Perfect equality diagonal (zorder=1, absolute bottom)
        ax.plot([0, 1], [0, 1], color="black", linestyle=":", linewidth=1, zorder=1)

        # 2. 'Air' Disaggregated
        # zorder=2 ensures it stays visually BELOW the aggregated curve
        air_col = f"transport_mode_{tmode}_routing_mode_air"
        if air_col in gdf.columns:
            air_data = gdf[air_col].fillna(0)
            x_air, y_air, gini_air = lorenz_curve(air_data)
            ax.plot(x_air, y_air, color=hex_colors.get("routing_mode_air", "cyan"),
                    label=f"Air Only (G={gini_air:.2f})", 
                    linewidth=2, linestyle="-.", zorder=2)

        # 3. Aggregated Alternatives
        # zorder=3 ensures it draws ON TOP of the Air curve
        alt_cols = [f"transport_mode_{tmode}_routing_mode_{rmode}" for rmode in routing_modes 
                    if f"transport_mode_{tmode}_routing_mode_{rmode}" in gdf.columns]
        
        if alt_cols:
            combined_alt_data = gdf[alt_cols].fillna(0).sum(axis=1)
            x_alt, y_alt, gini_alt = lorenz_curve(combined_alt_data)
            ax.plot(x_alt, y_alt, color=hex_colors.get("combined_alt", "red"),
                    label=f"Aggregated Alts (G={gini_alt:.2f})", 
                    linewidth=2.5, linestyle="--", zorder=3)

        # 4. ORS Baseline
        # zorder=4 ensures the baseline is always clearly visible on top of everything
        ors_col = f"transport_mode_{tmode}_routing_mode_ors"
        if ors_col in gdf.columns:
            ors_data = gdf[ors_col].fillna(0)
            x_ors, y_ors, gini_ors = lorenz_curve(ors_data)
            ax.plot(x_ors, y_ors, color=hex_colors.get("routing_mode_ors", "blue"),
                    label=f"ORS Baseline (G={gini_ors:.2f})", 
                    linewidth=2, zorder=4)

        # --- Styling & Formatting ---
        ax.set_title(tmode.capitalize(), fontsize=18)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        
        # Axis labels
        ax.set_xlabel("Cumulative share of cells", fontsize=16)
        if j == 0:
            ax.set_ylabel("Cumulative share of usage", fontsize=16)
        
        # Make tick labels larger
        ax.tick_params(axis='both', which='major', labelsize=16)
        
        # Remove upper and right borders
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        ax.legend(fontsize=16, loc="upper left", framealpha=0.9)

    fig.suptitle("Lorenz Curves: ORS vs. Aggregated Alternatives vs. Air", fontsize=20, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig("figs/lorenz_aggregated_with_air.png", dpi=450, bbox_inches="tight")
    plt.show()


def plot_lorenz_grid_complete(simulation_results, hex_colors, figsize=(18, 20)):
    """
    Plots a comprehensive grid of Lorenz curves with grouped legend entries.
    """
    transport_modes = ['transport_mode_cycle', 'transport_mode_drive', 'transport_mode_walk']
    routing_modes = ['routing_mode_air', 'routing_mode_distance', 'routing_mode_green', 'routing_mode_noise', 'routing_mode_slope']
    short_tnames = ['Cycle', 'Drive', 'Walk']
    
    fig, axes = plt.subplots(nrows=len(routing_modes), ncols=3, figsize=figsize, sharex=True, sharey=True)
    
    grid_res = 100
    common_x = np.linspace(0, 1, grid_res)
    ors_color = hex_colors.get('routing_mode_ors', '#8e8071')
    agg_color = '#008080'

    for i, rmode in enumerate(routing_modes):
        mode_label = rmode.replace('routing_mode_', '').capitalize()
        
        for j, tmode in enumerate(transport_modes):
            ax = axes[i, j]
            if tmode not in simulation_results: continue
            data = simulation_results[tmode]
            
            ax.plot([0, 1], [0, 1], color='grey', linestyle=':', alpha=0.6, zorder=0)

            final_handles = []
            final_labels = []

            # 1. ORS Baseline
            if 'routing_mode_ors' in data:
                d_ors = data['routing_mode_ors']
                line_ors, = ax.plot(common_x, d_ors['y_mean'], color=ors_color, linewidth=2.5, zorder=3)
                final_handles.append(line_ors)
                final_labels.append(f"ORS (G={d_ors['g_mean']:.2f})")

            # 2. Aggregated Mean + CI
            if 'aggregated' in data:
                d_agg = data['aggregated']
                line_agg, = ax.plot(common_x, d_agg['y_mean'], color=agg_color, linewidth=2, linestyle='--', zorder=4)
                ax.fill_between(common_x, d_agg['y_lower'], d_agg['y_upper'], color=agg_color, alpha=0.15, zorder=2)
                
                ci_patch = mpatches.Patch(color=agg_color, alpha=0.15)
                
                final_handles.extend([line_agg, ci_patch])
                final_labels.extend([
                    f"Aggregated Alts (Mean G={d_agg['g_mean']:.2f})",
                    f"Gini 95% CI: [{d_agg['g_lower']:.2f}-{d_agg['g_upper']:.2f}]"
                ])
                
                # --- SPACER ---
                # Add an empty proxy and label to create vertical distance before the next section
                final_handles.append(mpatches.Rectangle((0,0), 0, 0, fill=False, edgecolor='none', visible=False))
                final_labels.append("")

            # 3. Individual Mode
            if rmode in data:
                d_mode = data[rmode]
                m_color = hex_colors.get(rmode, 'blue')
                line_mode, = ax.plot(common_x, d_mode['y_mean'], color=m_color, linewidth=3, linestyle=':', zorder=5)
                final_handles.append(line_mode)
                final_labels.append(f"{mode_label} Only (G={d_mode['g_mean']:.2f})")

            if i == 0:
                ax.set_title(short_tnames[j], fontsize=20, fontweight='bold', pad=15)
            if j == 0:
                ax.set_ylabel(mode_label, fontsize=18, fontweight='bold')
            
            # Using labelspacing=0.35 and the spacer added above to separate groups
            ax.legend(handles=final_handles, labels=final_labels, loc='upper left', 
                      fontsize=16, frameon=True, labelspacing=0.35, handlelength=2.5)
            
            ax.tick_params(axis='both', which='major', labelsize=16)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.grid(True, linestyle='--', alpha=0.3)

    plt.suptitle("Grid Analysis: Individual Preferences vs. ORS and Combined Population Average", 
                 fontsize=26, y=0.99, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig("figs/lorenz_grid_complete.png", dpi=450, bbox_inches="tight")
    plt.show()


def plot_combined_results(simulation_results):
    """
    Specific focus plot with grouped legend and custom spacing.
    """
    tmodes = ['transport_mode_cycle', 'transport_mode_drive', 'transport_mode_walk']
    short_names = ['Cycle', 'Drive', 'Walk']
    grid_res = 100
    common_x = np.linspace(0, 1, grid_res)
    
    colors = {'ors': '#8e8071', 'air': '#feb40a', 'aggregated': '#008080'}

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)

    for ax, tmode, sname in zip(axes, tmodes, short_names):
        if tmode not in simulation_results:
            ax.set_axis_off()
            continue
            
        data = simulation_results[tmode]
        handles = []
        labels = []

        # 1. Aggregated Alternatives
        if 'aggregated' in data:
            d = data['aggregated']
            line_agg, = ax.plot(common_x, d['y_mean'], color=colors['aggregated'], linewidth=2.5, linestyle='--', zorder=5)
            ax.fill_between(common_x, d['y_lower'], d['y_upper'], color=colors['aggregated'], alpha=0.2, zorder=5)
            
            ci_patch = mpatches.Patch(color=colors['aggregated'], alpha=0.2)
            handles.extend([line_agg, ci_patch])
            labels.extend([
                f"Aggregated Alts (Mean G={d['g_mean']:.2f})",
                f"Gini 95% CI: [{d['g_lower']:.2f}-{d['g_upper']:.2f}]"
            ])
            
            # SPACER
            handles.append(mpatches.Rectangle((0,0), 0, 0, fill=False, edgecolor='none', visible=False))
            labels.append("")

        # 2. Air Routing Mode
        if 'routing_mode_air' in data:
            d = data['routing_mode_air']
            line_air, = ax.plot(common_x, d['y_mean'], color=colors['air'], linewidth=3, zorder=6, linestyle=':')
            handles.append(line_air)
            labels.append(f"Air Only (G={d['g_mean']:.2f})")

        # 3. ORS Baseline
        if 'routing_mode_ors' in data:
            d = data['routing_mode_ors']
            line_ors, = ax.plot(common_x, d['y_mean'], color=colors['ors'], linewidth=3, zorder=3)
            handles.append(line_ors)
            labels.append(f"ORS Baseline (G={d['g_mean']:.2f})")

        ax.plot([0, 1], [0, 1], color='grey', linestyle=':', alpha=0.6, zorder=0)
        ax.set_title(f"Usage Distribution: {sname}", fontsize=20, pad=20, fontweight='bold')
        ax.set_xlabel("Cumulative share of cells", fontsize=18)
        if sname == 'Cycle': ax.set_ylabel("Cumulative share of usage", fontsize=18)
        
        ax.legend(handles=handles, labels=labels, loc='upper left', 
                  fontsize=16, frameon=True, labelspacing=0.4, handlelength=3)
        
        ax.tick_params(axis='both', which='major', labelsize=16)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    plt.suptitle("Spatial Inequality Analysis: Deterministic Baseline vs. Aggregated Alternatives", 
                 fontsize=24, y=0.98, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig("figs/bootstrap_combined.png", dpi=450, bbox_inches="tight")
    plt.show()
# =============================================================================
# 5. EXECUTION PIPELINE
# =============================================================================

def main():
    os.makedirs("data", exist_ok=True)
    os.makedirs("figs", exist_ok=True)

    # -----------------------------------------------------------------
    # 5.1 Load Processed Routes
    # -----------------------------------------------------------------
    print("\n── Step 1: Loading route data ──────────────────────────────")
    gdf_routes = pd.read_pickle("data/gdf_routes_v4_merged.pkl")
    gdf_routes = gdf_routes.to_crs("EPSG:2056")
    print(f"Loaded {len(gdf_routes)} routes | CRS: {gdf_routes.crs}")

    # -----------------------------------------------------------------
    # 5.2 Generate Hex Grid & Count Routes  (cached)
    # -----------------------------------------------------------------
    ROUTE_COUNTS_CACHE = "data/route_counts_dict.pkl"
    HEX_GRID_CACHE     = "data/hex_grid_dict.pkl"

    cell_sizes = (list(range(50, 501, 50)) + list(range(600, 2001, 100))
                  + list(range(2500, 5001, 500)) + [10000, 20000, 50000])

    if os.path.exists(ROUTE_COUNTS_CACHE) and os.path.exists(HEX_GRID_CACHE):
        print(f"\n── Step 2: Loading hex grids & route counts from cache ─────")
        with open(ROUTE_COUNTS_CACHE, 'rb') as f:
            route_counts_dict = pickle.load(f)
        with open(HEX_GRID_CACHE, 'rb') as f:
            hex_grid_dict = pickle.load(f)
        print(f"Loaded {len(route_counts_dict)} grid sizes from cache.")
    else:
        print(f"\n── Step 2: Generating hex grids & counting routes ──────────")
        GRAPHML_PATH = "data/zurich_network.graphml"
        if os.path.exists(GRAPHML_PATH):
            print("  Loading road network from cached graphml...")
            G = ox.load_graphml(GRAPHML_PATH)
        else:
            print("  Downloading road network from OSM...")
            G = ox.graph_from_place("Zurich, Switzerland", network_type="all")
            ox.save_graphml(G, GRAPHML_PATH)
        _, edges          = ox.graph_to_gdfs(G)
        gdf_links_geometry = edges[['geometry']]

        hex_grid_dict = generate_hex_grids_for_sizes(gdf_routes, gdf_links_geometry, cell_sizes)
        with open(HEX_GRID_CACHE, 'wb') as f:
            pickle.dump(hex_grid_dict, f)

        route_counts_dict = count_routes_for_all_sizes_parallel(gdf_routes, hex_grid_dict, max_workers=6)
        with open(ROUTE_COUNTS_CACHE, 'wb') as f:
            pickle.dump(route_counts_dict, f)
        print("  Saved hex grids and route counts to cache.")

    # Quick sanity plot
    hex_grid_dict[500].plot()
    plt.title("500 m Hex Grid")
    plt.savefig("figs/hex_grid_500m.png", dpi=450, bbox_inches="tight")
    plt.show()

    # -----------------------------------------------------------------
    # 5.3 Run Master Pipeline  (cached)
    # -----------------------------------------------------------------
    ALL_RESULTS_CACHE = "data/all_results_hex_grids_v4.pkl"

    if os.path.exists(ALL_RESULTS_CACHE):
        print(f"\n── Step 3: Loading pre-computed metrics from cache ─────────")
        with open(ALL_RESULTS_CACHE, 'rb') as f:
            all_results = pickle.load(f)
        print(f"Loaded results for grid sizes: {sorted(all_results.keys())}")
    else:
        print(f"\n── Step 3: Computing all metrics ───────────────────────────")
        all_results = compute_all_metrics_master(
            route_counts_dict, use_gpu=False, max_workers=6,
            gpu_kwargs={"max_dist": 3000, "n_lags": 12}
        )
        with open(ALL_RESULTS_CACHE, 'wb') as f:
            pickle.dump(all_results, f)
        print("  Results saved.")

    # -----------------------------------------------------------------
    # 5.4 Extract Sub-results & Prepare 500 m Reference Grid
    # -----------------------------------------------------------------
    print("\n── Step 4: Extracting sub-results ──────────────────────────")
    pairwise_results   = {k: v["pairwise"]   for k, v in all_results.items()}
    inequality_results = {k: v["inequality"] for k, v in all_results.items()}
    moran_results      = {k: v["moran"]      for k, v in all_results.items()}
    variogram_results  = {k: v["variogram"]  for k, v in all_results.items()}

    route_counts_500 = route_counts_dict[500]
    route_counts_500 = calculate_hex_metrics_diffs(route_counts_500)
    print(f"route_counts_500: {len(route_counts_500)} cells | CRS: {route_counts_500.crs}")

    # -----------------------------------------------------------------
    # 5.5 Load Water Bodies
    # -----------------------------------------------------------------
    print("\n── Step 5: Loading water bodies ────────────────────────────")
    with open("data/water_ZH.pkl", "rb") as f:
        gdf_water = pickle.load(f)
    gdf_water = gdf_water.to_crs(route_counts_500.crs)
    print(f"Water bodies loaded: {len(gdf_water)} features")

    # -----------------------------------------------------------------
    # 6. Visualizations
    # -----------------------------------------------------------------
    print("\n── Step 6: Generating visualizations ───────────────────────")

    # 6.1 LISA on OLS residuals — disabled (functions preserved above)
    # computed_results_ols, summary_df_ols = compute_lisa_on_residuals(
    #     route_counts_500, column_suffix='', log_transform=True
    # )
    # print(summary_df_ols)
    # plot_lisa_residuals(
    #     computed_results_ols, route_counts_500,
    #     column_suffix='', model_type='OLS',
    #     water_gdf=gdf_water, log_transform=True,
    #     plot_ratio_background=False
    # )

    # 6.2 LISA on GWR residuals
    print("  6.2 LISA on GWR residuals...")
    computed_results_gwr, summary_df_gwr = compute_lisa_on_residuals_GWR(
        route_counts_500, column_suffix='', log_transform=True
    )
    print(summary_df_gwr)
    plot_lisa_residuals(
        computed_results_gwr, route_counts_500,
        column_suffix='', model_type='GWR',
        water_gdf=gdf_water, log_transform=True,
        plot_ratio_background=False
    )

    # 6.3 Pairwise DFD heatmaps
    print("  6.3 Computing pairwise Discrete Fréchet Distance...")
    DFD_CACHE = "data/result_matrices_dfd.pkl"
    if os.path.exists(DFD_CACHE):
        print("    Loading DFD results from cache...")
        with open(DFD_CACHE, 'rb') as f:
            result_matrices_dfd = pickle.load(f)
    else:
        result_matrices_dfd = run_parallel_comparison_full_stats(gdf_routes, calc_dfd_numba, n_jobs=-1)
        with open(DFD_CACHE, 'wb') as f:
            pickle.dump(result_matrices_dfd, f)
    plot_heatmaps_full_stats(result_matrices_dfd, "Discrete Fréchet (Meters)")

    # 6.4 Lorenz: ORS vs Combined Alternatives per transport mode
    print("  6.4 Lorenz — combined alternatives per mode...")
    plot_lorenz_combined_alternatives_per_mode(route_counts_500, hex_colors)

    # 6.5 Lorenz: Full 5x3 grid (each routing mode vs ORS)
    print("  6.5 Lorenz — full 5x3 grid...")
    plot_lorenz_grid(route_counts_500, hex_colors)

    # 6.6 Lorenz: ORS vs Aggregated Alternatives vs Air
    print("  6.6 Lorenz — aggregated with air...")
    plot_lorenz_aggregated_with_air(route_counts_500, hex_colors)

    # 6.7 Bootstrap Lorenz simulation
    print("  6.7 Bootstrap Lorenz simulation (n=2000)...")
    BOOTSTRAP_CACHE = "data/bootstrap_results.pkl"
    if os.path.exists(BOOTSTRAP_CACHE):
        print("    Loading bootstrap results from cache...")
        with open(BOOTSTRAP_CACHE, 'rb') as f:
            results_boots_comb_2 = pickle.load(f)
    else:
        results_boots_comb_2 = run_combined_simulation_2(
            gdf_routes, hex_grid_dict[500], n_iterations=2000
        )
        with open(BOOTSTRAP_CACHE, 'wb') as f:
            pickle.dump(results_boots_comb_2, f)

    # 6.8 Bootstrap: combined results plot
    print("  6.8 Bootstrap — combined results plot...")
    plot_combined_results(results_boots_comb_2)

    # 6.9 Bootstrap: complete Lorenz grid with confidence intervals
    print("  6.9 Bootstrap — complete Lorenz grid with CI...")
    plot_lorenz_grid_complete(results_boots_comb_2, hex_colors)

    print("✅ Pipeline complete.")


if __name__ == "__main__":
    main()
