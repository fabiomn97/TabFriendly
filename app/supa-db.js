// TabFriendly on Supabase: the small db/user API the app already uses on claude.ai
// (collection / doc / where / orderBy / limit / get / onSnapshot / set / delete, and user.id / can / canEdit),
// backed by Supabase Postgres tables of {id, data}, Realtime for live updates, and Auth for identity.
// Everyone gets a silent anonymous session; signing in with an email link makes it an account (needed for points and
// the leaderboard, and for editors). On claude.ai this file does nothing.
(() => {
  "use strict";
  if ((window.claude && window.claude.use) || window.TFBackend) return;  // claude.ai, or a test backend already in place

  const SUPABASE_URL = "https://brcwtiffgiojqnmfvaui.supabase.co";
  const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJyY3d0aWZmZ2lvanFubWZ2YXVpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE5Mjg1ODksImV4cCI6MjEwNzUwNDU4OX0.twsmr4VjKGPW2zTJSFlXcTuSPEvGm_ISz0QuJtKc0PU";
  const TABLE = { venues: "venues", reports: "reports", menus: "menus", menuEdits: "menu_edits", hours: "hours", mod: "mod", votes: "votes", photos: "photos", checks: "checks" };
  const CONTRIBUTOR_TABLES = new Set(["venues", "reports", "photos"]);  // contributors may only insert here

  // What a sign-in email link brought back: a new session (#access_token=...) or an error (#error_code=otp_expired...).
  // We read it ourselves (detectSessionInUrl is off) because the library drops the current session when a link fails,
  // which would lose an anonymous browser's posts.
  const linkHash = new URLSearchParams(location.hash.slice(1)), linkQuery = new URLSearchParams(location.search);
  const linkTokens = linkHash.get("access_token") && linkHash.get("refresh_token")
    ? { access_token: linkHash.get("access_token"), refresh_token: linkHash.get("refresh_token") } : null;
  let linkError = null;
  const linkErrCode = linkHash.get("error_code") || linkQuery.get("error_code") || linkHash.get("error") || linkQuery.get("error");
  if (linkErrCode) linkError = { code: linkErrCode, message: (linkHash.get("error_description") || linkQuery.get("error_description") || "").replace(/\+/g, " ") };
  if (linkTokens || linkErrCode) history.replaceState(null, "", location.pathname);  // keep tokens out of the address bar

  let clientP = null, sessionP = null, editor = false;
  function client() {
    return clientP || (clientP = import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm")
      .then(({ createClient }) => createClient(SUPABASE_URL, SUPABASE_ANON_KEY, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false } })));
  }
  // Everyone gets a session: an account's (from an email link, or kept from before), or a silent anonymous one.
  function session() {
    return sessionP || (sessionP = (async () => {
      const sb = await client();
      if (linkTokens) {
        const { error } = await sb.auth.setSession(linkTokens);
        if (error) linkError = { code: error.code || "link_failed", message: error.message };
      }
      let { data: { session: s } } = await sb.auth.getSession();
      if (!s) {
        const { data, error } = await sb.auth.signInAnonymously();
        if (error) throw error;
        s = data.session;
      }
      const { data: isEd } = await sb.rpc("is_editor");
      editor = isEd === true;
      return s;
    })());
  }

  // Errors in the shape the app's writeError() expects.
  function mapError(e) {
    const msg = String((e && (e.message || e.hint)) || "");
    if (/rate_limited/.test(msg)) return { code: "resource_exhausted", message: msg };
    if (e && (e.code === "42501" || /row-level security|permission denied/i.test(msg))) return { code: "invalid_argument", message: msg };
    return { code: "unavailable", message: msg };
  }
  const randomId = () => Array.from(crypto.getRandomValues(new Uint8Array(15)), (b) => "abcdefghijklmnopqrstuvwxyz0123456789"[b % 36]).join("").slice(0, 20);
  const snapOf = (rows) => ({ docs: rows.map(([id, d]) => ({ id, exists: true, data: () => d, metadata: {} })) });

  function matchSort(rows, q) {
    let out = [...rows].filter(([, d]) => q.filters.every(([f, v]) => d && d[f] === v));
    if (q.order) {
      const [f, dir] = q.order, s = dir === "desc" ? -1 : 1;
      out.sort((a, b) => (String(a[1][f] ?? "") < String(b[1][f] ?? "") ? -s : String(a[1][f] ?? "") > String(b[1][f] ?? "") ? s : 0));
    }
    return out.slice(0, q.lim);
  }
  async function fetchRows(coll, q) {
    const sb = await client();
    let r = sb.from(TABLE[coll]).select("id,data");
    for (const [f, v] of q.filters) r = r.eq(`data->>${f}`, String(v));
    if (q.order) r = r.order(`data->>${q.order[0]}`, { ascending: q.order[1] !== "desc" });
    const { data, error } = await r.limit(q.lim);
    if (error) throw mapError(error);
    return data.map((x) => [x.id, x.data]);
  }

  function ref(coll, id) {
    return {
      id,
      async set(data) {
        await session();
        const sb = await client();
        const row = { id, data };
        const { error } = CONTRIBUTOR_TABLES.has(coll) && !editor
          ? await sb.from(TABLE[coll]).insert(row)
          : await sb.from(TABLE[coll]).upsert(row);
        if (error) throw mapError(error);
      },
      async delete() {
        await session();
        const sb = await client();
        const { error } = await sb.from(TABLE[coll]).delete().eq("id", id);
        if (error) throw mapError(error);
      },
    };
  }

  function query(coll, q) {
    return {
      where(f, op, v) { return query(coll, { ...q, filters: [...q.filters, [f, v]] }); },
      orderBy(f, dir = "asc") { return query(coll, { ...q, order: [f, dir] }); },
      limit(n) { return query(coll, { ...q, lim: n }); },
      doc(id) { return ref(coll, id || randomId()); },
      async get() { return snapOf(await fetchRows(coll, q)); },
      // Initial load, then live changes from Realtime; reloads after a reconnect so nothing is missed.
      onSnapshot(fn, onErr) {
        let rows = new Map(), alive = true, timer = null, channel = null;
        const emit = () => { clearTimeout(timer); timer = setTimeout(() => alive && fn(snapOf(matchSort(rows, q))), 30); };
        const load = () => fetchRows(coll, { ...q, lim: Math.max(q.lim, 1000) })
          .then((r) => { rows = new Map(r); emit(); })
          .catch((e) => onErr && onErr(e));
        load();
        client().then((sb) => {
          if (!alive) return;
          channel = sb.channel(`tf-${TABLE[coll]}-${randomId()}`)
            .on("postgres_changes", { event: "*", schema: "public", table: TABLE[coll] }, (p) => {
              if (p.eventType === "DELETE") rows.delete(p.old.id);
              else rows.set(p.new.id, p.new.data);
              emit();
            })
            .subscribe((status) => { if (status === "SUBSCRIBED") load(); });
        });
        return () => { alive = false; clearTimeout(timer); if (channel) client().then((sb) => sb.removeChannel(channel)); };
      },
    };
  }

  const db = {
    collection(name) { return query(name, { filters: [], order: null, lim: 1000 }); },
    doc(path) { const [c, id] = path.split("/"); return ref(c, id); },
  };
  const user = {
    async id() { try { return (await session()).user.id; } catch { return null; } },
    async can() { try { await session(); return true; } catch { return false; } },
    async canEdit() { try { await session(); return editor; } catch { return false; } },
  };

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
  };
  // One-time claim tokens for this browser's anonymous sessions, kept until a sign-in link brings the person back.
  const claims = () => { try { const a = JSON.parse(store.get("tf-claims") || "[]"); return Array.isArray(a) ? a : []; } catch { return []; } };

  window.TFBackend = {
    async use(cap) { return cap === "db" ? db : cap === "user" ? user : null; },
    // Who's here: an anonymous browser, or an account (email) that may also be an editor.
    async account() {
      const s = await session().catch(() => null);
      if (!s) return null;
      return { id: s.user.id, anonymous: !!s.user.is_anonymous, email: s.user.email || null, editor };
    },
    // How the last sign-in email link went: null, or {code, message} (e.g. otp_expired: expired or replaced by a newer link).
    async linkResult() { await session().catch(() => null); return linkError; },
    // Sign in, or create an account, with an email link (Supabase's standard magic link). This browser's anonymous
    // posts and votes move to the account when the link brings the person back, by a one-time claim token.
    async signIn(email) {
      const sb = await client();
      const s = await session();
      if (s.user.is_anonymous) {
        const { data: token } = await sb.rpc("tf_claim_start");
        if (token && !claims().includes(token)) store.set("tf-claims", JSON.stringify([...claims().slice(-4), token]));
      }
      const { error } = await sb.auth.signInWithOtp({ email, options: { emailRedirectTo: location.origin + location.pathname, shouldCreateUser: true } });
      if (error) {
        const msg = error.message || "";
        throw { code: error.code === "over_email_send_rate_limit" || (error.status === 429 && /email/i.test(msg)) ? "email_limit"
          : error.code === "over_request_rate_limit" || /seconds/i.test(msg) ? "too_soon" : "send_failed", message: msg };
      }
      return "link";
    },
    // After a sign-in link: hand in this browser's claim tokens. Returns how many posts moved over.
    async finishClaim() {
      const s = await session().catch(() => null);
      if (!s || s.user.is_anonymous) return 0;
      const tokens = [...claims(), store.get("tf-claim")].filter(Boolean);  // tf-claim: the first version's single token
      if (!tokens.length) return 0;
      store.set("tf-claims", null);
      store.set("tf-claim", null);
      const sb = await client();
      let moved = 0;
      for (const tok of tokens) {
        const { data } = await sb.rpc("tf_claim_finish", { tok });
        moved += data || 0;
      }
      return moved;
    },
    // The leaderboard's database functions (tf_leaderboard, tf_me, tf_set_name, tf_mayors, tf_bounties).
    async rpc(name, args) {
      await session();
      const sb = await client();
      const { data, error } = await sb.rpc(name, args || {});
      if (error) throw { code: /name_taken|bad_name|not_signed_in/.exec(error.message || "")?.[0] || mapError(error).code, message: error.message };
      return data;
    },
    async signOut() { const sb = await client(); await sb.auth.signOut(); location.reload(); },
  };
})();
