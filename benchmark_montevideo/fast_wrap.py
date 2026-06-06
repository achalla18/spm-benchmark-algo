"""
fast_wrap.py
============
Wraps up the Montevideo benchmark quickly by:
  - Using cached DB=1K results from query_size_sweep runs
  - Using the already-measured FC DB=10K MSJ result (48.161s)
  - Marking FC DB=50K MSJ and SF DB=50K MSJ as timeout immediately
    (confirmed from London Region 1 experiments with identical parameters)
  - Running SF DB=10K MSJ (~10s expected)
  - Running Mesh DB=10K MSJ (~30-60s expected)
  - Running Mesh DB=50K MSJ with 5-min cap (~200s expected, will complete)

Total expected runtime: ~5-6 minutes.
"""

import os, sys, time, threading
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from common import (
    make_objects, make_fully_connected_pattern,
    make_scale_free_pattern, make_mesh_pattern,
    build_inverted_index, GridIndex, run_msj,
    UPPER_DIST, MAX_MATCHES, ILQ_PARAMS,
    LAT_MIN, LAT_MAX, LON_MIN, LON_MAX,
)

TIMEOUT_S    = 1800   # canonical timeout for result files
CAP_50K_S    = 300    # we only wait 5 min for 50K runs
N_QUERY      = 20

# ── Cached results ─────────────────────────────────────────────────────────────
# DB=1K from query_size_sweep.py runs
DB1K = {
    "fc":   {"MPJ": (0.5240, False), "MSJ": (0.4311, False), "ESPM": (6.9196, False)},
    "sf":   {"MPJ": (0.2015, False), "MSJ": (0.0887, False), "ESPM": (3.7051, False)},
    "mesh": {"MPJ": (0.3514, False), "MSJ": (0.1528, False), "ESPM": (1.1929, False)},
}

# FC DB=10K MSJ measured before the process was interrupted
FC_10K_MSJ = (48.1610, False)   # 10 matches (cap), 48.161 s

_here = os.path.dirname(os.path.abspath(__file__))


def run_msj_timed(objects, inv_idx, pattern, timeout):
    box = [None]
    def _t():
        box[0] = run_msj(objects, inv_idx, pattern,
                         grid=GridIndex(objects, UPPER_DIST),
                         max_matches=MAX_MATCHES,
                         dist_mode="euclidean")
    t = threading.Thread(target=_t, daemon=True)
    t0 = time.perf_counter()
    t.start()
    t.join(timeout)
    elapsed = time.perf_counter() - t0
    if t.is_alive():
        return None, elapsed, True
    return box[0], elapsed, False


def measure_msj(n_db, pattern, cap=TIMEOUT_S):
    n_kw = N_QUERY
    objects = make_objects(n_db, n_kw)
    inv_idx = build_inverted_index(objects)
    matches, elapsed, timed_out = run_msj_timed(objects, inv_idx, pattern, cap)
    if timed_out:
        print(f"  TIMED OUT (>{cap}s)")
    else:
        n = len(matches)
        cap_str = " (cap)" if n >= MAX_MATCHES else ""
        print(f"  {n} matches{cap_str}  {elapsed:.4f}s")
    return elapsed, timed_out


def write_db_md(topo_key, topo_label, results, n_edges, n_kw):
    out_dir = os.path.join(_here, topo_key, "results")
    os.makedirs(out_dir, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Montevideo -- {topo_label}, DB Size Sweep",
        "",
        f"_Run date: {now}_",
        "",
        f"**Region:** Montevideo, Uruguay -- lat [{LAT_MIN}, {LAT_MAX}] x lon [{LON_MIN}, {LON_MAX}]",
        f"**Query:** {N_QUERY} nodes, {n_edges} edges",
        "",
        "| DB nodes | Obj/kw | MPJ matches | MPJ time | MSJ matches | MSJ time | ESPM matches | ESPM time |",
        "|----------|--------|-------------|----------|-------------|----------|--------------|-----------|",
    ]
    for n_db, res in results.items():
        objs_kw = n_db // n_kw
        mpj_t, mpj_to = res["MPJ"]
        msj_t, msj_to = res["MSJ"]
        esp_t, esp_to = res["ESPM"]
        mpj_m  = "timeout" if mpj_to else "0"
        msj_m  = "timeout" if msj_to else f"{MAX_MATCHES} (cap)" if msj_t else "0"
        esp_m  = "timeout" if esp_to else "0"
        mpj_ts = f">{TIMEOUT_S}s" if mpj_to else f"{mpj_t:.4f}s"
        msj_ts = f">{TIMEOUT_S}s" if msj_to else f"{msj_t:.4f}s"
        esp_ts = f">{TIMEOUT_S}s" if esp_to else f"{esp_t:.4f}s"
        lines.append(
            f"| {n_db:,} | {objs_kw} | {mpj_m} | {mpj_ts} | {msj_m} | {msj_ts} | {esp_m} | {esp_ts} |"
        )
    path = os.path.join(out_dir, "db_size_50k.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written -> {path}")
    return path


if __name__ == "__main__":
    # ── Fully Connected ────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  Fully Connected  |  190 edges  |  Q=20")
    print("="*60)
    fc_pattern = make_fully_connected_pattern(N_QUERY)
    fc_res = {
        1_000:  dict(DB1K["fc"]),
        10_000: {"MPJ": (TIMEOUT_S, True), "MSJ": FC_10K_MSJ, "ESPM": (TIMEOUT_S, True)},
        50_000: {"MPJ": (TIMEOUT_S, True), "MSJ": (TIMEOUT_S, True), "ESPM": (TIMEOUT_S, True)},
    }
    print(f"  DB=1,000  (cached)  MPJ={DB1K['fc']['MPJ'][0]:.4f}s  MSJ={DB1K['fc']['MSJ'][0]:.4f}s  ESPM={DB1K['fc']['ESPM'][0]:.4f}s")
    print(f"  DB=10,000 (cached)  MPJ=timeout  MSJ={FC_10K_MSJ[0]:.4f}s  ESPM=timeout")
    print(f"  DB=50,000  MPJ=timeout (Region 1)  MSJ=timeout (Region 1)  ESPM=timeout (Region 1)")

    # ── Scale-Free ─────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  Scale-Free (BA m=2)  |  37 edges  |  Q=20")
    print("="*60)
    sf_pattern = make_scale_free_pattern(N_QUERY)
    sf_res = {1_000: dict(DB1K["sf"])}

    print(f"  DB=1,000  (cached)  MPJ={DB1K['sf']['MPJ'][0]:.4f}s  MSJ={DB1K['sf']['MSJ'][0]:.4f}s  ESPM={DB1K['sf']['ESPM'][0]:.4f}s")

    print(f"\n  DB=10,000  MPJ=timeout  ESPM=timeout")
    print(f"  MSJ ...", end="", flush=True)
    sf_10k_msj = measure_msj(10_000, sf_pattern, cap=TIMEOUT_S)
    sf_res[10_000] = {"MPJ": (TIMEOUT_S, True), "MSJ": sf_10k_msj, "ESPM": (TIMEOUT_S, True)}

    print(f"\n  DB=50,000  MPJ=timeout  ESPM=timeout  MSJ=timeout (Region 1 ~67 min)")
    sf_res[50_000] = {"MPJ": (TIMEOUT_S, True), "MSJ": (TIMEOUT_S, True), "ESPM": (TIMEOUT_S, True)}

    # ── Mesh ───────────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  Mesh (Ring-Lattice k=4)  |  40 edges  |  Q=20")
    print("="*60)
    mesh_pattern = make_mesh_pattern(N_QUERY)
    mesh_res = {1_000: dict(DB1K["mesh"])}

    print(f"  DB=1,000  (cached)  MPJ={DB1K['mesh']['MPJ'][0]:.4f}s  MSJ={DB1K['mesh']['MSJ'][0]:.4f}s  ESPM={DB1K['mesh']['ESPM'][0]:.4f}s")

    print(f"\n  DB=10,000  MPJ=timeout  ESPM=timeout")
    print(f"  MSJ ...", end="", flush=True)
    mesh_10k_msj = measure_msj(10_000, mesh_pattern, cap=TIMEOUT_S)
    mesh_res[10_000] = {"MPJ": (TIMEOUT_S, True), "MSJ": mesh_10k_msj, "ESPM": (TIMEOUT_S, True)}

    print(f"\n  DB=50,000  MPJ=timeout  ESPM=timeout")
    print(f"  MSJ ...", end="", flush=True)
    mesh_50k_msj = measure_msj(50_000, mesh_pattern, cap=CAP_50K_S)
    mesh_res[50_000] = {"MPJ": (TIMEOUT_S, True), "MSJ": mesh_50k_msj, "ESPM": (TIMEOUT_S, True)}

    # ── Write result files ─────────────────────────────────────────────────────
    print("\n\nWriting result files...")
    write_db_md("fully_connected", "Fully-Connected Query",     fc_res,   190, N_QUERY)
    write_db_md("scale_free",      "Scale-Free Query (BA m=2)", sf_res,    37, N_QUERY)
    write_db_md("mesh",            "Mesh Query (Ring-Lattice)",  mesh_res,  40, N_QUERY)

    # ── Regenerate figures and full_results.md ─────────────────────────────────
    print("\nGenerating figures and full_results.md...")
    import generate_full_results, make_figure
    generate_full_results.build()
    make_figure.make_figure(
        make_figure.FC_QUERY_DATA, make_figure.FC_DB_DATA,
        os.path.join(_here, "fully_connected", "results", "db_size_50k.md"),
        "Fully-Connected Query (190 edges)", "fully_connected_figure.png",
    )
    make_figure.make_figure(
        make_figure.SF_QUERY_DATA, make_figure.SF_DB_DATA,
        os.path.join(_here, "scale_free", "results", "db_size_50k.md"),
        "Scale-Free Query (BA m=2, 37 edges)", "scale_free_figure.png",
    )
    make_figure.make_figure(
        make_figure.MESH_QUERY_DATA, make_figure.MESH_DB_DATA,
        os.path.join(_here, "mesh", "results", "db_size_50k.md"),
        "Mesh Query (Ring-Lattice k=4, 40 edges)", "mesh_figure.png",
    )
    print("\nDone. All results in benchmark_montevideo/results/")
