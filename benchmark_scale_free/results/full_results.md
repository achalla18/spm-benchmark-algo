# Scale-Free Query Benchmark — Full Results

_Run date: 2026-06-05_

Query graph: **Barabási-Albert scale-free (m=2).**
Each new query node attaches preferentially to 2 already-present nodes,
producing a hub-and-spoke topology with far fewer edges than a fully-connected
clique.

---

## Papers under test

| Label | Paper | Algorithms |
|-------|-------|------------|
| Paper 1 | Fang et al., **ICDE 2018** — "Spatial Pattern Matching over Large-scale Geo-textual Data" | MPJ (Multi-Pair Join), MSJ (Multi-Star Join) |
| Paper 2 | Chen et al., **TKDE 2020** — "Efficient Spatial Pattern Matching over Large-Scale Geo-Textual Data" | ESPM (IL-Quadtree, n-match / e-match / join) |

---

## Fixed parameters (both sweeps)

| Parameter | Value |
|-----------|-------|
| Query topology | Barabási-Albert scale-free, m=2 |
| Distance bounds | lower=0.0 deg, upper=0.1 deg (~11.1 km) |
| Edge flags | Mutual inclusion, no exclusion |
| Max matches per algorithm | 10 |
| Per-algorithm timeout | 1,800 s (30 min) |
| DB node type | Point |
| DB edge type | Metric (Euclidean degrees) |
| DB edge distribution | Fully connected |
| Spatial bounding box | lat [51.0, 52.0] × lon [−0.5, 0.5] |
| Node placement | Uniform random, seed=42 |
| Grid cell size | 0.1 deg |

---

## Query graph edge counts vs fully-connected reference

| Query nodes | BA edges (scale-free) | Fully-connected edges | Reduction |
|-------------|----------------------|-----------------------|-----------|
| 20 | 37 | 190 | 80% fewer |
| 40 | 77 | 780 | 90% fewer |
| 60 | 117 | 1,770 | 93% fewer |

---

## Experiment 1 — Query Size Sweep

**Fixed:** DB = 1,000 nodes (50 objects/keyword)
**Varied:** Query nodes = 20, 40, 60

### Timing results

| Query nodes | BA edges | Algorithm | Paper | Matches | Time (s) |
|-------------|----------|-----------|-------|---------|----------|
| **20** | 37 | MPJ | ICDE 2018 | 0 | 0.3002 |
| **20** | 37 | MSJ | ICDE 2018 | 0 | 0.1630 |
| **20** | 37 | ESPM | TKDE 2020 | 0 | 1.6412 |
| **40** | 77 | MPJ | ICDE 2018 | 0 | 0.1283 |
| **40** | 77 | MSJ | ICDE 2018 | 0 | 0.1897 |
| **40** | 77 | ESPM | TKDE 2020 | 0 | 1.3318 |
| **60** | 117 | MPJ | ICDE 2018 | 0 | 0.5184 |
| **60** | 117 | MSJ | ICDE 2018 | 0 | 0.8569 |
| **60** | 117 | ESPM | TKDE 2020 | 0 | 1.4453 |

All algorithms complete. No timeouts.

### Scaling across query sizes

| Algorithm | Q=20 (s) | Q=40 (s) | Q=60 (s) | 20→40 | 40→60 |
|-----------|---------|---------|---------|-------|-------|
| MPJ  | 0.3002 | 0.1283 | 0.5184 | 0.43× faster | 4.04× slower |
| MSJ  | 0.1630 | 0.1897 | 0.8569 | 1.16× slower | 4.52× slower |
| ESPM | 1.6412 | 1.3318 | 1.4453 | 0.81× faster | 1.09× slower |

---

## Experiment 2 — Database Size Sweep

**Fixed:** Query = 20 nodes, BA scale-free (37 edges)
**Varied:** DB nodes = 1,000 / 10,000 / 50,000

### IL-Quadtree parameters

| DB nodes | Obj/keyword | IL-Quadtree params |
|----------|-------------|--------------------|
| 1,000 | 50 | split=1, lmin=2, lmax=5 |
| 10,000 | 500 | split=64, lmin=4, lmax=10 |
| 50,000 | 2,500 | split=64, lmin=6, lmax=12 |

### Timing results

| DB nodes | Obj/kw | Algorithm | Paper | Matches | Time (s) |
|----------|--------|-----------|-------|---------|----------|
| **1,000** | 50 | MPJ | ICDE 2018 | 0 | 0.2510 |
| **1,000** | 50 | MSJ | ICDE 2018 | 0 | 0.1473 |
| **1,000** | 50 | ESPM | TKDE 2020 | 0 | 1.9380 |
| **10,000** | 500 | MPJ | ICDE 2018 | timeout (>1800s) | >1800s |
| **10,000** | 500 | MSJ | ICDE 2018 | 10 (cap) | 10.1940 |
| **10,000** | 500 | ESPM | TKDE 2020 | timeout (>1800s) | >1800s |
| **50,000** | 2,500 | MPJ | ICDE 2018 | timeout (>1800s) | >1800s |
| **50,000** | 2,500 | MSJ | ICDE 2018 | 10 (cap) | 4,058.58 |
| **50,000** | 2,500 | ESPM | TKDE 2020 | timeout (>1800s) | >1800s |

### Scaling across DB sizes

| Algorithm | DB=1,000 (s) | DB=10,000 (s) | DB=50,000 (s) | 1K→10K | 10K→50K |
|-----------|-------------|--------------|--------------|--------|---------|
| MPJ  | 0.2510 | timeout | timeout | N/A | N/A |
| MSJ  | 0.1473 | 10.1940 | 4,058.58 | 69.2× | 398.1× |
| ESPM | 1.9380 | timeout | timeout | N/A | N/A |

Note: MSJ at DB=50,000 ran past the 30-minute ceiling (the daemon thread completed at 4,058 s ≈ 67 min before the process exited). The result is real.

---

## Comparison with fully-connected query

Same DB sizes, Q=20, but fully-connected clique (190 edges) instead of BA scale-free (37 edges).

| DB | Algorithm | Fully-connected | Scale-free | Speedup |
|----|-----------|----------------|------------|---------|
| 1,000 | MPJ | 0.72 s | 0.25 s | 2.9× |
| 1,000 | MSJ | 0.64 s | 0.15 s | 4.3× |
| 1,000 | ESPM | 5.37 s | 1.94 s | 2.8× |
| 10,000 | MPJ | timeout | timeout | — |
| 10,000 | MSJ | 58.31 s | 10.19 s | 5.7× |
| 10,000 | ESPM | timeout | timeout | — |
| 50,000 | MPJ | timeout | timeout | — |
| 50,000 | MSJ | timeout | 4,058 s (completed) | — |
| 50,000 | ESPM | timeout | timeout | — |

---

## Analysis

### Why 0 matches at DB=1,000

At 50 objects/keyword, the expected number of objects of any one keyword within
0.1° of a given point is 50 × π × 0.01 ≈ 1.6. Satisfying a 20-node query
(even a sparse one) requires 20 specific keywords to be co-located — essentially
impossible at this density with random uniform placement.

At DB=10,000 and 50,000, density is high enough that matches exist (MSJ finds 10).

### Query size sweep: why ESPM is nearly flat

ESPM's n-match phase processes each query edge once per tree level. With
BA scale-free edges growing as 37 → 77 → 117 (linear in Q), and the tree depth
fixed (lmin=2, lmax=5 for DB=1,000), total traversal work scales modestly.
MPJ and MSJ are more sensitive to the join tree structure, which depends on
both edge count and degree distribution.

### DB size sweep: why scale-free is faster than fully-connected for MSJ

The speedup comes from two places:

1. **Candidate generation**: MSJ generates e-match candidate pairs for every
   query edge before joining. 37 edges × grid lookups vs 190 edges = 80% less
   upfront work.

2. **Anchor-pruning in the join**: when assigning a new object, MSJ checks
   distances against all previously assigned objects. In a scale-free query,
   leaf nodes (degree 1–2) require only 1–2 such checks per extension step.
   In the clique, every node requires 19 checks. Fewer checks per step =
   faster join even at equal database size.

### Why MPJ still times out with a sparse query

MPJ's join defers cross-pair constraint checks until both endpoints are assigned.
With a scale-free query, leaf nodes at the fringe of the query graph are assigned
early with only their direct edge checked — all other constraints are verified
later. This means each branch survives longer before being pruned, keeping the
search tree wide at high database densities.

### Why ESPM times out at DB=10,000+

ESPM builds one IL-Quadtree per keyword and traverses pairs of trees for every
query edge at every level. With upper=0.1° covering ~10% of the 1°×1° area,
most tree-node pairs survive at every level, making the filtering ineffective.
The 37-edge scale-free query helps vs 190 edges (less total traversal work), but
500–2,500 objects/keyword still overwhelms the tree at these database sizes.

---

## Summary

| Finding | Detail |
|---------|--------|
| All algorithms complete at DB=1,000 | Scale-free query is manageable at low density |
| MSJ only algorithm to complete at DB=10,000+ | Anchor-pruning is the deciding factor |
| Scale-free 5.7× faster than fully-connected for MSJ at DB=10,000 | 80% fewer edges cuts candidate generation and join work |
| MSJ at DB=50,000 completes in ~67 min | Fully-connected MSJ does not finish in 30 min |
| MPJ and ESPM time out at DB=10,000+ regardless of query topology | Structural limitations unrelated to edge count |
| ESPM flat ~1.3–1.9 s across all query sizes at DB=1,000 | N-match traversal cost grows slowly with BA edge count |
