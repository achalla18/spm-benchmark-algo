# SPMBench — Query Size Sweep

_Generated 2026-06-05 02:18 UTC_

Fixed parameters: 1,000-node database, metric edges, fully-connected,
point nodes, upper=0.1 deg (~11.1 km), max_matches=10.

---

## Scenario summary

| Query nodes | Query edges | Keywords | Objects/keyword |
|-------------|-------------|----------|-----------------|
| 20 | 190 | 20 | 50 |
| 40 | 780 | 40 | 25 |
| 60 | 1,770 | 60 | 16 |

---

## Timing results

| Query nodes | Query edges | Algorithm | Paper | Matches | Time (s) |
|-------------|-------------|-----------|-------|---------|----------|
| 20 | 190 | MPJ | ICDE 2018 | 0 | 0.8065 |
| 20 | 190 | MSJ | ICDE 2018 | 0 | 0.4742 |
| 20 | 190 | ESPM | TKDE 2020 | 0 | 9.5500 |
|  |  |  |  |  |  |
| 40 | 780 | MPJ | ICDE 2018 | 0 | 1.9226 |
| 40 | 780 | MSJ | ICDE 2018 | 0 | 1.7922 |
| 40 | 780 | ESPM | TKDE 2020 | 0 | 10.1648 |
|  |  |  |  |  |  |
| 60 | 1,770 | MPJ | ICDE 2018 | 0 | 0.6441 |
| 60 | 1,770 | MSJ | ICDE 2018 | 0 | 0.9549 |
| 60 | 1,770 | ESPM | TKDE 2020 | 0 | 16.0021 |
|  |  |  |  |  |  |

\* capped at max_matches

---

## Scaling comparison (time in seconds)

| Algorithm | Q=20 | Q=40 | Q=60 | 20→40 factor | 40→60 factor |
|-----------|------|------|------|--------------|--------------|
| MPJ | 0.8065 | 1.9226 | 0.6441 | 2.38x | 0.34x |
| MSJ | 0.4742 | 1.7922 | 0.9549 | 3.78x | 0.53x |
| ESPM | 9.5500 | 10.1648 | 16.0021 | 1.06x | 1.57x |

---

## Notes

- All distances in coordinate degrees (euclidean). 1 deg ≈ 111 km.
- Query is a fully-connected clique; N nodes → N(N-1)/2 edges.
- Keywords = query nodes (each query node has a unique keyword).
- IL-Quadtree: split=1, lmin=2, lmax=5 (tuned for small datasets).
