# TabFriendly — Spec (version 2)

Source: *TabFriendly Product Brief v2* (Oct 8, 2026), which replaces the brief of Oct 2, plus the team's answers to its
open questions on Oct 13, 2026. Where this spec and the brief differ, this spec wins.

## Product
A mobile-friendly web app, hosted as a claude.ai artifact, that maps bars and restaurants
within **2 miles of 77 Massachusetts Ave** and labels each with its cheapest drinks.
The final version will cover all of Cambridge and Boston. Version 2 stops at 2 miles.
Audience: college and graduate students aged 21+.

## Per-venue data
| Field | Detail |
|---|---|
| Cheapest beer | brand/name, how it's served (draft, bottle or can), price, pour size (oz), price per oz (calculated) |
| Cheapest mixed drink | name, type (well drink or cocktail), price. **Mixed drinks only**, no straight shots |
| Full drink menu | researched menu per venue (beer, mixed drinks, wine, cider/seltzer/cans/shots) with regular prices, plus drinks and prices anyone adds from the app |
| Opening hours | regular weekly hours, with an "open now" indicator |
| Menu photos | uploaded by users and shown at the bottom of the venue card |

Each price records its source (a URL, "user-reported", or "editor") and its date.

## Freshness: six months
- A price counts for six months from its date, then leaves the map, the menus, the Drinks filter and the rankings.
- **Which date:** a user's or editor's entry uses when it was posted. A researched price uses the date printed on its menu,
  or, when the menu is undated, the date we checked it.
- A venue with no fresh price shows as a gray `?` pin. Its card says when its last price was and that it's out of date.
- Researched prices from undated menus that we checked in October 2026 expire in April 2027 unless someone re-checks them.

## Map and list
- A toggle switches between **Cheapest beer**, **Cheapest drink** (mixed), and **Overall** (whichever is lower).
- A second toggle ranks by **Total price** or **Per ounce**. Per ounce ranks only drinks with a known pour size.
  Venues whose prices all lack a size show an `oz?` pin and are listed after the ranked ones.
- A **Drinks** filter lets people search for and tick specific drinks (e.g. Coors Light, margarita). Each venue then shows its cheapest ticked drink.
- A **Size** button next to it picks the portions that count. **Just for you:** glass, bottle, draft, can (the default).
  **To share:** a bottle of wine, a pitcher. Rankings, the Drinks filter and the card's cheapest prices use only the ticked sizes;
  with bottles of wine ticked, wine joins Cheapest drink and Overall, and the card adds a "Cheapest bottle of wine". Drinks whose
  pour isn't known count only while all four personal sizes are ticked. The Max price slider goes up to $80 while a share size is on.
  Menus list pitchers and bottles of wine after the personal pours, tagged "to share".
- A **Max price** slider hides venues above the chosen price.
- Each pin shows the price for the current view. The **three cheapest** are green.
- List rows say whether the venue is open now.
- Crowded pins collapse to dots. The selected pin expands to show the drink name.
- Distances are measured from 77 Mass Ave.

## Submissions
- **Instant, latest wins.** A new price appears right away, labeled "user-reported" with its date.
- **Cheapest beer / mixed drink:** the update form opens filled in with the current price, so people only change what's different.
  Drink name and price are required. Serving type, pour size (beer), note and menu photo are optional.
- **Menu entry:** any Contributor can add a drink to a venue's menu (name, type, kind, serving, pour size, price), or change the
  price of any drink already on it. The entry is labeled "user-reported" with its date, and it feeds the Drinks filter and the rankings.
  The newest version of a drink wins.
- Other users can mark a user-reported cheapest price 👍 or 👎. More 👎 than 👍 shows it as "Disputed".
- Anyone with Contributor access can **add a venue** inside the radius and **add menu photos**.

## Opening hours
- Each venue's card shows "Open now · until 1am" or "Closed · opens 4pm", and the weekly hours.
- The card notes: "Hours may vary on holidays. Check the venue before you go."
- Hours come from venue websites, checked October 2026. Only editors can change them, through the data pipeline.

## Editors
- Hide or restore a price, menu entry or venue (reversible).
- Delete a single price (the previous one becomes current), or delete a venue with all its prices and photos.
- Remove a drink from a menu (removed researched drinks can be restored).

## Other
- Simple 21+ click-through gate, shown once per browser.
- Logo: a cardinal-red badge holding a white beer mug, with a "Tab" + "Friendly" wordmark in MIT colors.
- **Out of scope for v2:** the happy-hours / time-limited prices toggle (dropped: Massachusetts bans drink discounts, so there is
  little to show), filtering by bar versus restaurant, and venues beyond 2 miles.

## Seed data
Venues, prices and hours were researched from published menus and venue websites. Every price carries a source URL and a date.
The team reviews the list in data/venues_review.csv. data/live/ holds a snapshot of the live database.

## Success (version 2)
- Every price on the map is dated within the last six months.
- **Freshness:** a price older than six months disappears from the map and rankings, and its venue shows a gray `?` pin.
- **Menu entry:** a tester outside the team adds a drink to a venue's menu, and it appears on the card and in the Drinks filter.
- **Price edit:** a tester changes the price of a menu item, and the new price shows with the date of the change.
- **Per ounce:** with the toggle on, the three green pins match a hand-ranked list of venues with known pour sizes.
- **Hours:** opening hours match venue websites in a spot check of 10 venues.
- **Range:** every researched venue within 2 miles of 77 Mass Ave appears on the map.
- The v1 bar of 25 venues with a sourced cheapest-beer price carries over to the larger radius.

## Code & hosting
Source and seed data live in this repo. The live app is a claude.ai artifact with a shared database,
and testers need a claude.ai account with Contributor access.
