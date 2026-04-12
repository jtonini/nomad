#!/usr/bin/env python3
"""
NOMAD — Filter umbrella groups from niche overlap analysis

Groups that contain >80% of all users (e.g., 'managed') overlap with
everything by definition. Exclude them from pairwise overlap computation.

Apply on badenpowell:
    cd ~/nomad
    python3 patch_umbrella_groups.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
NICHE_PY = REPO / "nomad" / "dynamics" / "niche.py"

if not NICHE_PY.exists():
    print(f"Error: {NICHE_PY} not found")
    sys.exit(1)

text = NICHE_PY.read_text()

# Insert umbrella group filter between the query and conn.close()
old = '    rows = conn.execute(query, (cutoff, min_jobs)).fetchall()\n    conn.close()'

new = '''    rows = conn.execute(query, (cutoff, min_jobs)).fetchall()

    # Filter umbrella groups (>80% of all users)
    try:
        total_users = conn.execute(
            "SELECT COUNT(DISTINCT username) FROM group_membership"
        ).fetchone()[0]
        if total_users > 0:
            umbrella = set()
            grp_sizes = conn.execute(
                "SELECT group_name, COUNT(DISTINCT username) as cnt"
                " FROM group_membership GROUP BY group_name"
            ).fetchall()
            for g in grp_sizes:
                if g["cnt"] / total_users > 0.8:
                    umbrella.add(g["group_name"])
            if umbrella:
                rows = [r for r in rows if r["grp"] not in umbrella]
    except Exception:
        pass

    conn.close()'''

if old in text:
    text = text.replace(old, new)
    NICHE_PY.write_text(text)
    print("OK   Umbrella group filter added to niche.py")
else:
    print("Pattern not found")
    # Check what's there
    for i, line in enumerate(text.split('\n')):
        if 'conn.close()' in line or 'fetchall()' in line:
            print(f"  {i}: {line}")
