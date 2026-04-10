#!/usr/bin/env python3
"""
NOMAD fix — Dashboard partition grouping and per-node job display

Issues:
  1. Partitions show 1/1 nodes because nodes grouped by primary partition only
     (node in cpunodes+one only shows under cpunodes)
  2. Asterisks in SLURM partition names (cpunodes*) not stripped
  3. Second node card rendering path still shows "0 jobs" instead of running count
  4. Partition summary shows "0 jobs" instead of running count

Apply on badenpowell:
    cd ~/nomad
    python3 patch_dashboard_partitions.py
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


def patch_all(path, old, new, label):
    text = path.read_text()
    n = text.count(old)
    if n == 0:
        skipped.append(f"{label} -- pattern not found")
        return False
    if new in text:
        skipped.append(f"{label} -- already applied")
        return False
    path.write_text(text.replace(old, new))
    applied.append(f"{label} ({n}x)")
    print(f"  OK   {label} ({n} occurrences)")
    return True


# =====================================================================
print("\n[1] Fix node_state loader: strip asterisks, assign to ALL partitions")
# =====================================================================

patch(SERVER_PY,
    '                for row in rows:\n'
    '                    node = row[\'node_name\']\n'
    '                    cluster = row[\'cluster\'] or \'default\'\n'
    '                    partitions = row[\'partitions\'] or \'default\'\n'
    '                    primary_partition = partitions.split(\',\')[0]\n'
    '                    cluster_data[cluster][primary_partition].append(node)',

    '                for row in rows:\n'
    '                    node = row[\'node_name\']\n'
    '                    cluster = row[\'cluster\'] or \'default\'\n'
    '                    partitions = row[\'partitions\'] or \'default\'\n'
    '                    # Strip SLURM asterisks and assign node to ALL its partitions\n'
    '                    for part in partitions.split(\',\'):\n'
    '                        part = part.strip().rstrip(\'*\')\n'
    '                        if part:\n'
    '                            cluster_data[cluster][part].append(node)',

    "loader/all_partitions")


# =====================================================================
print("\n[2] Fix second node card: show running jobs")
# =====================================================================

patch(SERVER_PY,
    "{node.status === 'down' ? (node.slurm_state || 'OFFLINE') : `${node.jobs_today || 0} jobs`}",

    "{node.status === 'down' ? (node.slurm_state || 'OFFLINE') : (node.jobs_running > 0 ? `${node.jobs_running} running` : `${node.jobs_today || 0} jobs`)}",

    "frontend/node_card_running_v2")


# =====================================================================
print("\n[3] Fix partition summary: show running jobs")
# =====================================================================

patch(SERVER_PY,
    '                                            <span className="partition-jobs">\n'
    "                                                {totalJobs} jobs  <span style={{color: '#22c55e'}}>{okJobs} ok</span>  <span style={{color: '#ef4444'}}>{failJobs} fail</span>",

    '                                            <span className="partition-jobs">\n'
    "                                                {totalRunning > 0 ? <><span style={{color: '#3b82f6'}}>{totalRunning} running</span>{'  '}</> : ''}"
    "{okJobs > 0 ? <><span style={{color: '#22c55e'}}>{okJobs} ok</span>{'  '}</> : ''}"
    "{failJobs > 0 ? <span style={{color: '#ef4444'}}>{failJobs} fail</span> : ''}"
    "{totalRunning === 0 && okJobs === 0 && failJobs === 0 ? '0 jobs' : ''}",

    "frontend/partition_summary")


# =====================================================================
print("\n[4] Fix fallback nodes loader: strip asterisks too")
# =====================================================================

# The fallback loader (from nodes table) also doesn't strip asterisks
patch(SERVER_PY,
    '                for row in rows:\n'
    '                    node = row["hostname"]\n'
    '                    cluster_name = row["cluster"] or "default"\n'
    '                    partitions = row["partition"] or "default"\n'
    '                    primary_part = partitions.split(",")[0]\n'
    '                    partition_node_map[cluster_name][primary_part].append(node)',

    '                for row in rows:\n'
    '                    node = row["hostname"]\n'
    '                    cluster_name = row["cluster"] or "default"\n'
    '                    partitions = row["partition"] or "default"\n'
    '                    # Assign node to ALL its partitions, strip asterisks\n'
    '                    for part in partitions.split(","):\n'
    '                        part = part.strip().rstrip("*")\n'
    '                        if part:\n'
    '                            partition_node_map[cluster_name][part].append(node)',

    "loader/fallback_all_partitions")


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
