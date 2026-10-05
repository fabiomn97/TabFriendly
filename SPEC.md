# TabFriendly — Sprint Spec

Source: *TabFriendly Product Brief* (Oct 2, 2026), refined by team interview on Oct 5, 2026.
Where this spec and the brief differ, this spec wins.

## Product
A mobile-friendly web app, hosted as a claude.ai artifact, that maps bars and restaurants
within **1 mile of 77 Massachusetts Ave** and labels each with its cheapest drinks.
Audience: college and graduate students aged 21+.

## Per-venue data
| Field | Detail |
|---|---|
| Cheapest beer | price, pour size (oz), price per oz (calculated) |
| Cheapest hard-liquor drink | price only; **mixed drinks only** (well drinks or cocktails, not straight shots) |

This replaces the brief's "three cheapest drinks."
Each price records its source (a URL, or "user-reported") and the date it was checked or submitted.

## Map
- Each pin shows the **cheapest beer price** (for example `$5`).
- Venues with no price show as **gray `?` pins** that prompt users to add a price.
- Tapping a pin opens a venue card with both drinks, their sources and dates, and an "Update price" action.

## Submissions
- **Instant, latest wins.** A new price appears right away, labeled "user-reported" with its date.
- The full submission history is kept so a bad entry can be rolled back.
- Form: **drink name** and **price** are required. **Pour size** (beer), **menu photo** and **note** are optional.
  Price per oz shows only when the pour size is known.
- Users can **add a new venue** by dropping a pin inside the 1-mile radius, then add its prices.

## Other
- Simple 21+ click-through gate, shown once per browser.
- Out of scope: drink-type and venue-type filters, venues outside the radius, time-of-day pricing.

## Seed data
Claude researches the venues in the radius and their published prices. Every price carries a source URL
and a date checked. The team reviews the list before launch.

## Success
- At least **25 venues** in the radius show a sourced cheapest-beer price.
- A price entered by a tester outside the team appears correctly on the map.

## Code & hosting
Source and seed data live in this repo. The live app is a claude.ai artifact with a shared database,
and testers need a claude.ai account with access.
