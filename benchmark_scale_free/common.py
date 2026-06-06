"""
common.py  —  shared data-generation helpers for all scale-free sweeps.

Query graph: Barabási-Albert (BA) scale-free graph, m=2.
  Each new node attaches preferentially to 2 already-present nodes.
  Q=20 → ~36 edges   (vs 190 for the fully-connected clique)
  Q=40 → ~76 edges   (vs 780)
  Q=60 → ~116 edges  (vs 1,770)

Database: uniform-random points, same as the fully-connected benchmarks.
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
BA_M        = 2           # BA attachments per new node
SEED        = 42

ILQ_PARAMS = {
    1_000:  {"split": 1,  "lmin": 2,  "lmax": 5},
    10_000: {"split": 64, "lmin": 4,  "lmax": 10},
    50_000: {"split": 64, "lmin": 6,  "lmax": 12},
}


# ── Database generation ───────────────────────────────────────────────────────

def make_objects(n_db, n_kw, seed=SEED):
    """Uniform-random point nodes, round-robin keyword assignment."""
    rng = random.Random(seed)
    kws = [f"class_{i:02d}" for i in range(n_kw)]
    objs = {}
    for oid in range(n_db):
        lat = rng.uniform(LAT_MIN, LAT_MAX)
        lon = rng.uniform(LON_MIN, LON_MAX)
        objs[oid] = {"lon": lon, "lat": lat, "keywords": {kws[oid % n_kw]}}
    return objs


# ── Scale-free query generation (Barabási-Albert, m=2) ────────────────────────

def make_scale_free_pattern(n_query, m=BA_M, seed=SEED):
    """
    Build a BA scale-free query graph and return it as a list of SPM edge dicts.
    Node i ↔ keyword class_i.  All edges have lower=0, upper=UPPER_DIST.
    """
    rng   = random.Random(seed)
    kws   = [f"class_{i:02d}" for i in range(n_query)]

    # Seed: complete graph on the first m+1 nodes
    adj   = set()
    deg   = [0] * n_query
    for i in range(min(m + 1, n_query)):
        for j in range(i + 1, min(m + 1, n_query)):
            adj.add((i, j))
            deg[i] += 1
            deg[j] += 1

    # Preferential attachment for remaining nodes
    for new in range(m + 1, n_query):
        # Build probability pool proportional to current degree
        pool = [node for node in range(new) for _ in range(max(1, deg[node]))]
        chosen = set()
        while len(chosen) < m:
            chosen.add(rng.choice(pool))
        for node in chosen:
            e = (min(new, node), max(new, node))
            if e not in adj:
                adj.add(e)
                deg[new] += 1
                deg[node] += 1

    return [
        {"keyword_a": kws[i], "keyword_b": kws[j],
         "lower": LOWER_DIST, "upper": UPPER_DIST,
         "flag1": False, "flag2": False}
        for (i, j) in sorted(adj)
    ]


# ── Timed wrapper ─────────────────────────────────────────────────────────────

def run_timed(fn, *args, timeout=TIMEOUT_S, **kwargs):
    """Run fn in a daemon thread with a wall-clock timeout."""
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
    pattern = make_scale_free_pattern(n_query)
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
            results[algo] = {"time_s": elapsed, "matches": n,
                             "timed_out": False, "paper": paper}
            cap = " (cap)" if n >= MAX_MATCHES else ""
            print(f"  {n}{cap}   {elapsed:.4f}s")

    return results, {"n_db": n_db, "n_query": n_query, "n_edges": n_edges,
                     "objs_kw": objs_kw, "t_ilq": t_ilq, "ilq_params": ilq_p}
