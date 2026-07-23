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
    Categorizes into valid_addresses and problem_addresses.
    """
    valid_list = []
    problem_list = []
    
    for item in address_items:
        raw_addr = item['raw_address'].strip()
        papers = item['newspapers']
        
        # Check if city already present
        has_city = any(c.lower() in raw_addr.lower() for c in CONTRA_COSTA_CITIES)
        
        matching_cities = []
        best_geo = None
        
        if has_city:
            geo = geocode_address_candidate(f"{raw_addr}, CA")
            if geo:
                best_geo = geo
                matching_cities.append(geo['city'])
        else:
            # Test default candidate Walnut Creek first, as many addresses in this route are in Walnut Creek
            for city in ['Walnut Creek', 'Concord', 'Pleasant Hill', 'Lafayette']:
                full_test = f"{raw_addr}, {city}, CA"
                geo = geocode_address_candidate(full_test)
                if geo and ('Contra Costa' in geo.get('county', '') or geo.get('city') in CONTRA_COSTA_CITIES):
                    matching_cities.append(geo.get('city', city))
                    if not best_geo:
                        best_geo = geo
                        
        if len(matching_cities) == 1 or (best_geo and has_city):
            city_name = matching_cities[0] if matching_cities else best_geo.get('city', 'Walnut Creek')
            
            # Format clean full address e.g. "3104 Perra Way, Walnut Creek, CA"
            if not has_city:
                clean_full = f"{raw_addr}, {city_name}, CA"
            else:
                clean_full = raw_addr if "CA" in raw_addr else f"{raw_addr}, CA"
                
            valid_list.append({
                'raw_address': raw_addr,
                'full_address': clean_full,
                'city': city_name,
                'newspapers': papers,
                'lat': best_geo['lat'] if best_geo else None,
                'lon': best_geo['lon'] if best_geo else None
            })
        else:
            # Problem address (not found or multiple matches)
            possible_cities = list(set(matching_cities)) if matching_cities else ['Walnut Creek', 'Concord', 'Pleasant Hill']
            problem_list.append({
                'raw_address': raw_addr,
                'full_address': f"{raw_addr}, {possible_cities[0]}, CA",
                'possible_cities': possible_cities,
                'newspapers': papers,
                'reason': 'Multiple city matches found in Contra Costa County' if len(possible_cities) > 1 else 'Address not found in official Contra Costa County data'
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
