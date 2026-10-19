"""Turn a dump of the claude.ai database into SQL files that load it into Supabase.

Input: a directory with one folder per collection (venues, reports, menus, menuEdits, hours, mod, votes, photos),
each holding <doc id>.json files with the document's fields (the layout ArtifactData's out_dir writes).
Output: numbered .sql files, each small enough for the Supabase SQL Editor. Run them in order after supabase/schema.sql.
Re-running is safe: existing rows are overwritten with the dump's version.

Usage: python tools/export_supabase.py <dump dir> [<out dir, default supabase/data>]
"""
import glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "supabase", "data")
TABLES = [("venues", "venues"), ("hours", "hours"), ("menus", "menus"), ("menuEdits", "menu_edits"),
          ("reports", "reports"), ("mod", "mod"), ("votes", "votes"), ("photos", "photos")]
MAX_FILE = 700_000  # bytes per file, comfortably inside the SQL Editor's limit
ROWS_PER_INSERT = 50

os.makedirs(OUT, exist_ok=True)
for f in glob.glob(os.path.join(OUT, "*.sql")):
    os.remove(f)

q = lambda s: "'" + s.replace("'", "''") + "'"
files, buf, n_rows = [], [], 0


def flush():
    global buf
    if buf:
        path = os.path.join(OUT, f"{len(files) + 1:02d}.sql")
        open(path, "w", encoding="utf-8").write("".join(buf))
        files.append(path)
        buf = []


for coll, table in TABLES:
    docs = sorted(glob.glob(os.path.join(SRC, coll, "*.json")))
    for i in range(0, len(docs), ROWS_PER_INSERT):
        vals = []
        for f in docs[i:i + ROWS_PER_INSERT]:
            d = json.load(open(f, encoding="utf-8"))
            vals.append(f"({q(os.path.basename(f)[:-5])}, {q(json.dumps(d, ensure_ascii=False, separators=(',', ':')))}::jsonb)")
        stmt = (f"insert into public.{table} (id, data) values\n" + ",\n".join(vals)
                + "\non conflict (id) do update set data = excluded.data;\n")
        if buf and sum(len(b.encode()) for b in buf) + len(stmt.encode()) > MAX_FILE:
            flush()
        buf.append(stmt)
        n_rows += len(vals)
    print(f"{table}: {len(docs)} rows")
flush()
print(f"{n_rows} rows in {len(files)} files -> {OUT}")
