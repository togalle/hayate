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

## Graph topology (Ghent, from `cmd/explore`)

Structural facts that drive graph construction (tag EDA above does not cover these):

- 4,003,297 nodes in the file, but only 301,995 (**7.5%**) are referenced by bicycle-accessible ways
- 68,155 nodes are intersections (referenced by >=2 kept ways), 22.6% of referenced nodes
- 6.3 nodes per bike way on average
- Naive node-per-node graph: ~324,900 directed edges. Intersection-only compressed graph: ~68,155 edges (4.7x fewer)
- Of oneway bike ways, 5,968 are plain oneway and 1,848 (**24%**) let cyclists ride contraflow (`oneway:bicycle=no` or `cycleway=opposite*`), so the exemption check is load-bearing

Consequences for the build:

- **Parse in two passes, do not store all node coords.** Referenced nodes are 7.5% of the file. Pass 1 filters ways and collects referenced node IDs, pass 2 fills coordinates for that set only. ~13x less node memory than store-all, and far more on Belgium.
- **Start with the naive node-per-node graph.** 325k edges is cheap at city scale. Intersection-only compression is a later optimization, now quantified at 4.7x.

## Commands

```bash
# EDA (Python, requires .venv)
uv venv && uv pip install pyrosm
.venv/bin/python bike_eda.py osm-data/ghent.osm.pbf

# Explore raw tag frequencies + graph topology (Go)
go run ./cmd/explore osm-data/ghent.osm.pbf
```

## Roadmap

### Phase 1 - Graph construction
Parse the PBF into an in-memory directed graph. Target: `graph/build.go`, reusing the
accessibility and oneway-exemption logic already ported to Go in `cmd/explore/main.go`.

- **Two-pass parse** (see Graph topology above): pass 1 filters bicycle-accessible ways and
  collects referenced node IDs, pass 2 fills coordinates for that set only. Do not store all
  node coords.
- Filter ways to bicycle-accessible using OSM tag logic (`highway`, `bicycle`, `access`)
- Naive graph: split each way into directed edges between consecutive node pairs (every way-node
  is a vertex). Intersection-only compression is a later optimization, ~4.7x fewer edges.
- Handle oneway: add reverse edge unless `oneway in {yes,1,true}` and not cyclist-exempt
  (`oneway:bicycle=no` or `cycleway=opposite*`); for `oneway=-1` add only the reverse. 24% of
  oneway bike ways are exempt, so this check matters.
- Edge attributes: distance (haversine), highway type, surface, cycleway tag, maxspeed
- Infer missing surface and speed from highway type
- Skip for now: largest-connected-component pruning (add a BFS when a route fails across islands);
  `bicycle=use_sidepath` redirect (belongs in the Phase 3 cost function)

**Output:** `graph.Build(pbf) -> Graph`. Ghent: ~302k nodes, ~325k edges, loads in under 1 second.

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
