# TabFriendly

A mobile-friendly map of the cheapest beer and mixed drink at bars and restaurants in Boston and Cambridge
(plus the original 2 miles around MIT, 77 Massachusetts Ave). Live at https://tabfriendly-app.vercel.app/; the claude.ai artifact is the dev copy.
Prices start from published menus, and students keep them current by reporting what they paid.

**Live app:** https://claude.ai/artifact/QcmT22SRxJQFA8iM6xHRME (a claude.ai artifact; open it signed in to claude.ai)

Scope and decisions are in [SPEC.md](SPEC.md). `app/` matches the live version.

## How it works

- `app/index.html` is the whole app: Leaflet (from cdnjs) on a street map drawn from OpenStreetMap data, with no map tiles.
  Artifacts block outside images, so the streets ship as `app/basemap.json`.
- Venues and prices live in the artifact's shared database:
  - `venues/{id}`: name, type, address, lat/lng, website, note
  - `reports/{id}`: one price report with drink, price, oz, source, and date. Without `menu`, it's a cheapest beer or mixed drink report (`kind` is `beer` or `mixed`): the newest fresh one that isn't hidden is the current price, and older reports form the history. With `menu: true`, it's anyone's menu entry (`kind` beer, mixed, wine or other, plus `type`, `serve`, and `target`, the menu drink it updates, or null for a new drink); the newest version of each drink wins.
  - `menus/{venueId}`: the venue's researched drink menu (`items` with name, type, kind, serve, oz, price, plus `sources` and `sourceDate`; `serve` "pitcher", or "bottle" on a wine, marks a size to share). Only editors can write here.
  - `menuEdits/{id}`: one editor change to a menu (an added drink, or a change to or removal of a researched one). Only editors can write here.
  - `hours/{venueId}`: regular weekly hours (`hours: {mon: "11:30-14:30,17:00-02:00", ..., sun: "closed"}`, `source`, `checked`). Only editors can write here.
  - `photos/{id}`: menu photos (downscaled JPEG data URLs) tied to a venue
  - `votes/{userId}`: each person's 👍/👎 on user-reported prices; only they can change it
  - `mod/{reportId or venueId}`: `{hidden: true}`. Only editors can write here, so it works as the rollback switch for wrong prices or fake venues.
- Who can do what:
  - Contributors can post prices, add venues and menu photos, and vote.
  - Viewers and people outside the organization can only read.
  - Editors can also hide or delete prices and venues, and edit drink menus.
- Prices count for six months: user and editor entries from when they were posted, researched prices from their menu's date, or from when we checked an undated menu.
- `data/live/` is a snapshot of the live database (venues, reports, menus, menuEdits, hours), refreshed Oct 13, 2026, without user ids, photos or votes.

## Data pipeline

```
python tools/merge_research.py <dir with kendall/central/backbay/kenmore.json>   # -> data/venues.json (original 1-mile research)
python tools/add_research.py [--keep-unpriced] <research.json> ...               # append venues inside 2 mi that aren't listed yet
python tools/fixups.py                                                           # manual corrections
python tools/merge_menus.py data/menus.json <menus_*.json>                         # full drink menus -> data/menus.json
python tools/merge_share.py <share_*.json>                                       # pitchers and bottles of wine -> data/menus.json
python tools/merge_hours.py <hours_*.json | research.json> ...                    # opening hours -> data/hours.json
python tools/make_seed.py                                                        # -> data/seed/* (one JSON per db doc)
python tools/review_sheet.py                                                     # -> data/venues_review.csv
```

Seed documents are written to the artifact database with Claude's `ArtifactData` batch tool, using `data/seed/batches.json`.
That file only holds documents that aren't in the `data/live/` snapshot, so edits made in the app are never overwritten.
Refresh the snapshot before seeding.
`tools/seed_against_live.py` also matches research venues to live ones by name and location, which catches the same place under a different id.

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

## Hosting on Supabase + Vercel

The same `app/` runs outside claude.ai: `app/supa-db.js` provides the app's database and user API on Supabase
(Postgres tables of `{id, data}`, Realtime for live updates, Auth for identity). On claude.ai that file does nothing.

- **Contributors** never sign in: the site gives each browser a silent anonymous Supabase session, so votes, "your report"
  and posting limits still work. At most 20 new venues, prices and photos per person per hour.
- **Editors** tap **Editor** in the header and get an email sign-in link. Only emails listed in `public.editors` can
  hide, delete, or edit menus and hours.

One-time setup:

1. Supabase project `brcwtiffgiojqnmfvaui` (URL and anon key are in `app/supa-db.js`; the anon key is public by design).
2. **Authentication → Sign In / Providers:** turn on **Allow anonymous sign-ins**.
3. **SQL Editor:** run `supabase/schema.sql`, then add editors:
   `insert into public.editors (email) values ('you@mit.edu') on conflict do nothing;`
4. Load the data: `python tools/export_supabase.py <dump dir>` writes `supabase/data/01.sql`, `02.sql`, ...;
   run them in order in the SQL Editor. (The dump is the claude.ai database exported per collection; these files hold
   user posts and photos, so they're git-ignored.)
5. **Vercel:** import the GitHub repo, set **Root Directory** to `app`, no build command. Every push to `main` deploys.
6. **Authentication → URL Configuration:** set **Site URL** to the Vercel address (e.g. `https://tabfriendly.vercel.app`)
   and add it to **Redirect URLs**, so editors' sign-in links land on the site.
