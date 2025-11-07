# README — Batch Routing Runner

This guide shows you how to:
- set up a fresh Python virtual environment and install dependencies from `requirements.txt`
- install and use `tmux` to run the script in a detachable terminal session
- understand the required input/output files and formats
- ensure the required Routify services are up and healthy

---

## 1) Prerequisites

- **Python 3** (≥ 3.9 recommended) must be installed and available as `python3` and `pip`.
- **Git** and **Docker** (with Docker Compose) for running the Routify services.
- Internet access for Python packages (first-time setup only).

Check your Python:
```bash
python3 --version
pip --version
```

If `python3` isn’t found, install it from your OS package manager or from python.org.

---

## 2) Create & Activate a Virtual Environment

From the repository directory (the folder that contains your script and `requirements.txt`):

```bash
# Create a new venv named .venv
python3 -m venv .venv

# Activate it (Linux/macOS)
source .venv/bin/activate

# On Windows PowerShell
# .venv\\Scripts\\Activate.ps1
```

You should now see `(.venv)` in your shell prompt.

---

## 3) Install Dependencies

With the venv **activated**, install everything listed in `requirements.txt`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> If you see errors about missing build tools or headers, install your system’s build essentials (e.g., `build-essential` on Debian/Ubuntu) and retry.

---

## 4) Files & Expected Formats

Put these files **in the same directory** as the Python script:

- `coordinates.json` — input file with origin/destination pairs
- your Python script (e.g., `route_batcheComputeFullRouting_v4.py`) — the batching + progress-bar runner

**`coordinates.json` format** (array of objects; each has `origin` and `destination` as `[lat, lon]`):
```json
[
  { "origin": [47.3769, 8.5417], "destination": [47.3900, 8.5150] },
  { "origin": [47.3800, 8.5300], "destination": [47.3650, 8.5450] }
]
```

**Outputs**: The script writes batch results into a `results/` folder next to the script.  
Filenames include the date and batch index, e.g.:
```
results/
├─ routing_results_20251107_batch001_000000-000999.json
├─ routing_results_20251107_batch002_001000-001999.json
└─ ...
```

**Default routing API base URL** (as used in the script):  
`http://localhost:8080/route/`

---

## 5) Required Services

The script talks to the Routify backend stack. Ensure these **containers are healthy and running**:

- `routify-backend`
- `routify-nominatim`
- `routify-photon`

Follow the setup and run instructions in the **main repository README** for bringing these up.  
(Refer to that document for compose commands, environment configuration, and health checks.)

Typical quick checks:
```bash
docker ps                        # verify containers are up (STATUS should be healthy or up)
# optionally:
# curl -f http://localhost:8080/health || echo "backend not healthy"
```

If these services are not healthy, the script’s HTTP requests will fail.

---

## 6) Running with tmux (recommended for long jobs)

`tmux` lets you start a session, run your script, detach, and reconnect later—perfect for long-running batches.

### Install tmux

- **Debian/Ubuntu:**
  ```bash
  sudo apt-get update && sudo apt-get install -y tmux
  ```
- **Fedora:**
  ```bash
  sudo dnf install -y tmux
  ```
- **Arch:**
  ```bash
  sudo pacman -S tmux
  ```
- **macOS (Homebrew):**
  ```bash
  brew install tmux
  ```

### Start a new tmux session

From your project directory:

```bash
tmux new -s routify
```

You’ll drop into a new tmux shell.

### Activate venv & run the script inside tmux

```bash
source .venv/bin/activate
python ComputeFullRouting_v4.py
```

You’ll see a CLI progress bar (via `tqdm`) for each batch.

### Detach from tmux (leave it running)

- Press **`Ctrl-b`** then **`d`** (you’ll return to your normal shell; the job keeps running).

### Reattach later

```bash
tmux ls                  # list sessions
tmux attach -t routify   # attach to your session
```

### Stop/kill a tmux session

```bash
tmux kill-session -t routify
```

---

## 7) Typical Workflow Summary

```bash
# 1) Create venv
python3 -m venv .venv
source .venv/bin/activate

# 2) Install deps
pip install --upgrade pip
pip install -r requirements.txt

# 3) Ensure Routify services are up (see main repo README)
docker ps  # should show routify-backend, routify-nominatim, routify-photon as running/healthy

# 4) Prepare coordinates.json in same folder as the script

# 5) Run under tmux
tmux new -s routify
source .venv/bin/activate
python CumputeFullRouting_v4.py
# Ctrl-b then d to detach
```

---

## 8) Troubleshooting

- **`python3: command not found`**: Install Python 3 from your OS or python.org.
- **`pip: command not found`**: Use `python3 -m pip install -U pip` or install pip.
- **Dependency build errors**: Install system build tools (e.g., `sudo apt-get install -y build-essential`).
- **`coordinates.json` not found**: Ensure it’s in the same directory as the script.
- **Empty output files**: Often caused by the backend not running/healthy. Verify containers and API availability.
- **Progress bar missing/ugly**: Make sure `tqdm` is installed (`pip install tqdm`) and run in a regular terminal.

---

## 9) Optional: Post-process generated data

`PostProcessDataFull.py` can shrink the batch outputs created by `ComputeFullRouting_v4.py`.  
It walks every route in a raw results file, aggregates the metrics per routing mode and transport mode, and writes a lighter JSON snapshot that is easier to inspect or share.

Steps:

```bash
cd jupyter
source .venv/bin/activate                     # if not already active
python PostProcessDataFull.py results/routing_results_20251107_batch001_000000-000999.json
```

- The script accepts **one** input file at a time (any of the JSON files inside `results/`).
- The reduced file is written alongside the original and uses the same name with `_reduced` appended, e.g.  
  `results/routing_results_20251107_batch001_000000-000999_reduced.json`.
- Repeat the command for every batch file you want to condense.

Tip: run this after large jobs finish so you keep both the verbatim responses and the compact summaries.

---

## 10) Notes

- The script batches up to **1000** origin/destination pairs per file to keep memory bounded.
- Files include a **date and batch index** in the name to avoid overwrites and help with bookkeeping.
- For advanced use (like auto-retry on failed HTTP requests), adjust the script’s request loop or ask for an extended example.

---

That’s it! If you haven’t already, go to the **main repository README** for container setup and health check instructions for `routify-backend`, `routify-nominatim`, and `routify-photon`.
