"""Build app/_dev.html: the app plus an in-memory mock of the claude.ai db/user capabilities, seeded from data/seed.

Serve app/ locally (python -m http.server --directory app) and open /_dev.html to click through the app without claude.ai.
Add ?viewer to the URL to simulate a view-only user.
"""
import glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = {c: {os.path.basename(f)[:-5]: json.load(open(f, encoding="utf-8"))
            for f in glob.glob(os.path.join(ROOT, "data", "seed", c, "*.json"))} for c in ("venues", "reports")}
data["mod"], data["photos"] = {}, {}

MOCK = """<script>
(function () {
  const data = %s;
  const viewer = location.search.includes("viewer");
  const subs = [];
  const snap = (c) => ({ docs: Object.entries(data[c] || {}).map(([id, d]) => ({ id, exists: true, data: () => d, metadata: {} })) });
  const fire = (c) => subs.filter((s) => s.c === c).forEach((s) => s.fn(snap(c)));
  const deny = () => Promise.reject({ code: "invalid_argument", message: "mock: view-only" });
  const coll = (c) => {
    const q = {
      where() { return q; }, orderBy() { return q; }, limit() { return q; },
      get: async () => snap(c),
      onSnapshot(fn) { subs.push({ c, fn }); setTimeout(() => fn(snap(c)), 60); return () => {}; },
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
