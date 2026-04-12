#!/usr/bin/env python3
"""
NOMAD — Fix disk signals and alert detail display

1. read_disk_signals: fallback to filesystems table when storage_state is empty
2. read_alert_signals: include actual alert messages in the signal detail

Apply on badenpowell:
    cd ~/nomad
    python3 patch_disk_alert_signals.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
SIGNALS_PY = REPO / "nomad" / "insights" / "signals.py"

if not SIGNALS_PY.exists():
    print(f"Error: {SIGNALS_PY} not found")
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
print("\n[1] Alert signals: include actual alert messages")
# =====================================================================

patch(SIGNALS_PY,
    '        if unresolved:\n'
    '            # Group by severity\n'
    '            crit = [r for r in unresolved if r["severity"] == "critical"]\n'
    '            warn = [r for r in unresolved if r["severity"] == "warning"]\n'
    '\n'
    '            signals.append(Signal(\n'
    '                signal_type=SignalType.ALERT,\n'
    '                severity=Severity.CRITICAL if crit else Severity.WARNING,\n'
    '                title="active_alerts",\n'
    '                detail=f"{len(unresolved)} active alerts ({len(crit)} critical, {len(warn)} warning)",\n'
    '                metrics={\n'
    '                    "total_active": len(unresolved),\n'
    '                    "critical": len(crit),\n'
    '                    "warning": len(warn),\n'
    '                    "resolved_recently": len(resolved),\n'
    '                },\n'
    '            ))',

    '        if unresolved:\n'
    '            # Group by severity\n'
    '            crit = [r for r in unresolved if r["severity"] == "critical"]\n'
    '            warn = [r for r in unresolved if r["severity"] == "warning"]\n'
    '\n'
    '            # Build detail with actual alert messages\n'
    '            alert_msgs = []\n'
    '            for a in unresolved:\n'
    '                alert_msgs.append(a["message"])\n'
    '\n'
    '            detail = f"{len(unresolved)} active alert(s)"\n'
    '            if alert_msgs:\n'
    '                detail += ": " + "; ".join(\n'
    '                    alert_msgs[:5])  # Limit to 5\n'
    '                if len(alert_msgs) > 5:\n'
    '                    detail += f" (+{len(alert_msgs)-5} more)"\n'
    '\n'
    '            signals.append(Signal(\n'
    '                signal_type=SignalType.ALERT,\n'
    '                severity=Severity.CRITICAL if crit else Severity.WARNING,\n'
    '                title="active_alerts",\n'
    '                detail=detail,\n'
    '                metrics={\n'
    '                    "total_active": len(unresolved),\n'
    '                    "critical": len(crit),\n'
    '                    "warning": len(warn),\n'
    '                    "resolved_recently": len(resolved),\n'
    '                    "messages": alert_msgs[:10],\n'
    '                },\n'
    '            ))',

    "alerts/include_messages")


# =====================================================================
print("\n[2] Disk signals: fallback to filesystems table")
# =====================================================================
# After the storage_state query, add a fallback that reads from
# the filesystems table if no storage_state data was found.

patch(SIGNALS_PY,
    "def read_disk_signals(db_path: Path, hours: int = 6) -> list[Signal]:\n"
    '    """Check storage filesystem trends."""\n'
    "    signals: list[Signal] = []\n"
    "    conn = _get_conn(db_path)\n"
    "    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()\n"
    "\n"
    "    try:\n"
    "        # Get latest storage readings per server\n"
    "        rows = conn.execute(",

    "def read_disk_signals(db_path: Path, hours: int = 6) -> list[Signal]:\n"
    '    """Check storage filesystem trends."""\n'
    "    signals: list[Signal] = []\n"
    "    conn = _get_conn(db_path)\n"
    "    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()\n"
    "\n"
    "    # Try filesystems table first (from DiskCollector)\n"
    "    try:\n"
    "        fs_rows = conn.execute(\"\"\"\n"
    "            SELECT f.path, f.used_percent,\n"
    "                   (f.total_bytes/1073741824.0) as total_gb,\n"
    "                   (f.used_bytes/1073741824.0) as used_gb,\n"
    "                   (f.available_bytes/1073741824.0) as free_gb,\n"
    "                   f.days_until_full,\n"
    "                   f.first_derivative,\n"
    "                   f.timestamp,\n"
    "                   f.source_site\n"
    "            FROM filesystems f\n"
    "            INNER JOIN (\n"
    "                SELECT path,\n"
    "                       COALESCE(source_site, 'local') as ss,\n"
    "                       MAX(timestamp) as max_ts\n"
    "                FROM filesystems\n"
    "                GROUP BY path, COALESCE(source_site, 'local')\n"
    "            ) latest ON f.path = latest.path\n"
    "                AND f.timestamp = latest.max_ts\n"
    "                AND COALESCE(f.source_site, 'local') = latest.ss\n"
    "        \"\"\").fetchall()\n"
    "    except Exception:\n"
    "        try:\n"
    "            fs_rows = conn.execute(\"\"\"\n"
    "                SELECT f.path, f.used_percent,\n"
    "                    (f.total_bytes/1073741824.0) as total_gb,\n"
    "                    (f.used_bytes/1073741824.0) as used_gb,\n"
    "                    (f.available_bytes/1073741824.0) as free_gb,\n"
    "                    f.days_until_full,\n"
    "                    f.first_derivative,\n"
    "                    f.timestamp,\n"
    "                    NULL as source_site\n"
    "                FROM filesystems f\n"
    "                INNER JOIN (\n"
    "                    SELECT path, MAX(timestamp) as max_ts\n"
    "                    FROM filesystems GROUP BY path\n"
    "                ) latest ON f.path = latest.path\n"
    "                    AND f.timestamp = latest.max_ts\n"
    "            \"\"\").fetchall()\n"
    "        except Exception:\n"
    "            fs_rows = []\n"
    "\n"
    "    for r in fs_rows:\n"
    "        usage = r['used_percent']\n"
    "        site = r['source_site'] or 'local'\n"
    "        label = f\"{site}:{r['path']}\"\n"
    "        if usage >= 90:\n"
    "            sev = Severity.CRITICAL\n"
    "        elif usage >= 80:\n"
    "            sev = Severity.WARNING\n"
    "        elif usage >= 70:\n"
    "            sev = Severity.NOTICE\n"
    "        else:\n"
    "            continue\n"
    "\n"
    "        detail = (f\"{label} at {usage:.0f}% \"\n"
    "                  f\"({r['free_gb']:.1f} GB free)\")\n"
    "\n"
    "        # Add fill rate info if available\n"
    "        if r['days_until_full'] and r['days_until_full'] > 0:\n"
    "            detail += (f\". Projected full in \"\n"
    "                       f\"{r['days_until_full']:.0f} days.\")\n"
    "        if r['first_derivative'] and r['first_derivative'] > 0:\n"
    "            gb_per_day = (r['first_derivative']\n"
    "                          * 86400 / 1073741824.0)\n"
    "            if gb_per_day > 0.1:\n"
    "                detail += (f\" Fill rate: \"\n"
    "                           f\"{gb_per_day:.1f} GB/day.\")\n"
    "\n"
    "        signals.append(Signal(\n"
    "            signal_type=SignalType.DISK,\n"
    "            severity=sev,\n"
    "            title='filesystem_usage',\n"
    "            detail=detail,\n"
    "            metrics={\n"
    "                'server': label,\n"
    "                'usage_pct': usage,\n"
    "                'avail_gb': r['free_gb'],\n"
    "                'free_gb': r['free_gb'],\n"
    "                'total_gb': r['total_gb'],\n"
    "            },\n"
    "            affected_entities=[label],\n"
    "            tags={'server': site, 'path': r['path']},\n"
    "        ))\n"
    "\n"
    "    try:\n"
    "        # Also check storage_state (ZFS/NAS)\n"
    "        rows = conn.execute(",

    "disk/filesystems_fallback")


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
