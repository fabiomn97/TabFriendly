"""Append new research files to data/venues.json, keeping only venues inside the radius that aren't already listed.

Each file is a JSON list in the data/venues.json shape (plus an optional "miles", which is recomputed from lat/lng).
Usage: python tools/add_research.py <research.json> [<research.json> ...]
"""
import json, math, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "venues.json")
MIT = (42.35916, -71.09348)
RADIUS_MI = 1.5


def dist_mi(lat, lng):
    r = math.pi / 180
    a = math.sin((lat - MIT[0]) * r / 2) ** 2 + math.cos(MIT[0] * r) * math.cos(lat * r) * math.sin((lng - MIT[1]) * r / 2) ** 2
    return 2 * 3958.8 * math.asin(math.sqrt(a))


def meters(a, b):
    r = math.pi / 180
    x = (b["lng"] - a["lng"]) * r * math.cos((a["lat"] + b["lat"]) / 2 * r)
    y = (b["lat"] - a["lat"]) * r
    return 6371000 * math.hypot(x, y)


def norm(n):
    n = re.sub(r"^the\s+", "", n.lower())
    return re.sub(r"[^a-z0-9]", "", n)


def priced(p):
    return bool(p) and isinstance(p.get("price"), (int, float)) and p["price"] > 0 and bool(p.get("source"))


venues = json.load(open(P, encoding="utf-8"))
added = 0
for f in sys.argv[1:]:
    for v in json.load(open(f, encoding="utf-8")):
        v.pop("miles", None)
        d = dist_mi(v["lat"], v["lng"])
        if d > RADIUS_MI:
            print(f"skip (outside radius, {d:.2f} mi): {v['name']}")
            continue
        for k in ("beer", "mixed"):
            if v.get(k) and not priced(v[k]):
                v[k] = None
        if not v.get("beer") and not v.get("mixed"):
            print(f"skip (no sourced price): {v['name']}")
            continue
        dup = next((m for m in venues if norm(m["name"]) == norm(v["name"])), None)
        if dup:
            print(f"skip duplicate: {v['name']} ~ {dup['name']} ({meters(dup, v):.0f} m apart)")
            continue
        near = next((m for m in venues if meters(m, v) < 25), None)
        if near:
            print(f"check: {v['name']} is {meters(near, v):.0f} m from {near['name']} (kept both)")
        venues.append(v)
        added += 1

json.dump(venues, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"added {added}; {len(venues)} venues total -> {P}")
