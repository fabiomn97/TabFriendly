"""Manual corrections applied to data/venues.json after merging research. Re-runnable."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "venues.json")
v = json.load(open(P, encoding="utf-8"))

# Pagu was found by two agents with different geocodes; 310 Mass Ave matches the Central entry.
v = [x for x in v if x["name"] != "Pagu (Kendall)"]
# The Cellar's only prices ($2.50 PBR) come from a long-stale SinglePlatform listing; leave it for users to add.
v = [x for x in v if x["name"] != "The Cellar"]
RENAME = {
    "Pagu (Central)": "Pagu",
    "Brick & Mortar (Acqua & Bocca rebrand an": "Brick & Mortar",
}
NOTES = {  # shown to users on the venue card
    "The Muddy Charles Pub": "MIT ID required (affiliates and their guests). Cash only.",
    "Thirsty Ear Pub": "MIT ID required (affiliates and their guests).",
}
for x in v:
    for old, new in RENAME.items():
        if x["name"].startswith(old):
            x["name"] = new
    if x["name"] in NOTES:
        x["venue_note"] = NOTES[x["name"]]
json.dump(v, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(v), "venues")
