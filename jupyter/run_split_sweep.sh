#!/usr/bin/env bash
# Runs the full sensitivity sweep one routing mode at a time, writing each
# mode into its own subfolder of results_splitted/.
#
# Sequential by mode (each mode is still parallelised across the 4 backend
# replicas internally) so that per-mode progress is meaningful and each
# folder is complete before the next mode starts.
#
#   air first: it is the mode that previously failed, so it gets verified
#   earliest in the run.

set -uo pipefail

BASE=/mnt/data/routify-sweep/results_splitted
LOGS=/mnt/data/routify-sweep/logs
SCRIPT=/home/aeggerth/routify/jupyter/ComputeSweepRouting.py

mkdir -p "$LOGS"

# param:mode-folder
PASSES=(
  "air:routing_mode_air"
  "slope:routing_mode_slope"
  "green_index:routing_mode_green"
  "noise:routing_mode_noise"
)

echo "=== split sweep started $(date -Is) ==="

for entry in "${PASSES[@]}"; do
    param="${entry%%:*}"
    folder="${entry##*:}"
    out="$BASE/$folder"
    mkdir -p "$out"

    echo ""
    echo "=== PASS $folder (param=$param) starting $(date -Is) ==="
    python3 -u "$SCRIPT" --param "$param" --outdir "$out" 2>&1 \
        | tee -a "$LOGS/run_${folder}.log"
    rc=${PIPESTATUS[0]}
    if [ "$rc" -ne 0 ]; then
        echo "=== PASS $folder FAILED (rc=$rc) $(date -Is) ==="
    else
        echo "=== PASS $folder COMPLETE $(date -Is) ==="
    fi
done

echo ""
echo "=== split sweep finished $(date -Is) ==="
