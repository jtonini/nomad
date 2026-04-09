#!/usr/bin/env python3
"""
NOMAD fix — resilient migration system + node_state cluster column

Two problems:
  1. apply_migration crashes on "duplicate column" when column was manually added
  2. schema.sql missing cluster column in node_state table

Fixes:
  1. apply_migration catches benign SQLite errors (duplicate column, already exists)
     and records the migration as done instead of crashing
  2. schema.sql gets the cluster column for new installs
  3. Migration v4 adds the column for existing databases

Apply on badenpowell:
    cd ~/nomad
    python3 patch_migration_fix.py
    python3 -m pytest tests/ -v
    git add -A && git commit -m "fix: resilient migrations + node_state cluster column"
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
print("\n[1] Make apply_migration handle benign errors gracefully")
# =====================================================================

patch(MIGRATIONS_PY,
    '    def apply_migration(self, version: int, description: str, sql: str) -> None:\n'
    '        """Apply a single migration."""\n'
    '        logger.info(f"Applying migration {version}: {description}")\n'
    '\n'
    '        cursor = self.conn.cursor()\n'
    '        try:\n'
    '            # Execute the migration SQL\n'
    '            cursor.executescript(sql)\n'
    '\n'
    '            # Record the migration\n'
    '            cursor.execute(\n'
    '                "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",\n'
    '                (version, description)\n'
    '            )\n'
    '\n'
    '            self.conn.commit()\n'
    '            logger.info(f"Migration {version} applied successfully")\n'
    '\n'
    '        except Exception as e:\n'
    '            self.conn.rollback()\n'
    '            logger.error(f"Migration {version} failed: {e}")\n'
    '            raise',

    '    def apply_migration(self, version: int, description: str, sql: str) -> None:\n'
    '        """Apply a single migration.\n'
    '\n'
    '        Handles benign errors gracefully:\n'
    '          - "duplicate column name" (column already exists from manual ALTER)\n'
    '          - "already exists" (table/index created outside migrations)\n'
    '        These are recorded as successful so the migration is not retried.\n'
    '        """\n'
    '        logger.info(f"Applying migration {version}: {description}")\n'
    '\n'
    '        cursor = self.conn.cursor()\n'
    '        try:\n'
    '            # Execute the migration SQL\n'
    '            cursor.executescript(sql)\n'
    '\n'
    '            # Record the migration\n'
    '            cursor.execute(\n'
    '                "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",\n'
    '                (version, description)\n'
    '            )\n'
    '\n'
    '            self.conn.commit()\n'
    '            logger.info(f"Migration {version} applied successfully")\n'
    '\n'
    '        except sqlite3.OperationalError as e:\n'
    '            err_msg = str(e).lower()\n'
    '            if "duplicate column" in err_msg or "already exists" in err_msg:\n'
    '                # Benign: schema element already present (manual ALTER, etc.)\n'
    '                self.conn.rollback()\n'
    '                try:\n'
    '                    cursor.execute(\n'
    '                        "INSERT INTO schema_migrations"\n'
    '                        " (version, description) VALUES (?, ?)",\n'
    '                        (version, description)\n'
    '                    )\n'
    '                    self.conn.commit()\n'
    '                except Exception:\n'
    '                    pass\n'
    '                logger.warning(\n'
    '                    f"Migration {version}: {e} (already applied, continuing)")\n'
    '            else:\n'
    '                self.conn.rollback()\n'
    '                logger.error(f"Migration {version} failed: {e}")\n'
    '                raise\n'
    '\n'
    '        except Exception as e:\n'
    '            self.conn.rollback()\n'
    '            logger.error(f"Migration {version} failed: {e}")\n'
    '            raise',

    "migrations/resilient_apply")


# =====================================================================
print("\n[2] schema.sql: add cluster column to node_state")
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
print("\n[3] Add migration v4 for existing databases")
# =====================================================================

MIGRATION_V4 = '''    (4, "Add cluster column to node_state", """
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


# =====================================================================
print(f"\n{'='*60}")
print(f"Applied: {len(applied)}")
for a in applied:
    print(f"  + {a}")
if skipped:
    print(f"\nSkipped: {len(skipped)}")
    for s in skipped:
        print(f"  - {s}")
print()
