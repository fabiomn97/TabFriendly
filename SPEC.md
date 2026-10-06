# TabFriendly — Spec

Source: *TabFriendly Product Brief* (Oct 2, 2026), refined by the team interview and follow-up requests on Oct 5–6, 2026.
Where this spec and the brief differ, this spec wins. **This describes the final version.**

## Product
A mobile-friendly web app, hosted as a claude.ai artifact, that maps bars and restaurants
within **1.5 miles of 77 Massachusetts Ave** and labels each with its cheapest drinks.
Audience: college and graduate students aged 21+.

## Per-venue data
| Field | Detail |
|---|---|
| Cheapest beer | brand/name, how it's served (draft, bottle or can), price, pour size (oz), price per oz (calculated) |
| Cheapest mixed drink | name, type (well drink or cocktail), price. **Mixed drinks only**, no straight shots |
| Full drink menu | researched menu per venue (beer, mixed drinks, wine, cider/seltzer/cans/shots) with regular prices. Editors can add, change or remove drinks |
| Menu photos | uploaded by users and shown at the bottom of the venue card |

Each price records its source (a URL, "user-reported", or "editor") and the date it was checked or submitted.
A user's report is the latest word on a price. Otherwise the venue's menu sets the cheapest beer or mixed drink,
and the researched cheapest price fills in where there's no menu.

## Map and list
- A toggle switches between **Cheapest beer**, **Cheapest drink** (mixed), and **Overall** (whichever is lower).
- A **Drinks** filter lets people search for and tick specific drinks (e.g. Coors Light, margarita). Each venue then shows its cheapest ticked drink.
- A **Max price** slider hides venues above the chosen price.
- Each pin shows the price for the current view. The **three cheapest** are green. Unpriced venues show as gray `?` pins.
- Crowded pins collapse to dots. The selected pin expands to show the drink name.
- Distances are measured from 77 Mass Ave.

## Submissions
- **Instant, latest wins.** A new price appears right away, labeled "user-reported" with its date.
- The update form opens filled in with the current price, so people only change what's different.
- Form: **drink name** and **price** are required. Serving type, pour size (beer), note and menu photo are optional.
- Other users can mark a user-reported price 👍 or 👎. More 👎 than 👍 shows it as "Disputed".
- Anyone with Contributor access can **add a venue** inside the radius and **add menu photos**.

## Editors
- Hide or restore a price or venue (reversible).
- Delete a single price (the previous one becomes current), or delete a venue with all its prices and photos.
- Edit a venue's full drink menu: add a drink, change one, or remove one (removed drinks can be restored).

## Other
- Simple 21+ click-through gate, shown once per browser.
- Logo: a cardinal-red badge holding a white beer mug, with a "Tab" + "Friendly" wordmark in MIT colors.
- Out of scope: venue-type filters, venues outside the radius, time-of-day pricing.

## Seed data
Venues and prices were researched from published menus. Every price carries a source URL and a date checked.
The team reviews the list in data/venues_review.csv. data/live/ holds a snapshot of the live database.

## Success (original sprint)
- At least **25 venues** show a sourced cheapest-beer price.
- A price entered by a tester outside the team appears correctly on the map.

## Code & hosting
Source and seed data live in this repo. The live app is a claude.ai artifact with a shared database,
and testers need a claude.ai account with Contributor access.
