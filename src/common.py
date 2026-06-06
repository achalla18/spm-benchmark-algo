import math
from collections import defaultdict


def load_locations(path):
    locations = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            oid, lon, lat = line.split(",")[:3]
            locations[int(oid)] = (float(lon), float(lat))
    return locations


def load_documents(path):
    documents = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            documents[int(parts[0])] = {p.strip().lower() for p in parts[1:] if p.strip()}
    return documents


def load_objects(loc_path, doc_path):
    locations = load_locations(loc_path)
    documents = load_documents(doc_path)
    objects = {}
    for oid, (lon, lat) in locations.items():
        objects[oid] = {
            "lon": lon,
            "lat": lat,
            "keywords": documents.get(oid, set()),
        }
    return objects


def load_patterns(path):
    patterns = []
    current = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                if current:
                    patterns.append(current)
                    current = []
                continue

            a, b, lower, upper, flag1, flag2 = line.split()
            current.append({
                "keyword_a": a.lower(),
                "keyword_b": b.lower(),
                "lower": float(lower),
                "upper": float(upper),
                "flag1": flag1.lower() == "true",
                "flag2": flag2.lower() == "true",
            })

    if current:
        patterns.append(current)
    return patterns


def build_inverted_index(objects):
    index = defaultdict(list)
    for oid, obj in objects.items():
        for kw in obj["keywords"]:
            index[kw].append(oid)
    return {kw: sorted(ids) for kw, ids in index.items()}


def distance(a, b):
    dx = a["lon"] - b["lon"]
    dy = a["lat"] - b["lat"]
    return math.sqrt(dx * dx + dy * dy)


def keywords_in_pattern(pattern):
    result = set()
    for edge in pattern:
        result.add(edge["keyword_a"])
        result.add(edge["keyword_b"])
    return sorted(result)


def pair_satisfies(objects, index, edge, oid_a, oid_b):
    if oid_a == oid_b:
        return False

    obj_a = objects[oid_a]
    obj_b = objects[oid_b]
    d = distance(obj_a, obj_b)
    if d < edge["lower"] or d > edge["upper"]:
        return False

    if edge["flag1"]:
        for other in index.get(edge["keyword_b"], []):
            if other != oid_b and distance(obj_a, objects[other]) < edge["lower"]:
                return False

    if edge["flag2"]:
        for other in index.get(edge["keyword_a"], []):
            if other != oid_a and distance(obj_b, objects[other]) < edge["lower"]:
                return False

    return True


def full_match_satisfies(objects, index, pattern, match):
    used = set()
    for oid in match.values():
        if oid in used:
            return False
        used.add(oid)

    for edge in pattern:
        a = match.get(edge["keyword_a"])
        b = match.get(edge["keyword_b"])
        if a is None or b is None:
            continue
        if not pair_satisfies(objects, index, edge, a, b):
            return False
    return True


def stop_now(matches, max_matches):
    return max_matches > 0 and len(matches) >= max_matches
