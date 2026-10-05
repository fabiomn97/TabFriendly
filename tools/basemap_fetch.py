import json, urllib.request, urllib.parse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BBOX = "42.3250,-71.1400,42.3920,-71.0450"
Q = f"""[out:json][timeout:120];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link|living_street|pedestrian)$"]({BBOX});
  way["natural"="water"]({BBOX});
  relation["natural"="water"]({BBOX});
  way["leisure"~"^(park|pitch|garden)$"]({BBOX});
  way["railway"="rail"]({BBOX});
);
out geom;"""

for url in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]:
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": Q}).encode(),
                                     headers={"User-Agent": "TabFriendly-student-project/0.1 (MIT course project)",
                                              "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            body = r.read()
        json.loads(body)
        open(os.path.join(HERE, "osm.json"), "wb").write(body)
        print("ok", url, len(body))
        sys.exit(0)
    except Exception as e:
        print("fail", url, e)
sys.exit(1)
