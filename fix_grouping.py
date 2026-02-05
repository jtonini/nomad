#!/usr/bin/env python3
import sys
path = sys.argv[1]
content = open(path).read()

old = """            if rows:
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

new = """            if rows:
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
                    clusters[cluster_id] = {
                        "name": cluster_name,
                        "description": f"{len(all_nodes)}-node cluster",
                        "nodes": sorted(all_nodes),
                        "gpu_nodes": [n for n in all_nodes if n in gpu_nodes],
                        "type": "gpu" if all_nodes and all(n in gpu_nodes for n in all_nodes) else "cpu",
                        "partitions": {p: sorted(ns) for p, ns in part_map.items()},
                    }"""

if old in content:
    content = content.replace(old, new, 1)
    open(path, 'w').write(content)
    print("Fixed server.py grouping")
else:
    print("Could not find block - checking...")
    if "# Group by partition" in content:
        print("  Found '# Group by partition' - whitespace mismatch likely")
    if "# Group by cluster" in content:
        print("  Already patched!")
