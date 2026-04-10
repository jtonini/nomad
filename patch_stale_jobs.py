#!/usr/bin/env python3
"""
NOMAD fix — Stale RUNNING job cleanup in slurm collector

Problem: Jobs collected from squeue as RUNNING stay RUNNING in the DB
even after they finish, because the collector only upserts — it never
marks disappeared jobs as completed. Over time, the RUNNING count
grows without bound.

Fix: After storing current squeue data, mark any DB records with
state='RUNNING' that are NOT in the current squeue as 'COMPLETED'.
The sacct collector will later update them with the real exit code.

Apply on badenpowell:
    cd ~/nomad
    python3 patch_stale_jobs.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
SLURM_PY = REPO / "nomad" / "collectors" / "slurm.py"

if not SLURM_PY.exists():
    print(f"Error: {SLURM_PY} not found")
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
print("\n[1] Add stale job cleanup after store")
# =====================================================================

patch(SLURM_PY,
    '            conn.commit()\n'
    '            logger.debug(f"Stored {len(data)} SLURM records")',

    '            # Clean up stale RUNNING jobs that are no longer in squeue.\n'
    '            # When a job finishes between collection cycles, it disappears\n'
    '            # from squeue but stays as RUNNING in the DB. Mark these as\n'
    '            # COMPLETED so counts stay accurate. The sacct collector will\n'
    '            # later update them with the real exit code/state.\n'
    '            current_running = set()\n'
    '            for record in data:\n'
    '                if (record.get(\'type\') == \'job\'\n'
    '                        and record.get(\'state\') in (\'RUNNING\', \'PENDING\')):\n'
    '                    current_running.add(str(record[\'job_id\']))\n'
    '\n'
    '            if current_running:\n'
    '                # Find DB jobs marked RUNNING that are no longer in squeue\n'
    '                try:\n'
    '                    stale_rows = conn.execute(\n'
    '                        "SELECT job_id FROM jobs WHERE state IN (\'RUNNING\', \'PENDING\')"\n'
    '                    ).fetchall()\n'
    '                    stale_ids = [\n'
    '                        r[\'job_id\'] for r in stale_rows\n'
    '                        if str(r[\'job_id\']) not in current_running\n'
    '                    ]\n'
    '                    if stale_ids:\n'
    '                        placeholders = \',\'.join(\'?\' for _ in stale_ids)\n'
    '                        conn.execute(\n'
    '                            f"UPDATE jobs SET state=\'COMPLETED\',"\n'
    '                            f" end_time=datetime(\'now\')"\n'
    '                            f" WHERE job_id IN ({placeholders})",\n'
    '                            stale_ids\n'
    '                        )\n'
    '                        conn.commit()\n'
    '                        logger.info(\n'
    '                            f"Marked {len(stale_ids)} stale jobs"\n'
    '                            f" as COMPLETED (no longer in squeue)")\n'
    '                except Exception as e:\n'
    '                    logger.warning(f"Failed to clean stale jobs: {e}")\n'
    '\n'
    '            conn.commit()\n'
    '            logger.debug(f"Stored {len(data)} SLURM records")',

    "slurm/stale_job_cleanup")


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
