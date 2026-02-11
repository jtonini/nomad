#!/usr/bin/env python3
"""
Fix the nodes table loading path to build partition→nodes mapping.
"""
import sys

path = sys.argv[1]
content = open(path).read()

old = '''                for cluster_name, nodes in cluster_nodes.items():
                    cluster_id = cluster_name.lower().replace(" ", "-")
                    part_list = sorted(p for p in cluster_partitions[cluster_name] if p)
                    clusters[cluster_id] = {
                        "name": cluster_name,
                        "description": f"{len(nodes)}-node cluster (" + ", ".join(part_list) + ")",
                        "description": f"{len(nodes)}-node partition",
                        "nodes": sorted(nodes),
                        "gpu_nodes": [n for n in nodes if n in gpu_nodes],
                        "type": "gpu" if any(n in gpu_nodes for n in nodes) else "cpu"
                    }'''

new = '''                # Build partition -> nodes mapping
                partition_node_map = defaultdict(lambda: defaultdict(list))
                for row in rows:
                    node = row["hostname"]
                    cluster_name = row["cluster"] or "default"
                    partitions = row["partition"] or "default"
                    primary_part = partitions.split(",")[0]
                    partition_node_map[cluster_name][primary_part].append(node)
                
                for cluster_name, nodes in cluster_nodes.items():
                    cluster_id = cluster_name.lower().replace(" ", "-")
                    part_list = sorted(p for p in cluster_partitions[cluster_name] if p)
                    part_map = {p: sorted(ns) for p, ns in partition_node_map[cluster_name].items()}
                    clusters[cluster_id] = {
                        "name": cluster_name,
                        "description": f"{len(nodes)}-node cluster",
                        "nodes": sorted(nodes),
                        "gpu_nodes": [n for n in nodes if n in gpu_nodes],
                        "type": "gpu" if any(n in gpu_nodes for n in nodes) else "cpu",
                        "partitions": part_map,
                    }'''

if old in content:
    content = content.replace(old, new, 1)
    open(path, 'w').write(content)
    print("Fixed nodes table path - added partitions mapping")
else:
    print("Could not find block")
    # Debug
    if "description" in content and "node partition" in content:
        print("Found 'node partition' - checking context...")
