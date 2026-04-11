#!/usr/bin/env python3
"""
NOMAD — Sync site metadata and dashboard partition filtering

1. Sync: SCP each site's nomad.toml, extract config metadata,
   store in sync_sites table in combined.db
2. Dashboard: read sync_sites to filter partitions per cluster

Apply on badenpowell:
    cd ~/nomad
    python3 patch_sync_metadata.py
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
print("\n[1] Sync: SCP each site's nomad.toml and store metadata")
# =====================================================================
# Insert after the SCP loop (after "if not pulled:"), before Phase 2.
# SCP each site's TOML, parse it, collect metadata.
# After merge completes, write sync_sites table.

patch(CLI_PY,
    "    # Phase 2: Merge into combined database\n"
    "    click.echo(click.style(\n"
    "        \"  Phase 2: Merging databases\", bold=True))\n"
    "    click.echo()",

    "    # Phase 1b: Pull site configs (for partition metadata)\n"
    "    site_configs = {}\n"
    "    for site in sites:\n"
    "        name = site.get('name', 'unknown')\n"
    "        host = site.get('host', 'localhost')\n"
    "        user = site.get('user', '')\n"
    "        ssh_key = site.get('ssh_key')\n"
    "        # Derive config path from user's home\n"
    "        if user == 'root':\n"
    "            remote_toml = '/root/.config/nomad/nomad.toml'\n"
    "        else:\n"
    "            remote_toml = f'/home/{user}/.config/nomad/nomad.toml'\n"
    "        local_toml = cache_dir / f'{name}.toml'\n"
    "        toml_cmd = ['scp', '-o', 'ConnectTimeout=5',\n"
    "                    '-o', 'BatchMode=yes']\n"
    "        if ssh_key:\n"
    "            toml_cmd += ['-i', ssh_key]\n"
    "        toml_cmd += [f'{user}@{host}:{remote_toml}',\n"
    "                     str(local_toml)]\n"
    "        try:\n"
    "            r = sp.run(toml_cmd, capture_output=True,\n"
    "                       text=True, timeout=15)\n"
    "            if r.returncode == 0 and local_toml.exists():\n"
    "                with open(local_toml) as f:\n"
    "                    cfg = toml_lib.load(f)\n"
    "                partitions = (cfg.get('collectors', {})\n"
    "                              .get('slurm', {})\n"
    "                              .get('partitions', []))\n"
    "                filesystems = (cfg.get('collectors', {})\n"
    "                               .get('disk', {})\n"
    "                               .get('filesystems', []))\n"
    "                cluster_type = 'hpc'\n"
    "                for cn, cv in cfg.get('clusters', {}).items():\n"
    "                    ct = cv.get('type', 'hpc')\n"
    "                    if ct in ('workstations', 'workstation'):\n"
    "                        cluster_type = 'workstation'\n"
    "                    break\n"
    "                site_configs[name] = {\n"
    "                    'partitions': ','.join(partitions)\n"
    "                        if partitions else '',\n"
    "                    'filesystems': ','.join(filesystems)\n"
    "                        if filesystems else '',\n"
    "                    'cluster_type': cluster_type,\n"
    "                }\n"
    "        except Exception:\n"
    "            pass\n"
    "\n"
    "    # Phase 2: Merge into combined database\n"
    "    click.echo(click.style(\n"
    "        \"  Phase 2: Merging databases\", bold=True))\n"
    "    click.echo()",

    "sync/pull_site_configs")


# Now insert writing sync_sites table after merge, before combined.close()

patch(CLI_PY,
    "    combined.close()\n"
    "\n"
    "    # Summary",

    "    # Write sync_sites metadata table\n"
    "    if site_configs:\n"
    "        try:\n"
    "            combined.execute(\n"
    "                'CREATE TABLE IF NOT EXISTS sync_sites ('\n"
    "                '  name TEXT PRIMARY KEY,'\n"
    "                '  partitions TEXT,'\n"
    "                '  filesystems TEXT,'\n"
    "                '  cluster_type TEXT,'\n"
    "                '  synced_at TEXT'\n"
    "                ')'\n"
    "            )\n"
    "            combined.execute('DELETE FROM sync_sites')\n"
    "            from datetime import datetime\n"
    "            now = datetime.now().isoformat()\n"
    "            for sname, smeta in site_configs.items():\n"
    "                combined.execute(\n"
    "                    'INSERT OR REPLACE INTO sync_sites '\n"
    "                    '(name, partitions, filesystems, '\n"
    "                    ' cluster_type, synced_at) '\n"
    "                    'VALUES (?, ?, ?, ?, ?)',\n"
    "                    (sname, smeta['partitions'],\n"
    "                     smeta['filesystems'],\n"
    "                     smeta['cluster_type'], now)\n"
    "                )\n"
    "            combined.commit()\n"
    "        except Exception:\n"
    "            pass\n"
    "\n"
    "    combined.close()\n"
    "\n"
    "    # Summary",

    "sync/write_sync_sites_table")


# =====================================================================
print("\n[2] Dashboard: filter partitions using sync_sites table")
# =====================================================================
# After loading clusters from node_state, check sync_sites for allowed
# partitions and remove any that aren't configured.

patch(SERVER_PY,
    '                # Also detect non-SLURM clusters from source_site',

    '                # Filter partitions using sync_sites metadata\n'
    '                try:\n'
    '                    sync_rows = conn.execute(\n'
    '                        "SELECT name, partitions, cluster_type"\n'
    '                        " FROM sync_sites"\n'
    '                    ).fetchall()\n'
    '                    sync_meta = {\n'
    '                        r[0]: {\n'
    '                            "partitions": [\n'
    '                                p.strip() for p in\n'
    '                                (r[1] or "").split(",")\n'
    '                                if p.strip()\n'
    '                            ],\n'
    '                            "type": r[2] or "hpc",\n'
    '                        }\n'
    '                        for r in sync_rows\n'
    '                    }\n'
    '                    # Filter each cluster\'s partitions\n'
    '                    for cid, cdata in list(\n'
    '                            clusters.items()):\n'
    '                        cname = cdata.get("name", cid)\n'
    '                        meta = (sync_meta.get(cname)\n'
    '                                or sync_meta.get(cid))\n'
    '                        if meta and meta["partitions"]:\n'
    '                            allowed = set(\n'
    '                                meta["partitions"])\n'
    '                            filtered = {\n'
    '                                p: ns for p, ns\n'
    '                                in cdata.get(\n'
    '                                    "partitions",\n'
    '                                    {}).items()\n'
    '                                if p in allowed\n'
    '                            }\n'
    '                            cdata["partitions"] =\\\n'
    '                                filtered\n'
    '                            # Update node list to\n'
    '                            # only include filtered\n'
    '                            all_ns = set()\n'
    '                            for pns in filtered.values():\n'
    '                                all_ns.update(pns)\n'
    '                            cdata["nodes"] = sorted(\n'
    '                                all_ns)\n'
    '                        if meta:\n'
    '                            cdata["type"] = meta[\n'
    '                                "type"]\n'
    '                except Exception:\n'
    '                    pass  # No sync_sites table\n'
    '\n'
    '                # Also detect non-SLURM clusters from source_site',

    "dashboard/filter_partitions_from_sync_sites")


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
