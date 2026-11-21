# Hayate

A bicycle routing application built on OpenStreetMap data.

## Goal

Given a start and end coordinate, compute an optimal bicycle route using real road and path data from OpenStreetMap. "Optimal" for cycling means preferring dedicated cycle paths, smooth surfaces, and low-traffic roads over raw shortest distance.

A user will eventually be able to tune preferences (fastest, most comfortable, quietest) which shape the edge weights used by the routing algorithm. These preferences can be saved as a profile.

## Stack

- **Go** - core application, graph building, routing (`github.com/paulmach/osm` for PBF parsing)
- **OSM data** - `.osm.pbf` files from [Geofabrik](https://download.geofabrik.de/europe/belgium.html)
- Local data: `osm-data/ghent.osm.pbf` (36 MB, used for development), `osm-data/osm-data-belgium.osm.pbf` (667 MB)

## What we know about the data (Ghent EDA)

- 85% of ways in Ghent are bicycle-accessible (60,729 of 71,196 total)
- Total bicycle network: ~12,300 km
- Infrastructure breakdown: 40% low-traffic roads, 19% minor roads, 11% tracks, 7% dedicated cycleways, 5.6% roads with bike lanes
- 57% of ways have no `surface` tag - must infer from highway type
- 71% of shared roads have no `maxspeed` - must infer from highway type
- 7,816 one-way ways - contraflow handling matters (cyclists are often exempt)
- `bicycle=use_sidepath` on 3% of ways - router should redirect to the parallel cycleway

Key bicycle tags: `highway`, `bicycle`, `cycleway`, `surface`, `maxspeed`, `oneway:bicycle`

## Commands

```bash
# EDA (Python, requires .venv)
uv venv && uv pip install pyrosm
.venv/bin/python bike_eda.py osm-data/ghent.osm.pbf

# Explore raw tag frequencies (Go)
go run ./cmd/explore osm-data/ghent.osm.pbf
```

## Roadmap

### Phase 1 - Graph construction
Parse the PBF into an in-memory directed graph.

- Filter ways to bicycle-accessible using OSM tag logic (`highway`, `bicycle`, `access`)
- Split each way into directed edges between consecutive node pairs
- Handle oneway: add reverse edge only if `oneway:bicycle=no` or `cycleway=opposite*`
- Edge attributes: distance (haversine), highway type, surface, cycleway tag, maxspeed
- Infer missing surface and speed from highway type

**Output:** `graph.Build(pbf) -> Graph`. Ghent loads in under 1 second.

### Phase 2 - Basic routing (A\*)
Given two coordinates, return a route.

- Nearest-node lookup (linear scan is fine at city scale)
- A* with haversine heuristic
- Single cost dimension: distance only

**Output:** `route.Find(graph, from, to LatLon) -> []LatLon`, verified visually on geojson.io.

### Phase 3 - Cost function and profiles
Routes that feel natural for a cyclist.

- Edge cost = `distance * type_factor * surface_factor * speed_factor`
- Example type factors: dedicated cycleway 0.6x, bike lane road 0.8x, low-traffic road 1.0x, primary road 2.0x
- Surface penalty: cobblestones/sett ~1.3x, gravel ~1.4x, grass ~1.8x
- Suppress ways tagged `bicycle=use_sidepath`
- Three built-in profiles: `comfort`, `fast`, `balanced`

### Phase 4 - Elevation
Penalise climbs (relevant outside flat Ghent).

- Download a DEM (Copernicus GLO-30 or SRTM 90m)
- Annotate nodes with elevation at load time
- Add climb cost to edges: ascending metres * climb_factor

### Phase 5 - Visualisation
See routes, not just coordinates.

- Output route as GeoJSON
- Single-file Leaflet HTML viewer
- Optionally colour edges by infrastructure type

### Phase 6 - CLI and usability
Something you can hand to someone.

- `hayate route <lat,lon> <lat,lon> [--profile comfort|fast|balanced]`
- Pre-process graph at startup and cache to disk (`encoding/gob`) for instant cold starts
- Optionally: `hayate serve` for an HTTP endpoint

### Phase 7 - User profiles (optional, long-term)
Routing that adapts to a specific rider.

- Accept feedback on completed routes
- Adjust and persist profile weights
- Multiple saved profiles per user

## Explicitly out of scope (for now)
- OSM turn restrictions (adds complexity, minor quality gain at city scale)
- Traffic signals as routing costs (data too sparse)
- Real-time traffic
- Multi-modal routing (bike + transit)
