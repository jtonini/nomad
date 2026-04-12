#!/usr/bin/env python3
"""
NOMAD — Fix running jobs, resources dropdown, activity

1. Running jobs: use queue_state for header running/pending count
2. Resources dropdown: populate from all clusters in combined DB
3. Activity: fallback to jobs table when job_accounting is sparse

Apply on badenpowell:
    cd ~/nomad
    python3 patch_running_activity.py
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
print("\n[1] Running jobs: add queue_state running count to node loader")
# =====================================================================
# After loading per-node job stats from the jobs table,
# also load the aggregate running/pending from queue_state
# and inject into the data returned to the frontend.

patch(SERVER_PY,
    '                # Get job statistics per node from jobs table\n'
    '                job_stats = {}\n'
    '                try:\n'
    '                    job_rows = conn.execute("""\n'
    '                        SELECT \n'
    '                            node_list,\n'
    '                            state,\n'
    '                            COUNT(*) as count\n'
    '                        FROM jobs\n'
    '                        GROUP BY node_list, state\n'
    '                    """).fetchall()',

    '                # Get per-partition running/pending from queue_state\n'
    '                # (more accurate than jobs table for live counts)\n'
    '                queue_running = {}\n'
    '                try:\n'
    '                    qrows = conn.execute("""\n'
    '                        SELECT qs.partition,\n'
    '                               qs.running_jobs,\n'
    '                               qs.pending_jobs\n'
    '                        FROM queue_state qs\n'
    '                        INNER JOIN (\n'
    '                            SELECT partition,\n'
    '                                   MAX(timestamp) as mt\n'
    '                            FROM queue_state\n'
    '                            GROUP BY partition\n'
    '                        ) latest\n'
    '                        ON qs.partition = latest.partition\n'
    '                           AND qs.timestamp = latest.mt\n'
    '                    """).fetchall()\n'
    '                    for qr in qrows:\n'
    '                        queue_running[qr["partition"]] = {\n'
    '                            "running": qr["running_jobs"],\n'
    '                            "pending": qr["pending_jobs"],\n'
    '                        }\n'
    '                except Exception:\n'
    '                    pass\n'
    '\n'
    '                # Get job statistics per node from jobs table\n'
    '                job_stats = {}\n'
    '                try:\n'
    '                    job_rows = conn.execute("""\n'
    '                        SELECT \n'
    '                            node_list,\n'
    '                            state,\n'
    '                            COUNT(*) as count\n'
    '                        FROM jobs\n'
    '                        GROUP BY node_list, state\n'
    '                    """).fetchall()',

    "running/load_queue_state")


# Now add queue running/pending to the returned data
# After building the nodes dict, we need the frontend to use queue_state.
# The simplest fix: store queue stats in the DataManager and expose via /api/data.

# Actually, the better approach is to replace the per-node running count
# in the header stats with the queue_state total.
# The JS stats computation already deduplicates by node name.
# Let's add a queue_stats field to the /api/data response.

patch(SERVER_PY,
    '    def get_stats(self):\n'
    '        """Get cluster statistics."""\n',

    '    def get_queue_running(self):\n'
    '        """Get running/pending from queue_state."""\n'
    '        try:\n'
    '            conn = get_db_connection(self.db_path)\n'
    '            rows = conn.execute("""\n'
    '                SELECT qs.partition,\n'
    '                       qs.running_jobs, qs.pending_jobs,\n'
    '                       qs.source_site\n'
    '                FROM queue_state qs\n'
    '                INNER JOIN (\n'
    '                    SELECT partition,\n'
    '                           COALESCE(source_site,\'local\')\n'
    '                               as ss,\n'
    '                           MAX(timestamp) as mt\n'
    '                    FROM queue_state\n'
    '                    GROUP BY partition,\n'
    '                        COALESCE(source_site,\'local\')\n'
    '                ) latest\n'
    '                ON qs.partition = latest.partition\n'
    '                   AND qs.timestamp = latest.mt\n'
    '                   AND COALESCE(qs.source_site,\'local\')\n'
    '                       = latest.ss\n'
    '            """).fetchall()\n'
    '            conn.close()\n'
    '            by_site = {}\n'
    '            for r in rows:\n'
    '                site = r["source_site"] or "local"\n'
    '                if site not in by_site:\n'
    '                    by_site[site] = {\n'
    '                        "running": 0, "pending": 0}\n'
    '                by_site[site]["running"] += (\n'
    '                    r["running_jobs"] or 0)\n'
    '                by_site[site]["pending"] += (\n'
    '                    r["pending_jobs"] or 0)\n'
    '            return by_site\n'
    '        except Exception:\n'
    '            return {}\n'
    '\n'
    '    def get_stats(self):\n'
    '        """Get cluster statistics."""\n',

    "running/get_queue_running_method")


# Add queue_running to /api/data response
patch(SERVER_PY,
    '            self.wfile.write(json.dumps(DashboardHandler.data_manager.get_stats()).encode())',

    '            stats = DashboardHandler.data_manager.get_stats()\n'
    '            stats["queue_running"] = (\n'
    '                DashboardHandler.data_manager\n'
    '                .get_queue_running())\n'
    '            self.wfile.write(json.dumps(stats).encode())',

    "running/add_queue_to_stats_api")


# =====================================================================
print("\n[2] Activity: fallback to jobs table")
# =====================================================================

patch(SERVER_PY,
    "    if 'job_accounting' not in tables:\n"
    "        conn.close()\n"
    "        return empty\n"
    "    group_users = None",

    "    has_accounting = (\n"
    "        'job_accounting' in tables and\n"
    "        c.execute('SELECT COUNT(*) FROM job_accounting'\n"
    "                  ).fetchone()[0] >= 5)\n"
    "    if not has_accounting:\n"
    "        # Fallback: use jobs table for activity\n"
    "        if 'jobs' in tables:\n"
    "            try:\n"
    "                where_j = [\n"
    "                    'start_time >= ?',\n"
    "                    'start_time IS NOT NULL']\n"
    "                params_j = [start]\n"
    "                if cluster != 'all':\n"
    "                    where_j.append('source_site = ?')\n"
    "                    params_j.append(cluster)\n"
    "                c.execute(\n"
    "                    'SELECT start_time, user_name'\n"
    "                    ' FROM jobs WHERE '\n"
    "                    + ' AND '.join(where_j),\n"
    "                    params_j)\n"
    "                grid = [[0]*24 for _ in range(7)]\n"
    "                total = 0\n"
    "                gu2 = None\n"
    "                if group != 'all' and \\\n"
    "                        'group_membership' in tables:\n"
    "                    c2 = conn.cursor()\n"
    "                    c2.execute(\n"
    "                        'SELECT username FROM'\n"
    "                        ' group_membership WHERE'\n"
    "                        ' group_name = ?', (group,))\n"
    "                    gu2 = set(\n"
    "                        r[0] for r in c2.fetchall())\n"
    "                for row in c.fetchall():\n"
    "                    if gu2 and row['user_name'] \\\n"
    "                            not in gu2:\n"
    "                        continue\n"
    "                    try:\n"
    "                        dt = _dt.strptime(\n"
    "                            row['start_time'][:19],\n"
    "                            '%Y-%m-%dT%H:%M:%S')\n"
    "                        grid[dt.weekday()][\n"
    "                            dt.hour] += 1\n"
    "                        total += 1\n"
    "                    except (ValueError, TypeError):\n"
    "                        continue\n"
    "                max_val = max(\n"
    "                    max(row) for row in grid) \\\n"
    "                    if total else 0\n"
    "                busiest = quietest = None\n"
    "                if total:\n"
    "                    days = ['Monday','Tuesday',\n"
    "                        'Wednesday','Thursday',\n"
    "                        'Friday','Saturday',\n"
    "                        'Sunday']\n"
    "                    best = (0, 0, 0)\n"
    "                    worst = (0, 0, 999999)\n"
    "                    for d in range(7):\n"
    "                        for h in range(24):\n"
    "                            v = grid[d][h]\n"
    "                            if v > best[2]:\n"
    "                                best = (d, h, v)\n"
    "                            if v < worst[2]:\n"
    "                                worst = (d, h, v)\n"
    "                    busiest = {\n"
    "                        'day': days[best[0]],\n"
    "                        'hour': f'{best[1]}:00',\n"
    "                        'count': best[2]}\n"
    "                    quietest = {\n"
    "                        'day': days[worst[0]],\n"
    "                        'hour': f'{worst[1]}:00',\n"
    "                        'count': worst[2]}\n"
    "                all_clusters = []\n"
    "                try:\n"
    "                    all_clusters = sorted(set(\n"
    "                        r[0] for r in c.execute(\n"
    "                            'SELECT DISTINCT'\n"
    "                            ' source_site FROM jobs'\n"
    "                            ' WHERE source_site'\n"
    "                            ' IS NOT NULL'\n"
    "                        ).fetchall()))\n"
    "                except Exception:\n"
    "                    pass\n"
    "                all_groups = []\n"
    "                try:\n"
    "                    all_groups = sorted(set(\n"
    "                        r[0] for r in c.execute(\n"
    "                            'SELECT DISTINCT'\n"
    "                            ' group_name FROM'\n"
    "                            ' group_membership'\n"
    "                        ).fetchall()))\n"
    "                except Exception:\n"
    "                    pass\n"
    "                conn.close()\n"
    "                return {\n"
    "                    'grid': grid,\n"
    "                    'max_value': max_val,\n"
    "                    'total_jobs': total,\n"
    "                    'busiest': busiest,\n"
    "                    'quietest': quietest,\n"
    "                    'filters': {\n"
    "                        'clusters': all_clusters,\n"
    "                        'groups': all_groups,\n"
    "                    },\n"
    "                }\n"
    "            except Exception:\n"
    "                pass\n"
    "        conn.close()\n"
    "        return empty\n"
    "    group_users = None",

    "activity/fallback_jobs_table")


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
