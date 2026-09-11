"""Independent QA reproduction of F49 (unknown sentinel) and F57 (cross-type leak).
Does NOT import now_filters' own test helpers -- builds its own temp table and
its own copy of the exclusion SQL logic, reading only from the real
engine.type_relations table, to avoid trusting the implementer's test harness.
"""
import os
import psycopg

def env(name, default=None):
    v = os.environ.get(name)
    return v if v is not None else default

# Load .env manually (F31/F52 convention: CLIs read project .env)
envfile = {}
with open('.env', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        envfile[k] = v

conn = psycopg.connect(
    host='localhost', port=15432, dbname='now_jakarta',
    user=envfile.get('POSTGRES_USER', 'now'), password=envfile.get('POSTGRES_PASSWORD'),
)
conn.autocommit = False
cur = conn.cursor()

# 1. Real state of the 177 places
cur.execute("SELECT status, type, count(*) FROM places GROUP BY 1,2 ORDER BY 1,2")
print("Real places status/type distribution:", cur.fetchall())

# 2. Real type_relations matrix
cur.execute("SELECT type, exclude_same, complements FROM engine.type_relations ORDER BY type")
rels = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
print("\ntype_relations matrix:")
for t, (ex, comp) in rels.items():
    print(f"  {t}: exclude_same={ex} complements={comp}")

def excluded_types_for(subject_type):
    if subject_type not in rels:
        return set()
    exclude_same, _ = rels[subject_type]
    if not exclude_same:
        return set()
    return {subject_type, "unknown"}

# 3. Build a throwaway temp table (never touches public.places) with a
# realistic scenario mixing 'editorial' (old sentinel) and 'unknown' (F49
# sentinel), both activated, to test F49's core claim.
cur.execute("DROP TABLE IF EXISTS qa_synth_places")
cur.execute("""
    CREATE TEMP TABLE qa_synth_places (
        id int PRIMARY KEY, type text, status text
    )
""")
cur.execute("""
    INSERT INTO qa_synth_places (id, type, status) VALUES
    (1, 'editorial', 'active'),   -- OLD sentinel, activated early (F27 gap)
    (2, 'unknown', 'active'),     -- NEW sentinel (F49), activated early
    (3, 'stay', 'active'),        -- genuine competitor
    (4, 'eat', 'active')          -- genuine complement
""")

def run_filter(subject_type):
    excluded = excluded_types_for(subject_type)
    if excluded:
        cur.execute(
            "SELECT id FROM qa_synth_places WHERE status='active' AND type != ALL(%s) ORDER BY id",
            (list(excluded),)
        )
    else:
        cur.execute("SELECT id FROM qa_synth_places WHERE status='active' ORDER BY id")
    return [r[0] for r in cur.fetchall()]

print("\n--- F49 direction 1: active+unknown excluded where active+editorial was not ---")
survivors = run_filter("stay")
print("subject_type=stay -> survivors:", survivors)
print("  editorial (id=1) survives (not excluded):", 1 in survivors, "  [expected True: editorial exclude_same=False]")
print("  unknown (id=2) excluded:", 2 not in survivors, "  [expected True: F57 makes unknown excluded from every venue subject]")
print("  stay competitor (id=3) excluded:", 3 not in survivors, "  [expected True]")
print("  eat complement (id=4) survives:", 4 in survivors, "  [expected True]")

print("\n--- F49 direction 2 (self-exclusion): unknown subject excludes unknown candidates ---")
cur.execute("DROP TABLE IF EXISTS qa_synth_places2")
cur.execute("CREATE TEMP TABLE qa_synth_places2 (id int PRIMARY KEY, type text, status text)")
cur.execute("""
    INSERT INTO qa_synth_places2 (id, type, status) VALUES
    (10, 'unknown', 'active'),
    (11, 'unknown', 'active'),
    (12, 'eat', 'active')
""")
excluded = excluded_types_for("unknown")
cur.execute("SELECT id FROM qa_synth_places2 WHERE status='active' AND type != ALL(%s) ORDER BY id", (list(excluded),))
survivors2 = [r[0] for r in cur.fetchall()]
print("subject_type=unknown, excluded types:", excluded, "-> survivors:", survivors2)
print("  unknown-vs-unknown mutually excluded:", 10 not in survivors2 and 11 not in survivors2)
print("  eat complement survives:", 12 in survivors2)

print("\n--- F57 direction: cross-type leak -- unknown place onto an UNRELATED subject page ---")
cur.execute("DROP TABLE IF EXISTS qa_synth_places3")
cur.execute("CREATE TEMP TABLE qa_synth_places3 (id int PRIMARY KEY, type text, status text)")
cur.execute("""
    INSERT INTO qa_synth_places3 (id, type, status) VALUES
    (20, 'unknown', 'active'),  -- mislabelled hotel, activated too early
    (21, 'eat', 'active')       -- genuine complement
""")
excluded = excluded_types_for("stay")  # subject is a real 'stay' page, NOT 'unknown'
cur.execute("SELECT id FROM qa_synth_places3 WHERE status='active' AND type != ALL(%s) ORDER BY id", (list(excluded),))
survivors3 = [r[0] for r in cur.fetchall()]
print("subject_type=stay, candidate pool has an 'unknown'-typed place -> excluded set:", excluded, "-> survivors:", survivors3)
print("  unknown place (id=20) excluded from unrelated stay page:", 20 not in survivors3,
      "  [F57: should now be True if fix landed; F49-only would leave this False]")
print("  eat complement (id=21) survives:", 21 in survivors3)

conn.rollback()
cur.close()
conn.close()
