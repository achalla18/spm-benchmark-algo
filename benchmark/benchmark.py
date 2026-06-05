"""
benchmark.py
============
Synthetic SPMBench timing experiment.

Fixed parameters
----------------
  Database : 1000 point-nodes, metric (euclidean degrees),
             fully-connected topology, point nodes.
  upper    : 0.1 degrees (~11 km), lower=0, no exclusion flags.

Variable parameter
------------------
  --query-nodes N   size of the fully-connected query clique (default 20).
                    Keywords are set equal to N so each query node has a
                    unique keyword; objects/keyword = 1000 // N.

Runs MPJ (paper1, ICDE 2018), MSJ (paper1), and ESPM (paper2, TKDE 2020).
Writes per-run results to task2/results/benchmark_results_qN.md.
"""

import argparse
import os
import sys
import time
import random
from datetime import datetime, timezone

# ─── Locate paper directories ─────────────────────────────────────────────────
_here   = os.path.dirname(os.path.abspath(__file__))
_paper1 = os.path.normpath(os.path.join(_here, '..', 'paper1'))
_paper2 = os.path.normpath(os.path.join(_here, '..', 'paper2'))

for _p in (_paper1, _paper2):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from spm import (
    build_inverted_index,
    GridIndex,
    run_pattern as run_mpj,
    run_msj,
)
from espm import build_ilq, run_espm

# ─── Fixed parameters ─────────────────────────────────────────────────────────
N_DATABASE  = 1000
SEED        = 42
LAT_MIN, LAT_MAX = 51.0,  52.0
LON_MIN, LON_MAX = -0.5,   0.5
LOWER_DIST  = 0.0
UPPER_DIST  = 0.1
MAX_MATCHES = 10
ILQ_SPLIT   = 1
ILQ_LMIN    = 2
ILQ_LMAX    = 5


# ─── Data generation ──────────────────────────────────────────────────────────

def _make_objects(n_db, n_kw, seed):
    rng = random.Random(seed)
    kws = [f"class_{i:02d}" for i in range(n_kw)]
    objs = {}
    for oid in range(n_db):
        lat = rng.uniform(LAT_MIN, LAT_MAX)
        lon = rng.uniform(LON_MIN, LON_MAX)
        objs[oid] = {"lon": lon, "lat": lat, "keywords": {kws[oid % n_kw]}}
    return objs


def _make_pattern(n_query):
    kws   = [f"class_{i:02d}" for i in range(n_query)]
    edges = []
    for i in range(n_query):
        for j in range(i + 1, n_query):
            edges.append({
                "keyword_a": kws[i],
                "keyword_b": kws[j],
                "lower":     LOWER_DIST,
                "upper":     UPPER_DIST,
                "flag1":     False,
                "flag2":     False,
            })
    return edges


# ─── Core benchmark (callable from sweep scripts) ─────────────────────────────

def run_one(n_query):
    """
    Run MPJ / MSJ / ESPM for a fully-connected n_query-node query against a
    fixed 1000-node database.  Returns (results_dict, index_meta_dict).
    """
    n_kw    = n_query          # one unique keyword per query node
    n_edges = n_query * (n_query - 1) // 2

    print("=" * 68)
    print(f"Query size: {n_query} nodes  ({n_edges} edges)  "
          f"| DB: {N_DATABASE} nodes  | upper={UPPER_DIST} deg")
    print("=" * 68)

    t0      = time.perf_counter()
    objects = _make_objects(N_DATABASE, n_kw, SEED)
    pattern = _make_pattern(n_query)
    t_gen   = time.perf_counter() - t0
    print(f"\n[data]  {t_gen:.4f}s  |  {n_kw} keywords  "
          f"|  {N_DATABASE // n_kw} objects/keyword")

    t0      = time.perf_counter()
    inv_idx = build_inverted_index(objects)
    cell    = UPPER_DIST
    grid    = GridIndex(objects, cell)
    t_grid  = time.perf_counter() - t0
    print(f"[idx]   Grid {t_grid:.4f}s", end="")

    t0    = time.perf_counter()
    ilq   = build_ilq(objects, split_thresh=ILQ_SPLIT, lmin=ILQ_LMIN, lmax=ILQ_LMAX)
    t_ilq = time.perf_counter() - t0
    print(f"  |  IL-Quadtree {t_ilq:.4f}s")

    results = {}

    print(f"\n[MPJ]   ...", end="", flush=True)
    t0          = time.perf_counter()
    mpj_matches = run_mpj(objects, inv_idx, pattern, grid=grid,
                          max_matches=MAX_MATCHES, dist_mode="euclidean")
    t_mpj       = time.perf_counter() - t0
    results["MPJ"] = {"time_s": t_mpj, "matches": len(mpj_matches), "paper": "ICDE 2018"}
    print(f"  {len(mpj_matches)} matches  {t_mpj:.4f}s")

    print(f"[MSJ]   ...", end="", flush=True)
    t0          = time.perf_counter()
    msj_matches = run_msj(objects, inv_idx, pattern, grid=grid,
                          max_matches=MAX_MATCHES, dist_mode="euclidean")
    t_msj       = time.perf_counter() - t0
    results["MSJ"] = {"time_s": t_msj, "matches": len(msj_matches), "paper": "ICDE 2018"}
    print(f"  {len(msj_matches)} matches  {t_msj:.4f}s")

    print(f"[ESPM]  ...", end="", flush=True)
    t0           = time.perf_counter()
    espm_matches = run_espm(objects, pattern, ilq,
                            max_matches=MAX_MATCHES, verbose=False)
    t_espm       = time.perf_counter() - t0
    results["ESPM"] = {"time_s": t_espm, "matches": len(espm_matches), "paper": "TKDE 2020"}
    print(f"  {len(espm_matches)} matches  {t_espm:.4f}s")

    return results, {"t_gen": t_gen, "t_grid": t_grid, "t_ilq": t_ilq,
                     "n_query": n_query, "n_kw": n_kw}


# ─── Single-run report ────────────────────────────────────────────────────────

def write_single_results(results, meta):
    n_query = meta["n_query"]
    n_kw    = meta["n_kw"]
    n_edges = n_query * (n_query - 1) // 2
    now     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out_dir  = os.path.join(_here, "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"benchmark_results_q{n_query}.md")

    mpj_t  = results.get("MPJ",  {}).get("time_s")
    msj_t  = results.get("MSJ",  {}).get("time_s")
    espm_t = results.get("ESPM", {}).get("time_s")

    def _speedup_row(la, ta, lb, tb):
        if ta <= tb:
            return f"| {la} vs {lb} | {la} | {tb/ta:.2f}x |"
        return f"| {la} vs {lb} | {lb} | {ta/tb:.2f}x |"

    lines = [
        f"# SPMBench Results — Q={n_query}\n",
        f"_Generated {now}_\n",
        "## Scenario",
        "",
        "| Property | Value |",
        "|----------|-------|",
        f"| Database nodes | {N_DATABASE:,} |",
        f"| Database edge type | metric (euclidean degrees) |",
        f"| Database edge distribution | fully connected |",
        f"| Database node type | point |",
        f"| Unique keywords | {n_kw} |",
        f"| Objects per keyword | {N_DATABASE // n_kw} |",
        f"| Query nodes | {n_query} |",
        f"| Query edges | {n_edges} (fully connected clique) |",
        f"| Distance bounds | [{LOWER_DIST}, {UPPER_DIST}] deg (~{UPPER_DIST*111:.1f} km) |",
        f"| Max matches per algorithm | {MAX_MATCHES} |",
        "",
        "## Index Build Times",
        "",
        "| Index | Time (s) |",
        "|-------|----------|",
        f"| Inverted index + Grid | {meta['t_grid']:.4f} |",
        f"| IL-Quadtree (ESPM) | {meta['t_ilq']:.4f} |",
        "",
        "## Algorithm Timing",
        "",
        "| Algorithm | Paper | Matches | Time (s) |",
        "|-----------|-------|---------|----------|",
    ]

    for algo, res in results.items():
        m = f"{res['matches']:,}" + (f" (cap {MAX_MATCHES})" if res["matches"] >= MAX_MATCHES else "")
        lines.append(f"| {algo} | {res['paper']} | {m} | {res['time_s']:.4f} |")

    lines += ["", "## Speedups", "",
              "| Comparison | Faster | By |",
              "|------------|--------|----|"]
    if mpj_t and msj_t:
        lines.append(_speedup_row("MPJ", mpj_t, "MSJ", msj_t))
    if mpj_t and espm_t:
        lines.append(_speedup_row("MPJ", mpj_t, "ESPM", espm_t))
    if msj_t and espm_t:
        lines.append(_speedup_row("MSJ", msj_t, "ESPM", espm_t))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPMBench single-size benchmark")
    parser.add_argument("--query-nodes", type=int, default=20,
                        help="Number of query nodes (fully-connected clique). Default 20.")
    args = parser.parse_args()

    results, meta = run_one(args.query_nodes)
    out = write_single_results(results, meta)

    print()
    print("=" * 68)
    print(f"{'Algorithm':<10} {'Matches':>10} {'Time (s)':>12}")
    print("-" * 34)
    for algo, res in results.items():
        print(f"{algo:<10} {res['matches']:>10,} {res['time_s']:>12.4f}")
    print("=" * 68)
    print(f"\nResults -> {out}")
