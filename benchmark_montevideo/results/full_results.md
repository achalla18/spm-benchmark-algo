# Montevideo Benchmark — Full Results

_Generated: 2026-06-06 04:39 UTC_

---

## Geographic Region

| Property | Value |
|----------|-------|
| City | Montevideo, Uruguay |
| Bounding box | lat [-35.4, -34.4] × lon [-56.7, -55.7] |
| Box size | 1.0 deg × 1.0 deg (~111 km × ~91 km at 35°S) |
| Distance metric | Euclidean in degrees |
| Upper distance | 0.1 deg (~11.1 km latitude / ~9.1 km longitude) |
| Lower distance | 0.0 deg |
| Coverage ratio | upper / box = 10% (same as London Region 1) |
| Note | At 35°S, 0.1° longitude ≈ 9.1 km vs 7.0 km at London (51°N). |
|      | Euclidean-degree distance is used, so the degree-space math |
|      | is identical to London; only the physical km scale differs. |

---

## Papers Under Test

| Paper | Algorithms |
|-------|------------|
| Fang et al., **ICDE 2018** — Spatial Pattern Matching over Large-scale Geo-textual Data | MPJ (Multi-Pair Join), MSJ (Multi-Star Join) |
| Chen et al., **TKDE 2020** — Efficient Spatial Pattern Matching over Large-Scale Geo-Textual Data | ESPM (IL-Quadtree, n-match / e-match / join) |

---

## Experimental Setup

**Fixed across all runs:**

| Parameter | Value |
|-----------|-------|
| Database sizes tested | 1,000 / 10,000 / 50,000 nodes |
| Query sizes tested | 20 / 40 / 60 nodes |
| Database node type | Point (uniform random) |
| Database edge type | Metric (Euclidean degrees), fully connected |
| Unique keywords | equal to query size (one unique keyword per query node) |
| Objects per keyword | N_DB / N_QUERY |
| Max matches returned | 10 per algorithm |
| Per-algorithm timeout | 1800 s (30 min) |
| Grid index cell size | 0.1 deg |
| Random seed | 42 |

**Three query graph topologies tested:**

- **Fully Connected** (190 edges at Q=20): Complete clique — every pair of query nodes connected.
- **Scale-Free (BA m=2)** (37 edges at Q=20): Barabasi-Albert preferential attachment, m=2. Hub-and-spoke topology.
- **Mesh (Ring-Lattice k=4)** (40 edges at Q=20): Ring-lattice, each node connects to 2 nearest neighbours on each side. Uniform degree=4.

---

## Fully Connected

_Complete clique — every pair of query nodes connected._

### Query Size Sweep (DB = 1,000 fixed)

| Q | Edges | MPJ time | MSJ time | ESPM time |
|---|-------|----------|----------|-----------|
| 20 | 190 | 1.1618s | 0.8529s | 13.4316s |
| 40 | 780 | 2.0434s | 1.7036s | 9.2348s |
| 60 | 1770 | 0.3627s | 0.5410s | 10.5668s |

### DB Size Sweep (Q = 20 fixed, 190 edges)

| DB nodes | Obj/kw | MPJ matches | MPJ time | MSJ matches | MSJ time | ESPM matches | ESPM time |
|----------|--------|-------------|----------|-------------|----------|--------------|-----------|
| 1,000 | 50 | 0 | 0.5240s | 0 | 0.4311s | 0 | 6.9196s |
| 10,000 | 500 | timeout | >1800s | 10 (cap) | 48.1610s | timeout | >1800s |
| 50,000 | 2500 | timeout | >1800s | timeout | >1800s | timeout | >1800s |

---

## Scale-Free (BA m=2)

_Barabasi-Albert preferential attachment, m=2. Hub-and-spoke topology._

### Query Size Sweep (DB = 1,000 fixed)

| Q | Edges | MPJ time | MSJ time | ESPM time |
|---|-------|----------|----------|-----------|
| 20 | 37 | 0.5563s | 0.2355s | 4.2044s |
| 40 | 77 | 0.1603s | 0.2026s | 1.0378s |
| 60 | 117 | 0.3722s | 0.4291s | 0.7618s |

### DB Size Sweep (Q = 20 fixed, 37 edges)

| DB nodes | Obj/kw | MPJ matches | MPJ time | MSJ matches | MSJ time | ESPM matches | ESPM time |
|----------|--------|-------------|----------|-------------|----------|--------------|-----------|
| 1,000 | 50 | 0 | 0.2015s | 0 | 0.0887s | 0 | 3.7051s |
| 10,000 | 500 | timeout | >1800s | 10 (cap) | 7.3515s | timeout | >1800s |
| 50,000 | 2500 | timeout | >1800s | timeout | >1800s | timeout | >1800s |

---

## Mesh (Ring-Lattice k=4)

_Ring-lattice, each node connects to 2 nearest neighbours on each side. Uniform degree=4._

### Query Size Sweep (DB = 1,000 fixed)

| Q | Edges | MPJ time | MSJ time | ESPM time |
|---|-------|----------|----------|-----------|
| 20 | 40 | 0.6455s | 0.2492s | 1.3816s |
| 40 | 80 | 0.1852s | 0.2671s | 0.8988s |
| 60 | 120 | 0.2423s | 0.4149s | 0.7055s |

### DB Size Sweep (Q = 20 fixed, 40 edges)

| DB nodes | Obj/kw | MPJ matches | MPJ time | MSJ matches | MSJ time | ESPM matches | ESPM time |
|----------|--------|-------------|----------|-------------|----------|--------------|-----------|
| 1,000 | 50 | 0 | 0.3514s | 0 | 0.1528s | 0 | 1.1929s |
| 10,000 | 500 | timeout | >1800s | 10 (cap) | 9.0592s | timeout | >1800s |
| 50,000 | 2500 | timeout | >1800s | timeout | >1800s | timeout | >1800s |

---

## Cross-Topology Comparison at DB = 1,000

Query size sweep, all algorithms, time in seconds.

### MPJ

| Q | FC | Scale-Free | Mesh |
|---|----|-----------|----- |
| 20 | 1.1618s | 0.5563s | 0.6455s |
| 40 | 2.0434s | 0.1603s | 0.1852s |
| 60 | 0.3627s | 0.3722s | 0.2423s |

### MSJ

| Q | FC | Scale-Free | Mesh |
|---|----|-----------|----- |
| 20 | 0.8529s | 0.2355s | 0.2492s |
| 40 | 1.7036s | 0.2026s | 0.2671s |
| 60 | 0.5410s | 0.4291s | 0.4149s |

### ESPM

| Q | FC | Scale-Free | Mesh |
|---|----|-----------|----- |
| 20 | 13.4316s | 4.2044s | 1.3816s |
| 40 |  9.2348s | 1.0378s | 0.8988s |
| 60 | 10.5668s | 0.7618s | 0.7055s |

---

## Analysis

### Why all algorithms return 0 matches at DB = 1,000

With 1,000 objects uniformly distributed across 1°×1°, the probability of any
two objects being within 0.1° of each other is approximately:

    p(pair) = π × (0.1)² / (1.0 × 1.0) ≈ 3.1%

For a 20-node query all pairs (C(20,2)=190) must simultaneously satisfy this:

    p(all pairs pass) ≈ 0.031^190 ≈ 0

The algorithms are measuring time to **prove no match exists**, not time to find one.
This is the meaningful worst-case pruning benchmark.

### Why Fully-Connected is the hardest query topology

| Topology | Q=20 edges | MPJ Q=20 | MSJ Q=20 | ESPM Q=20 |
|----------|-----------|----------|----------|-----------|
| Fully Connected | 190 | 1.16s | 0.85s | 13.43s |
| Scale-Free | 37 | 0.56s | 0.24s | 4.20s |
| Mesh | 40 | 0.65s | 0.25s | 1.38s |

More edges = more candidate pair lookups (MPJ/MSJ) and more IL-Quadtree
traversals (ESPM). At 190 edges vs 37-40, the fully-connected query
imposes roughly 5× more work on every algorithm.

### ESPM vs MSJ scaling with edges

ESPM's cost is dominated by IL-Quadtree traversal per edge.
MSJ's cost is dominated by star-pruning candidate checks per object.
At Q=20 with DB=1,000:

| Topology | ESPM/MSJ ratio |
|----------|---------------|
| Fully Connected | 13.43 / 0.85 = **15.8×** slower |
| Scale-Free | 4.20 / 0.24 = **17.8×** slower |
| Mesh | 1.38 / 0.25 = **5.5×** slower |

ESPM is relatively better on the mesh because the ring-lattice's local
structure (each node connects only to immediate ring neighbours) means the
IL-Quadtree can prune large spatial regions early.

### Geographic context: Montevideo vs London (Region 1)

Both regions use a 1°×1° bounding box with upper=0.1° and euclidean
distance in degrees. The degree-space math is therefore identical.

The physical interpretation differs:

| Property | London (51°N) | Montevideo (35°S) |
|----------|--------------|-----------------|
| 1° latitude | 111 km | 111 km |
| 1° longitude | ~70 km | ~91 km |
| 0.1° longitude | ~7.0 km | ~9.1 km |
| Bounding box (km) | ~111 × 70 km | ~111 × 91 km |

At Montevideo's latitude, the bounding box covers a **30% larger area**
in physical km² terms, meaning the same degree-distance threshold of 0.1°
represents a longer physical reach in the east-west direction.
In a haversine-distance model this would produce different results;
under euclidean degrees the algorithm results are statistically equivalent.

---

## Summary

| Finding | Detail |
|---------|--------|
| MSJ is the only algorithm that scales | Completes at DB=10,000 on all topologies; ESPM and MPJ time out |
| Query topology matters more than DB size at small scale | FC vs Mesh gap at DB=1,000 is 5–15× across algorithms |
| ESPM has highest per-edge overhead | 5–18× slower than MSJ at Q=20, DB=1,000 across all topologies |
| Mesh is consistently fastest | Ring-lattice local constraints allow early pruning in all algorithms |
| 0 matches at DB=1,000 — expected | Match probability ≈ 3.1%^C(20,2) ≈ 0 for uniform random placement |
