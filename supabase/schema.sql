-- TabFriendly on Supabase: tables, access rules, posting limits and live updates.
-- Run once in the Supabase SQL Editor (safe to re-run). Then add editors at the bottom.
--
-- Each collection the app uses is a table of {id, data jsonb}: data holds exactly the document the app reads and writes.
-- owner is the Supabase user who created the row (anonymous contributors included); it drives the rules below.

-- ---------- editors ----------
-- Editors sign in with an email link. Anyone whose email is listed here (and isn't an anonymous session) can moderate.
create table if not exists public.editors (email text primary key);
alter table public.editors enable row level security;  -- no policies: only the SQL Editor can read or change it

create or replace function public.is_editor() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((auth.jwt() ->> 'is_anonymous')::boolean, true) = false
     and exists (select 1 from public.editors e where lower(e.email) = lower(auth.jwt() ->> 'email'));
$$;
grant execute on function public.is_editor() to anon, authenticated;

-- ---------- collections ----------
do $$
declare t text;
begin
  foreach t in array array['venues', 'reports', 'menus', 'menu_edits', 'hours', 'mod', 'votes', 'photos'] loop
    execute format($f$create table if not exists public.%I (
      id text primary key,
      data jsonb not null check (octet_length(data::text) < 1500000),
      owner uuid default auth.uid(),
      created_at timestamptz not null default now()
    )$f$, t);
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "anyone reads" on public.%I', t);
    execute format('create policy "anyone reads" on public.%I for select using (true)', t);
    execute format('drop policy if exists "editors write" on public.%I', t);
    execute format('create policy "editors write" on public.%I for all to authenticated using (public.is_editor()) with check (public.is_editor())', t);
    if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end $$;

create index if not exists photos_venue on public.photos ((data ->> 'venueId'));
create index if not exists reports_venue on public.reports ((data ->> 'venueId'));

-- ---------- contributors (anonymous sign-in counts) ----------
-- New venues, prices (including menu entries) and photos: insert only, as yourself.
do $$
declare t text;
begin
  foreach t in array array['venues', 'reports', 'photos'] loop
    execute format('drop policy if exists "contributors add" on public.%I', t);
    execute format($f$create policy "contributors add" on public.%I for insert to authenticated
      with check (owner = auth.uid() and data ->> 'by' = auth.uid()::text)$f$, t);
  end loop;
end $$;

-- Votes: one document per person, id = their user id.
drop policy if exists "own votes" on public.votes;
create policy "own votes" on public.votes for all to authenticated
  using (id = auth.uid()::text) with check (id = auth.uid()::text and owner = auth.uid());

-- ---------- posting limit ----------
-- At most 20 new venues + prices + photos per person per hour (editors and the SQL Editor are exempt).
create or replace function public.rate_limit() returns trigger
language plpgsql security definer set search_path = public as $$
declare n int;
begin
  if auth.uid() is null or public.is_editor() then return new; end if;
  select (select count(*) from public.venues  where owner = auth.uid() and created_at > now() - interval '1 hour')
       + (select count(*) from public.reports where owner = auth.uid() and created_at > now() - interval '1 hour')
       + (select count(*) from public.photos  where owner = auth.uid() and created_at > now() - interval '1 hour')
    into n;
  if n >= 20 then
    raise exception 'rate_limited' using errcode = 'P0001', hint = 'Too many posts in the last hour';
  end if;
  return new;
end $$;

do $$
declare t text;
begin
  foreach t in array array['venues', 'reports', 'photos'] loop
    execute format('drop trigger if exists rate_limit on public.%I', t);
    execute format('create trigger rate_limit before insert on public.%I for each row execute function public.rate_limit()', t);
  end loop;
end $$;

-- ---------- editors list ----------
-- Add your editors here and run this part again whenever the team changes, e.g.:
-- insert into public.editors (email) values ('someone@mit.edu'), ('another@mit.edu') on conflict do nothing;
-- delete from public.editors where email = 'someone@mit.edu';
