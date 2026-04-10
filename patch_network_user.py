#!/usr/bin/env python3
"""
NOMAD fix — Show user_name in network view job tooltip

Apply on badenpowell:
    cd ~/nomad
    python3 patch_network_user.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
SERVER_PY = REPO / "nomad" / "viz" / "server.py"

if not SERVER_PY.exists():
    print(f"Error: {SERVER_PY} not found")
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
print("\n[1] Add user_name to SQL SELECT in load_jobs_from_db")
# =====================================================================

patch(SERVER_PY,
    '                SELECT \n'
    '                    j.job_id,\n'
    '                    j.state,\n'
    '                    j.partition,',

    '                SELECT \n'
    '                    j.job_id,\n'
    '                    j.user_name,\n'
    '                    j.state,\n'
    '                    j.partition,',

    "sql/add_user_name")


# =====================================================================
print("\n[2] Add user_name to job dict")
# =====================================================================

patch(SERVER_PY,
    '                    jobs.append({\n'
    '                        "job_id": job_id,\n'
    '                        "state": row[\'state\'],\n'
    '                        "partition": row[\'partition\'],',

    '                    jobs.append({\n'
    '                        "job_id": job_id,\n'
    '                        "user_name": row[\'user_name\'] or \'—\',\n'
    '                        "state": row[\'state\'],\n'
    '                        "partition": row[\'partition\'],',

    "dict/add_user_name")


# =====================================================================
print("\n[3] Add user to tooltip template")
# =====================================================================

patch(SERVER_PY,
    '                            <div><span style="color: #8b949e;">Partition:</span> ${job.partition || \'—\'}</div>\n'
    '                            <div><span style="color: #8b949e;">Runtime:</span> ${formatValue(job.runtime_sec)}s</div>',

    '                            <div><span style="color: #8b949e;">User:</span> ${job.user_name || \'—\'}</div>\n'
    '                            <div><span style="color: #8b949e;">Partition:</span> ${job.partition || \'—\'}</div>\n'
    '                            <div><span style="color: #8b949e;">Runtime:</span> ${formatValue(job.runtime_sec)}s</div>',

    "tooltip/add_user")


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
