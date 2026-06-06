"""
common.py  —  shared helpers for all Montevideo benchmarks.

Geographic region
-----------------
  Montevideo, Uruguay.
  Bounding box: lat [-35.40, -34.40] x lon [-56.70, -55.70]
                1.0 deg x 1.0 deg  (~111 km x ~91 km at this latitude)

  Upper distance: 0.1 deg (~11 km lat / ~9.1 km lon at -35 deg)
  Coverage ratio: 10% of box width — same scale as Region 1 (London).

  Note on euclidean vs haversine: the algorithms use euclidean distance
  in degrees. At lat=-35 deg, 1 deg longitude = cos(35)*111 = 90.9 km
  (vs ~70 km at London lat=51 deg). The degree-space math is identical
  to Region 1; only the physical km interpretation differs.

Three query topologies benchmarked in subdirectories:
  fully_connected/   — complete clique
  scale_free/        — Barabasi-Albert m=2
  mesh/              — ring-lattice k=4
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

from spm  import build_inverted_index, GridIndex, run_pattern as run_mpj, run_msj
from espm import build_ilq, run_espm

# ── Geographic / benchmark parameters ─────────────────────────────────────────
LAT_MIN, LAT_MAX = -35.40, -34.40   # Montevideo, Uruguay — 1 deg x 1 deg
LON_MIN, LON_MAX = -56.70, -55.70
LOWER_DIST  = 0.0
UPPER_DIST  = 0.1    # same absolute threshold as Region 1 (London)
MAX_MATCHES = 10
TIMEOUT_S   = 1800   # 30 minutes per algorithm
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


# ── Query generators ──────────────────────────────────────────────────────────

def make_fully_connected_pattern(n_query):
    kws   = [f"class_{i:02d}" for i in range(n_query)]
    edges = []
    for i in range(n_query):
        for j in range(i + 1, n_query):
            edges.append({"keyword_a": kws[i], "keyword_b": kws[j],
                          "lower": LOWER_DIST, "upper": UPPER_DIST,
                          "flag1": False, "flag2": False})
    return edges


def make_scale_free_pattern(n_query, m=2, seed=SEED):
    """Barabasi-Albert preferential attachment, m=2."""
    rng    = random.Random(seed + 1)
    kws    = [f"class_{i:02d}" for i in range(n_query)]
    edges  = set()
    degree = [0] * n_query
    for i in range(m + 1):
        for j in range(i + 1, m + 1):
            edges.add((i, j))
            degree[i] += 1
            degree[j] += 1
    for new_node in range(m + 1, n_query):
        total   = sum(degree)
        targets = set()
        while len(targets) < m:
            r = rng.uniform(0, total)
            cum = 0
            for node, d in enumerate(degree):
                cum += d
                if cum >= r and node != new_node and node not in targets:
                    targets.add(node)
                    break
        for t in targets:
            edges.add((min(new_node, t), max(new_node, t)))
            degree[new_node] += 1
            degree[t]        += 1
    return [{"keyword_a": kws[i], "keyword_b": kws[j],
             "lower": LOWER_DIST, "upper": UPPER_DIST,
             "flag1": False, "flag2": False}
            for (i, j) in sorted(edges)]


def make_mesh_pattern(n_query, k=4):
    """Ring-lattice: every node connects to its k//2 nearest neighbours each side."""
    kws   = [f"class_{i:02d}" for i in range(n_query)]
    edges = set()
    half  = k // 2
    for i in range(n_query):
        for delta in range(1, half + 1):
            j = (i + delta) % n_query
            edges.add((min(i, j), max(i, j)))
    return [{"keyword_a": kws[i], "keyword_b": kws[j],
             "lower": LOWER_DIST, "upper": UPPER_DIST,
             "flag1": False, "flag2": False}
            for (i, j) in sorted(edges)]


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


# ── Run one (db_size, pattern) combination ────────────────────────────────────

def run_one(n_db, pattern, label="", n_kw=None):
    if n_kw is None:
        kw_set = set()
        for e in pattern:
            kw_set.add(e["keyword_a"])
            kw_set.add(e["keyword_b"])
        n_kw = len(kw_set)

    n_edges = len(pattern)
    objs_kw = n_db // n_kw
    ilq_p   = ILQ_PARAMS.get(n_db, {"split": 64, "lmin": 6, "lmax": 12})

    print(f"\n{'='*68}")
    print(f"DB={n_db:,}  kw={n_kw}  obj/kw={objs_kw}  edges={n_edges}"
          + (f"  [{label}]" if label else ""))
    print(f"{'='*68}")

    objects = make_objects(n_db, n_kw)
    inv_idx = build_inverted_index(objects)
    grid    = GridIndex(objects, UPPER_DIST)

    t0  = time.perf_counter()
    ilq = build_ilq(objects, split_thresh=ilq_p["split"],
                    lmin=ilq_p["lmin"], lmax=ilq_p["lmax"])
    t_ilq = time.perf_counter() - t0
    print(f"  IL-Quadtree: {t_ilq:.3f}s")

    results = {}
    for algo_name, fn, fn_kwargs in [
        ("MPJ",  run_mpj,  {"grid": grid, "max_matches": MAX_MATCHES, "dist_mode": "euclidean"}),
        ("MSJ",  run_msj,  {"grid": grid, "max_matches": MAX_MATCHES, "dist_mode": "euclidean"}),
        ("ESPM", run_espm, {"max_matches": MAX_MATCHES, "verbose": False}),
    ]:
        print(f"  [{algo_name}] ...", end="", flush=True)
        if algo_name in ("MPJ", "MSJ"):
            matches, elapsed, timed_out = run_timed(fn, objects, inv_idx, pattern, **fn_kwargs)
        else:
            matches, elapsed, timed_out = run_timed(fn, objects, pattern, ilq, **fn_kwargs)

        paper = "TKDE 2020" if algo_name == "ESPM" else "ICDE 2018"
        if timed_out:
            results[algo_name] = {"time_s": elapsed, "matches": None,
                                  "timed_out": True, "paper": paper}
            print(f"  TIMED OUT (>{TIMEOUT_S}s)")
        else:
            n   = len(matches)
            cap = " (cap)" if n >= MAX_MATCHES else ""
            results[algo_name] = {"time_s": elapsed, "matches": n,
                                  "timed_out": False, "paper": paper}
            print(f"  {n} matches{cap}  {elapsed:.4f}s")

    return results, {"n_db": n_db, "n_kw": n_kw, "objs_kw": objs_kw,
                     "n_edges": n_edges, "t_ilq": t_ilq, "ilq_params": ilq_p}


def fmt_result(r):
    if r["timed_out"]:
        return "timeout", f">{r['time_s']:.0f}s"
    cap = " (cap)" if r["matches"] >= MAX_MATCHES else ""
    return f"{r['matches']}{cap}", f"{r['time_s']:.4f}s"
