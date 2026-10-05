"""Merge per-area research files into data/venues.json, dropping duplicates (same name within 150 m).

Usage: python tools/merge_research.py <research_dir>
"""
import json, math, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = sys.argv[1]
AREAS = [("kendall", "Kendall"), ("central", "Central"), ("backbay", "Back Bay"), ("kenmore", "Fenway")]


def meters(a, b):
    r = math.pi / 180
    x = (b["lng"] - a["lng"]) * r * math.cos((a["lat"] + b["lat"]) / 2 * r)
    y = (b["lat"] - a["lat"]) * r
    return 6371000 * math.hypot(x, y)


def norm(n):
    n = re.sub(r"^the\s+", "", n.lower())
    return re.sub(r"[^a-z0-9]", "", n)


def score(v):
    return sum(1 for k in ("beer", "mixed") if v.get(k) and v[k].get("price") is not None)


merged = []
for fname, area in AREAS:
    for v in json.load(open(os.path.join(src_dir, fname + ".json"), encoding="utf-8")):
        v["area"] = area
        dup = next((m for m in merged if norm(m["name"]) == norm(v["name"]) and meters(m, v) < 150), None)
        if dup:
            print(f"duplicate: {v['name']} ({area}) ~ {dup['name']} ({dup['area']})")
            if score(v) > score(dup):
                merged[merged.index(dup)] = v
            continue
        if any(norm(m["name"]) == norm(v["name"]) for m in merged):
            v["name"] = f"{v['name']} ({area})"
            for m in merged:
                if norm(m["name"]) == norm(v["name"].rsplit(" (", 1)[0]):
                    m["name"] = f"{m['name']} ({m['area']})"
        merged.append(v)

out = os.path.join(ROOT, "data", "venues.json")
json.dump(merged, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
beer = sum(1 for v in merged if v.get("beer") and v["beer"].get("price") is not None)
mixed = sum(1 for v in merged if v.get("mixed") and v["mixed"].get("price") is not None)
print(f"{len(merged)} venues, {beer} with beer price, {mixed} with mixed-drink price -> {out}")
