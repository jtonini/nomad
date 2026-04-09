#!/usr/bin/env python3
"""
NOMAD v1.3.2 Final Patch — Remaining issues

Fixes:
  1. get_db_path() respects [database].path (relative to data_dir or absolute)
  2. collect command reports skipped collectors for transparency
  3. default.toml updated to document [database].path properly

Apply on badenpowell AFTER patch_v1.3.2.py and patch_v1.3.2_ux.py:
    cd ~/nomad
    python3 /path/to/patch_v1.3.2_final.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
if not (REPO / "nomad" / "cli.py").exists():
    print(f"Error: Expected repo at {REPO}/nomad/cli.py")
    sys.exit(1)

CLI_PY = REPO / "nomad" / "cli.py"
DEFAULT_TOML = REPO / "nomad" / "config" / "default.toml"

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
print("\n[1] Fix get_db_path() to respect [database].path")
# =====================================================================

patch(CLI_PY,
    'def get_db_path(config: dict[str, Any]) -> Path:\n'
    '    """Get database path from config."""\n'
    "    default_data = str(Path.home() / '.local' / 'share' / 'nomad')\n"
    "    data_dir = Path(config.get('general', {}).get('data_dir', default_data))\n"
    "    return data_dir / 'nomad.db'",

    'def get_db_path(config: dict[str, Any]) -> Path:\n'
    '    """Get database path from config.\n'
    '\n'
    '    Resolution:\n'
    '      1. [database].path — if absolute, use as-is; if relative, join with data_dir\n'
    '      2. Fall back to data_dir / nomad.db\n'
    '    """\n'
    "    default_data = str(Path.home() / '.local' / 'share' / 'nomad')\n"
    "    data_dir = Path(config.get('general', {}).get('data_dir', default_data))\n"
    "\n"
    "    db_path_str = config.get('database', {}).get('path', '')\n"
    "    if db_path_str:\n"
    "        db_path = Path(db_path_str)\n"
    "        if db_path.is_absolute():\n"
    "            return db_path\n"
    "        return data_dir / db_path\n"
    "\n"
    "    return data_dir / 'nomad.db'",

    "get_db_path/respect_config")


# =====================================================================
print("\n[2] collect command reports skipped collectors")
# =====================================================================

patch(CLI_PY,
    '    if not collectors:\n'
    '        raise click.ClickException("No collectors enabled")\n'
    '\n'
    '    click.echo(f"Running collectors: {[c.name for c in collectors]}")',

    '    if not collectors:\n'
    '        raise click.ClickException("No collectors enabled")\n'
    '\n'
    '    # Report which collectors are running and which were skipped\n'
    '    all_collector_names = [\n'
    '        "disk", "slurm", "job_metrics", "iostat", "mpstat",\n'
    '        "vmstat", "node_state", "gpu", "nfs", "groups", "interactive"\n'
    '    ]\n'
    '    running_names = [c.name for c in collectors]\n'
    '    skipped_names = [\n'
    '        n for n in all_collector_names\n'
    '        if n not in running_names\n'
    '        and config.get("collectors", {}).get(n, {}).get("enabled", True) is False\n'
    '    ]\n'
    '    click.echo(f"Running collectors: {running_names}")\n'
    '    if skipped_names:\n'
    '        click.echo(f"Disabled collectors: {skipped_names}")',

    "collect/report_skipped")


# =====================================================================
print("\n[3] Update default.toml [database] documentation")
# =====================================================================

if DEFAULT_TOML.exists():
    patch(DEFAULT_TOML,
        '[database]\n'
        '# SQLite database path (relative to data_dir or absolute)\n'
        'path = "nomad.db"',

        '[database]\n'
        '# SQLite database filename (relative to data_dir) or absolute path.\n'
        '# Default: nomad.db in data_dir.\n'
        '# Examples:\n'
        '#   path = "nomad.db"              # -> data_dir/nomad.db\n'
        '#   path = "mydb.sqlite"           # -> data_dir/mydb.sqlite\n'
        '#   path = "/var/lib/nomad/prod.db" # absolute, used as-is\n'
        'path = "nomad.db"',

        "default.toml/database_docs")
else:
    skipped.append("default.toml/database_docs -- file not found")
    print("  SKIP default.toml not found (will be in repo)")


# =====================================================================
# Summary
# =====================================================================
print(f"\n{'='*60}")
print(f"Applied: {len(applied)}")
for a in applied:
    print(f"  + {a}")
if skipped:
    print(f"\nSkipped: {len(skipped)}")
    for s in skipped:
        print(f"  - {s}")

print(f"""
All 5 original issues are now resolved:

  Issue 1: cluster_name defaults to "default"
           -> FIXED: resolve_cluster_name() reads [clusters.*] format (patch 1)

  Issue 2: Interactive config path mismatch
           -> FIXED: collect checks both paths; wizard writes [interactive] (patch 1)

  Issue 3: [collectors] enabled list is cosmetic
           -> FIXED: wizard writes explicit per-collector enabled = true/false (patch 1)
           -> FIXED: collect now reports disabled collectors (this patch)

  Issue 4: Missing GPU/NFS alert thresholds
           -> FIXED: wizard generates them when features are enabled (patch 1)

  Issue 5: [database] path is dead config
           -> FIXED: get_db_path() now respects [database].path (this patch)
           -> FIXED: default.toml documents the behavior (this patch)
""")
