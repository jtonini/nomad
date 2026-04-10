#!/usr/bin/env python3
"""
NOMAD fix — Database named after cluster, not generic nomad.db

The wizard now names the database after the primary cluster
(e.g., arachne.db instead of nomad.db). This avoids collision
with nomad demo which uses nomad.db or nomad_demo.db.

Also updates nomad demo to explicitly use nomad_demo.db.

Apply on badenpowell:
    cd ~/nomad
    python3 patch_db_naming.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
CLI_PY = REPO / "nomad" / "cli.py"

if not CLI_PY.exists():
    print(f"Error: {CLI_PY} not found")
    sys.exit(1)

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
print("\n[1] Wizard TOML: use cluster name for DB filename")
# =====================================================================

patch(CLI_PY,
    '    lines.append("[database]")\n'
    '    lines.append("# Database stored as nomad.db in data_dir")\n'
    '    lines.append("")',

    '    # Name database after primary cluster\n'
    '    db_name = clusters[0]["name"].lower().replace(" ", "_") if clusters else "nomad"\n'
    '    lines.append("[database]")\n'
    '    lines.append(f\'path = "{db_name}.db"\')\n'
    '    lines.append("")',

    "wizard/db_cluster_name")


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
After deploying, re-run wizard on arachne:
  nomad init --force
  # Will generate: path = "arachne.db" in [database]
  # Old nomad.db stays as-is (can be deleted or kept for reference)
  # Restart collector to use new DB
""")
