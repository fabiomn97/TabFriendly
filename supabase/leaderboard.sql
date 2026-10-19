-- TabFriendly leaderboard: accounts (display names), contribution scoring, boards, bar mayors and bounties.
-- Run in the Supabase SQL Editor after schema.sql (safe to re-run).
--
-- Points are worked out here from the rows people post, never sent by the page, so nobody can award themselves points.
-- The rules follow the leaderboard scoring brief: points are held until other people confirm a price, every positive
-- award is scaled by a hidden trust score, and boards reset weekly and monthly and can be narrowed to a neighborhood.
-- Every account's contributions are scored, including ones made anonymously before signing up (same browser).
-- Only signed-in accounts with a display name appear on the boards.
--
-- How it runs: changes to prices, venues, votes and moderation mark the scores out of date; the next board read
-- recomputes them all from scratch (tf_recompute), at most every 15 seconds. The numbers to tune are in tf_cfg().

-- ---------- settings ----------
create or replace function public.tf_cfg(k text) returns numeric language sql immutable as $$
  select case k
    when 'submit' then 2            -- posting a price, paid right away
    when 'confirm' then 8           -- more when it's confirmed
    when 'reject' then -5           -- a rejected price (replaces the +2)
    when 'confirm_net' then 3       -- weighted net votes that confirm a price
    when 'reject_net' then -3       -- ... or reject it
    when 'match_dollars' then 0.5   -- another account's price within this much confirms it
    when 'match_days' then 30       -- ... if posted within this many days of it
    when 'stale_days' then 30       -- updating a price older than this: x1.5
    when 'stale_x' then 1.5
    when 'bounty_days' then 45      -- filling a gap (no price for it in this many days): x3
    when 'bounty_x' then 3
    when 'first_x' then 2           -- the first price at a bar: x2
    when 'checkin' then 1           -- "still accurate" (an upvote on an established price)
    when 'checkin_days' then 7      -- ... once per price per person per week
    when 'new_drink' then 1         -- adding a drink to a menu
    when 'new_bar' then 5           -- adding a bar, held until someone else posts a price there
    when 'vote' then 0.5            -- a vote that matched the final call
    when 'vote_cap_day' then 10     -- ... paid at most this many times a day
    when 'anon_vote_weight' then 0.5  -- weight of a vote from a browser without an account
    when 'prior' then 2             -- trust starts at 0.5, as if 2 confirmed of 4 resolved
    when 'onsite_x' then 1          -- PLACEHOLDER: GPS on-site bonus (brief: about 1.2x) comes with the GPS work
    when 'mayor_days' then 60       -- bar mayor: most confirmed points at a bar in this many days
  end $$;

-- "Pabst Blue Ribbon (can)" -> "pabstblueribboncan": the key the app uses to match drink names.
create or replace function public.tf_bare(s text) returns text language sql immutable as $$
  select lower(regexp_replace(coalesce(s, ''), '[^A-Za-z0-9]', '', 'g')) $$;

-- A researched price's date: the menu's month, else when we checked it, else when the row was loaded.
create or replace function public.tf_research_date(menu_date text, checked text, fallback timestamptz)
returns timestamptz language plpgsql stable as $$
begin
  begin
    if menu_date ~ '^\d{4}-\d{2}' then return (substr(menu_date, 1, 7) || '-01')::date::timestamptz; end if;
  exception when others then null;  -- a malformed date falls through to the next one
  end;
  begin
    if checked ~ '^\d{4}-\d{2}-\d{2}' then return left(checked, 10)::date::timestamptz; end if;
  exception when others then null;
  end;
  return fallback;
end $$;

-- PLACEHOLDER: a new bar's +5 is also released when it matches a Google Places listing. Not wired up yet.
create or replace function public.tf_places_match(venue_id text) returns boolean language sql stable as $$ select false $$;

-- ---------- accounts ----------
-- A signed-in account (email, not anonymous) picks a public display name; that's all the boards show.
create table if not exists public.profiles (
  user_id uuid primary key,
  display_name text not null check (char_length(display_name) between 2 and 24),
  created_at timestamptz not null default now()
);
create unique index if not exists profiles_name on public.profiles (lower(display_name));
alter table public.profiles enable row level security;  -- read and written through the functions below

create or replace function public.tf_is_account() returns boolean language sql stable as $$
  select auth.uid() is not null and coalesce((auth.jwt() ->> 'is_anonymous')::boolean, true) = false $$;

create or replace function public.tf_set_name(name text) returns text
language plpgsql security definer set search_path = public as $$
declare n text := btrim(regexp_replace(coalesce(name, ''), '\s+', ' ', 'g'));
begin
  if not tf_is_account() then raise exception 'not_signed_in' using errcode = 'P0001'; end if;
  if char_length(n) < 2 or char_length(n) > 24 or n !~ '^[A-Za-z0-9 ._''-]+$' then
    raise exception 'bad_name' using errcode = 'P0001', hint = '2-24 letters, numbers, spaces, . _ - or ''';
  end if;
  if exists (select 1 from profiles where lower(display_name) = lower(n) and user_id <> auth.uid()) then
    raise exception 'name_taken' using errcode = 'P0001';
  end if;
  insert into profiles (user_id, display_name) values (auth.uid(), n)
    on conflict (user_id) do update set display_name = excluded.display_name;
  return n;
end $$;

-- Signing in on a browser that already posted anonymously: before leaving the anonymous session the page takes a
-- one-time token; after the email link brings it back signed in, it hands the token in and those posts move over.
create table if not exists public.tf_claims (
  token text primary key,
  anon_uid uuid not null,
  created_at timestamptz not null default now()
);
alter table public.tf_claims enable row level security;  -- no policies: functions only

create or replace function public.tf_claim_start() returns text
language plpgsql security definer set search_path = public as $$
declare t text := replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', '');
begin
  if auth.uid() is null or tf_is_account() then return null; end if;
  delete from tf_claims where created_at < now() - interval '2 days';
  insert into tf_claims (token, anon_uid) values (t, auth.uid());
  return t;
end $$;

create or replace function public.tf_claim_finish(tok text) returns integer
language plpgsql security definer set search_path = public as $$
declare c tf_claims; me uuid := auth.uid(); n integer := 0; k integer; old_votes jsonb;
begin
  if not tf_is_account() then return 0; end if;
  delete from tf_claims where token = tok and created_at > now() - interval '2 days' returning * into c;
  if c.anon_uid is null or c.anon_uid = me
     or not exists (select 1 from auth.users u where u.id = c.anon_uid and u.is_anonymous) then
    return 0;
  end if;
  perform set_config('tf.claiming', 'on', true);  -- the vote trigger stays out of the way; history moves below
  update reports set owner = me, data = jsonb_set(data, '{by}', to_jsonb(me::text)) where owner = c.anon_uid;
  get diagnostics k = row_count; n := n + k;
  update venues set owner = me, data = jsonb_set(data, '{by}', to_jsonb(me::text)) where owner = c.anon_uid;
  get diagnostics k = row_count; n := n + k;
  update photos set owner = me, data = jsonb_set(data, '{by}', to_jsonb(me::text)) where owner = c.anon_uid;
  get diagnostics k = row_count; n := n + k;
  -- votes: the account's own votes win where both voted on the same price
  select data into old_votes from votes where id = c.anon_uid::text;
  if old_votes is not null then
    insert into votes (id, data, owner) values (me::text, old_votes, me)
      on conflict (id) do update set data = old_votes || votes.data;
    delete from votes where id = c.anon_uid::text;
    delete from tf_votes_now a where a.voter = c.anon_uid
      and exists (select 1 from tf_votes_now b where b.voter = me and b.target = a.target);
    update tf_votes_now set voter = me where voter = c.anon_uid;
    update tf_vote_log set voter = me where voter = c.anon_uid;
  end if;
  update tf_state set dirty = true where id = 1;
  return n;
end $$;

-- ---------- vote history and "still accurate" check-ins ----------
-- votes/<user id> holds {priceId: 1 | -1}. This trigger keeps a timed copy of every change (the scores need when a
-- vote was cast) and treats each upvote as a "still accurate" check-in that renews the price: checks/<priceId>.at.
-- priceId is a report id, or "m:<venueId>:<drink key>" for a drink on a researched menu.
create table if not exists public.tf_vote_log (
  id bigserial primary key, voter uuid not null, target text not null, value smallint not null,
  at timestamptz not null default now());
create index if not exists tf_vote_log_target on public.tf_vote_log (target);
create table if not exists public.tf_votes_now (
  voter uuid not null, target text not null, value smallint not null, at timestamptz not null,
  primary key (voter, target));
alter table public.tf_vote_log enable row level security;
alter table public.tf_votes_now enable row level security;

create table if not exists public.checks (
  id text primary key, data jsonb not null, owner uuid, created_at timestamptz not null default now());
alter table public.checks enable row level security;
drop policy if exists "anyone reads" on public.checks;
create policy "anyone reads" on public.checks for select using (true);
do $$ begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'checks') then
    alter publication supabase_realtime add table public.checks;
  end if;
end $$;

create table if not exists public.tf_state (id int primary key default 1 check (id = 1), dirty boolean not null default true, ran_at timestamptz);
insert into public.tf_state (id) values (1) on conflict do nothing;
alter table public.tf_state enable row level security;

create or replace function public.tf_price_owner(target text) returns uuid language sql stable security definer set search_path = public as $$
  select owner from reports where id = target $$;

create or replace function public.tf_votes_changed() returns trigger
language plpgsql security definer set search_path = public as $$
declare uid uuid; o jsonb; n jsonb; k text; v smallint; ov smallint; vid text;
begin
  if current_setting('tf.claiming', true) = 'on' then return null; end if;
  vid := case when tg_op = 'DELETE' then old.id else new.id end;
  if vid !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then return null; end if;  -- pre-Supabase voters
  uid := vid::uuid;
  o := case when tg_op = 'INSERT' then '{}'::jsonb else coalesce(old.data, '{}'::jsonb) end;
  n := case when tg_op = 'DELETE' then '{}'::jsonb else coalesce(new.data, '{}'::jsonb) end;
  for k in select jsonb_object_keys(o) union select jsonb_object_keys(n) loop
    v := case when n ->> k in ('1', '-1') then (n ->> k)::smallint else 0 end;
    ov := case when o ->> k in ('1', '-1') then (o ->> k)::smallint else 0 end;
    continue when v = ov;
    insert into tf_vote_log (voter, target, value) values (uid, k, v);
    if v = 0 then
      delete from tf_votes_now where voter = uid and target = k;
    else
      insert into tf_votes_now (voter, target, value, at) values (uid, k, v, now())
        on conflict (voter, target) do update set value = excluded.value, at = excluded.at;
    end if;
    if v = 1 and tf_price_owner(k) is distinct from uid then
      insert into checks (id, data) values (k, jsonb_build_object('at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')))
        on conflict (id) do update set data = excluded.data;
    end if;
  end loop;
  update tf_state set dirty = true where id = 1 and not dirty;
  return null;
end $$;
drop trigger if exists tf_votes_changed on public.votes;
create trigger tf_votes_changed after insert or update or delete on public.votes for each row execute function public.tf_votes_changed();

-- Votes cast before this file was run: copy them in, timed by when the person first voted.
insert into public.tf_votes_now (voter, target, value, at)
  select v.id::uuid, k.key, k.value::text::smallint, v.created_at
  from public.votes v, jsonb_each(v.data) k
  where v.id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' and k.value::text in ('1', '-1')
on conflict do nothing;
insert into public.tf_vote_log (voter, target, value, at)
  select n.voter, n.target, n.value, n.at from public.tf_votes_now n
  where not exists (select 1 from public.tf_vote_log l where l.voter = n.voter and l.target = n.target);

-- Anything that changes the scores marks them out of date.
create or replace function public.tf_mark_dirty() returns trigger
language plpgsql security definer set search_path = public as $$
begin update tf_state set dirty = true where id = 1 and not dirty; return null; end $$;
do $$
declare t text;
begin
  foreach t in array array['venues', 'reports', 'menus', 'menu_edits', 'mod'] loop
    execute format('drop trigger if exists tf_mark_dirty on public.%I', t);
    execute format('create trigger tf_mark_dirty after insert or update or delete on public.%I for each statement execute function public.tf_mark_dirty()', t);
  end loop;
end $$;

-- ---------- neighborhoods ----------
-- The map's area labels; each venue belongs to the nearest one.
create table if not exists public.tf_areas (name text primary key, lat float8 not null, lng float8 not null);
alter table public.tf_areas enable row level security;
insert into public.tf_areas (name, lat, lng) values
  ('Kendall Sq', 42.3626, -71.0855), ('Central Sq', 42.3652, -71.1035), ('Cambridgeport', 42.3575, -71.1075),
  ('Back Bay', 42.3500, -71.0805), ('Kenmore', 42.3482, -71.0965), ('Fenway', 42.3437, -71.1000),
  ('MIT', 42.3612, -71.0950), ('Harvard Sq', 42.3732, -71.1190), ('Inman Sq', 42.3736, -71.1003),
  ('Union Sq', 42.3796, -71.0935), ('East Cambridge', 42.3700, -71.0790), ('Beacon Hill', 42.3588, -71.0680),
  ('West End', 42.3645, -71.0650), ('Downtown', 42.3555, -71.0610), ('South End', 42.3420, -71.0725),
  ('Longwood', 42.3378, -71.1060), ('Mission Hill', 42.3325, -71.0990), ('Allston', 42.3535, -71.1290)
on conflict (name) do update set lat = excluded.lat, lng = excluded.lng;

-- ---------- results of the last recompute (private; read through the functions below) ----------
create table if not exists public.tf_ledger (
  id bigserial primary key,
  user_id uuid not null,
  at timestamptz not null,
  points numeric not null,
  what text not null,         -- price | confirmed | rejected | drink | bar | vote | checkin
  ref text,                   -- the price, venue or vote it's for
  venue_id text,
  area text,
  held boolean not null default false,   -- waiting on confirmation; shown to its owner, not counted on boards
  solid boolean not null default false   -- confirmed points (what bar mayors are decided on)
);
create index if not exists tf_ledger_user on public.tf_ledger (user_id);
create table if not exists public.tf_subs (
  id text primary key, user_id uuid not null, venue_id text, status text not null, resolved_at timestamptz);
create table if not exists public.tf_trust (
  user_id uuid primary key, trust numeric not null, confirmed int not null, resolved int not null);
create table if not exists public.tf_prices (venue_id text not null, ckey text not null, at timestamptz not null);
create index if not exists tf_prices_venue on public.tf_prices (venue_id, ckey);
alter table public.tf_ledger enable row level security;
alter table public.tf_subs enable row level security;
alter table public.tf_trust enable row level security;
alter table public.tf_prices enable row level security;

-- ---------- the scoring ----------
create or replace function public.tf_recompute() returns void
language plpgsql security definer set search_path = public, pg_temp as $$
declare i int; cap int := tf_cfg('vote_cap_day')::int; p numeric := tf_cfg('prior');
begin
  if not pg_try_advisory_xact_lock(4207001) then return; end if;  -- one recompute at a time
  update tf_state set dirty = false, ran_at = now() where id = 1;

  drop table if exists t_venue, t_sub, t_vote, t_trust, t_res, t_price, t_match, t_corr, t_sv, t_st;

  -- venues, with their neighborhood
  create temp table t_venue on commit drop as
    select v.id, v.owner, v.created_at, v.data ->> 'source' = 'user' as user_added,
      coalesce((select (m.data ->> 'hidden')::boolean from mod m where m.id = v.id), false) as hidden,
      (select a.name from tf_areas a
        order by (a.lat - (v.data ->> 'lat')::float8) ^ 2 + ((a.lng - (v.data ->> 'lng')::float8) * 0.74) ^ 2 limit 1) as area
    from venues v where jsonb_typeof(v.data -> 'lat') = 'number' and jsonb_typeof(v.data -> 'lng') = 'number';

  -- people's prices: cheapest-beer/mixed reports and menu entries
  create temp table t_sub on commit drop as
    select r.id, r.owner as uid, r.created_at as at, r.data ->> 'venueId' as venue, r.data ->> 'kind' as kind,
      (r.data ->> 'price')::numeric as price, coalesce((r.data ->> 'menu')::boolean, false) as menu,
      nullif(r.data ->> 'target', '') is not null as edits,
      tf_bare(coalesce(nullif(r.data ->> 'type', ''), r.data ->> 'drink')) as tkey,
      coalesce(nullif(r.data ->> 'target', ''), tf_bare(r.data ->> 'drink') || '|' || coalesce(r.data ->> 'oz', '')) as mkey,
      coalesce((select (m.data ->> 'hidden')::boolean from mod m where m.id = r.id), false) as hidden,
      coalesce(u.is_anonymous, true) as anon,
      null::text as ckey, null::text as dkey, null::text as status, null::text as why, 0::numeric as net,
      null::timestamptz as resolved_at, 1::numeric as bonus, false as new_drink, 1::numeric as dim
    from reports r left join auth.users u on u.id = r.owner
    where r.data ->> 'source' = 'user' and r.owner is not null and r.data ? 'venueId'
      and jsonb_typeof(r.data -> 'price') = 'number' and r.data ->> 'kind' in ('beer', 'mixed', 'wine', 'other');
  -- ckey: what a price replaces (a drink on the menu, or the venue's cheapest of a kind);
  -- dkey: what another price must be to confirm it (the same drink)
  update t_sub set ckey = case when menu then 'm:' || mkey else 'c:' || kind end,
                   dkey = case when menu then 'm:' || mkey else 'c:' || kind || ':' || tkey end
    where true;  -- Supabase rejects UPDATE/DELETE without a WHERE clause
  create index on t_sub (venue, dkey);
  create index on t_sub (venue, ckey);
  create index on t_sub (uid);
  create index on t_sub (id);
  analyze t_venue; analyze t_sub;

  create temp table t_vote on commit drop as
    select n.voter, n.target, n.value, n.at, coalesce(u.is_anonymous, true) as anon
    from tf_votes_now n left join auth.users u on u.id = n.voter;
  create index on t_vote (target);
  analyze t_vote;

  -- Confirm or reject each price. Vote weight depends on trust, which depends on how prices resolve,
  -- so settle the two together over a few rounds (it settles quickly).
  create temp table t_trust (uid uuid primary key, trust numeric not null) on commit drop;
  -- Independent matches and possible corrections don't depend on votes: work them out once.
  create temp table t_match on commit drop as   -- another account's price for the same drink, close in price and time
    select s.id, min(o.at) as at from t_sub s join t_sub o on o.venue = s.venue and o.dkey = s.dkey and o.uid <> s.uid
      and not o.hidden and not o.anon and abs(o.price - s.price) <= tf_cfg('match_dollars')
      and abs(extract(epoch from o.at - s.at)) <= tf_cfg('match_days') * 86400
    group by s.id;
  create temp table t_corr on commit drop as    -- a later, different price from someone else for the same thing
    select s.id, c.id as cid, c.at from t_sub s join t_sub c on c.venue = s.venue and c.ckey = s.ckey and c.uid <> s.uid
      and c.at > s.at and (c.dkey <> s.dkey or abs(c.price - s.price) > tf_cfg('match_dollars'));
  create temp table t_sv on commit drop as      -- votes on each price, not counting its author's own
    select s.id, v.voter, v.value, v.at, v.anon from t_sub s join t_vote v on v.target = s.id and v.voter <> s.uid;
  create index on t_corr (cid);
  analyze t_match; analyze t_corr; analyze t_sv;

  create temp table t_st (id text primary key, uid uuid, net numeric, status text, why text) on commit drop;
  for i in 1..4 loop
    truncate t_st;
    insert into t_st
      select s.id, s.uid, coalesce(n.net, 0),
        case when s.hidden then 'rejected'
             when coalesce(n.net, 0) >= tf_cfg('confirm_net') then 'confirmed'
             when coalesce(n.net, 0) <= tf_cfg('reject_net') then 'rejected'
             when m.id is not null then 'confirmed'
             else 'pending' end,
        case when s.hidden then 'hidden'
             when coalesce(n.net, 0) >= tf_cfg('confirm_net') or coalesce(n.net, 0) <= tf_cfg('reject_net') then 'votes'
             when m.id is not null then 'match' end
      from t_sub s
      left join (select sv.id, sum(sv.value * case when sv.anon then tf_cfg('anon_vote_weight') else 0.5 + coalesce(t.trust, 0.5) end) as net
                 from t_sv sv left join t_trust t on t.uid = sv.voter group by sv.id) n on n.id = s.id
      left join t_match m on m.id = s.id;
    -- a price that was still open when someone else's correction got confirmed counts as rejected
    update t_st st set status = 'rejected', why = 'correction'
      from (select distinct x.id from t_corr x join t_st c on c.id = x.cid and c.status = 'confirmed') z
      where z.id = st.id and st.status = 'pending';
    truncate t_trust;
    insert into t_trust select uid,
        (count(*) filter (where status = 'confirmed') + p) / (count(*) filter (where status in ('confirmed', 'rejected')) + 2 * p)
      from t_st group by uid;
  end loop;

  -- when each price was settled
  update t_sub s set net = st.net, status = st.status, why = st.why, resolved_at = case
      when st.status = 'pending' then null
      when st.why = 'hidden' then greatest(s.at, coalesce((select m.created_at from mod m where m.id = s.id), s.at))
      when st.why = 'votes' then greatest(s.at, coalesce((select max(sv.at) from t_sv sv where sv.id = s.id), s.at))
      when st.why = 'match' then greatest(s.at, coalesce((select m.at from t_match m where m.id = s.id), s.at))
      else greatest(s.at, coalesce((select min(x.at) from t_corr x join t_st c on c.id = x.cid and c.status = 'confirmed' where x.id = s.id), s.at)) end
    from t_st st where st.id = s.id;

  -- Trust as of a moment: confirmed / resolved prices settled before then, smoothed so a new account starts at 0.5.
  create temp table t_res on commit drop as
    select uid, resolved_at as at, status = 'confirmed' as ok from t_sub where status in ('confirmed', 'rejected');
  create index on t_res (uid, at);
  analyze t_res;

  -- Every price the map has had, by venue and what it covers, for staleness, bounties and "first price at a bar".
  create temp table t_price (venue text, ckey text, at timestamptz) on commit drop;
  insert into t_price
    select coalesce(m.data ->> 'venueId', m.id), x.k, tf_research_date(m.data ->> 'sourceDate', m.data ->> 'at', m.created_at)
    from menus m,
      jsonb_array_elements(case when jsonb_typeof(m.data -> 'items') = 'array' then m.data -> 'items' else '[]'::jsonb end) it,
      lateral (values ('m:' || tf_bare(it ->> 'name') || '|' || coalesce(it ->> 'oz', '')), ('c:' || (it ->> 'kind'))) x(k);
  insert into t_price
    select r.data ->> 'venueId', 'c:' || (r.data ->> 'kind'), tf_research_date(r.data ->> 'sourceDate', r.data ->> 'at', r.created_at)
    from reports r where coalesce(r.data ->> 'source', '') <> 'user' and r.data ? 'venueId';
  insert into t_price
    select e.data ->> 'venueId', x.k, e.created_at
    from menu_edits e,
      lateral (values ('m:' || coalesce(nullif(e.data ->> 'target', ''), tf_bare(e.data #>> '{item,name}') || '|' || coalesce(e.data #>> '{item,oz}', ''))),
                      ('c:' || coalesce(e.data #>> '{item,kind}', ''))) x(k)
    where coalesce((e.data ->> 'removed')::boolean, false) = false;
  insert into t_price select venue, ckey, at from t_sub where not hidden;
  insert into t_price select venue, 'c:' || kind, at from t_sub where menu and not hidden;
  -- check-ins renew what they're on
  insert into t_price
    select coalesce(s.venue, split_part(l.target, ':', 2)),
           coalesce(s.ckey, 'm:' || substr(l.target, length(split_part(l.target, ':', 2)) + 4)), l.at
    from tf_vote_log l left join t_sub s on s.id = l.target
    where l.value = 1 and (s.id is not null or l.target like 'm:%:%');
  insert into t_price
    select r.data ->> 'venueId', 'c:' || (r.data ->> 'kind'), l.at
    from tf_vote_log l join reports r on r.id = l.target
    where l.value = 1 and coalesce(r.data ->> 'source', '') <> 'user';
  create index on t_price (venue, ckey, at);
  analyze t_price;

  -- Multipliers: first price at a bar x2; else filling a gap (bounty) x3; else updating a stale price x1.5.
  -- A drink a menu never listed is a new drink (+1) instead.
  update t_sub s set bonus = case
      when not exists (select 1 from t_price q where q.venue = s.venue and q.at < s.at) then tf_cfg('first_x')
      else (select case
          when max(q.at) is null then case when s.menu then 1 else tf_cfg('bounty_x') end
          when s.at - max(q.at) > make_interval(days => tf_cfg('bounty_days')::int) then tf_cfg('bounty_x')
          when s.at - max(q.at) > make_interval(days => tf_cfg('stale_days')::int) then tf_cfg('stale_x')
          else 1 end
        from t_price q where q.venue = s.venue and q.ckey = s.ckey and q.at < s.at) end,
    new_drink = s.menu and not s.edits and not exists (select 1 from t_price q where q.venue = s.venue and q.ckey = s.ckey and q.at < s.at)
    where true;
  -- several posts by one person at one bar on one day: the 2nd counts half, the 3rd a third, ...
  update t_sub s set dim = 1.0 / x.n from (
    select id, row_number() over (partition by uid, venue, (at at time zone 'America/New_York')::date order by at, id) as n from t_sub) x
  where x.id = s.id;

  -- ---------- the ledger ----------
  delete from tf_ledger where true;
  -- posting a price: +2 now (not kept if the price is rejected)
  insert into tf_ledger (user_id, at, points, what, ref, venue_id, solid)
    select s.uid, s.at, tf_cfg('submit') * s.bonus * s.dim * tf_cfg('onsite_x')
        * (0.5 + (select (count(*) filter (where r.ok) + p) / (count(*) + 2 * p) from t_res r where r.uid = s.uid and r.at < s.at)),
      'price', s.id, s.venue, s.status = 'confirmed'
    from t_sub s where s.status <> 'rejected';
  -- confirmed: +8 more (pending prices show the +8 as held, to their author only)
  insert into tf_ledger (user_id, at, points, what, ref, venue_id, held, solid)
    select s.uid, coalesce(s.resolved_at, now()), tf_cfg('confirm') * s.bonus * s.dim * tf_cfg('onsite_x')
        * (0.5 + (select (count(*) filter (where r.ok) + p) / (count(*) + 2 * p) from t_res r where r.uid = s.uid and r.at < coalesce(s.resolved_at, now()))),
      'confirmed', s.id, s.venue, s.status = 'pending', s.status = 'confirmed'
    from t_sub s where s.status in ('confirmed', 'pending');
  -- rejected: -5, no multipliers
  insert into tf_ledger (user_id, at, points, what, ref, venue_id)
    select s.uid, s.resolved_at, tf_cfg('reject'), 'rejected', s.id, s.venue from t_sub s where s.status = 'rejected';
  -- a new drink on a menu: +1
  insert into tf_ledger (user_id, at, points, what, ref, venue_id, solid)
    select s.uid, s.at, tf_cfg('new_drink') * s.dim
        * (0.5 + (select (count(*) filter (where r.ok) + p) / (count(*) + 2 * p) from t_res r where r.uid = s.uid and r.at < s.at)),
      'drink', s.id, s.venue, s.status = 'confirmed'
    from t_sub s where s.new_drink and s.status <> 'rejected';
  -- adding a bar: +5, held until someone else posts a price there (or it matches a Places listing: placeholder)
  insert into tf_ledger (user_id, at, points, what, ref, venue_id, held, solid)
    select v.owner, coalesce(x.at, v.created_at), tf_cfg('new_bar')
        * (0.5 + (select (count(*) filter (where r.ok) + p) / (count(*) + 2 * p) from t_res r where r.uid = v.owner and r.at < coalesce(x.at, now()))),
      'bar', v.id, v.id, x.at is null and not tf_places_match(v.id), x.at is not null
    from t_venue v
    left join lateral (select min(s.at) as at from t_sub s where s.venue = v.id and s.uid <> v.owner and not s.hidden) x on true
    where v.user_added and v.owner is not null and not v.hidden;
  -- votes that matched the final call on someone else's price: +0.5, at most 10 paid a day
  insert into tf_ledger (user_id, at, points, what, ref, venue_id)
    select x.voter, x.at, tf_cfg('vote')
        * (0.5 + (select (count(*) filter (where r.ok) + p) / (count(*) + 2 * p) from t_res r where r.uid = x.voter and r.at < x.at)),
      'vote', x.target, x.venue
    from (
      select v.voter, v.at, v.target, s.venue,
        row_number() over (partition by v.voter, (v.at at time zone 'America/New_York')::date order by v.at) as n
      from t_vote v join t_sub s on s.id = v.target
      -- votes cast after the call was made are check-ins, paid below, not consensus votes
      where v.voter <> s.uid and v.at <= s.resolved_at
        and ((v.value = 1 and s.status = 'confirmed') or (v.value = -1 and s.status = 'rejected'))
    ) x where x.n <= cap;
  -- "still accurate": an upvote on an established price (a researched or editor price, or someone else's price that
  -- was already confirmed) renews it: +1, once per price per person per week
  insert into tf_ledger (user_id, at, points, what, ref, venue_id, solid)
    select x.voter, x.at, tf_cfg('checkin')
        * (0.5 + (select (count(*) filter (where r.ok) + p) / (count(*) + 2 * p) from t_res r where r.uid = x.voter and r.at < x.at)),
      'checkin', x.target, x.venue, true
    from (
      select l.voter, l.at, l.target, coalesce(s.venue, r.data ->> 'venueId', split_part(l.target, ':', 2)) as venue,
        row_number() over (partition by l.voter, l.target, floor(extract(epoch from l.at) / (tf_cfg('checkin_days') * 86400)) order by l.at) as n
      from tf_vote_log l
      left join t_sub s on s.id = l.target
      left join reports r on r.id = l.target and s.id is null
      where l.value = 1
        and (case when s.id is not null then s.uid <> l.voter and s.status = 'confirmed' and s.resolved_at < l.at
                  when r.id is not null then coalesce(r.data ->> 'source', '') <> 'user'
                  else l.target like 'm:%:%' end)
    ) x where x.n = 1;
  update tf_ledger l set area = v.area from t_venue v where v.id = l.venue_id;

  -- ---------- kept for the boards ----------
  delete from tf_subs where true;
  insert into tf_subs select id, uid, venue, status, resolved_at from t_sub;
  delete from tf_trust where true;
  insert into tf_trust select t.uid, t.trust, coalesce(c.ok, 0), coalesce(c.n, 0)
    from t_trust t left join (select uid, count(*) filter (where status = 'confirmed') as ok,
      count(*) filter (where status in ('confirmed', 'rejected')) as n from t_sub group by uid) c on c.uid = t.uid;
  delete from tf_prices where true;
  insert into tf_prices select venue, ckey, max(at) from t_price where venue is not null group by venue, ckey;
end $$;

create or replace function public.tf_refresh() returns void
language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from tf_state where id = 1 and dirty and (ran_at is null or ran_at < now() - interval '15 seconds')) then
    perform tf_recompute();
  end if;
end $$;

-- Start of the current week (Monday) or month, Boston time.
create or replace function public.tf_since(period text) returns timestamptz language sql stable as $$
  select case period
    when 'week' then date_trunc('week', now() at time zone 'America/New_York') at time zone 'America/New_York'
    when 'month' then date_trunc('month', now() at time zone 'America/New_York') at time zone 'America/New_York'
    else '-infinity'::timestamptz end $$;

-- ---------- what the page reads ----------
-- The board: top 50 for a period ('week' | 'month' | 'all') and optionally one neighborhood, plus your own row.
create or replace function public.tf_leaderboard(period text default 'week', area text default null)
returns table (rank integer, name text, points numeric, me boolean)
language plpgsql security definer set search_path = public as $$
begin
  perform tf_refresh();
  return query
    with tot as (
      select l.user_id, sum(l.points) as pts from tf_ledger l
      where not l.held and l.at >= tf_since(period) and (tf_leaderboard.area is null or l.area = tf_leaderboard.area)
      group by l.user_id),
    ranked as (
      select (rank() over (order by t.pts desc))::integer as rk, p.display_name, round(t.pts, 1) as pts, t.user_id = auth.uid() as mine
      from tot t join profiles p on p.user_id = t.user_id join auth.users u on u.id = t.user_id
      where not coalesce(u.is_anonymous, true) and t.pts > 0)
    select r.rk, r.display_name, r.pts, r.mine from ranked r where r.rk <= 50 or r.mine order by r.rk, r.display_name;
end $$;

-- You: name, points per period (with any held), rank, and how your prices have fared. Trust stays hidden.
create or replace function public.tf_me() returns jsonb
language plpgsql security definer set search_path = public as $$
declare me uuid := auth.uid(); res jsonb;
begin
  if me is null then return null; end if;
  perform tf_refresh();
  select jsonb_build_object(
    'account', tf_is_account(),
    'name', (select display_name from profiles where user_id = me),
    'week', coalesce((select round(sum(points), 1) from tf_ledger where user_id = me and not held and at >= tf_since('week')), 0),
    'month', coalesce((select round(sum(points), 1) from tf_ledger where user_id = me and not held and at >= tf_since('month')), 0),
    'all', coalesce((select round(sum(points), 1) from tf_ledger where user_id = me and not held), 0),
    'held', coalesce((select round(sum(points), 1) from tf_ledger where user_id = me and held), 0),
    'posted', (select count(*) from tf_subs where user_id = me),
    'confirmed', (select count(*) from tf_subs where user_id = me and status = 'confirmed'),
    'rejected', (select count(*) from tf_subs where user_id = me and status = 'rejected'),
    'pending', (select count(*) from tf_subs where user_id = me and status = 'pending'),
    'recent', coalesce((select jsonb_agg(x order by x.at desc) from (
        select l.at, l.what, round(l.points, 1) as points, l.held, l.venue_id from tf_ledger l
        where l.user_id = me order by l.at desc limit 15) x), '[]'::jsonb)
  ) into res;
  return res;
end $$;

-- Bar mayors: who has the most confirmed points at each bar over the last 60 days (accounts with a name only).
create or replace function public.tf_mayors() returns table (venue_id text, name text, points numeric)
language plpgsql security definer set search_path = public as $$
begin
  perform tf_refresh();
  return query
    select distinct on (x.venue_id) x.venue_id, x.display_name, round(x.pts, 1)
    from (
      select l.venue_id, p.display_name, sum(l.points) as pts, max(l.at) as last_at
      from tf_ledger l join profiles p on p.user_id = l.user_id join auth.users u on u.id = l.user_id
      where l.solid and not l.held and l.points > 0 and l.at > now() - make_interval(days => tf_cfg('mayor_days')::int)
        and not coalesce(u.is_anonymous, true) and l.venue_id is not null
      group by l.venue_id, p.display_name) x
    order by x.venue_id, x.pts desc, x.last_at;
end $$;

-- Bounties: a bar's cheapest beer or mixed drink with no price in 45 days (or none at all, at a bar that has other
-- prices). Filling one pays 3x. The 30 with the oldest gaps.
create or replace function public.tf_bounties() returns table (venue_id text, kind text, last_at timestamptz)
language plpgsql security definer set search_path = public as $$
begin
  perform tf_refresh();
  return query
    select v.id, k.kind, p.at
    from venues v
    cross join (values ('beer'), ('mixed')) k(kind)
    left join tf_prices p on p.venue_id = v.id and p.ckey = 'c:' || k.kind
    where exists (select 1 from tf_prices q where q.venue_id = v.id)
      and not coalesce((select (m.data ->> 'hidden')::boolean from mod m where m.id = v.id), false)
      and (p.at is null or p.at < now() - make_interval(days => tf_cfg('bounty_days')::int))
    order by p.at nulls first, v.id
    limit 30;
end $$;

-- For editors: pairs of accounts that almost always vote the same way on the same prices (possible vote rings).
create or replace function public.tf_vote_clusters()
returns table (a text, b text, together integer, agree numeric)
language plpgsql security definer set search_path = public as $$
begin
  if not is_editor() then raise exception 'editors only' using errcode = '42501'; end if;
  return query
    select coalesce(pa.display_name, x.va::text), coalesce(pb.display_name, x.vb::text), x.n::integer, round(x.ag, 2)
    from (
      select v1.voter as va, v2.voter as vb, count(*) as n, avg((v1.value = v2.value)::int) as ag
      from tf_votes_now v1 join tf_votes_now v2 on v1.target = v2.target and v1.voter < v2.voter
      group by v1.voter, v2.voter
      having count(*) >= 5 and avg((v1.value = v2.value)::int) >= 0.9) x
    left join profiles pa on pa.user_id = x.va left join profiles pb on pb.user_id = x.vb
    order by x.n desc;
end $$;

revoke all on function public.tf_recompute() from public, anon, authenticated;
grant execute on function public.tf_set_name(text), public.tf_claim_start(), public.tf_claim_finish(text), public.tf_leaderboard(text, text),
  public.tf_me(), public.tf_mayors(), public.tf_bounties(), public.tf_vote_clusters() to anon, authenticated;

select public.tf_recompute();
