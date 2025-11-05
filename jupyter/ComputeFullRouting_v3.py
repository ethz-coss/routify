import requests  # pyright: ignore[reportMissingModuleSource]
import geopandas as gpd  # pyright: ignore[reportMissingModuleSource]
import json
from shapely.geometry import Point  # pyright: ignore[reportMissingModuleSource]
from IPython.display import display


# Open the file safely using context manager
with open("PATH_TO_COORDINATES_FILE/coordinates.json", "r") as f:
    coords_list = json.load(f)

# API endpoints with different routing modes
routing_modes = ["routing_mode_distance", "routing_mode_slope", "routing_mode_green", "routing_mode_noise", "routing_mode_air"]
# routing_modes = [ "routing_mode_air"]
base_url = "http://localhost:8080/route/"

successful_responses = []

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
        "slope": 50,
        "noise": 50,
        "air": 50,
    }

for coords in coords_list:
    data = make_payload(coords)
    
    all_responses = {}
    success = True

    for mode in routing_modes:
        route_url = f"{base_url}{mode}/"
        response = requests.post(route_url, json=data)
        
        if response.status_code == 200:
            all_responses[mode] = response.json()
        else:
            # If any routing mode fails, discard this pair
            success = False
            break

    if success:
        # Store the successful response
        successful_responses.append({"data": data, "responses": all_responses})
        print(str(len(successful_responses)) + "/" + str(len(coords_list)) + " routes requested.")

# Save the results to a JSON file
with open("routing_results.json", "w") as f:
    json.dump(successful_responses, f, indent=4)

print("Successfully saved all route responses.")