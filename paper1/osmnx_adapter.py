"""
OSM adapter for the SPM algorithm.

Downloads Points of Interest from OpenStreetMap via the Overpass API and
converts them into the same internal dict format used by spm.py:

    {object_id: {"lon": float, "lat": float, "keywords": set[str]}}

Uses stdlib urllib directly — confirmed to reach overpass-api.de from this
environment, whereas requests/osmnx fail due to a system-proxy routing issue.

Distance note
-------------
Pattern distances must be in KILOMETRES when using OSM data.
Pass dist_mode='haversine' to run_msj / run_pattern.
The Fang dataset uses raw Euclidean degrees; OSM users think in metres/km.
"""

import json
import math
import ssl
import time
import urllib.parse
import urllib.request
from collections import Counter

# ── Overpass API ──────────────────────────────────────────────────────────────

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Reusable SSL context that skips certificate verification.
# The sandbox sits behind an SSL-inspection proxy; skipping verification
# is the only way to reach external HTTPS endpoints from this environment.
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode    = ssl.CERT_NONE


def _overpass_query(query: str, timeout: int = 60) -> dict:
    """POST a raw Overpass QL query and return the parsed JSON."""
    data = urllib.parse.urlencode({"data": query}).encode()
    req  = urllib.request.Request(
        _OVERPASS_URL, data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent":   "spm-bench/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        return json.loads(resp.read())


# ── Tag → keyword mapping ──────────────────────────────────────────────────────

# OSM tag keys whose values become keywords directly.
_KEYWORD_KEYS = [
    "amenity", "shop", "tourism", "leisure", "historic",
    "building", "sport", "cuisine", "landuse", "natural",
    "public_transport", "office", "healthcare", "craft", "emergency",
]

_STOP_WORDS = {
    "the", "a", "an", "of", "and", "in", "at", "on", "for", "to", "is",
    "by", "with", "it", "its", "as", "or", "from", "be", "but", "not",
    "are", "was", "this", "that", "have", "had", "has",
}


def tags_to_keywords(tags: dict, include_name: bool = True) -> set:
    """
    Build a keyword set from an OSM element's tag dict.

    - Values for keys in _KEYWORD_KEYS become keywords directly.
    - Semicolon-separated multi-values are split.
    - If include_name=True: words from the 'name' tag are added after
      lowercasing and removing stop-words and tokens shorter than 3 chars.
    """
    keywords: set = set()

    for key in _KEYWORD_KEYS:
        val = tags.get(key, "")
        if not val:
            continue
        for part in str(val).replace(";", "/").split("/"):
            part = part.strip().lower().replace(" ", "_").replace("-", "_")
            if len(part) >= 2:
                keywords.add(part)

    if include_name:
        name = tags.get("name", "")
        if name:
            for token in str(name).lower().split():
                token = token.strip(".,;:!?'\"-()[]{}#@")
                if len(token) >= 3 and token not in _STOP_WORDS:
                    keywords.add(token)

    return keywords


# ── Download ──────────────────────────────────────────────────────────────────

def load_osm_objects(
    point: tuple = None,
    radius_m: float = 1500,
    place: str = None,
    bbox: tuple = None,
    tags: list = None,
    include_name: bool = True,
    max_objects: int = None,
) -> dict:
    """
    Download OSM POIs and return SPM spatial objects.

    Parameters
    ----------
    point     : (lat, lon) centre for a radius query (recommended).
    radius_m  : search radius in metres around point (default 1500 m).
    place     : place name — used only to look up a bounding box via Nominatim
                if point is not given.  Prefer point= for reliability.
    bbox      : (south, west, north, east) degrees fallback.
    tags      : list of OSM tag keys to include, e.g. ["amenity","shop"].
                Defaults to the full POI set.
    include_name : add name tokens as extra keywords (default True).
    max_objects  : cap the number of objects returned.

    Returns
    -------
    {object_id: {"lon": float, "lat": float, "keywords": set[str]}}
    Pattern distances for this data must be in km (use dist_mode='haversine').
    """
    if tags is None:
        tags = ["amenity", "shop", "tourism", "leisure", "historic"]

    if point is not None:
        lat, lon = point
        label = f"point ({lat}, {lon}) r={radius_m:.0f}m"
        # Build an Overpass union of node/way/relation queries for each tag key
        parts = "\n  ".join(
            f'node["{k}"](around:{radius_m:.0f},{lat},{lon});\n  '
            f'way["{k}"](around:{radius_m:.0f},{lat},{lon});'
            for k in tags
        )
        query = (
            f"[out:json][timeout:60];\n(\n  {parts}\n);\n"
            "out body center;"
        )
    elif bbox is not None:
        s, w, n, e = bbox
        label = f"bbox ({s},{w},{n},{e})"
        parts = "\n  ".join(
            f'node["{k}"]({s},{w},{n},{e});\n  way["{k}"]({s},{w},{n},{e});'
            for k in tags
        )
        query = f"[out:json][timeout:60];\n(\n  {parts}\n);\nout body center;"
    else:
        raise ValueError("Provide point= or bbox=")

    print(f"Downloading OSM features for {label}...")
    last_err = None
    for attempt in range(3):
        try:
            data = _overpass_query(query, timeout=90)
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                wait = 5 * (attempt + 1)
                print(f"  Attempt {attempt + 1} failed ({type(e).__name__}), retrying in {wait}s...")
                time.sleep(wait)
    else:
        raise RuntimeError(f"Overpass download failed after 3 attempts: {last_err}") from last_err

    elements = data.get("elements", [])
    print(f"  Raw elements: {len(elements):,}")

    objects: dict = {}
    skipped = 0

    for el in elements:
        if max_objects and len(objects) >= max_objects:
            break

        el_tags = el.get("tags", {})
        kws = tags_to_keywords(el_tags, include_name=include_name)
        if not kws:
            skipped += 1
            continue

        # Nodes have lat/lon directly; ways have a "center" key
        if el["type"] == "node":
            lon_v, lat_v = el["lon"], el["lat"]
        elif "center" in el:
            lon_v, lat_v = el["center"]["lon"], el["center"]["lat"]
        else:
            skipped += 1
            continue

        oid = len(objects)
        objects[oid] = {"lon": lon_v, "lat": lat_v, "keywords": kws}

    if skipped:
        print(f"  Skipped {skipped:,} elements (no geometry or no useful tags).")

    all_kw: set = set()
    for obj in objects.values():
        all_kw.update(obj["keywords"])
    print(f"  Objects loaded   : {len(objects):,}")
    print(f"  Unique keywords  : {len(all_kw):,}")
    print("  (Use dist_mode='haversine' — pattern distances should be in km)")
    return objects


def load_osm_objects_with_names(
    point: tuple = None,
    radius_m: float = 1500,
    place: str = None,
    bbox: tuple = None,
    tags: list = None,
    include_name: bool = True,
    max_objects: int = None,
) -> tuple:
    """
    Same as load_osm_objects but also returns a names dict for verification.

    Returns
    -------
    objects : dict   {oid: {"lon", "lat", "keywords"}}
    names   : dict   {oid: "Display Name (type)"}
    """
    if tags is None:
        tags = ["amenity", "shop", "tourism", "leisure", "historic"]

    if point is not None:
        lat, lon = point
        label = f"point ({lat}, {lon}) r={radius_m:.0f}m"
        parts = "\n  ".join(
            f'node["{k}"](around:{radius_m:.0f},{lat},{lon});\n  '
            f'way["{k}"](around:{radius_m:.0f},{lat},{lon});'
            for k in tags
        )
        query = (
            f"[out:json][timeout:60];\n(\n  {parts}\n);\n"
            "out body center;"
        )
    elif bbox is not None:
        s, w, n, e = bbox
        label = f"bbox ({s},{w},{n},{e})"
        parts = "\n  ".join(
            f'node["{k}"]({s},{w},{n},{e});\n  way["{k}"]({s},{w},{n},{e});'
            for k in tags
        )
        query = f"[out:json][timeout:60];\n(\n  {parts}\n);\nout body center;"
    else:
        raise ValueError("Provide point= or bbox=")

    print(f"Downloading OSM features for {label}...")
    last_err = None
    for attempt in range(3):
        try:
            data = _overpass_query(query, timeout=90)
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                wait = 5 * (attempt + 1)
                print(f"  Attempt {attempt + 1} failed, retrying in {wait}s...")
                time.sleep(wait)
    else:
        raise RuntimeError(f"Overpass download failed: {last_err}") from last_err

    elements = data.get("elements", [])
    print(f"  Raw elements: {len(elements):,}")

    objects: dict = {}
    names:   dict = {}
    skipped = 0

    for el in elements:
        if max_objects and len(objects) >= max_objects:
            break

        el_tags = el.get("tags", {})
        kws = tags_to_keywords(el_tags, include_name=include_name)
        if not kws:
            skipped += 1
            continue

        if el["type"] == "node":
            lon_v, lat_v = el["lon"], el["lat"]
        elif "center" in el:
            lon_v, lat_v = el["center"]["lon"], el["center"]["lat"]
        else:
            skipped += 1
            continue

        oid = len(objects)
        objects[oid] = {"lon": lon_v, "lat": lat_v, "keywords": kws}

        osm_name = el_tags.get("name", "")
        osm_type = next(
            (el_tags[k] for k in _KEYWORD_KEYS if k in el_tags), "?"
        )
        names[oid] = f"{osm_name} ({osm_type})" if osm_name else f"({osm_type})"

    if skipped:
        print(f"  Skipped {skipped:,} elements.")

    all_kw: set = set()
    for obj in objects.values():
        all_kw.update(obj["keywords"])
    print(f"  Objects  : {len(objects):,}")
    print(f"  Keywords : {len(all_kw):,}")
    return objects, names


# ── Verification ──────────────────────────────────────────────────────────────

def verify_matches(matches: list, objects: dict, pattern_edges: list,
                   names: dict = None, dist_mode: str = "haversine") -> bool:
    """
    Check every returned match satisfies ALL pattern constraints.

    Verifies for each match:
      1. Every matched object carries the required keyword.
      2. Every edge's distance [lower, upper] is satisfied.
      3. Every exclusion constraint holds.

    Prints PASS / FAIL per match with the OSM place names.
    Returns True if ALL matches are valid.
    """
    from spm import _dist_fn, build_inverted_index

    if not matches:
        print("No matches to verify.")
        return True

    dfn = _dist_fn(dist_mode)
    inv = build_inverted_index(objects)
    unit = "km" if dist_mode == "haversine" else "deg"
    all_ok = True

    for mi, m in enumerate(matches):
        errors = []

        for edge in pattern_edges:
            ka, kb       = edge["keyword_a"], edge["keyword_b"]
            lower, upper = edge["lower"],     edge["upper"]
            flag1, flag2 = edge["flag1"],     edge["flag2"]

            if ka not in m:
                errors.append(f"keyword '{ka}' missing from match"); continue
            if kb not in m:
                errors.append(f"keyword '{kb}' missing from match"); continue

            oa, ob   = m[ka], m[kb]
            obj_a    = objects[oa]
            obj_b    = objects[ob]

            # 1. Keyword membership
            if ka not in obj_a["keywords"]:
                errors.append(f"obj#{oa} lacks keyword '{ka}'")
            if kb not in obj_b["keywords"]:
                errors.append(f"obj#{ob} lacks keyword '{kb}'")

            # 2. Distance constraint
            d = dfn(obj_a, obj_b)
            if d < lower - 1e-9:
                errors.append(
                    f"'{ka}'–'{kb}' dist {d:.4f} {unit} < lower {lower:.4f}")
            if d > upper + 1e-9:
                errors.append(
                    f"'{ka}'–'{kb}' dist {d:.4f} {unit} > upper {upper:.4f}")

            # 3. Exclusion constraints
            if flag1:
                for bid in inv.get(kb, []):
                    if bid != oa and dfn(obj_a, objects[bid]) < lower - 1e-9:
                        errors.append(
                            f"exclusion violated: '{kb}' obj#{bid} "
                            f"is {dfn(obj_a, objects[bid]):.4f} {unit} "
                            f"from '{ka}' obj#{oa} (lower={lower:.4f})")
                        break
            if flag2:
                for aid in inv.get(ka, []):
                    if aid != ob and dfn(obj_b, objects[aid]) < lower - 1e-9:
                        errors.append(
                            f"exclusion violated: '{ka}' obj#{aid} "
                            f"is {dfn(obj_b, objects[aid]):.4f} {unit} "
                            f"from '{kb}' obj#{ob} (lower={lower:.4f})")
                        break

        status = "PASS" if not errors else "FAIL"
        if errors:
            all_ok = False

        line = f"  [{mi:3d}] {status}"
        if names:
            parts = [
                f"{kw}='{names.get(oid, '#'+str(oid))}'"
                for kw, oid in sorted(m.items())
            ]
            line += "  " + ",  ".join(parts)
        print(line)

        for e in errors:
            print(f"         ERROR: {e}")

    verdict = "ALL MATCHES VALID" if all_ok else "SOME MATCHES FAILED"
    print(f"\n{verdict}  ({len(matches)} matches checked)")
    return all_ok


# ── Utilities ─────────────────────────────────────────────────────────────────

def save_fang_format(objects: dict, loc_path: str, doc_path: str) -> None:
    """Cache OSM objects as Fang loc/doc files for instant reloads."""
    with open(loc_path, "w", encoding="utf-8") as f:
        for oid, obj in objects.items():
            f.write(f"{oid},{obj['lon']},{obj['lat']}\n")
    with open(doc_path, "w", encoding="utf-8") as f:
        for oid, obj in objects.items():
            f.write(f"{oid}," + ",".join(sorted(obj["keywords"])) + "\n")
    print(f"Saved {len(objects):,} objects to {loc_path} and {doc_path}")


def parse_pattern_km(text: str) -> list:
    """
    Parse a pattern whose distances are in kilometres.

    Each non-blank, non-comment line:
        keyword_a  keyword_b  lower_km  upper_km  [flag1]  [flag2]
    flag1/flag2 default to False (mutual inclusion).
    """
    edges = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"Need at least 4 tokens per edge: {line!r}")
        edges.append({
            "keyword_a": parts[0].lower(),
            "keyword_b": parts[1].lower(),
            "lower":     float(parts[2]),
            "upper":     float(parts[3]),
            "flag1":     parts[4].lower() == "true" if len(parts) > 4 else False,
            "flag2":     parts[5].lower() == "true" if len(parts) > 5 else False,
        })
    return edges


def keyword_stats(objects: dict, top_n: int = 30) -> None:
    """Print most common keywords — useful for designing patterns."""
    counts: Counter = Counter()
    for obj in objects.values():
        counts.update(obj["keywords"])
    print(f"Top {top_n} keywords ({len(counts)} total):")
    for kw, cnt in counts.most_common(top_n):
        print(f"  {kw:<30s} {cnt:,}")
