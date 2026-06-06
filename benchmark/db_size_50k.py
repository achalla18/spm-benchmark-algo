"""
db_size_50k.py
==============
DB size sweep: 1,000 / 10,000 / 50,000 nodes.
Query fixed at Q=20 (fully-connected clique, 190 edges).

All other parameters unchanged from the original sweep:
  metric edges, fully-connected DB, point nodes
  upper=0.1 deg (~11.1 km), lower=0, no exclusion flags
  seed=42, max_matches=10, timeout=1800s (30 min) per algorithm

IL-Quadtree parameters:
  DB=1,000   : split=1,  lmin=2,  lmax=5
  DB=10,000  : split=64, lmin=4,  lmax=10
  DB=50,000  : split=64, lmin=6,  lmax=12

Results -> benchmark/results/db_size_50k.md  (new file)
"""

import os
import sys
import time
import random
import threading
from datetime import datetime, timezone

_here   = os.path.dirname(os.path.abspath(__file__))
_paper1 = os.path.normpath(os.path.join(_here, '..', 'paper1'))
_paper2 = os.path.normpath(os.path.join(_here, '..', 'paper2'))

for _p in (_paper1, _paper2):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from spm import build_inverted_index, GridIndex, run_pattern as run_mpj, run_msj
from espm import build_ilq, run_espm

# ─── Parameters ───────────────────────────────────────────────────────────────
N_QUERY     = 20
N_KEYWORDS  = 20
SEED        = 42
LAT_MIN, LAT_MAX = 51.0, 52.0
LON_MIN, LON_MAX = -0.5,  0.5
LOWER_DIST  = 0.0
UPPER_DIST  = 0.1
MAX_MATCHES = 10
TIMEOUT_S   = 1800   # 30 minutes

DB_SIZES = [1_000, 10_000, 50_000]

ILQ_PARAMS = {
    1_000:  {"split": 1,  "lmin": 2,  "lmax": 5},
    10_000: {"split": 64, "lmin": 4,  "lmax": 10},
    50_000: {"split": 64, "lmin": 6,  "lmax": 12},
}


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
                "keyword_a": kws[i], "keyword_b": kws[j],
                "lower": LOWER_DIST, "upper": UPPER_DIST,
                "flag1": False, "flag2": False,
            })
    return edges


# ─── Timed wrapper ────────────────────────────────────────────────────────────

def _run_timed(fn, *args, timeout=TIMEOUT_S, **kwargs):
    container = [None]
    exc       = [None]

    def _target():
        try:
            container[0] = fn(*args, **kwargs)
        except Exception as e:
            exc[0] = e

    t = threading.Thread(target=_target, daemon=True)
    t0 = time.perf_counter()
    t.start()
    t.join(timeout)
    elapsed = time.perf_counter() - t0

    if t.is_alive():
        return None, elapsed, True
    if exc[0]:
        raise exc[0]
    return container[0], elapsed, False


# ─── Single DB size run ───────────────────────────────────────────────────────

def run_one(n_db):
    ilq_p   = ILQ_PARAMS[n_db]
    n_edges = N_QUERY * (N_QUERY - 1) // 2
    objs_kw = n_db // N_KEYWORDS

    print(f"\n{'='*68}")
    print(f"DB={n_db:,}  |  Q={N_QUERY} ({n_edges} edges)  "
          f"|  {objs_kw} obj/kw  |  timeout={TIMEOUT_S}s")
    print(f"{'='*68}")

    objects = _make_objects(n_db, N_KEYWORDS, SEED)
    pattern = _make_pattern(N_QUERY)

    inv_idx = build_inverted_index(objects)
    grid    = GridIndex(objects, UPPER_DIST)

    t0    = time.perf_counter()
    ilq   = build_ilq(objects, split_thresh=ilq_p["split"],
                      lmin=ilq_p["lmin"], lmax=ilq_p["lmax"])
    t_ilq = time.perf_counter() - t0
    print(f"  IL-Quadtree: {t_ilq:.3f}s  "
          f"(split={ilq_p['split']} lmin={ilq_p['lmin']} lmax={ilq_p['lmax']})")

    results = {}

    for algo_name, fn, fn_kwargs in [
        ("MPJ",  run_mpj,  {"grid": grid, "max_matches": MAX_MATCHES, "dist_mode": "euclidean"}),
        ("MSJ",  run_msj,  {"grid": grid, "max_matches": MAX_MATCHES, "dist_mode": "euclidean"}),
        ("ESPM", run_espm, {"max_matches": MAX_MATCHES, "verbose": False}),
    ]:
        print(f"  [{algo_name}]  ...", end="", flush=True)

        if algo_name in ("MPJ", "MSJ"):
            matches, elapsed, timed_out = _run_timed(
                fn, objects, inv_idx, pattern, timeout=TIMEOUT_S, **fn_kwargs)
        else:
            matches, elapsed, timed_out = _run_timed(
                fn, objects, pattern, ilq, timeout=TIMEOUT_S, **fn_kwargs)

        if timed_out:
            results[algo_name] = {"time_s": elapsed, "matches": None,
                                  "timed_out": True,
                                  "paper": "ICDE 2018" if algo_name != "ESPM" else "TKDE 2020"}
            print(f"  TIMED OUT (>{TIMEOUT_S}s)")
        else:
            n = len(matches)
            cap = " (cap)" if n >= MAX_MATCHES else ""
            results[algo_name] = {"time_s": elapsed, "matches": n,
                                  "timed_out": False,
                                  "paper": "ICDE 2018" if algo_name != "ESPM" else "TKDE 2020"}
            print(f"  {n} matches{cap}   {elapsed:.4f}s")

    return results, {"n_db": n_db, "objs_kw": objs_kw,
                     "t_ilq": t_ilq, "ilq_params": ilq_p}


# ─── Report ───────────────────────────────────────────────────────────────────

def write_results(all_results):
    out_dir  = os.path.join(_here, "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "db_size_50k.md")
    now      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n_edges  = N_QUERY * (N_QUERY - 1) // 2

    def _fmt(r):
        if r["timed_out"]:
            return f"timeout (>{TIMEOUT_S}s)", f">{r['time_s']:.0f}s"
        cap = " (cap)" if r["matches"] >= MAX_MATCHES else ""
        return f"{r['matches']}{cap}", f"{r['time_s']:.4f}"

    lines = [
        "# SPMBench — Database Size Sweep (Extended: up to 50,000 nodes)\n",
        f"_Run date: {now}_\n",
        "---",
        "",
        "## Papers under test",
        "",
        "| Label | Paper | Algorithms |",
        "|-------|-------|------------|",
        "| Paper 1 | Fang et al., **ICDE 2018** | MPJ (Multi-Pair Join), MSJ (Multi-Star Join) |",
        "| Paper 2 | Chen et al., **TKDE 2020** | ESPM (IL-Quadtree, n-match / e-match / join) |",
        "",
        "---",
        "",
        "## Setup",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Query nodes | {N_QUERY} (fully connected clique, {n_edges} edges) |",
        f"| Distance bounds | lower={LOWER_DIST} deg, upper={UPPER_DIST} deg (~{UPPER_DIST*111:.1f} km) |",
        f"| Edge flags | Mutual inclusion, no exclusion |",
        f"| Max matches | {MAX_MATCHES} per algorithm |",
        f"| Timeout per algorithm | {TIMEOUT_S} s (30 min) |",
        f"| DB node type | Point |",
        f"| DB edge type | Metric (Euclidean degrees) |",
        f"| DB edge distribution | Fully connected |",
        f"| Bounding box | lat [51.0, 52.0] × lon [−0.5, 0.5] |",
        f"| Node placement | Uniform random, seed={SEED} |",
        f"| Keywords | {N_KEYWORDS} (one per query node) |",
        f"| Grid cell size | {UPPER_DIST} deg |",
        "",
        "| DB nodes | Obj / keyword | IL-Quadtree params |",
        "|----------|---------------|--------------------|",
    ]

    for n_db in DB_SIZES:
        _, meta = all_results[n_db]
        p = meta["ilq_params"]
        lines.append(
            f"| {n_db:,} | {meta['objs_kw']} "
            f"| split={p['split']}, lmin={p['lmin']}, lmax={p['lmax']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Timing results",
        "",
        "| DB nodes | Obj/kw | Algorithm | Paper | Matches | Time (s) |",
        "|----------|--------|-----------|-------|---------|----------|",
    ]

    for n_db in DB_SIZES:
        res, meta = all_results[n_db]
        for algo, r in res.items():
            m_str, t_str = _fmt(r)
            lines.append(
                f"| **{n_db:,}** | {meta['objs_kw']} | {algo} "
                f"| {r['paper']} | {m_str} | {t_str} |"
            )
        lines.append("|  |  |  |  |  |  |")

    lines += [
        "",
        "---",
        "",
        "## Scaling across DB sizes",
        "",
        "| Algorithm | 1,000 (s) | 10,000 (s) | 50,000 (s) | 1K→10K | 10K→50K |",
        "|-----------|-----------|-----------|-----------|--------|---------|",
    ]

    for algo in ["MPJ", "MSJ", "ESPM"]:
        times = []
        for n_db in DB_SIZES:
            r = all_results[n_db][0][algo]
            times.append((r["time_s"], r["timed_out"]))

        def _cell(t, to):
            return f"timeout (>{TIMEOUT_S}s)" if to else f"{t:.4f}"

        def _factor(t1, to1, t2, to2):
            if to1 or to2:
                return "N/A"
            return f"{t2/t1:.1f}×"

        t1, to1 = times[0]
        t2, to2 = times[1]
        t3, to3 = times[2]

        lines.append(
            f"| {algo} | {_cell(t1,to1)} | {_cell(t2,to2)} | {_cell(t3,to3)} "
            f"| {_factor(t1,to1,t2,to2)} | {_factor(t2,to2,t3,to3)} |"
        )

    lines += ["", "---", "", "## Notes", "",
              f"- Matches marked `(cap)` hit the max_matches={MAX_MATCHES} limit.",
              f"- timeout = algorithm ran for the full {TIMEOUT_S}s without completing.",
              f"- MPJ lacks anchor-pruning → exponential join tree at high density.",
              f"- MSJ uses anchor-pruning → scales better but still grows with density.",
              f"- ESPM n-match overhead grows with edge count (190 edges × tree levels).",
              ""]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    all_results = {}
    for n_db in DB_SIZES:
        res, meta = run_one(n_db)
        all_results[n_db] = (res, meta)

    out = write_results(all_results)

    print(f"\n{'='*68}")
    print(f"{'DB':>8}  {'Algorithm':<8} {'Matches':>10}  {'Time':>12}")
    print("-" * 46)
    for n_db in DB_SIZES:
        res, _ = all_results[n_db]
        for algo, r in res.items():
            m = "timeout" if r["timed_out"] else str(r["matches"])
            t = f">{TIMEOUT_S}s" if r["timed_out"] else f"{r['time_s']:.4f}s"
            print(f"{n_db:>8,}  {algo:<8} {m:>10}  {t:>12}")
        print()
    print(f"{'='*68}")
    print(f"\nResults -> {out}")
