# Analysis

This folder contains two independent Python scripts for evaluating multi-objective
route optimisation strategies in Zurich. Each script addresses a different research
question and operates on different input data.

---

## Scripts overview

| Script | Input | Output | Question addressed |
|---|---|---|---|
| `analysis.py` | `routing_results.json` | CSV tables + 6 figures | Do alternative routing strategies deliver measurable environmental benefit at acceptable distance cost? |
| `routes_analysis.py` | `data/` (pkl, graphml) | Spatial maps + Lorenz/DFD figures | How does the spatial distribution of route usage differ across strategies? |

---

## `analysis.py` — Route performance analysis

Processes per-OD routing results from JSON, computes cost/benefit trade-offs,
classifies routes into Pareto quadrants, and runs statistical tests.

### Usage

```bash
python analysis.py --input routing_results.json --output results/
```

**Arguments**

| Flag | Default | Description |
|---|---|---|
| `--input` / `-i` | `routing_results.json` | Path to the JSON file with routing results |
| `--output` / `-o` | `final_results/` | Directory where tables and figures are saved |
| `--epsilon-cost` | `5.0` | Distance cost threshold (%) for quadrant assignment |
| `--epsilon-benefit` | `3.0` | Environmental benefit threshold (%) for quadrant assignment |

### Input format

`routing_results.json` is a list of OD objects. Each object must contain a
`responses` key with at least a `routing_mode_ors` baseline and one or more
alternative strategies (`routing_mode_distance`, `routing_mode_green`, etc.).

### Outputs

Saved to `--output` directory:

**Tables (CSV)**
- `Table1_Summary_Statistics.csv` — median/mean/SD per mode × strategy
- `Table2_Statistical_Tests.csv` — Wilcoxon signed-rank tests, FDR-corrected p-values
- `Table3_Quadrant_Distribution.csv` — % of routes in each Pareto quadrant

**Figures (PNG, 450 DPI)**
- `Figure1_Pareto_Optimality.png` — % Pareto-optimal routes per strategy/mode
- `Figure2_Quadrant_Classification.png` — cost vs. benefit scatter, colored by quadrant
- `Figure3_Synergy_Matrix.png` — heatmap of median % improvement across metrics
- `Figure4_Distribution_Heterogeneity.png` — violin plots of benefit distributions
- `Figure5_Effect_Sizes.png` — standardised Wilcoxon effect sizes (FDR-corrected)
- `Figure_Combined_Violin_Pareto.png` — composite 3×2 figure (violins + Pareto bars)

---

## `routes_analysis.py` — Spatial inequality analysis

Aggregates route usage onto hexagonal grids, computes spatial inequality metrics
(Gini, entropy, Moran's I, variograms), runs LISA cluster detection on GWR
residuals, and produces Lorenz curves and DFD heatmaps.

### Usage

```bash
python routes_analysis.py
```

All paths are relative to the script location. The `data/` folder must be present
(see [Data](#data) section below).

### Data files required

Place these inside a `data/` subfolder next to the script:

| File | Description | Used by |
|---|---|---|
| `gdf_routes_v4_merged.pkl` | GeoDataFrame of all computed routes (multi-index: transport mode × routing mode) | Step 1 |
| `route_counts_dict.pkl` | Pre-aggregated route counts per hex grid size | Step 2 cache |
| `hex_grid_dict.pkl` | Hexagonal grid GeoDataFrames per cell size | Step 2 cache |
| `all_results_hex_grids_v4.pkl` | Full metrics results (pairwise, Gini, Moran, variogram) | Step 3 cache |
| `bootstrap_results.pkl` | Bootstrap Lorenz simulation results | Step 6 cache |
| `result_matrices_dfd.pkl` | Pairwise Discrete Fréchet Distance matrices | Step 6 cache |
| `water_ZH.pkl` | Water body geometries for Zurich | Step 5 |
| `zurich_network.graphml` | OSM road network for Zurich (used only if hex grids are missing) | Step 2 fallback |

> **On first run** (no cache files present), the script recomputes everything from
> `gdf_routes_v4_merged.pkl` and saves all cache files. Subsequent runs load from
> cache and are much faster. Delete any `.pkl` to force recomputation of that step.

### Outputs

Saved to `figs/` subfolder (created automatically):

| File | Description |
|---|---|
| `hex_grid_500m.png` | Sanity check — 500 m hexagonal grid |
| `lisa_residuals_gwr.png` | LISA clusters on GWR regression residuals (5×3 map) |
| `dfd_heatmaps.png` | Pairwise Discrete Fréchet Distance heatmaps |
| `lorenz_combined_alternatives.png` | Lorenz curves: ORS vs. combined alternatives |
| `lorenz_grid.png` | Full 5×3 Lorenz grid (each mode vs. ORS baseline) |
| `lorenz_aggregated_with_air.png` | Lorenz: ORS vs. aggregated alternatives vs. air |
| `bootstrap_combined.png` | Bootstrap Lorenz — deterministic vs. aggregated |
| `lorenz_grid_complete.png` | Bootstrap Lorenz grid with 95% confidence intervals |

> The OLS LISA map (`lisa_residuals_ols.png`) is disabled by default. To re-enable
> it, uncomment the block labelled `6.1 LISA on OLS residuals` in `main()`.

---

## Data

The `data/` folder (~200 MB) is **not stored in this repository**. It is hosted
on OSF (Open Science Framework):

> 📦 **[OSF project — `https://osf.io/XXXXXXX`]**
> *(replace with actual OSF URL after upload)*

OSF is preferred here over Zenodo or Git LFS because it supports private storage
during peer review (switchable to public on acceptance), has direct GitHub repo
integration, and organises code + data + paper under one project page.

### Downloading the data

```bash
# Install the OSF command-line client
pip install osfclient

# Clone the OSF project data into the data/ folder
osf -p XXXXXXX clone data/
```

Or download `data.zip` manually from the OSF project page and unzip:

```bash
unzip data.zip -d data/
```

---

## Environment setup

Requires **Python 3.11**.

```bash
# Create and activate a conda environment (recommended)
conda create -n routes_env python=3.11
conda activate routes_env

# Install dependencies
pip install -r requirements.txt
```

> **Apple Silicon / macOS note:** install `pyproj` and `gdal` via conda before
> running pip to avoid binary wheel issues:
> ```bash
> conda install -c conda-forge pyproj gdal
> ```

> **Font note:** The script uses Helvetica if a licensed copy is placed at
> `data/Helvetica.ttc`. This file is **not included** in the OSF data package
> (Helvetica is proprietary — Linotype/Monotype). Without it the script
> automatically falls back to Helvetica Neue → Arial → DejaVu Sans, producing
> visually equivalent output.

> **Numba JIT note:** the first run of `routes_analysis.py` will be slower while
> Numba compiles the DFD/DTW functions. Compiled artifacts are cached automatically.

---

## Folder structure

```
analysis/
├── analysis.py              # Route performance analysis (JSON → tables + figures)
├── routes_analysis.py       # Spatial inequality analysis (pkl → maps + Lorenz)
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── routing_results.json     # Input for analysis.py
├── data/                    # ← download from Zenodo (not in repo)
│   ├── gdf_routes_v4_merged.pkl
│   ├── route_counts_dict.pkl
│   ├── hex_grid_dict.pkl
│   ├── all_results_hex_grids_v4.pkl
│   ├── bootstrap_results.pkl
│   ├── result_matrices_dfd.pkl
│   ├── water_ZH.pkl
│   ├── zurich_network.graphml
└── figs/                    # ← created automatically by routes_analysis.py
```
