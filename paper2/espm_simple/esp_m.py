"""
esp_m.py — Simple ESPM: Efficient Spatial Pattern Matching
Chen et al., IEEE TKDE 2020

Key idea: instead of comparing every object pair directly, build one quadtree
per query keyword and prune impossible spatial regions level-by-level before
ever touching the actual objects. This eliminates most of the work early.

Three-step pipeline:
  Step 1 — N-matches:  prune quadtree node pairs using rectangle distance bounds
  Step 2 — E-matches:  verify exact objects inside surviving node pairs
  Step 3 — Join:       combine per-edge e-matches into full pattern matches

Terminology:
  n-match  — a (node_a, node_b) pair that *might* contain a valid object pair
  e-match  — a confirmed (object_a, object_b) pair satisfying one pattern edge
  match    — a complete assignment {keyword: object_id} satisfying all edges
"""

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DATA TYPES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SpatialObject:
    """A geo-textual object in the database."""
    object_id: int
    lon: float
    lat: float
    keywords: set


@dataclass
class PatternEdge:
    """
    One edge in a spatial pattern query.

    sign values:
      "include"          — vi – vj  (mutual inclusion, no exclusion zone)
      "a_excludes_b"     — vi → vj  (no kw_b object within `lower` of the matched kw_a obj)
      "b_excludes_a"     — vj → vi  (no kw_a object within `lower` of the matched kw_b obj)
      "mutual_exclusion" — vi ↔ vj  (both exclusion directions)
    """
    keyword_a: str
    keyword_b: str
    lower: float    # minimum distance between matched objects
    upper: float    # maximum distance between matched objects
    sign: str = "include"


@dataclass
class QuadtreeNode:
    """A rectangular spatial region in a per-keyword quadtree."""
    node_id:    int
    level:      int
    min_lon:    float
    min_lat:    float
    max_lon:    float
    max_lat:    float
    object_ids: list  = field(default_factory=list)  # populated only in leaf nodes
    children:   list  = field(default_factory=list)  # empty list = leaf node
    is_leaf:    bool  = True
    obj_count:  int   = 0   # total objects in this subtree (for quick empty checks)


@dataclass
class EMatch:
    """An exact object pair satisfying one pattern edge."""
    keyword_a: str
    keyword_b: str
    object_a:  int
    object_b:  int
    distance:  float


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_locations(path: str) -> dict:
    """Read loc file  → {object_id: (lon, lat)}.  Format: object_id,lon,lat"""
    locs = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            locs[int(parts[0])] = (float(parts[1]), float(parts[2]))
    return locs


def load_documents(path: str) -> dict:
    """Read doc file → {object_id: set[str]}.  Format: object_id,kw1,kw2,..."""
    docs = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            docs[int(parts[0])] = {k.strip().lower() for k in parts[1:] if k.strip()}
    return docs


def load_objects(loc_path: str, doc_path: str) -> dict:
    """Merge locations and keywords into {object_id: SpatialObject}."""
    locs = load_locations(loc_path)
    docs = load_documents(doc_path)
    objs = {}
    for oid, (lon, lat) in locs.items():
        objs[oid] = SpatialObject(oid, lon, lat, docs.get(oid, set()))
    orphans = set(docs) - set(locs)
    if orphans:
        print(f"Warning: {len(orphans)} objects in doc have no location (skipped).")
    return objs


def _flags_to_sign(flag1: bool, flag2: bool) -> str:
    """Convert the UK dataset's two-boolean edge flags to a readable sign string."""
    if flag1 and flag2:   return "mutual_exclusion"
    if flag1:             return "a_excludes_b"
    if flag2:             return "b_excludes_a"
    return "include"


def load_patterns(pattern_path: str) -> list:
    """
    Read pattern file → list[list[PatternEdge]].

    Patterns are separated by blank lines.
    Each non-blank line:  keyword_a  keyword_b  lower  upper  flag1  flag2
    """
    patterns = []
    current = []
    with open(pattern_path) as f:
        for line in f:
            stripped = line.strip()
            if stripped == '':
                if current:
                    patterns.append(current)
                    current = []
            else:
                parts = stripped.split()
                if len(parts) != 6:
                    continue
                current.append(PatternEdge(
                    keyword_a = parts[0].lower(),
                    keyword_b = parts[1].lower(),
                    lower     = float(parts[2]),
                    upper     = float(parts[3]),
                    sign      = _flags_to_sign(parts[4].lower() == 'true',
                                               parts[5].lower() == 'true'),
                ))
    if current:
        patterns.append(current)
    return patterns


def build_inverted_index(objects: dict) -> dict:
    """Build {keyword: [object_id, ...]} over all objects."""
    idx = defaultdict(list)
    for oid, obj in objects.items():
        for kw in obj.keywords:
            idx[kw].append(oid)
    return dict(idx)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DISTANCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def raw_distance(a: SpatialObject, b: SpatialObject) -> float:
    """
    Euclidean distance in coordinate degrees.
    The UK dataset's pattern intervals are stored in coordinate space (not km),
    so this matches the paper's experimental setup exactly.
    """
    return math.hypot(a.lon - b.lon, a.lat - b.lat)


def rect_dmin(a: QuadtreeNode, b: QuadtreeNode) -> float:
    """
    Minimum possible distance between any point in rectangle a and any in b.

    If the rectangles overlap in a dimension, the gap in that dimension is 0.
    Used to prune node pairs that are definitely too far apart.
    """
    dx = max(0.0, max(a.min_lon - b.max_lon, b.min_lon - a.max_lon))
    dy = max(0.0, max(a.min_lat - b.max_lat, b.min_lat - a.max_lat))
    return math.hypot(dx, dy)


def rect_dmax(a: QuadtreeNode, b: QuadtreeNode) -> float:
    """
    Maximum possible distance between any point in rectangle a and any in b.

    The maximum is always achieved between two corners (one from each rectangle).
    Used to prune node pairs that are definitely too close together.
    """
    corners_a = [(a.min_lon, a.min_lat), (a.min_lon, a.max_lat),
                 (a.max_lon, a.min_lat), (a.max_lon, a.max_lat)]
    corners_b = [(b.min_lon, b.min_lat), (b.min_lon, b.max_lat),
                 (b.max_lon, b.min_lat), (b.max_lon, b.max_lat)]
    return max(math.hypot(ax - bx, ay - by)
               for ax, ay in corners_a
               for bx, by in corners_b)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. QUADTREE CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════════

_node_id_counter = 0

def _next_id() -> int:
    global _node_id_counter
    _node_id_counter += 1
    return _node_id_counter


def _build_node(objects: dict, oids: list, level: int,
                min_lon: float, min_lat: float,
                max_lon: float, max_lat: float,
                max_per_leaf: int, max_depth: int, min_depth: int) -> QuadtreeNode:
    """Recursively build one quadtree node covering the given bounding box."""
    node = QuadtreeNode(
        node_id = _next_id(),
        level   = level,
        min_lon = min_lon, min_lat = min_lat,
        max_lon = max_lon, max_lat = max_lat,
        obj_count = len(oids),
    )

    # Decide whether to split:
    # - always split below min_depth (force sufficient granularity)
    # - split above min_depth only when too many objects and not at max_depth
    should_split = (level < min_depth) or (level < max_depth and len(oids) > max_per_leaf)

    if not should_split or not oids:
        # Leaf node: store objects here
        node.object_ids = list(oids)
        node.is_leaf = True
        return node

    # Internal node: split into 4 quadrants
    node.is_leaf = False
    mid_lon = (min_lon + max_lon) / 2.0
    mid_lat = (min_lat + max_lat) / 2.0

    # Each object goes into exactly one quadrant (bit 1 = east, bit 0 = north)
    buckets: list = [[], [], [], []]
    for oid in oids:
        obj = objects[oid]
        q = (2 if obj.lon >= mid_lon else 0) | (1 if obj.lat >= mid_lat else 0)
        buckets[q].append(oid)

    bounds = [
        (min_lon, min_lat, mid_lon, mid_lat),   # q=0: SW
        (min_lon, mid_lat, mid_lon, max_lat),   # q=1: NW
        (mid_lon, min_lat, max_lon, mid_lat),   # q=2: SE
        (mid_lon, mid_lat, max_lon, max_lat),   # q=3: NE
    ]
    for i, (xlo, ylo, xhi, yhi) in enumerate(bounds):
        child = _build_node(
            objects, buckets[i], level + 1,
            xlo, ylo, xhi, yhi,
            max_per_leaf, max_depth, min_depth,
        )
        node.children.append(child)

    return node


def build_quadtree(objects: dict, object_ids: list,
                   max_per_leaf: int = 64, max_depth: int = 15,
                   min_depth: int = 2) -> Optional[QuadtreeNode]:
    """
    Build a quadtree for a specific subset of objects (e.g., all "school" objects).

    Returns None if object_ids is empty.
    """
    if not object_ids:
        return None

    lons = [objects[oid].lon for oid in object_ids]
    lats = [objects[oid].lat for oid in object_ids]
    eps = 1e-9   # tiny padding so boundary objects sit strictly inside the root

    return _build_node(
        objects, object_ids, level=0,
        min_lon=min(lons) - eps, min_lat=min(lats) - eps,
        max_lon=max(lons) + eps, max_lat=max(lats) + eps,
        max_per_leaf=max_per_leaf, max_depth=max_depth, min_depth=min_depth,
    )


def build_inverted_quadtrees(objects: dict, query_keywords: set,
                              max_per_leaf: int = 64,
                              max_depth: int = 15,
                              min_depth: int = 2) -> dict:
    """
    Build one quadtree per query keyword — the "Inverted" part of IL-Quadtree.

    Each tree contains only objects that have the corresponding keyword,
    so searches on unrelated keywords never touch irrelevant objects at all.

    Returns {keyword: root_QuadtreeNode}.
    """
    trees = {}
    for kw in query_keywords:
        kw_ids = [oid for oid, obj in objects.items() if kw in obj.keywords]
        root = build_quadtree(objects, kw_ids, max_per_leaf, max_depth, min_depth)
        if root is not None:
            trees[kw] = root
    return trees


def count_nodes(node: QuadtreeNode) -> int:
    """Count total nodes in a quadtree (for reporting)."""
    if node.is_leaf:
        return 1
    return 1 + sum(count_nodes(c) for c in node.children)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. N-MATCH COMPUTATION  (Step 1)
# ═══════════════════════════════════════════════════════════════════════════════

def is_node_pair_possible(node_a: QuadtreeNode, node_b: QuadtreeNode,
                           edge: PatternEdge) -> bool:
    """
    Check whether two quadtree nodes *might* contain a valid object pair for `edge`.

    Pruning rules:
      dmin > upper  →  all object pairs are too far apart:  prune
      dmax < lower  →  all object pairs are too close:      prune
      otherwise     →  some pair might satisfy [lower, upper]: keep

    For exclusion signs the same distance feasibility applies.
    The exact exclusion constraint is verified at the object level (Step 2).
    """
    if node_a.obj_count == 0 or node_b.obj_count == 0:
        return False
    d_min = rect_dmin(node_a, node_b)
    d_max = rect_dmax(node_a, node_b)
    return d_min <= edge.upper and d_max >= edge.lower


def compute_n_matches_for_edge(edge: PatternEdge,
                                keyword_quadtrees: dict) -> list:
    """
    Top-down node-pair pruning for one pattern edge.  This is the core ESPM idea.

    We start with the root nodes of the two keyword quadtrees and expand
    only the pairs that pass the rectangle distance check.  At each level,
    the number of surviving pairs shrinks dramatically — impossible regions
    are eliminated before any objects are ever loaded or compared.

    Returns a list of (leaf_node_a, leaf_node_b) pairs that survived all levels.
    """
    root_a = keyword_quadtrees.get(edge.keyword_a)
    root_b = keyword_quadtrees.get(edge.keyword_b)
    if root_a is None or root_b is None:
        return []

    # Start with the two root nodes; expand until both sides are leaves
    current_pairs = [(root_a, root_b)]
    leaf_pairs = []

    while current_pairs:
        next_pairs = []
        for node_a, node_b in current_pairs:

            if node_a.is_leaf and node_b.is_leaf:
                # Both sides are leaves — no further expansion possible
                leaf_pairs.append((node_a, node_b))
                continue

            # Expand whichever side still has children
            children_a = node_a.children if not node_a.is_leaf else [node_a]
            children_b = node_b.children if not node_b.is_leaf else [node_b]

            for child_a in children_a:
                for child_b in children_b:
                    # Key pruning: only keep spatially feasible child pairs
                    if is_node_pair_possible(child_a, child_b, edge):
                        next_pairs.append((child_a, child_b))

        current_pairs = next_pairs

    return leaf_pairs


# ═══════════════════════════════════════════════════════════════════════════════
# 6. E-MATCH COMPUTATION  (Step 2)
# ═══════════════════════════════════════════════════════════════════════════════

def _any_within_radius(node: QuadtreeNode, objects: dict,
                       lon: float, lat: float,
                       radius: float, exclude_id: int) -> bool:
    """
    Quadtree-accelerated proximity check: does any object in `node`'s subtree
    lie within `radius` of (lon, lat), excluding `exclude_id`?

    Uses dmin(point, rectangle) to prune entire subtrees that are too far away.
    Reduces exclusion checks from O(|keyword|) to O(log N) per candidate.
    """
    # Minimum distance from query point to this node's bounding box
    dx = max(0.0, max(node.min_lon - lon, lon - node.max_lon))
    dy = max(0.0, max(node.min_lat - lat, lat - node.max_lat))
    if math.hypot(dx, dy) >= radius:
        return False  # entire subtree is too far

    if node.is_leaf:
        for oid in node.object_ids:
            if oid == exclude_id:
                continue
            o = objects[oid]
            if math.hypot(o.lon - lon, o.lat - lat) < radius:
                return True
        return False

    return any(_any_within_radius(c, objects, lon, lat, radius, exclude_id)
               for c in node.children)


def check_exclusion_constraint(objects: dict, kw_trees: dict,
                                obj_a: SpatialObject, obj_b: SpatialObject,
                                edge: PatternEdge) -> bool:
    """
    Verify the sign (exclusion zone) constraint for one candidate pair.

    a_excludes_b: no OTHER kw_b object may be within `lower` of obj_a.
    b_excludes_a: no OTHER kw_a object may be within `lower` of obj_b.
    mutual_exclusion: both checks must pass.
    include: always passes.
    """
    if edge.sign == "include" or edge.lower <= 0:
        return True

    if edge.sign in ("a_excludes_b", "mutual_exclusion"):
        tree_b = kw_trees.get(edge.keyword_b)
        if tree_b and _any_within_radius(tree_b, objects, obj_a.lon, obj_a.lat,
                                          edge.lower, obj_b.object_id):
            return False

    if edge.sign in ("b_excludes_a", "mutual_exclusion"):
        tree_a = kw_trees.get(edge.keyword_a)
        if tree_a and _any_within_radius(tree_a, objects, obj_b.lon, obj_b.lat,
                                          edge.lower, obj_a.object_id):
            return False

    return True


def compute_e_matches_from_n_matches(objects: dict, edge: PatternEdge,
                                      n_matches: list,
                                      kw_trees: dict) -> list:
    """
    Compute exact object pairs (e-matches) from surviving leaf node pairs.

    Exclusion check uses the keyword quadtrees for O(log N) proximity queries
    instead of scanning all keyword objects linearly.
    """
    # Collect unique candidate objects from the leaf nodes
    seen_a: set = set()
    seen_b: set = set()
    cands_a: list = []
    cands_b: list = []

    for node_a, node_b in n_matches:
        for oid in node_a.object_ids:
            if oid not in seen_a:
                cands_a.append(objects[oid])
                seen_a.add(oid)
        for oid in node_b.object_ids:
            if oid not in seen_b:
                cands_b.append(objects[oid])
                seen_b.add(oid)

    # Pre-compute which candidate objects are excluded by sign constraints.
    # Uses _any_within_radius for O(log N) per candidate instead of O(|kw|).
    excl_a: set = set()
    if edge.sign in ("a_excludes_b", "mutual_exclusion") and edge.lower > 0:
        tree_b = kw_trees.get(edge.keyword_b)
        if tree_b:
            for obj_a in cands_a:
                if _any_within_radius(tree_b, objects, obj_a.lon, obj_a.lat,
                                       edge.lower, obj_a.object_id):
                    excl_a.add(obj_a.object_id)

    excl_b: set = set()
    if edge.sign in ("b_excludes_a", "mutual_exclusion") and edge.lower > 0:
        tree_a = kw_trees.get(edge.keyword_a)
        if tree_a:
            for obj_b in cands_b:
                if _any_within_radius(tree_a, objects, obj_b.lon, obj_b.lat,
                                       edge.lower, obj_b.object_id):
                    excl_b.add(obj_b.object_id)

    # Now do the actual pair comparison on the surviving candidates
    seen_pairs: set = set()
    results: list = []

    for obj_a in cands_a:
        if obj_a.object_id in excl_a:
            continue
        for obj_b in cands_b:
            if obj_b.object_id == obj_a.object_id:
                continue   # same object can't fill two different keyword roles
            if obj_b.object_id in excl_b:
                continue

            pair_key = (obj_a.object_id, obj_b.object_id)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            d = raw_distance(obj_a, obj_b)
            if edge.lower <= d <= edge.upper:
                results.append(EMatch(
                    keyword_a = edge.keyword_a,
                    keyword_b = edge.keyword_b,
                    object_a  = obj_a.object_id,
                    object_b  = obj_b.object_id,
                    distance  = d,
                ))

    return results


def compute_all_e_matches(objects: dict, pattern_edges: list,
                           keyword_quadtrees: dict,
                           verbose: bool = True) -> dict:
    """
    Compute e-matches for every pattern edge.

    Ordering: exclusion edges first (they have tighter constraints → fewer
    n-matches and e-matches → faster to prune if they're empty).

    Returns {edge_index: [EMatch, ...]} or {} if any edge has 0 e-matches.
    """
    # Sort: exclusion edges first, then inclusion edges (within each group: as-is)
    excl_indices = [i for i, e in enumerate(pattern_edges) if e.sign != "include"]
    incl_indices = [i for i, e in enumerate(pattern_edges) if e.sign == "include"]
    order = excl_indices + incl_indices

    result: dict = {}

    for edge_idx in order:
        edge = pattern_edges[edge_idx]
        sign_tag = f" [{edge.sign}]" if edge.sign != "include" else ""
        label = f"'{edge.keyword_a}'{sign_tag} -- '{edge.keyword_b}'"

        t0 = time.perf_counter()
        n_matches = compute_n_matches_for_edge(edge, keyword_quadtrees)
        t_n = time.perf_counter() - t0

        if not n_matches:
            if verbose:
                print(f"  Edge {edge_idx} {label}: 0 n-matches — no matches possible.")
            return {}

        e_matches = compute_e_matches_from_n_matches(objects, edge, n_matches, keyword_quadtrees)
        t_e = time.perf_counter() - t0

        if verbose:
            print(f"  Edge {edge_idx} {label}: "
                  f"{len(n_matches):,} n-matches, {len(e_matches):,} e-matches  ({t_e:.3f}s)")

        if not e_matches:
            if verbose:
                print(f"  -> 0 e-matches — no matches possible.")
            return {}

        result[edge_idx] = e_matches

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 7. JOIN E-MATCHES  (Step 3)
# ═══════════════════════════════════════════════════════════════════════════════

def _connected_join_order(pattern_edges: list, edge_to_ematches: dict) -> list:
    """
    Order edges for the backtracking join using a connected-first, size-ascending strategy.

    Connected-first ensures each new edge shares at least one keyword with the
    already-assigned set, so the join extends partial matches rather than creating
    Cartesian products.  Among connected candidates, we pick the one with the
    fewest e-matches first — smaller search space = faster pruning.
    """
    remaining = list(range(len(pattern_edges)))
    ordered:  list = []
    covered:  set  = set()

    while remaining:
        best_idx    = None
        best_conn   = False
        best_size   = float('inf')

        for i in remaining:
            e    = pattern_edges[i]
            conn = e.keyword_a in covered or e.keyword_b in covered
            size = len(edge_to_ematches.get(i, []))

            if (not best_conn and conn) or (conn == best_conn and size < best_size):
                best_idx  = i
                best_conn = conn
                best_size = size

        ordered.append(best_idx)
        remaining.remove(best_idx)
        e = pattern_edges[best_idx]
        covered.add(e.keyword_a)
        covered.add(e.keyword_b)

    return ordered


def join_e_matches(pattern_edges: list, edge_to_ematches: dict,
                   max_matches: int = 20) -> list:
    """
    Backtracking join: combine per-edge e-matches into complete pattern matches.

    Each e-match proposes keyword_a → object_a and keyword_b → object_b.
    We build partial assignments incrementally:
    - If a keyword is already assigned, the new e-match must agree.
    - No two keywords may map to the same physical object.

    Returns list of {keyword: object_id} dicts.
    """
    results: list = []
    if not edge_to_ematches:
        return results

    join_order = _connected_join_order(pattern_edges, edge_to_ematches)

    # Pre-build pair sets for O(1) backward-edge verification
    pair_sets = {
        i: {(em.object_a, em.object_b) for em in edge_to_ematches.get(i, [])}
        for i in range(len(pattern_edges))
    }

    def backtrack(step: int, assignment: dict, used_ids: set) -> None:
        if max_matches and len(results) >= max_matches:
            return
        if step == len(join_order):
            results.append(dict(assignment))
            return

        edge_idx = join_order[step]
        edge = pattern_edges[edge_idx]
        ka, kb = edge.keyword_a, edge.keyword_b

        # Backward edge: both keywords already bound — just verify the pair exists
        if ka in assignment and kb in assignment:
            if (assignment[ka], assignment[kb]) in pair_sets[edge_idx]:
                backtrack(step + 1, assignment, used_ids)
            return

        for em in edge_to_ematches.get(edge_idx, []):
            oa, ob = em.object_a, em.object_b

            # Skip if this e-match contradicts an already-made assignment
            if ka in assignment and assignment[ka] != oa:
                continue
            if kb in assignment and assignment[kb] != ob:
                continue
            # Skip if an object would be reused for a different keyword
            if oa in used_ids and assignment.get(ka) != oa:
                continue
            if ob in used_ids and assignment.get(kb) != ob:
                continue

            # Extend the partial assignment
            new_ka = ka not in assignment
            new_kb = kb not in assignment
            new_oa = oa not in used_ids
            new_ob = ob not in used_ids

            if new_ka: assignment[ka] = oa
            if new_kb: assignment[kb] = ob
            if new_oa: used_ids.add(oa)
            if new_ob: used_ids.add(ob)

            backtrack(step + 1, assignment, used_ids)

            # Undo the extension
            if new_ka: del assignment[ka]
            if new_kb: del assignment[kb]
            if new_oa: used_ids.discard(oa)
            if new_ob: used_ids.discard(ob)

    backtrack(0, {}, set())
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 8. BOUNDED PATTERN PRE-PROCESSING  (optional but valuable)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_bounded_pattern(pattern: list) -> tuple:
    """
    Tighten distance intervals via Floyd-Warshall triangle inequality.

    Example: if school--park [0, 0.5] and park--hospital [0, 0.3], then
    school--hospital can be at most 0.8, so [0, 0.8] is tighter than [0, ∞).

    This shrinks the search radius before any quadtree work begins.

    Returns (tightened_pattern, is_feasible).
    is_feasible=False means the pattern provably has no matches.
    """
    if len(pattern) < 2:
        return list(pattern), True

    kws = sorted({e.keyword_a for e in pattern} | {e.keyword_b for e in pattern})
    n   = len(kws)
    idx = {kw: i for i, kw in enumerate(kws)}
    INF = float('inf')

    u = [[INF] * n for _ in range(n)]
    l = [[0.0]  * n for _ in range(n)]
    for i in range(n):
        u[i][i] = 0.0

    for e in pattern:
        i, j = idx[e.keyword_a], idx[e.keyword_b]
        u[i][j] = min(u[i][j], e.upper);  u[j][i] = min(u[j][i], e.upper)
        l[i][j] = max(l[i][j], e.lower);  l[j][i] = max(l[j][i], e.lower)

    # Floyd-Warshall: tighten upper bounds
    for k in range(n):
        for i in range(n):
            if u[i][k] == INF:
                continue
            for j in range(n):
                if u[k][j] < INF:
                    u[i][j] = min(u[i][j], u[i][k] + u[k][j])

    # Iterative lower-bound tightening
    for _ in range(n):
        changed = False
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    nl = 0.0
                    if u[i][k] < INF: nl = max(nl, l[k][j] - u[i][k])
                    if u[k][j] < INF: nl = max(nl, l[i][k] - u[k][j])
                    if nl > l[i][j] + 1e-15:
                        l[i][j] = nl
                        changed = True
        if not changed:
            break

    tightened = []
    for e in pattern:
        i, j    = idx[e.keyword_a], idx[e.keyword_b]
        new_u   = min(e.upper, u[i][j])
        is_excl = e.sign != "include"
        new_l   = e.lower if is_excl else max(e.lower, l[i][j])
        if new_l > new_u + 1e-12:
            return list(pattern), False
        tightened.append(PatternEdge(e.keyword_a, e.keyword_b, new_l, new_u, e.sign))

    return tightened, True


# ═══════════════════════════════════════════════════════════════════════════════
# 9. TOP-LEVEL ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def run_espm(objects: dict, pattern: list,
             max_matches: int = 20,
             max_depth: int   = 15,
             leaf_size: int   = 64,
             verbose:   bool  = True) -> list:
    """
    Full ESPM pipeline for one query pattern.

    Args:
        objects:     {object_id: SpatialObject}
        pattern:     list of PatternEdge
        max_matches: stop after this many results (0 = unlimited)
        max_depth:   quadtree depth limit
        leaf_size:   split a node when it has more objects than this
        verbose:     print per-step statistics

    Returns:
        list of {keyword: object_id} dicts, one per match
    """
    t_start = time.perf_counter()

    # ── Pre-process: tighten distance intervals ────────────────────────────────
    pattern, feasible = compute_bounded_pattern(pattern)
    if not feasible:
        if verbose:
            print("  Pattern is infeasible (bounded-pattern detected empty interval).")
        return []

    # ── Collect query keywords ─────────────────────────────────────────────────
    query_kws: set = set()
    for e in pattern:
        query_kws.add(e.keyword_a)
        query_kws.add(e.keyword_b)

    if verbose:
        print(f"  Query keywords: {sorted(query_kws)}")

    # ── Build inverted index (restricted to query keywords for speed) ──────────
    inv_idx = defaultdict(list)
    for oid, obj in objects.items():
        for kw in obj.keywords:
            if kw in query_kws:
                inv_idx[kw].append(oid)

    if verbose:
        for kw in sorted(query_kws):
            print(f"    {kw}: {len(inv_idx.get(kw, [])):,} objects")

    # ── Build one quadtree per query keyword ───────────────────────────────────
    t0 = time.perf_counter()
    kw_trees = build_inverted_quadtrees(objects, query_kws, leaf_size, max_depth, min_depth=2)
    if verbose:
        print(f"  Built {len(kw_trees)} keyword quadtrees  ({time.perf_counter()-t0:.3f}s)")
        for kw, root in sorted(kw_trees.items()):
            print(f"    {kw}: {count_nodes(root):,} nodes")

    # Check every keyword has at least one object
    for kw in query_kws:
        if kw not in kw_trees:
            if verbose:
                print(f"  Keyword '{kw}' not found in dataset — no matches.")
            return []

    # ── Step 1 + 2: n-matches → e-matches per edge ────────────────────────────
    if verbose:
        print("  Computing n-matches + e-matches...")
    edge_to_ematches = compute_all_e_matches(objects, pattern, kw_trees, verbose)
    if not edge_to_ematches:
        return []

    # ── Step 3: join e-matches into full pattern matches ──────────────────────
    if verbose:
        print("  Joining e-matches...")
    matches = join_e_matches(pattern, edge_to_ematches, max_matches)

    t_total = time.perf_counter() - t_start
    if verbose:
        print(f"  Matches: {len(matches):,}   Total time: {t_total:.3f}s")

    return matches
