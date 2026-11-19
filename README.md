# Hayate

A bicycle routing application built on OpenStreetMap data.

## Goal

Given a start and end coordinate, compute an optimal bicycle route using real road and path data from OpenStreetMap. "Optimal" for cycling means preferring dedicated cycle paths, smooth surfaces, and low-traffic roads over raw shortest distance.

In the long run, maybe a user can input preferences, either just by ordering or giving them a score, on how much they prefer the fastest road, shortest, least traffic lights, dedicated bike lanes, etc.

## Next Steps

1. **Pick a scope.** Download a small `.osm.pbf` region (e.g. your city) from [Geofabrik](https://download.geofabrik.de) to work with locally.

2. **Understand the data.** Parse the PBF file and inspect raw nodes/ways. Focus on the `highway` tag and bicycle-relevant tags (`bicycle=yes/designated`, `surface`, `cycleway`). Tools: `osmium-tool` for quick inspection, or a library like `osmread` (Python) / `osmpbf` (Go/Rust).

3. **Build the graph.** Convert OSM ways into a weighted directed graph. Each node is an OSM node; each edge is a way segment with a cost (distance, surface penalty, road type penalty). Filter out ways where `bicycle=no` or `access=no`.

4. **Implement routing.** A* with geographic heuristic (haversine distance to goal) is the standard starting point. It is fast enough for city-scale graphs without preprocessing.

5. **Visualize results.** Plot the computed route on a map using Leaflet (browser) or folium (Python) to verify correctness visually before optimizing.

6. **Tune the cost function.** Adjust weights for surface type, road category, and elevation gain (if you add elevation data via a DEM file) to make routes feel natural for a cyclist.
