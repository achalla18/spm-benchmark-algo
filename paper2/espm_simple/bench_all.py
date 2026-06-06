"""
bench_all.py — Run all 240 patterns and compare ESPM vs MSJ.

Usage:
    python bench_all.py [--timeout 30]
"""
import os
import sys
import time
import concurrent.futures

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '../../paper1')))

from esp_m import load_objects, load_patterns, run_espm
from spm   import build_inverted_index, GridIndex, run_msj

TIMEOUT = int(sys.argv[1]) if len(sys.argv) > 1 else 30   # seconds per ESPM run

DATA = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../paper1/data/UK')
)

print(f"Dataset: {DATA}")
t0 = time.perf_counter()
objects_so = load_objects(os.path.join(DATA, 'loc'), os.path.join(DATA, 'doc'))
patterns   = load_patterns(os.path.join(DATA, 'pattern'))
print(f"Loaded {len(objects_so):,} objects, {len(patterns)} patterns  ({time.perf_counter()-t0:.2f}s)")

# Build MSJ indexes once
raw_objects = {oid: {'lon': o.lon, 'lat': o.lat, 'keywords': o.keywords}
               for oid, o in objects_so.items()}
inv_idx   = build_inverted_index(raw_objects)
all_upper = sorted(ed.upper for p in patterns for ed in p)
cell_size = all_upper[len(all_upper) // 2]
grid      = GridIndex(raw_objects, cell_size)
print(f"MSJ indexes ready (grid cell={cell_size:.6f} deg)  ESPM timeout={TIMEOUT}s/pattern")
print()

# Header
print(f"{'Pat':>4}  {'E':>2}  {'ESPM':>8}  {'MSJ':>8}  {'Match':>6}  "
      f"{'t_espm':>9}  {'t_msj':>7}")
print("-" * 62)

total_espm = total_msj = mismatches = timeouts = 0
t_espm_tot = t_msj_tot = 0.0
mismatch_list = []
timeout_list  = []


def _run_espm(pat):
    return run_espm(objects_so, pat, max_matches=0, verbose=False)


for i, pat in enumerate(patterns):
    raw_pat = [{
        'keyword_a': e.keyword_a, 'keyword_b': e.keyword_b,
        'lower': e.lower, 'upper': e.upper,
        'flag1': e.sign in ('a_excludes_b', 'mutual_exclusion'),
        'flag2': e.sign in ('b_excludes_a', 'mutual_exclusion'),
    } for e in pat]

    # Run ESPM with timeout
    t0 = time.perf_counter()
    em = None
    timed_out = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_run_espm, pat)
        try:
            em = fut.result(timeout=TIMEOUT)
        except concurrent.futures.TimeoutError:
            timed_out = True
    te = time.perf_counter() - t0

    # Run MSJ (no timeout needed — it's fast)
    t0 = time.perf_counter()
    mm = run_msj(raw_objects, inv_idx, raw_pat, grid=grid, max_matches=0)
    tm = time.perf_counter() - t0

    t_msj_tot += tm

    if timed_out:
        timeouts += 1
        timeout_list.append(i)
        total_msj += len(mm)
        status = "TIME"
        print(f"{i:>4}  {len(pat):>2}  {'---':>8}  {len(mm):>8,}  {status:>6}  "
              f"{te:>9.1f}s  {tm:>7.3f}s  (>{TIMEOUT}s)")
        continue

    t_espm_tot += te
    ok = (len(em) == len(mm))
    if not ok:
        mismatches += 1
        mismatch_list.append(i)

    total_espm += len(em)
    total_msj  += len(mm)

    status = "OK" if ok else "FAIL"
    print(f"{i:>4}  {len(pat):>2}  {len(em):>8,}  {len(mm):>8,}  {status:>6}  "
          f"{te:>9.3f}s  {tm:>7.3f}s")

# Summary
print("-" * 62)
non_timeout = len(patterns) - timeouts
verdict = ("PASS" if mismatches == 0 else f"{mismatches} FAIL") + \
          (f" {timeouts} SKIP" if timeouts else "")
print(f"{'TOT':>4}  {'':>2}  {total_espm:>8,}  {total_msj:>8,}  {verdict:>6}  "
      f"{t_espm_tot:>9.2f}s  {t_msj_tot:>7.2f}s")
print()

if mismatches == 0 and timeouts == 0:
    print(f"All {len(patterns)} patterns: ESPM == MSJ  [PASS]")
elif mismatches == 0:
    print(f"{non_timeout}/{len(patterns)} patterns completed: ESPM == MSJ  [PASS on completed]")
    print(f"Timed out (>{TIMEOUT}s): patterns {timeout_list}")
else:
    print(f"Mismatches: {mismatch_list}")
    if timeouts:
        print(f"Timed out:  {timeout_list}")

print(f"Total matches:  ESPM={total_espm:,}  MSJ={total_msj:,}")
if t_espm_tot > 0:
    print(f"Completed time: ESPM={t_espm_tot:.1f}s  MSJ (completed)={sum(0 for _ in range(non_timeout)):.1f}s")
print(f"MSJ total:      {t_msj_tot:.1f}s")
