# SPMBench Benchmark Results

_Generated 2026-06-04 22:13 UTC_

---

## Scenario

| Property | Value |
|----------|-------|
| Database nodes | 1,000 |
| Database edge type | metric (euclidean, degrees) |
| Database edge distribution | fully connected |
| Database node type | point |
| Unique keywords | 20 |
| Objects per keyword | 50 |
| Query nodes | 20 |
| Query edge distribution | fully connected (190 edges) |
| Distance lower bound | 0.0 deg |
| Distance upper bound | 0.1 deg  (~11.1 km) |
| Max matches per algorithm | 10 |
| Bounding box (lat × lon) | [51.0, 52.0] × [-0.5, 0.5] |
| Random seed | 42 |

---

## Index Build Times

| Index | Parameters | Time (s) |
|-------|------------|----------|
| Data generation | N=1000, seed=42 | 0.0015 |
| Inverted index + Grid | cell_size=0.1 deg | 0.0025 |
| IL-Quadtree (ESPM) | split=1, lmin=2, lmax=5 | 0.0085 |

---

## Algorithm Timing

| Algorithm | Paper | Matches | Time (s) |
|-----------|-------|---------|----------|
| MPJ | ICDE 2018 | 0 | 0.2959 |
| MSJ | ICDE 2018 | 0 | 0.2906 |
| ESPM | TKDE 2020 | 0 | 4.0668 |

---

## Relative Speedups

| Comparison | Faster algorithm | Speedup |
|------------|-----------------|---------|
| MPJ vs MSJ | MSJ | 1.02x |
| MPJ vs ESPM | MPJ | 13.75x |
| MSJ vs ESPM | MSJ | 13.99x |

---

## Notes

- Distances in coordinate degrees (euclidean). 1 deg latitude ≈ 111 km.
- Query is a 20-clique: all 190 pairs have an inclusion
  constraint `[0.0, 0.1]` degrees with no exclusion flags.
- Database: 1000 randomly placed point-objects, keywords assigned
  round-robin across 20 classes → 50 objects/keyword.
- ESPM IL-Quadtree tuned for small data (split=1, lmin=2, lmax=5).
  Paper default (split=64, lmin=8, lmax=15) is for datasets >100 K objects.
