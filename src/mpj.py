from common import build_inverted_index, pair_satisfies, stop_now


def _edge_pairs(objects, index, edge):
    pairs = []
    for oid_a in index.get(edge["keyword_a"], []):
        for oid_b in index.get(edge["keyword_b"], []):
            if pair_satisfies(objects, index, edge, oid_a, oid_b):
                pairs.append((oid_a, oid_b))
    return pairs


def run_mpj(objects, pattern, max_matches=20):
    index = build_inverted_index(objects)
    edge_pairs = []

    for edge in pattern:
        pairs = _edge_pairs(objects, index, edge)
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
