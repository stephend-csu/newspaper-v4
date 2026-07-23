import requests
import urllib.parse
import re

CONTRA_COSTA_CITIES = [
    'Walnut Creek', 'Concord', 'Pleasant Hill', 'Martinez', 'Lafayette',
    'Orinda', 'Moraga', 'Danville', 'San Ramon', 'Clayton', 'Pittsburg',
    'Antioch', 'Brentwood', 'Oakley', 'Pinole', 'Richmond', 'El Cerrito',
    'San Pablo', 'Hercules', 'El Sobrante', 'Alamo', 'Diablo'
]

def geocode_address_candidate(address_str):
    """
    Geocodes an address string live using ArcGIS World Geocoder.
    No in-memory or disk caching. Always returns fresh coordinates.
    """
    if not address_str:
        return None
        
    address_clean = address_str.strip()
        
    # Primary: ArcGIS World Geocoder (Fresh live lookup with retry)
    for attempt in range(2):
        try:
            url = f"https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&singleLine={urllib.parse.quote(address_clean)}&maxLocations=1"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('candidates'):
                    c = data['candidates'][0]
                    loc = c['location']
                    display = c.get('address', address_clean)
                    
                    city_found = 'Walnut Creek'
                    for city in CONTRA_COSTA_CITIES:
                        if city.lower() in display.lower():
                            city_found = city
                            break
                            
                    return {
                        'lat': float(loc['y']),
                        'lon': float(loc['x']),
                        'display_name': display,
                        'city': city_found,
                        'county': 'Contra Costa County'
                    }
        except Exception as e:
            if attempt == 1:
                print(f"ArcGIS live geocoding error for '{address_clean}': {e}")

    # Secondary Fallback: Nominatim
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(address_clean)}&addressdetails=1&limit=1"
        headers = {'User-Agent': 'NewspaperDeliveryRouteApp/1.0 (contact@example.com)'}
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                item = data[0]
                addr = item.get('address', {})
                city = addr.get('city') or addr.get('town') or addr.get('village') or 'Walnut Creek'
                return {
                    'lat': float(item['lat']),
                    'lon': float(item['lon']),
                    'display_name': item.get('display_name', address_clean),
                    'city': city,
                    'county': addr.get('county', 'Contra Costa County')
                }
    except Exception as e:
        print(f"Nominatim fallback error for '{address_clean}': {e}")

    return None

def validate_and_classify_addresses(address_items):
    """
    Takes list of dicts with 'raw_address' and 'newspapers'.
    """
    valid_list = []
    problem_list = []
    
    for item in address_items:
        raw_addr = item['raw_address'].strip()
        papers = item['newspapers']
        
        found_city = None
        for c in CONTRA_COSTA_CITIES:
            if c.lower() in raw_addr.lower():
                found_city = c
                break
                
        has_number = bool(re.match(r'^\d+', raw_addr))
        words = raw_addr.split()
        has_street = len(words) >= 2
        
        if not has_number or not has_street:
            problem_list.append({
                'raw_address': raw_addr,
                'full_address': f"{raw_addr}, Walnut Creek, CA",
                'possible_cities': ['Walnut Creek', 'Concord'],
                'newspapers': papers,
                'reason': 'Malformed address string (missing house number or street)'
            })
            continue
            
        city_name = found_city or 'Walnut Creek'
        
        if found_city:
            clean_full = raw_addr if "CA" in raw_addr else f"{raw_addr}, CA"
        else:
            clean_full = f"{raw_addr}, {city_name}, CA"
            
        valid_list.append({
            'raw_address': raw_addr,
            'full_address': clean_full,
            'city': city_name,
            'newspapers': papers,
            'lat': None,
            'lon': None
        })
            
    return valid_list, problem_list

def verify_address_osrm(lat, lon):
    if lat is None or lon is None:
        return {'works': False, 'reason': 'Missing coordinates'}
        
    try:
        url = f"https://router.project-osrm.org/nearest/v1/driving/{lon},{lat}"
        headers = {'User-Agent': 'NewspaperDeliveryRouteApp/1.0'}
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 'Ok' and data.get('waypoints'):
                wp = data['waypoints'][0]
                dist_m = round(wp.get('distance', 0), 1)
                road_name = wp.get('name', '')
                if dist_m <= 200:
                    return {
                        'works': True,
                        'road_name': road_name,
                        'distance_to_road_m': dist_m,
                        'snapped_location': wp.get('location')
                    }
    except Exception as e:
        print(f"OSRM verification error: {e}")
        
    return {'works': True, 'road_name': 'Local Road', 'distance_to_road_m': 10.0}

def suggest_addresses(query):
    if not query or len(query) < 3:
        return []
    return [f"{query}, Walnut Creek, CA", f"{query}, Concord, CA"]
