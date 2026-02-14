#!/usr/bin/env python3
"""
NØMAD Config Path Patcher
===========================
Fixes config/database path resolution so syscheck, collect, and
other commands find the config created by 'nomad init'.

Search order:
  1. -c /path/to/config.toml  (explicit CLI flag)
  2. ~/.config/nomad/nomad.toml  (user install)
  3. /etc/nomad/nomad.toml  (system install)

Usage:
    python3 patch_config_paths.py /path/to/nomad/nomad/cli.py
"""

import sys
import shutil
from pathlib import Path


def patch(cli_path: str):
    path = Path(cli_path)
    if not path.exists():
        print(f"ERROR: {cli_path} not found")
        sys.exit(1)

    content = path.read_text()
    changes = 0

    # ── Edit 1: Add resolve_config_path + fix get_db_path default ────
    old_1 = (
        "def get_db_path(config: dict[str, Any]) -> Path:\n"
        "    \"\"\"Get database path from config.\"\"\"\n"
        "    data_dir = Path(config.get('general', {}).get('data_dir', '/var/lib/nomad'))\n"
        "    return data_dir / 'nomad.db'"
    )
    new_1 = (
        "def resolve_config_path() -> str:\n"
        "    \"\"\"Find config file: user path first, then system path.\"\"\"\n"
        "    user_config = Path.home() / '.config' / 'nomad' / 'nomad.toml'\n"
        "    system_config = Path('/etc/nomad/nomad.toml')\n"
        "    if user_config.exists():\n"
        "        return str(user_config)\n"
        "    if system_config.exists():\n"
        "        return str(system_config)\n"
        "    return str(user_config)  # Default to user path even if missing\n"
        "\n"
        "\n"
        "def get_db_path(config: dict[str, Any]) -> Path:\n"
        "    \"\"\"Get database path from config.\"\"\"\n"
        "    default_data = str(Path.home() / '.local' / 'share' / 'nomad')\n"
        "    data_dir = Path(config.get('general', {}).get('data_dir', default_data))\n"
        "    return data_dir / 'nomad.db'"
    )

    if old_1 in content:
        content = content.replace(old_1, new_1)
        changes += 1
        print("  ✓ Added resolve_config_path() + fixed get_db_path default")
    else:
        print("  ✗ Could not find get_db_path function")
        print("    (already patched or code has changed)")

    # ── Edit 2: Change --config default from /etc/nomad to None ─────
    old_2 = "              default='/etc/nomad/nomad.toml',"
    new_2 = "              default=None,"

    if old_2 in content:
        content = content.replace(old_2, new_2)
        changes += 1
        print("  ✓ Changed --config default to None")
    else:
        print("  ✗ Could not find --config default='/etc/nomad/nomad.toml'")
        print("    (already patched or code has changed)")

    # ── Edit 3: Use resolve_config_path in cli() ────────────────────
    old_3 = (
        "    # Try to load config, but don't fail if not found\n"
        "    config_file = Path(config_path)"
    )
    new_3 = (
        "    # Try to load config, but don't fail if not found\n"
        "    if config_path is None:\n"
        "        config_path = resolve_config_path()\n"
        "    config_file = Path(config_path)"
    )

    if old_3 in content:
        content = content.replace(old_3, new_3)
        changes += 1
        print("  ✓ Updated cli() to use resolve_config_path()")
    else:
        print("  ✗ Could not find config_file = Path(config_path)")
        print("    (already patched or code has changed)")

    # ── Edit 4: Fix syscheck hardcoded error message ─────────────────
    old_4a = (
        "        click.echo(f\"  {click.style('✗', fg='red')}"
        " Config not found: /etc/nomad/nomad.toml\")\n"
        "        click.echo(f\"    → Create config or use:"
        " nomad -c /path/to/config.toml\")"
    )
    new_4a = (
        "        expected = resolve_config_path()\n"
        "        click.echo(f\"  {click.style('✗', fg='red')}"
        " Config not found: {expected}\")\n"
        "        click.echo(f\"    → Run: nomad init\")"
    )

    if old_4a in content:
        content = content.replace(old_4a, new_4a)
        changes += 1
        print("  ✓ Fixed syscheck error message")
    else:
        # Try a more flexible match
        old_4b = "Config not found: /etc/nomad/nomad.toml"
        if old_4b in content:
            content = content.replace(old_4b, "Config not found: {expected}")
            # Also add the expected = line before it
            old_line = "        click.echo(f\"  {click.style('✗', fg='red')} Config not found: {expected}\")"
            new_line = "        expected = resolve_config_path()\n" + old_line
            content = content.replace(old_line, new_line)
            # Fix the hint line too
            content = content.replace(
                "    → Create config or use: nomad -c /path/to/config.toml",
                "    → Run: nomad init"
            )
            changes += 1
            print("  ✓ Fixed syscheck error message (alt match)")
        else:
            print("  ✗ Could not find syscheck error message")
            print("    (already patched or code has changed)")

    if changes == 0:
        print("\nNo changes made. Already patched?")
        return

    # Create backup
    backup = path.with_suffix('.py.bak')
    shutil.copy(path, backup)
    print(f"\nBackup saved: {backup}")

    # Write
    path.write_text(content)
    print(f"Patched {changes} location(s)")
    print()
    print("Config resolution order is now:")
    print("  1. nomad -c /custom/path.toml  (explicit)")
    print("  2. ~/.config/nomad/nomad.toml  (user)")
    print("  3. /etc/nomad/nomad.toml  (system)")
    print()
    print("Test with:")
    print("  nomad syscheck")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(
            "Usage: python3 patch_config_paths.py"
            " /path/to/nomad/nomad/cli.py")
        sys.exit(1)
    patch(sys.argv[1])
