#!/usr/bin/env python3
"""
NOMAD — Multi-cluster dashboard fixes

1. Network tooltip: show cluster/source_site for each job
2. Storage page: fallback to filesystems table when storage_state empty

Apply on badenpowell:
    cd ~/nomad
    python3 patch_multi_cluster_fixes.py
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
print("\n[1] Network: add source_site to job SQL query")
# =====================================================================
# The load_jobs_from_db SELECT needs to include source_site if available

patch(SERVER_PY,
    '                SELECT \n'
    '                    j.job_id,\n'
    '                    j.user_name,\n'
    '                    j.state,\n'
    '                    j.partition,',

    '                SELECT \n'
    '                    j.job_id,\n'
    '                    j.user_name,\n'
    '                    j.state,\n'
    '                    j.partition,\n'
    '                    j.source_site,',

    "network/sql_source_site")


# =====================================================================
print("\n[2] Network: add source_site to job dict")
# =====================================================================

patch(SERVER_PY,
    '                    jobs.append({\n'
    '                        "job_id": job_id,\n'
    '                        "user_name": row[\'user_name\'] or \'—\',\n'
    '                        "state": row[\'state\'],',

    '                    jobs.append({\n'
    '                        "job_id": job_id,\n'
    '                        "user_name": row[\'user_name\'] or \'—\',\n'
    '                        "source_site": row_get(row, \'source_site\') or \'—\',\n'
    '                        "state": row[\'state\'],',

    "network/dict_source_site")


# =====================================================================
print("\n[3] Network: add source_site (Cluster) to tooltip")
# =====================================================================

patch(SERVER_PY,
    '                            <div><span style="color: #8b949e;">User:</span> ${job.user_name || \'—\'}</div>\n'
    '                            <div><span style="color: #8b949e;">Partition:</span> ${job.partition || \'—\'}</div>',

    '                            <div><span style="color: #8b949e;">User:</span> ${job.user_name || \'—\'}</div>\n'
    '                            <div><span style="color: #8b949e;">Cluster:</span> ${job.source_site || \'—\'}</div>\n'
    '                            <div><span style="color: #8b949e;">Partition:</span> ${job.partition || \'—\'}</div>',

    "network/tooltip_source_site")


# =====================================================================
print("\n[4] Storage: fallback to filesystems table")
# =====================================================================
# When storage_state is empty, show disk usage from filesystems table

patch(SERVER_PY,
    "            except Exception:\n"
    "                devices, summary = [], {}\n"
    "            self.wfile.write(json.dumps({'devices': devices, 'summary': summary}).encode())",

    "            except Exception:\n"
    "                devices, summary = [], {}\n"
    "\n"
    "            # Fallback: if no storage_state data, use filesystems table\n"
    "            if not devices:\n"
    "                try:\n"
    "                    conn2 = _sql.connect(str(dm.db_path))\n"
    "                    conn2.row_factory = _sql.Row\n"
    "                    c2 = conn2.cursor()\n"
    "                    # Get latest filesystem entry per path (per source_site)\n"
    "                    try:\n"
    "                        c2.execute(\"\"\"\n"
    "                            SELECT f.path, f.total_bytes, f.used_bytes,\n"
    "                                   f.available_bytes, f.used_percent,\n"
    "                                   f.timestamp, f.source_site,\n"
    "                                   f.days_until_full\n"
    "                            FROM filesystems f\n"
    "                            INNER JOIN (\n"
    "                                SELECT path,\n"
    "                                       COALESCE(source_site, 'local')\n"
    "                                           as ss,\n"
    "                                       MAX(timestamp) as max_ts\n"
    "                                FROM filesystems\n"
    "                                GROUP BY path,\n"
    "                                    COALESCE(source_site, 'local')\n"
    "                            ) latest\n"
    "                            ON f.path = latest.path\n"
    "                               AND f.timestamp = latest.max_ts\n"
    "                               AND COALESCE(f.source_site, 'local')\n"
    "                                   = latest.ss\n"
    "                        \"\"\")\n"
    "                    except Exception:\n"
    "                        # source_site column may not exist\n"
    "                        c2.execute(\"\"\"\n"
    "                            SELECT f.path, f.total_bytes, f.used_bytes,\n"
    "                                   f.available_bytes, f.used_percent,\n"
    "                                   f.timestamp, NULL as source_site,\n"
    "                                   f.days_until_full\n"
    "                            FROM filesystems f\n"
    "                            INNER JOIN (\n"
    "                                SELECT path, MAX(timestamp) as max_ts\n"
    "                                FROM filesystems GROUP BY path\n"
    "                            ) latest\n"
    "                            ON f.path = latest.path\n"
    "                               AND f.timestamp = latest.max_ts\n"
    "                        \"\"\")\n"
    "                    fs_rows = c2.fetchall()\n"
    "                    for row in fs_rows:\n"
    "                        site = row['source_site'] or 'local'\n"
    "                        devices.append({\n"
    "                            'hostname': site,\n"
    "                            'filesystem_type': 'disk',\n"
    "                            'mount_point': row['path'],\n"
    "                            'total_bytes': row['total_bytes'],\n"
    "                            'used_bytes': row['used_bytes'],\n"
    "                            'available_bytes':\n"
    "                                row['available_bytes'],\n"
    "                            'used_percent': row['used_percent'],\n"
    "                            'timestamp': row['timestamp'],\n"
    "                            'days_until_full':\n"
    "                                row['days_until_full'],\n"
    "                        })\n"
    "                    summary = {\n"
    "                        'total': len(devices),\n"
    "                        'total_bytes': sum(\n"
    "                            d.get('total_bytes', 0) or 0\n"
    "                            for d in devices),\n"
    "                        'used_bytes': sum(\n"
    "                            d.get('used_bytes', 0) or 0\n"
    "                            for d in devices),\n"
    "                        'nfs_clients': 0,\n"
    "                    }\n"
    "                    conn2.close()\n"
    "                except Exception:\n"
    "                    pass\n"
    "\n"
    "            self.wfile.write(json.dumps({'devices': devices, 'summary': summary}).encode())",

    "storage/filesystems_fallback")


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
