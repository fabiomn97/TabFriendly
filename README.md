# TabFriendly

A mobile-friendly map of the cheapest beer and mixed drink at bars and restaurants within 1.5 miles of MIT (77 Massachusetts Ave).
Prices start from published menus, and students keep them current by reporting what they paid.

**Live app:** https://claude.ai/artifact/QcmT22SRxJQFA8iM6xHRME (a claude.ai artifact; open it signed in to claude.ai)

Scope and decisions are in [SPEC.md](SPEC.md).

## How it works

- `app/index.html` is the whole app: Leaflet (from cdnjs) on a street map drawn from OpenStreetMap data, with no map tiles.
  Artifacts block outside images, so the streets ship as `app/basemap.json`.
- Venues and prices live in the artifact's shared database:
  - `venues/{id}`: name, type, address, lat/lng, website, note
  - `reports/{id}`: one price report (`kind` is `beer` or `mixed`) with drink, price, oz, source, and date. The newest report that isn't hidden is the current price, and older reports form the history.
  - `photos/{reportId}`: optional menu photo (a downscaled JPEG data URL)
  - `mod/{reportId or venueId}`: `{hidden: true}`. Only editors can write here, so it works as the rollback switch for wrong prices or fake venues.
- Who can do what:
  - Contributors can post prices and add venues.
  - Viewers and people outside the organization can only read.
  - Editors also get "Hide as wrong" and "Hide this venue".

## Data pipeline

```
python tools/merge_research.py <dir with kendall/central/backbay/kenmore.json>   # -> data/venues.json
python tools/fixups.py                                                           # manual corrections
python tools/merge_menus.py <menus_*.json>                                       # full drink menus -> data/menus.json
python tools/make_seed.py                                                        # -> data/seed/* (one JSON per db doc)
python tools/review_sheet.py                                                     # -> data/venues_review.csv
```

Seed documents are written to the artifact database with Claude's `ArtifactData` batch tool, using `data/seed/batches.json`.

To rebuild the basemap:

```
python tools/basemap_fetch.py && python tools/basemap_build.py app/basemap.json
```

## Local testing

```
python tools/dev_harness.py
python -m http.server 8765 --directory app
```

Then open http://localhost:8765/_dev.html. It runs the app against an in-memory mock of the database, seeded from `data/seed`.
Add `?viewer` to the URL to see the read-only view.

Map data © OpenStreetMap contributors (ODbL).
