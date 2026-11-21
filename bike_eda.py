#!/usr/bin/env python3
"""
Bicycle network EDA for OSM PBF files.

What this analyses:
  - What highway types cyclists actually use
  - Dedicated infrastructure vs shared road
  - Surface quality distribution
  - Explicit bicycle access tags
  - Speed context on shared roads (risk proxy)
  - Total routable network length

Usage:
  python bike_eda.py osm-data/ghent.osm.pbf
  python bike_eda.py osm-data/osm-data-belgium.osm.pbf
"""

import sys
from collections import Counter

import pyrosm

# Plotting is optional; imported only when --plot is requested
_PLT = None

def _ensure_plt():
    global _PLT
    if _PLT is None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _PLT = plt
    return _PLT

# ------------------------------------------------------------------
# OSM tag logic for bicycle accessibility
# ------------------------------------------------------------------

# Ways with these highway values are for cyclists by default
BIKE_HIGHWAY_TYPES = {
    "cycleway",        # dedicated cycling infrastructure
    "path",            # mixed-use paths (filtered further below)
    "track",           # unpaved tracks often usable by bike
    "footway",         # often bicycle=yes in Belgium
    "residential",
    "living_street",
    "unclassified",
    "tertiary",
    "tertiary_link",
    "secondary",
    "secondary_link",
    "primary",         # usually legal for bikes unless signed otherwise
    "primary_link",
    "service",
    "pedestrian",      # sometimes bicycle=yes
}

# Explicit "bicycles not allowed" values
BICYCLE_DENIED = {"no", "private", "restricted"}

# Cycleway tag values that mean there's a bike lane/track on a road
CYCLEWAY_HAS_INFRA = {
    "lane", "track", "opposite_lane", "opposite_track",
    "shared_lane", "segregated", "shared",
}


def is_bicycle_accessible(tags: dict) -> bool:
    bicycle = tags.get("bicycle", "")
    access = tags.get("access", "")
    highway = tags.get("highway", "")

    if bicycle in BICYCLE_DENIED:
        return False
    if bicycle in {"yes", "designated", "permissive", "destination"}:
        return True
    if highway in {"motorway", "motorway_link", "trunk", "trunk_link"}:
        return False
    if access in {"no", "private"} and bicycle not in {"yes", "designated", "permissive"}:
        return False

    return highway in BIKE_HIGHWAY_TYPES


def classify_infra(tags: dict) -> str:
    highway = tags.get("highway", "")
    cycleway = (
        tags.get("cycleway", "")
        or tags.get("cycleway:both", "")
        or tags.get("cycleway:right", "")
    )
    bicycle = tags.get("bicycle", "")

    if highway == "cycleway":
        return "dedicated_cycleway"
    if highway == "path" and bicycle in {"designated", "yes"}:
        return "dedicated_path"
    if highway == "track":
        return "track"
    if cycleway in CYCLEWAY_HAS_INFRA:
        return "road_with_bike_lane"
    if highway in {"footway", "pedestrian"} and bicycle in {"yes", "designated", "permissive"}:
        return "shared_footway"
    if highway in {"residential", "living_street", "service"}:
        return "low_traffic_road"
    if highway in {"unclassified", "tertiary", "tertiary_link"}:
        return "minor_road"
    if highway in {"secondary", "secondary_link"}:
        return "secondary_road"
    if highway in {"primary", "primary_link"}:
        return "primary_road"
    return "other"


def coerce_str(val) -> str:
    return "" if val is None else str(val)


def extract_tags(row) -> dict:
    tag_cols = [
        "highway", "bicycle", "access", "surface", "cycleway",
        "cycleway:both", "cycleway:right", "cycleway:left",
        "maxspeed", "segregated", "foot", "oneway", "lit",
    ]
    return {col: coerce_str(getattr(row, col, None)) for col in tag_cols}


def fmt_km(metres: float) -> str:
    return f"{metres / 1000:.1f} km"


def top_n(counter: Counter, n: int = 10) -> list:
    return counter.most_common(n)


def print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_table(rows: list, col1: str = "Value", col2: str = "Count", pct_of: int = None) -> None:
    total = sum(v for _, v in rows) if pct_of is None else pct_of
    print(f"  {col1:<35} {col2:>8}   {'%':>6}")
    print(f"  {'-'*35} {'--------':>8}   {'------':>6}")
    for label, count in rows:
        pct = 100 * count / total if total else 0
        print(f"  {str(label):<35} {count:>8}   {pct:>5.1f}%")


def plot_insights(
    infra_lengths: dict,
    surf_counter: Counter,
    speed_counter: Counter,
    dq: dict,          # {tag_name: (missing_count, total_count)}
    out_path: str = "bike_eda.png",
) -> None:
    plt = _ensure_plt()

    # Reference palette (single-series nominal bars: all same slot-1 blue)
    C_BLUE   = "#2a78d6"
    C_SURF   = "#fcfcfb"
    C_INK    = "#0b0b0b"
    C_INK2   = "#52514e"
    C_MUTED  = "#898781"
    C_GRID   = "#e1e0d9"

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), facecolor=C_SURF)
    fig.subplots_adjust(hspace=0.45, wspace=0.35)

    def style_ax(ax, title):
        ax.set_facecolor(C_SURF)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(C_GRID)
        ax.spines["bottom"].set_color(C_GRID)
        ax.tick_params(colors=C_MUTED, labelsize=8)
        ax.xaxis.label.set_color(C_INK2)
        ax.set_title(title, fontsize=10, fontweight="bold", color=C_INK, pad=8, loc="left")

    def hbar(ax, labels, values, xlabel, title, fmt=None):
        style_ax(ax, title)
        y = range(len(labels))
        bars = ax.barh(list(y), values, color=C_BLUE, height=0.6, zorder=2)
        ax.set_yticks(list(y))
        ax.set_yticklabels(labels, fontsize=8, color=C_INK2)
        ax.invert_yaxis()
        ax.set_xlabel(xlabel, fontsize=8, color=C_INK2)
        ax.xaxis.grid(True, color=C_GRID, linewidth=0.5, zorder=1)
        ax.set_axisbelow(True)
        # Direct value labels
        for bar, val in zip(bars, values):
            label = fmt(val) if fmt else str(val)
            ax.text(
                bar.get_width() + max(values) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                label, va="center", ha="left", fontsize=7, color=C_MUTED,
            )
        ax.margins(x=0.18)

    # --- 1. Infrastructure by km ---
    rows = sorted(infra_lengths.items(), key=lambda x: x[1])
    labels1 = [r[0].replace("_", " ") for r in rows]
    vals1   = [r[1] / 1000 for r in rows]
    hbar(axes[0, 0], labels1, vals1, "km", "Infrastructure class by length",
         fmt=lambda v: f"{v:.1f} km")

    # --- 2. Surface type (top 8, rest → other) ---
    surf_items = surf_counter.most_common()
    keep, rest = surf_items[:8], surf_items[8:]
    if rest:
        keep = keep + [("other", sum(v for _, v in rest))]
    keep = sorted(keep, key=lambda x: x[1])
    labels2 = [k.replace("(not tagged)", "untagged") for k, _ in keep]
    vals2   = [v for _, v in keep]
    hbar(axes[0, 1], labels2, vals2, "ways", "Surface type distribution",
         fmt=lambda v: f"{v:,}")

    # --- 3. Speed on shared roads (top 8) ---
    speed_items = [(k, v) for k, v in speed_counter.most_common(8)
                   if str(k) not in {"", "nan"}]
    speed_items = sorted(speed_items, key=lambda x: x[1])
    labels3 = [str(k).replace("(not tagged)", "untagged") for k, _ in speed_items]
    vals3   = [v for _, v in speed_items]
    hbar(axes[1, 0], labels3, vals3, "ways", "Speed limits on shared roads",
         fmt=lambda v: f"{v:,}")

    # --- 4. Data quality gaps ---
    dq_labels = list(dq.keys())
    dq_pcts   = [100 * missing / total if total else 0
                 for missing, total in dq.values()]
    dq_sorted = sorted(zip(dq_labels, dq_pcts), key=lambda x: x[1])
    labels4, vals4 = zip(*dq_sorted) if dq_sorted else ([], [])
    hbar(axes[1, 1], list(labels4), list(vals4), "% ways missing tag",
         "Data quality: missing tags", fmt=lambda v: f"{v:.1f}%")

    fig.suptitle("Bicycle network — OSM EDA", fontsize=12, fontweight="bold",
                 color=C_INK, y=0.98)

    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=C_SURF)
    plt.close(fig)
    print(f"\n  Plot saved to {out_path}")


def main(pbf_path: str, plot: bool = False) -> None:
    print(f"\nLoading {pbf_path} ...")
    osm = pyrosm.OSM(pbf_path)

    print("Parsing ways ...")
    net = osm.get_network(network_type="all")

    if net is None or len(net) == 0:
        print("No network data found.")
        return

    print(f"Total ways in file: {len(net):,}")

    # Filter to bicycle-accessible ways
    bike_mask = net.apply(lambda row: is_bicycle_accessible(extract_tags(row)), axis=1)
    bike = net[bike_mask].copy()

    print(f"Bicycle-accessible ways: {len(bike):,} ({100*len(bike)/len(net):.1f}% of total)")

    # Compute length (project to metric CRS first)
    bike_proj = bike.to_crs(epsg=3857)
    bike["length_m"] = bike_proj.geometry.length
    total_length_m = bike["length_m"].sum()

    # --- 1. Infrastructure classification ---
    print_section("1. Infrastructure type breakdown")
    bike["infra_class"] = bike.apply(lambda row: classify_infra(extract_tags(row)), axis=1)
    infra_counts = Counter(bike["infra_class"])
    infra_lengths = bike.groupby("infra_class")["length_m"].sum().to_dict()

    print(f"\n  Total bicycle network: {fmt_km(total_length_m)}\n")
    rows = sorted(infra_lengths.items(), key=lambda x: -x[1])
    print(f"  {'Infrastructure type':<35} {'Length':>10}   {'%':>6}   Ways")
    print(f"  {'-'*35} {'----------':>10}   {'------':>6}   ----")
    for label, length in rows:
        pct = 100 * length / total_length_m
        count = infra_counts[label]
        print(f"  {label:<35} {fmt_km(length):>10}   {pct:>5.1f}%   {count:,}")

    # --- 2. Highway types ---
    print_section("2. Highway tag distribution")
    hw_counter = Counter(bike["highway"].fillna("(none)"))
    print_table(top_n(hw_counter, 15), col1="highway=", pct_of=len(bike))

    # --- 3. Surface quality ---
    print_section("3. Surface type distribution")
    surf_counter = Counter(bike["surface"].fillna("(not tagged)"))
    total_ways = len(bike)
    print_table(top_n(surf_counter, 15), col1="surface=", pct_of=total_ways)
    untagged_surf_pct = 100 * surf_counter.get("(not tagged)", 0) / total_ways
    print(f"\n  Note: {untagged_surf_pct:.1f}% of ways have no surface tag.")

    # --- 4. Explicit bicycle access tags ---
    print_section("4. Explicit bicycle= tag distribution")
    bicy_counter = Counter(bike["bicycle"].fillna("(not tagged)"))
    print_table(top_n(bicy_counter, 10), col1="bicycle=", pct_of=total_ways)

    # --- 5. cycleway= tags ---
    print_section("5. cycleway= tags (bike lane/track on a road)")
    cy_vals = []
    for col in ["cycleway", "cycleway:both", "cycleway:right", "cycleway:left"]:
        if col in bike.columns:
            cy_vals.extend(bike[col].dropna().tolist())
    if cy_vals:
        cy_counter = Counter(str(v) for v in cy_vals if str(v) not in {"", "nan"})
        print_table(top_n(cy_counter, 10), col1="cycleway value", pct_of=len(cy_vals))
    else:
        print("  No cycleway tags found.")

    # --- 6. Speed limits on shared roads ---
    print_section("6. Max speed on shared roads (excluding dedicated infra)")
    shared = bike[~bike["infra_class"].isin({"dedicated_cycleway", "dedicated_path", "shared_footway"})]
    speed_counter = Counter(shared["maxspeed"].fillna("(not tagged)"))
    print_table(top_n(speed_counter, 10), col1="maxspeed=", pct_of=len(shared))

    # --- 7. Data quality ---
    print_section("7. Data quality notes")
    missing_surface = surf_counter.get("(not tagged)", 0)
    print(f"  Ways missing surface tag:  {missing_surface:,} / {total_ways:,} ({100*missing_surface/total_ways:.1f}%)")

    dq = {"surface": (missing_surface, total_ways)}

    if "oneway" in bike.columns:
        oneway_counts = Counter(bike["oneway"].fillna("(none)"))
        oneway_yes = oneway_counts.get("yes", 0) + oneway_counts.get("1", 0) + oneway_counts.get("-1", 0)
        print(f"  One-way ways (routing-relevant): {oneway_yes:,}")

    if "lit" in bike.columns:
        lit_counts = Counter(bike["lit"].fillna("(not tagged)"))
        lit_yes = lit_counts.get("yes", 0)
        print(f"  Lit ways:  {lit_yes:,} / {total_ways:,} ({100*lit_yes/total_ways:.1f}%)")
        unlit_pct = 100 * lit_counts.get("(not tagged)", 0) / total_ways
        print(f"  lit tag missing on {unlit_pct:.1f}% of ways")
        dq["lit"] = (lit_counts.get("(not tagged)", 0), total_ways)

    missing_speed = speed_counter.get("(not tagged)", 0)
    dq["maxspeed"] = (missing_speed, len(shared))

    print(f"\n  Done. {len(bike):,} bicycle-accessible ways, {fmt_km(total_length_m)} total.\n")

    if plot:
        plot_insights(infra_lengths, surf_counter, speed_counter, dq)


if __name__ == "__main__":
    args = sys.argv[1:]
    do_plot = "--plot" in args
    args = [a for a in args if a != "--plot"]
    path = args[0] if args else "osm-data/ghent.osm.pbf"
    main(path, plot=do_plot)
