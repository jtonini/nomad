#!/usr/bin/env python3
"""
NOMAD fix — Insights db path + health classification

1. All CLI commands that resolve db_path now use get_db_path(config)
   instead of broken hardcoded path to ~/.config/nomad/nomad.db
2. Insight Engine: diversity_fragility downgraded from WARNING to NOTICE
   so it doesn't escalate overall health to "degraded"

Apply on badenpowell:
    cd ~/nomad
    python3 patch_insights_fix.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
CLI_PY = REPO / "nomad" / "cli.py"
SIGNALS_PY = REPO / "nomad" / "insights" / "signals.py"

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
print("\n[1] Fix all CLI commands: use get_db_path(config) for db resolution")
# =====================================================================

# Replace the broken 3-line pattern everywhere it appears.
# Old pattern:
#   db_path = config.get('database', {}).get('path')
#   if not db_path:
#       db_path = str(Path.home() / '.config' / 'nomad' / 'nomad.db')
#
# New pattern:
#   db_path = str(get_db_path(config))

patch_all(CLI_PY,
    "        db_path = config.get('database', {}).get('path')\n"
    "        if not db_path:\n"
    "            db_path = str(Path.home() / '.config' / 'nomad' / 'nomad.db')",

    "        db_path = str(get_db_path(config))",

    "cli/insights_db_path")

# Also fix the 6th variant with different fallback
patch(CLI_PY,
    "        db_path = config.get('database', {}).get('path')\n"
    "        if not db_path:\n"
    "            default_db = Path.home() / '.config' / 'nomad' / 'nomad.db'\n"
    "            if default_db.exists():\n"
    "                db_path = str(default_db)\n"
    "            else:\n"
    "                click.echo(\"Error: No database found. Use --db to specify path.\", err=True)\n"
    "                raise SystemExit(1)",

    "        db_path = str(get_db_path(config))",

    "cli/export_db_path")


# =====================================================================
print("\n[2] Fix health classification: diversity is NOTICE, not WARNING")
# =====================================================================

if SIGNALS_PY.exists():
    patch(SIGNALS_PY,
        '        if div.fragility_warning:\n'
        '            signals.append(Signal(\n'
        '                signal_type=SignalType.DYNAMICS,\n'
        '                severity=Severity.WARNING,\n'
        '                title="diversity_fragility",',

        '        if div.fragility_warning:\n'
        '            signals.append(Signal(\n'
        '                signal_type=SignalType.DYNAMICS,\n'
        '                severity=Severity.NOTICE,\n'
        '                title="diversity_fragility",',

        "insights/diversity_not_degraded")
else:
    skipped.append("signals.py not found")


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
