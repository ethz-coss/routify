# README — Parameter Sensitivity Sweep

How the sensitivity-analysis datasets were generated, including the
`slope_raw` variant. Companion to `extended_experiment_setup.txt`, which
argues *why* these parameter values were chosen; this file documents *how*
the runs were executed so they can be reproduced.

All runs described here were executed on the ETH dev-server against a local
Routify stack, writing to the NVMe volume at `/mnt/data/routify-sweep/`.

---

## 1) Scripts

| file | role |
|---|---|
| `ComputeSweepRouting.py` | sweep generator; same output format as `ComputeFullRouting_v4.py` |
| `run_split_sweep.sh` | driver — runs all four routing modes sequentially into per-mode folders |
| `run_slope_raw.sh` | driver — runs the slope mode only, against the clamped-slope build |
| `PostProcessSweep.py` | reduction driver; imports `PostProcessDataFull.py` unchanged |
| `SlopeDistribution.py` | slope distribution figure, from `GET /status/graph/` |

`ComputeSweepRouting.py` differs from `ComputeFullRouting_v4.py` in three
ways: it sweeps 6 values per parameter instead of one default set, it spreads
requests round-robin across several backend replicas concurrently, and it
checkpoints per batch so an interrupted run resumes. The record format is
unchanged, so `PostProcessDataFull.py` consumes the output as-is.

---

## 2) Parameters swept

Defaults for every non-swept parameter, in every record:

    green_index = 50, slope = 10, noise = 50, air = 50

| routing mode | parameter | values |
|---|---|---|
| `routing_mode_slope` | `slope` | 30, 19, 10, 7, 3, 0 |
| `routing_mode_green` | `green_index` | 0, 10, 25, 50, 75, 100 |
| `routing_mode_noise` | `noise` | 0, 10, 25, 50, 75, 100 |
| `routing_mode_air` | `air` | 0, 10, 25, 50, 75, 100 |

The slope values are the Jenks natural-break upper edges of the *uphill*
slope distribution; the impact values are an even ramp. Both series include
the pre-existing default (slope = 10, impact = 50), so each sweep passes
through the original operating point.

**The two families are not comparable.** `slope` is a THRESHOLD in percent
grade — edges steeper than the value are penalised, the rest are untouched,
so *lower* means stricter. `green_index` / `noise` / `air` are IMPACT
MULTIPLIERS on [0,100] — 0 disables the operation entirely (reducing the
route to pure distance), 100 is maximum weighting.

---

## 3) Backend replicas

The sweep is CPU-bound, not GC-bound: measured throughput was ~1.3–1.9 req/s
and did not improve with a larger heap. Four replicas were used mainly to
keep all cores busy.

```bash
# build once
docker compose build backend

# four replicas on 8091-8094, all on the compose network
for n in 1 2 3 4; do
  docker run -d --name routify-sweep-$n \
    --network routify_routify-network \
    -p 809$n:8080 \
    -e JAVA_TOOL_OPTIONS="-Xms2g -Xmx4500m" \
    routify-backend:latest
done
```

`ComputeSweepRouting.py` targets `localhost:8091..8094` (constant `BACKENDS`),
8 concurrent workers, 25 O/D pairs per output file.

### Verify before dispatching — do not skip

An earlier air-quality sweep was invalidated because the
`airqualityservice` container had **no networks attached**, so every edge
carried `pm_10 = 0.0` and `aqius = -1.0`. The backend logged
`java.net.UnknownHostException: airqualityservice` at startup and the run
proceeded anyway. Check all three gates:

```bash
# 1) graph loaded on every replica (expect 438457 edges / 200012 vertices)
for n in 1 2 3 4; do curl -s http://localhost:809$n/status/; echo; done

# 2) PM10 actually loaded — read the startup log, do not assume
docker logs routify-sweep-1 2>&1 | grep -iE "pm_?10|airqual|UnknownHost"
#    want: "PM10 values have been updated"
#    NOT:  "UnknownHostException: airqualityservice"

# 3) if the service was started late, attach it to the network
docker network connect --alias airqualityservice \
  routify_routify-network routify-airqualityservice-1
```

A fourth gate is worth the two minutes: run a handful of pairs and confirm
the swept parameter actually changes the route. A mode that returns an
identical route at every slider value is a red flag — that is exactly how
the broken air run was caught (1/6 distinct routes, versus 6/6 for slope).

---

## 4) Running the sweep

`run_split_sweep.sh` runs the four modes one after another, each into its own
folder, so a mode is complete before the next starts. Air runs first because
it is the mode that previously failed, and so gets verified earliest.

```bash
cd jupyter
bash run_split_sweep.sh          # ~9 h for all four modes
```

Per mode it calls:

```bash
python3 -u ComputeSweepRouting.py --param air --outdir /mnt/data/routify-sweep/results_splitted/routing_mode_air
```

Useful flags:

```bash
python3 ComputeSweepRouting.py --limit 8      # smoke test on 8 pairs
python3 ComputeSweepRouting.py --bench 48     # throughput benchmark only
python3 ComputeSweepRouting.py --workers 12   # override concurrency
```

`--outdir` also relocates `_checkpoint.json`, so each mode checkpoints
independently and a rerun into a fresh folder starts clean.

**Result:** 2 000 pairs × 6 values × 4 modes = 48 000 requests, 9.05 h,
0 errors, 57 GB across `results_splitted/routing_mode_{air,slope,green,noise}/`.

---

## 5) The `slope_raw` variant

### What it is

`SlopeOperation` compares the **signed** slope against the threshold:

```java
double limit = context.requireDouble(thresholdField) / 100.0;
double slope = Math.abs(edge.getSlope());
if (edge.getSlope() > limit) {                     // signed, not abs
    weight += penaltyMultiplier * edge.getDistance() * (1 + slope);
}
```

Since `limit = slider/100 >= 0` for every value in the sweep, descents can
never satisfy the test. Slope avoidance is therefore **asymmetric**: climbs
are penalised, descents never are. The `Math.abs()` on the line above only
scales the penalty magnitude and is a no-op for any edge that passes the
test.

`slope_raw` is the dataset where that asymmetry is also reflected in the
*reported* slope, by clamping negatives to zero system-wide.

### The temporary code change

Every consumer — `SlopeOperation`, the route JSON, the graph export — reads
the slope through one getter, so one edit covers all of them.
`backend/src/main/java/ch/routify/graph/CustomEdge.java`:

```java
public double getSlope() {
    return Math.max(0.0, slope);    // TEMPORARY: slope_raw variant
}
```

**This change is not committed and must be reverted after the run.** Tag both
images so either build is one command away:

```bash
docker tag routify-backend:latest routify-backend:signed-slope   # before
docker compose build backend
docker tag routify-backend:latest routify-backend:clamped-slope  # after
# restore afterwards:
docker tag routify-backend:signed-slope routify-backend:latest
```

Recreate the four replicas from the clamped image before running, and stop
them afterwards — replicas left running on the clamped build will silently
serve clamped slopes to anything else that queries them.

### Running it

```bash
cd jupyter
bash run_slope_raw.sh            # ~2.25 h
```

which is:

```bash
python3 -u ComputeSweepRouting.py --param slope \
    --outdir /mnt/data/routify-sweep/results_splitted/slope_raw
```

**Result:** 12 000 requests, 2.25 h, 0 errors, 15 GB, 80 batches. Validated:
12 000 records, 2 000 contiguous pairs, 2 000 per slider value, 36 000 routes,
15 834 324 edges, **zero negative slopes**, `pm_10` 8.00–15.00 with no zeros.

### Routes do not change

Clamping descents to zero **does not move a single route** — it cannot, since
descents already failed the threshold test. Confirmed four ways:

- 450/450 route-identity match (edge id sequences) on batch 001
- total edge count across all 36 000 routes identical to the signed run
  (15 834 324)
- mean distance matches in all 18 slider × transport cells
- analytically, from the predicate above

What changes is the slope **attribute**, and therefore the reduced metric.

---

## 6) Reduction

`PostProcessSweep.py` applies `PostProcessDataFull.py`'s reduction to every
batch file in a folder, writing to a separate output folder so the raw data
is untouched.

```bash
cd jupyter
python3 -u PostProcessSweep.py \
  --in  /mnt/data/routify-sweep/results_splitted/slope_raw \
  --out /mnt/data/routify-sweep/results_split_reduced/slope_raw_reduced
```

Repeat per mode. ~4 min and ~18 MB per mode (80 files, 12 000 routes).
`--force` reprocesses files whose output already exists; without it existing
outputs are skipped, so an interrupted reduction resumes.

---

## 7) Output layout

```
/mnt/data/routify-sweep/
├── results_splitted/                 raw sweep output, 74 GB
│   ├── routing_mode_air/             80 batch files, 15 GB
│   ├── routing_mode_slope/           80 batch files, 15 GB
│   ├── routing_mode_green/           80 batch files, 15 GB
│   ├── routing_mode_noise/           80 batch files, 14 GB
│   └── slope_raw/                    80 batch files, 15 GB
├── results_split_reduced/            reduced metrics, ~18 MB per mode
│   ├── routing_mode_air/  routing_mode_slope/
│   ├── routing_mode_green/ routing_mode_noise/
│   └── slope_raw_reduced/
└── logs/                             run logs and errors_<date>.tsv
```

Batch files are `routing_results_<YYYYMMDD>_batch<NNN>_<start>-<end>.json`,
25 O/D pairs each. They are standard JSON arrays written one compact record
per line — `json.load()` returns exactly the same object as an indented file,
but the file is ~5× smaller, which matters at this volume. For very large
files, stream instead:

```python
with open(path) as f:
    for line in f:
        line = line.strip().rstrip(",")
        if line.startswith("{"):
            rec = json.loads(line)
```

See `/mnt/data/routify-sweep/example/README.txt` for the full record and
edge schema, with a single-pair sample.

---

## 8) Gotchas

**The reduced `slope` metric cancels itself in the signed datasets.**
`PostProcessDataFull.py` computes `sum(slope × distance) / total_distance` on
the *signed* value, so climbs and descents cancel and the result collapses
toward (net elevation change)/(distance) — near-constant across sliders,
because origin and destination are fixed. Measured over 2 000 pairs (walk):

| slider | signed mean slope | clamped (`slope_raw`) | mean distance |
|---|---|---|---|
| 30 | +0.000613 | 0.017671 | 6 456 m |
| 19 | +0.000297 | 0.016819 | 6 594 m |
| 10 | −0.000334 | 0.015266 | 6 965 m |
| 7  | −0.000731 | 0.013960 | 7 367 m |
| 3  | −0.000496 | 0.013377 | 7 973 m |
| 0  | +0.000167 | 0.018025 | 7 678 m |

The signed column oscillates around zero with no ordering and carries no
information about the slider. The clamped column is a genuine dose-response
curve: tightening 30 → 3 cuts the mean climb rate 24% and pays for it with
23% more distance. **Use `slope_raw_reduced/` for any slope-exposure
analysis**; the signed column is only meaningful as a net-elevation check.

**Slider 0 is a different objective, not the extreme of the series.** The
mean climb rate jumps back up at slider 0 while distance falls. This follows
from the penalty `20 × distance × (1 + slope)`: at sliders 3–30 the router
escapes onto gentler sub-threshold climbs, but at 0 *every* uphill edge is
penalised, so gentleness no longer helps and the only way to cut cost is to
minimise uphill **distance**. A short steep climb then beats a long gentle
one. Do not read the six values as a monotone series through this point.

**Transport-mode keys are doubled in reduced files.**
`PostProcessDataFull.py` builds `f"transport_mode_{tm}"` where `tm` is
already `transport_mode_walk`, yielding
`transport_mode_transport_mode_walk`. This affects all reduced folders
consistently and was left as-is for parity; analysis code needs the doubled
prefix.

**Zero-length edges report `slope = -1`.** `CustomEdge.calculateSlope()`
returns early when `distance == 0` without assigning the field, so it keeps
its initialiser of `-1`. Harmless for routing (the penalty term is multiplied
by a zero distance), but it will show up in any raw edge-attribute histogram.

---

## 9) Reproducing from scratch

```bash
# 1) stack up, replicas built and verified (section 3)
docker compose build backend
for n in 1 2 3 4; do docker run -d --name routify-sweep-$n \
  --network routify_routify-network -p 809$n:8080 \
  -e JAVA_TOOL_OPTIONS="-Xms2g -Xmx4500m" routify-backend:latest; done
#    then run all verification gates in section 3

# 2) main sweep, ~9 h
cd jupyter && bash run_split_sweep.sh

# 3) slope_raw variant, ~2.25 h
#    apply the CustomEdge.getSlope() clamp, rebuild, recreate replicas
bash run_slope_raw.sh
#    revert the clamp, restore routify-backend:latest, stop the replicas

# 4) reduce each mode, ~4 min each
for m in routing_mode_air routing_mode_slope routing_mode_green routing_mode_noise; do
  python3 -u PostProcessSweep.py \
    --in  /mnt/data/routify-sweep/results_splitted/$m \
    --out /mnt/data/routify-sweep/results_split_reduced/$m
done
python3 -u PostProcessSweep.py \
  --in  /mnt/data/routify-sweep/results_splitted/slope_raw \
  --out /mnt/data/routify-sweep/results_split_reduced/slope_raw_reduced
```

Budget ~75 GB for the raw output and ~90 MB for the reduced output.
