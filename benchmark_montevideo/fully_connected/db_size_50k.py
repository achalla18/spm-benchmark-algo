"""
Fully-connected DB size sweep — Montevideo region.
Q=20 fixed (190 edges).  DB = 1,000 / 10,000 / 50,000 nodes.
"""
import os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))
from common import make_fully_connected_pattern, run_one, fmt_result, LAT_MIN, LAT_MAX, LON_MIN, LON_MAX

N_QUERY  = 20
DB_SIZES = [1_000, 10_000, 50_000]
OUT      = os.path.join(os.path.dirname(__file__), "results", "db_size_50k.md")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

pattern = make_fully_connected_pattern(N_QUERY)
all_results = {}
for n_db in DB_SIZES:
    res, meta = run_one(n_db, pattern, label=f"FC DB={n_db}")
    all_results[n_db] = (res, meta)

now   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
lines = [
    "# Montevideo — Fully-Connected Query, DB Size Sweep\n",
    f"_Run date: {now}_\n",
    f"**Region:** Montevideo, Uruguay — lat [{LAT_MIN}, {LAT_MAX}] x lon [{LON_MIN}, {LON_MAX}]  (1 deg x 1 deg)\n",
    f"**Query:** {N_QUERY} nodes, fully-connected clique, {N_QUERY*(N_QUERY-1)//2} edges\n",
    "",
    "| DB nodes | Obj/kw | MPJ matches | MPJ time | MSJ matches | MSJ time | ESPM matches | ESPM time |",
    "|----------|--------|-------------|----------|-------------|----------|--------------|-----------|",
]
for n_db, (res, meta) in all_results.items():
    mm, mt = fmt_result(res["MPJ"]); sm, st = fmt_result(res["MSJ"]); em, et = fmt_result(res["ESPM"])
    lines.append(f"| {n_db:,} | {meta['objs_kw']} | {mm} | {mt} | {sm} | {st} | {em} | {et} |")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nResults -> {OUT}")
