"""Compact the Overpass dump into a small basemap.json for the TabFriendly map.

Output coordinates are [lat, lng] rounded to 5 decimals (about 1 m), simplified with Douglas-Peucker.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "basemap.json")
# Crop window for water polygons: the Charles River relation spans miles; keep the part near MIT.
S, W, N, E = 42.315, -71.155, 42.400, -71.030

TOL = 0.000035
osm = json.load(open(os.path.join(HERE, "osm.json"), encoding="utf-8"))


def pts(geom):
    return [(g["lat"], g["lon"]) for g in geom if g]


def dp(points, tol):
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (ay, ax), (by, bx) = points[a], points[b]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        best, idx = 0, -1
        for i in range(a + 1, b):
            py, px = points[i]
            if L == 0:
                d = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
                d = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d > best:
                best, idx = d, i
        if best > tol * tol and idx > 0:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, keep) if k]


def rnd(points):
    out = []
    for y, x in points:
        p = [round(y, 5), round(x, 5)]
        if not out or out[-1] != p:
            out.append(p)
    return out


def stitch(ways):
    """Join open way segments into closed rings."""
    ways = [list(w) for w in ways if len(w) > 1]
    rings = []
    while ways:
        ring = ways.pop(0)
        changed = True
        while ring[0] != ring[-1] and changed:
            changed = False
            for i, w in enumerate(ways):
                if w[0] == ring[-1]:
                    ring += w[1:]
                elif w[-1] == ring[-1]:
                    ring += w[::-1][1:]
                elif w[-1] == ring[0]:
                    ring = w[:-1] + ring
                elif w[0] == ring[0]:
                    ring = w[::-1][:-1] + ring
                else:
                    continue
                ways.pop(i)
                changed = True
                break
        rings.append(ring)
    return rings


def clip_ring(ring):
    """Sutherland-Hodgman clip of a polygon ring to the crop window."""
    def clip(poly, inside, inter):
        out = []
        for i in range(len(poly)):
            cur, prev = poly[i], poly[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(inter(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(inter(prev, cur))
        return out

    def ix_lat(lat):
        return lambda a, b: (lat, a[1] + (b[1] - a[1]) * (lat - a[0]) / (b[0] - a[0]))

    def ix_lng(lng):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (lng - a[1]) / (b[1] - a[1]), lng)

    poly = ring
    for inside, inter in [
        (lambda p: p[0] >= S, ix_lat(S)), (lambda p: p[0] <= N, ix_lat(N)),
        (lambda p: p[1] >= W, ix_lng(W)), (lambda p: p[1] <= E, ix_lng(E)),
    ]:
        if not poly:
            break
        poly = clip(poly, inside, inter)
    return poly


water, parks, rail = [], [], []
roads = {"major": [], "mid": [], "minor": []}
names = {}
CLASS = {
    "motorway": "major", "trunk": "major", "primary": "major", "motorway_link": "major", "trunk_link": "major",
    "primary_link": "major", "secondary": "mid", "secondary_link": "mid", "tertiary": "mid", "tertiary_link": "mid",
}

for el in osm["elements"]:
    tags = el.get("tags", {})
    if el["type"] == "way":
        p = pts(el.get("geometry", []))
        if "highway" in tags:
            c = CLASS.get(tags["highway"], "minor")
            line = rnd(dp(p, TOL))
            if len(line) > 1:
                roads[c].append(line)
                if c != "minor" and tags.get("name"):
                    names.setdefault(tags["name"], []).append(line)
        elif tags.get("railway") == "rail":
            rail.append(rnd(dp(p, TOL)))
        elif tags.get("natural") == "water":
            r = rnd(dp(clip_ring(p), TOL))
            if len(r) > 3:
                water.append([r])
        elif tags.get("leisure") == "park":
            r = rnd(dp(p, TOL))
            if len(r) > 3:
                parks.append([r])
    elif el["type"] == "relation" and tags.get("natural") == "water":
        outers = [pts(m["geometry"]) for m in el.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
        inners = [pts(m["geometry"]) for m in el.get("members", []) if m.get("role") == "inner" and m.get("geometry")]
        outer_rings = [rnd(dp(clip_ring(r), TOL)) for r in stitch(outers)]
        inner_rings = [rnd(dp(clip_ring(r), TOL)) for r in stitch(inners)]
        outer_rings = [r for r in outer_rings if len(r) > 3]
        inner_rings = [r for r in inner_rings if len(r) > 3]
        for o in outer_rings:
            water.append([o] + inner_rings)
            inner_rings = []  # attach holes to the first outer only; fine for the river islands here


# Compact encoding: each line/ring becomes a flat int list in 1e-5 degree units —
# the first pair is relative to BASE, the rest are deltas from the previous point. Decoded in app/index.html.
BASE = (42.3, -71.1)


def enc(line):
    out, py, px = [], round(BASE[0] * 1e5), round(BASE[1] * 1e5)
    for lat, lng in line:
        y, x = round(lat * 1e5), round(lng * 1e5)
        out += [y - py, x - px]
        py, px = y, x
    return out


water = [[enc(r) for r in poly] for poly in water]
parks = [[enc(r) for r in poly] for poly in parks]
rail = [enc(l) for l in rail]
roads = {k: [enc(l) for l in v] for k, v in roads.items()}
out = {"base": BASE, "water": water, "parks": parks, "rail": rail, "roads": roads}
s = json.dumps(out, separators=(",", ":"))
open(OUT, "w", encoding="utf-8").write(s)
print("bytes", len(s), {k: len(v) for k, v in roads.items()}, "water", len(water), "parks", len(parks))
