from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import requests
from PIL import Image
import numpy as np
from io import BytesIO
import threading
import time
from pyproj import Transformer
from contextlib import asynccontextmanager
import argparse
import os
from datetime import datetime
import hashlib
from fastapi.responses import FileResponse
import rasterio
from rasterio.transform import from_bounds
import tempfile

# ------------------------------
# Define your data models
# ------------------------------
class Coordinate(BaseModel):
    lat: float
    lon: float
    id: int

class CoordinateWithPM10(BaseModel):
    pm_10: float
    id: int

class StatusResponse(BaseModel):
    mode: str  # "seed" or "live"
    seed_file: str | None = None
    last_update: str
    image_size: str | None = None
    data_source: str
    uptime_seconds: int

# ------------------------------
# Example color map and function 
# to extract pm10 from pixel color
# ------------------------------
color_map = {
    # (R, G, B) -> PM10
    "PM10_actual" : {
        (250.0, 92.0, 189.0) : 102,
        (251.0, 93.0, 183.0) : 101,
        (250.0, 94.0, 176.0) : 100,
        (250.0, 94.0, 168.0) : 99,
        (250.0, 96.0, 160.0) : 98,
        (251.0, 96.0, 154.0) : 97,
        (250.0, 96.0, 147.0) : 96,
        (251.0, 97.0, 140.0) : 95,
        (251.0, 97.0, 131.0) : 94,
        (251.0, 98.0, 125.0) : 93,
        (251.0, 98.0, 118.0) : 92,
        (251.0, 99.0, 111.0) : 91,
        (251.0, 100.0, 105.0) : 90,
        (251.0, 100.0, 98.0) : 89,
        (251.0, 101.0, 90.0) : 88,
        (251.0, 101.0, 86.0) : 87,
        (251.0, 105.0, 86.0) : 86,
        (251.0, 109.0, 86.0) : 85,
        (251.0, 123.0, 86.0) : 84,
        (251.0, 117.0, 86.0) : 83,
        (251.0, 120.0, 86.0) : 82,
        (251.0, 128.0, 86.0) : 81,
        (251.0, 132.0, 86.0) : 80,
        (251.0, 136.0, 86.0) : 79,
        (251.0, 140.0, 86.0) : 78,
        (251.0, 143.0, 86.0) : 77,
        (251.0, 147.0, 86.0) : 76,
        (251.0, 151.0, 86.0) : 75,
        (251.0, 155.0, 86.0) : 74,
        (251.0, 159.0, 86.0) : 73,
        (251.0, 162.0, 86.0) : 72,
        (251.0, 166.0, 86.0) : 71,
        (251.0, 171.0, 86.0) : 70,
        (251.0, 174.0, 86.0) : 69,
        (251.0, 178.0, 86.0) : 68,
        (251.0, 181.0, 86.0) : 67,
        (251.0, 183.0, 86.0) : 66,
        (251.0, 193.0, 85.0) : 65,
        (250.0, 197.0, 85.0) : 64,
        (250.0, 202.0, 85.0) : 63,
        (249.0, 206.0, 84.0) : 62,
        (249.0, 211.0, 84.0) : 61,
        (248.0, 215.0, 84.0) : 60,
        (247.0, 223.0, 83.0) : 59,
        (248.0, 227.0, 82.0) : 58,
        (247.0, 231.0, 82.0) : 57,
        (246.0, 236.0, 81.0) : 56,
        (246.0, 244.0, 81.0) : 55,
        (237.0, 244.0, 81.0) : 54,
        (213.0, 244.0, 81.0) : 53,
        (201.0, 245.0, 81.0) : 52,
        (189.0, 244.0, 81.0) : 52,
        (165.0, 244.0, 81.0) : 51,
        (154.0, 245.0, 81.0) : 50,
        (130.0, 245.0, 81.0) : 49,
        (106.0, 245.0, 81.0) : 48,
        (94.0, 245.0, 81.0) : 47,
        (83.0, 245.0, 81.0) : 46,
        (81.0, 245.0, 83.0) : 45,
        (81.0, 245.0, 90.0) : 44,
        (81.0, 245.0, 96.0) : 43,
        (82.0, 246.0, 102.0) : 42,
        (82.0, 246.0, 107.0) : 41,
        (82.0, 246.0, 112.0) : 40,
        (82.0, 246.0, 120.0) : 39,
        (82.0, 247.0, 125.0) : 38,
        (82.0, 246.0, 131.0) : 37,
        (83.0, 247.0, 149.0) : 36,
        (83.0, 246.0, 155.0) : 35,
        (83.0, 247.0, 161.0) : 34,
        (83.0, 247.0, 168.0) : 33,
        (84.0, 247.0, 173.0) : 32,
        (84.0, 247.0, 179.0) : 31,
        (84.0, 247.0, 185.0) : 30,
        (84.0, 247.0, 192.0) : 29,
        (84.0, 247.0, 197.0) : 28,
        (84.0, 248.0, 203.0) : 27,
        (85.0, 248.0, 210.0) : 26,
        (85.0, 248.0, 221.0) : 25,
        (85.0, 249.0, 228.0) : 24,
        (86.0, 248.0, 233.0) : 23,
        (86.0, 249.0, 245.0) : 22,
        (86.0, 249.0, 251.0) : 21,
        (84.0, 245.0, 250.0) : 20,
        (81.0, 234.0, 248.0) : 19,
        (77.0, 224.0, 245.0) : 18,
        (72.0, 214.0, 244.0) : 17,
        (68.0, 204.0, 241.0) : 16,
        (64.0, 194.0, 239.0) : 15,
        (61.0, 184.0, 237.0) : 14,
        (57.0, 174.0, 236.0) : 13,
        (53.0, 163.0, 232.0) : 12,
        (49.0, 153.0, 231.0) : 11,
        (44.0, 142.0, 229.0) : 10,
        (40.0, 132.0, 226.0) : 9,
        (36.0, 122.0, 223.0) : 8,
        (32.0, 112.0, 222.0) : 7,
        (27.0, 102.0, 220.0) : 6,
        (25.0, 92.0, 216.0) : 5,
        (21.0, 82.0, 216.0) : 4,
        (17.0, 71.0, 212.0) : 3,
        (13.0, 61.0, 210.0) : 2,
        (8.0, 51.0, 208.0) : 1,
        (5.0, 41.0, 206.0) : 0
    }
}

def get_pm10_from_color(pixel_color, pm10_map):
    """
    Return the PM10 value from pm10_map whose RGB key is closest to pixel_color.
    pixel_color: (R, G, B) from your image pixel (floats or ints).
    pm10_map: A dict with keys=(R, G, B), values=PM10.
    """
    # Convert to float for distance calculations if they are not already
    px_r, px_g, px_b = map(float, pixel_color)

    best_pm10 = 0.0  # Default value instead of None
    min_dist = float("inf")

    for (r, g, b), pm10_value in pm10_map.items():
        # Euclidean distance in RGB space
        dist = (px_r - r)**2 + (px_g - g)**2 + (px_b - b)**2
        if dist < min_dist:
            min_dist = dist
            best_pm10 = float(pm10_value)  # Ensure it's a float

    return best_pm10

# ------------------------------
# Image and concurrency globals
# ------------------------------
image_lock = threading.Lock()  # Protects the global image data
img_array = None
img_width = None
img_height = None
use_seed_mode = False
seed_file_path = None

# Bounds for your WMS image: [(min_lat, min_lon), (max_lat, max_lon)]
image_bounds = [(47.3202187, 8.4480061), (47.4346662, 8.6254413)]

transformer_epsg4326_to_epsg2056 = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)

# Initial bounding box in EPSG:2056 (Swiss LV95) (minx,miny,maxx,maxy)
x1, y1 = transformer_epsg4326_to_epsg2056.transform(8.4480061, 47.3202187)
x2, y2 = transformer_epsg4326_to_epsg2056.transform(8.6254413, 47.4346662)

bbox = [x1, y1, x2, y2]

# WMS URL/params
wms_url = "https://ostluft.meteotest.ch/wms"
params = {
    "service": "WMS",
    "request": "GetMap",
    "version": "1.1.1",
    "layers": "PM10_actual",
    "styles": "",
    "format": "image/png",
    "transparent": "true",
    "height": str(4096),
    "width": str(4096),
    "zindex": 10,
    "srs": "EPSG:2056",
    # Convert bbox list to the comma-separated string minx,miny,maxx,maxy
    "bbox": ",".join(str(v) for v in bbox)
}

# ------------------------------
# Function to generate seed file
# ------------------------------
def generate_seed():
    """
    Generate a seed PNG file with timestamp naming convention.
    """
    try:
        url = requests.Request("GET", wms_url, params=params).prepare().url
        if url is None:
            print("Failed to prepare URL")
            return False
            
        response = requests.get(url)
        if response.status_code == 200:
            # Generate timestamp for filename
            timestamp = int(time.time())
            filename = f"seed_{timestamp}.png"
            
            # Save the image
            with open(filename, 'wb') as f:
                f.write(response.content)
            
            print(f"Seed file generated: {filename}")
            return True
        else:
            print("Failed to fetch image:", response.status_code)
            return False
    except Exception as e:
        print("Exception while generating seed:", e)
        return False

# ------------------------------
# Global variables for status tracking
# ------------------------------
startup_time = None
last_update_time = None
current_mode = "live"
current_seed_file = None

# ------------------------------
# Function to fetch the image
# ------------------------------
def fetch_image():
    """
    Fetch the WMS image, convert to RGB if needed, and store it
    in the global variables under a lock.
    """
    global img_array, img_width, img_height, last_update_time, current_mode, current_seed_file

    try:
        if use_seed_mode and seed_file_path:
            # Load from seed file
            if os.path.exists(seed_file_path):
                image = Image.open(seed_file_path)
                if image.mode != "RGB":
                    image = image.convert("RGB")
                
                with image_lock:
                    img_array = np.array(image)
                    img_width, img_height = image.size
                
                current_mode = "seed"
                current_seed_file = seed_file_path
                last_update_time = datetime.now()
                print(f"Seed image loaded from: {seed_file_path}")
            else:
                print(f"Seed file not found: {seed_file_path}")
        else:
            # Fetch from WMS
            url = requests.Request("GET", wms_url, params=params).prepare().url
            if url is None:
                print("Failed to prepare URL")
                return
                
            response = requests.get(url)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                if image.mode != "RGB":
                    image = image.convert("RGB")

                with image_lock:
                    img_array = np.array(image)
                    img_width, img_height = image.size
                
                current_mode = "live"
                current_seed_file = None
                last_update_time = datetime.now()
                print("WMS image updated.")
            else:
                print("Failed to fetch image:", response.status_code)
    except Exception as e:
        print("Exception while fetching image:", e)

# ------------------------------
# Background updater thread
# ------------------------------
def background_updater():
    """
    Periodically re-fetch the WMS image every 5 minutes.
    Runs in a background thread (daemon).
    Only runs if not in seed mode.
    """
    while True:
        time.sleep(300)  # 5 minutes
        if not use_seed_mode:
            fetch_image()

# ------------------------------
# Lat/Lon to pixel function
# ------------------------------
def latlon_to_pixel(lat, lon, bounds, img_size):
    """
    Converts lat/lon to pixel x,y within the given image bounds and size.
    bounds: [(min_lat, min_lon), (max_lat, max_lon)]
    img_size: (width, height)
    """
    (min_lat, min_lon), (max_lat, max_lon) = bounds
    width, height = img_size
    
    # Normalize longitude to range [0, width]
    x = int((lon - min_lon) / (max_lon - min_lon) * width)
    
    # Normalize latitude to range [0, height], with y=0 at top.
    y = int((max_lat - lat) / (max_lat - min_lat) * height)
    
    # Clamp to valid image indices
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))

    return x, y

# ------------------------------
# Function to convert PNG to PM10 raster
# ------------------------------
def convert_png_to_pm10_raster(img_array, bounds, output_path):
    """
    Convert the PNG image array to a PM10 raster file.
    
    Args:
        img_array: NumPy array of the image (height, width, 3)
        bounds: [(min_lat, min_lon), (max_lat, max_lon)]
        output_path: Path to save the raster file
    """
    try:
        # Convert image to PM10 values
        height, width = img_array.shape[:2]
        pm10_array = np.zeros((height, width), dtype=np.float32)
        
        for y in range(height):
            for x in range(width):
                pixel_color = img_array[y, x]
                pm10_value = get_pm10_from_color(pixel_color, color_map["PM10_actual"])
                pm10_array[y, x] = pm10_value
        
        # Define the geotransform from bounds
        (min_lat, min_lon), (max_lat, max_lon) = bounds
        transform = from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)
        
        # Write the raster file
        with rasterio.open(
            output_path,
            'w',
            driver='GTiff',
            height=height,
            width=width,
            count=1,
            dtype=pm10_array.dtype,
            crs='EPSG:4326',
            transform=transform,
            nodata=-9999
        ) as dst:
            dst.write(pm10_array, 1)
            dst.update_tags(
                title="PM10 Air Quality Data",
                source="OstLuft WMS Service",
                units="μg/m³",
                description="PM10 particulate matter concentration derived from WMS image"
            )
        
        return True
    except Exception as e:
        print(f"Error converting to raster: {e}")
        return False

# ------------------------------
# Lifespan context manager
# ------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup logic ---
    fetch_image()
    
    # Only start background updater if not in seed mode
    if not use_seed_mode:
        thread = threading.Thread(target=background_updater, daemon=True)
        thread.start()

    # Yield to let the application serve
    yield

    # --- Teardown logic (if any) ---
    # For example, if you want to join threads or release resources:
    # thread.join()   # Usually you won't do this if you want the thread to run forever.
    print("Application shutdown. (Optional cleanup here)")

# ------------------------------
# Create FastAPI app with lifespan
# ------------------------------
app = FastAPI(lifespan=lifespan)

@app.get("/status", response_model=StatusResponse)
def get_status():
    """
    Get the current status of the air quality service.
    """
    global startup_time, last_update_time, current_mode, current_seed_file, img_width, img_height
    
    if startup_time is None:
        startup_time = datetime.now()
    
    uptime = int((datetime.now() - startup_time).total_seconds())
    
    last_update_str = last_update_time.isoformat() if last_update_time else "Never"
    image_size_str = f"{img_width}x{img_height}" if img_width and img_height else "Not loaded"
    
    data_source = f"Seed file: {current_seed_file}" if current_mode == "seed" else "Live WMS data"
    
    return StatusResponse(
        mode=current_mode,
        seed_file=current_seed_file,
        last_update=last_update_str,
        image_size=image_size_str,
        data_source=data_source,
        uptime_seconds=uptime
    )

@app.get("/export/raster")
def export_raster():
    """
    Export the current PM10 data as a GeoTIFF raster file.
    """
    global img_array, image_bounds
    
    if img_array is None:
        return {"error": "No data available for export"}
    
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tmp_file:
            temp_path = tmp_file.name
        
        # Convert to raster
        success = convert_png_to_pm10_raster(img_array, image_bounds, temp_path)
        
        if success:
            # Return the file
            return FileResponse(
                temp_path,
                media_type='application/octet-stream',
                filename=f"pm10_data_{int(time.time())}.tif"
            )
        else:
            return {"error": "Failed to create raster file"}
            
    except Exception as e:
        return {"error": f"Export failed: {str(e)}"}

@app.get("/export/csv")
def export_csv():
    """
    Export the current PM10 data as a CSV file with coordinates and values.
    """
    global img_array, image_bounds, img_width, img_height
    
    if img_array is None:
        return {"error": "No data available for export"}
    
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as tmp_file:
            temp_path = tmp_file.name
            
            # Write CSV header
            tmp_file.write("lat,lon,pm10\n")
            
            # Convert pixel coordinates to lat/lon and get PM10 values
            (min_lat, min_lon), (max_lat, max_lon) = image_bounds
            
            if img_height is None or img_width is None:
                return {"error": "Image dimensions not available"}
            
            for y in range(img_height):
                for x in range(img_width):
                    # Convert pixel to lat/lon
                    lat = max_lat - (y + 0.5) * (max_lat - min_lat) / img_height
                    lon = min_lon + (x + 0.5) * (max_lon - min_lon) / img_width
                    
                    # Get PM10 value
                    pixel_color = img_array[y, x]
                    pm10_value = get_pm10_from_color(pixel_color, color_map["PM10_actual"])
                    
                    # Write to CSV
                    tmp_file.write(f"{lat:.6f},{lon:.6f},{pm10_value}\n")
        
        # Return the file
        return FileResponse(
            temp_path,
            media_type='text/csv',
            filename=f"pm10_data_{int(time.time())}.csv"
        )
            
    except Exception as e:
        return {"error": f"Export failed: {str(e)}"}

@app.post("/get_pm10", response_model=List[CoordinateWithPM10])
def get_pm10(coordinates: List[Coordinate]):
    """
    Receives a list of coordinates:
      [
        {"lat": 47.380434, "lon": 8.539759, "id": "..."},
        ...
      ]
    Returns the same list, each item with an extra 'pm_10' field and the same 'id' value as provided.
    """

    # Safely read the global image data under a lock
    with image_lock:
        local_img_array = img_array
        local_width = img_width
        local_height = img_height

    # If the image isn't loaded yet for some reason, return -1.0 for pm_10
    if local_img_array is None:
        return [
            CoordinateWithPM10(pm_10=-1.0, id=coord.id)
            for coord in coordinates
        ]
    
    output = []
    for coord in coordinates:
        # Convert lat/lon to pixel coords
        x, y = latlon_to_pixel(coord.lat, coord.lon, image_bounds, (local_width, local_height))
        
        # Get pixel color from the NumPy array
        pixel_color = local_img_array[y, x]  # (R, G, B)
        
        # Determine PM10 from color
        pm10_value = get_pm10_from_color(pixel_color, color_map["PM10_actual"])
        
        # Echo back the provided id
        updated = CoordinateWithPM10(
            pm_10=pm10_value,
            id=coord.id
        )
        output.append(updated)

    return output

@app.get("/help")
def get_help():
    """
    Get comprehensive help and usage information for the OstLuft API.
    """
    help_info = {
        "api_name": "OstLuft Air Quality API",
        "description": "API for retrieving PM10 air quality data from OstLuft WMS service or seed files",
        "version": "1.0.0",
        "endpoints": {
            "POST /get_pm10": {
                "description": "Get PM10 values for specific coordinates",
                "request_body": [
                    {
                        "lat": 47.380434,
                        "lon": 8.539759,
                        "id": 1
                    }
                ],
                "response": [
                    {
                        "pm_10": 42,
                        "id": 1
                    }
                ],
                "example_curl": "curl -X POST 'http://localhost:8000/get_pm10' -H 'Content-Type: application/json' -d '[{\"lat\": 47.380434, \"lon\": 8.539759, \"id\": 1}]'"
            },
            "GET /status": {
                "description": "Get current service status and configuration",
                "response_fields": {
                    "mode": "Current mode: 'seed' or 'live'",
                    "seed_file": "Name of seed file if using seed mode",
                    "last_update": "ISO timestamp of last data update",
                    "image_size": "Dimensions of loaded image (e.g., '4096x4096')",
                    "data_source": "Description of data source",
                    "uptime_seconds": "Service uptime in seconds"
                },
                "example_curl": "curl http://localhost:8000/status"
            },
            "GET /export/raster": {
                "description": "Export PM10 data as GeoTIFF raster file",
                "format": "GeoTIFF (.tif)",
                "features": [
                    "Spatial reference: EPSG:4326",
                    "PM10 values in μg/m³",
                    "Metadata tags included",
                    "Downloadable file"
                ],
                "example_curl": "curl -o pm10_data.tif http://localhost:8000/export/raster"
            },
            "GET /export/csv": {
                "description": "Export PM10 data as CSV file",
                "format": "CSV (.csv)",
                "columns": ["lat", "lon", "pm10"],
                "features": [
                    "One row per pixel",
                    "Latitude/longitude coordinates",
                    "PM10 values in μg/m³"
                ],
                "example_curl": "curl -o pm10_data.csv http://localhost:8000/export/csv"
            },
            "GET /help": {
                "description": "This help endpoint - shows API usage information"
            }
        },
        "command_line_options": {
            "--generate-seed": "Generate a seed PNG file and exit",
            "--use-seed FILENAME": "Use a seed file instead of fetching from WMS"
        },
        "docker_usage": {
            "build": "docker build -t ostluft-api .",
            "run_normal": "docker run -p 8000:8000 ostluft-api",
            "run_with_seed": "docker run -p 8000:8000 ostluft-api python OstLuftApi.py --use-seed seed_123456.png",
            "generate_seed": "docker run ostluft-api python OstLuftApi.py --generate-seed"
        },
        "data_sources": {
            "live_mode": {
                "source": "OstLuft WMS service (https://ostluft.meteotest.ch/wms)",
                "update_frequency": "Every 5 minutes",
                "layer": "PM10_actual"
            },
            "seed_mode": {
                "source": "Local PNG file",
                "update_frequency": "Static (no updates)",
                "naming_convention": "seed_TIMESTAMP.png"
            }
        },
        "coverage_area": {
            "description": "Switzerland (Zurich area)",
            "bounds": {
                "min_lat": 47.3202187,
                "max_lat": 47.4346662,
                "min_lon": 8.4480061,
                "max_lon": 8.6254413
            },
            "coordinate_system": "EPSG:4326 (WGS84)"
        },
        "pm10_values": {
            "description": "PM10 particulate matter concentration",
            "unit": "μg/m³",
            "range": "0-102 μg/m³",
            "source": "Color mapping from OstLuft WMS image"
        },
        "error_handling": {
            "no_data": "Returns pm_10: -1 when no data is available",
            "invalid_coordinates": "Coordinates outside bounds are clamped to image edges",
            "file_not_found": "Returns error message when seed file is not found"
        }
    }
    
    return help_info

@app.get("/")
def root():
    """
    Root endpoint with basic information and links to help.
    """
    return {
        "message": "OstLuft Air Quality API",
        "version": "1.0.0",
        "endpoints": {
            "help": "/help",
            "status": "/status", 
            "get_pm10": "POST /get_pm10",
            "export_raster": "/export/raster",
            "export_csv": "/export/csv"
        },
        "documentation": "Use /help for detailed usage information"
    }

# ------------------------------
# Command line argument parsing
# ------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(description='OstLuft API with seed generation/usage support')
    parser.add_argument('--generate-seed', action='store_true', 
                       help='Generate a seed PNG file and exit')
    parser.add_argument('--use-seed', type=str, metavar='FILENAME',
                       help='Use a seed file instead of fetching from WMS')
    return parser.parse_args()

# ------------------------------
# How to run:
#   uvicorn filename:app --reload
#   python filename.py --generate-seed
#   python filename.py --use-seed seedfile_123456.png
# ------------------------------
if __name__ == '__main__':
    args = parse_arguments()
    
    if args.generate_seed:
        print("Generating seed file...")
        if generate_seed():
            print("Seed generation completed successfully.")
        else:
            print("Seed generation failed.")
        exit(0)
    
    if args.use_seed:
        use_seed_mode = True
        seed_file_path = args.use_seed
        print(f"Using seed file: {seed_file_path}")
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)