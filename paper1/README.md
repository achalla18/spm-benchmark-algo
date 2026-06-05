# Spatial Pattern Matching — MPJ + MSJ

Implementation of the ICDE 2018 paper:

> Fang, Y., et al. (2018).  
> **"Spatial Pattern Matching over Large-scale Geo-textual Data."**  
> *IEEE International Conference on Data Engineering (ICDE).*

Both algorithms from the paper are implemented:
- **MPJ** (Multi-Pair Join) — the baseline: candidate pairs per edge, then backtracking join.
- **MSJ** (Multi-Star Join) — the optimized version: star-pruning eliminates objects
  that cannot participate in any valid match before the join phase.

## What this project does

Spatial Pattern Matching (SPM) answers queries like:
*"Find groups of nearby places where one is a 'school', one is a 'park',
and one is a 'hospital', with specific distance constraints between them."*

The query is a **pattern graph**: each vertex is a keyword (like "school") and
each edge specifies how far apart two keywords must be.
The algorithm searches a database of geo-textual objects (locations + keywords)
for all groups of objects that satisfy the pattern.

---

## Dataset format (UK dataset from Fang et al. 2019)

The data lives in `data/UK/` after extracting `UK.zip`.

### `loc` — coordinates

```
object_id,longitude,latitude
0,-3.12199,51.01387
1,-1.99886,52.58378
```

### `doc` — keywords

```
object_id,keyword1,keyword2,...
0,park,musgrove,taunton
1,walsall
```

### `pattern` — query patterns

Patterns are groups of consecutive lines separated by blank/space-only lines.
Each line is one edge:

```
keyword_a keyword_b lower_distance upper_distance flag1 flag2
west garden 0.005343840358687814 0.017155104489580665 false false
```

The distances are in raw coordinate units (degrees), **not kilometers**.
The UK dataset has 181,964 objects, 38,304 unique keywords, and 240 query patterns
(20 patterns each for 1, 2, 3, 3, 4, 5, 5, 6, 7 edge counts).

---

## How the algorithm works

**Step 1 — Load**
Read `loc` and `doc`, combine them into a dict of spatial objects:
`{object_id: {"lon", "lat", "keywords"}}`.

**Step 2 — Inverted index**
Build `{keyword: [object_ids]}` so we can instantly look up all objects
that have a given keyword, without scanning all 181,964 objects.

**Step 3 — Candidate pairs (per edge)**
For each pattern edge `(keyword_a, keyword_b, lower, upper)`:
- Get all objects with `keyword_a` (set A) and all with `keyword_b` (set B).
- Find every pair (a, b) where `lower <= distance(a, b) <= upper`.

The grid index speeds this up: instead of O(|A| × |B|) comparisons, each
object in A only checks nearby objects in B using a spatial grid.

**Step 4 — Join (backtracking)**
Combine the per-edge candidate lists into full matches, where each keyword
vertex maps to one unique object. Uses backtracking: process edges in order
of increasing candidate count (most-constrained first), extend partial
assignments, and prune inconsistent branches early.

---

## Files

```
spm.py            Core algorithm: parsing, distance, grid index, MPJ, MSJ
main.py           Command-line runner
osmnx_adapter.py  Converts OpenStreetMap POIs into the loc/doc format
data/UK/          Dataset (extracted from UK.zip)
UK.zip            Raw dataset archive (181,964 objects, 38,304 keywords, 240 patterns)
paper.pdf         The ICDE 2018 paper
```

---

## How to run

```bash
# MSJ (default, optimized) — pattern 0, up to 20 matches
python main.py --pattern 0 --max-matches 20

# MPJ baseline
python main.py --pattern 0 --algo mpj

# Compare both algorithms on the same pattern
python main.py --pattern 140 --algo both --max-matches 100

# Run without the grid index (naive mode)
python main.py --pattern 0 --no-grid
```

---

## How this differs from OSMnx data

| Feature | Fang dataset | OSMnx |
|---|---|---|
| Main object | Geo-textual POI | Street network node/edge |
| Coordinates | `loc`: id → lon/lat | `nodes` GeoDataFrame: x, y |
| Labels | `doc`: id → keywords | OSM tags: amenity, shop, name, … |
| Need road graph? | No | Usually yes |
| Best structure | Flat dict + inverted index | GeoDataFrame / NetworkX graph |

To use OSMnx data with this algorithm, convert each OSM feature into the
same format: pick a centroid as lon/lat, and collect tag values as keywords.

---

## Edge signs (flags)

Each pattern edge carries two boolean flags that encode the "sign" from the paper (Definition 1):

| flag1 | flag2 | Sign | Meaning |
|-------|-------|------|---------|
| False | False | vi – vj  | Mutual inclusion: any other object near either endpoint is allowed |
| True  | False | vi → vj  | vi excludes vj: no other wj object may be closer than `lower` to ok |
| False | True  | vi ← vj  | vj excludes vi: no other wi object may be closer than `lower` to ol |
| True  | True  | vi ↔ vj  | Mutual exclusion: both exclusion directions apply |

The exclusion constraint is enforced in `find_candidate_pairs` before generating
pairs. An object ok is excluded from an edge if the exclusion zone around it already
contains another object of the opposing keyword.

In the UK dataset: 87/240 patterns contain at least one exclusion edge.

## Limitations of this baseline

- **Naive join is slow for large candidate sets.** If a pattern edge links two
  very common keywords (e.g., "st" with 10,000+ objects), the candidate list
  can be huge and backtracking becomes slow. The paper's MSJ algorithm adds
  pruning to handle this.
- **Distance is raw Euclidean (degrees), not km.** The pattern file distances
  appear to be in coordinate space (degrees), matching the paper's Euclidean
  distance assumption for this dataset.
- **Same-keyword vertices on one edge are not supported.** If a pattern has an
  edge both labeled with the same keyword, the join would conflate them. The
  paper uses vertex IDs, not keywords, as identifiers. Shared-keyword vertices
  across different edges (e.g., "gc" appearing in both edges of a 2-edge path)
  are handled correctly.
