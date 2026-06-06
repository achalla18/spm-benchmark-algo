"""
run_msj_only.py
===============
Targeted script: runs ONLY MSJ at DB=10,000 and DB=50,000 for all three
query topologies.  MPJ and ESPM are recorded as timeout (established by
Region 1 experiments with identical parameters).

Writes final db_size_50k.md files for each topology, then regenerates
full_results.md and all three figures.
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

TIMEOUT_S   = 1800
DB_SIZES    = [1_000, 10_000, 50_000]
N_QUERY     = 20

# Known DB=1,000 timings from the query_size_sweep runs
DB1K = {
    "fc":   {"MPJ": (0.5240, False), "MSJ": (0.4311, False), "ESPM": (6.9196, False)},
    "sf":   {"MPJ": (0.2015, False), "MSJ": (0.0887, False), "ESPM": (3.7051, False)},
    "mesh": {"MPJ": (0.3514, False), "MSJ": (0.1528, False), "ESPM": (1.1929, False)},
}

_here = os.path.dirname(os.path.abspath(__file__))


def run_msj_timed(objects, inv_idx, pattern, timeout=TIMEOUT_S):
    """Run MSJ with a wall-clock timeout.  Returns (matches, elapsed, timed_out)."""
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


def run_topology(label, key, pattern_fn):
    pattern = pattern_fn(N_QUERY)
    n_edges = len(pattern)
    n_kw    = N_QUERY
    results = {}

    print(f"\n{'='*60}")
    print(f"  {label}  |  {n_edges} edges  |  Q={N_QUERY}")
    print(f"{'='*60}")

    # DB=1,000 — already measured, use cached values
    results[1_000] = {
        "MPJ":  DB1K[key]["MPJ"],
        "MSJ":  DB1K[key]["MSJ"],
        "ESPM": DB1K[key]["ESPM"],
    }
    print(f"  DB=1,000   MPJ={DB1K[key]['MPJ'][0]:.4f}s  "
          f"MSJ={DB1K[key]['MSJ'][0]:.4f}s  ESPM={DB1K[key]['ESPM'][0]:.4f}s  (cached)")

    # DB=10,000 and 50,000 — MPJ and ESPM timeout (known); run MSJ only
    for n_db in [10_000, 50_000]:
        objs_kw = n_db // n_kw
        print(f"\n  DB={n_db:,}  ({objs_kw} obj/kw)")
        print(f"    MPJ  -> timeout  (established by Region 1)")
        print(f"    ESPM -> timeout  (established by Region 1)")
        print(f"    MSJ  ...", end="", flush=True)

        objects = make_objects(n_db, n_kw)
        inv_idx = build_inverted_index(objects)
        matches, elapsed, timed_out = run_msj_timed(objects, inv_idx, pattern)

        if timed_out:
            print(f"  TIMED OUT (>{TIMEOUT_S}s)")
        else:
            n   = len(matches)
            cap = " (cap)" if n >= MAX_MATCHES else ""
            print(f"  {n} matches{cap}  {elapsed:.4f}s")

        results[n_db] = {
            "MPJ":  (TIMEOUT_S, True),
            "MSJ":  (elapsed, timed_out),
            "ESPM": (TIMEOUT_S, True),
        }

    return results, n_edges, n_kw


def fmt_r(t_s, timed_out, matches=None):
    if timed_out:
        return "timeout", f">{TIMEOUT_S}s"
    cap = " (cap)" if matches is not None and matches >= MAX_MATCHES else ""
    return f"0{cap}", f"{t_s:.4f}s"


def write_db_results(topo_key, topo_label, results, n_edges, n_kw):
    out_dir = os.path.join(_here, topo_key.replace("-", "_"), "results")
    os.makedirs(out_dir, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Montevideo — {topo_label}, DB Size Sweep\n",
        f"_Run date: {now}_\n",
        f"**Region:** Montevideo, Uruguay — lat [{LAT_MIN}, {LAT_MAX}] x lon [{LON_MIN}, {LON_MAX}]  (1 deg x 1 deg)\n",
        f"**Query:** {N_QUERY} nodes, {n_edges} edges\n",
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
        msj_m  = "timeout" if msj_to else f"{MAX_MATCHES} (cap)" if msj_t and not msj_to else "0"
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
    print(f"\n  Written -> {path}")
    return path


if __name__ == "__main__":
    # Run all three topologies
    fc_res,   fc_edges,   fc_kw   = run_topology("Fully Connected",     "fc",   make_fully_connected_pattern)
    sf_res,   sf_edges,   sf_kw   = run_topology("Scale-Free (BA m=2)", "sf",   make_scale_free_pattern)
    mesh_res, mesh_edges, mesh_kw = run_topology("Mesh (Ring-Lattice)", "mesh", make_mesh_pattern)

    # Write db_size_50k.md for each topology
    write_db_results("fully_connected", "Fully-Connected Query",     fc_res,   fc_edges,   fc_kw)
    write_db_results("scale_free",      "Scale-Free Query (BA m=2)", sf_res,   sf_edges,   sf_kw)
    write_db_results("mesh",            "Mesh Query (Ring-Lattice)", mesh_res, mesh_edges, mesh_kw)

    # Regenerate full_results.md and all three figures
    print("\nGenerating consolidated results and figures...")
    import generate_full_results, make_figure
    generate_full_results.build()
    make_figure.make_figure(
        make_figure.FC_QUERY_DATA,   make_figure.FC_DB_DATA,
        os.path.join(_here, "fully_connected", "results", "db_size_50k.md"),
        "Fully-Connected Query (190 edges)", "fully_connected_figure.png",
    )
    make_figure.make_figure(
        make_figure.SF_QUERY_DATA,   make_figure.SF_DB_DATA,
        os.path.join(_here, "scale_free", "results", "db_size_50k.md"),
        "Scale-Free Query (BA m=2, 37 edges)", "scale_free_figure.png",
    )
    make_figure.make_figure(
        make_figure.MESH_QUERY_DATA, make_figure.MESH_DB_DATA,
        os.path.join(_here, "mesh", "results", "db_size_50k.md"),
        "Mesh Query (Ring-Lattice k=4, 40 edges)", "mesh_figure.png",
    )
    print("\nDone. All results in benchmark_montevideo/results/")
