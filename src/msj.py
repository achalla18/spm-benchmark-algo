from common import build_inverted_index, full_match_satisfies, keywords_in_pattern, stop_now


def run_msj(objects, pattern, max_matches=20):
    index = build_inverted_index(objects)
    keywords = keywords_in_pattern(pattern)
    candidates = {kw: index.get(kw, []) for kw in keywords}

    if any(len(ids) == 0 for ids in candidates.values()):
        return []

    order = sorted(keywords, key=lambda kw: len(candidates[kw]))
    matches = []

    def partial_ok(assignment):
        for edge in pattern:
            a = edge["keyword_a"]
            b = edge["keyword_b"]
            if a in assignment and b in assignment:
                if not full_match_satisfies(objects, index, [edge], assignment):
                    return False
        return True

    def backtrack(pos, assignment, used):
        if stop_now(matches, max_matches):
            return
        if pos == len(order):
            if full_match_satisfies(objects, index, pattern, assignment):
                matches.append(dict(assignment))
            return

        kw = order[pos]
        for oid in candidates[kw]:
            if oid in used:
                continue
            assignment[kw] = oid
            used.add(oid)

            if partial_ok(assignment):
                backtrack(pos + 1, assignment, used)

            used.remove(oid)
            del assignment[kw]

    backtrack(0, {}, set())
    return matches
