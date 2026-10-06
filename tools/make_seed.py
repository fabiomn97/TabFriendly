"""Turn data/venues.json (the reviewed research list) into one JSON file per database document.

Output: data/seed/venues/<id>.json, data/seed/reports/<id>.json and data/seed/menus/<venue id>.json (from
data/menus.json, if present), plus data/seed/batches.json —
a list of ArtifactData batch-write lists (50 writes max each) for the documents not in the live snapshot (data/live/).

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
for sub in ("venues", "reports", "menus"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    for f in os.listdir(os.path.join(OUT, sub)):
        os.remove(os.path.join(OUT, sub, f))

for v in venues:
    d = dist_mi(v["lat"], v["lng"])
    if d > 1.5:
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

n_reports = len(writes) - len(seen)

# Full drink menus (data/menus.json, built by tools/merge_menus.py): one doc per venue, keyed by the venue id.
menu_writes = []
MENUS = os.path.join(ROOT, "data", "menus.json")
for m in json.load(open(MENUS, encoding="utf-8")) if os.path.exists(MENUS) else []:
    if m["venue_id"] not in seen or not m["items"]:
        continue
    doc = {"venueId": m["venue_id"], "items": m["items"], "sources": m["menu_sources"],
           "sourceDate": m["menu_date"] if m["menu_date"] != "unknown" else None, "by": None, "at": SEED_AT}
    path = os.path.join(OUT, "menus", m["venue_id"] + ".json")
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    menu_writes.append({"op": "set", "collection": "menus", "doc_id": m["venue_id"], "file_path": path})
writes += menu_writes

# Documents already in the latest live snapshot (data/live/) are never re-sent: a write would overwrite edits
# made in the app, and the database refuses unpinned writes to existing documents anyway.
live = set()
for coll in ("venues", "reports", "menus"):
    p = os.path.join(ROOT, "data", "live", coll + ".json")
    if os.path.exists(p):
        live.update(f"{coll}/{k}" for k in json.load(open(p, encoding="utf-8")))
writes = [w for w in writes if f"{w['collection']}/{w['doc_id']}" not in live]
menu_writes = [w for w in menu_writes if f"{w['collection']}/{w['doc_id']}" not in live]

chunk = lambda ws: [ws[i:i + 50] for i in range(0, len(ws), 50)]
batches = chunk(writes)
json.dump(batches, open(os.path.join(OUT, "batches.json"), "w", encoding="utf-8"), indent=1)
json.dump(chunk(menu_writes), open(os.path.join(OUT, "batches_menus.json"), "w", encoding="utf-8"), indent=1)
print(f"{len(seen)} venues, {n_reports} price reports; {len(writes)} documents not live yet, in {len(batches)} batches")
