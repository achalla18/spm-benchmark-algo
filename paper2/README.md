# ESPM — Efficient Spatial Pattern Matching

Python implementation of the TKDE 2020 paper:

> Chen, Y., Zhao, X., Fang, Y., & Chen, L. (2020).  
> **"Efficient Spatial Pattern Matching over Large-Scale Geo-Textual Data."**  
> *IEEE Transactions on Knowledge and Data Engineering*, Vol. 32, No. 6.

---

## What this solves

The same Spatial Pattern Matching (SPM) problem as paper1 (ICDE 2018), but faster
on very large datasets (10M+ objects).

The key idea: instead of comparing individual objects upfront, ESPM first prunes
entire *regions* of space using a hierarchical quadtree index, then only checks
actual objects in the surviving regions. On disk-based datasets where I/O is the
bottleneck, this yields 100x+ speedups over MSJ.

---

## Algorithm overview (3 steps)

### Step 1 — N-matches (node-pair filtering)

For each pattern edge `(keyword_a, keyword_b, lower, upper)`, traverse the
`keyword_a` and `keyword_b` quadtrees in parallel, level by level.  
At each level, discard node pairs whose *minimum* bounding distance exceeds
`upper` (too far apart) or *maximum* bounding distance falls below `lower`
(too close). Only surviving node pairs expand to the next level.  
S-sets track which keyword-a nodes survive across multiple edges — cross-edge
pruning that becomes powerful on dense, connected patterns.

### Step 2 — E-matches (object-pair filtering)

From the leaf nodes produced by Step 1, extract actual object IDs and verify
the exact distance constraint. Pre-compute excluded object sets for exclusion
edges. Skip-edges (cycle-closing edges on mutual-inclusion cycles) skip this
step entirely.

### Step 3 — Join

Backtracking join in connected order, identical in structure to MSJ/MPJ from
paper1. For skip-edges, only the distance constraint is checked inline; the
n/e-match filtering handled them already.

---

## Files

```
paper2/
  espm.py          Full ESPM implementation (IL-Quadtree + 3-step algorithm)
  main.py          Command-line runner; can compare ESPM vs MSJ vs MPJ
  espm_simple/
    esp_m.py       Simpler, more readable ESPM (uses dataclasses + named edge signs)
    main.py        Runner for the simple version (includes --toy and --compare)
    bench_all.py   Sweep benchmark across patterns
    README.md      Explanation of differences vs espm.py
```

The `espm_simple/` subdirectory is a cleaner, more readable variant of the same
algorithm. It trades the cross-edge S-set optimisation for readability.
Results are identical; performance is similar on the UK dataset.

---

## How to run

```bash
# Run ESPM on pattern 140 (5 edges) against the UK dataset
python main.py --pattern 140 --algo espm

# Compare ESPM vs MSJ on the same pattern
python main.py --pattern 140 --algo both

# Compare all three (ESPM, MSJ, MPJ)
python main.py --pattern 140 --algo all

# Unlimited matches for a full correctness comparison
python main.py --pattern 40 --algo both --max-matches 0

# Simpler version with toy test
python espm_simple/main.py --toy
python espm_simple/main.py --data-dir ../paper1/data/UK --pattern 0 --max-matches 20
```

The runner automatically imports MSJ/MPJ from `../paper1/spm.py`, so both
implementations share the same dataset loading code.

---

## IL-Quadtree parameters

| Parameter | Small data (<10K) | UK dataset (182K) | Large data (10M+) |
|-----------|------------------|-------------------|-------------------|
| `split_thresh` | 1 | 64 | 64–256 |
| `lmin` | 2 | 8 | 8–10 |
| `lmax` | 5 | 15 | 15–20 |

For the synthetic SPMBench benchmark (`task2/benchmark.py`), use `split=1,
lmin=2, lmax=5` because the dataset has only 1,000 objects.

---

## Performance vs paper1 (MSJ)

On the UK dataset (~182K objects, in-memory):

| Scenario | ESPM vs MSJ |
|----------|-------------|
| Patterns with large candidate sets (5–7 edges) | 4–20x **slower** |
| Patterns with small candidate sets | ~1x (index overhead dominates) |

This matches the paper's expectation: the quadtree benefit appears at scale
(disk I/O and 10M+ objects), not on an in-memory 182K-object dataset where
MSJ's star-pruning (often 96–99% reduction) is very cheap.

---

## Edge flag semantics

Same as paper1 — see `paper1/README.md` for the full table.

| flag1 | flag2 | Sign | Meaning |
|-------|-------|------|---------|
| False | False | `--` | Mutual inclusion |
| True  | False | `->` | vi excludes vj |
| False | True  | `<-` | vj excludes vi |
| True  | True  | `<>` | Mutual exclusion |
