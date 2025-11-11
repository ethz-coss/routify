import requests  # pyright: ignore[reportMissingModuleSource]
import json
from pathlib import Path
from datetime import datetime
from tqdm import tqdm  # pip install tqdm

# --------------------------
# Path setup (relative to this script)
# --------------------------
# The folder where this Python file is located
SCRIPT_DIR = Path(__file__).resolve().parent

INPUT_PATH = SCRIPT_DIR / "coordinates.json"
OUTPUT_DIR = SCRIPT_DIR / "results"  # results go in a subfolder called "results"
BATCH_SIZE = 1000

routing_modes = [
    "routing_mode_distance",
    "routing_mode_slope",
    "routing_mode_green",
    "routing_mode_noise",
    "routing_mode_air",
]
base_url = "http://localhost:8080/route/"

# Optional: resume from a given pair index (0-based)
RESUME_FROM = 0

# --------------------------
# Helpers
# --------------------------
def make_payload(item: dict) -> dict:
    o = item["origin"]
    d = item["destination"]
    if not (isinstance(o, (list, tuple)) and len(o) == 2 and isinstance(d, (list, tuple)) and len(d) == 2):
        raise ValueError("origin/destination must be [lat, lon]")
    o_lat, o_lon = float(o[0]), float(o[1])
    d_lat, d_lon = float(d[0]), float(d[1])
    return {
        "fromLat": o_lat,
        "fromLon": o_lon,
        "toLat": d_lat,
        "toLon": d_lon,
        "green_index": 50,
        "slope": 10,
        "noise": 50,
        "air": 50,
    }

def chunk_indices(n_total: int, batch_size: int):
    """Yield (start, end) index pairs for batches [start, end)."""
    start = RESUME_FROM
    while start < n_total:
        end = min(start + batch_size, n_total)
        yield start, end
        start = end

# --------------------------
# Main
# --------------------------
if __name__ == "__main__":
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")

    with INPUT_PATH.open("r") as f:
        coords_list = json.load(f)[:10]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_date = datetime.now().strftime("%Y%m%d")
    total_pairs = len(coords_list)
    print(f"Total coordinate pairs: {total_pairs}. Processing in batches of {BATCH_SIZE}...\n")

    batch_idx = 0
    for start, end in chunk_indices(total_pairs, BATCH_SIZE):
        batch_idx += 1
        successful_responses = []
        batch_size = end - start

        print(f"--- Batch {batch_idx} | Pairs {start}-{end-1} ({batch_size} items) ---")

        # tqdm progress bar for CLI
        for i in tqdm(range(start, end), desc=f"Batch {batch_idx}", ncols=100):
            item = coords_list[i]
            try:
                data = make_payload(item)
            except Exception:
                continue  # skip malformed entries

            all_responses = {}
            success = True

            for mode in routing_modes:
                route_url = f"{base_url}{mode}/"
                try:
                    response = requests.post(route_url, json=data, timeout=30)
                except Exception:
                    success = False
                    break

                if response.status_code == 200:
                    try:
                        all_responses[mode] = response.json()
                    except Exception:
                        success = False
                        break
                else:
                    success = False
                    break

            if success:
                successful_responses.append({"index": i, "data": data, "responses": all_responses})

        # Save after each batch
        out_name = f"routing_results_{run_date}_batch{batch_idx:03d}_{start:06d}-{end-1:06d}.json"
        out_path = OUTPUT_DIR / out_name
        with out_path.open("w") as f:
            json.dump(successful_responses, f, indent=4)

        print(f"Saved {len(successful_responses)} successful routes to {out_path}\n")

    print("All batches complete.")
