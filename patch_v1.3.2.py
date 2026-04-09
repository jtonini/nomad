#!/usr/bin/env python3
"""
NOMAD v1.3.2 Patch Script — Wizard & Config Resolution Fixes

Fixes:
  1. Unified resolve_cluster_name() helper in config/__init__.py
  2. collect -> node_state uses helper (not ad-hoc config.get)
  3. collect -> interactive reads both [interactive] and [collectors.interactive]
  4. insights CLI (5 occurrences) uses helper
  5. dynamics CLI uses helper
  6. Wizard TOML: explicit per-collector enabled/disabled (drop cosmetic list)
  7. Wizard TOML: [interactive] section when enabled
  8. Wizard TOML: [alerts.thresholds.gpu] and [alerts.thresholds.nfs]
  9. Wizard TOML: remove dead [database] path key

Apply on badenpowell:
    cd ~/nomad
    python3 /path/to/patch_v1.3.2.py
    git diff
    python3 -m pytest tests/ -v
"""

import sys
from pathlib import Path

# ─── Detect repo root ────────────────────────────────────────────────
REPO = Path.home() / "nomad"
if not (REPO / "nomad" / "cli.py").exists():
    print(f"Error: Expected repo at {REPO}/nomad/cli.py")
    sys.exit(1)

CONFIG_INIT = REPO / "nomad" / "config" / "__init__.py"
CLI_PY = REPO / "nomad" / "cli.py"
DYN_CLI = REPO / "nomad" / "dynamics" / "cli_commands.py"

applied = []
skipped = []


def patch(path, old, new, label):
    """Replace old with new in file. old must appear exactly once."""
    text = path.read_text()
    n = text.count(old)
    if n == 0:
        skipped.append(f"{label} -- pattern not found")
        return False
    if n > 1:
        print(f"  WARN [{label}]: found {n} times, replacing all")
    path.write_text(text.replace(old, new))
    applied.append(label)
    print(f"  OK   {label}")
    return True


def patch_all(path, old, new, label):
    """Replace all occurrences of old with new."""
    text = path.read_text()
    n = text.count(old)
    if n == 0:
        skipped.append(f"{label} -- pattern not found")
        return False
    path.write_text(text.replace(old, new))
    applied.append(f"{label} ({n}x)")
    print(f"  OK   {label} ({n} occurrences)")
    return True


# =====================================================================
print("\n[1] config/__init__.py -- add resolve_cluster_name()")
# =====================================================================

HELPER = '''

def resolve_cluster_name(config: dict) -> str:
    """Resolve cluster name from config, trying all known paths.

    Resolution order:
      1. config['clusters'] -- wizard-generated format (first cluster name)
      2. config['cluster_name'] -- legacy top-level key
      3. config['cluster']['name'] -- another legacy path
      4. hostname via socket.gethostname()
      5. 'default' as ultimate fallback
    """
    import socket

    # 1. Wizard format: [clusters.<id>] name = "..."
    clusters = config.get('clusters', {})
    if clusters:
        first_id = next(iter(clusters))
        name = clusters[first_id].get('name', first_id)
        if name:
            return name

    # 2. Legacy top-level key
    name = config.get('cluster_name')
    if name:
        return name

    # 3. Another legacy path
    name = config.get('cluster', {}).get('name')
    if name:
        return name

    # 4. Hostname
    try:
        hostname = socket.gethostname().split('.')[0]
        if hostname:
            return hostname
    except Exception:
        pass

    return 'default'


def resolve_all_cluster_names(config: dict) -> list[str]:
    """Return all cluster names from config.

    For multi-cluster setups returns all names from [clusters.*].
    For single-cluster legacy configs returns a one-element list.
    """
    clusters = config.get('clusters', {})
    if clusters:
        return [c.get('name', cid) for cid, c in clusters.items()]
    return [resolve_cluster_name(config)]
'''

text = CONFIG_INIT.read_text()
if 'def resolve_cluster_name' in text:
    skipped.append("config/helper -- already present")
    print("  SKIP config/helper -- already present")
else:
    text += HELPER
    CONFIG_INIT.write_text(text)
    applied.append("config/helper")
    print("  OK   config/helper")


# =====================================================================
print("\n[2] cli.py collect -- node_state uses helper")
# =====================================================================

patch(CLI_PY,
      "            if 'cluster_name' not in node_state_config:\n"
      "                node_state_config['cluster_name'] = config.get('cluster_name', 'default')",

      "            if 'cluster_name' not in node_state_config:\n"
      "                from nomad.config import resolve_cluster_name\n"
      "                node_state_config['cluster_name'] = resolve_cluster_name(config)",

      "collect/node_state")


# =====================================================================
print("\n[3] cli.py collect -- interactive reads both config paths")
# =====================================================================

patch(CLI_PY,
      '    # Interactive session collector\n'
      '    interactive_config = config.get("interactive", {})\n'
      '    if not collector or "interactive" in collector:\n'
      '        if interactive_config.get("enabled", False):',

      '    # Interactive session collector -- check [interactive] and [collectors.interactive]\n'
      '    interactive_config = config.get("interactive", {})\n'
      '    if not interactive_config:\n'
      '        interactive_config = config.get("collectors", {}).get("interactive", {})\n'
      '    if not collector or "interactive" in collector:\n'
      '        if interactive_config.get("enabled", False):',

      "collect/interactive")


# =====================================================================
print("\n[4] cli.py insights + dyn_summary -- use helper")
# =====================================================================

# This pattern appears 5 times in insights commands and 1 in dyn_summary
patch_all(CLI_PY,
          "    cluster_name = cluster or ctx.obj.get('config', {}).get('cluster', {}).get('name', 'cluster')",

          "    if not cluster:\n"
          "        from nomad.config import resolve_cluster_name\n"
          "        cluster_name = resolve_cluster_name(ctx.obj.get('config', {}))\n"
          "    else:\n"
          "        cluster_name = cluster",

          "insights+dyn/cluster_name")


# =====================================================================
print("\n[5] dynamics/cli_commands.py -- use helper")
# =====================================================================

if DYN_CLI.exists():
    patch(DYN_CLI,
          "        cluster_name = config.get('cluster', {}).get('name', 'cluster')",

          "        from nomad.config import resolve_cluster_name\n"
          "        cluster_name = resolve_cluster_name(config)",

          "dynamics/cluster_name")


# =====================================================================
print("\n[6] Wizard TOML -- explicit per-collector enabled/disabled")
# =====================================================================

# The old block goes from "# Collectors" through the nfs mount_points line.
# We need to match it exactly character by character.

OLD_COLLECTORS = (
    '    # Collectors\n'
    '    coll_list = ["disk", "slurm", "node_state"]\n'
    '    any_gpu = any(c.get("has_gpu") for c in clusters)\n'
    '    any_nfs = any(c.get("has_nfs") for c in clusters)\n'
    '    any_interactive = any(\n'
    '        c.get("has_interactive") for c in clusters)\n'
    '    if any_gpu:\n'
    '        coll_list.append("gpu")\n'
    '    if any_nfs:\n'
    '        coll_list.append("nfs")\n'
    '    if any_interactive:\n'
    '        coll_list.append("interactive")\n'
    '\n'
    '    lines.append("[collectors]")\n'
    "    coll_str = ', '.join(f'\"{{c}}\"' for c in coll_list)\n"
    '    lines.append(f"enabled = [{{coll_str}}]")\n'
    '    lines.append("interval = 60")\n'
    '    lines.append("")\n'
    '\n'
    '    # Filesystems\n'
    '    all_fs = set()\n'
    '    for c in clusters:\n'
    '        all_fs.update(c.get("filesystems", []))\n'
    "    fs_items = ', '.join(f'\"{{f}}\"' for f in sorted(all_fs))\n"
    '    lines.append("[collectors.disk]")\n'
    '    lines.append(f"filesystems = [{{fs_items}}]")\n'
    '    lines.append("")\n'
    '\n'
    '    # SLURM partitions\n'
    '    all_parts = set()\n'
    '    for c in clusters:\n'
    '        if c.get("type", "hpc") == "hpc":\n'
    '            all_parts.update(\n'
    '                c.get("partitions", {{}}).keys())\n'
    '    if all_parts:\n'
    '        parts_items = \', \'.join(\n'
    "            f'\"{{p}}\"' for p in sorted(all_parts))\n"
    '        lines.append("[collectors.slurm]")\n'
    '        lines.append(f"partitions = [{{parts_items}}]")\n'
    '        lines.append("")\n'
    '\n'
    '    if any_gpu:\n'
    '        lines.append("[collectors.gpu]")\n'
    '        lines.append("enabled = true")\n'
    '        lines.append("")\n'
    '\n'
    '    if any_nfs:\n'
    '        lines.append("[collectors.nfs]")\n'
    '        lines.append("mount_points = []")\n'
    '        lines.append("")'
)

# Since f-strings with braces are tricky in Python string matching,
# let's read the file and find the block by its boundaries instead
text = CLI_PY.read_text()

BLOCK_START = '    # Collectors\n    coll_list = ["disk", "slurm", "node_state"]'
BLOCK_END = '        lines.append("mount_points = []")\n        lines.append("")'

if BLOCK_START in text and BLOCK_END in text:
    start_idx = text.index(BLOCK_START)
    end_idx = text.index(BLOCK_END, start_idx) + len(BLOCK_END)
    old_block = text[start_idx:end_idx]

    new_block = (
        '    # Collector feature flags\n'
        '    any_gpu = any(c.get("has_gpu") for c in clusters)\n'
        '    any_nfs = any(c.get("has_nfs") for c in clusters)\n'
        '    any_interactive = any(\n'
        '        c.get("has_interactive") for c in clusters)\n'
        '\n'
        '    lines.append("[collectors]")\n'
        '    lines.append("# Collection interval in seconds")\n'
        '    lines.append("interval = 60")\n'
        '    lines.append("")\n'
        '\n'
        '    # Disk collector\n'
        '    all_fs = set()\n'
        '    for c in clusters:\n'
        '        all_fs.update(c.get("filesystems", []))\n'
        "    fs_items = ', '.join(f'\"{{f}}\"' for f in sorted(all_fs))\n"
        '    lines.append("[collectors.disk]")\n'
        '    lines.append("enabled = true")\n'
        '    lines.append(f"filesystems = [{{fs_items}}]")\n'
        '    lines.append("")\n'
        '\n'
        '    # SLURM collector\n'
        '    all_parts = set()\n'
        '    for c in clusters:\n'
        '        if c.get("type", "hpc") == "hpc":\n'
        '            all_parts.update(\n'
        '                c.get("partitions", {{}}).keys())\n'
        '    lines.append("[collectors.slurm]")\n'
        '    lines.append("enabled = true")\n'
        '    if all_parts:\n'
        '        parts_items = \', \'.join(\n'
        "            f'\"{{p}}\"' for p in sorted(all_parts))\n"
        '        lines.append(f"partitions = [{{parts_items}}]")\n'
        '    lines.append("")\n'
        '\n'
        '    # Node state collector\n'
        '    lines.append("[collectors.node_state]")\n'
        '    lines.append("enabled = true")\n'
        '    lines.append("")\n'
        '\n'
        '    # System stat collectors\n'
        '    lines.append("[collectors.iostat]")\n'
        '    lines.append("enabled = true")\n'
        '    lines.append("")\n'
        '    lines.append("[collectors.mpstat]")\n'
        '    lines.append("enabled = true")\n'
        '    lines.append("")\n'
        '    lines.append("[collectors.vmstat]")\n'
        '    lines.append("enabled = true")\n'
        '    lines.append("")\n'
        '    lines.append("[collectors.job_metrics]")\n'
        '    lines.append("enabled = true")\n'
        '    lines.append("")\n'
        '    lines.append("[collectors.groups]")\n'
        '    lines.append("enabled = true")\n'
        '    lines.append("")\n'
        '\n'
        '    # GPU collector\n'
        '    lines.append("[collectors.gpu]")\n'
        '    lines.append(f"enabled = {{str(any_gpu).lower()}}")\n'
        '    lines.append("")\n'
        '\n'
        '    # NFS collector\n'
        '    lines.append("[collectors.nfs]")\n'
        '    lines.append(f"enabled = {{str(any_nfs).lower()}}")\n'
        '    if any_nfs:\n'
        '        lines.append("mount_points = []")\n'
        '    lines.append("")\n'
        '\n'
        '    # Interactive collector\n'
        '    lines.append("[collectors.interactive]")\n'
        '    lines.append(f"enabled = {{str(any_interactive).lower()}}")\n'
        '    lines.append("")'
    )

    text = text[:start_idx] + new_block + text[end_idx:]
    CLI_PY.write_text(text)
    applied.append("wizard/collectors_explicit")
    print("  OK   wizard/collectors_explicit")
else:
    skipped.append("wizard/collectors_explicit -- boundary markers not found")
    print(f"  SKIP wizard/collectors_explicit -- markers not found")
    print(f"       BLOCK_START found: {BLOCK_START[:50] in text}")
    print(f"       BLOCK_END found: {BLOCK_END[:50] in text}")


# =====================================================================
print("\n[7] Wizard TOML -- [interactive] section when enabled")
# =====================================================================

OLD_INTERACTIVE = (
    '    if any_interactive:\n'
    '        lines.append("[alerts.thresholds.interactive]")\n'
    '        lines.append("idle_sessions_warning = 50")\n'
    '        lines.append("idle_sessions_critical = 100")\n'
    '        lines.append("memory_gb_warning = 32")\n'
    '        lines.append("memory_gb_critical = 64")\n'
    '        lines.append("")'
)

NEW_INTERACTIVE = (
    '    if any_interactive:\n'
    '        lines.append("[alerts.thresholds.interactive]")\n'
    '        lines.append("idle_sessions_warning = 50")\n'
    '        lines.append("idle_sessions_critical = 100")\n'
    '        lines.append("memory_gb_warning = 32")\n'
    '        lines.append("memory_gb_critical = 64")\n'
    '        lines.append("")\n'
    '\n'
    '    # Interactive session monitoring config (top-level, read by collect)\n'
    '    if any_interactive:\n'
    '        lines.append("# ============================================")\n'
    '        lines.append("# INTERACTIVE SESSION MONITORING")\n'
    '        lines.append("# ============================================")\n'
    '        lines.append("")\n'
    '        lines.append("[interactive]")\n'
    '        lines.append("enabled = true")\n'
    '        lines.append("idle_session_hours = 24")\n'
    '        lines.append("memory_hog_mb = 8192")\n'
    '        lines.append("")'
)

if '# Interactive session monitoring config (top-level, read by collect)' not in CLI_PY.read_text():
    patch(CLI_PY, OLD_INTERACTIVE, NEW_INTERACTIVE,
          "wizard/interactive_section")
else:
    skipped.append("wizard/interactive_section -- already applied")
    print("  SKIP wizard/interactive_section -- already applied")


# =====================================================================
print("\n[8] Wizard TOML -- GPU and NFS alert thresholds")
# =====================================================================

OLD_DISK_ALERTS = (
    '    lines.append("[alerts.thresholds.disk]")\n'
    '    lines.append("used_percent_warning = 80")\n'
    '    lines.append("used_percent_critical = 95")\n'
    '    lines.append("")'
)

NEW_DISK_ALERTS = (
    '    lines.append("[alerts.thresholds.disk]")\n'
    '    lines.append("used_percent_warning = 80")\n'
    '    lines.append("used_percent_critical = 95")\n'
    '    lines.append("")\n'
    '\n'
    '    if any_gpu:\n'
    '        lines.append("[alerts.thresholds.gpu]")\n'
    '        lines.append("memory_percent_warning = 90")\n'
    '        lines.append("temperature_warning = 80")\n'
    '        lines.append("temperature_critical = 90")\n'
    '        lines.append("")\n'
    '\n'
    '    if any_nfs:\n'
    '        lines.append("[alerts.thresholds.nfs]")\n'
    '        lines.append("retrans_percent_warning = 1.0")\n'
    '        lines.append("retrans_percent_critical = 5.0")\n'
    '        lines.append("avg_rtt_ms_warning = 50")\n'
    '        lines.append("avg_rtt_ms_critical = 100")\n'
    '        lines.append("")'
)

if 'alerts.thresholds.gpu' not in CLI_PY.read_text():
    patch(CLI_PY, OLD_DISK_ALERTS, NEW_DISK_ALERTS,
          "wizard/gpu_nfs_thresholds")
else:
    skipped.append("wizard/gpu_nfs_thresholds -- already applied")
    print("  SKIP wizard/gpu_nfs_thresholds -- already applied")


# =====================================================================
print("\n[9] Wizard TOML -- remove dead [database] path")
# =====================================================================

patch(CLI_PY,
      '    lines.append("[database]")\n'
      "    lines.append('path = \"nomad.db\"')\n"
      '    lines.append("")',

      '    lines.append("[database]")\n'
      '    lines.append("# Database stored as nomad.db in data_dir")\n'
      '    lines.append("")',

      "wizard/dead_db_path")


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
Next steps on badenpowell:
  1. git diff                    # review all changes
  2. python3 -m pytest tests/ -v # run tests
  3. nomad init --force          # test wizard, inspect TOML
  4. nomad collect --once        # verify collectors start
  5. nomad status                # check cluster_name in output
  6. Bump version in pyproject.toml to 1.3.2
  7. git add -A && git commit -m "fix: unified cluster_name resolution, wizard TOML completeness"
  8. Publish to PyPI
""")
