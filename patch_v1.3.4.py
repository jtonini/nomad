#!/usr/bin/env python3
"""
NOMAD v1.3.4 Patch — Deployment fixes from arachne setup

Fixes:
  1. collect calls ensure_database() before collectors (missing tables)
  2. Wizard local mode: detect filesystems/features locally, not via SSH
  3. run_cmd adds BatchMode=yes and handles ssh_user=None
  4. sacct ReqGRES -> ReqTRES (slurm.py + groups.py)
  5. nomad --version flag on CLI group
  6. Wizard clears screen on launch
  7. ReqTRES parsing handles both old GRES and new TRES formats

Apply on badenpowell:
    cd ~/nomad
    python3 patch_v1.3.4.py
    python3 -m pytest tests/ -v
"""

import os
import sys
from pathlib import Path

REPO = Path.home() / "nomad"
if not (REPO / "nomad" / "cli.py").exists():
    print(f"Error: Expected repo at {REPO}/nomad/cli.py")
    sys.exit(1)

CLI_PY = REPO / "nomad" / "cli.py"
SLURM_PY = REPO / "nomad" / "collectors" / "slurm.py"
GROUPS_PY = REPO / "nomad" / "collectors" / "groups.py"

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


def patch_all(path, old, new, label):
    text = path.read_text()
    n = text.count(old)
    if n == 0:
        skipped.append(f"{label} -- pattern not found")
        return False
    if new in text:
        skipped.append(f"{label} -- already applied")
        return False
    path.write_text(text.replace(old, new))
    applied.append(f"{label} ({n}x)")
    print(f"  OK   {label} ({n} occurrences)")
    return True


# =====================================================================
print("\n[1] collect: call ensure_database before collectors")
# =====================================================================

patch(CLI_PY,
    '    click.echo(f"Database: {db_path}")\n'
    '\n'
    '    # Initialize collectors',

    '    # Ensure database schema exists\n'
    '    from nomad.db import ensure_database\n'
    '    ensure_database(db_path)\n'
    '\n'
    '    click.echo(f"Database: {db_path}")\n'
    '\n'
    '    # Initialize collectors',

    "collect/ensure_database")


# =====================================================================
print("\n[2] Wizard: fix collect_filesystems for local mode")
# =====================================================================

# The bug: when host=None (local mode), it sets probe_host to first compute node.
# Fix: only probe a node for workstation groups in remote mode. For HPC local,
# run df locally (probe_host stays None).

patch(CLI_PY,
    '    def collect_filesystems(cluster, host, ssh_user, ssh_key):\n'
    '        """Ask user about filesystems. Modifies cluster."""\n'
    '        # For workstation groups, probe first node instead of headnode\n'
    '        probe_host = host\n'
    '        if not probe_host and cluster.get("partitions"):\n'
    '            first_part = next(iter(cluster["partitions"].values()), {})\n'
    '            first_nodes = first_part.get("nodes", [])\n'
    '            if first_nodes:\n'
    '                probe_host = first_nodes[0]',

    '    def collect_filesystems(cluster, host, ssh_user, ssh_key):\n'
    '        """Ask user about filesystems. Modifies cluster."""\n'
    '        # For remote workstation groups, probe first node\n'
    '        # For local HPC headnode, run df locally (host=None)\n'
    '        probe_host = host\n'
    '        if (not probe_host\n'
    '                and cluster.get("mode") == "remote"\n'
    '                and cluster.get("type") == "workstations"\n'
    '                and cluster.get("partitions")):\n'
    '            first_part = next(iter(cluster["partitions"].values()), {})\n'
    '            first_nodes = first_part.get("nodes", [])\n'
    '            if first_nodes:\n'
    '                probe_host = first_nodes[0]',

    "wizard/collect_filesystems")


# =====================================================================
print("\n[3] Wizard: fix collect_features for local mode")
# =====================================================================

patch(CLI_PY,
    '    def collect_features(cluster, host, ssh_user, ssh_key):\n'
    '        """Ask user about optional features. Modifies cluster."""\n'
    '        # For workstation groups, probe first node instead of headnode\n'
    '        probe_host = host\n'
    '        if not probe_host and cluster.get("partitions"):\n'
    '            first_part = next(iter(cluster["partitions"].values()), {})\n'
    '            first_nodes = first_part.get("nodes", [])\n'
    '            if first_nodes:\n'
    '                probe_host = first_nodes[0]',

    '    def collect_features(cluster, host, ssh_user, ssh_key):\n'
    '        """Ask user about optional features. Modifies cluster."""\n'
    '        # For remote workstation groups, probe first node\n'
    '        # For local HPC headnode, run commands locally\n'
    '        probe_host = host\n'
    '        if (not probe_host\n'
    '                and cluster.get("mode") == "remote"\n'
    '                and cluster.get("type") == "workstations"\n'
    '                and cluster.get("partitions")):\n'
    '            first_part = next(iter(cluster["partitions"].values()), {})\n'
    '            first_nodes = first_part.get("nodes", [])\n'
    '            if first_nodes:\n'
    '                probe_host = first_nodes[0]',

    "wizard/collect_features")


# =====================================================================
print("\n[4] Wizard: fix run_cmd — BatchMode + handle None user")
# =====================================================================

patch(CLI_PY,
    '    def run_cmd(cmd, host=None, ssh_user=None, ssh_key=None):\n'
    '        """Run a command locally or via SSH. Returns stdout or None."""\n'
    '        if host:\n'
    '            ssh_cmd = ["ssh", "-o", "ConnectTimeout=5",\n'
    '                       "-o", "StrictHostKeyChecking=accept-new"]\n'
    '            if ssh_key:\n'
    '                ssh_cmd += ["-i", ssh_key]\n'
    '            ssh_cmd += [f"{ssh_user}@{host}", cmd]',

    '    def run_cmd(cmd, host=None, ssh_user=None, ssh_key=None):\n'
    '        """Run a command locally or via SSH. Returns stdout or None."""\n'
    '        if host:\n'
    '            if not ssh_user:\n'
    '                ssh_user = os.getenv("USER", "root")\n'
    '            ssh_cmd = ["ssh", "-o", "ConnectTimeout=5",\n'
    '                       "-o", "BatchMode=yes",\n'
    '                       "-o", "StrictHostKeyChecking=accept-new"]\n'
    '            if ssh_key:\n'
    '                ssh_cmd += ["-i", ssh_key]\n'
    '            ssh_cmd += [f"{ssh_user}@{host}", cmd]',

    "wizard/run_cmd_fix")


# =====================================================================
print("\n[5] slurm.py: ReqGRES -> ReqTRES")
# =====================================================================

if SLURM_PY.exists():
    # Fix the format comment
    patch(SLURM_PY,
        '# Format: JobID|User|Group|Partition|JobName|State|NodeList|AllocCPUS|ReqMem|ReqGRES|Timelimit|Elapsed|Submit|Start|End|ExitCode\n'
        '            format_str = "JobID,User,Group,Partition,JobName,State,NodeList,AllocCPUS,ReqMem,ReqGRES,Timelimit,Elapsed,Submit,Start,End,ExitCode"',

        '# Format: JobID|User|Group|Partition|JobName|State|NodeList|AllocCPUS|ReqMem|ReqTRES|Timelimit|Elapsed|Submit|Start|End|ExitCode\n'
        '            format_str = "JobID,User,Group,Partition,JobName,State,NodeList,AllocCPUS,ReqMem,ReqTRES,Timelimit,Elapsed,Submit,Start,End,ExitCode"',

        "slurm/ReqGRES_to_ReqTRES")

    # Fix _parse_gpus to handle ReqTRES format (gres/gpu=2 or gres/gpu:type=N)
    patch(SLURM_PY,
        '    def _parse_gpus(self, value: str) -> int:\n'
        '        """Parse GPU request string (e.g., \'gpu:2\')."""\n'
        '        try:\n'
        '            value = value.strip()\n'
        '            if not value or value == \'N/A\':\n'
        '                return 0\n'
        '\n'
        '            # Format: gpu:N or gpu:type:N\n'
        '            if \'gpu\' in value.lower():\n'
        '                parts = value.split(\':\')\n'
        '                for p in reversed(parts):\n'
        '                    try:\n'
        '                        return int(p)\n'
        '                    except ValueError:\n'
        '                        continue\n'
        '            return 0',

        '    def _parse_gpus(self, value: str) -> int:\n'
        '        """Parse GPU request from ReqTRES or ReqGRES format.\n'
        '\n'
        '        Handles:\n'
        '          ReqGRES:  gpu:2, gpu:a100:1\n'
        '          ReqTRES:  cpu=4,mem=8G,gres/gpu=2, gres/gpu:a100=2\n'
        '        """\n'
        '        try:\n'
        '            value = value.strip()\n'
        '            if not value or value == \'N/A\':\n'
        '                return 0\n'
        '\n'
        '            # ReqTRES format: comma-separated key=value pairs\n'
        '            if \'=\' in value:\n'
        '                for part in value.split(\',\'):\n'
        '                    if \'gpu\' in part.lower():\n'
        '                        # gres/gpu=2 or gres/gpu:a100=2\n'
        '                        try:\n'
        '                            return int(part.split(\'=\')[-1])\n'
        '                        except ValueError:\n'
        '                            continue\n'
        '                return 0\n'
        '\n'
        '            # Legacy ReqGRES format: gpu:N or gpu:type:N\n'
        '            if \'gpu\' in value.lower():\n'
        '                parts = value.split(\':\')\n'
        '                for p in reversed(parts):\n'
        '                    try:\n'
        '                        return int(p)\n'
        '                    except ValueError:\n'
        '                        continue\n'
        '            return 0',

        "slurm/parse_gpus_tres")
else:
    skipped.append("slurm.py -- file not found")


# =====================================================================
print("\n[6] groups.py: ReqGRES -> ReqTRES")
# =====================================================================

if GROUPS_PY.exists():
    # Fix the sacct format string
    patch(GROUPS_PY,
        'f"Start,End,ReqGRES"',
        'f"Start,End,ReqTRES"',
        "groups/ReqGRES_to_ReqTRES")

    # Fix the comment
    patch(GROUPS_PY,
        '# Parse GPU count from ReqGRES (e.g. "gpu:2", "gpu:a100:1")',
        '# Parse GPU count from ReqTRES (e.g. "gres/gpu=2", "gres/gpu:a100=2")',
        "groups/comment_TRES")

    # Fix _parse_gpu_gres to handle ReqTRES format too
    patch(GROUPS_PY,
        '    def _parse_gpu_gres(gres_str: str) -> int:\n'
        '        """Parse SLURM GRES string for GPU count."""\n'
        '        gpu_count = 0\n'
        '        for part in gres_str.split(\',\'):\n'
        '            if \'gpu\' in part.lower():\n'
        '                pieces = part.split(\':\')\n'
        '                try:\n'
        '                    gpu_count += int(pieces[-1])\n'
        '                except ValueError:\n'
        '                    gpu_count += 1\n'
        '        return gpu_count',

        '    def _parse_gpu_gres(gres_str: str) -> int:\n'
        '        """Parse SLURM GRES/TRES string for GPU count.\n'
        '\n'
        '        Handles:\n'
        '          ReqGRES:  gpu:2, gpu:a100:1\n'
        '          ReqTRES:  cpu=4,mem=8G,gres/gpu=2\n'
        '        """\n'
        '        gpu_count = 0\n'
        '        for part in gres_str.split(\',\'):\n'
        '            if \'gpu\' not in part.lower():\n'
        '                continue\n'
        '            # ReqTRES: gres/gpu=2 or gres/gpu:a100=2\n'
        '            if \'=\' in part:\n'
        '                try:\n'
        '                    gpu_count += int(part.split(\'=\')[-1])\n'
        '                except ValueError:\n'
        '                    gpu_count += 1\n'
        '            else:\n'
        '                # ReqGRES: gpu:2 or gpu:a100:1\n'
        '                pieces = part.split(\':\')\n'
        '                try:\n'
        '                    gpu_count += int(pieces[-1])\n'
        '                except ValueError:\n'
        '                    gpu_count += 1\n'
        '        return gpu_count',

        "groups/parse_gpu_tres")
else:
    skipped.append("groups.py -- file not found")


# =====================================================================
print("\n[7] CLI group: add --version flag")
# =====================================================================

patch(CLI_PY,
    "@click.group()\n"
    "@click.option('-c', '--config', 'config_path',\n"
    "              type=click.Path(),\n"
    "              default=None,\n"
    "              help='Path to config file')\n"
    "@click.option('-v', '--verbose', is_flag=True, help='Enable debug logging')\n"
    "@click.pass_context\n"
    'def cli(ctx: click.Context, config_path: str, verbose: bool) -> None:\n'
    '    """NØMAD - NØde Monitoring And Diagnostics\n'
    '    \n'
    '    Lightweight HPC monitoring and prediction tool.\n'
    '    """',

    "def _get_version():\n"
    "    try:\n"
    "        from importlib.metadata import version as pkg_version\n"
    "        return pkg_version('nomad-hpc')\n"
    "    except Exception:\n"
    "        return 'dev'\n"
    "\n"
    "\n"
    "@click.group()\n"
    "@click.version_option(version=_get_version(), prog_name='nomad')\n"
    "@click.option('-c', '--config', 'config_path',\n"
    "              type=click.Path(),\n"
    "              default=None,\n"
    "              help='Path to config file')\n"
    "@click.option('-v', '--verbose', is_flag=True, help='Enable debug logging')\n"
    "@click.pass_context\n"
    'def cli(ctx: click.Context, config_path: str, verbose: bool) -> None:\n'
    '    """NØMAD - NØde Monitoring And Diagnostics\n'
    '    \n'
    '    Lightweight HPC monitoring and prediction tool.\n'
    '    """',

    "cli/version_flag")


# =====================================================================
print("\n[8] Wizard: clear screen on launch")
# =====================================================================

patch(CLI_PY,
    '    # ── Banner ───────────────────────────────────────────────────────\n'
    '    click.echo()\n'
    '    click.echo(click.style(\n'
    '        "  ◈ NØMAD Setup Wizard", fg="cyan", bold=True))',

    '    # ── Banner ───────────────────────────────────────────────────────\n'
    '    click.echo("\\033[2J\\033[H", nl=False)  # Clear screen\n'
    '    click.echo()\n'
    '    click.echo(click.style(\n'
    '        "  ◈ NØMAD Setup Wizard", fg="cyan", bold=True))',

    "wizard/clear_screen")


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
Fixes:
  1. nomad collect --once now creates all tables on first run
  2. Wizard detects filesystems/features locally in headnode mode
  3. SSH in wizard uses BatchMode=yes, falls back to $USER if no ssh_user
  4. sacct uses ReqTRES instead of removed ReqGRES field
  5. nomad --version works
  6. Wizard clears screen on launch
  7. GPU parsing handles both ReqGRES and ReqTRES formats

Next steps:
  1. git diff
  2. python3 -m pytest tests/ -v
  3. git add -A && git commit
  4. git push origin main
  5. On arachne: pip install --user --force-reinstall --no-deps \\
       git+https://github.com/jtonini/nomad-hpc.git@main
  6. nomad init --force   (re-run wizard)
  7. nomad collect --once  (should work now)
""")
