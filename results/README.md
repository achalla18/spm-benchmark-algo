# SPMBench Results

Timing benchmarks for MPJ, MSJ (ICDE 2018) and ESPM (TKDE 2020) across
three query graph topologies and three database sizes.

---

## Files

| File | Contents |
|------|----------|
| `fully_connected_results.md` | Fully-connected clique query (Q=20: 190 edges) |
| `scale_free_results.md` | Barabási-Albert scale-free query (Q=20: 37 edges) |
| `mesh_results.md` | Ring-lattice mesh query, degree k=4 (Q=20: 40 edges) |
| `results_figure.png` | Two-panel timing figure (query size sweep + DB size sweep) |

---

## Quick comparison — MSJ timing (only algorithm that completes at large DB)

| DB nodes | Fully-connected | Scale-free | Mesh |
|----------|----------------|------------|------|
| 1,000 | 0.64 s | 0.15 s | **0.07 s** |
| 10,000 | 58.3 s | 10.2 s | **32.4 s** |
| 50,000 | timeout (>30 min) | 4,058 s | **199.6 s** |

MPJ and ESPM time out at DB ≥ 10,000 across all three topologies.

---

## Experiment parameters

- Query nodes: 20 (for DB sweep); 20 / 40 / 60 (for query size sweep)
- DB nodes: 1,000 / 10,000 / 50,000
- Distance bounds: lower=0.0 deg, upper=0.1 deg (~11 km)
- Timeout: 30 minutes per algorithm
- Node placement: uniform random, 1°×1° bounding box, seed=42
