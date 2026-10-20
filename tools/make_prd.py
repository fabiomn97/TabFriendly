"""Build docs/TabFriendly_PRD_Final.pdf, the final product requirements document, in the style of Product Brief v2.

Usage: python tools/make_prd.py   (needs reportlab; uses the Windows Cambria and Calibri fonts)
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle, Flowable)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "TabFriendly_PRD_Final.pdf")
FONTS = r"C:\Windows\Fonts"
for name, f in [("Serif-Bold", "cambriab.ttf"), ("Sans", "calibri.ttf"), ("Sans-Bold", "calibrib.ttf"),
                ("Sans-Italic", "calibrii.ttf")]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FONTS, f)))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Italic", boldItalic="Sans-Bold")

RED = colors.HexColor("#A31F34")
INK = colors.HexColor("#222326")
MUTED = colors.HexColor("#6B6F76")
LINE = colors.HexColor("#E3DFDA")
BEIGE = colors.HexColor("#F6F3EF")
GREEN = colors.HexColor("#2E7D4F")
AMBER = colors.HexColor("#B26A00")
DATE = "October 19, 2026"
AUTHORS = "José Mariano Martinez  ·  Fabio Macedo  ·  Zion Moore"

def ss(**k):
    return ParagraphStyle("x", **{"fontName": "Sans", "fontSize": 10, "leading": 14, "textColor": INK, "alignment": TA_LEFT, **k})
BODY = ss()
SMALL = ss(fontSize=8.5, leading=11.5, textColor=MUTED)
CELL = ss(fontSize=9, leading=12)
CELLM = ss(fontSize=9, leading=12, textColor=MUTED)
CELLB = ss(fontSize=9, leading=12, fontName="Sans-Bold")
HEAD = ss(fontSize=7.5, leading=10, textColor=MUTED, fontName="Sans-Bold")
TITLE = ss(fontName="Serif-Bold", fontSize=34, leading=38)
SUB = ss(fontName="Sans-Bold", fontSize=12, leading=16, textColor=RED)
SEC = ss(fontName="Serif-Bold", fontSize=15, leading=19)
LEAD = ss(fontSize=10.5, leading=15)
NOTE = ss(fontName="Sans-Italic", fontSize=8, leading=11, textColor=MUTED)


def P(t, s=BODY):
    return Paragraph(t, s)


class Rule(Flowable):
    def __init__(self, w=7 * inch, color=LINE, t=0.6):
        super().__init__()
        self.w, self.color, self.t = w, color, t
        self.height = 4

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.t)
        self.canv.line(0, 2, self.w, 2)


class Chip(Flowable):
    """A small rounded status label, like the NEW / EXTENDS chips of brief v2."""
    STYLE = {"LIVE": (GREEN, colors.white), "DONE": (GREEN, colors.white), "TO DO": (AMBER, colors.white),
             "DROPPED": (MUTED, colors.white), "NEW": (RED, colors.white), "TO RUN": (AMBER, colors.white),
             "MET": (GREEN, colors.white), "OPEN": (AMBER, colors.white)}

    def __init__(self, text):
        super().__init__()
        self.text = text
        self.width, self.height = 46, 13

    def draw(self):
        bg, fg = self.STYLE[self.text]
        c = self.canv
        c.setFillColor(bg)
        c.roundRect(0, 0, self.width, self.height, 6.5, stroke=0, fill=1)
        c.setFillColor(fg)
        c.setFont("Sans-Bold", 7)
        c.drawCentredString(self.width / 2, 3.8, self.text)


class Timeline(Flowable):
    """Three stops: version 1, version 2, final (current)."""

    def __init__(self, stops):
        super().__init__()
        self.stops = stops
        self.width, self.height = 7 * inch, 0.95 * inch

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(BEIGE)
        c.roundRect(0, 0, w, h, 8, stroke=0, fill=1)
        y = h - 22
        xs = [24, w / 2, w - 24]
        c.setStrokeColor(colors.HexColor("#B9B4AE"))
        c.setLineWidth(1.2)
        c.line(xs[0], y, xs[2], y)
        for i, (x, (label, value, current)) in enumerate(zip(xs, self.stops)):
            c.setFillColor(colors.white)
            c.setStrokeColor(RED if current else INK)
            c.circle(x, y, 7 if current else 5.5, stroke=1, fill=1)
            c.setFillColor(RED if current else INK)
            c.circle(x, y, 3.5 if current else 2.5, stroke=0, fill=1)
            align = [c.drawString, c.drawCentredString, c.drawRightString][i]
            c.setFont("Sans-Bold", 7)
            c.setFillColor(MUTED)
            align(x - (6 if i == 0 else 0) + (6 if i == 2 else 0), y - 22, label)
            c.setFont("Sans-Bold", 11.5)
            c.setFillColor(RED if current else INK)
            align(x - (6 if i == 0 else 0) + (6 if i == 2 else 0), y - 38, value)


def section(n, title):
    return KeepTogether([Spacer(1, 10), Table([[P(f'<font color="#A31F34">{n:02d}</font>', SEC), P(title, SEC)]],
                                              colWidths=[0.42 * inch, 6.58 * inch],
                                              style=[("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]),
                         Rule(), Spacer(1, 6)])


def grid(rows, widths, header=None, zebra=True):
    data = ([[P(h, HEAD) for h in header]] if header else []) + rows
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
          ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
          ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE)]
    if header:
        st.append(("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#C9C4BE")))
    if zebra:
        for i in range(1 if header else 0, len(data), 2):
            st.append(("BACKGROUND", (0, i), (-1, i), BEIGE))
    return Table(data, colWidths=widths, style=st, repeatRows=1 if header else 0)


def page(c, doc):
    c.saveState()
    c.setFillColor(RED)
    c.rect(0, letter[1] - 6, letter[0], 6, stroke=0, fill=1)
    c.setFont("Sans-Bold", 7.5)
    c.setFillColor(MUTED)
    c.drawString(0.75 * inch, letter[1] - 0.45 * inch, "TAB FRIENDLY  ·  PRODUCT REQUIREMENTS  ·  FINAL")
    c.drawRightString(letter[0] - 0.75 * inch, letter[1] - 0.45 * inch, f"{doc.page:02d}")
    c.setStrokeColor(LINE)
    c.line(0.75 * inch, 0.62 * inch, letter[0] - 0.75 * inch, 0.62 * inch)
    c.setFont("Sans", 7.5)
    c.drawString(0.75 * inch, 0.45 * inch, f"AI Builder Space Proseminar  ·  {DATE}")
    c.drawRightString(letter[0] - 0.75 * inch, 0.45 * inch, AUTHORS)
    c.restoreState()


story = []
story += [P("Tab Friendly", TITLE), Spacer(1, 4),
          P('Product Requirements  ·  Final', SUB), Spacer(1, 3),
          P(f"AI Builder Space Proseminar  ·  {AUTHORS}", ss(fontSize=9.5, textColor=MUTED)), Spacer(1, 2),
          P(f"{DATE.upper()}   ·   REPLACES PRODUCT BRIEF v2 OF OCTOBER 8, 2026", ss(fontSize=7.5, fontName="Sans-Bold", textColor=MUTED)),
          Spacer(1, 10)]
summary = Table([[P(
    "Tab Friendly is a mobile-friendly web app that maps bars and restaurants by the price of their cheapest drinks, so "
    "college and graduate students can plan a night out around what they want to spend. <b>The final version is live at "
    "tabfriendly.fabio.cool</b>: it covers all of Boston and Cambridge (about 500 venues), hides any price older than six "
    "months, lets anyone add or fix a price without signing in, shows opening hours, ranks by total price or price per ounce "
    "and by portion size, opens on what is around you, and rewards contributors with a leaderboard. This document records "
    "what shipped, what was dropped, and what is still to do.", LEAD)]],
    colWidths=[7 * inch], style=[("BACKGROUND", (0, 0), (-1, -1), BEIGE), ("LEFTPADDING", (0, 0), (-1, -1), 14),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, -1), 11),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 12), ("LINEBEFORE", (0, 0), (0, -1), 3, RED)])
story += [summary]

story += [section(1, "The Idea &amp; The User"),
          P("The app maps bars and restaurants in Boston and Cambridge and labels each one with its cheapest drinks and their "
            "prices, so users can see where they can afford to drink and plan their night around it. It starts from menu and "
            "price information already published online, and users fill in missing prices or correct outdated ones, so the map "
            "keeps itself current."), Spacer(1, 5),
          P("It is built for college and graduate students aged 21 and over who want to keep the cost of a night out low and "
            "know what they will spend before choosing where to go. The idea and the user have not changed since the first brief.")]

story += [section(2, "Where we are"),
          grid([
              [P("Coverage", CELLB), P("At least 2 miles of 77 Massachusetts Ave; final version all of Cambridge + Boston", CELLM),
               P("<b>All of Boston and Cambridge</b>, plus the original 2 miles around 77 Mass Ave (parts of Somerville and Brookline): 497 venues", CELL)],
              [P("Hosting &amp; access", CELLB), P("Claude artifact; Contributor access on claude.ai", CELLM),
               P("<b>tabfriendly.fabio.cool</b> on Vercel + Supabase. Anyone can post without signing in; accounts are optional. "
                 "The claude.ai artifact stays as the team's dev copy", CELL)],
              [P("Prices per venue", CELLB), P("Cheapest beer, cheapest mixed drink, researched full menu", CELLM),
               P("Same, plus full menus at 291 venues: 15,100+ priced drinks, including 129 pitchers and 2,800 bottles of wine", CELL)],
              [P("Rankings &amp; filters", CELLB), P("Drinks filter, beer / mixed / overall, max price", CELLM),
               P("Adds a per-ounce toggle, a Size filter (personal pours vs. to share) and a list that follows the map around you", CELL)],
              [P("Freshness", CELLB), P("Proposed: six months", CELLM),
               P("Live: older prices leave the map, menus, Drinks filter and rankings", CELL)],
              [P("Hours", CELLB), P("Proposed: weekly hours, open now", CELLM),
               P("393 venues with weekly hours, an open-now badge and an \"hours may vary\" note", CELL)],
              [P("Submissions", CELLB), P("Report a cheapest price; editors-only menus", CELLM),
               P("Anyone adds or edits any menu item; votes, \"Disputed\" label; accounts, points and a leaderboard; 20 posts an hour per person", CELL)],
              [P("Moderation", CELLB), P("Editors hide, restore and delete", CELLM),
               P("Same, with editors signing in by email link and listed in the database", CELL)],
          ], [1.25 * inch, 2.3 * inch, 3.45 * inch], header=["AREA", "BRIEF v2  ·  OCT 8", "LIVE  ·  OCT 19"]),
          Spacer(1, 4),
          P("Sources: SPEC.md and README.md in github.com/fabiomn97/TabFriendly; the live database on October 19, 2026.", NOTE)]

story += [section(3, "Requirements and status"),
          Timeline([("VERSION 1  ·  OCT 6", "1.5 miles of MIT", False), ("VERSION 2  ·  OCT 13", "2 miles of MIT", False),
                    ("FINAL  ·  OCT 19", "All of Boston + Cambridge", True)]),
          Spacer(1, 8)]
reqs = [
    ("Menu entry from the app", "LIVE", "Anyone can add a drink to a venue's menu from its card: name, type, serving, pour size and price. "
     "Entries are labeled \"user-reported\" with a date and feed the Drinks filter and the cheapest-price ranking."),
    ("Edit any price", "LIVE", "Anyone can change the price of any menu item or the cheapest beer and mixed drink. The newest entry wins, "
     "every change is dated, and editors can remove or restore items."),
    ("Freshness: six months", "LIVE", "A price counts for six months from its menu date, or from the date we checked it when the menu is "
     "undated. Older prices leave the map and rankings; a venue with none shows a gray \"?\" pin."),
    ("Opening hours", "LIVE", "Weekly hours on each card with an \"Open now · until 1am\" badge, open-now tags in the list, and "
     "\"Hours may vary on holidays\". Researched for 393 venues."),
    ("Per ounce vs total price", "LIVE", "A toggle ranks by price per ounce instead of total price. Drinks without a known pour size are "
     "left out and their venues marked \"oz?\"."),
    ("Portion sizes", "LIVE", "A Size button next to Choose drinks: glass, bottle, draft and can for one person, or a bottle of wine "
     "and a pitcher to share. Rankings, filters and cards follow the choice. <i>Added after brief v2.</i>"),
    ("Coverage: Boston + Cambridge", "LIVE", "The map, its outline and new-venue checks cover both cities plus the original 2-mile circle. "
     "192 venues were researched beyond 2 miles, 101 of them with full menus including pitchers and bottles of wine; Logan airport bars past security are left out."),
    ("Near you", "LIVE", "The map asks for location as it opens and zooms to about 6-7 blocks around the person. Every pin stays on the "
     "map; the list and the green top 3 follow the view. <i>Added after brief v2.</i>"),
    ("Accounts &amp; leaderboard", "LIVE", "Optional email-link accounts with display names; a browser's anonymous posts carry over. Points "
     "are held until others confirm a price and scaled by trust, with bounties, first-price and stale-update bonuses, check-ins, "
     "weekly and monthly boards by neighborhood, and bar mayors. <i>Added after brief v2.</i>"),
    ("Production hosting", "LIVE", "Vercel serves the app; Supabase stores the data with row-level security, live updates and a posting "
     "limit. Contributors get a silent anonymous session; editors sign in by email link. Changes go to both the live site and the "
     "claude.ai dev copy."),
    ("Happy hours toggle", "DROPPED", "Dropped in the v2 sprint: Massachusetts has banned drink discounts since 1984, so venues publish "
     "almost no time-limited prices."),
]
story.append(grid([[P(f'<font color="#A31F34"><b>{i}</b></font>', CELL), P(t, CELLB), Chip(s), P(d, CELL)]
                   for i, (t, s, d) in enumerate(reqs, 1)],
                  [0.3 * inch, 1.6 * inch, 0.8 * inch, 4.3 * inch]))
story += [Spacer(1, 8), P("OUT OF SCOPE", HEAD), Spacer(1, 3),
          grid([[P("<b>Filter by bar versus restaurant</b><br/>Still deferred.", CELL),
                 P("<b>Venues outside Boston and Cambridge</b><br/>Except the parts of Somerville and Brookline inside the original 2-mile circle.", CELL)]],
               [3.5 * inch, 3.5 * inch], zebra=False)]

story += [section(4, "Waiting to be done"),
          grid([
              [P("Custom domain", CELLB), P("In Cloudflare, switch the tabfriendly record to DNS only (grey cloud) so Vercel manages the certificate. The site already works through the proxy.", CELL), P("Fabio", CELLM)],
              [P("Research follow-up", CELLB), P("About 60 places were dropped unverified when web searches ran out, including known bars such as Shenannigans, The Playwright, L Street Tavern, Murphy's Law and Tom English's. 91 of the 192 venues beyond 2 miles publish no priced menu online, so they rely on user reports; discovery in Hyde Park and Mattapan is thin.", CELL), P("Next research pass", CELLM)],
              [P("Venue status checks", CELLB), P("Champions, DX Arcade, Marliave and Sidebar may be closed, and Trillium Garden on the Greenway reportedly lost its lease for 2026. Two unbranded \"$2 beer all day\" claims (Sissy K's, Wild Rover) are left off the rankings pending a check.", CELL), P("Editors", CELLM)],
              [P("Price refresh plan", CELLB), P("Researched prices from undated menus checked in October 2026 expire in April 2027. Plan a re-check before then.", CELL), P("Team", CELLM)],
              [P("Leaderboard placeholders", CELLB), P("GPS on-site bonus and the Places check are not built yet.", CELL), P("Zion", CELLM)],
              [P("Dev and live data", CELLB), P("The claude.ai dev copy and Supabase keep separate databases, and the dev copy has no leaderboard backend. Decide whether to reseed dev from live.", CELL), P("Team", CELLM)],
              [P("Bot protection", CELLB), P("Optional: add Cloudflare Turnstile to anonymous sign-in if spam appears.", CELL), P("Team", CELLM)],
              [P("Pass/fail tests", CELLB), P("Run the outside-tester checks in section 05.", CELL), P("Team", CELLM)],
          ], [1.45 * inch, 4.4 * inch, 1.15 * inch], header=["ITEM", "WHAT'S LEFT", "OWNER"])]

story += [section(5, "Success"),
          grid([[P("<font color='#A31F34' size='22'><b>6 months</b></font>", ss(leading=26)),
                 P("<b>Maximum age of any price shown.</b> The v1 bar of 25 venues with a sourced cheapest-beer price is far "
                   "exceeded: 227 venues have one. Each check below should pass before the course demo.", CELL)]],
               [1.6 * inch, 5.4 * inch], zebra=False),
          Spacer(1, 6),
          grid([
              [P("Freshness", CELLB), P("A price older than six months disappears from the map and rankings; its venue shows a gray \"?\" pin.", CELL), Chip("TO RUN")],
              [P("Menu entry", CELLB), P("A tester outside the team adds a drink in the app; it appears on the card and in the Drinks filter.", CELL), Chip("TO RUN")],
              [P("Price edit", CELLB), P("A tester changes an existing menu price; the new price shows with the date of the change.", CELL), Chip("TO RUN")],
              [P("Per ounce", CELLB), P("With the toggle on, the three green pins match a hand-ranked list of venues with known pour sizes.", CELL), Chip("TO RUN")],
              [P("Hours", CELLB), P("Opening hours match venue websites in a spot check of 10 venues.", CELL), Chip("TO RUN")],
              [P("Range", CELLB), P("Every researched venue in Boston, Cambridge or the 2-mile circle appears on the map (497 loaded).", CELL), Chip("MET")],
              [P("Sizes", CELLB), P("\"To share\" ranks pitchers and bottles of wine; personal sizes leave them out.", CELL), Chip("MET")],
              [P("Near you", CELLB), P("Opening the site zooms to the person; zooming out keeps every pin and widens the list.", CELL), Chip("MET")],
          ], [1.1 * inch, 5.15 * inch, 0.75 * inch], header=["CHECK", "TEST", "STATUS"]),
          Spacer(1, 4),
          P("MET: verified by the team with a test copy of the app. TO RUN: built, waiting on the outside-tester check.", NOTE)]

story += [section(6, "Risks and open questions")]
risks = [
    ("Bad data with open posting.", "Anyone can post without an account. Defenses are votes and the \"Disputed\" label, editors who hide "
     "entries, a limit of 20 posts an hour per person, and leaderboard trust scores that weigh unconfirmed posts less."),
    ("Uneven research coverage.", "Busy areas have many priced venues while Hyde Park, Mattapan and parts of Dorchester have few. Gray "
     "pins invite users to fill gaps, and the leaderboard pays bounties for them."),
    ("Prices aging out.", "Most researched prices expire together in April 2027. Without a re-check the map will thin out suddenly."),
    ("Per ounce needs pour sizes.", "Menus often omit sizes, so the per-ounce view ranks fewer venues than the total-price view."),
    ("Hours go stale.", "Holidays and one-off closures will not show; the card says hours may vary."),
    ("Inferred share-size prices.", "Some wine lists print two unlabeled prices; we took the larger as the bottle price, noted per venue."),
    ("Two databases.", "The dev copy and the live site drift apart over time. Editors must work on the live site."),
]
story.append(grid([[P(f'<font color="#A31F34"><b>{i:02d}</b></font>', CELL), P(f"<b>{t}</b> {d}", CELL)] for i, (t, d) in enumerate(risks, 1)],
                  [0.4 * inch, 6.6 * inch], zebra=False))
story += [Spacer(1, 6), P("Sources: SPEC.md and README.md in the TabFriendly repo; the live Supabase database and app on October 19, 2026; "
                          "Product Brief v2 (October 8, 2026).", NOTE)]

os.makedirs(os.path.dirname(OUT), exist_ok=True)
doc = BaseDocTemplate(OUT, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.7 * inch,
                      bottomMargin=0.8 * inch, title="Tab Friendly - Product Requirements (Final)",
                      author="José Mariano Martinez, Fabio Macedo, Zion Moore", subject="Final PRD, AI Builder Space Proseminar")
doc.addPageTemplates([PageTemplate(frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")], onPage=page)])
doc.build(story)
print(OUT)
