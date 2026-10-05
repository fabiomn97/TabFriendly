"""Write data/venues_review.csv — one row per venue for the team's pre-launch review (open in Excel/Sheets)."""
import csv, json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIT = (42.35916, -71.09348)
v = json.load(open(os.path.join(ROOT, "data", "venues.json"), encoding="utf-8"))


def dist(a):
    r = math.pi / 180
    x = (a["lng"] - MIT[1]) * r * math.cos(MIT[0] * r)
    y = (a["lat"] - MIT[0]) * r
    return round(3958.8 * math.hypot(x, y), 2)


with open(os.path.join(ROOT, "data", "venues_review.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["venue", "area", "miles", "beer", "beer $", "oz", "beer source", "beer date",
                "mixed drink", "mixed $", "mixed source", "mixed date", "research notes"])
    for a in sorted(v, key=lambda a: ((a.get("beer") or {}).get("price") or 99, a["name"])):
        b, m = a.get("beer") or {}, a.get("mixed") or {}
        w.writerow([a["name"], a["area"], dist(a), b.get("name"), b.get("price"), b.get("oz"), b.get("source"),
                    b.get("source_date"), m.get("name"), m.get("price"), m.get("source"), m.get("source_date"),
                    a.get("notes", "")])
print("wrote data/venues_review.csv")
