import requests
import urllib.parse

CONTRA_COSTA_CITIES = [
    'Walnut Creek', 'Concord', 'Pleasant Hill', 'Martinez', 'Lafayette',
    'Orinda', 'Moraga', 'Danville', 'San Ramon', 'Clayton', 'Pittsburg',
    'Antioch', 'Brentwood', 'Oakley', 'Pinole', 'Richmond', 'El Cerrito',
    'San Pablo', 'Hercules', 'El Sobrante', 'Alamo', 'Diablo'
]

# Simple in-memory cache to avoid duplicate geocoding API hits
GEOCODE_CACHE = {}

def geocode_address_candidate(address_str):
    """
    Geocodes an address string using OpenStreetMap Nominatim or Photon API.
    Returns dict with lat, lon, display_name, city, and county or None.
    """
    if address_str in GEOCODE_CACHE:
        return GEOCODE_CACHE[address_str]
        
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(address_str)}&addressdetails=1&limit=5"
        headers = {'User-Agent': 'NewspaperDeliveryRouteApp/1.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                # Find best candidate in Contra Costa County
                for item in data:
                    addr = item.get('address', {})
                    county = addr.get('county', '')
                    city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('hamlet')
                    
                    if 'Contra Costa' in county or (city and city in CONTRA_COSTA_CITIES):
                        res = {
                            'lat': float(item['lat']),
                            'lon': float(item['lon']),
                            'display_name': item['display_name'],
                            'city': city or 'Walnut Creek',
                            'county': county
                        }
                        GEOCODE_CACHE[address_str] = res
                        return res
                        
                # Fallback to first result if lat/lon present
                item = data[0]
                addr = item.get('address', {})
                city = addr.get('city') or addr.get('town') or addr.get('village') or 'Walnut Creek'
                res = {
                    'lat': float(item['lat']),
                    'lon': float(item['lon']),
                    'display_name': item['display_name'],
                    'city': city,
                    'county': addr.get('county', '')
                }
                GEOCODE_CACHE[address_str] = res
                return res
    except Exception as e:
        print(f"Geocoding error for '{address_str}': {e}")
        
    return None

def validate_and_classify_addresses(address_items):
    """
    Takes list of dicts with 'raw_address' and 'newspapers'.
    Fast local classification to ensure instant response on PDF upload.
    Categorizes into valid_addresses and problem_addresses based on address format and city resolution.
    """
    valid_list = []
    problem_list = []
    
    import re
    
    for item in address_items:
        raw_addr = item['raw_address'].strip()
        papers = item['newspapers']
        
        # Check if city already present in string
        found_city = None
        for c in CONTRA_COSTA_CITIES:
            if c.lower() in raw_addr.lower():
                found_city = c
                break
                
        # Validate house number and street structure
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
        
        # Format full address string
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

def suggest_addresses(query):
    """
    Provides auto-suggest options for address input on Confirmation Screen.
    """
    if not query or len(query) < 3:
        return []
        
    query_clean = f"{query}, Contra Costa County, CA"
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(query_clean)}&addressdetails=1&limit=5"
        headers = {'User-Agent': 'NewspaperDeliveryRouteApp/1.0'}
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            results = []
            for item in resp.json():
                display = item.get('display_name', '')
                addr = item.get('address', {})
                house = addr.get('house_number', '')
                road = addr.get('road', '')
                city = addr.get('city') or addr.get('town') or addr.get('village') or 'Walnut Creek'
                
                if house and road:
                    formatted = f"{house} {road}, {city}, CA"
                else:
                    formatted = display.split(',')[0] + f", {city}, CA"
                    
                if formatted not in results:
                    results.append(formatted)
            return results
    except Exception as e:
        print(f"Auto-suggest error: {e}")
        
    return [f"{query}, Walnut Creek, CA", f"{query}, Concord, CA"]
