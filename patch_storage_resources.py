#!/usr/bin/env python3
"""
NOMAD — Fix storage display and resources fallback

1. Storage: fix field mapping (used_percent -> usage_pct, add mount_point)
2. Resources: fallback to jobs table when job_accounting is empty

Apply on badenpowell:
    cd ~/nomad
    python3 patch_storage_resources.py
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
print("\n[1] Storage API: fix filesystems fallback field names")
# =====================================================================
# The frontend expects: hostname, usage_pct, storage_type, mount_point
# The current fallback sends: hostname, used_percent, filesystem_type

patch(SERVER_PY,
    "                    for row in fs_rows:\n"
    "                        site = row['source_site'] or 'local'\n"
    "                        devices.append({\n"
    "                            'hostname': site,\n"
    "                            'filesystem_type': 'disk',\n"
    "                            'mount_point': row['path'],",

    "                    for row in fs_rows:\n"
    "                        site = row['source_site'] or 'local'\n"
    "                        devices.append({\n"
    "                            'hostname':\n"
    "                                f\"{site}:{row['path']}\",\n"
    "                            'storage_type': 'disk',\n"
    "                            'mount_point': row['path'],\n"
    "                            'status': 'online',",

    "storage/fix_hostname_mount")


patch(SERVER_PY,
    "                            'used_percent': row['used_percent'],",

    "                            'used_percent': row['used_percent'],\n"
    "                            'usage_pct': row['used_percent'],",

    "storage/add_usage_pct")


# =====================================================================
print("\n[2] Resources: fallback to jobs table when job_accounting empty")
# =====================================================================
# The Resources panel queries job_accounting for cpu_hours/gpu_hours.
# When job_accounting is empty/sparse, fallback to computing from jobs table.

patch(SERVER_PY,
    "    if 'job_accounting' not in tables:\n"
    "        conn.close()\n"
    "        return empty",

    "    if 'job_accounting' not in tables or (\n"
    "            'job_accounting' in tables and\n"
    "            c.execute('SELECT COUNT(*) FROM job_accounting'\n"
    "                      ).fetchone()[0] < 5):\n"
    "        # Fallback: compute from jobs table\n"
    "        if 'jobs' in tables:\n"
    "            try:\n"
    "                where_j = ['end_time >= ?']\n"
    "                params_j = [start]\n"
    "                if cluster != 'all':\n"
    "                    where_j.append(\n"
    "                        \"source_site = ?\")\n"
    "                    params_j.append(cluster)\n"
    "                c.execute(\"\"\"\n"
    "                    SELECT user_name as username,\n"
    "                        COALESCE(source_site, 'unknown')\n"
    "                            as cluster,\n"
    "                        SUM(CASE WHEN req_gpus > 0\n"
    "                            THEN runtime_seconds/3600.0\n"
    "                            ELSE 0 END) as gpu_hours,\n"
    "                        SUM(CASE WHEN req_gpus = 0\n"
    "                                      OR req_gpus IS NULL\n"
    "                            THEN req_cpus *\n"
    "                                 runtime_seconds/3600.0\n"
    "                            ELSE 0 END) as cpu_hours,\n"
    "                        COUNT(*) as jobs\n"
    "                    FROM jobs\n"
    "                    WHERE \"\"\" + ' AND '.join(where_j)\n"
    "                    + ' GROUP BY username, cluster',\n"
    "                    params_j)\n"
    "                user_rows = c.fetchall()\n"
    "                grp_map = {}\n"
    "                if 'group_membership' in tables:\n"
    "                    c.execute(\n"
    "                        'SELECT username, group_name'\n"
    "                        ' FROM group_membership')\n"
    "                    for row in c.fetchall():\n"
    "                        grp_map.setdefault(\n"
    "                            row['username'], []\n"
    "                        ).append(row['group_name'])\n"
    "                users = []\n"
    "                for row in user_rows:\n"
    "                    u = row['username']\n"
    "                    ugroups = grp_map.get(u, [])\n"
    "                    if group != 'all' and \\\n"
    "                            group not in ugroups:\n"
    "                        continue\n"
    "                    users.append({\n"
    "                        'username': u,\n"
    "                        'cluster': row['cluster'],\n"
    "                        'cpu_hours': round(\n"
    "                            row['cpu_hours'] or 0, 1),\n"
    "                        'gpu_hours': round(\n"
    "                            row['gpu_hours'] or 0, 1),\n"
    "                        'jobs': row['jobs'],\n"
    "                        'groups': ugroups,\n"
    "                    })\n"
    "                gtotals = {}\n"
    "                for u in users:\n"
    "                    for g in u['groups']:\n"
    "                        if g not in gtotals:\n"
    "                            gtotals[g] = {\n"
    "                                'name': g,\n"
    "                                'cpu_hours': 0,\n"
    "                                'gpu_hours': 0,\n"
    "                                'jobs': 0,\n"
    "                                'users': set()}\n"
    "                        gtotals[g]['cpu_hours'] += \\\n"
    "                            u['cpu_hours']\n"
    "                        gtotals[g]['gpu_hours'] += \\\n"
    "                            u['gpu_hours']\n"
    "                        gtotals[g]['jobs'] += u['jobs']\n"
    "                        gtotals[g]['users'].add(\n"
    "                            u['username'])\n"
    "                groups_list = []\n"
    "                for g in sorted(\n"
    "                        gtotals.values(),\n"
    "                        key=lambda x: x['jobs'],\n"
    "                        reverse=True):\n"
    "                    g['users'] = len(g['users'])\n"
    "                    groups_list.append(g)\n"
    "                all_clusters = sorted(set(\n"
    "                    u['cluster'] for u in users))\n"
    "                all_groups = sorted(set(\n"
    "                    g for u in users\n"
    "                    for g in u['groups']))\n"
    "                conn.close()\n"
    "                return {\n"
    "                    'groups': groups_list,\n"
    "                    'users': sorted(\n"
    "                        users,\n"
    "                        key=lambda x: x['jobs'],\n"
    "                        reverse=True),\n"
    "                    'totals': {\n"
    "                        'cpu_hours': round(sum(\n"
    "                            u['cpu_hours']\n"
    "                            for u in users), 1),\n"
    "                        'gpu_hours': round(sum(\n"
    "                            u['gpu_hours']\n"
    "                            for u in users), 1),\n"
    "                        'jobs': sum(\n"
    "                            u['jobs'] for u in users),\n"
    "                        'users': len(set(\n"
    "                            u['username']\n"
    "                            for u in users)),\n"
    "                    },\n"
    "                    'filters': {\n"
    "                        'clusters': all_clusters,\n"
    "                        'groups': all_groups,\n"
    "                    },\n"
    "                }\n"
    "            except Exception:\n"
    "                pass\n"
    "        conn.close()\n"
    "        return empty",

    "resources/fallback_jobs_table")


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
