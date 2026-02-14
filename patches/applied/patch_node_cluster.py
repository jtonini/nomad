#!/usr/bin/env python3
"""
NOMADE Option B: Add cluster column to node_state
===================================================
Adds cluster identity to every node_state record so the dashboard
can group partitions within clusters (matching nomad demo behavior).

Changes:
    1. nomad/collectors/node_state.py - add cluster to schema/collect/store
    2. nomad/cli.py - pass cluster_name to NodeStateCollector
    3. nomad/viz/server.py - update cluster loading to group by cluster→partition
    4. Migration: ALTER TABLE for existing databases

Usage:
    python3 patch_node_cluster.py /path/to/nomad/

After patching:
    # Migrate existing database
    python3 patch_node_cluster.py --migrate /path/to/nomad.db [cluster_name]

    # Or add cluster_name to your nomad.toml:
    #   cluster_name = "spydur"
"""

import sys
import shutil
from pathlib import Path


# =====================================================================
# PATCH: node_state.py
# =====================================================================

def patch_node_state(nomad_dir):
    """Add cluster column to NodeStateCollector."""
    path = nomad_dir / 'collectors' / 'node_state.py'
    if not path.exists():
        print(f"  ! {path} not found")
        return False

    content = path.read_text()
    backup = path.with_suffix('.py.bak')
    shutil.copy(path, backup)
    changes = 0

    # 1. Add cluster_name to __init__
    old_init = "        self.nodes = config.get('nodes', None)  # None = all nodes"
    new_init = (
        "        self.nodes = config.get('nodes', None)  # None = all nodes\n"
        "        self.cluster_name = config.get('cluster_name', 'default')")
    if 'self.cluster_name' not in content:
        if old_init in content:
            content = content.replace(old_init, new_init, 1)
            changes += 1
            print("    + __init__: cluster_name")
        else:
            print("    ! Could not find __init__ marker")

    # 2. Add cluster to each record in collect()
    old_record = "                    'type': 'node_state',"
    new_record = (
        "                    'type': 'node_state',\n"
        "                    'cluster': self.cluster_name,")
    if "'cluster': self.cluster_name" not in content:
        if old_record in content:
            content = content.replace(old_record, new_record, 1)
            changes += 1
            print("    + collect(): cluster field in records")
        else:
            print("    ! Could not find record marker")

    # 3. Add cluster to CREATE TABLE
    old_schema = (
        "                    partitions TEXT,\n"
        "                    reason TEXT,")
    new_schema = (
        "                    cluster TEXT DEFAULT 'default',\n"
        "                    partitions TEXT,\n"
        "                    reason TEXT,")
    if "cluster TEXT" not in content:
        if old_schema in content:
            content = content.replace(old_schema, new_schema, 1)
            changes += 1
            print("    + CREATE TABLE: cluster column")
        else:
            print("    ! Could not find schema marker")

    # 4. Add cluster index
    old_idx = (
        "                CREATE INDEX IF NOT EXISTS idx_node_state_name\n"
        "                ON node_state(node_name, timestamp)")
    new_idx = (
        "                CREATE INDEX IF NOT EXISTS idx_node_state_name\n"
        "                ON node_state(node_name, timestamp)\n"
        "            \"\"\")\n"
        "            conn.execute(\"\"\"\n"
        "                CREATE INDEX IF NOT EXISTS idx_node_state_cluster\n"
        "                ON node_state(cluster, timestamp)")
    if "idx_node_state_cluster" not in content:
        if old_idx in content:
            content = content.replace(old_idx, new_idx, 1)
            changes += 1
            print("    + INDEX: cluster")
        else:
            print("    ! Could not find index marker")

    # 5. Add cluster to INSERT column list
    old_insert_cols = (
        "                        INSERT INTO node_state\n"
        "                        (timestamp, node_name, state, cpus_total, cpus_alloc, cpu_load,\n"
        "                         memory_total_mb, memory_alloc_mb, memory_free_mb,\n"
        "                         cpu_alloc_percent, memory_alloc_percent,\n"
        "                         partitions, reason, features, gres, is_healthy)")
    new_insert_cols = (
        "                        INSERT INTO node_state\n"
        "                        (timestamp, node_name, cluster, state, cpus_total, cpus_alloc, cpu_load,\n"
        "                         memory_total_mb, memory_alloc_mb, memory_free_mb,\n"
        "                         cpu_alloc_percent, memory_alloc_percent,\n"
        "                         partitions, reason, features, gres, is_healthy)")
    if "node_name, cluster, state" not in content:
        if old_insert_cols in content:
            content = content.replace(old_insert_cols, new_insert_cols, 1)
            changes += 1
            print("    + INSERT: cluster column")
        else:
            print("    ! Could not find INSERT cols marker")

    # 6. Add cluster to VALUES
    old_values = (
        "                            record['timestamp'],\n"
        "                            record['node_name'],\n"
        "                            record['state'],")
    new_values = (
        "                            record['timestamp'],\n"
        "                            record['node_name'],\n"
        "                            record.get('cluster', 'default'),\n"
        "                            record['state'],")

    # Also update the VALUES placeholder count (add one ?)
    old_placeholders = "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    new_placeholders = "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"

    if "record.get('cluster', 'default')" not in content:
        if old_values in content:
            content = content.replace(old_values, new_values, 1)
            changes += 1
            print("    + VALUES: cluster field")
        else:
            print("    ! Could not find VALUES marker")

    if old_placeholders in content and new_placeholders not in content:
        content = content.replace(old_placeholders, new_placeholders, 1)
        changes += 1
        print("    + VALUES: placeholder count")

    if changes > 0:
        path.write_text(content)
        print(f"  + node_state.py ({changes} edits)")
    else:
        print("  = node_state.py (already patched)")
    return True


# =====================================================================
# PATCH: cli.py
# =====================================================================

def patch_cli(nomad_dir):
    """Pass cluster_name from config to NodeStateCollector."""
    path = nomad_dir / 'cli.py'
    if not path.exists():
        print(f"  ! {path} not found")
        return False

    content = path.read_text()
    changes = 0

    # Inject cluster_name into node_state config
    old_wiring = (
        "    node_state_config = config.get('collectors', {}).get('node_state', {})\n"
        "    if not collector or 'node_state' in collector:\n"
        "        if node_state_config.get('enabled', True):\n"
        "            collectors.append(NodeStateCollector(node_state_config, db_path))")
    new_wiring = (
        "    node_state_config = config.get('collectors', {}).get('node_state', {})\n"
        "    if not collector or 'node_state' in collector:\n"
        "        if node_state_config.get('enabled', True):\n"
        "            if 'cluster_name' not in node_state_config:\n"
        "                node_state_config['cluster_name'] = config.get('cluster_name', 'default')\n"
        "            collectors.append(NodeStateCollector(node_state_config, db_path))")

    if "'cluster_name' not in node_state_config" not in content:
        if old_wiring in content:
            content = content.replace(old_wiring, new_wiring, 1)
            changes += 1
            print("    + Inject cluster_name into node_state config")
        else:
            print("    ! Could not find node_state wiring block")
            print("      Will try line-based approach")
            # Try just inserting before the append line
            marker = "            collectors.append(NodeStateCollector(node_state_config, db_path))"
            inject = (
                "            if 'cluster_name' not in node_state_config:\n"
                "                node_state_config['cluster_name'] = config.get('cluster_name', 'default')\n")
            if marker in content:
                content = content.replace(
                    marker,
                    inject + marker, 1)
                changes += 1
                print("    + Inject cluster_name (line-based)")

    if changes > 0:
        backup = path.with_suffix('.py.bak2')
        shutil.copy(path, backup)
        path.write_text(content)
        print(f"  + cli.py ({changes} edits)")
    else:
        print("  = cli.py (already patched)")
    return True


# =====================================================================
# PATCH: server.py - cluster loading from node_state
# =====================================================================

def patch_server(nomad_dir):
    """Update server.py to group node_state data by cluster→partition."""
    path = nomad_dir / 'viz' / 'server.py'
    if not path.exists():
        print(f"  ! {path} not found")
        return False

    content = path.read_text()
    backup = path.with_suffix('.py.bak2')
    shutil.copy(path, backup)
    changes = 0

    # 1. Update the SQL query to include cluster column
    old_query = (
        "                SELECT DISTINCT node_name, partitions, gres\n"
        "                FROM node_state\n"
        "                WHERE timestamp = (SELECT MAX(timestamp) FROM node_state)")
    new_query = (
        "                SELECT DISTINCT node_name, partitions, gres,\n"
        "                       COALESCE(cluster, 'default') as cluster\n"
        "                FROM node_state\n"
        "                WHERE timestamp = (SELECT MAX(timestamp) FROM node_state)")

    if "COALESCE(cluster" not in content:
        if old_query in content:
            content = content.replace(old_query, new_query, 1)
            changes += 1
            print("    + SQL query: added cluster column")
        else:
            print("    ! Could not find node_state query")

    # 2. Replace the partition-only grouping with cluster→partition grouping
    old_grouping = """\
            if rows:
                # Group by partition
                partition_nodes = defaultdict(list)
                gpu_nodes = set()
                for row in rows:
                    node = row['node_name']
                    partitions = row['partitions'] or 'default'
                    # Use first partition as primary
                    primary_partition = partitions.split(',')[0]
                    partition_nodes[primary_partition].append(node)
                    if row['gres'] and 'gpu' in row['gres'].lower():
                        gpu_nodes.add(node)
                for partition, nodes in partition_nodes.items():
                    cluster_id = partition.lower().replace(' ', '-')
                    clusters[cluster_id] = {
                        "name": partition,
                        "description": f"{len(nodes)}-node partition",
                        "nodes": sorted(nodes),
                        "gpu_nodes": [n for n in nodes if n in gpu_nodes],
                        "type": "gpu" if any(n in gpu_nodes for n in nodes) else "cpu"
                    }"""

    new_grouping = """\
            if rows:
                # Group by cluster, then by partition
                cluster_data = defaultdict(lambda: defaultdict(list))
                gpu_nodes = set()
                for row in rows:
                    node = row['node_name']
                    cluster = row['cluster'] or 'default'
                    partitions = row['partitions'] or 'default'
                    primary_partition = partitions.split(',')[0]
                    cluster_data[cluster][primary_partition].append(node)
                    if row['gres'] and 'gpu' in row['gres'].lower():
                        gpu_nodes.add(node)
                for cluster_name, part_map in cluster_data.items():
                    all_nodes = []
                    for p_nodes in part_map.values():
                        all_nodes.extend(p_nodes)
                    cluster_id = cluster_name.lower().replace(' ', '-')
                    part_desc = ", ".join(
                        f"{p}: {len(ns)} nodes"
                        for p, ns in sorted(part_map.items()))
                    clusters[cluster_id] = {
                        "name": cluster_name,
                        "description": f"{len(all_nodes)}-node cluster ({part_desc})",
                        "nodes": sorted(all_nodes),
                        "gpu_nodes": [n for n in all_nodes if n in gpu_nodes],
                        "type": "gpu" if all(n in gpu_nodes for n in all_nodes) else "cpu",
                        "partitions": {p: sorted(ns) for p, ns in part_map.items()},
                    }"""

    if "Group by cluster, then by partition" not in content:
        if old_grouping in content:
            content = content.replace(old_grouping, new_grouping, 1)
            changes += 1
            print("    + Cluster→partition grouping")
        else:
            print("    ! Could not find grouping block")
            print("      This may need manual patching")

    # 3. Update node loading from node_state to include cluster field
    #    Need to find where nodes dict is built from node_state data
    #    and ensure each node has 'cluster' set
    old_node_select = (
        "                SELECT DISTINCT node_name AS hostname,\n"
        "                    state AS status,\n"
        "                    cpus_total AS cpu_count,\n"
        "                    CASE WHEN gres LIKE '%gpu%' THEN 1 ELSE 0 END AS gpu_count,\n"
        "                    memory_total_mb AS memory_mb,\n"
        "                    partitions, reason, gres, is_healthy")
    new_node_select = (
        "                SELECT DISTINCT node_name AS hostname,\n"
        "                    COALESCE(cluster, 'default') AS cluster,\n"
        "                    state AS status,\n"
        "                    cpus_total AS cpu_count,\n"
        "                    CASE WHEN gres LIKE '%gpu%' THEN 1 ELSE 0 END AS gpu_count,\n"
        "                    memory_total_mb AS memory_mb,\n"
        "                    partitions, reason, gres, is_healthy")

    if old_node_select in content and "COALESCE(cluster, 'default') AS cluster" not in content.split(old_node_select)[0]:
        content = content.replace(old_node_select, new_node_select, 1)
        changes += 1
        print("    + Node SELECT: added cluster column")

    if changes > 0:
        path.write_text(content)
        print(f"  + server.py ({changes} edits)")
    else:
        print("  = server.py (already patched or needs manual edits)")
    return True


# =====================================================================
# MIGRATION: existing databases
# =====================================================================

def migrate_db(db_path, cluster_name='default'):
    """Add cluster column to existing node_state table."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    # Check if column exists
    cols = [r[1] for r in c.execute("PRAGMA table_info(node_state)").fetchall()]
    if 'cluster' in cols:
        print(f"  = node_state.cluster already exists")
        conn.close()
        return True

    print(f"  Adding cluster column to node_state...")
    c.execute(f"ALTER TABLE node_state ADD COLUMN cluster TEXT DEFAULT '{cluster_name}'")
    c.execute("CREATE INDEX IF NOT EXISTS idx_node_state_cluster ON node_state(cluster, timestamp)")

    # Count updated rows
    count = c.execute("SELECT COUNT(*) FROM node_state").fetchone()[0]
    conn.commit()
    conn.close()
    print(f"  + Migrated {count} rows (cluster='{cluster_name}')")
    return True


# =====================================================================
# MAIN
# =====================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 patch_node_cluster.py /path/to/nomad/")
        print("  python3 patch_node_cluster.py --migrate /path/to/db [cluster_name]")
        sys.exit(1)

    # Migration mode
    if sys.argv[1] == '--migrate':
        if len(sys.argv) < 3:
            print("Usage: python3 patch_node_cluster.py --migrate /path/to/nomad.db [cluster_name]")
            sys.exit(1)
        db_path = Path(sys.argv[2])
        cluster_name = sys.argv[3] if len(sys.argv) > 3 else 'default'
        if not db_path.exists():
            print(f"ERROR: {db_path} not found")
            sys.exit(1)
        print(f"\nMigrating: {db_path}")
        print(f"Cluster name: {cluster_name}")
        migrate_db(db_path, cluster_name)
        print("\nDone!")
        print("Add to your nomad.toml:")
        print(f'  cluster_name = "{cluster_name}"')
        return

    # Patch mode
    nomad_dir = Path(sys.argv[1])
    if (nomad_dir / 'collectors').exists():
        pass
    elif (nomad_dir / 'nomad' / 'collectors').exists():
        nomad_dir = nomad_dir / 'nomad'
    else:
        print(f"ERROR: Could not find collectors/ in {nomad_dir}")
        sys.exit(1)

    print()
    print("NOMADE Node Cluster Patch (Option B)")
    print("=" * 44)
    print(f"Target: {nomad_dir}")
    print()

    ok1 = patch_node_state(nomad_dir)
    ok2 = patch_cli(nomad_dir)
    ok3 = patch_server(nomad_dir)

    print()
    if ok1 and ok2 and ok3:
        print("Code patched! Next steps:")
        print()
        print("1. Add cluster_name to nomad.toml:")
        print('     cluster_name = "spydur"')
        print()
        print("2. Migrate existing databases:")
        print("     python3 patch_node_cluster.py --migrate ~/.local/share/nomad/nomad.db spydur")
        print("     python3 patch_node_cluster.py --migrate vm-simulation/nomad.db demo")
        print()
        print("3. Test:")
        print("     nomad collect -C node_state --once")
        print("     nomad dashboard")
    else:
        print("Some patches may need manual attention.")


if __name__ == '__main__':
    main()
