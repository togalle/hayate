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

	scanner := osmpbf.New(context.Background(), f, runtime.NumCPU())
	defer scanner.Close()

	for scanner.Scan() {
		way, ok := scanner.Object().(*osm.Way)
		if !ok {
			continue
		}
		tags := way.Tags.Map()
		if _, hasHighway := tags["highway"]; !hasHighway {
			continue
		}
		total++
		for key := range counts {
			if v, ok := tags[key]; ok {
				counts[key][v]++
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
