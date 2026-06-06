"""
query_size_sweep.py  (scale-free query)
========================================
DB=1,000 fixed.  Query size varied: 20, 40, 60 nodes.
Query graph: Barabási-Albert scale-free (m=2).

Results -> benchmark_scale_free/results/query_size_sweep.md
"""

import os, sys
from datetime import datetime, timezone

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
from common import run_one, make_scale_free_pattern, TIMEOUT_S, MAX_MATCHES

N_DATABASE  = 1_000
QUERY_SIZES = [20, 40, 60]


def write_results(all_results):
    out_dir  = os.path.join(_here, "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "query_size_sweep.md")
    now      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _fmt(r):
        if r["timed_out"]:
            return f"timeout (>{TIMEOUT_S}s)", f">{r['time_s']:.0f}s"
        cap = " (cap)" if r["matches"] >= MAX_MATCHES else ""
        return f"{r['matches']}{cap}", f"{r['time_s']:.4f}"

    lines = [
        "# Scale-Free Query — Query Size Sweep\n",
        f"_Run date: {now}_\n",
        "Query graph: Barabási-Albert scale-free (m=2). "
        "DB=1,000 fixed, uniform random.\n",
        "---",
        "",
        "## Query graph edge counts",
        "",
        "| Query nodes | BA edges (scale-free) | Fully-connected edges (reference) |",
        "|-------------|----------------------|-----------------------------------|",
    ]
    for n_q in QUERY_SIZES:
        p = make_scale_free_pattern(n_q)
        fc = n_q * (n_q - 1) // 2
        lines.append(f"| {n_q} | {len(p)} | {fc} |")

    lines += [
        "",
        "---",
        "",
        "## Timing results",
        "",
        "| Query nodes | BA edges | Algorithm | Paper | Matches | Time (s) |",
        "|-------------|----------|-----------|-------|---------|----------|",
    ]

    for n_q in QUERY_SIZES:
        res, meta = all_results[n_q]
        for algo, r in res.items():
            m_str, t_str = _fmt(r)
            lines.append(
                f"| **{n_q}** | {meta['n_edges']} | {algo} "
                f"| {r['paper']} | {m_str} | {t_str} |"
            )
        lines.append("|  |  |  |  |  |  |")

    lines += ["", "---", "", "## Scaling", "",
              "| Algorithm | Q=20 (s) | Q=40 (s) | Q=60 (s) | 20→40 | 40→60 |",
              "|-----------|---------|---------|---------|-------|-------|"]

    for algo in ["MPJ", "MSJ", "ESPM"]:
        row = [algo]
        times = [(all_results[q][0][algo]["time_s"],
                  all_results[q][0][algo]["timed_out"]) for q in QUERY_SIZES]
        for t, to in times:
            row.append(f"timeout" if to else f"{t:.4f}")
        def f(i, j):
            t1, to1 = times[i]; t2, to2 = times[j]
            return "N/A" if (to1 or to2) else f"{t2/t1:.2f}x"
        row += [f(0,1), f(1,2)]
        lines.append("| " + " | ".join(row) + " |")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path


if __name__ == "__main__":
    all_results = {}
    for n_q in QUERY_SIZES:
        res, meta = run_one(N_DATABASE, n_q)
        all_results[n_q] = (res, meta)

    out = write_results(all_results)

    print(f"\n{'='*68}")
    print(f"{'Q':>4}  {'edges':>6}  {'Algorithm':<8} {'Matches':>9}  {'Time':>12}")
    print("-" * 48)
    for n_q in QUERY_SIZES:
        res, meta = all_results[n_q]
        for algo, r in res.items():
            m = "timeout" if r["timed_out"] else str(r["matches"])
            t = f">{TIMEOUT_S}s" if r["timed_out"] else f"{r['time_s']:.4f}s"
            print(f"{n_q:>4}  {meta['n_edges']:>6}  {algo:<8} {m:>9}  {t:>12}")
        print()
    print(f"{'='*68}")
    print(f"\nResults -> {out}")
