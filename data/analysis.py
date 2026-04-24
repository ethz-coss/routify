"""
Route Analysis Pipeline
=======================
Processes routing comparison data from JSON, generates statistical tables,
and creates publication-quality figures for evaluating multi-objective
route optimization strategies.

Usage:
    python route_analysis.py --input routing_results.json --output results/

Author: Sachit Mahajan
Date: 2026
"""

import json
import os
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from scipy import stats
from statsmodels.stats.multitest import multipletests


# -----------------------------------------------------------------------------
# Plot styling defaults — tweak once, apply everywhere
# -----------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 16,
    "axes.titlesize": 18,
    "axes.titleweight": "bold",
    "axes.labelsize": 16,
    "xtick.labelsize": 16,
    "ytick.labelsize": 16,
    "legend.fontsize": 16,
    "figure.dpi": 450,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
    "lines.linewidth": 2.5,
})


# -----------------------------------------------------------------------------
# Color palette — consistent hex codes for strategies across all figures
# -----------------------------------------------------------------------------
HEX_COLORS = {
    'routing_mode_distance': '#bc1530',
    'routing_mode_slope':    '#236bbf',
    'routing_mode_green':    '#1bd39b',
    'routing_mode_noise':    '#840087',
    'routing_mode_air':      '#feb40a',
    'routing_mode_ors':      '#8e8071',
    'combined_alt':          '#000000',
}

STRATEGY_COLORS = {
    'distance': HEX_COLORS['routing_mode_distance'],
    'slope':    HEX_COLORS['routing_mode_slope'],
    'green':    HEX_COLORS['routing_mode_green'],
    'noise':    HEX_COLORS['routing_mode_noise'],
    'air':      HEX_COLORS['routing_mode_air'],
}


class FinalRouteAnalysis:
    """
    Main analysis class for processing route comparison data and generating
    tables + figures. Handles data loading, statistical testing, Pareto
    evaluation, and visualization.
    """

    def __init__(self, json_path, output_dir="final_results",
                 epsilon_cost=5.0, epsilon_benefit=3.0):
        self.json_path = json_path
        self.output_dir = output_dir
        self.epsilon_cost = epsilon_cost
        self.epsilon_benefit = epsilon_benefit
        os.makedirs(output_dir, exist_ok=True)
        self.df = self._process_data()

    # -------------------------------------------------------------------------
    # Data loading and preprocessing
    # -------------------------------------------------------------------------
    def _process_data(self):
        """Load JSON, compute deltas/percentages, flag Pareto-optimal routes."""
        print("Processing route data...")
        with open(self.json_path, "r") as f:
            data = json.load(f)

        records = []
        strategy_map = {
            "green":    ("greenIndex", False),
            "noise":    ("noise",      True),
            "air":      ("pm_10",      True),
            "slope":    ("slope",      True),
            "distance": ("distance",   True),
        }

        for od in data:
            res = od.get("responses", {})
            if "routing_mode_ors" not in res:
                continue
            ors_group = res["routing_mode_ors"]

            for strategy_key, modes in res.items():
                if strategy_key == "routing_mode_ors":
                    continue

                strategy = strategy_key.replace("routing_mode_", "")
                if strategy not in strategy_map:
                    continue

                target_col, minimize = strategy_map[strategy]

                for mode_key, metrics in modes.items():
                    mode = mode_key.split("_")[-1]
                    if mode_key not in ors_group:
                        continue
                    ors = ors_group[mode_key]

                    d_r = metrics.get("distance", np.nan)
                    d_o = ors.get("distance", np.nan)
                    if pd.isna(d_r) or pd.isna(d_o) or d_o == 0:
                        continue

                    delta_dist = d_r - d_o
                    pct_cost = (delta_dist / d_o) * 100

                    v_r = metrics.get(target_col, np.nan)
                    v_o = ors.get(target_col, np.nan)

                    if strategy == 'slope':
                        v_r, v_o = abs(v_r), abs(v_o)

                    if pd.isna(v_r) or pd.isna(v_o) or v_o == 0:
                        delta_target = np.nan
                        pct_benefit = 0
                    else:
                        delta_target = v_r - v_o
                        raw = (delta_target / v_o) * 100
                        pct_benefit = -raw if minimize else raw

                    # Quadrant assignment based on cost/benefit thresholds
                    if pct_cost <= self.epsilon_cost and pct_benefit > self.epsilon_benefit:
                        quad = "I. Win-Win"
                    elif pct_cost > self.epsilon_cost and pct_benefit > self.epsilon_benefit:
                        quad = "II. High Gain"
                    elif pct_cost <= self.epsilon_cost and pct_benefit <= self.epsilon_benefit:
                        quad = "III. Status Quo"
                    else:
                        quad = "IV. Detrimental"

                    is_pareto = self._check_pareto_optimal_fixed(
                        pct_cost,
                        metrics.get("greenIndex", np.nan), ors.get("greenIndex", np.nan),
                        metrics.get("noise", np.nan), ors.get("noise", np.nan),
                        metrics.get("pm_10", np.nan), ors.get("pm_10", np.nan),
                    )

                    record = {
                        "mode": mode,
                        "strategy": strategy,
                        "delta_distance": delta_dist,
                        "pct_cost": pct_cost,
                        "pct_benefit": pct_benefit,
                        "quadrant": quad,
                        "pareto_optimal": is_pareto,
                    }

                    # Add delta/pct for all metrics to each record
                    for s_key, (m_key, is_min) in strategy_map.items():
                        m_val_r = metrics.get(m_key, np.nan)
                        m_val_o = ors.get(m_key, np.nan)

                        if m_key == "slope":
                            m_val_r, m_val_o = abs(m_val_r), abs(m_val_o)

                        if not pd.isna(m_val_r) and not pd.isna(m_val_o):
                            delta = m_val_r - m_val_o
                            record[f"delta_{m_key}"] = delta
                            if abs(m_val_o) > 0.001:
                                pct = (delta / m_val_o) * 100
                                pct = np.clip(pct, -200, 200)
                                record[f"pct_{m_key}"] = -pct if is_min else pct
                            else:
                                record[f"pct_{m_key}"] = np.nan
                        else:
                            record[f"delta_{m_key}"] = np.nan
                            record[f"pct_{m_key}"] = np.nan

                    records.append(record)

        df = pd.DataFrame(records)
        print(f"Processed {len(df)} route comparisons")
        return df

    def _check_pareto_optimal_fixed(self, pct_cost, green_r, green_o,
                                    noise_r, noise_o, pm10_r, pm10_o):
        """
        Heuristic Pareto check: weighs improvements vs. worsenings across
        green index, noise, and air quality, with cost-dependent thresholds.
        """
        if any(pd.isna(x) for x in [pct_cost, green_r, green_o,
                                      noise_r, noise_o, pm10_r, pm10_o]):
            return False

        green_imp = green_r - green_o
        noise_imp = noise_o - noise_r
        pm10_imp = pm10_o - pm10_r

        improvements = sum([
            green_imp > 0.005,
            noise_imp > 0.5,
            pm10_imp > 0.01
        ])
        worsenings = sum([
            green_imp < -0.01,
            noise_imp < -1.0,
            pm10_imp < -0.05
        ])

        if pct_cost <= 0:
            return worsenings < 3
        elif pct_cost <= 20:
            return improvements >= 1 and worsenings <= 2
        else:
            return improvements >= 2 and worsenings == 0

    # -------------------------------------------------------------------------
    # Table generation — summary stats, statistical tests, quadrant counts
    # -------------------------------------------------------------------------
    def generate_tables(self):
        """Export three CSV tables: summary stats, Wilcoxon tests, quadrant distribution."""
        print("Generating CSV tables...")

        strategy_map = {
            "green": "greenIndex", "noise": "noise", "air": "pm_10",
            "slope": "slope", "distance": "distance",
        }

        # Table 1: Summary statistics per mode/strategy
        summary_data = []
        for mode in sorted(self.df['mode'].unique()):
            for strategy in sorted(self.df['strategy'].unique()):
                subset = self.df[(self.df['mode'] == mode) & (self.df['strategy'] == strategy)]
                if len(subset) == 0:
                    continue

                target_metric = strategy_map.get(strategy, "")
                row = {
                    'Mode': mode.capitalize(),
                    'Strategy': strategy.capitalize(),
                    'N': len(subset),
                    'Distance_Median_m': subset['delta_distance'].median(),
                    'Distance_Mean_m': subset['delta_distance'].mean(),
                    'Distance_SD_m': subset['delta_distance'].std(),
                    'Distance_ImprovementRate_%': (subset['delta_distance'] <= 0).sum() / len(subset) * 100,
                }

                if target_metric and f"delta_{target_metric}" in subset.columns:
                    target_data = subset[f"delta_{target_metric}"].dropna()
                    if len(target_data) > 0:
                        is_min = strategy in ['noise', 'air', 'slope', 'distance']
                        improved = (target_data < 0).sum() if is_min else (target_data > 0).sum()
                        row[f'{strategy.capitalize()}_Median'] = target_data.median()
                        row[f'{strategy.capitalize()}_Mean'] = target_data.mean()
                        row[f'{strategy.capitalize()}_SD'] = target_data.std()
                        row[f'{strategy.capitalize()}_ImprovementRate_%'] = improved / len(target_data) * 100

                row['Pareto_Optimal_%'] = (subset['pareto_optimal']).sum() / len(subset) * 100
                summary_data.append(row)

        pd.DataFrame(summary_data).to_csv(
            f"{self.output_dir}/Table1_Summary_Statistics.csv",
            index=False, float_format='%.2f')

        # Table 2: Wilcoxon signed-rank tests with FDR correction
        stats_data = []
        for mode in sorted(self.df['mode'].unique()):
            for strategy in sorted(self.df['strategy'].unique()):
                subset = self.df[(self.df['mode'] == mode) & (self.df['strategy'] == strategy)]
                if len(subset) == 0:
                    continue

                target_metric = strategy_map.get(strategy, "")
                dist_data = subset['delta_distance'].dropna()
                if len(dist_data) >= 5:
                    try:
                        w_stat, p_val = stats.wilcoxon(dist_data)
                        n = len(dist_data)
                        r = w_stat / (n * (n + 1) / 2)
                        r = 2 * r - 1
                        r = -abs(r) if dist_data.median() < 0 else abs(r)
                        stats_data.append({
                            'Mode': mode.capitalize(), 'Strategy': strategy.capitalize(),
                            'Metric': 'Distance', 'Wilcoxon_W': w_stat,
                            'p_value': p_val, 'Effect_Size_r': r,
                            'Median_Change': dist_data.median(),
                        })
                    except Exception:
                        pass

                if target_metric and target_metric != 'distance' and f"delta_{target_metric}" in subset.columns:
                    target_data = subset[f"delta_{target_metric}"].dropna()
                    if len(target_data) >= 5:
                        try:
                            w_stat, p_val = stats.wilcoxon(target_data)
                            n = len(target_data)
                            r = w_stat / (n * (n + 1) / 2)
                            r = 2 * r - 1
                            r = -abs(r) if target_data.median() < 0 else abs(r)
                            stats_data.append({
                                'Mode': mode.capitalize(), 'Strategy': strategy.capitalize(),
                                'Metric': strategy.capitalize(), 'Wilcoxon_W': w_stat,
                                'p_value': p_val, 'Effect_Size_r': r,
                                'Median_Change': target_data.median(),
                            })
                        except Exception:
                            pass

        stats_df = pd.DataFrame(stats_data)
        if len(stats_df) > 0:
            _, p_corrected, _, _ = multipletests(stats_df['p_value'], method='fdr_bh')
            stats_df['p_value_FDR'] = p_corrected
            stats_df['Significant_FDR_0.05'] = p_corrected < 0.05
            stats_df['Significant_FDR_0.01'] = p_corrected < 0.01
        stats_df.to_csv(f"{self.output_dir}/Table2_Statistical_Tests.csv",
                        index=False, float_format='%.4f')

        # Table 3: Quadrant distribution percentages
        quad_dist = self.df.groupby(['mode', 'strategy', 'quadrant']).size().reset_index(name='count')
        quad_pct = quad_dist.pivot_table(
            index=['mode', 'strategy'], columns='quadrant', values='count', fill_value=0)
        quad_pct = quad_pct.div(quad_pct.sum(axis=1), axis=0) * 100
        quad_pct.round(1).to_csv(f"{self.output_dir}/Table3_Quadrant_Distribution.csv",
                                  float_format='%.1f')
        print("Generated tables")

    # -------------------------------------------------------------------------
    # Figure 1: Pareto optimality rates by strategy (grouped bar chart)
    # -------------------------------------------------------------------------
    def figure1_pareto_optimality(self):
        """Bar chart showing % of Pareto-optimal routes per strategy, per mode."""
        print("Generating Figure 1: Pareto Optimality...")

        modes = sorted(self.df['mode'].unique())
        strategies = sorted(self.df['strategy'].unique())

        fig, axes = plt.subplots(1, 3, figsize=(20, 7))

        for idx, mode in enumerate(modes):
            ax = axes[idx]
            pareto_rates = []
            for strategy in strategies:
                subset = self.df[(self.df['mode'] == mode) & (self.df['strategy'] == strategy)]
                rate = (subset['pareto_optimal'].sum() / len(subset) * 100 if len(subset) > 0 else 0)
                pareto_rates.append(rate)

            x = np.arange(len(strategies))
            bars = ax.bar(
                x, pareto_rates, width=0.35,
                color=[STRATEGY_COLORS.get(s, '#333333') for s in strategies],
                edgecolor='black', linewidth=1.5, alpha=0.88,
            )

            for bar, rate in zip(bars, pareto_rates):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2., height + 1.0,
                        f'{rate:.1f}%', ha='center', va='bottom',
                        fontsize=12, fontweight='bold', rotation=90)

            ax.set_ylabel("Pareto Optimal Routes (%)", fontsize=18, fontweight='bold')
            ax.set_title(mode.upper(), pad=15, fontsize=20, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels([s.capitalize() for s in strategies],
                               fontsize=14, rotation=90, ha='center')
            ax.set_ylim(0, 120)
            ax.axhline(y=90, color='green', linestyle='--', linewidth=2, alpha=0.5)
            ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(f"{self.output_dir}/Figure1_Pareto_Optimality.png",
                    bbox_inches="tight", dpi=450)
        plt.close()

    # -------------------------------------------------------------------------
    # Figure 2: Quadrant classification scatter plots
    # -------------------------------------------------------------------------
    def figure2_quadrant_classification(self):
        """Scatter plots of cost vs. benefit, colored by quadrant, faceted by strategy."""
        print("Generating Figure 2: Quadrant Classification...")

        strategies = sorted(self.df['strategy'].unique())
        palette = {
            "I. Win-Win": "#1f78b4", "II. High Gain": "#33a02c",
            "III. Status Quo": "#7f7f7f", "IV. Detrimental": "#e31a1c",
        }

        n_strat = len(strategies)
        cols, rows = 2, (n_strat + 1) // 2
        fig = plt.figure(figsize=(16, 6 * rows))
        gs = fig.add_gridspec(rows, cols, hspace=0.3, wspace=0.2)

        df_clean = self.df[
            (self.df['pct_cost'] > -10) & (self.df['pct_cost'] < 50) &
            (self.df['pct_benefit'] > -15) & (self.df['pct_benefit'] < 80)
        ]

        axes = []
        for i in range(rows):
            for j in range(cols):
                if i * cols + j < n_strat:
                    axes.append(fig.add_subplot(gs[i, j]))

        for i, strat in enumerate(strategies):
            ax = axes[i]
            subset = df_clean[df_clean['strategy'] == strat]
            if subset.empty:
                ax.text(0.5, 0.5, "No Data", ha='center', fontsize=16)
                continue

            for quad, color in palette.items():
                quad_data = subset[subset['quadrant'] == quad]
                for mode in ['walk', 'cycle', 'drive']:
                    mode_data = quad_data[quad_data['mode'] == mode]
                    if len(mode_data) > 0:
                        marker = 'o' if mode == 'walk' else ('X' if mode == 'cycle' else 's')
                        ms = 50 if mode == 'walk' else (60 if mode == 'cycle' else 50)
                        ax.scatter(mode_data['pct_cost'], mode_data['pct_benefit'],
                                   c=color, marker=marker, s=ms,
                                   alpha=0.7, edgecolors='black', linewidth=0.5)

            ax.axvline(0, color='black', lw=2)
            ax.axhline(0, color='black', lw=2)
            ax.axvline(self.epsilon_cost, color='blue', linestyle=':', lw=2, alpha=0.7)
            ax.axhline(self.epsilon_benefit, color='blue', linestyle=':', lw=2, alpha=0.7)
            mx, my = subset['pct_cost'].median(), subset['pct_benefit'].median()
            ax.axvline(mx, color='gray', linestyle='--', lw=2, alpha=0.8)
            ax.axhline(my, color='gray', linestyle='--', lw=2, alpha=0.8)

            ax.set_title(strat.upper(), pad=15, fontsize=20, fontweight='bold')
            if i >= len(strategies) - 2:
                ax.set_xlabel("Distance Cost (%)", fontsize=16, fontweight='bold')
            if i % 2 == 0:
                ax.set_ylabel("Environmental Benefit (%)", fontsize=16, fontweight='bold')

        # Legends
        quad_handles = [mpatches.Patch(color=c, label=l) for l, c in palette.items()]
        mode_handles = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                   markersize=10, markeredgecolor='black', linewidth=1.5, label='Walk'),
            Line2D([0], [0], marker='X', color='w', markerfacecolor='gray',
                   markersize=11, markeredgecolor='black', linewidth=1.5, label='Cycle'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor='gray',
                   markersize=10, markeredgecolor='black', linewidth=1.5, label='Drive'),
        ]
        line_handles = [
            Line2D([0], [0], color='black', lw=2.5, label='Zero'),
            Line2D([0], [0], color='blue', linestyle=':', lw=2.5, label='Threshold'),
            Line2D([0], [0], color='gray', linestyle='--', lw=2.5, label='Median'),
        ]
        fig.legend(handles=quad_handles + mode_handles + line_handles,
                   loc="upper center", bbox_to_anchor=(0.5, 1.0),
                   ncol=5, frameon=True, fontsize=14)

        plt.savefig(f"{self.output_dir}/Figure2_Quadrant_Classification.png",
                    bbox_inches="tight", dpi=450)
        plt.close()

    # -------------------------------------------------------------------------
    # Figure 3: Synergy heatmap (median % change per metric/strategy/mode)
    # -------------------------------------------------------------------------
    def figure3_synergy_matrix(self):
        """Heatmap of median % improvements across metrics, strategies, and modes."""
        print("Generating Figure 3: Synergy Matrix...")

        metrics = ['pct_distance', 'pct_greenIndex', 'pct_noise', 'pct_pm_10']
        labels = ['Distance', 'Green Index', 'Noise', 'Air Quality']
        modes = sorted(self.df['mode'].unique())

        # Compute data-driven color scale bounds
        all_vals = []
        for mode in modes:
            subset = self.df[self.df['mode'] == mode].copy()
            subset['pct_distance'] = -subset['pct_cost']
            grouped = subset.groupby('strategy')[metrics].median()
            grouped = grouped.applymap(lambda x: 0.0 if abs(x) < 0.05 else x)
            all_vals.extend(grouped.values.flatten().tolist())

        all_vals = [v for v in all_vals if not np.isnan(v)]
        vmin, vmax = min(all_vals), max(all_vals)
        if vmax - vmin < 1.0:
            vmin -= 0.5
            vmax += 0.5

        fig, axes = plt.subplots(1, len(modes), figsize=(18, 7))

        for i, mode in enumerate(modes):
            subset = self.df[self.df['mode'] == mode].copy()
            subset['pct_distance'] = -subset['pct_cost']
            grouped = subset.groupby('strategy')[metrics].median().sort_index()
            grouped = grouped.applymap(lambda x: 0.0 if abs(x) < 0.05 else x)

            sns.heatmap(grouped, annot=True, fmt=".1f", cmap="RdYlGn", center=0,
                        vmin=vmin, vmax=vmax, ax=axes[i],
                        cbar=(i == len(modes) - 1), linewidths=2, linecolor='white',
                        annot_kws={"size": 14, "weight": "bold"},
                        cbar_kws={"label": "% Improvement", "shrink": 0.8})

            axes[i].set_title(mode.upper(), pad=15, fontsize=18, fontweight='bold')
            axes[i].set_xticklabels(labels, rotation=0, fontsize=16)
            axes[i].set_yticklabels([s.capitalize() for s in grouped.index],
                                     rotation=0, fontsize=16) if i == 0 else axes[i].set_yticklabels([])
            axes[i].set_ylabel("")
            if i == len(modes) - 1:
                cbar = axes[i].collections[0].colorbar
                if cbar:
                    cbar.set_label("% Improvement", fontsize=18, weight='bold')

        plt.tight_layout()
        plt.savefig(f"{self.output_dir}/Figure3_Synergy_Matrix.png",
                    bbox_inches="tight", dpi=450)
        plt.close()

    # -------------------------------------------------------------------------
    # Figure 4: Violin plots of benefit distributions per strategy/mode
    # -------------------------------------------------------------------------
    def figure4_distribution_heterogeneity(self):
        """Violin plots showing distribution of environmental benefits by mode."""
        print("Generating Figure 4: Distribution Heterogeneity...")

        strategies = sorted(self.df['strategy'].unique())
        cols, rows = 2, (len(strategies) + 1) // 2
        fig, axes = plt.subplots(rows, cols, figsize=(16, 6 * rows))
        axes = axes.flatten()
        colors = {"walk": "#2ecc71", "cycle": "#3498db", "drive": "#e74c3c"}

        for i, strat in enumerate(strategies):
            ax = axes[i]
            subset = self.df[self.df['strategy'] == strat]
            benefit_data = []
            for mode in ['walk', 'cycle', 'drive']:
                mode_data = subset[subset['mode'] == mode]['pct_benefit'].dropna()
                if len(mode_data) > 0:
                    Q1, Q3 = mode_data.quantile(0.25), mode_data.quantile(0.75)
                    IQR = Q3 - Q1
                    cleaned = mode_data[(mode_data >= Q1 - 2.5*IQR) & (mode_data <= Q3 + 2.5*IQR)]
                    benefit_data.append(cleaned)
                else:
                    benefit_data.append(pd.Series([]))

            if any(len(d) > 0 for d in benefit_data):
                parts = ax.violinplot(benefit_data, positions=[0, 1, 2],
                                      showmeans=True, showextrema=True, widths=0.7)
                for j, pc in enumerate(parts['bodies']):
                    mode = ['walk', 'cycle', 'drive'][j]
                    pc.set_facecolor(colors[mode])
                    pc.set_alpha(0.7)
                    pc.set_edgecolor('black')
                    pc.set_linewidth(1.5)
                for partname in ('cbars', 'cmins', 'cmaxes', 'cmeans'):
                    vp = parts[partname]
                    vp.set_edgecolor('black')
                    vp.set_linewidth(2)

            ax.axhline(0, color='black', linestyle=':', linewidth=2, alpha=0.5)
            ax.axhline(self.epsilon_benefit, color='green', linestyle='--',
                       linewidth=2, alpha=0.6, label=f'{self.epsilon_benefit}% threshold')
            ax.set_title(strat.upper(), pad=15, fontsize=18, fontweight='bold')
            ax.set_xticks([0, 1, 2])
            ax.set_xticklabels(['Walk', 'Cycle', 'Drive'], fontsize=14)
            ax.set_ylabel("Environmental Benefit (%)", fontsize=15, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            if i == 0:
                ax.legend(loc='upper right', fontsize=13, frameon=True)

        for j in range(len(strategies), len(axes)):
            axes[j].axis('off')

        plt.tight_layout()
        plt.savefig(f"{self.output_dir}/Figure4_Distribution_Heterogeneity.png",
                    bbox_inches="tight", dpi=450)
        plt.close()

    # -------------------------------------------------------------------------
    # Figure 5: Effect size plot (Wilcoxon r values, FDR-corrected)
    # -------------------------------------------------------------------------
    def figure5_effect_sizes(self):
        """Dot plot of standardized effect sizes for significant results only."""
        print("Generating Figure 5: Effect Sizes...")

        stats_data = []
        strategy_map = {
            "green": ("greenIndex", False), "noise": ("noise", True),
            "air": ("pm_10", True), "slope": ("slope", True),
            "distance": ("distance", True),
        }

        for mode in sorted(self.df['mode'].unique()):
            for strategy in sorted(self.df['strategy'].unique()):
                subset = self.df[(self.df['mode'] == mode) & (self.df['strategy'] == strategy)]
                if len(subset) == 0:
                    continue
                target_metric, is_minimize = strategy_map.get(strategy, ("", False))

                # Distance side-effect
                dist_data = subset['delta_distance'].dropna()
                if len(dist_data) >= 5:
                    try:
                        w_stat, p_val = stats.wilcoxon(dist_data)
                        n = len(dist_data)
                        r = w_stat / (n * (n + 1) / 2)
                        r = 2 * r - 1
                        r = abs(r) if dist_data.median() < 0 else -abs(r)
                        stats_data.append({
                            'Mode': mode, 'Strategy': strategy,
                            'Metric': 'Distance', 'Effect_r': r, 'p_value': p_val,
                        })
                    except Exception:
                        pass

                # Target metric effect
                if target_metric and target_metric != 'distance' and f"delta_{target_metric}" in subset.columns:
                    target_data = subset[f"delta_{target_metric}"].dropna()
                    if len(target_data) >= 5:
                        try:
                            w_stat, p_val = stats.wilcoxon(target_data)
                            n = len(target_data)
                            r = w_stat / (n * (n + 1) / 2)
                            r = 2 * r - 1
                            if is_minimize:
                                r = abs(r) if target_data.median() < 0 else -abs(r)
                            else:
                                r = abs(r) if target_data.median() > 0 else -abs(r)
                            stats_data.append({
                                'Mode': mode, 'Strategy': strategy,
                                'Metric': strategy.capitalize(),
                                'Effect_r': r, 'p_value': p_val,
                            })
                        except Exception:
                            pass

        if not stats_data:
            print("No statistical data")
            return

        stats_df = pd.DataFrame(stats_data)
        _, p_corrected, _, _ = multipletests(stats_df['p_value'], method='fdr_bh')
        stats_df['p_corrected'] = p_corrected
        stats_df = stats_df[stats_df['p_corrected'] < 0.05]
        if len(stats_df) == 0:
            print("No significant effects")
            return

        stats_df['Label'] = stats_df['Strategy'].str.capitalize() + ' → ' + stats_df['Metric']
        stats_df['abs_r'] = stats_df['Effect_r'].abs()
        order = stats_df.groupby('Label')['abs_r'].mean().sort_values(ascending=True).index

        fig, ax = plt.subplots(figsize=(12, 12))
        colors = {"walk": "#66c2a5", "cycle": "#fc8d62", "drive": "#8da0cb"}
        markers = {"walk": "o", "cycle": "s", "drive": "^"}

        for i, label in enumerate(order):
            ax.axhline(y=i, color='lightgray', alpha=0.3, zorder=1)

        for mode in ["walk", "cycle", "drive"]:
            mode_data = stats_df[stats_df['Mode'] == mode]
            mode_data = mode_data.set_index('Label').reindex(order).reset_index().dropna(subset=['Effect_r'])
            y_indices = [list(order).index(lbl) for lbl in mode_data['Label']]
            ax.scatter(mode_data['Effect_r'], y_indices,
                       c=colors[mode], marker=markers[mode], s=150,
                       edgecolor='black', linewidth=1.5, label=mode.capitalize(), zorder=3)
            for r_val, y_idx, p_val in zip(mode_data['Effect_r'], y_indices, mode_data['p_corrected']):
                x_off = 0.04 if r_val > 0 else -0.04
                sig = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else ""))
                if sig:
                    ax.text(r_val + x_off, y_idx, sig, ha='center', va='center', fontsize=10, weight='bold')

        ax.set_yticks(range(len(order)))
        ax.set_yticklabels(order, fontsize=12)
        ax.axvline(0, color='black', linewidth=2.5)
        ax.axvline(-0.3, color='orange', linestyle=':', linewidth=1.5, alpha=0.5)
        ax.axvline(0.3, color='orange', linestyle=':', linewidth=1.5, alpha=0.5)
        ax.axvline(-0.5, color='red', linestyle='--', linewidth=1.5, alpha=0.5)
        ax.axvline(0.5, color='red', linestyle='--', linewidth=1.5, alpha=0.5)
        ax.set_xlabel("Effect Size (Standardized)\n← Detrimental | Beneficial →",
                      fontsize=15, fontweight='bold')
        ax.set_title("Statistical Effect Sizes (Positive = Improvement)\nFDR-corrected p < 0.05",
                     pad=20, fontsize=18, fontweight='bold')

        leg_handles = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor=colors['walk'],
                   markersize=10, markeredgecolor='black', linewidth=1.5, label='Walk'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor=colors['cycle'],
                   markersize=10, markeredgecolor='black', linewidth=1.5, label='Cycle'),
            Line2D([0], [0], marker='^', color='w', markerfacecolor=colors['drive'],
                   markersize=10, markeredgecolor='black', linewidth=1.5, label='Drive'),
            Line2D([0], [0], color='orange', linestyle=':', linewidth=2, label='Medium (|r|=0.3)'),
            Line2D([0], [0], color='red', linestyle='--', linewidth=2, label='Large (|r|=0.5)'),
        ]
        ax.legend(handles=leg_handles, loc='lower right', fontsize=12, frameon=True)
        ax.grid(axis='x', alpha=0.3)
        ax.set_xlim(-1.05, 1.05)

        plt.tight_layout()
        plt.savefig(f"{self.output_dir}/Figure5_Effect_Sizes.png",
                    bbox_inches="tight", dpi=450)
        plt.close()

    # -------------------------------------------------------------------------
    # Combined figure: 3x2 grid with violin plots + Pareto summary
    # -------------------------------------------------------------------------
    def figure_combined_violin_pareto(self):
        """
        Composite figure: 3 rows × 2 columns.
        Cells 0-4: violin plots per strategy (labeled a–e).
        Cell 5: grouped Pareto bar chart (labeled f).
        """
        print("Generating Combined Figure (3×2: Violin + Pareto)...")

        strategies = sorted(self.df['strategy'].unique())
        modes = sorted(self.df['mode'].unique())
        violin_colors = {"walk": "#2ecc71", "cycle": "#3498db", "drive": "#e74c3c"}
        panel_labels = list("abcdef")

        fig, axes = plt.subplots(3, 2, figsize=(20, 26))
        axes_flat = axes.flatten()

        # Violin subplots (cells 0-4)
        for i, strat in enumerate(strategies):
            ax = axes_flat[i]
            subset = self.df[self.df['strategy'] == strat]
            benefit_data = []
            for mode in ['walk', 'cycle', 'drive']:
                mode_data = subset[subset['mode'] == mode]['pct_benefit'].dropna()
                if len(mode_data) > 0:
                    Q1, Q3 = mode_data.quantile(0.25), mode_data.quantile(0.75)
                    IQR = Q3 - Q1
                    cleaned = mode_data[(mode_data >= Q1 - 2.5*IQR) & (mode_data <= Q3 + 2.5*IQR)]
                    benefit_data.append(cleaned)
                else:
                    benefit_data.append(pd.Series([]))

            if any(len(d) > 0 for d in benefit_data):
                parts = ax.violinplot(benefit_data, positions=[0, 1, 2],
                                      showmeans=True, showextrema=True, widths=0.7)
                for j, pc in enumerate(parts['bodies']):
                    mode = ['walk', 'cycle', 'drive'][j]
                    pc.set_facecolor(violin_colors[mode])
                    pc.set_alpha(0.7)
                    pc.set_edgecolor('black')
                    pc.set_linewidth(1.5)
                for partname in ('cbars', 'cmins', 'cmaxes', 'cmeans'):
                    vp = parts[partname]
                    vp.set_edgecolor('black')
                    vp.set_linewidth(2)

            ax.axhline(0, color='black', linestyle=':', linewidth=2, alpha=0.5)
            ax.axhline(self.epsilon_benefit, color='green', linestyle='--',
                       linewidth=2.5, alpha=0.7)
            ax.text(0.02, 0.97, f'({panel_labels[i]})', transform=ax.transAxes,
                    fontsize=20, fontweight='bold', va='top', ha='left')
            ax.set_title(strat.upper(), pad=12, fontsize=20, fontweight='bold')
            ax.set_xticks([0, 1, 2])
            ax.set_xticklabels(['Walk', 'Cycle', 'Drive'], fontsize=17)
            ax.set_ylabel("Environmental Benefit (%)", fontsize=18, fontweight='bold')
            ax.tick_params(axis='y', labelsize=16)
            ax.grid(axis='y', alpha=0.3)
            if i == 0:
                violin_handles = [
                    mpatches.Patch(facecolor=violin_colors[m], edgecolor='black', label=m.capitalize())
                    for m in ['walk', 'cycle', 'drive']
                ]
                violin_handles += [
                    Line2D([0], [0], color='green', linestyle='--', lw=2.5,
                           label=f'{self.epsilon_benefit}% threshold'),
                    Line2D([0], [0], color='black', linestyle=':', lw=2, label='Zero line'),
                ]
                ax.legend(handles=violin_handles, loc='upper right', fontsize=16, frameon=True)

        # Pareto subplot (cell 5)
        ax_p = axes_flat[5]
        bar_width, bar_step, group_gap = 0.08, 0.13, 0.45
        group_w = len(strategies) * bar_step + group_gap
        x_centers = np.arange(len(modes)) * group_w
        offsets = np.linspace(-(len(strategies)-1)/2 * bar_step,
                               (len(strategies)-1)/2 * bar_step, len(strategies))

        for s_idx, strategy in enumerate(strategies):
            rates = []
            for mode in modes:
                subset = self.df[(self.df['mode'] == mode) & (self.df['strategy'] == strategy)]
                rate = (subset['pareto_optimal'].sum() / len(subset) * 100 if len(subset) > 0 else 0)
                rates.append(rate)
            ax_p.bar(x_centers + offsets[s_idx], rates, width=bar_width,
                     color=STRATEGY_COLORS.get(strategy, '#333333'),
                     edgecolor='#888888', linewidth=0.4, alpha=0.88,
                     label=strategy.capitalize())

        ax_p.axhline(y=90, color='green', linestyle='--', linewidth=2.2,
                     alpha=0.7, label='90% threshold')
        ax_p.set_xticks(x_centers)
        ax_p.set_xticklabels([m.capitalize() for m in modes], fontsize=16, ha='center')
        ax_p.set_ylabel("Pareto Optimal Routes (%)", fontsize=17, fontweight='bold')
        ax_p.set_title("PARETO OPTIMALITY", pad=15, fontsize=20, fontweight='bold')
        ax_p.set_ylim(0, 115)
        ax_p.tick_params(axis='y', labelsize=15)
        ax_p.grid(axis='y', alpha=0.3)
        ax_p.text(0.02, 0.97, '(f)', transform=ax_p.transAxes,
                  fontsize=20, fontweight='bold', va='top', ha='left')

        handles_p, labels_p = ax_p.get_legend_handles_labels()
        ax_p.legend(handles=handles_p, labels=labels_p, loc='upper center',
                    bbox_to_anchor=(0.5, 0.96), ncol=3, fontsize=15,
                    frameon=True, handlelength=1.4, columnspacing=0.9)

        plt.tight_layout()
        plt.savefig(f"{self.output_dir}/Figure_Combined_Violin_Pareto.png",
                    bbox_inches="tight", dpi=450)
        plt.close()

    # -------------------------------------------------------------------------
    # Run everything
    # -------------------------------------------------------------------------
    def run_complete_analysis(self):
        """Execute full pipeline: tables + all figures."""
        print("\n" + "=" * 70)
        print("FINAL ANALYSIS - WITH DISTANCE STRATEGY INCLUDED")
        print("=" * 70 + "\n")

        self.generate_tables()
        self.figure1_pareto_optimality()
        self.figure2_quadrant_classification()
        self.figure3_synergy_matrix()
        self.figure4_distribution_heterogeneity()
        self.figure5_effect_sizes()
        self.figure_combined_violin_pareto()

        print("\n" + "=" * 70)
        print("COMPLETE")
        print("=" * 70)
        print(f"\nResults in: {os.path.abspath(self.output_dir)}\n")


# -----------------------------------------------------------------------------
# CLI entry point
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Route optimization analysis pipeline")
    parser.add_argument("--input", "-i", default="routing_results.json",
                        help="Path to input JSON file")
    parser.add_argument("--output", "-o", default="final_results",
                        help="Output directory for tables and figures")
    parser.add_argument("--epsilon-cost", type=float, default=5.0,
                        help="Cost threshold (%) for quadrant classification")
    parser.add_argument("--epsilon-benefit", type=float, default=3.0,
                        help="Benefit threshold (%) for quadrant classification")
    args = parser.parse_args()

    analyzer = FinalRouteAnalysis(
        json_path=args.input,
        output_dir=args.output,
        epsilon_cost=args.epsilon_cost,
        epsilon_benefit=args.epsilon_benefit,
    )
    analyzer.run_complete_analysis()


if __name__ == "__main__":
    main()