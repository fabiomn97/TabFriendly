"""Build app/_dev.html: the app plus an in-memory mock of the claude.ai db/user capabilities, seeded from data/seed.

Serve app/ locally (python -m http.server --directory app) and open /_dev.html to click through the app without claude.ai.
Add ?viewer to the URL to simulate a view-only user.
"""
import glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = {c: {os.path.basename(f)[:-5]: json.load(open(f, encoding="utf-8"))
            for f in glob.glob(os.path.join(ROOT, "data", "seed", c, "*.json"))} for c in ("venues", "reports")}
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
  window.claude = { use: async (n) => (n === "db" ? db : n === "user" ? user : null) };
})();
</script>
"""

page = open(os.path.join(ROOT, "app", "index.html"), encoding="utf-8").read()
out = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
       + MOCK % json.dumps(data) + "</head><body>" + page + "</body></html>")
open(os.path.join(ROOT, "app", "_dev.html"), "w", encoding="utf-8").write(out)
print("wrote app/_dev.html")
