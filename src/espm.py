import math
from collections import defaultdict

from common import build_inverted_index, distance, pair_satisfies, stop_now


class GridIndex:
    def __init__(self, objects, cell_size):
        self.objects = objects
        self.cell_size = max(cell_size, 1e-9)
        self.cells = defaultdict(list)
        for oid, obj in objects.items():
            self.cells[self._cell(obj["lon"], obj["lat"])].append(oid)

    def _cell(self, lon, lat):
        return (math.floor(lon / self.cell_size), math.floor(lat / self.cell_size))

    def around(self, lon, lat, radius):
        cx, cy = self._cell(lon, lat)
        span = int(math.ceil(radius / self.cell_size)) + 1
        result = []
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                result.extend(self.cells.get((cx + dx, cy + dy), []))
        return result


def _cell_size(pattern):
    uppers = [edge["upper"] for edge in pattern if edge["upper"] > 0]
    if not uppers:
        return 0.001
    uppers.sort()
    return uppers[len(uppers) // 2]


def _indexed_pairs(objects, index, grid, edge):
    pairs = []
    a_ids = index.get(edge["keyword_a"], [])
    b_set = set(index.get(edge["keyword_b"], []))

    for oid_a in a_ids:
        obj_a = objects[oid_a]
        nearby = grid.around(obj_a["lon"], obj_a["lat"], edge["upper"])
        for oid_b in nearby:
            if oid_b in b_set and pair_satisfies(objects, index, edge, oid_a, oid_b):
                pairs.append((oid_a, oid_b))
    return pairs


def run_espm(objects, pattern, max_matches=20):
    index = build_inverted_index(objects)
    grid = GridIndex(objects, _cell_size(pattern))
    edge_pairs = []

    for edge in pattern:
        pairs = _indexed_pairs(objects, index, grid, edge)
        if not pairs:
            return []
        edge_pairs.append((edge, pairs))

    edge_pairs.sort(key=lambda item: len(item[1]))
    matches = []

    def backtrack(pos, assignment, used):
        if stop_now(matches, max_matches):
            return
        if pos == len(edge_pairs):
            matches.append(dict(assignment))
            return

        edge, pairs = edge_pairs[pos]
        ka = edge["keyword_a"]
        kb = edge["keyword_b"]

        for oid_a, oid_b in pairs:
            if ka in assignment and assignment[ka] != oid_a:
                continue
            if kb in assignment and assignment[kb] != oid_b:
                continue
            if ka not in assignment and oid_a in used:
                continue
            if kb not in assignment and oid_b in used:
                continue

            added = []
            if ka not in assignment:
                assignment[ka] = oid_a
                used.add(oid_a)
                added.append((ka, oid_a))
            if kb not in assignment:
                assignment[kb] = oid_b
                used.add(oid_b)
                added.append((kb, oid_b))

            backtrack(pos + 1, assignment, used)

            for kw, oid in reversed(added):
                del assignment[kw]
                used.remove(oid)

    backtrack(0, {}, set())
    return matches
