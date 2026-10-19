"""Coverage area: the cities of Boston and Cambridge (simplified OSM boundaries in tools/cities.json), plus the original
2-mile circle around 77 Mass Ave, which also takes in parts of Somerville and Brookline."""
import json, math, os

MIT = (42.35916, -71.09348)
RADIUS_MI = 2.0

_HERE = os.path.dirname(os.path.abspath(__file__))
_RINGS = []
for _g in json.load(open(os.path.join(_HERE, "cities.json"), encoding="utf-8")).values():
    for _poly in ([_g["coordinates"]] if _g["type"] == "Polygon" else _g["coordinates"]):
        _RINGS.append([(lat, lng) for lng, lat in _poly[0]])


def dist_mi(lat, lng):
    r = math.pi / 180
    a = math.sin((lat - MIT[0]) * r / 2) ** 2 + math.cos(MIT[0] * r) * math.cos(lat * r) * math.sin((lng - MIT[1]) * r / 2) ** 2
    return 2 * 3958.8 * math.asin(math.sqrt(a))


def in_area(lat, lng):
    if dist_mi(lat, lng) <= RADIUS_MI:
        return True
    hit = False
    for ring in _RINGS:
        for (y0, x0), (y1, x1) in zip(ring, ring[1:] + ring[:1]):
            if (y0 > lat) != (y1 > lat) and lng < x0 + (lat - y0) * (x1 - x0) / (y1 - y0):
                hit = not hit
    return hit
