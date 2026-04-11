#!/usr/bin/env python3
"""
NOMAD — Multi-cluster dashboard support

Fixes:
  1. Sync: add source_site to ALL data tables (not just a subset)
  2. Dashboard: per-cluster MAX(timestamp) instead of global
  3. Dashboard: detect non-SLURM clusters (spiderweb) from source_site
  4. Dashboard: node data loader uses per-cluster timestamps

Apply on badenpowell:
    cd ~/nomad
    python3 patch_multi_cluster.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
CLI_PY = REPO / "nomad" / "cli.py"
SERVER_PY = REPO / "nomad" / "viz" / "server.py"

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
print("\n[1] Sync: add source_site to ALL data tables")
# =====================================================================
# Move tables from SAFE_TABLES to NEEDS_SITE_COL so every table
# gets tagged with source_site during merge.

patch(CLI_PY,
    "    # Tables that need a source_site column added during merge\n"
    "    NEEDS_SITE_COL = {\n"
    "        'filesystems', 'queue_state',\n"
    "        'iostat_cpu', 'iostat_device',\n"
    "        'mpstat_core', 'mpstat_summary',\n"
    "        'vmstat', 'nfs_stats',\n"
    "    }\n"
    "\n"
    "    # Tables that already have cluster/hostname disambiguation\n"
    "    SAFE_TABLES = {\n"
    "        'jobs', 'job_summary', 'job_metrics', 'node_state',\n"
    "        'gpu_stats', 'workstation_state', 'group_membership',\n"
    "        'job_accounting', 'alerts', 'cloud_metrics',\n"
    "        'interactive_sessions', 'interactive_summary',\n"
    "        'interactive_servers', 'network_perf',\n"
    "        'storage_state', 'proficiency_scores',\n"
    "    }",

    "    # Tables that get a source_site column during merge.\n"
    "    # Every data table gets tagged so the dashboard can filter by site.\n"
    "    NEEDS_SITE_COL = {\n"
    "        'filesystems', 'queue_state',\n"
    "        'iostat_cpu', 'iostat_device',\n"
    "        'mpstat_core', 'mpstat_summary',\n"
    "        'vmstat', 'nfs_stats',\n"
    "        'jobs', 'job_summary', 'job_metrics', 'node_state',\n"
    "        'gpu_stats', 'workstation_state', 'group_membership',\n"
    "        'job_accounting', 'alert_history',\n"
    "        'interactive_sessions', 'interactive_summary',\n"
    "        'interactive_servers', 'network_perf',\n"
    "        'storage_state', 'proficiency_scores',\n"
    "        'collector_runs',\n"
    "    }\n"
    "\n"
    "    # No longer needed — all tables get source_site\n"
    "    SAFE_TABLES = set()",

    "sync/source_site_all_tables")


# =====================================================================
print("\n[2] Dashboard: per-cluster MAX(timestamp) in cluster loader")
# =====================================================================

patch(SERVER_PY,
    '                SELECT DISTINCT node_name, partitions, gres,\n'
    '                       COALESCE(cluster, \'default\') as cluster\n'
    '                FROM node_state\n'
    '                WHERE timestamp = (SELECT MAX(timestamp) FROM node_state)',

    '                SELECT DISTINCT ns.node_name, ns.partitions, ns.gres,\n'
    '                       COALESCE(ns.cluster, \'default\') as cluster\n'
    '                FROM node_state ns\n'
    '                INNER JOIN (\n'
    '                    SELECT cluster, MAX(timestamp) as max_ts\n'
    '                    FROM node_state\n'
    '                    GROUP BY cluster\n'
    '                ) latest ON ns.cluster = latest.cluster\n'
    '                    AND ns.timestamp = latest.max_ts',

    "dashboard/per_cluster_timestamp_loader")


# =====================================================================
print("\n[3] Dashboard: per-cluster MAX(timestamp) in node data loader")
# =====================================================================

patch(SERVER_PY,
    '                SELECT \n'
    '                    node_name, state, cpus_total, cpus_alloc, cpu_load,\n'
    '                    memory_total_mb, memory_alloc_mb, memory_free_mb,\n'
    '                    cpu_alloc_percent, memory_alloc_percent,\n'
    '                    partitions, reason, gres, is_healthy\n'
    '                FROM node_state\n'
    '                WHERE timestamp = (SELECT MAX(timestamp) FROM node_state)',

    '                SELECT \n'
    '                    ns.node_name, ns.state, ns.cpus_total, ns.cpus_alloc,\n'
    '                    ns.cpu_load,\n'
    '                    ns.memory_total_mb, ns.memory_alloc_mb,\n'
    '                    ns.memory_free_mb,\n'
    '                    ns.cpu_alloc_percent, ns.memory_alloc_percent,\n'
    '                    ns.partitions, ns.reason, ns.gres, ns.is_healthy,\n'
    '                    COALESCE(ns.cluster, \'default\') as cluster\n'
    '                FROM node_state ns\n'
    '                INNER JOIN (\n'
    '                    SELECT cluster, MAX(timestamp) as max_ts\n'
    '                    FROM node_state\n'
    '                    GROUP BY cluster\n'
    '                ) latest ON ns.cluster = latest.cluster\n'
    '                    AND ns.timestamp = latest.max_ts',

    "dashboard/per_cluster_timestamp_nodes")


# =====================================================================
print("\n[4] Dashboard: detect non-SLURM clusters from source_site")
# =====================================================================
# After loading SLURM clusters from node_state, also check for sites
# that only appear in other tables (like spiderweb which has no node_state).
# Add them as workstation-type clusters.

patch(SERVER_PY,
    '                conn.close()\n'
    '                return clusters\n'
    '\n'
    '        except sqlite3.OperationalError:\n'
    '            pass  # Table doesn\'t exist\n'
    '\n'
    '        # Try cluster_monitor\'s node_status table',

    '                # Also detect non-SLURM clusters from source_site\n'
    '                # (e.g., spiderweb has no node_state but has data\n'
    '                # in other tables with source_site column)\n'
    '                try:\n'
    '                    site_tables = [\n'
    '                        "filesystems", "iostat_cpu",\n'
    '                        "interactive_sessions"]\n'
    '                    known_clusters = set(clusters.keys())\n'
    '                    for st in site_tables:\n'
    '                        try:\n'
    '                            sites = conn.execute(\n'
    '                                f"SELECT DISTINCT source_site"\n'
    '                                f" FROM {st}"\n'
    '                                f" WHERE source_site IS NOT NULL"\n'
    '                            ).fetchall()\n'
    '                            for (site,) in sites:\n'
    '                                site_id = site.lower().replace(\n'
    '                                    " ", "-")\n'
    '                                if site_id not in known_clusters:\n'
    '                                    clusters[site_id] = {\n'
    '                                        "name": site,\n'
    '                                        "description":\n'
    '                                            "Workstation/server",\n'
    '                                        "nodes": [],\n'
    '                                        "gpu_nodes": [],\n'
    '                                        "type": "workstation",\n'
    '                                        "partitions": {},\n'
    '                                    }\n'
    '                                    known_clusters.add(site_id)\n'
    '                        except Exception:\n'
    '                            pass\n'
    '                except Exception:\n'
    '                    pass\n'
    '\n'
    '                conn.close()\n'
    '                return clusters\n'
    '\n'
    '        except sqlite3.OperationalError:\n'
    '            pass  # Table doesn\'t exist\n'
    '\n'
    '        # Try cluster_monitor\'s node_status table',

    "dashboard/detect_non_slurm_clusters")


# =====================================================================
print(f"\n{'='*60}")
print(f"Applied: {len(applied)}")
for a in applied:
    print(f"  + {a}")
if skipped:
    print(f"\nSkipped: {len(skipped)}")
    for s in skipped:
        print(f"  - {s}")

print("""
After applying:
  1. Push to GitHub
  2. On mingus: reinstall, re-run sync (to get source_site in all tables)
     rm -rf ~/.local/share/nomad/sync_cache/ combined.db*
     nomad sync
  3. Launch combined dashboard
     nomad dashboard --db combined.db --host 0.0.0.0 --port 8050
  4. Should see tabs for: arachne, spydur, spiderweb
""")
