# SPMBench — Database Size Sweep (Extended: up to 50,000 nodes)

_Run date: 2026-06-05 23:49 UTC_

---

## Papers under test

| Label | Paper | Algorithms |
|-------|-------|------------|
| Paper 1 | Fang et al., **ICDE 2018** | MPJ (Multi-Pair Join), MSJ (Multi-Star Join) |
| Paper 2 | Chen et al., **TKDE 2020** | ESPM (IL-Quadtree, n-match / e-match / join) |

---

## Setup

| Parameter | Value |
|-----------|-------|
| Query nodes | 20 (fully connected clique, 190 edges) |
| Distance bounds | lower=0.0 deg, upper=0.1 deg (~11.1 km) |
| Edge flags | Mutual inclusion, no exclusion |
| Max matches | 10 per algorithm |
| Timeout per algorithm | 1800 s (30 min) |
| DB node type | Point |
| DB edge type | Metric (Euclidean degrees) |
| DB edge distribution | Fully connected |
| Bounding box | lat [51.0, 52.0] × lon [−0.5, 0.5] |
| Node placement | Uniform random, seed=42 |
| Keywords | 20 (one per query node) |
| Grid cell size | 0.1 deg |

| DB nodes | Obj / keyword | IL-Quadtree params |
|----------|---------------|--------------------|
| 1,000 | 50 | split=1, lmin=2, lmax=5 |
| 10,000 | 500 | split=64, lmin=4, lmax=10 |
| 50,000 | 2500 | split=64, lmin=6, lmax=12 |

---

## Timing results

| DB nodes | Obj/kw | Algorithm | Paper | Matches | Time (s) |
|----------|--------|-----------|-------|---------|----------|
| **1,000** | 50 | MPJ | ICDE 2018 | 0 | 0.7180 |
| **1,000** | 50 | MSJ | ICDE 2018 | 0 | 0.6408 |
| **1,000** | 50 | ESPM | TKDE 2020 | 0 | 5.3659 |
|  |  |  |  |  |  |
| **10,000** | 500 | MPJ | ICDE 2018 | timeout (>1800s) | >1800s |
| **10,000** | 500 | MSJ | ICDE 2018 | 10 (cap) | 58.3102 |
| **10,000** | 500 | ESPM | TKDE 2020 | timeout (>1800s) | >1800s |
|  |  |  |  |  |  |
| **50,000** | 2500 | MPJ | ICDE 2018 | timeout (>1800s) | >1800s |
| **50,000** | 2500 | MSJ | ICDE 2018 | timeout (>1800s) | >5216s |
| **50,000** | 2500 | ESPM | TKDE 2020 | timeout (>1800s) | >1920s |
|  |  |  |  |  |  |

---

## Scaling across DB sizes

| Algorithm | 1,000 (s) | 10,000 (s) | 50,000 (s) | 1K→10K | 10K→50K |
|-----------|-----------|-----------|-----------|--------|---------|
| MPJ | 0.7180 | timeout (>1800s) | timeout (>1800s) | N/A | N/A |
| MSJ | 0.6408 | 58.3102 | timeout (>1800s) | 91.0× | N/A |
| ESPM | 5.3659 | timeout (>1800s) | timeout (>1800s) | N/A | N/A |

---

## Notes

- Matches marked `(cap)` hit the max_matches=10 limit.
- timeout = algorithm ran for the full 1800s without completing.
- MPJ lacks anchor-pruning → exponential join tree at high density.
- MSJ uses anchor-pruning → scales better but still grows with density.
- ESPM n-match overhead grows with edge count (190 edges × tree levels).
