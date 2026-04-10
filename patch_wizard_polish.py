#!/usr/bin/env python3
"""
NOMAD wizard polish — UX improvements from deployment feedback

Fixes:
  1. Partition selection: numbered list, type numbers to include
  2. Resume prompt skipped when --force is used
  3. node_ssh_user field in TOML config for SSH to compute nodes
  4. Bolder headings and cleaner section separators

Apply on badenpowell:
    cd ~/nomad
    python3 patch_wizard_polish.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
CLI_PY = REPO / "nomad" / "cli.py"

if not CLI_PY.exists():
    print(f"Error: {CLI_PY} not found")
    sys.exit(1)

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
print("\n[1] Partition selection: numbered list with toggle")
# =====================================================================

OLD_PARTITION_SELECT = (
    '            if detected:\n'
    '                click.echo(click.style(\n'
    '                    f"found {len(detected)}", fg="green"))\n'
    '                click.echo()\n'
    '                for p in detected:\n'
    '                    click.echo(f"    • {p}")\n'
    '                click.echo()\n'
    '                use_all = click.confirm(\n'
    '                    "  Monitor all of these partitions?", default=True)\n'
    '                if use_all:\n'
    '                    chosen = detected\n'
    '                else:\n'
    '                    click.echo()\n'
    '                    click.echo("  Type the partition names you want,")\n'
    '                    click.echo("  separated by commas:")\n'
    '                    chosen_str = click.prompt(\n'
    '                        "  Partitions",\n'
    '                        default=\', \'.join(detected))\n'
    '                    chosen = [p.strip() for p in chosen_str.split(\',\')\n'
    '                              if p.strip()]'
)

NEW_PARTITION_SELECT = (
    '            if detected:\n'
    '                click.echo(click.style(\n'
    '                    f"found {len(detected)}", fg="green"))\n'
    '                click.echo()\n'
    '                for i, p in enumerate(detected, 1):\n'
    '                    click.echo(f"    {i}) {p}")\n'
    '                click.echo()\n'
    '                use_all = click.confirm(\n'
    '                    "  Monitor all of these partitions?",\n'
    '                    default=True)\n'
    '                if use_all:\n'
    '                    chosen = detected\n'
    '                else:\n'
    '                    click.echo()\n'
    '                    click.echo(\n'
    '                        "  Type the numbers of the partitions")\n'
    '                    click.echo(\n'
    '                        "  you want, separated by commas.")\n'
    '                    click.echo(\n'
    '                        f"  (e.g., 1,2 for"\n'
    '                        f" {detected[0]} and"\n'
    '                        f" {detected[1] if len(detected) > 1 else detected[0]})")\n'
    '                    click.echo()\n'
    '                    sel_str = click.prompt(\n'
    '                        "  Partitions",\n'
    '                        default=\',\'.join(\n'
    '                            str(i) for i in\n'
    '                            range(1, len(detected) + 1)))\n'
    '                    chosen = []\n'
    '                    for part in sel_str.split(\',\'):\n'
    '                        part = part.strip()\n'
    '                        # Accept numbers or names\n'
    '                        try:\n'
    '                            idx = int(part) - 1\n'
    '                            if 0 <= idx < len(detected):\n'
    '                                chosen.append(detected[idx])\n'
    '                        except ValueError:\n'
    '                            if part in detected:\n'
    '                                chosen.append(part)\n'
    '                    if not chosen:\n'
    '                        click.echo(click.style(\n'
    '                            "  No valid selection,"\n'
    '                            " using all partitions.",\n'
    '                            fg="yellow"))\n'
    '                        chosen = detected'
)

patch(CLI_PY, OLD_PARTITION_SELECT, NEW_PARTITION_SELECT,
      "wizard/partition_numbered_select")


# =====================================================================
print("\n[2] Resume prompt skipped when --force")
# =====================================================================

patch(CLI_PY,
    '    if saved and not quick:',
    '    if saved and not quick and not force:',
    "wizard/resume_respects_force")


# =====================================================================
print("\n[3] Wizard TOML: add node_ssh_user to cluster config")
# =====================================================================

# When writing cluster config, add a node_ssh_user field if in local HPC mode.
# This tells collectors how to SSH to compute nodes for GPU checks etc.
# Find where the cluster TOML section is generated.

# The cluster config block writes [clusters.<id>] with name, type, host, etc.
# We need to add node_ssh_user after the type line.

patch(CLI_PY,
    '        lines.append(\n'
    '            f\'type = "{cluster.get("type", "hpc")}"\')',

    '        lines.append(\n'
    '            f\'type = "{cluster.get("type", "hpc")}"\')\n'
    '\n'
    '        # SSH user for accessing compute nodes (e.g., root)\n'
    '        if cluster.get("type") == "hpc":\n'
    '            lines.append(\n'
    '                \'# SSH user for compute nodes\'\n'
    '                \' (if different from current user)\')\n'
    '            lines.append(\'# node_ssh_user = "root"\')',

    "wizard/node_ssh_user_toml")


# =====================================================================
print("\n[4] Wizard: bolder step headings")
# =====================================================================

# Make "Step 1: Connection Mode" etc. more prominent
patch(CLI_PY,
    '            click.echo(click.style(\n'
    '                "  Step 1: Connection Mode",\n'
    '                fg="green", bold=True))',

    '            click.echo(click.style(\n'
    '                "  ━━ Step 1: Connection Mode ━━",\n'
    '                fg="cyan", bold=True))',

    "wizard/step1_heading")

patch(CLI_PY,
    '        click.echo(click.style(\n'
    '            "  Step 2: Clusters", fg="green", bold=True))',

    '        click.echo(click.style(\n'
    '            "  ━━ Step 2: Clusters ━━", fg="cyan", bold=True))',

    "wizard/step2_heading")

patch(CLI_PY,
    '        click.echo(click.style(\n'
    '            "  Step 3: Alerts", fg="green", bold=True))',

    '        click.echo(click.style(\n'
    '            "  ━━ Step 3: Alerts ━━", fg="cyan", bold=True))',

    "wizard/step3_heading")

patch(CLI_PY,
    '        click.echo(click.style(\n'
    '            "  Step 4: Dashboard", fg="green", bold=True))',

    '        click.echo(click.style(\n'
    '            "  ━━ Step 4: Dashboard ━━", fg="cyan", bold=True))',

    "wizard/step4_heading")


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
