#!/usr/bin/env python3
"""
NØMAD Cosmetic Patcher
========================
Fixes two cosmetic issues in the wizard output:
  1. Final summary says "groups" for HPC clusters (should be "partitions")
  2. Extra spaces in cluster summary alignment

Usage:
    python3 patch_cosmetic.py /path/to/nomad/nomad/cli.py
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

    # ── Fix 1: "groups" → "partitions" for HPC in final summary ──────
    old_1 = (
        '        click.echo(\n'
        '            f"    • {c[\'name\']}:"\n'
        '            f" {pcount} groups,"\n'
        '            f" {ncount} nodes{loc}")'
    )
    new_1 = (
        '        plabel = ("partitions"\n'
        '                  if c.get("type") == "hpc"\n'
        '                  else "groups")\n'
        '        click.echo(\n'
        '            f"    • {c[\'name\']}:"\n'
        '            f" {pcount} {plabel},"\n'
        '            f" {ncount} nodes{loc}")'
    )

    if old_1 in content:
        content = content.replace(old_1, new_1)
        changes += 1
        print("  ✓ Fixed partition/group label in final summary")
    else:
        print("  ✗ Could not find final summary label block")

    # ── Fix 2: Alignment in show_cluster_summary ─────────────────────
    old_2 = (
        '            click.echo(\n'
        '                f"    {part_label}:  "\n'
        '                f"   {pid}"\n'
        '                f" — {len(pdata[\'nodes\'])} nodes{gpu_info}")'
    )
    new_2 = (
        '            click.echo(\n'
        '                f"    {part_label}:    {pid}"\n'
        '                f" — {len(pdata[\'nodes\'])} nodes{gpu_info}")'
    )

    if old_2 in content:
        content = content.replace(old_2, new_2)
        changes += 1
        print("  ✓ Fixed alignment in cluster summary")
    else:
        print("  ✗ Could not find cluster summary alignment block")

    if changes == 0:
        print("\nNo changes made. Already patched?")
        return

    # Backup
    backup = path.with_suffix('.py.bak')
    shutil.copy(path, backup)
    print(f"\nBackup saved: {backup}")

    path.write_text(content)
    print(f"Patched {changes} location(s)")
    print()
    print("Test with:")
    print("  nomad init --force")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(
            "Usage: python3 patch_cosmetic.py"
            " /path/to/nomad/nomad/cli.py")
        sys.exit(1)
    patch(sys.argv[1])
