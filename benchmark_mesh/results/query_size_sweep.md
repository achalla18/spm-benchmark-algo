# Mesh Query — Query Size Sweep

_Run date: 2026-06-06 01:00 UTC_

Query graph: ring-lattice (degree k=4). DB=1,000 fixed, uniform random.

---

## Query graph edge counts

| Query nodes | Mesh edges (k=4) | Scale-free edges (ref) | Fully-connected (ref) |
|-------------|-----------------|------------------------|----------------------|
| 20 | 40 | 37 | 190 |
| 40 | 80 | 77 | 780 |
| 60 | 120 | 117 | 1770 |

---

## Timing results

| Query nodes | Mesh edges | Algorithm | Paper | Matches | Time (s) |
|-------------|------------|-----------|-------|---------|----------|
| **20** | 40 | MPJ | ICDE 2018 | 0 | 0.1770 |
| **20** | 40 | MSJ | ICDE 2018 | 0 | 0.0654 |
| **20** | 40 | ESPM | TKDE 2020 | 0 | 0.6008 |
|  |  |  |  |  |  |
| **40** | 80 | MPJ | ICDE 2018 | 0 | 0.0747 |
| **40** | 80 | MSJ | ICDE 2018 | 0 | 0.0965 |
| **40** | 80 | ESPM | TKDE 2020 | 0 | 0.3653 |
|  |  |  |  |  |  |
| **60** | 120 | MPJ | ICDE 2018 | 0 | 0.1206 |
| **60** | 120 | MSJ | ICDE 2018 | 0 | 0.1973 |
| **60** | 120 | ESPM | TKDE 2020 | 0 | 0.3957 |
|  |  |  |  |  |  |

---

## Scaling

| Algorithm | Q=20 (s) | Q=40 (s) | Q=60 (s) | 20→40 | 40→60 |
|-----------|---------|---------|---------|-------|-------|
| MPJ | 0.1770 | 0.0747 | 0.1206 | 0.42x | 1.61x |
| MSJ | 0.0654 | 0.0965 | 0.1973 | 1.48x | 2.04x |
| ESPM | 0.6008 | 0.3653 | 0.3957 | 0.61x | 1.08x |
