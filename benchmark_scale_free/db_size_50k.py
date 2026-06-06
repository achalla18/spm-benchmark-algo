"""
db_size_50k.py  (scale-free query)
====================================
Q=20 fixed (BA scale-free query, m=2).
DB size varied: 1,000 / 10,000 / 50,000 nodes.

Results -> benchmark_scale_free/results/db_size_50k.md
"""

import os, sys
from datetime import datetime, timezone

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
from common import run_one, make_scale_free_pattern, TIMEOUT_S, MAX_MATCHES, ILQ_PARAMS

N_QUERY  = 20
DB_SIZES = [1_000, 10_000, 50_000]


def write_results(all_results):
    out_dir  = os.path.join(_here, "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "db_size_50k.md")
    now      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pattern = make_scale_free_pattern(N_QUERY)
    n_edges = len(pattern)

    def _fmt(r):
        if r["timed_out"]:
            return f"timeout (>{TIMEOUT_S}s)", f">{r['time_s']:.0f}s"
        cap = " (cap)" if r["matches"] >= MAX_MATCHES else ""
        return f"{r['matches']}{cap}", f"{r['time_s']:.4f}"

    lines = [
        "# Scale-Free Query — Database Size Sweep (up to 50,000 nodes)\n",
        f"_Run date: {now}_\n",
        f"Query: {N_QUERY} nodes, BA scale-free (m=2), {n_edges} edges. "
        f"DB varied. Timeout {TIMEOUT_S}s per algorithm.\n",
        "---",
        "",
        "## Setup",
        "",
        "| DB nodes | Obj/keyword | IL-Quadtree params |",
        "|----------|-------------|--------------------|",
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
        "|-----------|-----------|------------|------------|--------|---------|",
    ]
    for algo in ["MPJ", "MSJ", "ESPM"]:
        times = [(all_results[n][0][algo]["time_s"],
                  all_results[n][0][algo]["timed_out"]) for n in DB_SIZES]
        def _cell(t, to): return f"timeout" if to else f"{t:.4f}"
        def _factor(i, j):
            t1, to1 = times[i]; t2, to2 = times[j]
            return "N/A" if (to1 or to2) else f"{t2/t1:.1f}x"
        t1,to1 = times[0]; t2,to2 = times[1]; t3,to3 = times[2]
        lines.append(
            f"| {algo} | {_cell(t1,to1)} | {_cell(t2,to2)} | {_cell(t3,to3)} "
            f"| {_factor(0,1)} | {_factor(1,2)} |"
        )

    lines += ["", "---", "", "## Notes", "",
              f"- Query: {N_QUERY}-node BA scale-free graph, m=2, {n_edges} edges.",
              f"- timeout = algorithm ran for the full {TIMEOUT_S}s.",
              f"- Matches marked (cap) hit the max_matches={MAX_MATCHES} limit.", ""]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path


if __name__ == "__main__":
    all_results = {}
    for n_db in DB_SIZES:
        res, meta = run_one(n_db, N_QUERY)
        all_results[n_db] = (res, meta)

    out = write_results(all_results)

    print(f"\n{'='*68}")
    print(f"{'DB':>8}  {'Algorithm':<8} {'Matches':>9}  {'Time':>12}")
    print("-" * 44)
    for n_db in DB_SIZES:
        res, _ = all_results[n_db]
        for algo, r in res.items():
            m = "timeout" if r["timed_out"] else str(r["matches"])
            t = f">{TIMEOUT_S}s" if r["timed_out"] else f"{r['time_s']:.4f}s"
            print(f"{n_db:>8,}  {algo:<8} {m:>9}  {t:>12}")
        print()
    print(f"{'='*68}")
    print(f"\nResults -> {out}")
