"""
Mesh query size sweep — Montevideo region.
DB=1,000 fixed.  Q = 20 / 40 / 60 nodes.
"""
import os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))
from common import make_mesh_pattern, run_one, fmt_result, LAT_MIN, LAT_MAX, LON_MIN, LON_MAX

N_DB    = 1_000
Q_SIZES = [20, 40, 60]
OUT     = os.path.join(os.path.dirname(__file__), "results", "query_size_sweep.md")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

all_results = {}
for q in Q_SIZES:
    pat = make_mesh_pattern(q)
    res, meta = run_one(N_DB, pat, label=f"Mesh Q={q}")
    all_results[q] = (res, meta)

now   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
lines = [
    "# Montevideo — Mesh Query Size Sweep\n",
    f"_Run date: {now}_\n",
    f"**Region:** Montevideo, Uruguay — lat [{LAT_MIN}, {LAT_MAX}] x lon [{LON_MIN}, {LON_MAX}]  (1 deg x 1 deg)\n",
    "",
    "| Q | Mesh edges | MPJ matches | MPJ time | MSJ matches | MSJ time | ESPM matches | ESPM time |",
    "|---|------------|-------------|----------|-------------|----------|--------------|-----------|",
]
for q, (res, meta) in all_results.items():
    mm, mt = fmt_result(res["MPJ"]); sm, st = fmt_result(res["MSJ"]); em, et = fmt_result(res["ESPM"])
    lines.append(f"| {q} | {meta['n_edges']} | {mm} | {mt} | {sm} | {st} | {em} | {et} |")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nResults -> {OUT}")
