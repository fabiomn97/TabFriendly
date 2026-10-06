"""Build seed batches for venues that are NOT already in the live database, within a radius.

Compares data/seed (from make_seed.py) against a dump of the live `venues` and `reports` collections
(JSON files saved by ArtifactData list with out_dir), matching on document id, on name + location
(same normalized name within 300 m), and on location alone (any live venue within 10 m).

Usage: python tools/seed_against_live.py <live_dump_dir> <max_miles>
Writes data/seed/batches.json.
"""
import glob, json, math, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seed")
live_dir, max_mi = sys.argv[1], float(sys.argv[2])
MIT = (42.35916, -71.09348)


def load(sub):
    return {os.path.basename(f)[:-5]: json.load(open(f, encoding="utf-8")) for f in glob.glob(os.path.join(live_dir, sub, "*.json"))}


def meters(a, b):
    r = math.pi / 180
    x = (b["lng"] - a["lng"]) * r * math.cos((a["lat"] + b["lat"]) / 2 * r)
    return 6371000 * math.hypot(x, (b["lat"] - a["lat"]) * r)


def miles(a):
    return meters(a, {"lat": MIT[0], "lng": MIT[1]}) / 1609.34


def norm(n):
    n = re.sub(r"\s*\([^)]*\)\s*", " ", n.lower())
    n = re.sub(r"^the\s+", "", n.strip())
    return re.sub(r"[^a-z0-9]", "", n)


live_v, live_r = load("venues"), load("reports")
lv = [v for v in live_v.values() if isinstance(v.get("lat"), (int, float))]
writes, skipped = [], []
for f in sorted(glob.glob(os.path.join(SEED, "venues", "*.json"))):
    vid = os.path.basename(f)[:-5]
    v = json.load(open(f, encoding="utf-8"))
    if miles(v) > max_mi:
        continue
    # geocoders disagree by a block or two, so a matching name within 300 m counts as the same place;
    # neighbors (e.g. adjacent storefronts) are only merged when they sit within 10 m
    clash = vid in live_v or next((x for x in lv if (norm(x["name"]) == norm(v["name"]) and meters(x, v) < 300) or meters(x, v) < 10), None)
    if clash:
        if vid not in live_v:
            skipped.append(f"{v['name']}  ~  live: {clash['name']}")
        continue
    writes.append({"op": "set", "collection": "venues", "doc_id": vid, "file_path": f"data/seed/venues/{vid}.json"})
    for kind in ("beer", "mixed"):
        rid = f"seed-{vid[2:]}-{kind}"
        if os.path.exists(os.path.join(SEED, "reports", rid + ".json")) and rid not in live_r:
            writes.append({"op": "set", "collection": "reports", "doc_id": rid, "file_path": f"data/seed/reports/{rid}.json"})

batches = [writes[i:i + 50] for i in range(0, len(writes), 50)]
json.dump(batches, open(os.path.join(SEED, "batches.json"), "w", encoding="utf-8"), indent=1)
print("matched to a differently-named live venue (skipped):")
for s in skipped:
    print("  ", s)
nv = sum(1 for w in writes if w["collection"] == "venues")
print(f"{nv} venues + {len(writes) - nv} reports to write, in {len(batches)} batches")
