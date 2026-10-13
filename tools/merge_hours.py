"""Validate and merge opening-hours research into data/hours.json ({venue id: {hours, source, checked}}).

Inputs are JSON lists in either shape:
  - hours files: [{venue_id, name, hours, source, checked, notes}]
  - venue research files (data/venues.json shape) with "hours" and "hours_source"; the venue id is derived from the
    name the same way tools/make_seed.py does.
Each day is "closed" or comma-separated "HH:MM-HH:MM" ranges in 24-hour time (a range past midnight ends the next
morning, e.g. "16:00-02:00"). Days that don't parse are dropped, and so is a venue with no valid day.

Usage: python tools/merge_hours.py <file.json> [<file.json> ...]
"""
import json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "hours.json")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
RANGE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d-([01]?\d|2[0-4]):[0-5]\d$")


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def clean_day(v):
    if not isinstance(v, str):
        return None
    v = v.strip().lower().replace(" ", "").replace("–", "-")
    if v == "closed":
        return "closed"
    parts = v.split(",")
    return ",".join(parts) if parts and all(RANGE.match(p) for p in parts) else None


hours = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
for f in sys.argv[1:]:
    for x in json.load(open(f, encoding="utf-8")):
        vid = x.get("venue_id") or ("v-" + slug(x["name"]))
        h = x.get("hours")
        if not isinstance(h, dict):
            continue
        week = {d: clean_day(h.get(d)) for d in DAYS}
        bad = [d for d in DAYS if week[d] is None]
        if len(bad) == len(DAYS):
            print(f"skip (no valid days): {x.get('name')}")
            continue
        if bad:
            print(f"note: {x.get('name')}: unreadable {', '.join(bad)} left blank")
        hours[vid] = {"hours": {d: week[d] for d in DAYS if week[d] is not None},
                      "source": x.get("source") or x.get("hours_source"), "checked": x.get("checked") or "2026-10"}

json.dump(dict(sorted(hours.items())), open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(hours)} venues with hours -> {OUT}")
