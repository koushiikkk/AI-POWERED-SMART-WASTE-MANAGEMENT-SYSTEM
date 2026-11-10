import requests
import math
from typing import List, Dict

OSRM_BASE_URL = "http://router.project-osrm.org"

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points in km."""
    R = 6371.0 # Earth radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_distance_matrix(start_loc: dict, stops: List[dict]) -> dict:
    """
    Fetch distance matrix using OSRM Table API.
    start_loc: {"lat": float, "lon": float}
    stops: [{"lat": float, "lon": float}, ...]
    Returns dict with 'distances' and 'durations' matrices.
    """
    if not stops:
        return {"distances": [[0]], "durations": [[0]]}
        
    all_points = [start_loc] + stops
    coords_string = ";".join([f"{p['lon']},{p['lat']}" for p in all_points])
    url = f"{OSRM_BASE_URL}/table/v1/driving/{coords_string}?annotations=distance,duration"
    
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return {
                "distances": data.get("distances", []), # in meters
                "durations": data.get("durations", [])  # in seconds
            }
    except Exception as e:
        print(f"OSRM Request failed: {e}")
        
    # Fallback to haversine if OSRM fails
    n = len(all_points)
    dist_matrix = [[0]*n for _ in range(n)]
    dur_matrix = [[0]*n for _ in range(n)]
    
    for i in range(n):
        for j in range(n):
            dist_km = haversine_distance(all_points[i]['lat'], all_points[i]['lon'], all_points[j]['lat'], all_points[j]['lon'])
            dist_matrix[i][j] = dist_km * 1000 # Convert to meters
            dur_matrix[i][j] = (dist_km / 25.0) * 3600 # Assume 25 km/h avg speed
            
    return {"distances": dist_matrix, "durations": dur_matrix}

def get_route_geometry(start_loc: dict, ordered_stops: List[dict]) -> dict:
    """
    Fetch full route geometry for mapping.
    """
    if not ordered_stops:
        return None
        
    all_points = [start_loc] + ordered_stops
    coords_string = ";".join([f"{p['lon']},{p['lat']}" for p in all_points])
    url = f"{OSRM_BASE_URL}/route/v1/driving/{coords_string}?overview=full&geometries=geojson"
    
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json().get("routes", [{}])[0].get("geometry")
    except Exception as e:
        print(f"OSRM geometry request failed: {e}")
        
    return None

def calculate_baseline_route(start_loc: dict, stops: List[dict]) -> dict:
    """
    Nearest neighbor algorithm purely based on distance.
    Returns a sequence of stops ordered by road distance.
    """
    if not stops:
        return {"stops": [], "total_distance_km": 0, "total_duration_minutes": 0, "geometry": None}
        
    matrix = get_distance_matrix(start_loc, stops)
    distances = matrix["distances"]
    durations = matrix["durations"]
    
    unvisited = list(range(1, len(stops) + 1))
    current_node = 0
    ordered_stops = []
    
    total_distance = 0
    total_duration = 0
    sequence = 1
    
    while unvisited:
        best_node = -1
        best_dist = float('inf')
        
        for candidate in unvisited:
            dist = distances[current_node][candidate]
            if dist < best_dist:
                best_dist = dist
                best_node = candidate
                
        # Move to best node
        dist = distances[current_node][best_node]
        dur = durations[current_node][best_node]
        
        total_distance += dist
        total_duration += dur
        
        stop_data = stops[best_node - 1].copy()
        stop_data["sequence"] = sequence
        stop_data["distance_from_previous_km"] = dist / 1000.0
        stop_data["estimated_duration_minutes"] = dur / 60.0
        
        ordered_stops.append(stop_data)
        
        unvisited.remove(best_node)
        current_node = best_node
        sequence += 1
        
    geometry = get_route_geometry(start_loc, ordered_stops)
        
    return {
        "stops": ordered_stops,
        "total_distance_km": total_distance / 1000.0,
        "total_duration_minutes": total_duration / 60.0,
        "geometry": geometry,
        "explanation": "Ordered primarily by road distance."
    }

def calculate_smart_route(start_loc: dict, stops: List[dict]) -> dict:
    """
    Heuristic that factors in both distance, priority, and AI confidence to compute an optimized route.
    """
    if not stops:
        return {"stops": [], "total_distance_km": 0, "total_duration_minutes": 0, "geometry": None}
        
    matrix = get_distance_matrix(start_loc, stops)
    distances = matrix["distances"]
    durations = matrix["durations"]
    
    unvisited = list(range(1, len(stops) + 1))
    current_node = 0
    ordered_stops = []
    
    total_distance = 0
    total_duration = 0
    sequence = 1
    
    while unvisited:
        best_node = -1
        best_score = -1.0
        
        for candidate in unvisited:
            dist_m = distances[current_node][candidate]
            dist_km = dist_m / 1000.0
            
            # The stop priority score
            priority = stops[candidate - 1].get("priority_score", 50)
            confidence = stops[candidate - 1].get("confidence", 1.0)
            if confidence is None:
                confidence = 1.0
            
            # Reduce priority influence if AI confidence is low
            adjusted_priority = priority * confidence
            
            # Simple heuristic
            score = (adjusted_priority ** 2) / (dist_km + 1)
            
            if score > best_score:
                best_score = score
                best_node = candidate
                
        # Move to best node
        dist = distances[current_node][best_node]
        dur = durations[current_node][best_node]
        
        total_distance += dist
        total_duration += dur
        
        stop_data = stops[best_node - 1].copy()
        stop_data["sequence"] = sequence
        stop_data["distance_from_previous_km"] = dist / 1000.0
        stop_data["estimated_duration_minutes"] = dur / 60.0
        
        ordered_stops.append(stop_data)
        
        unvisited.remove(best_node)
        current_node = best_node
        sequence += 1
        
    geometry = get_route_geometry(start_loc, ordered_stops)
        
    return {
        "stops": ordered_stops,
        "total_distance_km": total_distance / 1000.0,
        "total_duration_minutes": total_duration / 60.0,
        "geometry": geometry,
        "explanation": "Reordered using urgency, severity, confidence and road distance."
    }
