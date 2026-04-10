#!/usr/bin/env python3
"""
NOMAD fix — Dashboard remaining issues

1. Per-node cards in partition view show "0 jobs" (reads jobs_today not jobs_running)
2. Cluster description says "10-node" instead of "6-node" (duplicates in all_nodes)
3. Dashboard shows all partitions instead of configured ones

Apply on badenpowell:
    cd ~/nomad
    python3 patch_dashboard_final.py
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
print("\n[1] Fix partition-view node card: show running jobs")
# =====================================================================
# This is the SECOND rendering path (inside the partition loop at ~line 4395)
# that was never patched. The first path (flat view) was already fixed.

patch(SERVER_PY,
    '                                                <div className="node-jobs">\n'
    "                                                    {node.status === 'down' ? (node.slurm_state || 'OFFLINE') : `${node.jobs_today || 0} jobs`}\n"
    '                                                </div>\n'
    '                                                <div className="node-gpu-badge"',

    '                                                <div className="node-jobs">\n'
    "                                                    {node.status === 'down' ? (node.slurm_state || 'OFFLINE') : (node.jobs_running > 0 ? `${node.jobs_running} running` : `${node.jobs_today || 0} jobs`)}\n"
    '                                                </div>\n'
    '                                                <div className="node-gpu-badge"',

    "frontend/partition_node_card_running")


# =====================================================================
print("\n[2] Fix cluster node count: deduplicate all_nodes")
# =====================================================================

patch(SERVER_PY,
    '                for cluster_name, part_map in cluster_data.items():\n'
    '                    all_nodes = []\n'
    '                    for p_nodes in part_map.values():\n'
    '                        all_nodes.extend(p_nodes)\n'
    '                    cluster_id = cluster_name.lower().replace(\' \', \'-\')\n'
    '                    clusters[cluster_id] = {\n'
    '                        "name": cluster_name,\n'
    '                        "description": f"{len(all_nodes)}-node cluster",\n'
    '                        "nodes": sorted(all_nodes),',

    '                for cluster_name, part_map in cluster_data.items():\n'
    '                    all_nodes_set = set()\n'
    '                    for p_nodes in part_map.values():\n'
    '                        all_nodes_set.update(p_nodes)\n'
    '                    all_nodes = sorted(all_nodes_set)\n'
    '                    cluster_id = cluster_name.lower().replace(\' \', \'-\')\n'
    '                    clusters[cluster_id] = {\n'
    '                        "name": cluster_name,\n'
    '                        "description": f"{len(all_nodes)}-node cluster",\n'
    '                        "nodes": all_nodes,',

    "backend/dedup_all_nodes")


# =====================================================================
print("\n[3] Fix dashboard: filter partitions by TOML config")
# =====================================================================
# The dashboard reads partitions from node_state (all SLURM partitions).
# It should filter to only show partitions in the TOML collectors.slurm.partitions.
# We do this by reading the config and passing configured partitions to the
# cluster data loader, then filtering the partition map.

# The approach: in load_node_data_from_db, after building the cluster,
# check if a TOML config exists and filter partitions accordingly.
# But the dashboard code doesn't have easy access to the TOML config.
#
# Simpler approach: pass configured_partitions to load_clusters_from_db.
# But that requires changing the function signature.
#
# Even simpler: read the TOML config at dashboard startup and filter.
# The dashboard already reads config in NomadDataSource.__init__

# Let me check if there's already a way to get configured partitions
# Actually, the cleanest approach is to filter in the JS. 
# If cluster.configured_partitions exists, only show those.
# We add that field from the TOML config.

# First, let's add configured_partitions to the cluster data when config is available.
# The dashboard's NomadDataSource reads config. Let me trace that path.

# For now, a simpler approach: read the config in load_clusters_from_db
# and use it to filter. But load_clusters_from_db doesn't receive config.
#
# Simplest fix that works: in the dashboard JS, add a filter that checks
# if the node exists in the TOML partition. But the JS doesn't have TOML access.
#
# Most practical fix for now: have the backend annotate each cluster with
# configured partitions from the TOML config file.

# Check if NomadDataSource has config access
text = SERVER_PY.read_text()

# Find where clusters are loaded in NomadDataSource
if "self._clusters = load_clusters_from_db" in text:
    patch(SERVER_PY,
        '            self._clusters = load_clusters_from_db(self.db_path)\n'
        '\n'
        '            if self._clusters:',

        '            self._clusters = load_clusters_from_db(self.db_path)\n'
        '\n'
        '            # Filter partitions by TOML config if available\n'
        '            if self._clusters and self.config:\n'
        '                slurm_config = self.config.get("collectors", {}).get("slurm", {})\n'
        '                configured_parts = slurm_config.get("partitions")\n'
        '                if configured_parts:\n'
        '                    for cid, cluster in self._clusters.items():\n'
        '                        if "partitions" in cluster:\n'
        '                            filtered = {p: ns for p, ns in cluster["partitions"].items()\n'
        '                                        if p in configured_parts}\n'
        '                            if filtered:\n'
        '                                cluster["partitions"] = filtered\n'
        '                                # Update node list to only configured partition nodes\n'
        '                                all_ns = set()\n'
        '                                for ns in filtered.values():\n'
        '                                    all_ns.update(ns)\n'
        '                                cluster["nodes"] = sorted(all_ns)\n'
        '                                cluster["description"] = f"{len(all_ns)}-node cluster"\n'
        '\n'
        '            if self._clusters:',

        "backend/filter_partitions_by_config")


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
