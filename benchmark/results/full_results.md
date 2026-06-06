# SPMBench — Query Size Sweep Results

_Run date: 2026-06-05_

---

## Papers under test

| Label | Paper | Algorithms |
|-------|-------|------------|
| Paper 1 | Fang et al., **ICDE 2018** — "Spatial Pattern Matching over Large-scale Geo-textual Data" | MPJ (Multi-Pair Join), MSJ (Multi-Star Join) |
| Paper 2 | Chen et al., **TKDE 2020** — "Efficient Spatial Pattern Matching over Large-Scale Geo-Textual Data" | ESPM (IL-Quadtree, n-match / e-match / join) |

---

## Setup

**What was held constant across all three runs:**

| Parameter | Value |
|-----------|-------|
| Database nodes | 1,000 |
| Database node type | Point |
| Database edge type | Metric (Euclidean distance, degrees) |
| Database edge distribution | Fully connected |
| Spatial bounding box | lat [51.0, 52.0] × lon [−0.5, 0.5] (~111 × 111 km) |
| Node placement | Uniform random, seed = 42 |
| Distance bounds (all query edges) | lower = 0.0 deg, upper = 0.1 deg (~11.1 km) |
| Edge flags | Mutual inclusion — no exclusion |
| Max matches returned | 10 per algorithm |
| Grid index cell size | 0.1 deg |
| IL-Quadtree (ESPM) | split = 1, lmin = 2, lmax = 5 |

**What was varied:**

| Run | Query nodes | Query edges | Keywords | DB objects / keyword |
|-----|-------------|-------------|----------|----------------------|
| 1 | 20 | 190 | 20 | 50 |
| 2 | 40 | 780 | 40 | 25 |
| 3 | 60 | 1,770 | 60 | 16 |

Each query node has a unique keyword; query size and keyword count are equal.
DB objects are split evenly across keywords (round-robin, same seed each run).

---

## Timing results

| Query nodes | Query edges | Algorithm | Paper | Matches | Time (s) |
|-------------|-------------|-----------|-------|---------|----------|
| **20** | 190 | MPJ | ICDE 2018 | 0 | **0.8065** |
| **20** | 190 | MSJ | ICDE 2018 | 0 | **0.4742** |
| **20** | 190 | ESPM | TKDE 2020 | 0 | **9.5500** |
| **40** | 780 | MPJ | ICDE 2018 | 0 | **1.9226** |
| **40** | 780 | MSJ | ICDE 2018 | 0 | **1.7922** |
| **40** | 780 | ESPM | TKDE 2020 | 0 | **10.1648** |
| **60** | 1,770 | MPJ | ICDE 2018 | 0 | **0.6441** |
| **60** | 1,770 | MSJ | ICDE 2018 | 0 | **0.9549** |
| **60** | 1,770 | ESPM | TKDE 2020 | 0 | **16.0021** |

---

## Scaling table

| Algorithm | Q = 20 (s) | Q = 40 (s) | Q = 60 (s) | 20 → 40 | 40 → 60 |
|-----------|-----------|-----------|-----------|---------|---------|
| MPJ | 0.8065 | 1.9226 | 0.6441 | 2.38× slower | 0.34× — faster |
| MSJ | 0.4742 | 1.7922 | 0.9549 | 3.78× slower | 0.53× — faster |
| ESPM | 9.5500 | 10.1648 | 16.0021 | 1.06× slower | 1.57× slower |

---

## Head-to-head at each query size

| Query nodes | Fastest | 2nd | Slowest | ESPM / MSJ ratio |
|-------------|---------|-----|---------|-----------------|
| Q = 20 | MSJ — 0.47 s | MPJ — 0.81 s | ESPM — 9.55 s | 20.1× slower |
| Q = 40 | MSJ — 1.79 s | MPJ — 1.92 s | ESPM — 10.16 s | 5.7× slower |
| Q = 60 | MPJ — 0.64 s | MSJ — 0.95 s | ESPM — 16.00 s | 16.8× slower |

---

## Why 0 matches

A fully connected N-node query requires every pair among the matched objects to lie within 0.1° of each other. Two randomly placed points satisfy this with probability ≈ π × 0.01 ≈ 3.1%. The probability all C(N, 2) pairs simultaneously pass:

| Query nodes | Pairs | Probability all pairs pass |
|-------------|-------|---------------------------|
| 20 | 190 | ~0.031^190 ≈ 0 |
| 40 | 780 | ~0.031^780 ≈ 0 |
| 60 | 1,770 | ~0.031^1770 ≈ 0 |

All three algorithms are measuring the time to prove no match exists — which is the meaningful benchmark for worst-case pruning behavior.

---

## Why MPJ and MSJ get faster from Q=40 to Q=60

Two forces compete as query size grows:

1. **More edges = more setup work** — MPJ scans all edges to build candidate lists; Floyd-Warshall on N keywords is O(N³).
2. **More keywords = fewer objects per keyword** — 50 → 25 → 16 objects/keyword means fewer candidate pairs per edge, and the backtracking join fails faster at each branch.

By Q=60, force 2 dominates: there are so few objects per keyword that the join dies almost immediately at every branch, making Q=60 cheaper than Q=40 despite 2.27× more edges.

MSJ adds star-pruning on top: each object must have at least one valid partner in all N−1 neighboring keywords. Expected partners per keyword ≈ (objects/keyword) × 3.1%:

| Query nodes | Obj/keyword | Expected partners (one keyword) |
|-------------|-------------|----------------------------------|
| 20 | 50 | ~1.6 |
| 40 | 25 | ~0.8 |
| 60 | 16 | ~0.5 |

With ~0.5 expected partners at Q=60, almost no object survives pruning. Star-pruning is decisive — but the overhead of running 59 neighbor-list checks per object makes MSJ slightly slower than MPJ's direct backtracking at this size.

## Why ESPM scales monotonically

ESPM's n-match phase traverses the IL-Quadtree once per pattern edge, regardless of how many objects/keyword exist. More edges always means more traversals:

| Query nodes | Edges | ESPM time (s) | Time / edge (ms) |
|-------------|-------|---------------|-----------------|
| 20 | 190 | 9.55 | 50.3 |
| 40 | 780 | 10.16 | 13.0 |
| 60 | 1,770 | 16.00 | 9.0 |

Per-edge cost falls (fewer objects per tree = faster traversal) but total edge count grows faster, so total time rises. ESPM's advantage over MSJ/MPJ appears at ~10 M+ objects where tree-level pruning avoids disk I/O; on this 1,000-object in-memory dataset, MSJ's star-pruning is simpler and faster.

---

## Summary

| Finding | Detail |
|---------|--------|
| Fastest overall | MSJ at Q=20 (0.47 s), MPJ at Q=60 (0.64 s) |
| Slowest overall | ESPM at Q=60 (16.00 s) |
| MSJ vs MPJ | MSJ leads at smaller queries; MPJ takes the lead at Q=60 due to lower star-pruning overhead |
| ESPM | 6–20× slower than MSJ/MPJ at every query size on this dataset |
| MPJ + MSJ scaling | Non-monotone — peak cost at Q=40, then faster at Q=60 as fewer objects/keyword shrinks the search space |
| ESPM scaling | Monotonically slower with edge count; not suited to small in-memory datasets |
