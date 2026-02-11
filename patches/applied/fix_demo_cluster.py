#!/usr/bin/env python3
"""Fix demo.py to include cluster column in node_state table."""
import sys
path = sys.argv[1]
content = open(path).read()
changes = 0

# 1. CREATE TABLE - add cluster column
old_create = (
    '            memory_free_mb INTEGER, cpu_alloc_percent REAL, memory_alloc_percent REAL,\n'
    '            partitions TEXT, reason TEXT, features TEXT, gres TEXT, is_healthy INTEGER)""")')
new_create = (
    '            memory_free_mb INTEGER, cpu_alloc_percent REAL, memory_alloc_percent REAL,\n'
    '            cluster TEXT DEFAULT \'demo\', partitions TEXT, reason TEXT, features TEXT, gres TEXT, is_healthy INTEGER)""")')
if old_create in content:
    content = content.replace(old_create, new_create, 1)
    changes += 1
    print("  + CREATE TABLE: added cluster column")

# 2. INSERT columns - add cluster
old_insert = (
    '            c.execute("""INSERT INTO node_state\n'
    '                (timestamp, node_name, state, cpus_total, cpus_alloc, cpu_load,\n'
    '                 memory_total_mb, memory_alloc_mb, memory_free_mb,\n'
    '                 cpu_alloc_percent, memory_alloc_percent, partitions, gres, is_healthy)')
new_insert = (
    '            c.execute("""INSERT INTO node_state\n'
    '                (timestamp, node_name, state, cpus_total, cpus_alloc, cpu_load,\n'
    '                 memory_total_mb, memory_alloc_mb, memory_free_mb,\n'
    '                 cpu_alloc_percent, memory_alloc_percent, cluster, partitions, gres, is_healthy)')
if old_insert in content:
    content = content.replace(old_insert, new_insert, 1)
    changes += 1
    print("  + INSERT columns: added cluster")

# 3. VALUES - add 'demo' and extra placeholder
old_values = 'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",'
new_values = 'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",'
if old_values in content:
    content = content.replace(old_values, new_values, 1)
    changes += 1
    print("  + VALUES: added placeholder")

# 4. Tuple - add 'demo' before partition
old_tuple = "                 random.uniform(10, 80), random.uniform(20, 70), node[\"partition\"],"
new_tuple = "                 random.uniform(10, 80), random.uniform(20, 70), \"demo\", node[\"partition\"],"
if old_tuple in content:
    content = content.replace(old_tuple, new_tuple, 1)
    changes += 1
    print("  + Tuple: added 'demo' cluster value")

if changes > 0:
    open(path, 'w').write(content)
    print(f"\nFixed demo.py ({changes} edits)")
else:
    print("Already patched or could not find markers")
