#!/usr/bin/env python3
"""
NOMAD — Run dynamics signals per-cluster in combined databases

When the DB has multiple source_sites (combined via sync),
run diversity/capacity/niche/resilience per cluster and tag signals.

Apply on badenpowell:
    cd ~/nomad
    python3 patch_dynamics_per_cluster.py
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
print("\n[1] Wrap read_dynamics_signals to run per-cluster")
# =====================================================================
# Replace the function signature and opening to detect multi-site DBs
# and loop per site.

patch(SIGNALS_PY,
    'def read_dynamics_signals(db_path: Path, hours: int = 168) -> list[Signal]:\n'
    '    """Read system dynamics metrics and convert notable findings to signals."""\n'
    '    signals: list[Signal] = []\n'
    '\n'
    '    try:\n'
    '        from nomad.dynamics.diversity import compute_diversity',

    'def _read_dynamics_for_site(\n'
    '        db_path: Path, hours: int, site_label: str = ""\n'
    ') -> list[Signal]:\n'
    '    """Run dynamics for a single site/cluster."""\n'
    '    signals: list[Signal] = []\n'
    '    prefix = f"{site_label}: " if site_label else ""\n'
    '\n'
    '    try:\n'
    '        from nomad.dynamics.diversity import compute_diversity',

    "dynamics/rename_inner_function")


# Now add the new read_dynamics_signals that detects multi-site and loops
# Find the end of the function and add the wrapper after it

patch(SIGNALS_PY,
    'def read_all_signals(db_path: Path, hours: int = 24) -> list[Signal]:',

    'def read_dynamics_signals(db_path: Path, hours: int = 168) -> list[Signal]:\n'
    '    """Read system dynamics metrics per-cluster."""\n'
    '    # Detect multi-site (combined) database\n'
    '    conn = _get_conn(db_path)\n'
    '    sites = []\n'
    '    try:\n'
    '        sites = [r[0] for r in conn.execute(\n'
    '            "SELECT DISTINCT source_site FROM jobs"\n'
    '            " WHERE source_site IS NOT NULL"\n'
    '        ).fetchall()]\n'
    '    except Exception:\n'
    '        pass\n'
    '    conn.close()\n'
    '\n'
    '    if len(sites) > 1:\n'
    '        # Combined DB: run per-cluster using temp DBs\n'
    '        import tempfile\n'
    '        all_signals = []\n'
    '        for site in sites:\n'
    '            try:\n'
    '                # Create temp DB with just this site\'s jobs\n'
    '                tmp = tempfile.NamedTemporaryFile(\n'
    '                    suffix=".db", delete=False)\n'
    '                tmp.close()\n'
    '                tmp_path = Path(tmp.name)\n'
    '                src = _get_conn(db_path)\n'
    '                dst = sqlite3.connect(str(tmp_path))\n'
    '                # Copy jobs for this site\n'
    '                dst.execute(\n'
    '                    "CREATE TABLE jobs AS"\n'
    '                    " SELECT * FROM ("\n'
    '                    "  SELECT * FROM jobs WHERE 0)"\n'
    '                )\n'
    '                # Get column names\n'
    '                cols = [r[1] for r in src.execute(\n'
    '                    "PRAGMA table_info(jobs)"\n'
    '                ).fetchall()]\n'
    '                col_list = ", ".join(cols)\n'
    '                placeholders = ", ".join(\n'
    '                    ["?"] * len(cols))\n'
    '                rows = src.execute(\n'
    '                    f"SELECT {col_list} FROM jobs"\n'
    '                    f" WHERE source_site = ?",\n'
    '                    (site,)\n'
    '                ).fetchall()\n'
    '                if rows:\n'
    '                    dst.execute(\n'
    '                        "DROP TABLE IF EXISTS jobs")\n'
    '                    dst.execute(\n'
    '                        f"CREATE TABLE jobs"\n'
    '                        f" AS SELECT * FROM("\n'
    '                        f"  SELECT {col_list}"\n'
    '                        f"  FROM jobs WHERE 0)"\n'
    '                    )\n'
    '                    # Actually just copy with INSERT\n'
    '                    src2 = sqlite3.connect(str(db_path))\n'
    '                    dst.execute("DROP TABLE IF EXISTS jobs")\n'
    '                    dst.execute("ATTACH DATABASE ? AS src",\n'
    '                                (str(db_path),))\n'
    '                    dst.execute(\n'
    '                        "CREATE TABLE jobs AS"\n'
    '                        " SELECT * FROM src.jobs"\n'
    '                        " WHERE source_site = ?",\n'
    '                        (site,))\n'
    '                    dst.execute("DETACH DATABASE src")\n'
    '                    dst.commit()\n'
    '                sigs = _read_dynamics_for_site(\n'
    '                    tmp_path, hours, site)\n'
    '                all_signals.extend(sigs)\n'
    '                src.close()\n'
    '                dst.close()\n'
    '                tmp_path.unlink(missing_ok=True)\n'
    '            except Exception:\n'
    '                try:\n'
    '                    tmp_path.unlink(missing_ok=True)\n'
    '                except Exception:\n'
    '                    pass\n'
    '        return all_signals\n'
    '    else:\n'
    '        # Single-site DB: run directly\n'
    '        return _read_dynamics_for_site(\n'
    '            db_path, hours)\n'
    '\n'
    '\n'
    'def read_all_signals(db_path: Path, hours: int = 24) -> list[Signal]:',

    "dynamics/per_cluster_wrapper")


# Now fix the signal details in _read_dynamics_for_site to include prefix
# The prefix is passed in but needs to be used in each signal's detail

patch(SIGNALS_PY,
    '                detail=div.fragility_detail,',
    '                detail=prefix + div.fragility_detail,',
    "dynamics/prefix_fragility")

patch(SIGNALS_PY,
    '                detail=(\n'
    '                    f"Workload diversity is declining "\n'
    '                    f"(slope: {div.trend_slope:.4f}/window). "\n'
    '                    f"Current H\'={div.current.shannon_h:.3f}."',

    '                detail=(\n'
    '                    f"{prefix}Workload diversity is declining "\n'
    '                    f"(slope: {div.trend_slope:.4f}/window). "\n'
    '                    f"Current H\'={div.current.shannon_h:.3f}."',

    "dynamics/prefix_declining")

patch(SIGNALS_PY,
    '                detail=(\n'
    '                    f"{bc.label} is the binding constraint at "',

    '                detail=(\n'
    '                    f"{prefix}{bc.label} is the binding constraint at "',

    "dynamics/prefix_capacity")

patch(SIGNALS_PY,
    '                detail=(\n'
    '                    f"{bc.label} projected to reach saturation "',

    '                detail=(\n'
    '                    f"{prefix}{bc.label} projected to reach saturation "',

    "dynamics/prefix_saturation")

patch(SIGNALS_PY,
    '                detail=(\n'
    '                    f"{high_count} high-overlap group pair(s) detected. "',

    '                detail=(\n'
    '                    f"{prefix}{high_count} high-overlap group pair(s) detected. "',

    "dynamics/prefix_niche")


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
