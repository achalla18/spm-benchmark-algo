"""
common.py  —  shared helpers for mesh benchmark.

Query graph: ring-lattice (circulant graph), k=4.
  Every node i connects to (i+1)%n, (i-1)%n, (i+2)%n, (i-2)%n.
  Every node has degree exactly 4 — uniform, no hubs.

  Q=20  → 40 edges   (vs 190 fully-connected, 37 scale-free)
  Q=40  → 80 edges   (vs 780,  77)
  Q=60  → 120 edges  (vs 1770, 117)

Database: same uniform-random point placement as all other benchmarks.
"""

import os
import sys
import time
import random
import threading

_here   = os.path.dirname(os.path.abspath(__file__))
_paper1 = os.path.normpath(os.path.join(_here, '..', 'paper1'))
_paper2 = os.path.normpath(os.path.join(_here, '..', 'paper2'))

for _p in (_paper1, _paper2):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from spm import build_inverted_index, GridIndex, run_pattern as run_mpj, run_msj
from espm import build_ilq, run_espm

# ── Fixed parameters ──────────────────────────────────────────────────────────
LAT_MIN, LAT_MAX = 51.0, 52.0
LON_MIN, LON_MAX = -0.5,  0.5
LOWER_DIST  = 0.0
UPPER_DIST  = 0.1
MAX_MATCHES = 10
TIMEOUT_S   = 1800        # 30 minutes
MESH_K      = 4           # connections per node (degree)
SEED        = 42

ILQ_PARAMS = {
    1_000:  {"split": 1,  "lmin": 2,  "lmax": 5},
    10_000: {"split": 64, "lmin": 4,  "lmax": 10},
    50_000: {"split": 64, "lmin": 6,  "lmax": 12},
}


# ── Database generation ───────────────────────────────────────────────────────

def make_objects(n_db, n_kw, seed=SEED):
    rng = random.Random(seed)
    kws = [f"class_{i:02d}" for i in range(n_kw)]
    objs = {}
    for oid in range(n_db):
        lat = rng.uniform(LAT_MIN, LAT_MAX)
        lon = rng.uniform(LON_MIN, LON_MAX)
        objs[oid] = {"lon": lon, "lat": lat, "keywords": {kws[oid % n_kw]}}
    return objs


# ── Mesh query generation (ring lattice, degree k) ────────────────────────────

def make_mesh_pattern(n_query, k=MESH_K):
    """
    Ring-lattice circulant graph: node i connects to i±1, i±2, ..., i±(k//2)
    (mod n_query).  Every node has degree exactly k.
    """
    kws   = [f"class_{i:02d}" for i in range(n_query)]
    edges = set()
    half  = k // 2
    for i in range(n_query):
        for delta in range(1, half + 1):
            j = (i + delta) % n_query
            edges.add((min(i, j), max(i, j)))
    return [
        {"keyword_a": kws[i], "keyword_b": kws[j],
         "lower": LOWER_DIST, "upper": UPPER_DIST,
         "flag1": False, "flag2": False}
        for (i, j) in sorted(edges)
    ]


# ── Timed wrapper ─────────────────────────────────────────────────────────────

def run_timed(fn, *args, timeout=TIMEOUT_S, **kwargs):
    box = [None]
    exc = [None]

    def _t():
        try:
            box[0] = fn(*args, **kwargs)
        except Exception as e:
            exc[0] = e

    t  = threading.Thread(target=_t, daemon=True)
    t0 = time.perf_counter()
    t.start()
    t.join(timeout)
    elapsed = time.perf_counter() - t0

    if t.is_alive():
        return None, elapsed, True
    if exc[0]:
        raise exc[0]
    return box[0], elapsed, False


# ── Run one (db_size, query_size) combination ─────────────────────────────────

def run_one(n_db, n_query):
    n_kw    = n_query
    ilq_p   = ILQ_PARAMS.get(n_db, {"split": 64, "lmin": 6, "lmax": 12})
    pattern = make_mesh_pattern(n_query)
    n_edges = len(pattern)
    objs_kw = n_db // n_kw

    print(f"\n{'='*68}")
    print(f"DB={n_db:,}  Q={n_query}  edges={n_edges}  "
          f"{objs_kw} obj/kw  timeout={TIMEOUT_S}s")
    print(f"{'='*68}")

    objects = make_objects(n_db, n_kw)
    inv_idx = build_inverted_index(objects)
    grid    = GridIndex(objects, UPPER_DIST)

    t0    = time.perf_counter()
    ilq   = build_ilq(objects, split_thresh=ilq_p["split"],
                      lmin=ilq_p["lmin"], lmax=ilq_p["lmax"])
    t_ilq = time.perf_counter() - t0
    print(f"  IL-Quadtree: {t_ilq:.3f}s")

    results = {}
    for algo, fn, kw in [
        ("MPJ",  run_mpj,  {"grid": grid, "max_matches": MAX_MATCHES, "dist_mode": "euclidean"}),
        ("MSJ",  run_msj,  {"grid": grid, "max_matches": MAX_MATCHES, "dist_mode": "euclidean"}),
        ("ESPM", run_espm, {"max_matches": MAX_MATCHES, "verbose": False}),
    ]:
        print(f"  [{algo}]  ...", end="", flush=True)
        if algo in ("MPJ", "MSJ"):
            m, elapsed, to = run_timed(fn, objects, inv_idx, pattern, **kw)
        else:
            m, elapsed, to = run_timed(fn, objects, pattern, ilq, **kw)

        paper = "ICDE 2018" if algo != "ESPM" else "TKDE 2020"
        if to:
            results[algo] = {"time_s": elapsed, "matches": None,
                             "timed_out": True, "paper": paper}
            print(f"  TIMED OUT (>{TIMEOUT_S}s)")
        else:
            n = len(m)
            cap = " (cap)" if n >= MAX_MATCHES else ""
            results[algo] = {"time_s": elapsed, "matches": n,
                             "timed_out": False, "paper": paper}
            print(f"  {n}{cap}   {elapsed:.4f}s")

    return results, {"n_db": n_db, "n_query": n_query, "n_edges": n_edges,
                     "objs_kw": objs_kw, "t_ilq": t_ilq, "ilq_params": ilq_p}
