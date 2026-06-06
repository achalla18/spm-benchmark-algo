import math
from collections import defaultdict


# ── DATA LOADING ──────────────────────────────────────────────────────────────

def load_locations(loc_path: str) -> dict:
    """
    Read UK/loc → {object_id: (lon, lat)}.
    Line format: object_id,longitude,latitude
    """
    locations = {}
    with open(loc_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            oid = int(parts[0])
            locations[oid] = (float(parts[1]), float(parts[2]))
    return locations


def load_documents(doc_path: str) -> dict:
    """
    Read UK/doc → {object_id: set of keywords}.
    Line format: object_id,keyword1,keyword2,...
    """
    documents = {}
    with open(doc_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            oid = int(parts[0])
            keywords = {k.strip().lower() for k in parts[1:] if k.strip()}
            documents[oid] = keywords
    return documents


def load_objects(loc_path: str, doc_path: str) -> dict:
    """
    Combine location and keyword data.
    Returns: {object_id: {"lon": float, "lat": float, "keywords": set[str]}}
    """
    locations = load_locations(loc_path)
    documents = load_documents(doc_path)

    objects = {}
    for oid, (lon, lat) in locations.items():
        objects[oid] = {"lon": lon, "lat": lat, "keywords": documents.get(oid, set())}

    orphans = set(documents) - set(locations)
    if orphans:
        print(f"Warning: {len(orphans)} objects in doc but not loc (skipped).")

    return objects


def load_patterns(pattern_path: str) -> list:
    """
    Read UK/pattern → list of patterns.
    Each pattern is a list of edge dicts.

    File format:
      - Edges within one pattern appear on CONSECUTIVE lines.
      - Patterns are separated by blank/space-only lines.

    Each edge line: keyword_a keyword_b lower upper flag1 flag2

    Flag semantics (Section II of the paper):
      flag1=False, flag2=False → vi – vj  (mutual inclusion)
      flag1=True,  flag2=False → vi → vj  (vi excludes vj)
      flag1=False, flag2=True  → vi ← vj  (vj excludes vi)
      flag1=True,  flag2=True  → vi ↔ vj  (mutual exclusion)

    Exclusion: if vi → vj, no object with keyword_b may exist within
    distance [lower] of the object matched with vi.
    """
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
                print(f"Warning: malformed edge line: {repr(line.rstrip())}")
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


# ── INVERTED INDEX ────────────────────────────────────────────────────────────

def build_inverted_index(objects: dict) -> dict:
    """keyword → sorted list of object_ids that have that keyword."""
    index = defaultdict(list)
    for oid, obj in objects.items():
        for kw in obj["keywords"]:
            index[kw].append(oid)
    return {kw: sorted(ids) for kw, ids in index.items()}


# ── DISTANCE ──────────────────────────────────────────────────────────────────

def distance(obj1: dict, obj2: dict) -> float:
    """
    Raw Euclidean distance in coordinate degrees.
    The paper uses Euclidean distance (Section II). The UK dataset stores
    pattern distances in coordinate space (not km), so this matches exactly.
    Use dist_mode='euclidean' (the default) to select this function.
    """
    dlon = obj1["lon"] - obj2["lon"]
    dlat = obj1["lat"] - obj2["lat"]
    return math.sqrt(dlon * dlon + dlat * dlat)


def haversine_km(obj1: dict, obj2: dict) -> float:
    """
    Great-circle distance in kilometres (Haversine formula).
    Use dist_mode='haversine' to select this function.
    Appropriate when pattern distance intervals are specified in km,
    e.g. patterns built from OSM data where users think in metres/km.
    """
    R = 6371.0
    lat1 = math.radians(obj1["lat"])
    lat2 = math.radians(obj2["lat"])
    dlat = lat2 - lat1
    dlon = math.radians(obj2["lon"] - obj1["lon"])
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# Approximate km per degree of latitude (used to convert grid radii).
# Grid cells are always stored in coordinate degrees; when distance values
# are in km we divide by this factor to get the equivalent degree radius.
_KM_PER_DEG = 111.32


def _dist_fn(dist_mode: str):
    """Return the distance function for the given mode string."""
    if dist_mode == "haversine":
        return haversine_km
    return distance


def _to_deg(value: float, dist_mode: str) -> float:
    """Convert a distance value to degrees for grid-cell radius queries."""
    if dist_mode == "haversine":
        return value / _KM_PER_DEG
    return value


# ── BOUNDED DISTANCES (shared by MPJ and MSJ) ─────────────────────────────────

def _compute_bounds_matrix(pattern_edges: list) -> tuple:
    """
    Floyd-Warshall + iterative triangle-inequality propagation for all keyword pairs.

    Upper bound (Lemma 4):
        u_hat[i][j] = min over k of (u[i][k] + u[k][j])

    Lower bound (Lemma 5):
        l_hat[i][j] = max over k of max(0, l[k][j]-u[i][k], l[i][k]-u[k][j])

    Returns (kw_list, kw_idx, l_matrix, u_matrix).
    kw_list  : sorted list of all keyword strings in the pattern.
    kw_idx   : dict mapping keyword -> row/col index in the matrices.
    l_matrix : tight lower-bound distances between all pairs.
    u_matrix : tight upper-bound distances between all pairs.
    """
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

    # Floyd-Warshall for upper bounds (Lemma 4)
    for k in range(n):
        for i in range(n):
            if u[i][k] == INF:
                continue
            for j in range(n):
                if u[k][j] < INF:
                    u[i][j] = min(u[i][j], u[i][k] + u[k][j])

    # Iterative lower-bound tightening (Lemma 5), at most n passes
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

    return kws, idx, l, u


# ── BOUNDED PATTERN (Section IV.A) ────────────────────────────────────────────

def compute_bounded_pattern(pattern_edges: list) -> tuple:
    """
    Tighten each edge's distance interval using the bounded pattern.

    For each existing edge (vi, vj):
      - new_upper = min(original_upper, u_hat[i][j])   (always applied)
      - new_lower = max(original_lower, l_hat[i][j])   (inclusion edges only;
          exclusion edge lowers are NOT tightened — Section IV.A, criterion ⑤)

    Returns (tightened_edges, is_feasible).
    is_feasible=False means the pattern provably has no matches.
    """
    if len(pattern_edges) < 2:
        return list(pattern_edges), True

    _, idx, l, u = _compute_bounds_matrix(pattern_edges)
    INF = float('inf')

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


# ── GRID INDEX ────────────────────────────────────────────────────────────────

class GridIndex:
    """
    Uniform grid for fast radius queries.

    Divides the coordinate plane into square cells of `cell_size` degrees.
    A radius query inspects only the cells that could overlap a circle of
    that radius — a small (2*span+1)^2 block of cells rather than all objects.
    """

    def __init__(self, objects: dict, cell_size: float):
        self.cell_size = cell_size
        self.grid = defaultdict(list)
        for oid, obj in objects.items():
            cx = math.floor(obj["lon"] / cell_size)
            cy = math.floor(obj["lat"] / cell_size)
            self.grid[(cx, cy)].append(oid)

    def query_candidates(self, lon: float, lat: float, radius: float) -> list:
        """
        All object IDs in cells that MAY be within `radius` of (lon, lat).
        Exact distance check is still required after this call.
        """
        span = math.floor(radius / self.cell_size) + 1
        cx = math.floor(lon / self.cell_size)
        cy = math.floor(lat / self.cell_size)
        result = []
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                result.extend(self.grid.get((cx + dx, cy + dy), []))
        return result


# ── CANDIDATE PAIR FINDING ────────────────────────────────────────────────────

def find_candidate_pairs(objects: dict, inverted_index: dict, edge: dict,
                          grid: GridIndex = None,
                          dist_mode: str = "euclidean") -> list:
    """
    For one pattern edge, find all e-matches — pairs (ok, ol) such that:
      1. ok has keyword_a and ol has keyword_b.
      2. lower ≤ dist(ok, ol) ≤ upper.
      3. Exclusion constraints are satisfied (Section II):
           flag1=True: no object with keyword_b within [lower] of ok.
           flag2=True: no object with keyword_a within [lower] of ol.

    With grid=None: naive O(|A|·|B|). With GridIndex: grid-accelerated.
    """
    ka    = edge["keyword_a"]
    kb    = edge["keyword_b"]
    lower = edge["lower"]
    upper = edge["upper"]
    flag1 = edge["flag1"]
    flag2 = edge["flag2"]

    a_ids = inverted_index.get(ka, [])
    b_ids = inverted_index.get(kb, [])
    if not a_ids or not b_ids:
        return []

    b_set = set(b_ids)
    a_set = set(a_ids)

    # Choose distance function and convert edge bounds to degrees for grid queries.
    # The grid is always stored in coordinate degrees; haversine distances are in km.
    dfn        = _dist_fn(dist_mode)
    upper_deg  = _to_deg(upper, dist_mode)   # grid query radius for candidate pass
    lower_deg  = _to_deg(lower, dist_mode)   # grid query radius for exclusion pass

    # Precompute excluded objects for exclusion edges
    excluded_a: set = set()
    if flag1 and lower > 0:
        for aid in a_ids:
            a_obj = objects[aid]
            if grid is not None:
                for bid in grid.query_candidates(a_obj["lon"], a_obj["lat"], lower_deg):
                    if bid != aid and bid in b_set and dfn(a_obj, objects[bid]) < lower:
                        excluded_a.add(aid)
                        break
            else:
                for bid in b_ids:
                    if bid != aid and dfn(a_obj, objects[bid]) < lower:
                        excluded_a.add(aid)
                        break

    excluded_b: set = set()
    if flag2 and lower > 0:
        for bid in b_ids:
            b_obj = objects[bid]
            if grid is not None:
                for aid in grid.query_candidates(b_obj["lon"], b_obj["lat"], lower_deg):
                    if aid != bid and aid in a_set and dfn(b_obj, objects[aid]) < lower:
                        excluded_b.add(bid)
                        break
            else:
                for aid in a_ids:
                    if aid != bid and dfn(b_obj, objects[aid]) < lower:
                        excluded_b.add(bid)
                        break

    pairs = []
    if grid is not None:
        for aid in a_ids:
            if aid in excluded_a:
                continue
            a_obj = objects[aid]
            for bid in grid.query_candidates(a_obj["lon"], a_obj["lat"], upper_deg):
                if bid == aid or bid not in b_set or bid in excluded_b:
                    continue
                d = dfn(a_obj, objects[bid])
                if lower <= d <= upper:
                    pairs.append({"keyword_a": ka, "keyword_b": kb,
                                  "object_a": aid, "object_b": bid, "distance": d})
    else:
        for aid in a_ids:
            if aid in excluded_a:
                continue
            a_obj = objects[aid]
            for bid in b_ids:
                if bid == aid or bid in excluded_b:
                    continue
                d = dfn(a_obj, objects[bid])
                if lower <= d <= upper:
                    pairs.append({"keyword_a": ka, "keyword_b": kb,
                                  "object_a": aid, "object_b": bid, "distance": d})

    return pairs


# ── SHARED JOIN UTILITIES ─────────────────────────────────────────────────────

def _connected_join_order(edge_candidate_pairs: list) -> list:
    """
    Re-order (edge, candidates) for efficient backtracking.

    Follows MPJOrder's BFS strategy (Section III.B): each forward edge shares
    at least one keyword with the already-covered set, so partial assignments
    are extended rather than combined by Cartesian product.

    Priority: (1) connected first; (2) smallest candidate count among connected.
    """
    remaining = list(edge_candidate_pairs)
    ordered   = []
    covered: set = set()

    while remaining:
        best_idx  = 0
        best_conn = False
        best_size = float('inf')

        for i, (edge, cands) in enumerate(remaining):
            conn = edge["keyword_a"] in covered or edge["keyword_b"] in covered
            size = len(cands)
            if (not best_conn and conn) or (conn == best_conn and size < best_size):
                best_idx  = i
                best_conn = conn
                best_size = size

        edge, cands = remaining.pop(best_idx)
        covered.add(edge["keyword_a"])
        covered.add(edge["keyword_b"])
        ordered.append((edge, cands))

    return ordered


# ══════════════════════════════════════════════════════════════════════════════
# MPJ — Multi-Pair Join
# ══════════════════════════════════════════════════════════════════════════════

def join_mpj(pattern_edges: list, edge_candidates: list,
             max_matches: int = 20) -> list:
    """
    Backtracking join for MPJ.

    Processes edges in connected-first, size-ascending order.
    Backward edges (both vertices already assigned) use a pre-built pair-set
    for O(1) lookup instead of scanning the candidate list.
    """
    results = []
    by_size = sorted(zip(pattern_edges, edge_candidates), key=lambda x: len(x[1]))
    indexed = _connected_join_order(by_size)

    pair_sets = [
        {(p["object_a"], p["object_b"]) for p in cands}
        for _, cands in indexed
    ]

    def backtrack(i: int, assignment: dict, used_objects: set):
        if max_matches and len(results) >= max_matches:
            return
        if i == len(indexed):
            results.append(dict(assignment))
            return

        edge, candidates = indexed[i]
        ka = edge["keyword_a"]
        kb = edge["keyword_b"]

        if ka in assignment and kb in assignment:
            if (assignment[ka], assignment[kb]) in pair_sets[i]:
                backtrack(i + 1, assignment, used_objects)
            return

        for pair in candidates:
            a = pair["object_a"]
            b = pair["object_b"]
            if ka in assignment and assignment[ka] != a: continue
            if kb in assignment and assignment[kb] != b: continue
            if a in used_objects and assignment.get(ka) != a: continue
            if b in used_objects and assignment.get(kb) != b: continue

            added_ka = ka not in assignment
            added_kb = kb not in assignment
            added_a  = a not in used_objects
            added_b  = b not in used_objects
            if added_ka: assignment[ka] = a
            if added_kb: assignment[kb] = b
            if added_a:  used_objects.add(a)
            if added_b:  used_objects.add(b)

            backtrack(i + 1, assignment, used_objects)

            if added_ka: del assignment[ka]
            if added_kb: del assignment[kb]
            if added_a:  used_objects.discard(a)
            if added_b:  used_objects.discard(b)

    backtrack(0, {}, set())
    return results


def run_pattern(objects: dict, inverted_index: dict, pattern: list,
                grid: GridIndex = None, max_matches: int = 20,
                dist_mode: str = "euclidean") -> list:
    """
    MPJ (Multi-Pair Join) for one query pattern.

    Steps:
      1. Bounded pattern tightening (Section IV.A) — prune infeasible intervals.
      2. Generate candidate e-matches per edge.
      3. Backtracking join with connected-first edge ordering.

    dist_mode: 'euclidean' (pattern distances in degrees, default for Fang data)
               'haversine' (pattern distances in km, appropriate for OSM data)
    """
    tightened, feasible = compute_bounded_pattern(pattern)
    if not feasible:
        print("  Pattern is infeasible (bounded pattern detected empty interval).")
        return []

    for orig, tight in zip(pattern, tightened):
        du = orig["upper"] - tight["upper"]
        dl = tight["lower"] - orig["lower"]
        if du > 1e-12 or dl > 1e-12:
            print(f"  Bounded: '{orig['keyword_a']}'-'{orig['keyword_b']}' "
                  f"[{orig['lower']:.6f}, {orig['upper']:.6f}] -> "
                  f"[{tight['lower']:.6f}, {tight['upper']:.6f}]"
                  f"  (lower+{dl:.6f}, upper-{du:.6f})")

    edge_candidates = []
    for edge in tightened:
        sign = ("->" if edge["flag1"] and not edge["flag2"] else
                "<-" if not edge["flag1"] and edge["flag2"] else
                "<>" if edge["flag1"] and edge["flag2"] else "--")
        pairs = find_candidate_pairs(objects, inverted_index, edge,
                                     grid=grid, dist_mode=dist_mode)
        print(f"  Edge '{edge['keyword_a']}' {sign} '{edge['keyword_b']}': "
              f"{len(pairs):,} candidate pairs")
        if not pairs:
            print("  -> No candidates for this edge; pattern has no matches.")
            return []
        edge_candidates.append(pairs)

    return join_mpj(tightened, edge_candidates, max_matches=max_matches)


# ══════════════════════════════════════════════════════════════════════════════
# MSJ — Multi-Star Join  (Section IV of the paper)
# ══════════════════════════════════════════════════════════════════════════════

def star_pruning(pattern_edges: list, edge_candidates: list) -> list:
    """
    Remove candidate pairs where an endpoint has no e-match in some neighbor edge.

    Lemma 6 (Section IV.C): Object ok (matched with wi) must appear in at least
    one e-match for EVERY neighbor edge of vi.  If it fails for any one neighbor,
    ok can never appear in a full match → remove it from all candidate lists.

    Iterated until convergence because pruning one side can expose more pruning.
    """
    # keyword -> [(edge_index, 'a'|'b'), ...]
    kw_map: dict = defaultdict(list)
    for i, e in enumerate(pattern_edges):
        kw_map[e["keyword_a"]].append((i, 'a'))
        kw_map[e["keyword_b"]].append((i, 'b'))

    changed = True
    while changed:
        changed = False
        for kw, refs in kw_map.items():
            # Objects still valid for kw: must appear in ALL neighbor edges
            valid = None
            for ei, side in refs:
                objs = (
                    {p["object_a"] for p in edge_candidates[ei]} if side == 'a'
                    else {p["object_b"] for p in edge_candidates[ei]}
                )
                valid = objs if valid is None else valid & objs

            if valid is None:
                continue

            # Remove pairs where kw's object is not in the valid set
            for ei, side in refs:
                before = len(edge_candidates[ei])
                if side == 'a':
                    edge_candidates[ei] = [
                        p for p in edge_candidates[ei] if p["object_a"] in valid
                    ]
                else:
                    edge_candidates[ei] = [
                        p for p in edge_candidates[ei] if p["object_b"] in valid
                    ]
                if len(edge_candidates[ei]) < before:
                    changed = True

    return edge_candidates


def join_msj(pattern_edges: list, edge_candidates: list,
             kw_idx: dict, l_mat: list, u_mat: list,
             objects: dict, max_matches: int = 20,
             dist_mode: str = "euclidean") -> list:
    """
    MSJ backtracking join with anchor-pruning.

    Anchor-pruning (Section IV.C-D): when a new object oid_new is added for
    keyword kw_new, check its distance against ALL already-assigned objects
    using the FULL bounded distance matrix (l_mat / u_mat).  If any distance
    violates a bounded constraint, prune this partial match immediately — even
    before the corresponding edge is processed.

    Why this is correct: the bounded matrix entries are derived from the full
    pattern by triangle inequality. A partial match violating a bounded constraint
    cannot be extended to a valid full match, so discarding it is safe.
    """
    INF = float('inf')
    results = []

    by_size = sorted(zip(pattern_edges, edge_candidates), key=lambda x: len(x[1]))
    indexed = _connected_join_order(by_size)

    pair_sets = [
        {(p["object_a"], p["object_b"]) for p in cands}
        for _, cands in indexed
    ]

    dfn = _dist_fn(dist_mode)

    def anchor_ok(new_kw: str, new_oid: int, assignment: dict) -> bool:
        """
        Return False if new_oid violates any bounded distance constraint with
        an already-assigned object.  Only checks pairs where u_mat is finite
        (i.e., an implied constraint exists via the pattern graph).
        Uses the same distance function as candidate generation.
        """
        ni = kw_idx.get(new_kw)
        if ni is None:
            return True
        new_obj = objects[new_oid]
        for old_kw, old_oid in assignment.items():
            oi = kw_idx.get(old_kw)
            if oi is None:
                continue
            hi = u_mat[ni][oi]
            if hi == INF:
                continue
            lo = l_mat[ni][oi]
            d = dfn(new_obj, objects[old_oid])
            if d < lo - 1e-10 or d > hi + 1e-10:
                return False
        return True

    def backtrack(i: int, assignment: dict, used_objects: set):
        if max_matches and len(results) >= max_matches:
            return
        if i == len(indexed):
            results.append(dict(assignment))
            return

        edge, candidates = indexed[i]
        ka = edge["keyword_a"]
        kb = edge["keyword_b"]

        # Backward edge: both already assigned — just verify the pair exists
        if ka in assignment and kb in assignment:
            if (assignment[ka], assignment[kb]) in pair_sets[i]:
                backtrack(i + 1, assignment, used_objects)
            return

        for pair in candidates:
            a = pair["object_a"]
            b = pair["object_b"]

            # Consistency check
            if ka in assignment and assignment[ka] != a: continue
            if kb in assignment and assignment[kb] != b: continue
            if a in used_objects and assignment.get(ka) != a: continue
            if b in used_objects and assignment.get(kb) != b: continue

            # Anchor-pruning: check implied distances for newly introduced keywords
            if ka not in assignment and not anchor_ok(ka, a, assignment):
                continue
            if kb not in assignment and not anchor_ok(kb, b, assignment):
                continue

            added_ka = ka not in assignment
            added_kb = kb not in assignment
            added_a  = a not in used_objects
            added_b  = b not in used_objects
            if added_ka: assignment[ka] = a
            if added_kb: assignment[kb] = b
            if added_a:  used_objects.add(a)
            if added_b:  used_objects.add(b)

            backtrack(i + 1, assignment, used_objects)

            if added_ka: del assignment[ka]
            if added_kb: del assignment[kb]
            if added_a:  used_objects.discard(a)
            if added_b:  used_objects.discard(b)

    backtrack(0, {}, set())
    return results


def run_msj(objects: dict, inverted_index: dict, pattern: list,
            grid: GridIndex = None, max_matches: int = 20,
            dist_mode: str = "euclidean") -> list:
    """
    MSJ (Multi-Star Join) for one query pattern.

    Algorithm (Section IV):
      1. Bounded pattern tightening — shrink edge intervals via triangle inequality.
         Detects infeasible patterns early. (Section IV.A)
      2. Compute full bounded distance matrix for ALL keyword pairs.
         Used by anchor-pruning to check implied constraints during join.
      3. Generate candidate e-matches per edge (same as MPJ).
      4. Star-pruning — remove objects lacking e-matches in any neighbor edge.
         Iterated until convergence. (Section IV.C, Lemma 6)
      5. Backtracking join with anchor-pruning — check bounded distances against
         all already-assigned objects when extending a partial match. (Section IV.D)

    dist_mode: 'euclidean' (default, Fang patterns in degrees)
               'haversine' (OSM patterns in km)
    """
    # Step 1: Bounded pattern tightening
    tightened, feasible = compute_bounded_pattern(pattern)
    if not feasible:
        print("  Pattern is infeasible (bounded pattern detected empty interval).")
        return []

    for orig, tight in zip(pattern, tightened):
        du = orig["upper"] - tight["upper"]
        dl = tight["lower"] - orig["lower"]
        if du > 1e-12 or dl > 1e-12:
            print(f"  Bounded: '{orig['keyword_a']}'-'{orig['keyword_b']}' "
                  f"[{orig['lower']:.6f}, {orig['upper']:.6f}] -> "
                  f"[{tight['lower']:.6f}, {tight['upper']:.6f}]"
                  f"  (lower+{dl:.6f}, upper-{du:.6f})")

    # Step 2: Full bounded distance matrix (used in anchor-pruning)
    # Called on the tightened edges so anchor checks use the tightest possible bounds.
    _, kw_idx, l_mat, u_mat = _compute_bounds_matrix(tightened)

    # Step 3: Candidate generation
    edge_candidates = []
    for edge in tightened:
        sign = ("->" if edge["flag1"] and not edge["flag2"] else
                "<-" if not edge["flag1"] and edge["flag2"] else
                "<>" if edge["flag1"] and edge["flag2"] else "--")
        pairs = find_candidate_pairs(objects, inverted_index, edge,
                                     grid=grid, dist_mode=dist_mode)
        print(f"  Edge '{edge['keyword_a']}' {sign} '{edge['keyword_b']}': "
              f"{len(pairs):,} candidate pairs")
        if not pairs:
            print("  -> No candidates for this edge; pattern has no matches.")
            return []
        edge_candidates.append(pairs)

    total_before = sum(len(c) for c in edge_candidates)

    # Step 4: Star-pruning
    edge_candidates = star_pruning(tightened, edge_candidates)
    total_after = sum(len(c) for c in edge_candidates)

    if total_after == 0:
        print("  -> All candidates pruned by star-pruning; pattern has no matches.")
        return []

    if total_after < total_before:
        reduction = (total_before - total_after) / total_before * 100
        print(f"  Star-pruning: {total_before:,} -> {total_after:,} candidates "
              f"({reduction:.1f}% pruned)")

    if any(len(c) == 0 for c in edge_candidates):
        print("  -> No candidates for some edge after star-pruning.")
        return []

    # Step 5: Join with anchor-pruning
    return join_msj(tightened, edge_candidates, kw_idx, l_mat, u_mat,
                    objects, max_matches=max_matches, dist_mode=dist_mode)
