#!/usr/bin/env python3
"""
NOMAD v1.3.2 UX Patch — Wizard usability improvements

Improvements:
  1. --dry-run option: show generated TOML before writing, ask for confirmation
  2. --show option: dump current config to terminal
  3. Banner hint about nomad syscheck
  4. Edit menu shows current feature values and lets you pick one to toggle

Apply on badenpowell AFTER patch_v1.3.2.py:
    cd ~/nomad
    python3 /path/to/patch_v1.3.2_ux.py
    git diff
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


# =====================================================================
print("\n[1] Add --dry-run and --show options to init command")
# =====================================================================

# Add the two new options to the decorator chain
patch(CLI_PY,
    "@click.option('--no-prolog', is_flag=True, help='Skip SLURM prolog hook')\n"
    "@click.pass_context\n"
    "def init(ctx, system, force, quick, no_systemd, no_prolog):",

    "@click.option('--no-prolog', is_flag=True, help='Skip SLURM prolog hook')\n"
    "@click.option('--dry-run', is_flag=True, help='Show config without writing')\n"
    "@click.option('--show', is_flag=True, help='Display current config and exit')\n"
    "@click.pass_context\n"
    "def init(ctx, system, force, quick, no_systemd, no_prolog, dry_run, show):",

    "init/options")


# =====================================================================
print("\n[2] Add --show handler at top of init function")
# =====================================================================

# Insert the --show logic right after the path determination, before the
# existing config check. We'll put it after the config_file assignment.

patch(CLI_PY,
    "    config_file = config_dir / 'nomad.toml'\n"
    "\n"
    "    # Check existing config\n"
    "    if config_file.exists() and not force:",

    "    config_file = config_dir / 'nomad.toml'\n"
    "\n"
    "    # ── Show current config and exit ────────────────────────────────\n"
    "    if show:\n"
    "        if config_file.exists():\n"
    "            click.echo()\n"
    "            click.echo(click.style(\n"
    "                f\"  Config: {config_file}\", fg=\"cyan\", bold=True))\n"
    "            click.echo(click.style(\n"
    "                \"  ══════════════════════════════════════\", fg=\"cyan\"))\n"
    "            click.echo()\n"
    "            click.echo(config_file.read_text())\n"
    "        else:\n"
    "            click.echo()\n"
    "            click.echo(click.style(\n"
    "                f\"  No config found at {config_file}\", fg=\"yellow\"))\n"
    "            click.echo(\"  Run 'nomad init' to create one.\")\n"
    "            click.echo()\n"
    "        return\n"
    "\n"
    "    # Check existing config\n"
    "    if config_file.exists() and not force:",

    "init/show_handler")


# =====================================================================
print("\n[3] Add --dry-run logic around config write")
# =====================================================================

patch(CLI_PY,
    "    # Write the config\n"
    "    config_content = '\\n'.join(lines)\n"
    "    config_file.write_text(config_content)\n"
    "\n"
    "    # Clean up wizard state file\n"
    "    clear_state()",

    "    # Write the config\n"
    "    config_content = '\\n'.join(lines)\n"
    "\n"
    "    if dry_run:\n"
    "        click.echo()\n"
    "        click.echo(click.style(\n"
    "            \"  ── Preview (--dry-run) ──\", fg=\"yellow\", bold=True))\n"
    "        click.echo()\n"
    "        click.echo(config_content)\n"
    "        click.echo()\n"
    "        click.echo(click.style(\n"
    "            f\"  Would be written to: {config_file}\", fg=\"yellow\"))\n"
    "        click.echo(\"  Run without --dry-run to save.\")\n"
    "        click.echo()\n"
    "        return\n"
    "\n"
    "    config_file.write_text(config_content)\n"
    "\n"
    "    # Clean up wizard state file\n"
    "    clear_state()",

    "init/dry_run")


# =====================================================================
print("\n[4] Add syscheck hint to banner")
# =====================================================================

patch(CLI_PY,
    "        click.echo(\n"
    "            \"  This wizard will help you configure NØMAD for your\")\n"
    "        click.echo(\n"
    "            \"  HPC environment. Press Enter to accept the default\")\n"
    "        click.echo(\"  value shown in [brackets].\")\n"
    "        click.echo()",

    "        click.echo(\n"
    "            \"  This wizard will help you configure NØMAD for your\")\n"
    "        click.echo(\n"
    "            \"  HPC environment. Press Enter to accept the default\")\n"
    "        click.echo(\"  value shown in [brackets].\")\n"
    "        click.echo()\n"
    "        click.echo(click.style(\n"
    "            \"  Tip:\", fg=\"green\", bold=True) +\n"
    "            \" After this wizard, run 'nomad syscheck' to verify\")\n"
    "        click.echo(\n"
    "            \"  your environment is ready for data collection.\")\n"
    "        click.echo()",

    "init/syscheck_hint")


# =====================================================================
print("\n[5] Edit menu shows current values and per-feature toggle")
# =====================================================================

OLD_EDIT_FEATURES = (
    '                    elif edit_choice == 4:\n'
    '                        cluster["has_gpu"] = (\n'
    '                            click.confirm(\n'
    '                                "  Enable GPU monitoring?",\n'
    '                                default=cluster.get(\n'
    '                                    "has_gpu", False)))\n'
    '                        cluster["has_nfs"] = (\n'
    '                            click.confirm(\n'
    '                                "  Enable NFS monitoring?",\n'
    '                                default=cluster.get(\n'
    '                                    "has_nfs", False)))\n'
    '                        cluster["has_interactive"] = (\n'
    '                            click.confirm(\n'
    '                                "  Enable interactive"\n'
    '                                " session monitoring?",\n'
    '                                default=cluster.get(\n'
    '                                    "has_interactive",\n'
    '                                    False)))'
)

NEW_EDIT_FEATURES = (
    '                    elif edit_choice == 4:\n'
    '                        gpu_st = click.style(\n'
    '                            "on" if cluster.get("has_gpu")\n'
    '                            else "off",\n'
    '                            fg="green" if cluster.get("has_gpu")\n'
    '                            else "red")\n'
    '                        nfs_st = click.style(\n'
    '                            "on" if cluster.get("has_nfs")\n'
    '                            else "off",\n'
    '                            fg="green" if cluster.get("has_nfs")\n'
    '                            else "red")\n'
    '                        int_st = click.style(\n'
    '                            "on" if cluster.get("has_interactive")\n'
    '                            else "off",\n'
    '                            fg="green"\n'
    '                            if cluster.get("has_interactive")\n'
    '                            else "red")\n'
    '                        click.echo()\n'
    '                        click.echo(\n'
    '                            f"    1) GPU monitoring:"\n'
    '                            f"         {gpu_st}")\n'
    '                        click.echo(\n'
    '                            f"    2) NFS monitoring:"\n'
    '                            f"         {nfs_st}")\n'
    '                        click.echo(\n'
    '                            f"    3) Interactive sessions:"\n'
    '                            f"  {int_st}")\n'
    '                        click.echo(\n'
    '                            "    4) Toggle all")\n'
    '                        click.echo()\n'
    '                        feat_choice = click.prompt(\n'
    '                            "  Select",\n'
    '                            type=click.IntRange(1, 4),\n'
    '                            default=4)\n'
    '                        if feat_choice == 1:\n'
    '                            cluster["has_gpu"] = (\n'
    '                                not cluster.get(\n'
    '                                    "has_gpu", False))\n'
    '                            st = ("enabled"\n'
    '                                  if cluster["has_gpu"]\n'
    '                                  else "disabled")\n'
    '                            click.echo(\n'
    '                                f"  GPU monitoring {st}.")\n'
    '                        elif feat_choice == 2:\n'
    '                            cluster["has_nfs"] = (\n'
    '                                not cluster.get(\n'
    '                                    "has_nfs", False))\n'
    '                            st = ("enabled"\n'
    '                                  if cluster["has_nfs"]\n'
    '                                  else "disabled")\n'
    '                            click.echo(\n'
    '                                f"  NFS monitoring {st}.")\n'
    '                        elif feat_choice == 3:\n'
    '                            cluster["has_interactive"] = (\n'
    '                                not cluster.get(\n'
    '                                    "has_interactive",\n'
    '                                    False))\n'
    '                            st = ("enabled"\n'
    '                                  if cluster[\n'
    '                                      "has_interactive"]\n'
    '                                  else "disabled")\n'
    '                            click.echo(\n'
    '                                "  Interactive session"\n'
    '                                f" monitoring {st}.")\n'
    '                        elif feat_choice == 4:\n'
    '                            cluster["has_gpu"] = (\n'
    '                                click.confirm(\n'
    '                                    "  Enable GPU?",\n'
    '                                    default=cluster.get(\n'
    '                                        "has_gpu",\n'
    '                                        False)))\n'
    '                            cluster["has_nfs"] = (\n'
    '                                click.confirm(\n'
    '                                    "  Enable NFS?",\n'
    '                                    default=cluster.get(\n'
    '                                        "has_nfs",\n'
    '                                        False)))\n'
    '                            cluster["has_interactive"] = (\n'
    '                                click.confirm(\n'
    '                                    "  Enable interactive?",\n'
    '                                    default=cluster.get(\n'
    '                                        "has_interactive",\n'
    '                                        False)))'
)

patch(CLI_PY, OLD_EDIT_FEATURES, NEW_EDIT_FEATURES,
      "wizard/edit_features")


# =====================================================================
print("\n[6] Update --help docstring with new options")
# =====================================================================

patch(CLI_PY,
    '      nomad init                    Interactive wizard\n'
    '      nomad init --quick            Auto-detect everything\n'
    '      nomad init --force            Overwrite existing config\n'
    '      sudo nomad init --system      System-wide installation',

    '      nomad init                    Interactive wizard\n'
    '      nomad init --quick            Auto-detect everything\n'
    '      nomad init --force            Overwrite existing config\n'
    '      nomad init --show             Display current config\n'
    '      nomad init --dry-run          Preview without writing\n'
    '      sudo nomad init --system      System-wide installation',

    "init/docstring")


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
Next steps:
  1. git diff                    # review
  2. nomad init --help           # verify new options show up
  3. nomad init --show           # test show mode
  4. nomad init --dry-run        # test dry-run mode
  5. nomad init --force          # test edit menu features display
""")
