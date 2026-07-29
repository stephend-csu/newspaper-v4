# Newspaper Delivery Route Optimizer

This project automatically extracts addresses from delivery PDFs, geocodes them, and optimizes a vehicle route using the OR-Tools TSP solver with time matrices from OSRM. 

**Note on Multi-User & Routing Refactor (July 2026):**
The project underwent a massive refactoring to support multi-user isolation (via custom URLs and partitioned CSV data) and significantly upgraded the routing engine from a legacy Haversine distance heuristic to a true time-travel matrix using OSRM and Google OR-Tools. 

To view the exact changes where this multi-user and OR-Tools routing system was implemented, please refer to commit **`88d5c40`** (July 29, 2026) in the repository history.
