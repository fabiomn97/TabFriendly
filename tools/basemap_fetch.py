"""Download the OpenStreetMap data the basemap is built from (roads, water, coastline, parks, rail) into tools/osm.json.

The area is fetched in tiles so each Overpass request stays small; tiles are retried on other mirrors and merged.
"""
import json, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BBOX = (42.2250, -71.1950, 42.4060, -70.9850)  # Boston (without the outer harbor islands) and Cambridge
TILES = 3  # 3 x 3 tiles
MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
QUERY = """[out:json][timeout:180];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link|living_street|pedestrian)$"]({b});
  way["natural"="water"]({b});
  relation["natural"="water"]({b});
  way["natural"="coastline"]({b});
  way["leisure"~"^(park|pitch|garden)$"]({b});
  way["railway"="rail"]({b});
);
out geom;"""


def fetch(bbox):
    q = QUERY.replace("{b}", ",".join(f"{x:.4f}" for x in bbox))
    for attempt in range(4):
        for url in MIRRORS:
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(),
                                             headers={"User-Agent": "TabFriendly-student-project/0.1 (MIT course project)"})
                with urllib.request.urlopen(req, timeout=200) as r:
                    return json.loads(r.read())["elements"]
            except Exception as e:
                print("  fail", url, e)
        time.sleep(20 * (attempt + 1))
    sys.exit("could not fetch tile %s" % (bbox,))


s, w, n, e = BBOX
elements = {}
for i in range(TILES):
    for j in range(TILES):
        tile = (s + (n - s) * i / TILES, w + (e - w) * j / TILES, s + (n - s) * (i + 1) / TILES, w + (e - w) * (j + 1) / TILES)
        els = fetch(tile)
        for el in els:
            elements[(el["type"], el["id"])] = el  # ways crossing tile edges come back whole, so duplicates are identical
        print(f"tile {i * TILES + j + 1}/{TILES * TILES}: {len(els)} elements, {len(elements)} total")
json.dump({"elements": list(elements.values())}, open(os.path.join(HERE, "osm.json"), "w", encoding="utf-8"))
print("ok", len(elements))
