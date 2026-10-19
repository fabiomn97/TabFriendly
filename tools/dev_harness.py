"""Build app/_dev.html: the app plus an in-memory mock of the claude.ai db/user capabilities, seeded from data/seed.

Serve app/ locally (python -m http.server --directory app) and open /_dev.html to click through the app without claude.ai.
Add ?viewer to the URL to simulate a view-only user. Add ?tf=anon, ?tf=noname or ?tf=acct to try the Supabase build's
accounts and leaderboard with made-up scores (a signed-out browser, a new account, an account with a name).
"""
import glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = {c: {os.path.basename(f)[:-5]: json.load(open(f, encoding="utf-8"))
            for f in glob.glob(os.path.join(ROOT, "data", "seed", c, "*.json"))} for c in ("venues", "reports", "menus", "hours")}
data["mod"], data["photos"], data["votes"] = {}, {}, {}
# A report from another user, so voting can be tried locally.
data["reports"]["dev-other-user"] = {
    "venueId": "v-the-middle-east", "kind": "beer", "drink": "Narragansett Lager", "serve": "draft", "price": 4,
    "oz": 16, "note": "Tuesday night", "hasPhoto": False, "source": "user", "sourceUrl": None, "sourceDate": None,
    "by": "u_other", "at": "2026-10-06T01:00:00.000Z"}
data["votes"]["u_other2"] = {"dev-other-user": 1}

MOCK = """<script>
(function () {
  const data = %s;
  const viewer = location.search.includes("viewer");
  const subs = [];
  const snap = (c, f) => ({ docs: Object.entries(data[c] || {}).filter(([, d]) => !f || d[f[0]] === f[2]).map(([id, d]) => ({ id, exists: true, data: () => d, metadata: {} })) });
  const fire = (c) => subs.filter((s) => s.c === c && s.on).forEach((s) => s.fn(snap(c, s.f)));
  const deny = () => Promise.reject({ code: "invalid_argument", message: "mock: view-only" });
  const coll = (c, f) => {
    const q = {
      where(a, op, b) { return coll(c, [a, op, b]); }, orderBy() { return q; }, limit() { return q; },
      get: async () => snap(c, f),
      onSnapshot(fn) { const s = { c, f, fn, on: true }; subs.push(s); setTimeout(() => fn(snap(c, f)), 60); return () => { s.on = false; }; },
      doc(id) {
        id = id || "m" + Math.random().toString(36).slice(2, 10);
        return {
          id,
          get: async () => ({ exists: !!(data[c] || {})[id], data: () => data[c][id] }),
          set: async (d) => { if (viewer) return deny(); (data[c] = data[c] || {})[id] = d; fire(c); },
          delete: async () => { if (viewer) return deny(); delete data[c][id]; fire(c); },
        };
      },
    };
    return q;
  };
  const db = { collection: coll, doc: (p) => { const [c, id] = p.split("/"); return coll(c).doc(id); } };
  const user = { id: async () => "u_dev", can: async () => !viewer, canEdit: async () => !viewer };
  window.__mock = data;
  const tf = new URLSearchParams(location.search).get("tf");
  if (!tf) { window.claude = { use: async (n) => (n === "db" ? db : n === "user" ? user : null) }; return; }
  // Stand-in for supa-db.js: accounts, and the leaderboard functions with made-up numbers.
  let name = tf === "acct" ? "Pint Hunter" : null;
  const acct = { id: "u_dev", anonymous: tf === "anon", email: tf === "anon" ? null : "dev@mit.edu", pendingEmail: null, editor: !viewer };
  const vids = Object.keys(data.venues);
  const rpc = {
    tf_me: () => ({ account: !acct.anonymous, name, week: 12.5, month: 40, all: 120.3, held: 8, posted: 9, confirmed: 6, rejected: 1, pending: 2,
      recent: [{ at: "2026-10-18T20:00:00Z", what: "confirmed", points: 24, held: false, venue_id: vids[0] },
               { at: "2026-10-18T19:00:00Z", what: "price", points: 2, held: false, venue_id: vids[1] },
               { at: "2026-10-17T22:00:00Z", what: "rejected", points: -5, held: false, venue_id: vids[2] },
               { at: "2026-10-17T21:00:00Z", what: "confirmed", points: 8, held: true, venue_id: vids[3] }] }),
    tf_set_name: (a) => { if (/taken/i.test(a.name)) throw { code: "name_taken" }; name = a.name.trim(); return name; },
    tf_leaderboard: (a) => [["Cheap Pint Hunter", 210.5], ["Kendall Regular", 180], ["Back Bay Barfly", 151.3], ["Muddy Charles Fan", 97]]
      .filter((r, i) => !a.area || i %% 2 === 0).map(([n, p], i) => ({ rank: i + 1, name: n, points: a.period === "week" ? Math.round(p / 5) : p, me: false }))
      .concat(name ? [{ rank: 7, name, points: a.period === "week" ? 12.5 : 120.3, me: true }] : []),
    tf_mayors: () => [{ venue_id: "v-the-kenmore", name: "Kendall Regular", points: 42 }],
    tf_bounties: () => vids.slice(5, 9).map((v, i) => ({ venue_id: v, kind: i %% 2 ? "mixed" : "beer", last_at: i ? "2026-08-01T00:00:00Z" : null })),
  };
  window.TFBackend = {
    use: async (n) => (n === "db" ? db : n === "user" ? user : null),
    account: async () => ({ ...acct }),
    signIn: async () => "verify",
    finishClaim: async () => 0,
    signOut: async () => location.reload(),
    rpc: async (fn, a) => rpc[fn](a || {}),
  };
})();
</script>
"""

page = open(os.path.join(ROOT, "app", "index.html"), encoding="utf-8").read()
out = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
       + MOCK % json.dumps(data) + "</head><body>" + page + "</body></html>")
open(os.path.join(ROOT, "app", "_dev.html"), "w", encoding="utf-8").write(out)
print("wrote app/_dev.html")
