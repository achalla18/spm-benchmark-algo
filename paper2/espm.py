"""
ESPM: Efficient Spatial Pattern Matching
Chen et al., IEEE Transactions on Knowledge and Data Engineering, Vol. 32, No. 6, 2020

Three-step algorithm over an Inverted Linear Quadtree (IL-Quadtree) index:
  Step 1: N-matches  — node-pair filtering, level by level, top-down
  Step 2: E-matches  — object-pair candidate filtering from leaf n-match nodes
  Step 3: Join       — backtracking join with skip-edge pruning

Edge sign semantics (same as paper1/spm.py):
  flag1=False, flag2=False  →  vi – vj  (mutual inclusion)
  flag1=True,  flag2=False  →  vi → vj  (vi excludes vj: no obj w/ kw_b within lo of matched vi obj)
  flag1=False, flag2=True   →  vj → vi  (vj excludes vi: no obj w/ kw_a within lo of matched vj obj)
  flag1=True,  flag2=True   →  vi ↔ vj  (mutual exclusion: both directions)
"""

import math
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


# ─── Data Loading ─────────────────────────────────────────────────────────────

def load_locations(loc_path: str) -> dict:
    locs = {}
    with open(loc_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            locs[int(parts[0])] = (float(parts[1]), float(parts[2]))
    return locs


def load_documents(doc_path: str) -> dict:
    docs = {}
    with open(doc_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            oid = int(parts[0])
            docs[oid] = {k.strip().lower() for k in parts[1:] if k.strip()}
    return docs


def load_objects(loc_path: str, doc_path: str) -> dict:
    locs = load_locations(loc_path)
    docs = load_documents(doc_path)
    objs = {}
    for oid, (lon, lat) in locs.items():
        objs[oid] = {"lon": lon, "lat": lat, "keywords": docs.get(oid, set())}
    orphans = set(docs) - set(locs)
    if orphans:
        print(f"Warning: {len(orphans)} objects in doc but not loc (skipped).")
    return objs


def load_patterns(pattern_path: str) -> list:
    with open(pattern_path) as f:
        lines = f.readlines()
    patterns = []
    current = []
    for line in lines:
        stripped = line.strip()
        if stripped == '':
            if current:
                patterns.append(current)
                current = []
        else:
            parts = stripped.split()
            if len(parts) != 6:
                continue
            current.append({
                "keyword_a": parts[0].lower(),
                "keyword_b": parts[1].lower(),
                "lower":     float(parts[2]),
                "upper":     float(parts[3]),
                "flag1":     parts[4].lower() == 'true',
                "flag2":     parts[5].lower() == 'true',
            })
    if current:
        patterns.append(current)
    return patterns


# ─── Bounded Pattern Tightening (Section IV.A of the ICDE 2018 paper) ─────────

def compute_bounded_pattern(pattern_edges: list) -> tuple:
    """
    Tighten each edge's distance interval via Floyd-Warshall triangle inequality.
    Returns (tightened_edges, is_feasible).
    """
    if len(pattern_edges) < 2:
        return list(pattern_edges), True

    kws = sorted(
        {e["keyword_a"] for e in pattern_edges} |
        {e["keyword_b"] for e in pattern_edges}
    )
    n = len(kws)
    idx = {kw: i for i, kw in enumerate(kws)}
    INF = float('inf')

    u = [[INF] * n for _ in range(n)]
    l = [[0.0]  * n for _ in range(n)]
    for i in range(n):
        u[i][i] = 0.0

    for e in pattern_edges:
        i, j = idx[e["keyword_a"]], idx[e["keyword_b"]]
        u[i][j] = min(u[i][j], e["upper"])
        u[j][i] = min(u[j][i], e["upper"])
        l[i][j] = max(l[i][j], e["lower"])
        l[j][i] = max(l[j][i], e["lower"])

    for k in range(n):
        for i in range(n):
            if u[i][k] == INF:
                continue
            for j in range(n):
                if u[k][j] < INF:
                    u[i][j] = min(u[i][j], u[i][k] + u[k][j])

    for _ in range(n):
        changed = False
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    new_l = 0.0
                    if u[i][k] < INF:
                        new_l = max(new_l, l[k][j] - u[i][k])
                    if u[k][j] < INF:
                        new_l = max(new_l, l[i][k] - u[k][j])
                    if new_l > l[i][j] + 1e-15:
                        l[i][j] = new_l
                        changed = True
        if not changed:
            break

    tightened = []
    for e in pattern_edges:
        i, j   = idx[e["keyword_a"]], idx[e["keyword_b"]]
        new_u  = min(e["upper"], u[i][j])
        is_excl = e["flag1"] or e["flag2"]
        new_l  = e["lower"] if is_excl else max(e["lower"], l[i][j])
        if new_l > new_u + 1e-12:
            return list(pattern_edges), False
        new_e = dict(e)
        new_e["lower"] = new_l
        new_e["upper"] = new_u
        tightened.append(new_e)

    return tightened, True


# ─── MBR ──────────────────────────────────────────────────────────────────────

@dataclass
class MBR:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def dmin(self, other: "MBR") -> float:
        """Minimum possible distance between two MBRs."""
        dx = max(0.0, max(self.xmin, other.xmin) - min(self.xmax, other.xmax))
        dy = max(0.0, max(self.ymin, other.ymin) - min(self.ymax, other.ymax))
        return math.hypot(dx, dy)

    def dmax(self, other: "MBR") -> float:
        """Maximum possible distance between two MBRs."""
        dx = max(abs(self.xmin - other.xmax), abs(self.xmax - other.xmin))
        dy = max(abs(self.ymin - other.ymax), abs(self.ymax - other.ymin))
        return math.hypot(dx, dy)


# ─── Linear Quadtree Node ─────────────────────────────────────────────────────

class QNode:
    """Node in a linear quadtree. Leaf nodes store object tuples (oid, lon, lat)."""
    __slots__ = ("mbr", "level", "objects", "children", "n_objects")

    def __init__(self, mbr: MBR, level: int):
        self.mbr = mbr
        self.level = level
        self.objects: list = []   # (oid, lon, lat) — only populated in leaf nodes
        self.children: list = []  # 4 QNodes for internal nodes, empty for leaves
        self.n_objects: int = 0   # total objects in subtree (for fast empty check)

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def all_objects(self) -> list:
        """Collect all (oid, lon, lat) tuples in this subtree."""
        if self.is_leaf:
            return list(self.objects)
        result = []
        for c in self.children:
            if c.n_objects > 0:
                result.extend(c.all_objects())
        return result

    def nodes_at_level(self, target: int) -> list:
        """
        Return nodes at the given tree level.
        Leaf nodes above the target level count themselves (no further splitting).
        Skips empty subtrees.
        """
        if self.n_objects == 0:
            return []
        if self.level == target or self.is_leaf:
            return [self]
        result = []
        for c in self.children:
            result.extend(c.nodes_at_level(target))
        return result


def _build_qnode(items: list, mbr: MBR, level: int,
                 split_thresh: int, lmin: int, lmax: int) -> QNode:
    """
    Recursively build a quadtree node.
    items: list of (oid, lon, lat)
    Splits if: below lmin (forced), OR below lmax and over split_thresh objects.
    """
    node = QNode(mbr, level)
    node.n_objects = len(items)
    should_split = (level < lmin) or (level < lmax and len(items) > split_thresh)

    if not should_split or not items:
        node.objects = list(items)
        return node

    cx = (mbr.xmin + mbr.xmax) / 2.0
    cy = (mbr.ymin + mbr.ymax) / 2.0

    # Assign each object to one of 4 quadrants (no boundary duplicates)
    # Bit 1 (value 2): x >= cx → east; Bit 0 (value 1): y >= cy → north
    buckets: list = [[], [], [], []]
    for item in items:
        _, lon, lat = item
        q = (2 if lon >= cx else 0) | (1 if lat >= cy else 0)
        buckets[q].append(item)

    child_mbrs = [
        MBR(mbr.xmin, mbr.ymin, cx, cy),          # q=0: SW
        MBR(mbr.xmin, cy,        cx, mbr.ymax),    # q=1: NW
        MBR(cx,       mbr.ymin,  mbr.xmax, cy),    # q=2: SE
        MBR(cx,       cy,        mbr.xmax, mbr.ymax),  # q=3: NE
    ]

    node.children = [
        _build_qnode(buckets[i], child_mbrs[i], level + 1, split_thresh, lmin, lmax)
        for i in range(4)
    ]
    return node


# ─── Linear Quadtree (per keyword) ───────────────────────────────────────────

class LinearQuadtree:
    """Spatial index for a single keyword."""

    def __init__(self, kw: str, items: list, space: MBR,
                 split_thresh: int, lmin: int, lmax: int):
        self.kw = kw
        self.lmax = lmax
        self.root = _build_qnode(items, space, 0, split_thresh, lmin, lmax)

    def nodes_at_level(self, level: int) -> list:
        return self.root.nodes_at_level(level)

    def all_objects(self) -> list:
        return self.root.all_objects()


# ─── IL-Quadtree (Inverted Linear Quadtree) ───────────────────────────────────

class ILQuadtree:
    """
    IL-Quadtree: one LinearQuadtree per keyword.
    Combines advantages of Inverted R-tree and IR2-tree (Section 3.2).
    """

    def __init__(self, objects: dict,
                 split_thresh: int = 64, lmin: int = 8, lmax: int = 15):
        self.lmax = lmax
        self.trees: dict = {}

        if not objects:
            return

        # Global bounding box (shared across all keyword trees for consistent MBRs)
        lons = [o["lon"] for o in objects.values()]
        lats = [o["lat"] for o in objects.values()]
        eps = 1e-9
        space = MBR(min(lons) - eps, min(lats) - eps,
                    max(lons) + eps, max(lats) + eps)

        # Group objects by keyword
        kw_map: dict = defaultdict(list)
        for oid, obj in objects.items():
            for kw in obj["keywords"]:
                kw_map[kw].append((oid, obj["lon"], obj["lat"]))

        for kw, items in kw_map.items():
            self.trees[kw] = LinearQuadtree(kw, items, space, split_thresh, lmin, lmax)

    def get(self, kw: str) -> Optional[LinearQuadtree]:
        return self.trees.get(kw)


# ─── N-Match Check (Definition 4) ────────────────────────────────────────────

def _is_n_match(ni: QNode, nj: QNode,
                lo: float, hi: float, flag1: bool, flag2: bool,
                all_nj: list, all_ni: list) -> bool:
    """
    Check if (ni, nj) is an n-match for an edge with distance [lo, hi] and signs.

    Case vi–vj (inclusive): dmin(bi, bj) <= hi AND dmax(bi, bj) >= lo
    Case vi→vj (flag1): above + no n'_j (≠nj) with dmax(bi, b'j) < lo
    Case vj→vi (flag2): above + no n'_i (≠ni) with dmax(bj, b'i) < lo
    Case vi↔vj: both exclusion checks
    """
    bi, bj = ni.mbr, nj.mbr

    if bi.dmin(bj) > hi:
        return False
    if bi.dmax(bj) < lo:
        return False

    # vi→vj exclusion: no other nj-side node guarantees all bi objects violate lo
    if flag1 and lo > 0:
        for npj in all_nj:
            if npj is nj:
                continue
            if bi.dmax(npj.mbr) < lo:
                return False

    # vj→vi exclusion: symmetric
    if flag2 and lo > 0:
        for npi in all_ni:
            if npi is ni:
                continue
            if bj.dmax(npi.mbr) < lo:
                return False

    return True


def _children_of(node: QNode) -> list:
    """Children of node, or [node] itself if it is a leaf."""
    return node.children if not node.is_leaf else [node]


# ─── N-Match Computation (Level by Level) ────────────────────────────────────

def _compute_n_matches_level(
    edge: dict,
    tree_i: LinearQuadtree,
    tree_j: LinearQuadtree,
    level: int,
    prev_nm: Optional[list],  # (QNode_i, QNode_j) pairs from level-1
    si: set,                  # S-set for vi (empty = unconstrained)
    sj: set,                  # S-set for vj
) -> list:
    """
    Compute n-matches for one edge at one tree level.
    Returns list of (QNode_i, QNode_j) pairs.
    """
    lo, hi = edge["lower"], edge["upper"]
    flag1, flag2 = edge["flag1"], edge["flag2"]

    # Determine candidate node sets
    if prev_nm is None:
        # Level 1: start from all nodes at this level
        cands_i = tree_i.nodes_at_level(level)
        cands_j = tree_j.nodes_at_level(level)
    else:
        # Expand previous n-match nodes to their children
        seen_i: set = set()
        seen_j: set = set()
        cands_i, cands_j = [], []
        for ni, nj in prev_nm:
            for c in _children_of(ni):
                pk = id(c)
                if pk not in seen_i:
                    cands_i.append(c)
                    seen_i.add(pk)
            for c in _children_of(nj):
                pk = id(c)
                if pk not in seen_j:
                    cands_j.append(c)
                    seen_j.add(pk)

    # S-set pruning: remove nodes not in S (if S is initialized)
    if si:
        cands_i = [n for n in cands_i if n in si]
    # Paper prunes vj side only for mutual-inclusion edges (symmetric constraint)
    is_incl = not flag1 and not flag2
    if is_incl and sj:
        cands_j = [n for n in cands_j if n in sj]

    if not cands_i or not cands_j:
        return []

    # For exclusion check: ALL nodes at this level (not just candidates)
    all_nj = tree_j.nodes_at_level(level) if flag1 and lo > 0 else []
    all_ni = tree_i.nodes_at_level(level) if flag2 and lo > 0 else []

    result = []
    for ni in cands_i:
        for nj in cands_j:
            if _is_n_match(ni, nj, lo, hi, flag1, flag2, all_nj, all_ni):
                result.append((ni, nj))
    return result


# ─── Ordering Heuristics ──────────────────────────────────────────────────────

def _n_match_order(pattern_edges: list, nm_counts: dict) -> list:
    """
    Heuristic order for n-match computation (Observations 1 & 2, Section 4.2.2):
    1. Exclusive edges first (more constraints → fewer n-matches).
    2. Within each group: ascending n-match count from previous level.
    """
    excl = [i for i, e in enumerate(pattern_edges) if e["flag1"] or e["flag2"]]
    incl = [i for i, e in enumerate(pattern_edges) if not e["flag1"] and not e["flag2"]]
    excl.sort(key=lambda i: nm_counts.get(i, 0))
    incl.sort(key=lambda i: nm_counts.get(i, 0))
    return excl + incl


def _identify_skip_edges(pattern_edges: list, order: list) -> set:
    """
    Identify skip-edges (Section 4.3): mutual-inclusion edges that form a cycle
    in the subgraph built by processing `order`.

    Skip-edges don't need explicit e-match computation; their distance constraint
    is checked inline during the join phase.
    """
    # Collect all unique keywords as vertices for union-find
    kws = sorted(
        {e["keyword_a"] for e in pattern_edges} |
        {e["keyword_b"] for e in pattern_edges}
    )
    kw_id = {kw: i for i, kw in enumerate(kws)}
    parent = list(range(len(kws)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    skips: set = set()
    for idx in order:
        e = pattern_edges[idx]
        va = kw_id[e["keyword_a"]]
        vb = kw_id[e["keyword_b"]]
        is_incl = not e["flag1"] and not e["flag2"]
        if is_incl and find(va) == find(vb):
            skips.add(idx)
        else:
            union(va, vb)
    return skips


def _join_order(pattern_edges: list, e_matches: dict,
                nm_counts: dict, skips: set) -> list:
    """
    Join order (Section 4.4):
    - Non-skip edges first: connected ordering (BFS, ascending e-match count).
    - Skip edges last: ascending n-match count.
    """
    non_skip = [i for i in range(len(pattern_edges)) if i not in skips]

    # Connected ordering for non-skip edges (MPJOrder strategy)
    remaining = list(non_skip)
    ordered: list = []
    covered: set = set()

    while remaining:
        best_idx = None
        best_conn = False
        best_size = float('inf')

        for i in remaining:
            e = pattern_edges[i]
            conn = e["keyword_a"] in covered or e["keyword_b"] in covered
            size = len(e_matches.get(i, []))
            if (not best_conn and conn) or (conn == best_conn and size < best_size):
                best_idx = i
                best_conn = conn
                best_size = size

        ordered.append(best_idx)
        remaining.remove(best_idx)
        e = pattern_edges[best_idx]
        covered.add(e["keyword_a"])
        covered.add(e["keyword_b"])

    skip_list = sorted(list(skips), key=lambda i: nm_counts.get(i, 0))
    return ordered + skip_list


# ─── E-Match Computation ──────────────────────────────────────────────────────

def _obj_dist(a: tuple, b: tuple) -> float:
    """Euclidean distance between two (oid, lon, lat) tuples."""
    return math.hypot(a[1] - b[1], a[2] - b[2])


def _compute_e_matches(
    edge: dict,
    tree_i: LinearQuadtree,
    tree_j: LinearQuadtree,
    final_nm: list,
) -> list:
    """
    Compute e-matches (object pairs) for one non-skip edge.

    Objects come from leaf nodes of the final n-match level. Sign constraints
    are checked against ALL objects with the respective keyword (not just candidates).

    Returns list of (oid_a, oid_b) pairs.
    """
    lo, hi = edge["lower"], edge["upper"]
    flag1, flag2 = edge["flag1"], edge["flag2"]

    # Collect candidate objects from n-match leaf nodes
    if final_nm:
        seen_i: set = set()
        seen_j: set = set()
        objs_i, objs_j = [], []
        for ni, nj in final_nm:
            for o in ni.all_objects():
                if o[0] not in seen_i:
                    objs_i.append(o)
                    seen_i.add(o[0])
            for o in nj.all_objects():
                if o[0] not in seen_j:
                    objs_j.append(o)
                    seen_j.add(o[0])
    else:
        # Fallback: use all objects (shouldn't happen in normal execution)
        objs_i = tree_i.all_objects()
        objs_j = tree_j.all_objects()

    # Full keyword sets for sign constraint verification
    all_j = tree_j.all_objects() if flag1 and lo > 0 else []
    all_i = tree_i.all_objects() if flag2 and lo > 0 else []

    # Pre-compute excluded object sets (vectorised for performance)
    # excl_i: oid_a values that have an object of kw_b within lo → violates vi→vj
    excl_i: set = set()
    if flag1 and lo > 0:
        for oa in objs_i:
            for ob in all_j:
                if ob[0] != oa[0] and _obj_dist(oa, ob) < lo:
                    excl_i.add(oa[0])
                    break

    # excl_j: oid_b values that have an object of kw_a within lo → violates vj→vi
    excl_j: set = set()
    if flag2 and lo > 0:
        for ob in objs_j:
            for oa in all_i:
                if oa[0] != ob[0] and _obj_dist(ob, oa) < lo:
                    excl_j.add(ob[0])
                    break

    result = []
    for oa in objs_i:
        if oa[0] in excl_i:
            continue
        for ob in objs_j:
            if ob[0] == oa[0] or ob[0] in excl_j:
                continue
            d = _obj_dist(oa, ob)
            if lo <= d <= hi:
                result.append((oa[0], ob[0]))

    return result


# ─── Join Phase ───────────────────────────────────────────────────────────────

def _join(
    pattern_edges: list,
    e_matches: dict,
    order: list,
    skips: set,
    objects: dict,
    max_matches: int,
) -> list:
    """
    Backtracking join over e-match lists (Section 4.4).

    Assignment: {keyword: oid}. used_oids ensures no object is used twice.
    Skip-edges check the distance constraint inline (no e-match list needed).
    Backward edges (both endpoints already bound) are verified via pair_sets.
    """
    results: list = []
    if not order:
        return results

    # Build pair sets for O(1) backward-edge lookup
    pair_sets = {
        i: {(a, b) for a, b in e_matches.get(i, [])}
        for i in range(len(pattern_edges))
    }

    def bt(step: int, assignment: dict, used_oids: set) -> None:
        if max_matches and len(results) >= max_matches:
            return
        if step == len(order):
            results.append(dict(assignment))
            return

        eidx = order[step]
        edge = pattern_edges[eidx]
        ka, kb = edge["keyword_a"], edge["keyword_b"]
        ka_bound = ka in assignment
        kb_bound = kb in assignment

        if eidx in skips:
            # Both keywords must be bound; check distance constraint only
            if ka_bound and kb_bound:
                oa = objects[assignment[ka]]
                ob = objects[assignment[kb]]
                d = math.hypot(oa["lon"] - ob["lon"], oa["lat"] - ob["lat"])
                if edge["lower"] <= d <= edge["upper"]:
                    bt(step + 1, assignment, used_oids)
            else:
                # Skip-edge keywords not yet bound — should not happen with correct
                # join order (non-skip spanning tree is processed first).
                bt(step + 1, assignment, used_oids)
            return

        # Backward edge: both keywords already bound — just verify pair exists
        if ka_bound and kb_bound:
            if (assignment[ka], assignment[kb]) in pair_sets[eidx]:
                bt(step + 1, assignment, used_oids)
            return

        for oa_id, ob_id in e_matches.get(eidx, []):
            if ka_bound and assignment[ka] != oa_id:
                continue
            if kb_bound and assignment[kb] != ob_id:
                continue
            # Prevent the same object from being used for two different keywords
            if oa_id in used_oids and assignment.get(ka) != oa_id:
                continue
            if ob_id in used_oids and assignment.get(kb) != ob_id:
                continue

            added_ka = not ka_bound
            added_kb = not kb_bound
            added_oa = oa_id not in used_oids
            added_ob = ob_id not in used_oids

            if added_ka: assignment[ka] = oa_id
            if added_kb: assignment[kb] = ob_id
            if added_oa: used_oids.add(oa_id)
            if added_ob: used_oids.add(ob_id)

            bt(step + 1, assignment, used_oids)

            if added_ka: del assignment[ka]
            if added_kb: del assignment[kb]
            if added_oa: used_oids.discard(oa_id)
            if added_ob: used_oids.discard(ob_id)

    bt(0, {}, set())
    return results


# ─── ESPM Entry Points ────────────────────────────────────────────────────────

def build_ilq(objects: dict,
              split_thresh: int = 64, lmin: int = 8, lmax: int = 15) -> ILQuadtree:
    """Build the IL-Quadtree index from the objects dictionary."""
    return ILQuadtree(objects, split_thresh, lmin, lmax)


def run_espm(
    objects: dict,
    pattern_edges: list,
    ilq: ILQuadtree,
    max_matches: int = 0,
    verbose: bool = True,
) -> list:
    """
    ESPM: Efficient Spatial Pattern Matching (Algorithm 1, Section 4).

    Args:
        objects:       {oid: {"lon": float, "lat": float, "keywords": set}}
        pattern_edges: list of edge dicts with keyword_a/b, lower, upper, flag1/2
        ilq:           pre-built ILQuadtree (call build_ilq() once per dataset)
        max_matches:   stop after this many matches; 0 = unlimited
        verbose:       print per-level and per-edge progress

    Returns:
        List of assignment dicts {keyword: oid}, one per match.
        Same format as run_msj() in paper1/spm.py.
    """
    # Step 0: apply bounded-pattern tightening; verify all keywords present
    tightened, feasible = compute_bounded_pattern(pattern_edges)
    if not feasible:
        if verbose:
            print("  Pattern is infeasible (bounded-pattern detected empty interval).")
        return []

    if verbose:
        for orig, tight in zip(pattern_edges, tightened):
            du = orig["upper"] - tight["upper"]
            dl = tight["lower"] - orig["lower"]
            if du > 1e-12 or dl > 1e-12:
                sign = ("->" if orig["flag1"] and not orig["flag2"] else
                        "<-" if not orig["flag1"] and orig["flag2"] else
                        "<>" if orig["flag1"] and orig["flag2"] else "--")
                print(f"  Bounded '{orig['keyword_a']}' {sign} '{orig['keyword_b']}': "
                      f"[{orig['lower']:.6f},{orig['upper']:.6f}] → "
                      f"[{tight['lower']:.6f},{tight['upper']:.6f}]")

    pattern_edges = tightened

    for edge in pattern_edges:
        for kw in (edge["keyword_a"], edge["keyword_b"]):
            if ilq.get(kw) is None:
                if verbose:
                    print(f"  Keyword '{kw}' not in index — no matches.")
                return []

    n_edges = len(pattern_edges)
    L = ilq.lmax

    # n_prev[eidx] = list of (QNode_i, QNode_j) from the previous level
    n_prev: dict = {i: None for i in range(n_edges)}
    nm_counts: dict = {i: 0 for i in range(n_edges)}

    # ── Step 1: N-matches, level by level ─────────────────────────────────────
    for level in range(1, L + 1):
        order = _n_match_order(pattern_edges, nm_counts)

        # S-sets: keyword → set of QNode (empty = not yet initialized)
        s: dict = defaultdict(set)
        s_init: dict = defaultdict(bool)

        n_curr: dict = {}

        for eidx in order:
            edge = pattern_edges[eidx]
            ka, kb = edge["keyword_a"], edge["keyword_b"]

            si = s[ka] if s_init[ka] else set()
            sj = s[kb] if s_init[kb] else set()

            matches = _compute_n_matches_level(
                edge, ilq.get(ka), ilq.get(kb),
                level, n_prev[eidx], si, sj,
            )

            if not matches:
                if verbose:
                    print(f"  Level {level}, edge {eidx} "
                          f"({ka}–{kb}): 0 n-matches — terminating early.")
                return []

            n_curr[eidx] = matches

            # Update S-sets for both keywords (intersection with new n-match nodes)
            ni_set = {ni for ni, _ in matches}
            nj_set = {nj for _, nj in matches}

            if s_init[ka]:
                s[ka] &= ni_set
            else:
                s[ka] = ni_set
                s_init[ka] = True

            if s_init[kb]:
                s[kb] &= nj_set
            else:
                s[kb] = nj_set
                s_init[kb] = True

            if not s[ka] or not s[kb]:
                if verbose:
                    print(f"  Level {level}: S-set emptied — no matches.")
                return []

        n_prev = n_curr
        nm_counts = {i: len(m) for i, m in n_prev.items()}

        if verbose:
            total = sum(nm_counts.values())
            print(f"  Level {level:2d}: {total:,} total n-match node pairs")

    # ── Step 2: E-matches ──────────────────────────────────────────────────────
    init_order = sorted(range(n_edges), key=lambda i: nm_counts.get(i, 0))
    skips = _identify_skip_edges(pattern_edges, init_order)

    e_matches: dict = {}
    e_counts: dict = {}

    for eidx in init_order:
        edge = pattern_edges[eidx]
        ka, kb = edge["keyword_a"], edge["keyword_b"]
        sign = ("->" if edge["flag1"] and not edge["flag2"] else
                "<-" if not edge["flag1"] and edge["flag2"] else
                "<>" if edge["flag1"] and edge["flag2"] else "--")

        if eidx in skips:
            e_matches[eidx] = []
            e_counts[eidx] = 0
            if verbose:
                print(f"  Edge {eidx} '{ka}' {sign} '{kb}': skip-edge "
                      f"(distance checked during join)")
            continue

        pairs = _compute_e_matches(
            edge, ilq.get(ka), ilq.get(kb), n_prev.get(eidx, [])
        )

        if verbose:
            print(f"  Edge {eidx} '{ka}' {sign} '{kb}': {len(pairs):,} e-matches")

        if not pairs:
            if verbose:
                print("  -> 0 e-matches — no matches for this pattern.")
            return []

        e_matches[eidx] = pairs
        e_counts[eidx] = len(pairs)

    # ── Step 3: Join ──────────────────────────────────────────────────────────
    jorder = _join_order(pattern_edges, e_matches, nm_counts, skips)
    return _join(pattern_edges, e_matches, jorder, skips, objects, max_matches)
