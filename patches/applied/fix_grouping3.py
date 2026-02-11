#!/usr/bin/env python3
import sys
path = sys.argv[1]
content = open(path).read()

# The old block with the exact trailing whitespace lines
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
                    }
                
                conn.close()
                return clusters'''

new = '''            if rows:
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
                    }
                
                conn.close()
                return clusters'''

if old in content:
    content = content.replace(old, new, 1)
    open(path, 'w').write(content)
    print("Fixed!")
else:
    # Try stripping the trailing whitespace from blank lines
    # and match that way
    import re
    # Normalize: replace lines that are only whitespace with empty
    norm_content = re.sub(r'\n[ \t]+\n', '\n\n', content)
    norm_old = re.sub(r'\n[ \t]+\n', '\n\n', old)
    
    if norm_old in norm_content:
        print("Found with normalized whitespace - applying fix...")
        # Do a line-by-line replacement
        lines = content.split('\n')
        new_lines = []
        i = 0
        while i < len(lines):
            if '# Group by partition' in lines[i] and i < 200:
                # Found the start, remove the "if rows:" we already added
                if new_lines and 'if rows:' in new_lines[-1]:
                    new_lines.pop()
                # Now add the replacement block
                new_lines.append('            if rows:')
                new_lines.append('                # Group by cluster, then by partition')
                new_lines.append('                cluster_data = defaultdict(lambda: defaultdict(list))')
                new_lines.append('                gpu_nodes = set()')
                new_lines.append('                ')
                new_lines.append('                for row in rows:')
                new_lines.append("                    node = row['node_name']")
                new_lines.append("                    cluster = row['cluster'] or 'default'")
                new_lines.append("                    partitions = row['partitions'] or 'default'")
                new_lines.append("                    primary_partition = partitions.split(',')[0]")
                new_lines.append('                    cluster_data[cluster][primary_partition].append(node)')
                new_lines.append('                    ')
                new_lines.append("                    if row['gres'] and 'gpu' in row['gres'].lower():")
                new_lines.append('                        gpu_nodes.add(node)')
                new_lines.append('                ')
                new_lines.append('                for cluster_name, part_map in cluster_data.items():')
                new_lines.append('                    all_nodes = []')
                new_lines.append('                    for p_nodes in part_map.values():')
                new_lines.append('                        all_nodes.extend(p_nodes)')
                new_lines.append("                    cluster_id = cluster_name.lower().replace(' ', '-')")
                new_lines.append('                    clusters[cluster_id] = {')
                new_lines.append('                        "name": cluster_name,')
                new_lines.append('                        "description": f"{len(all_nodes)}-node cluster",')
                new_lines.append('                        "nodes": sorted(all_nodes),')
                new_lines.append('                        "gpu_nodes": [n for n in all_nodes if n in gpu_nodes],')
                new_lines.append('                        "type": "gpu" if all_nodes and all(n in gpu_nodes for n in all_nodes) else "cpu",')
                new_lines.append('                        "partitions": {p: sorted(ns) for p, ns in part_map.items()},')
                new_lines.append('                    }')
                new_lines.append('                ')
                new_lines.append('                conn.close()')
                new_lines.append('                return clusters')
                # Skip the old block - find return clusters
                while i < len(lines) and 'return clusters' not in lines[i]:
                    i += 1
                i += 1  # skip the return clusters line too
                continue
            new_lines.append(lines[i])
            i += 1
        
        open(path, 'w').write('\n'.join(new_lines))
        print("Fixed with line-by-line replacement!")
    else:
        print("Still can't match - manual edit needed")
