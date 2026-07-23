import requests
import urllib.parse
import csv
import io
from geocoder import geocode_address_candidate

START_ADDRESS = {
    'raw_address': '2505 Dean Lesher Dr',
    'full_address': '2505 Dean Lesher Dr, Concord, CA',
    'city': 'Concord',
    'newspapers': [],
    'lat': 38.0205834,
    'lon': -122.0306097
}

MANDATORY_ADDRESS = {
    'raw_address': '923 Pacific Ct',
    'full_address': '923 Pacific Ct, Walnut Creek, CA',
    'city': 'Walnut Creek',
    'newspapers': ['EBT'],
    'lat': 37.934891,
    'lon': -122.012541
}

def ensure_coordinates(address_obj):
    """
    Ensures an address dictionary has valid float latitude and longitude.
    """
    if address_obj.get('lat') is not None and address_obj.get('lon') is not None:
        return address_obj
        
    full = address_obj.get('full_address') or f"{address_obj.get('raw_address')}, CA"
    geo = geocode_address_candidate(full)
    if geo:
        address_obj['lat'] = geo['lat']
        address_obj['lon'] = geo['lon']
        if not address_obj.get('city'):
            address_obj['city'] = geo.get('city', 'Walnut Creek')
    else:
        # Fallback default coordinates if geocoding server fails
        address_obj['lat'] = 37.937464
        address_obj['lon'] = -122.012413
        
    return address_obj

def optimize_road_route(confirmed_addresses):
    """
    Takes a list of confirmed address objects.
    Fixes 2505 Dean Lesher Dr, Concord, CA as the first start node.
    Includes 923 Pacific Ct, Walnut Creek, CA if missing.
    Calls OSRM Trip API (source=first) to find shortest driving distance/time route along real roads.
    Returns ordered list of route waypoints with calculated leg distances in miles to 1 decimal place.
    """
    # Deduplicate and format address list
    addr_dict = {}
    
    # 1. Start address is ALWAYS first
    start_item = dict(START_ADDRESS)
    addr_dict[start_item['full_address'].lower()] = start_item
    
    # 2. Add mandatory address
    mandatory_item = dict(MANDATORY_ADDRESS)
    
    # Check if mandatory address already in confirmed list to combine newspapers
    for item in confirmed_addresses:
        full_lower = item.get('full_address', '').lower()
        if '923 pacific' in full_lower:
            mandatory_item['newspapers'] = sorted(list(set(mandatory_item['newspapers'] + item.get('newspapers', []))))
            break
            
    addr_dict[mandatory_item['full_address'].lower()] = mandatory_item
    
    # 3. Add all user confirmed addresses
    for item in confirmed_addresses:
        full_lower = item.get('full_address', '').lower()
        if full_lower in addr_dict:
            # Merge newspapers
            existing = addr_dict[full_lower]
            existing['newspapers'] = sorted(list(set(existing['newspapers'] + item.get('newspapers', []))))
        else:
            addr_dict[full_lower] = dict(item)
            
    # Ensure all items have lat/lon coordinates
    address_list = list(addr_dict.values())
    for item in address_list:
        ensure_coordinates(item)
        
    # Ensure 2505 Dean Lesher Dr is index 0
    start_index = 0
    for idx, item in enumerate(address_list):
        if '2505 dean lesher' in item['full_address'].lower():
            start_index = idx
            break
            
    if start_index != 0:
        address_list.insert(0, address_list.pop(start_index))
        
    # Call OSRM Trip API with source=first to optimize sequence along real roads
    # OSRM expects coordinates in "lon,lat" order separated by semicolon
    coords_str = ";".join([f"{item['lon']:.6f},{item['lat']:.6f}" for item in address_list])
    
    route_waypoints = list(address_list)
    leg_miles = [0.0] * len(route_waypoints)
    
    try:
        url = f"https://router.project-osrm.org/trip/v1/driving/{coords_str}?source=first&overview=false&steps=false"
        resp = requests.get(url, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 'Ok' and data.get('trips'):
                trip = data['trips'][0]
                waypoints_info = data.get('waypoints', [])
                
                # Reorder according to OSRM waypoint waypoint_index
                ordered = [None] * len(address_list)
                for orig_idx, wp in enumerate(waypoints_info):
                    order_pos = wp['waypoint_index']
                    ordered[order_pos] = address_list[orig_idx]
                    
                route_waypoints = [w for w in ordered if w is not None]
                
                # Extract leg distances (in meters -> converted to miles)
                legs = trip.get('legs', [])
                leg_miles = []
                for leg in legs:
                    dist_meters = leg.get('distance', 0)
                    dist_miles = round(dist_meters / 1609.34, 1)
                    leg_miles.append(dist_miles)
                    
                # Pad final leg (last address to end) if needed
                while len(leg_miles) < len(route_waypoints):
                    leg_miles.append(0.0)
    except Exception as e:
        print(f"OSRM Trip API call error: {e}. Falling back to default order.")
        # Fallback leg calculation using Haversine distance formula if API call fails
        for i in range(len(route_waypoints) - 1):
            w1 = route_waypoints[i]
            w2 = route_waypoints[i+1]
            # Simple Euclidean/Haversine approx in miles
            dlat = (w2['lat'] - w1['lat']) * 69.0
            dlon = (w2['lon'] - w1['lon']) * 55.0
            dist = round((dlat**2 + dlon**2)**0.5, 1)
            leg_miles[i] = dist
            
    # Assign miles to next address on each item
    for idx, item in enumerate(route_waypoints):
        item['miles_to_next'] = leg_miles[idx] if idx < len(leg_miles) else 0.0
        
    return route_waypoints

def generate_chapters_csv(route_waypoints):
    """
    Generates the CSV string for Chapters.csv matching Leaflet Storymaps schema.
    """
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
        
        # Google Maps Search Link formula format requested:
        # ="https://www.google.com/maps/search/?api=1&query=" & SUBSTITUTE(A4, " ", "+")
        # In CSV cell as https link
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
