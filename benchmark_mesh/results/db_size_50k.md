# Mesh Query — Database Size Sweep (up to 50,000 nodes)

_Run date: 2026-06-06_

Query: 20 nodes, ring-lattice k=4, 40 edges. DB varied. Timeout 1800s per algorithm.

---

## Setup

| DB nodes | Obj/keyword | IL-Quadtree params |
|----------|-------------|--------------------|
| 1,000 | 50 | split=1, lmin=2, lmax=5 |
| 10,000 | 500 | split=64, lmin=4, lmax=10 |
| 50,000 | 2,500 | split=64, lmin=6, lmax=12 |

---

## Timing results

| DB nodes | Obj/kw | Algorithm | Paper | Matches | Time (s) |
|----------|--------|-----------|-------|---------|----------|
| **1,000** | 50 | MPJ | ICDE 2018 | 0 | 0.1920 |
| **1,000** | 50 | MSJ | ICDE 2018 | 0 | 0.0661 |
| **1,000** | 50 | ESPM | TKDE 2020 | 0 | 0.6215 |
|  |  |  |  |  |  |
| **10,000** | 500 | MPJ | ICDE 2018 | timeout (>1800s) | >1800s |
| **10,000** | 500 | MSJ | ICDE 2018 | 10 (cap) | 32.3728 |
| **10,000** | 500 | ESPM | TKDE 2020 | timeout (>1800s) | >1800s |
|  |  |  |  |  |  |
| **50,000** | 2,500 | MPJ | ICDE 2018 | timeout (>1800s) | >1800s |
| **50,000** | 2,500 | MSJ | ICDE 2018 | 10 (cap) | 199.5623 |
| **50,000** | 2,500 | ESPM | TKDE 2020 | timeout (>1800s) | >1800s |
|  |  |  |  |  |  |

---

## Scaling across DB sizes

| Algorithm | 1,000 (s) | 10,000 (s) | 50,000 (s) | 1K→10K | 10K→50K |
|-----------|-----------|------------|------------|--------|---------|
| MPJ | 0.1920 | timeout | timeout | N/A | N/A |
| MSJ | 0.0661 | 32.3728 | 199.5623 | 489.8× | 6.2× |
| ESPM | 0.6215 | timeout | timeout | N/A | N/A |

---

## Notes

- Query: 20-node ring-lattice, k=4, 40 edges.
- timeout = algorithm ran for the full 1800s.
- Matches marked (cap) hit the max_matches=10 limit.
- DB=50,000 MSJ timed out in the original sweep run; re-run with 300s timeout completed in 199.6s.
