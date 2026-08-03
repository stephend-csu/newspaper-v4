import os
from pdf_extractor import extract_addresses_from_pdf_stream
from geocoder import validate_and_classify_addresses
from router import optimize_road_route, generate_chapters_csv
from github_sync import sync_chapters_and_metadata_to_github
import json

def main():
    print("Extracting text from mon726.pdf...")
    with open("mon726.pdf", "rb") as f:
        extracted_items = extract_addresses_from_pdf_stream([f])
    
    print("Parsing and geocoding addresses...")
    addresses, problem_list = validate_and_classify_addresses(extracted_items)
    print(f"Found {len(addresses)} valid addresses, {len(problem_list)} problems.")
    
    print("Optimizing route using OSRM + OR-Tools...")
    route_waypoints, route_segments, route_stats = optimize_road_route(addresses)
    
    print("Generating CSV...")
    csv_string = generate_chapters_csv(route_waypoints)
    
    print("Generating metadata...")
    metadata = {
        "route_segments": route_segments,
        "total_stops": len(route_waypoints),
        "total_duration_seconds": route_stats.get("total_duration_seconds", 0),
        "total_drive_time": route_stats.get("total_drive_time", ""),
        "total_miles": route_stats.get("total_miles", 0)
    }
    
    # Save locally
    if not os.path.exists("csv"):
        os.makedirs("csv")
    with open("csv/Chapters_test.csv", "w", encoding="utf-8") as f:
        f.write(csv_string)
    with open("csv/metadata_test.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f)
        
    print("Uploading to GitHub as 'test' run...")
    sync_chapters_and_metadata_to_github(csv_string, metadata, "test")
    
    print("Done! View the route at: http://your-render-url/map?id=test")

if __name__ == "__main__":
    main()
