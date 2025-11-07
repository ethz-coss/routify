#!/usr/bin/env python3
"""
Post-Process Aggregation Script
This script takes the output from AggregateDataFull.py and restructures it
to group data by routing_mode -> transport_mode with weighted averages.

Usage: python PostProcessDataFull.py <input_aggregated_file>
Output: <input_aggregated_file>_reduced.json (same folder as input)
"""

import json
import sys
import os


def reduce_transport_mode_data(routes_data):
    """
    Apply reduce function to calculate weighted averages for each transport mode.
    
    Args:
        routes_data: List of route data for a specific transport mode
        
    Returns:
        Dictionary with weighted averages
    """
    if not routes_data:
        return None
    
    # Calculate total distance across all routes for this transport mode
    total_distance = sum(route.get("distance", 0) for route in routes_data)
    
    if total_distance == 0:
        return None
    
    # Calculate weighted averages
    traveltime_sum = sum(route.get("traveltime", 0) for route in routes_data)
    noise_sum = sum(route.get("noise", 0) * route.get("distance", 0) for route in routes_data)
    slope_sum = sum(route.get("slope", 0) * route.get("distance", 0) for route in routes_data)
    green_sum = sum(route.get("greenIndex", 0) * route.get("distance", 0) for route in routes_data)
    pm10_sum = sum(route.get("pm_10", 0) * route.get("distance", 0) for route in routes_data)
    
    return {
        "traveltime": traveltime_sum / len(routes_data),  # Average travel time
        "distance": total_distance,
        "noise": noise_sum / total_distance,
        "slope": slope_sum / total_distance,
        "greenIndex": green_sum / total_distance,
        "pm_10": pm10_sum / total_distance
    }


def postprocess_aggregated_data(aggregated_data):
    """
    Transform input into desired structure and apply reduce over edges per route,
    per routing mode and transport mode. Supports two input shapes:
    - Raw generator output: [{"data": {...}, "responses": {mode: response_json}}]
    - Previously aggregated output: [{"original_data": {...}, "routing_modes": {mode: metrics}}]
    
    Args:
        aggregated_data: List of route entries from AggregateDataFull.py
        
    Returns:
        List of restructured route entries
    """
    results = []

    def reduce_route_single(route):
        if not isinstance(route, dict):
            return None
        edges = route.get("edges", [])
        if not isinstance(edges, list) or not edges:
            return None
        total_distance = sum(e.get("distance", 0) for e in edges if isinstance(e, dict))
        if total_distance == 0:
            return None
        noise_sum = sum(e.get("noise", 0) * e.get("distance", 0) for e in edges if isinstance(e, dict))
        slope_sum = sum(e.get("slope", 0) * e.get("distance", 0) for e in edges if isinstance(e, dict))
        green_sum = sum(e.get("greenIndex", 0) * e.get("distance", 0) for e in edges if isinstance(e, dict))
        pm10_sum = sum(e.get("pm_10", 0) * e.get("distance", 0) for e in edges if isinstance(e, dict))
        return {
            "transportMode": route.get("transportMode", "unknown"),
            "traveltime": route.get("traveltime", 0),
            "distance": total_distance,
            "noise": noise_sum / total_distance,
            "slope": slope_sum / total_distance,
            "greenIndex": green_sum / total_distance,
            "pm_10": pm10_sum / total_distance
        }

    def extract_candidate_routes(response_obj):
        """Return a list of route dicts from a mode response of varying shapes."""
        routes = []
        # Dict with a single route under 'route'
        if isinstance(response_obj, dict) and "route" in response_obj:
            if isinstance(response_obj["route"], dict):
                routes.append(response_obj["route"])
            elif isinstance(response_obj["route"], list):
                routes.extend([r for r in response_obj["route"] if isinstance(r, dict)])
        # Dict with 'routes' list
        elif isinstance(response_obj, dict) and "routes" in response_obj and isinstance(response_obj["routes"], list):
            routes.extend([r for r in response_obj["routes"] if isinstance(r, dict)])
        # Response is already a route dict
        elif isinstance(response_obj, dict) and "edges" in response_obj:
            routes.append(response_obj)
        # Response is a list of route dicts
        elif isinstance(response_obj, list):
            routes.extend([r for r in response_obj if isinstance(r, dict)])
        return routes
    
    print(f"Post-processing {len(aggregated_data)} routes...")
    
    for i, route_entry in enumerate(aggregated_data):
        try:
            # Detect input shape
            has_raw = isinstance(route_entry, dict) and "responses" in route_entry
            has_agg = isinstance(route_entry, dict) and "routing_modes" in route_entry

            if has_raw:
                original_data = route_entry.get("data", {})
                new_entry = {"data": original_data, "responses": {}}
                for routing_mode, mode_response in route_entry.get("responses", {}).items():
                    # Extract candidate routes from this mode's response
                    routes = extract_candidate_routes(mode_response)
                    if not routes:
                        continue
                    # Aggregate per transport mode (first route per transport)
                    per_transport = {}
                    for route in routes:
                        reduced = reduce_route_single(route)
                        if not reduced:
                            continue
                        tm = reduced.get("transportMode", "unknown")
                        key = f"transport_mode_{tm}"
                        if key not in per_transport:
                            per_transport[key] = {
                                "traveltime": reduced.get("traveltime", 0),
                                "distance": reduced.get("distance", 0),
                                "noise": reduced.get("noise", 0),
                                "slope": reduced.get("slope", 0),
                                "greenIndex": reduced.get("greenIndex", 0),
                                "pm_10": reduced.get("pm_10", 0)
                            }
                    if per_transport:
                        new_entry["responses"][routing_mode] = per_transport

            elif has_agg:
                original_data = route_entry.get("original_data", {})
                routing_modes = route_entry.get("routing_modes", {})
                new_entry = {"data": original_data, "responses": {}}
                for routing_mode, metrics in routing_modes.items():
                    tm = metrics.get("transportMode", "unknown")
                    key = f"transport_mode_{tm}"
                    new_entry.setdefault("responses", {}).setdefault(routing_mode, {})[key] = {
                        "traveltime": metrics.get("traveltime", 0),
                        "distance": metrics.get("distance", 0),
                        "noise": metrics.get("noise", 0),
                        "slope": metrics.get("slope", 0),
                        "greenIndex": metrics.get("greenIndex", 0),
                        "pm_10": metrics.get("pm_10", 0)
                    }
            else:
                # Unknown shape; attempt best-effort passthrough
                new_entry = {"data": route_entry.get("data", route_entry.get("original_data", {})), "responses": {}}
            
            results.append(new_entry)
            
            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"Post-processed {i + 1}/{len(aggregated_data)} routes...")
                
        except Exception as e:
            print(f"Error post-processing route {i}: {e}")
            continue
    
    print(f"Successfully post-processed {len(results)} routes")
    return results


def load_aggregated_file(filename):
    """
    Load the aggregated JSON file.
    
    Args:
        filename: Path to the aggregated JSON file
        
    Returns:
        Loaded data or None if error
    """
    print(f"Loading aggregated file: {filename}")
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        print(f"Loaded {len(data)} route entries")
        return data
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file - {e}")
        return None
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        return None
    except Exception as e:
        print(f"Error loading file: {e}")
        return None


def main():
    """Main function to process command line arguments and run the post-processing."""
    
    if len(sys.argv) != 2:
        print("Usage: python PostProcessDataFull.py <input_aggregated_file>")
        print("Example: python PostProcessDataFull.py results/routing_results_20240210_batch001.json")
        sys.exit(1)
    
    input_filename = sys.argv[1]
    
    # Check if input file exists
    if not os.path.exists(input_filename):
        print(f"Error: Input file '{input_filename}' not found")
        sys.exit(1)
    
    # Derive output filename next to the input file
    input_dir = os.path.dirname(input_filename)
    base_name = os.path.basename(input_filename)
    name, ext = os.path.splitext(base_name)
    if not ext:
        ext = ".json"
    output_name = f"{name}_reduced{ext}"
    output_filename = os.path.join(input_dir if input_dir else ".", output_name)
    
    print(f"Input file: {input_filename}")
    print(f"Output file: {output_filename}")
    
    # Load the aggregated data
    aggregated_data = load_aggregated_file(input_filename)
    
    if aggregated_data is None:
        print("Failed to load the input file")
        sys.exit(1)
    
    # Post-process the data
    postprocessed_results = postprocess_aggregated_data(aggregated_data)
    
    if not postprocessed_results:
        print("No data to process")
        sys.exit(1)
    
    # Save results
    try:
        with open(output_filename, 'w') as f:
            json.dump(postprocessed_results, f, indent=4)
        
        print(f"Successfully saved post-processed results to {output_filename}")
        print(f"Number of routes processed: {len(postprocessed_results)}")
        
        # Show sample structure
        if postprocessed_results:
            sample_route = postprocessed_results[0]
            print(f"Sample routing modes: {list(sample_route.get('responses', {}).keys())}")
            
            first_mode = list(sample_route.get('responses', {}).keys())[0] if sample_route.get('responses') else None
            if first_mode:
                transport_modes = list(sample_route['responses'][first_mode].keys())
                print(f"Sample transport modes in {first_mode}: {transport_modes}")
        
    except Exception as e:
        print(f"Error saving output file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
