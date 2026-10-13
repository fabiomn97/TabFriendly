"""Manual corrections applied to data/venues.json after merging research. Re-runnable."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "venues.json")
v = json.load(open(P, encoding="utf-8"))

# Pagu was found by two agents with different geocodes; 310 Mass Ave matches the Central entry.
v = [x for x in v if x["name"] != "Pagu (Kendall)"]
# The Cellar's only prices ($2.50 PBR) come from a long-stale SinglePlatform listing; leave it for users to add.
v = [x for x in v if x["name"] != "The Cellar"]
# Closed (checked Oct 13, 2026): Grotto (lease ended Aug 2025), Mother Anna's (listed permanently closed),
# Guy Fieri's Boston Kitchen (shut down); Courtside, Beacon Hill Pub, Delux Cafe and Pho Basil look closed (no current
# presence; Pho Basil's domain is parked).
CLOSED = {"Grotto Restaurant", "Mother Anna's", "Guy Fieri's Boston Kitchen + Bar", "Courtside Restaurant & Pub",
          "Beacon Hill Pub", "Delux Cafe", "Pho Basil"}
v = [x for x in v if x["name"] not in CLOSED]
RENAME = {
    "Pagu (Central)": "Pagu",
    "Brick & Mortar (Acqua & Bocca rebrand an": "Brick & Mortar",
}
NOTES = {  # shown to users on the venue card
    "The Muddy Charles Pub": "MIT ID required (affiliates and their guests). Cash only.",
    "Thirsty Ear Pub": "MIT ID required (affiliates and their guests).",
    "Sweet Cheeks Q": "Closing after Nov 24, 2026.",
    "Paradise Rock Club": "Music venue: the bars usually need a show ticket.",
    "Scullers Jazz Club": "Jazz club: usually needs a show ticket.",
    "Over the Charles Rooftop Bar (DoubleTree Suites)": "Seasonal rooftop (about June to October).",
}
# Tasty Burger's chain menu lists "PBR Lager $5" under Tallboys with no size; the 19.2 oz in the research was a guess.
for x in v:
    if x["name"] == "Tasty Burger Fenway" and x.get("beer"):
        x["beer"].update({"name": "PBR Lager (tallboy can)", "oz": None})
for x in v:
    for old, new in RENAME.items():
        if x["name"].startswith(old):
            x["name"] = new
    if x["name"] in NOTES:
        x["venue_note"] = NOTES[x["name"]]
json.dump(v, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(v), "venues")
