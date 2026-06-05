# main.py - Run Spatial Pattern Matching on the UK dataset
# Usage:
#   python main.py --pattern 0 --max-matches 20           # MSJ (default)
#   python main.py --pattern 0 --algo mpj                 # MPJ baseline
#   python main.py --pattern 40 --algo both               # compare MPJ vs MSJ
#   python main.py --pattern 0 --no-grid                  # no grid index

import argparse
import time
import os

from spm import (
    load_objects,
    build_inverted_index,
    load_patterns,
    GridIndex,
    run_pattern,
    run_msj,
    _KM_PER_DEG,
)


def print_matches(matches, objects, max_show=5):
    if not matches:
        print("  (none)")
        return
    for i, match in enumerate(matches[:max_show]):
        parts = [f"{kw} -> obj #{oid}" for kw, oid in sorted(match.items())]
        print(f"  [{i}]  " + ",  ".join(parts))
        for kw, oid in sorted(match.items()):
            obj = objects[oid]
            print(f"       {kw:20s}  lon={obj['lon']:.5f}  lat={obj['lat']:.5f}")


def main():
    parser = argparse.ArgumentParser(
        description="Spatial Pattern Matching — ICDE 2018 (MPJ + MSJ)"
    )
    parser.add_argument("--data-dir",    default="data/UK",
                        help="Path to the UK data folder (default: data/UK)")
    parser.add_argument("--pattern",     type=int, default=0,
                        help="Pattern index (0-based) when using --data-dir")
    parser.add_argument("--max-matches", type=int, default=20,
                        help="Stop after this many matches (default: 20)")
    parser.add_argument("--algo",        choices=["mpj", "msj", "both"],
                        default="msj",
                        help="Algorithm: mpj | msj | both (default: msj)")
    parser.add_argument("--no-grid",     action="store_true",
                        help="Disable the grid index (slower, for debugging)")
    # OSM mode
    parser.add_argument("--osm",         default=None, metavar="PLACE",
                        help='Download OSM data instead of using --data-dir. '
                             'E.g. --osm "Oxford, UK"')
    parser.add_argument("--osm-pattern", default=None, metavar="FILE",
                        help="Pattern file (km distances) to use with --osm. "
                             "Omit to get keyword stats and build one interactively.")
    parser.add_argument("--distance",    choices=["euclidean", "haversine"],
                        default=None,
                        help="Distance mode. Defaults to 'euclidean' for Fang data "
                             "and 'haversine' for --osm. Override with this flag.")
    args = parser.parse_args()

    t_start = time.perf_counter()

    # ── Resolve distance mode ─────────────────────────────────────────────────
    # Explicit --distance overrides the default; otherwise OSM defaults to
    # haversine and Fang data defaults to euclidean.
    if args.distance is not None:
        dist_mode = args.distance
    elif args.osm is not None:
        dist_mode = "haversine"
    else:
        dist_mode = "euclidean"

    # ── Load dataset ──────────────────────────────────────────────────────────
    print("=" * 62)
    patterns = []

    if args.osm is not None:
        # ── OSM mode ──────────────────────────────────────────────────────────
        from osmnx_adapter import (load_osm_objects, parse_pattern_km,
                                   keyword_stats)
        print(f"Mode: OSM  |  distance: {dist_mode}")
        t0 = time.perf_counter()
        objects = load_osm_objects(place=args.osm)
        t_load  = time.perf_counter() - t0
        print(f"  Load time: {t_load:.3f}s")

        if args.osm_pattern:
            with open(args.osm_pattern) as fh:
                patterns = [parse_pattern_km(fh.read())]
            print(f"  Loaded 1 pattern from {args.osm_pattern}")
        else:
            print()
            print("No --osm-pattern file given. Top keywords for building one:")
            keyword_stats(objects, top_n=40)
            print()
            print("Example pattern file (distances in km):")
            print("  restaurant pub 0.05 0.5")
            print("  pub hotel 0.1 1.0")
            print("Run again with --osm-pattern mypattern.txt")
            return

    else:
        # ── Fang / file mode ──────────────────────────────────────────────────
        loc_path     = os.path.join(args.data_dir, "loc")
        doc_path     = os.path.join(args.data_dir, "doc")
        pattern_path = os.path.join(args.data_dir, "pattern")

        print(f"Mode: Fang  |  distance: {dist_mode}")
        t0 = time.perf_counter()
        objects  = load_objects(loc_path, doc_path)
        patterns = load_patterns(pattern_path)
        t_load   = time.perf_counter() - t0

    all_keywords: set = set()
    for obj in objects.values():
        all_keywords.update(obj["keywords"])

    print(f"  Objects:         {len(objects):,}")
    print(f"  Unique keywords: {len(all_keywords):,}")
    if patterns:
        print(f"  Patterns:        {len(patterns)}")
    print(f"  Load time:       {t_load:.3f}s")

    # ── Build inverted index ──────────────────────────────────────────────────
    print()
    print("Building inverted index...")
    t0 = time.perf_counter()
    inverted_index = build_inverted_index(objects)
    print(f"  Done. ({time.perf_counter() - t0:.3f}s)")

    # ── Build grid index ──────────────────────────────────────────────────────
    grid = None
    if not args.no_grid:
        print()
        print("Building grid index...")
        t0 = time.perf_counter()
        if patterns:
            all_uppers = sorted(e["upper"] for p in patterns for e in p)
            median_upper = all_uppers[len(all_uppers) // 2]
        else:
            median_upper = 0.5  # fallback for OSM with no patterns yet
        # Grid is always in coordinate degrees. Convert km→degrees if needed.
        cell_size = median_upper / _KM_PER_DEG if dist_mode == "haversine" else median_upper
        grid = GridIndex(objects, cell_size)
        unit = "km" if dist_mode == "haversine" else "deg"
        print(f"  Cell size: {cell_size:.6f} degrees  (median upper: {median_upper:.4f} {unit})")
        print(f"  Done. ({time.perf_counter() - t0:.3f}s)")

    # ── Select pattern ────────────────────────────────────────────────────────
    print()
    print("=" * 62)

    if not patterns:
        print("No patterns loaded.")
        return

    if args.pattern >= len(patterns):
        print(f"Error: pattern {args.pattern} is out of range "
              f"(0 to {len(patterns)-1}).")
        return

    pattern = patterns[args.pattern]
    edge_lbl = f"{len(pattern)} edge" + ("s" if len(pattern) != 1 else "")
    print(f"Pattern {args.pattern}  ({edge_lbl}):")
    for edge in pattern:
        sign = ("->" if edge["flag1"] and not edge["flag2"] else
                "<-" if not edge["flag1"] and edge["flag2"] else
                "<>" if edge["flag1"] and edge["flag2"] else "--")
        n_a = len(inverted_index.get(edge["keyword_a"], []))
        n_b = len(inverted_index.get(edge["keyword_b"], []))
        print(f"  '{edge['keyword_a']}' {sign} '{edge['keyword_b']}'  "
              f"[{edge['lower']:.6f}, {edge['upper']:.6f}]  "
              f"({n_a:,} vs {n_b:,} objects)")

    grid_lbl = "grid" if grid else "no grid"

    # ── Run algorithm(s) ──────────────────────────────────────────────────────

    dist_lbl = dist_mode

    if args.algo in ("mpj", "both"):
        print()
        print(f"Running MPJ  [{grid_lbl}, {dist_lbl}, max_matches={args.max_matches}]...")
        print()
        t0 = time.perf_counter()
        mpj_matches = run_pattern(objects, inverted_index, pattern,
                                  grid=grid, max_matches=args.max_matches,
                                  dist_mode=dist_mode)
        t_mpj = time.perf_counter() - t0
        print()
        print(f"MPJ matches:  {len(mpj_matches):,}   time: {t_mpj:.3f}s")
        if args.algo == "mpj":
            print()
            print(f"First {min(5, len(mpj_matches))} match(es):")
            print_matches(mpj_matches, objects)

    if args.algo in ("msj", "both"):
        print()
        print(f"Running MSJ  [{grid_lbl}, {dist_lbl}, max_matches={args.max_matches}]...")
        print()
        t0 = time.perf_counter()
        msj_matches = run_msj(objects, inverted_index, pattern,
                              grid=grid, max_matches=args.max_matches,
                              dist_mode=dist_mode)
        t_msj = time.perf_counter() - t0
        print()
        print(f"MSJ matches:  {len(msj_matches):,}   time: {t_msj:.3f}s")
        if args.algo == "msj":
            print()
            print(f"First {min(5, len(msj_matches))} match(es):")
            print_matches(msj_matches, objects)

    if args.algo == "both":
        print()
        print("=" * 62)
        print(f"MPJ:  {len(mpj_matches):,} matches in {t_mpj:.3f}s")
        print(f"MSJ:  {len(msj_matches):,} matches in {t_msj:.3f}s")
        speedup = t_mpj / t_msj if t_msj > 0 else float('inf')
        print(f"Speedup (MSJ vs MPJ): {speedup:.2f}x")
        print()
        print(f"First {min(5, len(msj_matches))} MSJ match(es):")
        print_matches(msj_matches, objects)

    print()
    print(f"Total time: {time.perf_counter() - t_start:.3f}s")
    print("=" * 62)


if __name__ == "__main__":
    main()
