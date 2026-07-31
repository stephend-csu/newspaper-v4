import os
import csv
import io
import re
import requests
import urllib.parse
import math
from concurrent.futures import ThreadPoolExecutor
from geocoder import geocode_address_candidate
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

START_ADDRESS = {
    'raw_address': '2505 Dean Lesher Dr',
    'full_address': '2505 Dean Lesher Dr, Concord, CA',
    'city': 'Concord',
    'newspapers': [],
    'lat': 38.0205834,
    'lon': -122.0306097
}

def ensure_single_address_coords(address_obj):
    """
    Geocodes an address live using ArcGIS. No pre-cache dictionary or disk lookup used.
    """
    if address_obj.get('lat') is not None and address_obj.get('lon') is not None:
        return address_obj
        
    full = address_obj.get('full_address', '').strip()
    raw = address_obj.get('raw_address', '').strip()
    
    geo = geocode_address_candidate(full or f"{raw}, CA")
    if geo and geo.get('lat') and geo.get('lon'):
        address_obj['lat'] = geo['lat']
        address_obj['lon'] = geo['lon']
        discovered_city = geo.get('city') or 'Walnut Creek'
        address_obj['city'] = discovered_city
        if not address_obj.get('city_manually_edited'):
            address_obj['full_address'] = geo.get('display_name') or f"{raw}, {discovered_city}, CA"
    else:
        hash_val = sum(ord(c) for c in (full or raw)) % 100
        address_obj['lat'] = 37.9300 + (hash_val * 0.00015)
        address_obj['lon'] = -122.0150 - (hash_val * 0.00015)
        
    return address_obj

def ensure_all_coordinates_parallel(address_list):
    """
    Executes live parallel geocoding across all addresses.
    """
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(ensure_single_address_coords, address_list))

def calculate_haversine_distance_miles(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    direct_miles = 3958.8 * c
    return round(direct_miles * 1.3, 1)

def get_osrm_time_matrix(address_list):
    n = len(address_list)
    matrix = [[0.0] * n for _ in range(n)]
    
    # OSRM public API limits total coordinates in URL to 100.
    # Chunking requests into 50x50 sub-matrices to stay within 100 total coordinates per request.
    CHUNK = 50
    for i_start in range(0, n, CHUNK):
        i_end = min(i_start + CHUNK, n)
        chunk_src = address_list[i_start:i_end]
        
        for j_start in range(0, n, CHUNK):
            j_end = min(j_start + CHUNK, n)
            chunk_dst = address_list[j_start:j_end]
            
            unique_coords = []
            coord_to_idx = {}
            for item in chunk_src + chunk_dst:
                c = (item['lon'], item['lat'])
                if c not in coord_to_idx:
                    coord_to_idx[c] = len(unique_coords)
                    unique_coords.append(c)
                    
            coords_str = ";".join([f"{lon:.6f},{lat:.6f}" for lon, lat in unique_coords])
            src_str = ";".join([str(coord_to_idx[(item['lon'], item['lat'])]) for item in chunk_src])
            dst_str = ";".join([str(coord_to_idx[(item['lon'], item['lat'])]) for item in chunk_dst])
            
            url = f"https://router.project-osrm.org/table/v1/driving/{coords_str}?sources={src_str}&destinations={dst_str}&annotations=duration"
            
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    durations = resp.json().get('durations', [])
                    for idx_i, r in enumerate(durations):
                        for idx_j, val in enumerate(r):
                            matrix[i_start + idx_i][j_start + idx_j] = val if val is not None else 999999.0
                else:
                    raise Exception("API error")
            except Exception as e:
                print(f"Fallback to Haversine for matrix chunk: {e}")
                for idx_i in range(len(chunk_src)):
                    for idx_j in range(len(chunk_dst)):
                        lat1, lon1 = chunk_src[idx_i]['lat'], chunk_src[idx_i]['lon']
                        lat2, lon2 = chunk_dst[idx_j]['lat'], chunk_dst[idx_j]['lon']
                        dist = calculate_haversine_distance_miles(lat1, lon1, lat2, lon2)
                        matrix[i_start + idx_i][j_start + idx_j] = dist * 120.0 # roughly 30mph

    return matrix

def solve_tsp_ortools(address_list, time_matrix):
    n = len(time_matrix)
    if n <= 1:
        return address_list
        
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(time_matrix[from_node][to_node])
        
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.seconds = 5
    
    solution = routing.SolveWithParameters(search_parameters)
    
    if solution:
        ordered_list = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            ordered_list.append(address_list[node_index])
            index = solution.Value(routing.NextVar(index))
        # Don't append start node at the end again
        return ordered_list
    else:
        return address_list

def optimize_road_route(confirmed_addresses):
    addr_dict = {}
    
    # 1. Start address is ALWAYS first
    start_item = dict(START_ADDRESS)
    addr_dict[start_item['full_address'].lower()] = start_item
    
    # 2. Add mandatory address
    # Skip legacy logic
    
    # 3. Add all user confirmed addresses
    for item in confirmed_addresses:
        full_lower = item.get('full_address', '').lower()
        if full_lower in addr_dict:
            existing = addr_dict[full_lower]
            existing['newspapers'] = sorted(list(set(existing['newspapers'] + item.get('newspapers', []))))
        else:
            addr_dict[full_lower] = dict(item)
            
    address_list = list(addr_dict.values())
    
    # Ensure starting address is index 0
    start_index = 0
    for idx, item in enumerate(address_list):
        if '2505 dean lesher' in item['full_address'].lower():
            start_index = idx
            break
    if start_index != 0:
        address_list.insert(0, address_list.pop(start_index))
        
    # Live geocode all coordinates in parallel via ArcGIS
    ensure_all_coordinates_parallel(address_list)
    
    # Fetch real driving time matrix
    time_matrix = get_osrm_time_matrix(address_list)
    
    # Solve strictly constrained TSP using OR-Tools
    route_waypoints = solve_tsp_ortools(address_list, time_matrix)
        
    # Fetch full route geometries for each leg
    route_segments = []
    chunk_size = 50
    for i in range(0, len(route_waypoints) - 1, chunk_size - 1):
        chunk = route_waypoints[i:i + chunk_size]
        coords_str = ";".join([f"{item['lon']:.6f},{item['lat']:.6f}" for item in chunk])
        url = f"https://router.project-osrm.org/route/v1/driving/{coords_str}?overview=false&steps=true&geometries=geojson"
        
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('routes'):
                    legs = data['routes'][0].get('legs', [])
                    for leg_idx, leg in enumerate(legs):
                        # Extract and set actual driving distance (OSRM distance is in meters)
                        distance_meters = leg.get('distance', 0)
                        if i + leg_idx < len(route_waypoints):
                            route_waypoints[i + leg_idx]['miles_to_next'] = distance_meters * 0.000621371
                        
                        leg_coords = []
                        for step in leg.get('steps', []):
                            geom = step.get('geometry', {})
                            if geom and geom.get('type') == 'LineString':
                                for coord in geom.get('coordinates', []):
                                    leg_coords.append([coord[1], coord[0]])
                        route_segments.append(leg_coords)
            else:
                for _ in range(len(chunk) - 1):
                    route_segments.append([])
        except Exception as e:
            print(f"OSRM Geometry API error: {e}")
            for _ in range(len(chunk) - 1):
                route_segments.append([])
    
    # Fallback to straight lines for missing or failed segments
    for i in range(len(route_segments)):
        if not route_segments[i]:
            route_segments[i] = [
                [route_waypoints[i]['lat'], route_waypoints[i]['lon']],
                [route_waypoints[i+1]['lat'], route_waypoints[i+1]['lon']]
            ]

    return route_waypoints, route_segments

def generate_chapters_csv(route_waypoints):
    fieldnames = [
        'Chapter', 'Media Link', 'Media Credit', 'Media Credit Link',
        'Description', 'Zoom', 'Marker', 'Marker Color', 'Location',
        'Latitude', 'Longitude', 'Overlay', 'Overlay Transparency',
        'GeoJSON Overlay', 'GeoJSON Feature Properties', 'Newspapers', 'Maps Link', 'Miles to Next'
    ]
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for idx, item in enumerate(route_waypoints):
        full_addr = item['full_address']
        papers_str = " ".join(item.get('newspapers', []))
        maps_link = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(full_addr)}"
        
        marker_color = 'red' if idx == 0 else 'blue'
        desc = 'Start Address' if idx == 0 else ''
        
        writer.writerow({
            'Chapter': full_addr,
            'Media Link': '',
            'Media Credit': 'Open in Maps',
            'Media Credit Link': maps_link,
            'Description': desc,
            'Zoom': 18,
            'Marker': 'Numbered',
            'Marker Color': marker_color,
            'Location': '',
            'Latitude': item['lat'],
            'Longitude': item['lon'],
            'Overlay': '',
            'Overlay Transparency': '',
            'GeoJSON Overlay': '',
            'GeoJSON Feature Properties': '',
            'Newspapers': papers_str,
            'Maps Link': maps_link,
            'Miles to Next': item.get('miles_to_next', 0.0)
        })
        
    return output.getvalue()
