# Newspaper Route Delivery Platform

This repository contains the dynamic, multi-user routing system for optimizing newspaper delivery routes. 

## Multi-User Architecture Update

This project has been updated to support multiple concurrent users! The application no longer relies on a single `Chapters.csv` file. Instead, the backend automatically generates unique CSV and JSON metadata files for every route job by pairing the Driver's Name with a timestamp.

These dynamically generated files are pushed to the GitHub repository automatically using the GitHub API, and the frontend dynamically reads the correct map based on the `?id=` parameter in the URL. To keep the repository clean, the sync script automatically purges any generated files older than 48 hours.

*See Git commit `929e752` (July 28, 2026) for the core architectural changes that transitioned this project from a single-file system to a multi-user dynamic system, and commit `3093c9b` for the addition of the QR share flow.*
