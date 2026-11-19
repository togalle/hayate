# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Hayate is a bicycle routing application built on OpenStreetMap (OSM) data. It parses OSM graph data and computes optimal bike routes between two points.

## Key Concepts

- OSM data: nodes (points), ways (edges), relations. Relevant tags: `highway`, `bicycle`, `surface`, `access`, `cycleway`.
- OSM data source: download `.osm.pbf` files from [Geofabrik](https://download.geofabrik.de) or query the Overpass API for small areas.
- Routing runs on a graph derived from OSM ways filtered for bicycle access.

## Commands

```bash
# (add build, test, lint commands here once stack is chosen)
```
