"""Turn data/venues.json (the reviewed research list) into one JSON file per database document.

Output: data/seed/venues/<id>.json and data/seed/reports/<id>.json, plus data/seed/batches.json —
a list of ArtifactData batch-write lists (50 writes max each) that point at those files.

Run:  python tools/make_seed.py
"""
import json, math, os, re, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "venues.json")
OUT = os.path.join(ROOT, "data", "seed")
MIT = (42.35916, -71.09348)
SEED_AT = "2026-10-05T00:00:00.000Z"  # older than any real user report, so user reports win


def dist_mi(lat, lng):
    r = math.pi / 180
    a = math.sin((lat - MIT[0]) * r / 2) ** 2 + math.cos(MIT[0] * r) * math.cos(lat * r) * math.sin((lng - MIT[1]) * r / 2) ** 2
    return 2 * 3958.8 * math.asin(math.sqrt(a))


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


venues = json.load(open(SRC, encoding="utf-8"))
writes, seen = [], set()
for sub in ("venues", "reports"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    for f in os.listdir(os.path.join(OUT, sub)):
        os.remove(os.path.join(OUT, sub, f))

for v in venues:
    d = dist_mi(v["lat"], v["lng"])
    if d > 1.0:
        print(f"skip (outside radius, {d:.2f} mi): {v['name']}")
        continue
    vid = "v-" + slug(v["name"])
    if vid in seen:
        print("skip duplicate:", v["name"])
        continue
    seen.add(vid)
    doc = {"name": v["name"], "type": v.get("type", "bar"), "address": v.get("address"), "lat": v["lat"], "lng": v["lng"],
           "website": v.get("website"), "note": v.get("venue_note"), "source": "seed", "by": None, "at": SEED_AT}
    path = os.path.join(OUT, "venues", vid + ".json")
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    writes.append({"op": "set", "collection": "venues", "doc_id": vid, "file_path": path})
    for kind in ("beer", "mixed"):
        p = v.get(kind)
        if not p or p.get("price") is None:
            continue
        rid = f"seed-{vid[2:]}-{kind}"
        sd = p.get("source_date")
        rep = {"venueId": vid, "kind": kind, "drink": p["name"], "price": float(p["price"]),
               "oz": p.get("oz") if kind == "beer" else None, "note": None, "hasPhoto": False, "source": "web",
               "sourceUrl": p.get("source"), "sourceDate": sd if sd and sd != "unknown" else None, "by": None, "at": SEED_AT}
        path = os.path.join(OUT, "reports", rid + ".json")
        json.dump(rep, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        writes.append({"op": "set", "collection": "reports", "doc_id": rid, "file_path": path})

batches = [writes[i:i + 50] for i in range(0, len(writes), 50)]
json.dump(batches, open(os.path.join(OUT, "batches.json"), "w", encoding="utf-8"), indent=1)
print(f"{len(seen)} venues, {len(writes) - len(seen)} price reports, {len(batches)} batches")
