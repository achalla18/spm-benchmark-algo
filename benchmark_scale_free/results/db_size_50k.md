# Scale-Free Query — Database Size Sweep (up to 50,000 nodes)

_Run date: 2026-06-05 23:33 UTC_

Query: 20 nodes, BA scale-free (m=2), 37 edges. DB varied. Timeout 1800s per algorithm.

---

## Setup

| DB nodes | Obj/keyword | IL-Quadtree params |
|----------|-------------|--------------------|
| 1,000 | 50 | split=1, lmin=2, lmax=5 |
| 10,000 | 500 | split=64, lmin=4, lmax=10 |
| 50,000 | 2500 | split=64, lmin=6, lmax=12 |

---

## Timing results

| DB nodes | Obj/kw | Algorithm | Paper | Matches | Time (s) |
|----------|--------|-----------|-------|---------|----------|
| **1,000** | 50 | MPJ | ICDE 2018 | 0 | 0.2510 |
| **1,000** | 50 | MSJ | ICDE 2018 | 0 | 0.1473 |
| **1,000** | 50 | ESPM | TKDE 2020 | 0 | 1.9380 |
|  |  |  |  |  |  |
| **10,000** | 500 | MPJ | ICDE 2018 | timeout (>1800s) | >1800s |
| **10,000** | 500 | MSJ | ICDE 2018 | 10 (cap) | 10.1940 |
| **10,000** | 500 | ESPM | TKDE 2020 | timeout (>1800s) | >1800s |
|  |  |  |  |  |  |
| **50,000** | 2500 | MPJ | ICDE 2018 | timeout (>1800s) | >1800s |
| **50,000** | 2500 | MSJ | ICDE 2018 | 10 (cap) | 4058.5805 |
| **50,000** | 2500 | ESPM | TKDE 2020 | timeout (>1800s) | >1800s |
|  |  |  |  |  |  |

---

## Scaling across DB sizes

| Algorithm | 1,000 (s) | 10,000 (s) | 50,000 (s) | 1K→10K | 10K→50K |
|-----------|-----------|------------|------------|--------|---------|
| MPJ | 0.2510 | timeout | timeout | N/A | N/A |
| MSJ | 0.1473 | 10.1940 | 4058.5805 | 69.2x | 398.1x |
| ESPM | 1.9380 | timeout | timeout | N/A | N/A |

---

## Notes

- Query: 20-node BA scale-free graph, m=2, 37 edges.
- timeout = algorithm ran for the full 1800s.
- Matches marked (cap) hit the max_matches=10 limit.
