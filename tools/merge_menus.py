"""Validate and merge full-drink-menu research files into data/menus.json.

Each research file is a JSON list of {venue_id, name, menu_sources, menu_date, items: [{name, type, kind, serve, oz, price}], notes}.
Drink types are what the app's Drinks filter lists, so spellings are unified here: common brands and classic
cocktails map to one canonical name, and any other type takes its most common spelling across venues.

Usage: python tools/merge_menus.py <menus_1.json> [<menus_2.json> ...]
"""
import collections, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "menus.json")
KINDS = {"beer", "mixed", "wine", "other"}
SERVES = {"draft", "bottle", "can", "well", "cocktail", "glass"}
CANON = """Coors Light|Coors Banquet|Bud Light|Budweiser|Miller Lite|Miller High Life|Michelob Ultra|Pabst Blue Ribbon|
Narragansett Lager|Sam Adams Boston Lager|Guinness|Modelo Especial|Negra Modelo|Corona Extra|Corona Light|Pacifico|Dos Equis|
Tecate|Heineken|Stella Artois|Peroni|Sapporo|Kirin Ichiban|Asahi|Tsingtao|Blue Moon|Harpoon IPA|Allagash White|
Sierra Nevada Pale Ale|Lagunitas IPA|Bell's Two Hearted|Jack's Abby House Lager|Night Shift Nite Lite|Downeast Cider|White Claw|
High Noon|Truly|Margarita|Spicy Margarita|Paloma|Old Fashioned|Manhattan|Negroni|Martini|Espresso Martini|Cosmopolitan|
Moscow Mule|Mojito|Daiquiri|Mai Tai|Whiskey Sour|Bloody Mary|Aperol Spritz|Gin & Tonic|Vodka Soda|Rum & Coke|
Long Island Iced Tea|Dark & Stormy|Tom Collins|Sazerac|Boulevardier|Penicillin|Irish Coffee|Pina Colada|Mezcal Margarita|
French 75|Gimlet|Mimosa|Well drink|House cocktail|Red wine|White wine|Rosé|Sparkling wine|Sangria|Hard cider|Hard seltzer|
Shot|Sake""".replace("\n", "").split("|")
ALIASES = {"pbr": "Pabst Blue Ribbon", "pabst": "Pabst Blue Ribbon", "high life": "Miller High Life", "narragansett": "Narragansett Lager",
           "gansett": "Narragansett Lager", "sam adams": "Sam Adams Boston Lager", "boston lager": "Sam Adams Boston Lager",
           "modelo": "Modelo Especial", "corona": "Corona Extra", "michelob ultra light": "Michelob Ultra", "mich ultra": "Michelob Ultra",
           "stella": "Stella Artois", "kirin": "Kirin Ichiban", "asahi super dry": "Asahi", "well": "Well drink", "well drinks": "Well drink",
           "rose": "Rosé", "rosé wine": "Rosé", "prosecco": "Sparkling wine", "champagne": "Sparkling wine", "cider": "Hard cider",
           "seltzer": "Hard seltzer", "gin and tonic": "Gin & Tonic", "rum and coke": "Rum & Coke", "dark and stormy": "Dark & Stormy",
           "piña colada": "Pina Colada", "signature cocktail": "House cocktail", "cocktail": "House cocktail"}


def key(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9&]+", " ", t).strip()


CANON_BY_KEY = {key(c): c for c in CANON}
CANON_BY_KEY.update({key(a): c for a, c in ALIASES.items()})


def num(x, lo, hi):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and lo <= x <= hi else None


# Menus the research flagged as clearly out of date: their old, low prices would otherwise win "cheapest" on the map.
STALE = {
    "v-naco-taco": "only priced drink menu is a July 2021 PDF",
    "v-ole-mexican-grill": "only source is a 2019 menu image",
    "v-la-fabrica-central": "undated SinglePlatform listing with 2016-2020 wine vintages",
    "v-pho-basil": "undated SinglePlatform listing with very old prices",
    "v-india-quality-restaurant": "undated menu with stale-looking prices",
    "v-flat-top-johnny-s": "2011-2013 drink page; the address is now Alice & Monarch, so the bar looks closed",
}
# The Paramount (Beacon Hill) has a beer-and-wine license: its "cocktails" are made with wine-based stand-ins.
WINE_COCKTAILS = {"v-the-paramount-beacon-hill"}

venue_ids = set()
for v in json.load(open(os.path.join(ROOT, "data", "venues.json"), encoding="utf-8")):
    s = unicodedata.normalize("NFKD", v["name"]).encode("ascii", "ignore").decode()
    venue_ids.add("v-" + re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60])

menus, dropped = {}, collections.Counter()
for f in sys.argv[1:]:
    for m in json.load(open(f, encoding="utf-8")):
        vid = m.get("venue_id")
        if vid not in venue_ids:
            print("skip unknown venue:", vid, m.get("name"))
            continue
        if vid in STALE:
            print(f"skip stale menu: {vid} ({STALE[vid]})")
            continue
        items, seen = [], set()
        for it in m.get("items") or []:
            price = num(it.get("price"), 0.5, 100)
            name = re.sub(r"\s+", " ", str(it.get("name") or "")).strip()
            kind = it.get("kind")
            if not price or not name or kind not in KINDS:
                dropped["invalid"] += 1
                continue
            t = re.sub(r"\s+", " ", str(it.get("type") or name)).strip()
            if vid in WINE_COCKTAILS and kind == "mixed":
                kind, t = "wine", "Wine cocktail"
            # Canned ready-to-drink cocktails sit with hard seltzers, so a bar-made drink stays the map's "cheapest mixed drink".
            if kind == "mixed" and (it.get("serve") == "can" or re.search(r"\b(sun ?cruiser|surfside|lucky one|long drink|rtd)\b", name, re.I)):
                kind, t = "other", "Canned cocktail"
            # Wine-based drinks count as wine, not mixed drinks.
            if kind == "mixed" and (key(t) in ("mimosa", "sangria") or re.search(r"\bsangria\b|\bmimosa\b", name, re.I)):
                kind = "wine"
            sig = (name.lower(), it.get("oz"), price)
            if sig in seen:
                dropped["duplicate"] += 1
                continue
            seen.add(sig)
            items.append({"name": name[:80], "type": CANON_BY_KEY.get(key(t), t)[:60], "kind": kind,
                          "serve": it.get("serve") if it.get("serve") in SERVES else None,
                          "oz": num(it.get("oz"), 1, 64), "price": round(float(price), 2)})
        srcs = [u for u in (m.get("menu_sources") or []) if isinstance(u, str) and u.startswith("https://")]
        date = m.get("menu_date") if re.fullmatch(r"\d{4}-\d{2}", str(m.get("menu_date"))) else "unknown"
        if vid in menus and len(menus[vid]["items"]) >= len(items):
            continue
        menus[vid] = {"venue_id": vid, "name": m.get("name"), "menu_sources": srcs[:5], "menu_date": date,
                      "items": items, "notes": m.get("notes") or ""}

# one spelling per non-canonical type: the most common one across venues
spell = collections.defaultdict(collections.Counter)
for m in menus.values():
    for it in m["items"]:
        spell[key(it["type"])][it["type"]] += 1
for m in menus.values():
    for it in m["items"]:
        it["type"] = spell[key(it["type"])].most_common(1)[0][0]

out = sorted(menus.values(), key=lambda m: m["venue_id"])
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
n_items = sum(len(m["items"]) for m in out)
types = collections.Counter(it["type"] for m in out for it in m["items"])
print(f"{len(out)} venues ({sum(1 for m in out if m['items'])} with items), {n_items} items, {len(types)} drink types; dropped {dict(dropped)} -> {OUT}")
print("most common types:", ", ".join(f"{t} ({n})" for t, n in types.most_common(25)))
missing = sorted(venue_ids - {m["venue_id"] for m in out if m["items"]})
print(f"{len(missing)} venues without a priced menu:", ", ".join(missing))
