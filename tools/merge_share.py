"""Add share-size prices (pitchers, bottles of wine) from research files to the menus in data/menus.json.

Each research file is a JSON list of {venue_id, name, sources, source_date, items: [{name, type, kind, serve, oz, price}], notes},
where serve is "pitcher" (any kind) or "bottle" (wine only). Items already on the menu (same name, size and price) are skipped.
Types reuse the spelling already on the menus, so the Drinks filter lists one entry per drink.

Usage: python tools/merge_share.py <share_1.json> [<share_2.json> ...]
"""
import collections, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "menus.json")
KINDS = {"beer", "mixed", "wine", "other"}


def key(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9&]+", " ", t).strip()


def num(x, lo, hi):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and lo <= x <= hi else None


menus = {m["venue_id"]: m for m in json.load(open(P, encoding="utf-8"))}
spell = {}
for t, _ in collections.Counter(it["type"] for m in menus.values() for it in m["items"]).most_common():
    spell.setdefault(key(t), t)

added, dropped, venues = collections.Counter(), collections.Counter(), set()
for f in sys.argv[1:]:
    for r in json.load(open(f, encoding="utf-8")):
        m = menus.get(r.get("venue_id"))
        if not m:
            print("skip venue without a menu:", r.get("venue_id"))
            continue
        seen = {(it["name"].lower(), it["oz"], it["price"]) for it in m["items"]}
        n0 = len(m["items"])
        for it in r.get("items") or []:
            name = re.sub(r"\s+", " ", str(it.get("name") or "")).strip()
            kind, serve = it.get("kind"), it.get("serve")
            price = num(it.get("price"), 1, 500)
            if not name or kind not in KINDS or not price or serve not in ("pitcher", "bottle") or (serve == "bottle" and kind != "wine"):
                dropped["invalid"] += 1
                continue
            oz = num(it.get("oz"), 1, 128)
            sig = (name.lower()[:80], oz, round(float(price), 2))
            if sig in seen:
                dropped["duplicate"] += 1
                continue
            seen.add(sig)
            t = re.sub(r"\s+", " ", str(it.get("type") or name)).strip()
            m["items"].append({"name": name[:80], "type": spell.get(key(t), t)[:60], "kind": kind, "serve": serve,
                               "oz": oz, "price": round(float(price), 2)})
            added[serve] += 1
        if len(m["items"]) > n0:
            venues.add(m["venue_id"])
            for u in r.get("sources") or []:
                if isinstance(u, str) and u.startswith("https://") and u not in m["menu_sources"] and len(m["menu_sources"]) < 5:
                    m["menu_sources"].append(u)

json.dump(sorted(menus.values(), key=lambda m: m["venue_id"]), open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"added {added['pitcher']} pitchers and {added['bottle']} bottles of wine at {len(venues)} venues; dropped {dict(dropped)} -> {P}")
