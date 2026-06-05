# Simple ESPM Implementation

A clean, readable Python implementation of **Efficient Spatial Pattern Matching**
(Chen et al., IEEE TKDE 2020) — no external spatial libraries required.

---

## What this does

Finds groups of real-world objects (e.g., a school, a park, and a hospital)
satisfying spatial constraints (e.g., within 500m of each other) by querying
a geo-textual dataset.

The key improvement over a naive approach: instead of comparing every pair of
objects directly, ESPM first prunes impossible spatial *regions* using a
quadtree index, then only checks actual objects in the surviving regions.

---

## How ESPM works

### The problem with the naive approach

For a 3-keyword pattern over 180 K objects, naively checking every triple is
O(|A| × |B| × |C|) — potentially billions of comparisons.  The MSJ baseline
reduces this with star-pruning, but still generates all candidate object pairs
first.

### ESPM's solution: keyword-specific quadtrees

```
"school" objects  →  school quadtree (one per keyword)
"park" objects    →  park quadtree
"hospital" objects → hospital quadtree
```

For each pattern edge (e.g., school–park), we compare *rectangles* before
objects:

```
Level 0: compare the two root rectangles (whole country)
Level 1: only expand child pairs whose rectangles are close enough
Level 2: only expand children of level-1 survivors
...
Leaf:    compare actual objects inside the surviving leaf pairs
```

At level 1, maybe only 3 out of 16 possible node pairs survive.  At level 2,
maybe 5 of those 3×4=12 pairs survive.  By the leaf level, we may need to
check only 0.1% of all object pairs.

### Pruning rule

A node pair (A, B) is *impossible* if:

```
dmin(A, B) > upper   →  all objects in A and B are too far apart
dmax(A, B) < lower   →  all objects in A and B are too close
```

where `dmin` and `dmax` are the minimum/maximum distances between the two
rectangles.

---

## Key terms

| Term     | Meaning                                                           |
|----------|-------------------------------------------------------------------|
| n-match  | A (node_a, node_b) pair that *might* contain a valid object pair  |
| e-match  | A confirmed (object_a, object_b) pair satisfying one pattern edge |
| match    | Complete assignment {keyword → object_id} satisfying all edges    |
| sign     | Exclusion constraint on an edge (`include`, `a_excludes_b`, …)   |

---

## Dataset format

```
data/UK/loc      object_id,longitude,latitude
data/UK/doc      object_id,keyword1,keyword2,...
data/UK/pattern  keyword_a keyword_b lower upper flag1 flag2
                 (blank lines separate patterns)
```

Flag semantics:
- `false false` → mutual inclusion (`--`)
- `true false`  → a_excludes_b (`->`)  — no kw_b object within `lower` of matched kw_a obj
- `false true`  → b_excludes_a (`<-`)
- `true true`   → mutual exclusion (`<>`)

---

## How to run

```bash
# Built-in toy correctness test
python main.py --toy

# Run pattern 0 on the UK dataset
python main.py --data-dir ../../paper1/data/UK --pattern 0 --max-matches 20

# Compare ESPM vs MSJ (unlimited matches for exact set comparison)
python main.py --data-dir ../../paper1/data/UK --pattern 40 --max-matches 0 --compare

# Quiet mode (suppress per-edge output)
python main.py --data-dir ../../paper1/data/UK --pattern 140 --quiet
```

---

## Toy example (built into main.py --toy)

```
Objects:
  0  lon=0.0  lat=0.00  keywords={school}
  1  lon=0.0  lat=0.01  keywords={park}
  2  lon=0.0  lat=0.02  keywords={hospital}
  3  lon=1.0  lat=1.00  keywords={school}   ← far away

Pattern:
  school -- park      [0.00, 0.02]
  school -- hospital  [0.00, 0.03]

Expected match:
  {school: 0, park: 1, hospital: 2}
```

Object 3 is excluded because its distance to park (≈1.414) exceeds 0.02.

---

## Differences vs `paper2/espm.py`

| Aspect                | `espm_simple/esp_m.py`              | `paper2/espm.py`               |
|-----------------------|-------------------------------------|--------------------------------|
| Data types            | `SpatialObject`, `PatternEdge`, `EMatch` dataclasses | Raw dicts + boolean flags |
| Edge signs            | Named strings (`a_excludes_b`, …)   | `flag1`, `flag2` booleans      |
| N-match computation   | Per-edge top-down expansion loop    | All edges × S-sets per level   |
| Cross-edge pruning    | Not applied (simpler)               | S-set intersection per level   |
| Exclusion check       | Pre-computed excluded sets          | Same                           |
| Output                | Per-edge n/e-match counts + timing  | Level counts                   |

The `espm_simple` version trades the cross-edge S-set optimisation for
readability.  Results are identical; performance is similar on the UK dataset
where the S-set benefit is modest.  On very large datasets (10M+ objects) the
S-set version in `paper2/espm.py` would be meaningfully faster.

---

## Limitations

- Uses raw coordinate distance (not km) — matches the UK dataset.
- In-memory only (no disk-based linear quadtree storage).
- Exclusion constraint O(|cand| × |keyword|) per edge — adequate for 200K objects.
- No explicit skip-edge optimisation (cycle-closing edges are handled normally).
