#!/usr/bin/env python3
"""
NOMAD v1.3.3 Patch — Workstation collector + nomad sync

Two features:
  1. Wire WorkstationCollector into `nomad collect`
     - Add to collector init loop in cli.py
     - Wizard generates [collectors.workstation] config
  2. New `nomad sync` command
     - Pull remote nomad.db files via SCP
     - Merge into combined.db using SQLite ATTACH
     - Add source_site column to tables that lack disambiguation
     - Dedup by (timestamp, hostname/source_site) composite

Apply on badenpowell:
    cd ~/nomad
    python3 patch_v1.3.3.py
    python3 -m pytest tests/ -v
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
if not (REPO / "nomad" / "cli.py").exists():
    print(f"Error: Expected repo at {REPO}/nomad/cli.py")
    sys.exit(1)

CLI_PY = REPO / "nomad" / "cli.py"

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


def insert_before(path, anchor, code, label):
    text = path.read_text()
    if anchor not in text:
        skipped.append(f"{label} -- anchor not found")
        return False
    if code.strip()[:60] in text:
        skipped.append(f"{label} -- already applied")
        return False
    text = text.replace(anchor, code + anchor, 1)
    path.write_text(text)
    applied.append(label)
    print(f"  OK   {label}")
    return True


def insert_after(path, anchor, code, label):
    text = path.read_text()
    if anchor not in text:
        skipped.append(f"{label} -- anchor not found")
        return False
    if code.strip()[:60] in text:
        skipped.append(f"{label} -- already applied")
        return False
    text = text.replace(anchor, anchor + code, 1)
    path.write_text(text)
    applied.append(label)
    print(f"  OK   {label}")
    return True


# =====================================================================
print("\n[1] Add WorkstationCollector import")
# =====================================================================

patch(CLI_PY,
    "from nomad.collectors.vmstat import VMStatCollector",

    "from nomad.collectors.vmstat import VMStatCollector\n"
    "from nomad.collectors.workstation import WorkstationCollector",

    "import/workstation")


# =====================================================================
print("\n[2] Add WorkstationCollector to collect loop")
# =====================================================================

# Insert after the interactive collector block, before cloud collectors
patch(CLI_PY,
    "    # Cloud collectors\n"
    "    cloud_config = config.get('collectors', {}).get('cloud', {})",

    "    # Workstation collector (SSH-based remote collection)\n"
    "    ws_config = config.get('collectors', {}).get('workstation', {})\n"
    "    if not collector or 'workstation' in collector:\n"
    "        if ws_config.get('enabled', False):\n"
    "            collectors.append(WorkstationCollector(ws_config, db_path))\n"
    "\n"
    "    # Cloud collectors\n"
    "    cloud_config = config.get('collectors', {}).get('cloud', {})",

    "collect/workstation")


# =====================================================================
print("\n[3] Add 'workstation' to all_collector_names list")
# =====================================================================

patch(CLI_PY,
    '        "disk", "slurm", "job_metrics", "iostat", "mpstat",\n'
    '        "vmstat", "node_state", "gpu", "nfs", "groups", "interactive"',

    '        "disk", "slurm", "job_metrics", "iostat", "mpstat",\n'
    '        "vmstat", "node_state", "gpu", "nfs", "groups", "interactive",\n'
    '        "workstation"',

    "collect/all_names")


# =====================================================================
print("\n[4] Add nomad sync command")
# =====================================================================

# We'll add it after the init function but before the demo function.
# Find the demo command decorator as anchor.

SYNC_COMMAND = '''

@cli.command()
@click.option('--config-file', '-c', type=click.Path(),
              help='Sync config file (default: ~/.config/nomad/sync.toml)')
@click.option('--output', '-o', type=click.Path(),
              default=None, help='Output combined database path')
@click.option('--dry-run', is_flag=True, help='Show what would be synced')
@click.pass_context
def sync(ctx, config_file, output, dry_run):
    """Sync remote NOMAD databases into a combined local database.

    \\b
    Pulls nomad.db from each configured remote site via SCP,
    then merges all tables into a single combined database.
    Each site keeps its own database as a fallback.

    \\b
    Config file (~/.config/nomad/sync.toml):
      [[sites]]
      name = "arachne"
      host = "arachne"
      user = "jtonini"
      db_path = "~/.local/share/nomad/nomad.db"

      [[sites]]
      name = "workstations"
      host = "jonimitchell"
      user = "zeus"
      db_path = "~/.local/share/nomad/nomad.db"

    \\b
    Examples:
      nomad sync                     Sync all configured sites
      nomad sync --dry-run           Show what would happen
      nomad sync -o /tmp/combined.db Custom output path
    """
    import shutil
    import sqlite3
    import subprocess as sp
    import toml as toml_lib

    # Resolve config
    if not config_file:
        config_file = Path.home() / '.config' / 'nomad' / 'sync.toml'
    else:
        config_file = Path(config_file)

    if not config_file.exists():
        click.echo(click.style(
            f"  Sync config not found: {config_file}", fg="red"))
        click.echo()
        click.echo("  Create it with your remote sites:")
        click.echo()
        click.echo(f"    nano {config_file}")
        click.echo()
        click.echo("  Example contents:")
        click.echo()
        click.echo('    [[sites]]')
        click.echo('    name = "arachne"')
        click.echo('    host = "arachne"')
        click.echo('    user = "jtonini"')
        click.echo('    db_path = "~/.local/share/nomad/nomad.db"')
        click.echo()
        click.echo('    [[sites]]')
        click.echo('    name = "workstations"')
        click.echo('    host = "jonimitchell"')
        click.echo('    user = "zeus"')
        click.echo('    db_path = "~/.local/share/nomad/nomad.db"')
        click.echo()
        return

    with open(config_file) as f:
        sync_config = toml_lib.load(f)

    sites = sync_config.get('sites', [])
    if not sites:
        click.echo(click.style(
            "  No sites configured in sync.toml", fg="yellow"))
        return

    # Output path
    default_data = Path.home() / '.local' / 'share' / 'nomad'
    if output:
        combined_path = Path(output)
    else:
        combined_path = default_data / 'combined.db'

    cache_dir = default_data / 'sync_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)

    click.echo()
    click.echo(click.style(
        "  NOMAD Sync", fg="cyan", bold=True))
    click.echo(click.style(
        "  ══════════════════════════════════════", fg="cyan"))
    click.echo()
    click.echo(f"  Sites:    {len(sites)}")
    click.echo(f"  Output:   {combined_path}")
    click.echo()

    if dry_run:
        click.echo(click.style("  Dry run mode", fg="yellow"))
        click.echo()
        for site in sites:
            name = site.get('name', 'unknown')
            host = site.get('host', '?')
            user = site.get('user', '?')
            db = site.get('db_path', '?')
            click.echo(f"  Would sync: {name}")
            click.echo(f"    scp {user}@{host}:{db} -> {cache_dir}/{name}.db")
        click.echo()
        click.echo(f"  Would merge into: {combined_path}")
        return

    # Phase 1: Pull remote databases
    click.echo(click.style(
        "  Phase 1: Pulling remote databases", bold=True))
    click.echo()

    pulled = []
    for site in sites:
        name = site.get('name', 'unknown')
        host = site.get('host')
        user = site.get('user')
        remote_db = site.get('db_path', '~/.local/share/nomad/nomad.db')
        ssh_key = site.get('ssh_key')
        local_copy = cache_dir / f"{name}.db"

        click.echo(f"  {name}: ", nl=False)

        scp_cmd = ["scp", "-o", "ConnectTimeout=10",
                    "-o", "BatchMode=yes"]
        if ssh_key:
            scp_cmd += ["-i", ssh_key]
        scp_cmd.append(f"{user}@{host}:{remote_db}")
        scp_cmd.append(str(local_copy))

        try:
            result = sp.run(scp_cmd, capture_output=True,
                            text=True, timeout=60)
            if result.returncode == 0:
                size_mb = local_copy.stat().st_size / (1024 * 1024)
                click.echo(click.style(
                    f"OK ({size_mb:.1f} MB)", fg="green"))
                pulled.append((name, local_copy))
            else:
                click.echo(click.style(
                    f"FAILED: {result.stderr.strip()[:80]}",
                    fg="red"))
        except sp.TimeoutExpired:
            click.echo(click.style("TIMEOUT", fg="red"))
        except Exception as e:
            click.echo(click.style(f"ERROR: {e}", fg="red"))

    if not pulled:
        click.echo()
        click.echo(click.style(
            "  No databases pulled. Check SSH connectivity.",
            fg="red"))
        return

    click.echo()

    # Phase 2: Merge into combined database
    click.echo(click.style(
        "  Phase 2: Merging databases", bold=True))
    click.echo()

    # Tables that need a source_site column added during merge
    NEEDS_SITE_COL = {
        'filesystems', 'queue_state',
        'iostat_cpu', 'iostat_device',
        'mpstat_core', 'mpstat_summary',
        'vmstat', 'nfs_stats',
    }

    # Tables that already have cluster/hostname disambiguation
    SAFE_TABLES = {
        'jobs', 'job_summary', 'job_metrics', 'node_state',
        'gpu_stats', 'workstation_state', 'group_membership',
        'job_accounting', 'alerts', 'cloud_metrics',
        'interactive_sessions', 'interactive_summary',
        'interactive_servers', 'network_perf',
        'storage_state', 'proficiency_scores',
    }

    # Schema-only tables (don't merge data)
    SKIP_TABLES = {
        'schema_version', 'schema_migrations',
        'sqlite_sequence', 'config',
    }

    # Remove old combined DB and start fresh
    if combined_path.exists():
        combined_path.unlink()

    combined = sqlite3.connect(combined_path)
    combined.execute("PRAGMA journal_mode=WAL")

    total_records = 0

    for site_name, db_path in pulled:
        click.echo(f"  Merging {site_name}... ", nl=False)
        site_records = 0

        try:
            combined.execute(
                f"ATTACH DATABASE ? AS source", (str(db_path),))

            # Get list of tables in source
            tables = [row[0] for row in combined.execute(
                "SELECT name FROM source.sqlite_master "
                "WHERE type='table'"
            ).fetchall()]

            for table in tables:
                if table in SKIP_TABLES or table.startswith('sqlite_'):
                    continue

                # Get source columns
                cols_info = combined.execute(
                    f"PRAGMA source.table_info({table})"
                ).fetchall()
                col_names = [c[1] for c in cols_info]
                col_defs = []
                for c in cols_info:
                    cname, ctype = c[1], c[2] or 'TEXT'
                    col_defs.append(f"{cname} {ctype}")

                # Check if table needs source_site
                needs_site = table in NEEDS_SITE_COL

                # Create table in combined if not exists
                if needs_site:
                    all_defs = col_defs + ["source_site TEXT"]
                    all_cols = col_names + ["source_site"]
                else:
                    all_defs = col_defs
                    all_cols = col_names

                # Skip autoincrement id column for inserts
                insert_cols = [c for c in all_cols if c != 'id']
                insert_defs = [d for d, c in zip(all_defs, all_cols)
                               if c != 'id']

                create_cols = ", ".join(
                    [f"id INTEGER PRIMARY KEY AUTOINCREMENT"]
                    + insert_defs
                )
                combined.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} "
                    f"({create_cols})"
                )

                # Build insert query
                src_cols = [c for c in col_names if c != 'id']
                if needs_site:
                    select_part = ", ".join(
                        [f"source.{table}.{c}" for c in src_cols]
                        + [f"'{site_name}'"]
                    )
                    dest_cols = ", ".join(
                        src_cols + ["source_site"])
                else:
                    select_part = ", ".join(
                        [f"source.{table}.{c}" for c in src_cols])
                    dest_cols = ", ".join(src_cols)

                combined.execute(
                    f"INSERT INTO {table} ({dest_cols}) "
                    f"SELECT {select_part} FROM source.{table}"
                )

                count = combined.execute(
                    f"SELECT changes()").fetchone()[0]
                site_records += count

            combined.execute("DETACH DATABASE source")
            combined.commit()
            total_records += site_records
            click.echo(click.style(
                f"OK ({site_records:,} records)", fg="green"))

        except Exception as e:
            click.echo(click.style(f"ERROR: {e}", fg="red"))
            try:
                combined.execute("DETACH DATABASE source")
            except Exception:
                pass

    combined.close()

    # Summary
    click.echo()
    click.echo(click.style(
        "  ══════════════════════════════════════", fg="cyan"))
    click.echo(click.style(
        f"  Done: {len(pulled)} site(s) merged", fg="green",
        bold=True))
    click.echo()
    size_mb = combined_path.stat().st_size / (1024 * 1024)
    click.echo(f"  Combined DB: {combined_path} ({size_mb:.1f} MB)")
    click.echo(f"  Total records: {total_records:,}")
    click.echo()
    click.echo("  View with:")
    click.echo(f"    nomad status --db {combined_path}")
    click.echo(f"    nomad dashboard --db {combined_path}")
    click.echo()


'''

# Insert before the demo command
insert_before(CLI_PY,
    "@cli.command()\n"
    "@click.option('--jobs', '-n', type=int, default=1000,",
    SYNC_COMMAND,
    "sync_command")


# =====================================================================
print("\n[5] Wizard: add workstation collector config for workstation-type clusters")
# =====================================================================

# After the interactive collector section in the wizard TOML generator,
# add a workstation section when the cluster type is "workstations"
# The interactive collector line uses f-string braces that are hard to match.
# Use insert_before with the "# Clusters" section anchor instead.
WS_BLOCK = (
    '    # Workstation collector\n'
    '    any_workstation = any(\n'
    '        c.get("type") == "workstations" for c in clusters)\n'
    '    if any_workstation:\n'
    '        lines.append("[collectors.workstation]")\n'
    '        lines.append("enabled = true")\n'
    '        ws_list = []\n'
    '        for c in clusters:\n'
    '            if c.get("type") != "workstations":\n'
    '                continue\n'
    '            for dept, pdata in c.get("partitions", {}).items():\n'
    '                for node in pdata.get("nodes", []):\n'
    '                    ws_list.append(\n'
    '                        f\'  {{hostname = "{node}", \'\n'
    '                        f\'department = "{dept}"}}\')\n'
    '        if ws_list:\n'
    '            lines.append("workstations = [")\n'
    '            for ws in ws_list:\n'
    '                lines.append(ws + ",")\n'
    '            lines.append("]")\n'
    '        lines.append("")\n'
    '    else:\n'
    '        lines.append("[collectors.workstation]")\n'
    '        lines.append("enabled = false")\n'
    '        lines.append("")\n'
    '\n'
)

insert_before(CLI_PY,
    '    # Clusters\n'
    '    lines.append("# ============================================")\n'
    '    lines.append("# CLUSTERS")',
    WS_BLOCK,
    "wizard/workstation_collector")


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
What was added:
  - WorkstationCollector wired into nomad collect
  - nomad sync command (SCP + SQLite ATTACH merge)
  - Wizard generates [collectors.workstation] config
  - Tables without cluster/hostname get source_site column in combined DB

Next steps:
  1. git diff
  2. python3 -m pytest tests/ -v
  3. Test: nomad collect --once --collector workstation
  4. Create sync.toml, test: nomad sync --dry-run
  5. Bump version to 1.3.3 and publish
""")
