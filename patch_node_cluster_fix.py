#!/usr/bin/env python3
"""
Cleanup patch for remaining node_cluster issues.
Fixes:
  1. node_state.py - index creation
  2. node_state.py - INSERT column list  
  3. server.py - cluster→partition grouping
"""
import sys
import shutil
from pathlib import Path


def patch_node_state_index(nomade_dir):
    """Add cluster index to node_state.py."""
    path = nomade_dir / 'collectors' / 'node_state.py'
    content = path.read_text()
    
    if 'idx_node_state_cluster' in content:
        print("  = node_state.py: index already exists")
        return True
    
    # Find the second index block and add cluster index after it
    old = '''            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_node_state_name
                ON node_state(node_name, timestamp)
            """)'''
    
    new = '''            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_node_state_name
                ON node_state(node_name, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_node_state_cluster
                ON node_state(cluster, timestamp)
            """)'''
    
    if old in content:
        content = content.replace(old, new, 1)
        path.write_text(content)
        print("  + node_state.py: added cluster index")
        return True
    else:
        print("  ! node_state.py: could not find index block")
        return False


def patch_node_state_insert(nomade_dir):
    """Fix INSERT statement in node_state.py."""
    path = nomade_dir / 'collectors' / 'node_state.py'
    content = path.read_text()
    
    if 'node_name, cluster, state' in content:
        print("  = node_state.py: INSERT already has cluster")
        return True
    
    # The INSERT column list
    old = '''                        INSERT INTO node_state
                        (timestamp, node_name, state, cpus_total, cpus_alloc, cpu_load,
                         memory_total_mb, memory_alloc_mb, memory_free_mb,
                         cpu_alloc_percent, memory_alloc_percent,'''
    
    new = '''                        INSERT INTO node_state
                        (timestamp, node_name, cluster, state, cpus_total, cpus_alloc, cpu_load,
                         memory_total_mb, memory_alloc_mb, memory_free_mb,
                         cpu_alloc_percent, memory_alloc_percent,'''
    
    if old in content:
        content = content.replace(old, new, 1)
        path.write_text(content)
        print("  + node_state.py: added cluster to INSERT columns")
        return True
    else:
        print("  ! node_state.py: could not find INSERT block")
        # Show what we have
        if 'INSERT INTO node_state' in content:
            idx = content.index('INSERT INTO node_state')
            print(f"    Found INSERT at char {idx}, snippet:")
            print(content[idx:idx+300])
        return False


def patch_server_grouping(nomade_dir):
    """Replace partition-only grouping with cluster→partition grouping."""
    path = nomade_dir / 'viz' / 'server.py'
    content = path.read_text()
    
    if 'Group by cluster, then by partition' in content:
        print("  = server.py: grouping already patched")
        return True
    
    # The exact block from lines 157-177
    old = '''            if rows:
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
                    }'''
    
    new = '''            if rows:
                # Group by cluster, then by partition
                cluster_data = defaultdict(lambda: defaultdict(list))
                gpu_nodes = set()
                for row in rows:
                    node = row['node_name']
                    cluster = row['cluster'] if 'cluster' in row.keys() else 'default'
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
                    partitions_info = {p: sorted(ns) for p, ns in part_map.items()}
                    clusters[cluster_id] = {
                        "name": cluster_name,
                        "description": f"{len(all_nodes)}-node cluster",
                        "nodes": sorted(all_nodes),
                        "gpu_nodes": [n for n in all_nodes if n in gpu_nodes],
                        "type": "gpu" if all_nodes and all(n in gpu_nodes for n in all_nodes) else "cpu",
                        "partitions": partitions_info,
                    }'''
    
    if old in content:
        content = content.replace(old, new, 1)
        backup = path.with_suffix('.py.bak3')
        shutil.copy(path, backup)
        path.write_text(content)
        print("  + server.py: cluster→partition grouping")
        return True
    else:
        print("  ! server.py: could not find grouping block")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 patch_node_cluster_fix.py /path/to/nomade/")
        sys.exit(1)
    
    nomade_dir = Path(sys.argv[1])
    if (nomade_dir / 'collectors').exists():
        pass
    elif (nomade_dir / 'nomade' / 'collectors').exists():
        nomade_dir = nomade_dir / 'nomade'
    else:
        print(f"ERROR: Could not find collectors/ in {nomade_dir}")
        sys.exit(1)
    
    print()
    print("Node Cluster Cleanup Patch")
    print("=" * 30)
    
    ok1 = patch_node_state_index(nomade_dir)
    ok2 = patch_node_state_insert(nomade_dir)
    ok3 = patch_server_grouping(nomade_dir)
    
    print()
    if ok1 and ok2 and ok3:
        print("Done! Test with: nomade dashboard")
    else:
        print("Some patches need manual attention.")


if __name__ == '__main__':
    main()
