# Scale-Free Query — Query Size Sweep

_Run date: 2026-06-05 20:25 UTC_

Query graph: Barabási-Albert scale-free (m=2). DB=1,000 fixed, uniform random.

---

## Query graph edge counts

| Query nodes | BA edges (scale-free) | Fully-connected edges (reference) |
|-------------|----------------------|-----------------------------------|
| 20 | 37 | 190 |
| 40 | 77 | 780 |
| 60 | 117 | 1770 |

---

## Timing results

| Query nodes | BA edges | Algorithm | Paper | Matches | Time (s) |
|-------------|----------|-----------|-------|---------|----------|
| **20** | 37 | MPJ | ICDE 2018 | 0 | 0.3002 |
| **20** | 37 | MSJ | ICDE 2018 | 0 | 0.1630 |
| **20** | 37 | ESPM | TKDE 2020 | 0 | 1.6412 |
|  |  |  |  |  |  |
| **40** | 77 | MPJ | ICDE 2018 | 0 | 0.1283 |
| **40** | 77 | MSJ | ICDE 2018 | 0 | 0.1897 |
| **40** | 77 | ESPM | TKDE 2020 | 0 | 1.3318 |
|  |  |  |  |  |  |
| **60** | 117 | MPJ | ICDE 2018 | 0 | 0.5184 |
| **60** | 117 | MSJ | ICDE 2018 | 0 | 0.8569 |
| **60** | 117 | ESPM | TKDE 2020 | 0 | 1.4453 |
|  |  |  |  |  |  |

---

## Scaling

| Algorithm | Q=20 (s) | Q=40 (s) | Q=60 (s) | 20→40 | 40→60 |
|-----------|---------|---------|---------|-------|-------|
| MPJ | 0.3002 | 0.1283 | 0.5184 | 0.43x | 4.04x |
| MSJ | 0.1630 | 0.1897 | 0.8569 | 1.16x | 4.52x |
| ESPM | 1.6412 | 1.3318 | 1.4453 | 0.81x | 1.09x |
