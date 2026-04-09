#!/usr/bin/env python3
"""
NOMAD hotfix — node_state missing cluster column

The schema.sql (migration v1) creates node_state without a 'cluster' column,
but the NodeStateCollector tries to INSERT into it. This adds:
  1. The column to schema.sql (for new installs)
  2. Migration v4 to ALTER existing databases

Apply on badenpowell:
    cd ~/nomad
    python3 patch_node_state_cluster.py
    python3 -m pytest tests/ -v
    git add -A && git commit -m "fix: add cluster column to node_state schema + migration v4"
    git push origin main
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
SCHEMA_SQL = REPO / "nomad" / "db" / "schema.sql"
MIGRATIONS_PY = REPO / "nomad" / "db" / "migrations.py"

applied = []
skipped = []


def patch(path, old, new, label):
    text = path.read_text()
    if old not in text:
        skipped.append(f"{label} -- pattern not found")
        return False
    if new in text:
        skipped.append(f"{label} -- already applied")
        return False
    path.write_text(text.replace(old, new, 1))
    applied.append(label)
    print(f"  OK   {label}")
    return True


# =====================================================================
print("\n[1] schema.sql: add cluster column to node_state")
# =====================================================================

if SCHEMA_SQL.exists():
    patch(SCHEMA_SQL,
        "    memory_alloc_percent REAL,\n"
        "    partitions TEXT,",

        "    memory_alloc_percent REAL,\n"
        "    cluster TEXT DEFAULT 'default',\n"
        "    partitions TEXT,",

        "schema.sql/node_state_cluster")
else:
    skipped.append("schema.sql not found")


# =====================================================================
print("\n[2] migrations.py: add migration v4 for existing databases")
# =====================================================================

if MIGRATIONS_PY.exists():
    # Find the end of the MIGRATIONS list and add v4 before the closing ]
    # The list ends with the collector_runs migration
    MIGRATION_V4 = '''
    (4, "Add cluster column to node_state", """
        ALTER TABLE node_state ADD COLUMN cluster TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_node_state_cluster
            ON node_state(cluster);
    """),
'''

    patch(MIGRATIONS_PY,
        '        CREATE INDEX idx_collector_runs_name ON collector_runs(collector_name);\n'
        '    """),\n'
        ']',

        '        CREATE INDEX idx_collector_runs_name ON collector_runs(collector_name);\n'
        '    """),\n'
        + MIGRATION_V4 +
        ']',

        "migrations/v4_cluster_column")
else:
    skipped.append("migrations.py not found")


# =====================================================================
# Summary
# =====================================================================
print(f"\n{'='*60}")
print(f"Applied: {len(applied)}")
for a in applied:
    print(f"  + {a}")
if skipped:
    print(f"\nSkipped: {len(skipped)}")
    for s in skipped:
        print(f"  - {s}")

print(f"""
On arachne after update:
  nomad collect --once --collector node_state
  (migration v4 runs automatically via ensure_database)
""")
