#!/usr/bin/env bash
# Runs the 6-value slope sweep against the clamped-slope build, where
# CustomEdge.getSlope() returns max(0, slope) so descents are treated as
# flat everywhere in the system.
#
# Writes to results_splitted/slope_raw/ and never touches the existing
# routing_mode_slope/ data.

set -uo pipefail

OUT=/mnt/data/routify-sweep/results_splitted/slope_raw
LOGS=/mnt/data/routify-sweep/logs
SCRIPT=/home/aeggerth/routify/jupyter/ComputeSweepRouting.py

mkdir -p "$OUT" "$LOGS"

echo "=== slope_raw sweep started $(date -Is) ==="
python3 -u "$SCRIPT" --param slope --outdir "$OUT" 2>&1 \
    | tee -a "$LOGS/run_slope_raw.log"
rc=${PIPESTATUS[0]}
if [ "$rc" -ne 0 ]; then
    echo "=== slope_raw FAILED (rc=$rc) $(date -Is) ==="
else
    echo "=== slope_raw COMPLETE $(date -Is) ==="
fi
echo "=== finished $(date -Is) ==="
