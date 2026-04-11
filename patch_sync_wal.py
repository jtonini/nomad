#!/usr/bin/env python3
"""
NOMAD fix — Sync merge fails on WAL-mode databases

The SCP copies .db but not .db-wal and .db-shm files. WAL-mode
databases need all three to be readable. Fix: also SCP the WAL
files, then checkpoint before ATTACH.

Apply on badenpowell:
    cd ~/nomad
    python3 patch_sync_wal.py
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
print("\n[1] SCP also copies WAL and SHM files")
# =====================================================================

patch(CLI_PY,
    '        scp_cmd = ["scp", "-o", "ConnectTimeout=10",\n'
    '                    "-o", "BatchMode=yes"]\n'
    '        if ssh_key:\n'
    '            scp_cmd += ["-i", ssh_key]\n'
    '        scp_cmd.append(f"{user}@{host}:{remote_db}")\n'
    '        scp_cmd.append(str(local_copy))\n'
    '\n'
    '        try:\n'
    '            result = sp.run(scp_cmd, capture_output=True,\n'
    '                            text=True, timeout=60)',

    '        scp_base = ["scp", "-o", "ConnectTimeout=10",\n'
    '                     "-o", "BatchMode=yes"]\n'
    '        if ssh_key:\n'
    '            scp_base += ["-i", ssh_key]\n'
    '\n'
    '        # Copy main DB + WAL/SHM files (WAL-mode databases need all three)\n'
    '        scp_cmd = scp_base + [\n'
    '            f"{user}@{host}:{remote_db}",\n'
    '            str(local_copy)]\n'
    '\n'
    '        try:\n'
    '            result = sp.run(scp_cmd, capture_output=True,\n'
    '                            text=True, timeout=60)\n'
    '\n'
    '            # Also try to copy WAL and SHM (may not exist if not in WAL mode)\n'
    '            if result.returncode == 0:\n'
    '                for suffix in [\"-wal\", \"-shm\"]:\n'
    '                    sp.run(\n'
    '                        scp_base + [\n'
    '                            f\"{user}@{host}:{remote_db}{suffix}\",\n'
    '                            str(local_copy) + suffix],\n'
    '                        capture_output=True, text=True, timeout=30)',

    "sync/scp_wal_files")


# =====================================================================
print("\n[2] Checkpoint WAL before ATTACH during merge")
# =====================================================================

patch(CLI_PY,
    '        try:\n'
    '            combined.execute(\n'
    '                f"ATTACH DATABASE ? AS source", (str(db_path),))',

    '        try:\n'
    '            # Checkpoint WAL on the cached copy before attaching\n'
    '            try:\n'
    '                _tmp = sqlite3.connect(str(db_path))\n'
    '                _tmp.execute("PRAGMA wal_checkpoint(TRUNCATE)")\n'
    '                _tmp.close()\n'
    '            except Exception:\n'
    '                pass\n'
    '\n'
    '            combined.execute(\n'
    '                f"ATTACH DATABASE ? AS source", (str(db_path),))',

    "sync/checkpoint_before_attach")


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
