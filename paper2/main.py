"""
ESPM vs MSJ benchmarking runner.

Usage:
    python main.py --pattern 0                        # ESPM (default)
    python main.py --pattern 0 --algo msj             # MSJ from paper1
    python main.py --pattern 0 --algo both            # compare ESPM vs MSJ
    python main.py --pattern 0 --algo all             # compare all three (ESPM, MSJ, MPJ)
    python main.py --pattern 0 --max-matches 0        # all matches
    python main.py --data-dir ../paper1/data/UK       # use paper1's UK dataset
"""

import argparse
import os
import sys
import time

# ── Import ESPM ───────────────────────────────────────────────────────────────
from espm import (
    load_objects,
    load_patterns,
    build_ilq,
    run_espm,
)

# ── Import MSJ/MPJ from paper1 ────────────────────────────────────────────────
_paper1 = os.path.join(os.path.dirname(__file__), '..', 'paper1')
if _paper1 not in sys.path:
    sys.path.insert(0, _paper1)

try:
    from spm import (
        build_inverted_index,
        GridIndex,
        run_pattern as run_mpj,
        run_msj,
        _KM_PER_DEG,
    )
    _paper1_available = True
except ImportError:
    _paper1_available = False
    print("Note: paper1/spm.py not found — MSJ/MPJ comparison unavailable.")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _sign(edge: dict) -> str:
    if edge["flag1"] and not edge["flag2"]:  return "->"
    if not edge["flag1"] and edge["flag2"]:  return "<-"
    if edge["flag1"] and edge["flag2"]:      return "<>"
    return "--"


def print_matches(matches: list, objects: dict, max_show: int = 5) -> None:
    if not matches:
        print("  (none)")
        return
    for i, match in enumerate(matches[:max_show]):
        parts = [f"{kw} -> obj#{oid}" for kw, oid in sorted(match.items())]
        print(f"  [{i}]  " + ",  ".join(parts))
        for kw, oid in sorted(match.items()):
            obj = objects[oid]
            print(f"       {kw:20s}  lon={obj['lon']:.5f}  lat={obj['lat']:.5f}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ESPM: Efficient Spatial Pattern Matching (TKDE 2020)"
    )
    parser.add_argument("--data-dir",    default="../paper1/data/UK",
                        help="Path to data folder with loc/doc/pattern files "
                             "(default: ../paper1/data/UK)")
    parser.add_argument("--pattern",     type=int, default=0,
                        help="0-based pattern index (default: 0)")
    parser.add_argument("--max-matches", type=int, default=20,
                        help="Stop after this many matches; 0 = unlimited (default: 20)")
    parser.add_argument("--algo",
                        choices=["espm", "msj", "mpj", "both", "all"],
                        default="espm",
                        help="Algorithm to run (default: espm)")
    parser.add_argument("--lmin",  type=int, default=8,
                        help="IL-Quadtree min level (default: 8)")
    parser.add_argument("--lmax",  type=int, default=15,
                        help="IL-Quadtree max level (default: 15)")
    parser.add_argument("--split", type=int, default=64,
                        help="IL-Quadtree split threshold (default: 64)")
    parser.add_argument("--no-grid", action="store_true",
                        help="Disable grid index for MSJ/MPJ")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress per-level/edge progress output")
    args = parser.parse_args()

    data_dir = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), args.data_dir)
        if not os.path.isabs(args.data_dir)
        else args.data_dir
    )
    loc_path     = os.path.join(data_dir, "loc")
    doc_path     = os.path.join(data_dir, "doc")
    pattern_path = os.path.join(data_dir, "pattern")

    for p in (loc_path, doc_path, pattern_path):
        if not os.path.exists(p):
            print(f"Error: missing data file: {p}")
            print("Hint: use --data-dir pointing to a folder with loc/doc/pattern files.")
            sys.exit(1)

    # ── Load data ─────────────────────────────────────────────────────────────
    print("=" * 66)
    t0 = time.perf_counter()
    objects  = load_objects(loc_path, doc_path)
    patterns = load_patterns(pattern_path)
    t_load   = time.perf_counter() - t0

    all_kws: set = set()
    for obj in objects.values():
        all_kws.update(obj["keywords"])

    # Build keyword→count map once (avoids O(n) scan per edge keyword below)
    kw_count: dict = {}
    for obj in objects.values():
        for kw in obj["keywords"]:
            kw_count[kw] = kw_count.get(kw, 0) + 1

    print(f"Dataset:  {data_dir}")
    print(f"Objects:  {len(objects):,}   |  Keywords: {len(all_kws):,}  "
          f"|  Patterns: {len(patterns)}")
    print(f"Load:     {t_load:.3f}s")

    if args.pattern >= len(patterns):
        print(f"Error: pattern {args.pattern} out of range (0..{len(patterns)-1}).")
        sys.exit(1)

    pattern = patterns[args.pattern]
    print()
    print(f"Pattern {args.pattern}  ({len(pattern)} edge{'s' if len(pattern) != 1 else ''}):")
    for e in pattern:
        n_a = kw_count.get(e["keyword_a"], 0)
        n_b = kw_count.get(e["keyword_b"], 0)
        print(f"  '{e['keyword_a']}' {_sign(e)} '{e['keyword_b']}'  "
              f"[{e['lower']:.6f}, {e['upper']:.6f}]  "
              f"({n_a:,} vs {n_b:,} objects)")

    # ── Build ESPM index ──────────────────────────────────────────────────────
    run_espm_algo = args.algo in ("espm", "both", "all")
    ilq = None

    if run_espm_algo:
        print()
        print(f"Building IL-Quadtree  "
              f"(split={args.split}, lmin={args.lmin}, lmax={args.lmax})...")
        t0 = time.perf_counter()
        ilq = build_ilq(objects, split_thresh=args.split, lmin=args.lmin, lmax=args.lmax)
        t_ilq = time.perf_counter() - t0
        kw_count = len(ilq.trees)
        print(f"  {kw_count:,} keyword trees built.  ({t_ilq:.3f}s)")

    # ── Build MSJ/MPJ grid index ───────────────────────────────────────────────
    run_msj_algo = args.algo in ("msj", "both", "all") and _paper1_available
    run_mpj_algo = args.algo in ("mpj", "all") and _paper1_available
    grid = None
    inv_idx = None

    if (run_msj_algo or run_mpj_algo) and not args.no_grid:
        print()
        print("Building inverted index + grid...")
        t0 = time.perf_counter()
        inv_idx = build_inverted_index(objects)
        all_uppers = sorted(e["upper"] for p in patterns for e in p)
        cell_size  = all_uppers[len(all_uppers) // 2]
        grid = GridIndex(objects, cell_size)
        print(f"  Grid cell size: {cell_size:.6f} deg.  ({time.perf_counter() - t0:.3f}s)")
    elif run_msj_algo or run_mpj_algo:
        t0 = time.perf_counter()
        inv_idx = build_inverted_index(objects)
        print(f"  Inverted index built.  ({time.perf_counter() - t0:.3f}s)")

    print()
    print("=" * 66)

    # ── Run algorithms ────────────────────────────────────────────────────────
    t_espm = t_msj = t_mpj = None
    espm_matches = msj_matches = mpj_matches = None

    if run_espm_algo:
        print(f"\nRunning ESPM  [lmin={args.lmin}, lmax={args.lmax}, "
              f"split={args.split}, max_matches={args.max_matches}]...\n")
        t0 = time.perf_counter()
        espm_matches = run_espm(objects, pattern, ilq,
                                max_matches=args.max_matches,
                                verbose=not args.quiet)
        t_espm = time.perf_counter() - t0
        print(f"\nESPM:  {len(espm_matches):,} matches   time: {t_espm:.3f}s")

    if run_msj_algo:
        grid_lbl = "grid" if grid else "no grid"
        print(f"\nRunning MSJ  [{grid_lbl}, max_matches={args.max_matches}]...\n")
        t0 = time.perf_counter()
        msj_matches = run_msj(objects, inv_idx, pattern, grid=grid,
                              max_matches=args.max_matches, dist_mode="euclidean")
        t_msj = time.perf_counter() - t0
        print(f"\nMSJ:   {len(msj_matches):,} matches   time: {t_msj:.3f}s")

    if run_mpj_algo:
        grid_lbl = "grid" if grid else "no grid"
        print(f"\nRunning MPJ  [{grid_lbl}, max_matches={args.max_matches}]...\n")
        t0 = time.perf_counter()
        mpj_matches = run_mpj(objects, inv_idx, pattern, grid=grid,
                              max_matches=args.max_matches, dist_mode="euclidean")
        t_mpj = time.perf_counter() - t0
        print(f"\nMPJ:   {len(mpj_matches):,} matches   time: {t_mpj:.3f}s")

    # ── Summary ───────────────────────────────────────────────────────────────
    if args.algo in ("both", "all"):
        print()
        print("=" * 66)
        if t_espm is not None:
            print(f"ESPM:  {len(espm_matches):,} matches   {t_espm:.3f}s")
        if t_msj is not None:
            print(f"MSJ:   {len(msj_matches):,} matches   {t_msj:.3f}s")
        if t_mpj is not None:
            print(f"MPJ:   {len(mpj_matches):,} matches   {t_mpj:.3f}s")

        if t_espm is not None and t_msj is not None and t_msj > 0:
            print(f"Speedup ESPM vs MSJ:  {t_msj / t_espm:.2f}x")
        if t_espm is not None and t_mpj is not None and t_mpj > 0:
            print(f"Speedup ESPM vs MPJ:  {t_mpj / t_espm:.2f}x")

        # Correctness check: only meaningful with unlimited matches (max_matches=0).
        # With a limit, the two algorithms may return different valid subsets —
        # that is expected, not a bug.
        if espm_matches is not None and msj_matches is not None:
            if args.max_matches == 0:
                def normalise(matches):
                    return {frozenset((k, v) for k, v in m.items()) for m in matches}
                e_set = normalise(espm_matches)
                m_set = normalise(msj_matches)
                if e_set == m_set:
                    print("Correctness: ESPM == MSJ [OK]")
                else:
                    only_e = e_set - m_set
                    only_m = m_set - e_set
                    print(f"Correctness: MISMATCH - "
                          f"{len(only_e)} only in ESPM, {len(only_m)} only in MSJ")
            else:
                print("Correctness: use --max-matches 0 for a full set comparison")

    # ── Show sample matches ────────────────────────────────────────────────────
    print()
    if espm_matches is not None:
        first = min(5, len(espm_matches))
        print(f"First {first} ESPM match{'es' if first != 1 else ''}:")
        print_matches(espm_matches, objects)
    elif msj_matches is not None:
        first = min(5, len(msj_matches))
        print(f"First {first} MSJ match{'es' if first != 1 else ''}:")
        print_matches(msj_matches, objects)
    elif mpj_matches is not None:
        first = min(5, len(mpj_matches))
        print(f"First {first} MPJ match{'es' if first != 1 else ''}:")
        print_matches(mpj_matches, objects)

    print()
    print("=" * 66)


if __name__ == "__main__":
    main()
