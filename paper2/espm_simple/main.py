"""
main.py — ESPM simple runner

Usage:
    python main.py --data-dir ../../paper1/data/UK --pattern 0 --max-matches 20
    python main.py --data-dir ../../paper1/data/UK --pattern 40 --compare
    python main.py --toy                          # built-in toy dataset
"""

import argparse
import os
import sys
import time

from esp_m import (
    SpatialObject, PatternEdge,
    load_objects, load_patterns, build_inverted_index,
    run_espm,
)

# Optional: import MSJ from paper1 for comparison
_paper1 = os.path.join(os.path.dirname(__file__), '..', '..', 'paper1')
_have_paper1 = False
if os.path.isdir(_paper1):
    sys.path.insert(0, _paper1)
    try:
        from spm import (build_inverted_index as _mpj_inv,
                         GridIndex, run_msj, _KM_PER_DEG)
        _have_paper1 = True
    except ImportError:
        pass


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _sign_arrow(sign: str) -> str:
    return {"include": "--", "a_excludes_b": "->",
            "b_excludes_a": "<-", "mutual_exclusion": "<>"}.get(sign, sign)


def print_matches(matches: list, objects: dict, max_show: int = 5) -> None:
    if not matches:
        print("  (none)")
        return
    for i, m in enumerate(matches[:max_show]):
        parts = [f"{kw}: obj#{oid}" for kw, oid in sorted(m.items())]
        print(f"  [{i}]  " + ",  ".join(parts))
        for kw, oid in sorted(m.items()):
            obj = objects[oid]
            print(f"       {kw:20s}  lon={obj.lon:.5f}  lat={obj.lat:.5f}")


# ─── Toy dataset ──────────────────────────────────────────────────────────────

def run_toy() -> None:
    """
    Tiny built-in test to verify correctness.

    Objects:
      0  lon=0.0  lat=0.0   keywords={school}
      1  lon=0.0  lat=0.01  keywords={park}
      2  lon=0.0  lat=0.02  keywords={hospital}
      3  lon=1.0  lat=1.0   keywords={school}   ← too far away

    Pattern:
      school -- park     [0.00, 0.02]
      school -- hospital [0.00, 0.03]

    Expected single match: {school: 0, park: 1, hospital: 2}
    Object 3 must NOT appear (distance to park/hospital >> 0.03).
    """
    print("=" * 56)
    print("Toy dataset test")
    print("=" * 56)

    objects = {
        0: SpatialObject(0, 0.0,  0.0,  {"school"}),
        1: SpatialObject(1, 0.0,  0.01, {"park"}),
        2: SpatialObject(2, 0.0,  0.02, {"hospital"}),
        3: SpatialObject(3, 1.0,  1.0,  {"school"}),    # far away
    }

    pattern = [
        PatternEdge("school", "park",     lower=0.0, upper=0.02),
        PatternEdge("school", "hospital", lower=0.0, upper=0.03),
    ]

    print("Pattern:")
    for e in pattern:
        print(f"  {e.keyword_a} {_sign_arrow(e.sign)} {e.keyword_b}"
              f"  [{e.lower}, {e.upper}]  sign={e.sign}")
    print()

    matches = run_espm(objects, pattern, max_matches=0,
                       max_depth=5, leaf_size=1, verbose=True)
    print()
    print(f"Found {len(matches)} match(es)  (expected: 1)")
    for m in matches:
        print(" ", {kw: f"obj#{oid}" for kw, oid in sorted(m.items())})

    ok = (len(matches) == 1 and
          matches[0].get("school") == 0 and
          matches[0].get("park")   == 1 and
          matches[0].get("hospital") == 2)
    print("PASS" if ok else "FAIL  <-- check implementation")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Simple ESPM runner")
    parser.add_argument("--data-dir",    default="../../paper1/data/UK",
                        help="Folder with loc / doc / pattern files")
    parser.add_argument("--pattern",     type=int, default=0,
                        help="0-based pattern index (default: 0)")
    parser.add_argument("--max-matches", type=int, default=20,
                        help="Stop after N matches; 0 = unlimited (default: 20)")
    parser.add_argument("--max-depth",   type=int, default=15,
                        help="Quadtree max depth (default: 15)")
    parser.add_argument("--leaf-size",   type=int, default=64,
                        help="Max objects per leaf node (default: 64)")
    parser.add_argument("--compare",     action="store_true",
                        help="Also run MSJ from paper1 and compare results")
    parser.add_argument("--quiet",       action="store_true",
                        help="Suppress per-edge progress output")
    parser.add_argument("--toy",         action="store_true",
                        help="Run the built-in toy correctness test instead")
    args = parser.parse_args()

    if args.toy:
        run_toy()
        return

    # ── Resolve data dir ──────────────────────────────────────────────────────
    data_dir = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), args.data_dir)
        if not os.path.isabs(args.data_dir) else args.data_dir
    )
    for fname in ("loc", "doc", "pattern"):
        p = os.path.join(data_dir, fname)
        if not os.path.exists(p):
            print(f"Error: missing {p}")
            print("Hint: use --data-dir pointing to a folder containing loc/doc/pattern")
            sys.exit(1)

    # ── Load dataset ──────────────────────────────────────────────────────────
    print("=" * 60)
    t0 = time.perf_counter()

    # espm_simple uses SpatialObject; paper1's MSJ uses raw dicts.
    # We load both forms here when --compare is requested.
    objects_so = load_objects(os.path.join(data_dir, "loc"),
                               os.path.join(data_dir, "doc"))
    patterns   = load_patterns(os.path.join(data_dir, "pattern"))
    t_load     = time.perf_counter() - t0

    all_kws: set = set()
    for obj in objects_so.values():
        all_kws.update(obj.keywords)

    print(f"Dataset:  {data_dir}")
    print(f"Objects:  {len(objects_so):,}   Keywords: {len(all_kws):,}   Patterns: {len(patterns)}")
    print(f"Load:     {t_load:.3f}s")

    if args.pattern >= len(patterns):
        print(f"Error: pattern {args.pattern} is out of range (0..{len(patterns)-1}).")
        sys.exit(1)

    pattern = patterns[args.pattern]
    print()
    print(f"Pattern {args.pattern}  ({len(pattern)} edge{'s' if len(pattern)!=1 else ''}):")
    for e in pattern:
        n_a = sum(1 for o in objects_so.values() if e.keyword_a in o.keywords)
        n_b = sum(1 for o in objects_so.values() if e.keyword_b in o.keywords)
        print(f"  '{e.keyword_a}' {_sign_arrow(e.sign)} '{e.keyword_b}'"
              f"  [{e.lower:.6f}, {e.upper:.6f}]  sign={e.sign}"
              f"  ({n_a:,} vs {n_b:,} objects)")

    # ── Run ESPM ──────────────────────────────────────────────────────────────
    print()
    print(f"Running ESPM  [max_depth={args.max_depth}, leaf_size={args.leaf_size}, "
          f"max_matches={args.max_matches}]...")
    print()

    t0 = time.perf_counter()
    espm_matches = run_espm(
        objects_so, pattern,
        max_matches = args.max_matches,
        max_depth   = args.max_depth,
        leaf_size   = args.leaf_size,
        verbose     = not args.quiet,
    )
    t_espm = time.perf_counter() - t0

    print()
    print(f"ESPM:  {len(espm_matches):,} matches   {t_espm:.3f}s")

    # ── Optionally run MSJ for comparison ─────────────────────────────────────
    if args.compare:
        if not _have_paper1:
            print("(MSJ comparison unavailable — paper1/spm.py not found)")
        else:
            # Convert SpatialObject dict to the raw-dict format paper1 expects
            raw_objects = {oid: {"lon": o.lon, "lat": o.lat, "keywords": o.keywords}
                           for oid, o in objects_so.items()}
            raw_pattern = [{"keyword_a": e.keyword_a, "keyword_b": e.keyword_b,
                             "lower": e.lower, "upper": e.upper,
                             "flag1": e.sign in ("a_excludes_b", "mutual_exclusion"),
                             "flag2": e.sign in ("b_excludes_a", "mutual_exclusion")}
                            for e in pattern]

            inv_idx   = _mpj_inv(raw_objects)
            all_upper = sorted(ed.upper for p in patterns for ed in p)
            cell_size = all_upper[len(all_upper)//2]
            grid      = GridIndex(raw_objects, cell_size)

            print()
            print(f"Running MSJ  [grid, max_matches={args.max_matches}]...")
            t0 = time.perf_counter()
            msj_matches = run_msj(raw_objects, inv_idx, raw_pattern,
                                  grid=grid, max_matches=args.max_matches)
            t_msj = time.perf_counter() - t0

            print(f"MSJ:   {len(msj_matches):,} matches   {t_msj:.3f}s")

            # Correctness check (only meaningful with unlimited matches)
            if args.max_matches == 0:
                def norm(ml):
                    return {frozenset(m.items()) for m in ml}
                if norm(espm_matches) == norm(msj_matches):
                    print("Correctness: ESPM == MSJ [OK]")
                else:
                    only_e = norm(espm_matches) - norm(msj_matches)
                    only_m = norm(msj_matches)  - norm(espm_matches)
                    print(f"Correctness: MISMATCH - "
                          f"{len(only_e)} only in ESPM, {len(only_m)} only in MSJ")

            if t_espm > 0:
                print(f"Speedup ESPM vs MSJ: {t_msj/t_espm:.2f}x  "
                      f"({'faster' if t_msj > t_espm else 'slower'})")

    # ── Print sample matches ───────────────────────────────────────────────────
    print()
    show = min(5, len(espm_matches))
    print(f"First {show} match{'es' if show != 1 else ''}:")
    print_matches(espm_matches, objects_so)
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
