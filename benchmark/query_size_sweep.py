"""
query_size_sweep.py
===================
Runs benchmark.run_one() for query sizes 20, 40, and 60 nodes, holding
everything else constant (1000-node DB, metric, fully-connected, point).

Writes a combined comparison table to:
    task2/results/query_size_sweep.md
"""

import os
import sys
from datetime import datetime, timezone

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

from benchmark import run_one, N_DATABASE, UPPER_DIST, MAX_MATCHES, ILQ_SPLIT, ILQ_LMIN, ILQ_LMAX

QUERY_SIZES = [20, 40, 60]


def run_sweep():
    all_results = {}   # n_query -> (results, meta)

    for n_q in QUERY_SIZES:
        print()
        res, meta = run_one(n_q)
        all_results[n_q] = (res, meta)

    return all_results


def write_sweep_results(all_results):
    out_dir  = os.path.join(_here, "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "query_size_sweep.md")
    now      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# SPMBench — Query Size Sweep\n",
        f"_Generated {now}_\n",
        "Fixed parameters: 1,000-node database, metric edges, fully-connected,",
        f"point nodes, upper={UPPER_DIST} deg (~{UPPER_DIST*111:.1f} km), max_matches={MAX_MATCHES}.\n",
        "---",
        "",
        "## Scenario summary",
        "",
        "| Query nodes | Query edges | Keywords | Objects/keyword |",
        "|-------------|-------------|----------|-----------------|",
    ]

    for n_q in QUERY_SIZES:
        n_edges = n_q * (n_q - 1) // 2
        n_kw    = n_q
        objs_kw = N_DATABASE // n_kw
        lines.append(f"| {n_q} | {n_edges:,} | {n_kw} | {objs_kw} |")

    lines += [
        "",
        "---",
        "",
        "## Timing results",
        "",
        "| Query nodes | Query edges | Algorithm | Paper | Matches | Time (s) |",
        "|-------------|-------------|-----------|-------|---------|----------|",
    ]

    for n_q in QUERY_SIZES:
        n_edges = n_q * (n_q - 1) // 2
        res, _  = all_results[n_q]
        for algo, r in res.items():
            m = str(r["matches"]) + ("*" if r["matches"] >= MAX_MATCHES else "")
            lines.append(f"| {n_q} | {n_edges:,} | {algo} | {r['paper']} | {m} | {r['time_s']:.4f} |")
        lines.append("|  |  |  |  |  |  |")   # visual separator

    lines += [
        "",
        "\\* capped at max_matches",
        "",
        "---",
        "",
        "## Scaling comparison (time in seconds)",
        "",
        "| Algorithm | Q=20 | Q=40 | Q=60 | 20→40 factor | 40→60 factor |",
        "|-----------|------|------|------|--------------|--------------|",
    ]

    for algo in ["MPJ", "MSJ", "ESPM"]:
        times = []
        for n_q in QUERY_SIZES:
            res, _ = all_results[n_q]
            times.append(res[algo]["time_s"])
        t20, t40, t60 = times
        f2040 = f"{t40/t20:.2f}x" if t20 > 0 else "—"
        f4060 = f"{t60/t40:.2f}x" if t40 > 0 else "—"
        lines.append(
            f"| {algo} | {t20:.4f} | {t40:.4f} | {t60:.4f} | {f2040} | {f4060} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Notes",
        "",
        f"- All distances in coordinate degrees (euclidean). 1 deg ≈ 111 km.",
        f"- Query is a fully-connected clique; N nodes → N(N-1)/2 edges.",
        f"- Keywords = query nodes (each query node has a unique keyword).",
        f"- IL-Quadtree: split={ILQ_SPLIT}, lmin={ILQ_LMIN}, lmax={ILQ_LMAX} (tuned for small datasets).",
        "",
    ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return out_path


if __name__ == "__main__":
    all_results = run_sweep()
    out = write_sweep_results(all_results)

    print("\n" + "=" * 68)
    print(f"{'Q':>4}  {'Algorithm':<10} {'Edges':>7} {'Matches':>8} {'Time (s)':>10}")
    print("-" * 44)
    for n_q in QUERY_SIZES:
        n_edges = n_q * (n_q - 1) // 2
        res, _  = all_results[n_q]
        for algo, r in res.items():
            print(f"{n_q:>4}  {algo:<10} {n_edges:>7,} {r['matches']:>8,} {r['time_s']:>10.4f}")
        print()
    print("=" * 68)
    print(f"\nSweep results -> {out}")
