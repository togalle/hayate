package main

import (
	"context"
	"fmt"
	"os"
	"runtime"
	"sort"

	"github.com/paulmach/osm"
	"github.com/paulmach/osm/osmpbf"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: explore <file.osm.pbf>")
		os.Exit(1)
	}

	f, err := os.Open(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer f.Close()

	counts := map[string]map[string]int{
		"highway":  {},
		"bicycle":  {},
		"surface":  {},
		"cycleway": {},
	}
	total := 0

	// Topology counters (Step 0: structural analysis for graph construction).
	totalNodes := 0           // every node in the file
	bikeWays := 0             // bicycle-accessible ways
	bikeWayNodeRefs := 0      // sum of node refs across bike ways (for avg + edge estimate)
	nodeUse := map[osm.NodeID]int{} // times a node is referenced by a kept way
	oneway := map[string]int{"plain_oneway": 0, "bike_exempt": 0}

	scanner := osmpbf.New(context.Background(), f, runtime.NumCPU())
	defer scanner.Close()

	for scanner.Scan() {
		switch obj := scanner.Object().(type) {
		case *osm.Node:
			totalNodes++
		case *osm.Way:
			tags := obj.Tags.Map()
			if _, hasHighway := tags["highway"]; !hasHighway {
				continue
			}
			total++
			for key := range counts {
				if v, ok := tags[key]; ok {
					counts[key][v]++
				}
			}
			if !isBicycleAccessible(tags) {
				continue
			}
			bikeWays++
			bikeWayNodeRefs += len(obj.Nodes)
			for _, wn := range obj.Nodes {
				nodeUse[wn.ID]++
			}
			if ow := tags["oneway"]; ow == "yes" || ow == "1" || ow == "true" || ow == "-1" {
				if bicycleExemptFromOneway(tags) {
					oneway["bike_exempt"]++
				} else {
					oneway["plain_oneway"]++
				}
			}
		}
	}
	if err := scanner.Err(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	fmt.Printf("Total highway ways: %d\n\n", total)
	for _, key := range []string{"highway", "bicycle", "surface", "cycleway"} {
		printFreq(key, counts[key])
	}

	// --- Topology summary ---
	referenced := len(nodeUse)
	intersections := 0
	for _, n := range nodeUse {
		if n >= 2 {
			intersections++
		}
	}
	fmt.Println("=== topology (bicycle-accessible subgraph) ===")
	fmt.Printf("  total nodes in file          %d\n", totalNodes)
	fmt.Printf("  bike-accessible ways         %d\n", bikeWays)
	fmt.Printf("  nodes referenced by bike ways %d  (%.1f%% of file)\n", referenced, pct(referenced, totalNodes))
	fmt.Printf("  intersection nodes (ref >=2) %d  (%.1f%% of referenced)\n", intersections, pct(intersections, referenced))
	fmt.Printf("  avg nodes per bike way       %.1f\n", ratio(bikeWayNodeRefs, bikeWays))
	fmt.Printf("  naive edges (node-per-node)  ~%d\n", bikeWayNodeRefs-bikeWays)
	fmt.Printf("  compressed edges (intersection-only) ~%d\n", intersections)
	fmt.Printf("  oneway ways: plain %d, cyclist-exempt %d\n", oneway["plain_oneway"], oneway["bike_exempt"])
}

func pct(a, b int) float64 {
	if b == 0 {
		return 0
	}
	return 100 * float64(a) / float64(b)
}

func ratio(a, b int) float64 {
	if b == 0 {
		return 0
	}
	return float64(a) / float64(b)
}

// isBicycleAccessible ports bike_eda.py's logic for the structural pass.
func isBicycleAccessible(tags map[string]string) bool {
	bicycle, access, highway := tags["bicycle"], tags["access"], tags["highway"]
	switch bicycle {
	case "no", "private", "restricted":
		return false
	case "yes", "designated", "permissive", "destination":
		return true
	}
	switch highway {
	case "motorway", "motorway_link", "trunk", "trunk_link":
		return false
	}
	if (access == "no" || access == "private") &&
		bicycle != "yes" && bicycle != "designated" && bicycle != "permissive" {
		return false
	}
	_, ok := bikeHighwayTypes[highway]
	return ok
}

var bikeHighwayTypes = map[string]bool{
	"cycleway": true, "path": true, "track": true, "footway": true,
	"residential": true, "living_street": true, "unclassified": true,
	"tertiary": true, "tertiary_link": true, "secondary": true,
	"secondary_link": true, "primary": true, "primary_link": true,
	"service": true, "pedestrian": true,
}

// bicycleExemptFromOneway reports whether cyclists may ride against a oneway.
func bicycleExemptFromOneway(tags map[string]string) bool {
	if tags["oneway:bicycle"] == "no" {
		return true
	}
	for _, k := range []string{"cycleway", "cycleway:both", "cycleway:left", "cycleway:right"} {
		if v := tags[k]; len(v) >= 8 && v[:8] == "opposite" {
			return true
		}
	}
	return false
}

func printFreq(tag string, m map[string]int) {
	type kv struct {
		k string
		v int
	}
	pairs := make([]kv, 0, len(m))
	for k, v := range m {
		pairs = append(pairs, kv{k, v})
	}
	sort.Slice(pairs, func(i, j int) bool { return pairs[i].v > pairs[j].v })

	fmt.Printf("=== %s (%d values) ===\n", tag, len(pairs))
	for _, p := range pairs {
		fmt.Printf("  %-30s %d\n", p.k, p.v)
	}
	fmt.Println()
}
