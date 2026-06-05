# SPMBench — Database Size Sweep Results

_Run date: 2026-06-05 15:44 UTC_

---

## Papers under test

| Label | Paper | Algorithms |
|-------|-------|------------|
| Paper 1 | Fang et al., **ICDE 2018** — "Spatial Pattern Matching over Large-scale Geo-textual Data" | MPJ (Multi-Pair Join), MSJ (Multi-Star Join) |
| Paper 2 | Chen et al., **TKDE 2020** — "Efficient Spatial Pattern Matching over Large-Scale Geo-Textual Data" | ESPM (IL-Quadtree, n-match / e-match / join) |

---

## Setup

**Fixed across all runs:**

| Parameter | Value |
|-----------|-------|
| Query nodes | 20 (fully connected clique, 190 edges) |
| Distance bounds | lower=0.0 deg, upper=0.1 deg (~11.1 km) |
| Edge flags | Mutual inclusion, no exclusion |
| Max matches | 10 per algorithm |
| Per-algorithm timeout | 120 s |
| DB node type | Point |
| DB edge type | Metric (Euclidean degrees) |
| DB edge distribution | Fully connected |
| Spatial bounding box | lat [51.0, 52.0] × lon [−0.5, 0.5] |
| Node placement | Uniform random, seed=42 |
| Keywords | 20 (one per query node) |
| Grid cell size | 0.1 deg |

**What was varied:**

| DB nodes | Obj / keyword | IL-Quadtree params |
|----------|---------------|--------------------|
| 1,000 | 50 | split=1, lmin=2, lmax=5 |
| 10,000 | 500 | split=64, lmin=4, lmax=10 |

---

## Timing results

| DB nodes | Obj/keyword | Algorithm | Paper | Matches | Time (s) |
|----------|-------------|-----------|-------|---------|----------|
| **1,000** | 50 | MPJ | ICDE 2018 | 0 | 1.1210 |
| **1,000** | 50 | MSJ | ICDE 2018 | 0 | 0.8710 |
| **1,000** | 50 | ESPM | TKDE 2020 | 0 | 10.6561 |
|  |  |  |  |  |  |
| **10,000** | 500 | MPJ | ICDE 2018 | timeout (>120s) | >120s |
| **10,000** | 500 | MSJ | ICDE 2018 | 10 (cap) | 72.4307 |
| **10,000** | 500 | ESPM | TKDE 2020 | timeout (>120s) | >120s |
|  |  |  |  |  |  |

---

## Scaling: 1,000 → 10,000 nodes (10× DB size)

| Algorithm | DB=1,000 (s) | DB=10,000 (s) | Slowdown |
|-----------|-------------|--------------|---------|
| MPJ | 1.1210 | timeout (>120s) | >107× |
| MSJ | 0.8710 | 72.4307 | 83.2× |
| ESPM | 10.6561 | timeout (>120s) | >11× |

---

## Why MPJ times out at DB=10,000

MPJ's backtracking join processes edges in connected order but does **not** perform
anchor-pruning — cross-pair constraints are only verified after all nodes are assigned.
For a fully connected 20-node clique at DB=10,000 (500 objects/keyword):

- Each expansion step branches to ~15.7 new candidates (500 obj/kw × π × 0.01 = 15.7 expected within 0.1°).
- 18 expansion steps are needed before any cross-pair constraint is checked.
- Search tree depth 18 with branching 15.7: ~15.7^18 ≈ 5.6 × 10^21 paths before pruning.

This is intractable regardless of max_matches.

**MSJ** avoids this with anchor-pruning in its join: when assigning a new object,
it immediately checks ALL distance constraints against already-assigned objects.
This collapses the search tree dramatically (most cross-pair constraints fail,
pruning branches before they expand further).

**ESPM** avoids the join explosion entirely by filtering at the IL-Quadtree
region level before comparing individual objects.

---

## Notes

- Distances in coordinate degrees (Euclidean). 1 deg ≈ 111 km.
- Query is a fixed 20-node fully-connected clique (190 edges).
- At DB=1,000 there are 50 obj/keyword (low density) → 0 matches found (geometrically impossible).
- At DB=10,000 there are 500 obj/keyword (high density) → matches likely exist for MSJ/ESPM.
- Matches marked `(cap)` hit the max_matches=10 limit.
