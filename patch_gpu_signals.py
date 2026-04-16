#!/usr/bin/env python3
"""
Extend GPU signals and narrative templates for Idea 13.

Changes:
  1. nomad/insights/signals.py — extend read_gpu_signals() with three new
     signal types from gpu_stats and gpu_health:
       - gpu_util_gap (Real Util vs nvidia-smi divergence)
       - gpu_workload_pattern (dominant workload class)
       - gpu_hardware_health (WARN/HOT/CRIT from gpu_health table)

  2. nomad/insights/templates.py — add three narrative functions and
     register them in _TEMPLATE_MAP.
"""
import sys

ok = True

def patch(filepath, old, new, name):
    global ok
    text = open(filepath).read()
    if old not in text:
        print(f'SKIP (not found): {name}')
        ok = False
        return
    if text.count(old) > 1:
        print(f'ERROR (ambiguous): {name}')
        ok = False
        return
    open(filepath, 'w').write(text.replace(old, new))
    print(f'OK: {name}')

# -----------------------------------------------------------------------
# PATCH 1: signals.py — extend read_gpu_signals
# -----------------------------------------------------------------------

OLD_GPU_SIGNALS = '''# ── GPU signals ──────────────────────────────────────────────────────────
def read_gpu_signals(db_path: Path, hours: int = 24) -> list[Signal]:
    """Analyze GPU utilization and memory patterns."""
    signals: list[Signal] = []
    conn = _get_conn(db_path)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    try:
        # GPU utilization from jobs requesting GPUs
        gpu_jobs = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN state = 'FAILED' THEN 1 ELSE 0 END) as failed,
                   SUM(CASE WHEN state = 'OUT_OF_MEMORY' THEN 1 ELSE 0 END) as oom,
                   AVG(CAST(req_gpus AS REAL)) as avg_gpus
            FROM jobs
            WHERE end_time >= ? AND req_gpus > 0
        """, (cutoff,)).fetchone()
        if gpu_jobs and gpu_jobs["total"] > 0:
            total = gpu_jobs["total"]
            failed = gpu_jobs["failed"] or 0
            oom = gpu_jobs["oom"] or 0
            fail_rate = (failed / total) * 100
            if fail_rate > 20:
                signals.append(Signal(
                    signal_type=SignalType.GPU,
                    severity=Severity.WARNING,
                    title="gpu_job_failure_rate",
                    detail=f"{fail_rate:.0f}% of GPU jobs failed in the last {hours}h ({failed}/{total})",
                    metrics={"total_gpu_jobs": total, "failed": failed, "fail_rate": fail_rate},
                ))
            if oom > 0:
                signals.append(Signal(
                    signal_type=SignalType.GPU,
                    severity=Severity.WARNING if oom > 2 else Severity.NOTICE,
                    title="gpu_oom",
                    detail=f"{oom} GPU jobs ran out of memory — possible VRAM limitation",
                    metrics={"gpu_oom_count": oom, "total_gpu_jobs": total},
                ))
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return signals'''

NEW_GPU_SIGNALS = '''# ── GPU signals ──────────────────────────────────────────────────────────
def read_gpu_signals(db_path: Path, hours: int = 24) -> list[Signal]:
    """Analyze GPU utilization, workload patterns, and hardware health."""
    signals: list[Signal] = []
    conn = _get_conn(db_path)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    # ── Job-level GPU signals (from jobs table) ──────────────────────────
    try:
        gpu_jobs = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN state = 'FAILED' THEN 1 ELSE 0 END) as failed,
                   SUM(CASE WHEN state = 'OUT_OF_MEMORY' THEN 1 ELSE 0 END) as oom,
                   AVG(CAST(req_gpus AS REAL)) as avg_gpus
            FROM jobs
            WHERE end_time >= ? AND req_gpus > 0
        """, (cutoff,)).fetchone()
        if gpu_jobs and gpu_jobs["total"] > 0:
            total = gpu_jobs["total"]
            failed = gpu_jobs["failed"] or 0
            oom = gpu_jobs["oom"] or 0
            fail_rate = (failed / total) * 100
            if fail_rate > 20:
                signals.append(Signal(
                    signal_type=SignalType.GPU,
                    severity=Severity.WARNING,
                    title="gpu_job_failure_rate",
                    detail=f"{fail_rate:.0f}% of GPU jobs failed in the last {hours}h ({failed}/{total})",
                    metrics={"total_gpu_jobs": total, "failed": failed, "fail_rate": fail_rate},
                ))
            if oom > 0:
                signals.append(Signal(
                    signal_type=SignalType.GPU,
                    severity=Severity.WARNING if oom > 2 else Severity.NOTICE,
                    title="gpu_oom",
                    detail=f"{oom} GPU jobs ran out of memory — possible VRAM limitation",
                    metrics={"gpu_oom_count": oom, "total_gpu_jobs": total},
                ))
    except sqlite3.OperationalError:
        pass

    # ── Real Util vs nvidia-smi gap (from gpu_stats, DCGM only) ─────────
    try:
        gap_rows = conn.execute("""
            SELECT node_name,
                   AVG(gpu_util_percent) as avg_smi,
                   AVG(real_util_pct) as avg_real,
                   AVG(gpu_util_percent - real_util_pct) as avg_gap,
                   COUNT(*) as samples
            FROM gpu_stats
            WHERE timestamp >= ?
              AND real_util_pct IS NOT NULL
              AND gpu_util_percent > 30
            GROUP BY node_name
            HAVING avg_gap > 20 AND samples >= 3
            ORDER BY avg_gap DESC
        """, (cutoff,)).fetchall()

        for row in gap_rows:
            gap = row["avg_gap"] or 0
            smi = row["avg_smi"] or 0
            real = row["avg_real"] or 0
            node = row["node_name"]
            sev = Severity.WARNING if gap > 35 else Severity.NOTICE
            signals.append(Signal(
                signal_type=SignalType.GPU,
                severity=sev,
                title="gpu_util_gap",
                detail=(
                    f"{node}: nvidia-smi reports {smi:.0f}% but Real Util is "
                    f"{real:.0f}% (gap: {gap:.0f} pts)"
                ),
                metrics={
                    "node": node,
                    "avg_smi_util": round(smi, 1),
                    "avg_real_util": round(real, 1),
                    "avg_gap": round(gap, 1),
                    "samples": row["samples"],
                },
                affected_entities=[node],
                tags={"node": node},
            ))
    except sqlite3.OperationalError:
        pass

    # ── Workload pattern signals (from gpu_stats) ────────────────────────
    try:
        wl_rows = conn.execute("""
            SELECT node_name, workload_class, COUNT(*) as n
            FROM gpu_stats
            WHERE timestamp >= ?
              AND workload_class IS NOT NULL
            GROUP BY node_name, workload_class
            ORDER BY node_name, n DESC
        """, (cutoff,)).fetchall()

        # Find dominant workload per node
        node_dominant: dict[str, tuple[str, int]] = {}
        node_total: dict[str, int] = {}
        for row in wl_rows:
            node = row["node_name"]
            node_total[node] = node_total.get(node, 0) + row["n"]
            if node not in node_dominant:
                node_dominant[node] = (row["workload_class"], row["n"])

        for node, (wclass, count) in node_dominant.items():
            total_n = node_total.get(node, count)
            pct = (count / total_n * 100) if total_n > 0 else 0

            # Signal for memory-bound workloads (actionable inefficiency)
            if wclass == "memory-bound" and pct >= 50:
                signals.append(Signal(
                    signal_type=SignalType.GPU,
                    severity=Severity.NOTICE,
                    title="gpu_workload_pattern",
                    detail=f"{node}: memory-bound workload dominant ({pct:.0f}% of samples)",
                    metrics={
                        "node": node,
                        "workload_class": wclass,
                        "dominant_pct": round(pct, 1),
                        "pattern_type": "memory-bound",
                    },
                    affected_entities=[node],
                    tags={"node": node, "workload": wclass},
                ))
            # Signal for sustained idle GPUs
            elif wclass == "idle" and pct >= 70:
                signals.append(Signal(
                    signal_type=SignalType.GPU,
                    severity=Severity.NOTICE,
                    title="gpu_workload_pattern",
                    detail=f"{node}: GPU idle {pct:.0f}% of the time in the last {hours}h",
                    metrics={
                        "node": node,
                        "workload_class": wclass,
                        "dominant_pct": round(pct, 1),
                        "pattern_type": "idle",
                    },
                    affected_entities=[node],
                    tags={"node": node, "workload": wclass},
                ))
            # Informational: sustained high-value workloads
            elif wclass in ("tensor-heavy compute", "FP64 / HPC compute") and pct >= 60:
                signals.append(Signal(
                    signal_type=SignalType.GPU,
                    severity=Severity.INFO,
                    title="gpu_workload_pattern",
                    detail=f"{node}: {wclass} dominant ({pct:.0f}% of samples)",
                    metrics={
                        "node": node,
                        "workload_class": wclass,
                        "dominant_pct": round(pct, 1),
                        "pattern_type": "productive",
                    },
                    affected_entities=[node],
                    tags={"node": node, "workload": wclass},
                ))
    except sqlite3.OperationalError:
        pass

    # ── Hardware health signals (from gpu_health) ────────────────────────
    try:
        health_rows = conn.execute("""
            SELECT node, gpu_id, health_status,
                   MAX(pcie_replay_rate_per_sec) as max_pcie_rate,
                   MAX(ecc_uncorrectable_total) as max_ecc_unc,
                   MAX(row_remap_failure) as remap_fail,
                   MAX(temperature_c) as max_temp
            FROM gpu_health
            WHERE timestamp >= ?
              AND health_status != 'OK'
            GROUP BY node, gpu_id
            ORDER BY
                CASE health_status
                    WHEN 'CRIT' THEN 3
                    WHEN 'HOT'  THEN 2
                    WHEN 'WARN' THEN 1
                    ELSE 0
                END DESC
        """, (cutoff,)).fetchall()

        for row in health_rows:
            node = row["node"]
            gpu_id = row["gpu_id"]
            status = row["health_status"]

            if status == "CRIT":
                sev = Severity.CRITICAL
                if row["remap_fail"]:
                    reason = "row remap failure — GPU memory permanently degraded"
                elif row["max_ecc_unc"]:
                    reason = f"{row['max_ecc_unc']} uncorrectable ECC error(s)"
                else:
                    reason = "critical hardware condition"
                detail = f"{node} GPU {gpu_id}: {reason}. Remove from production."
            elif status == "HOT":
                sev = Severity.WARNING
                detail = (
                    f"{node} GPU {gpu_id}: temperature at or above warning threshold"
                    + (f" ({row['max_temp']}°C)" if row.get("max_temp") else "")
                )
            else:  # WARN
                sev = Severity.NOTICE
                rate = row["max_pcie_rate"] or 0
                detail = (
                    f"{node} GPU {gpu_id}: PCIe replay errors detected "
                    f"({rate:.3f}/s) — monitor link health"
                )

            signals.append(Signal(
                signal_type=SignalType.GPU,
                severity=sev,
                title="gpu_hardware_health",
                detail=detail,
                metrics={
                    "node": node,
                    "gpu_id": gpu_id,
                    "health_status": status,
                    "pcie_replay_rate": row["max_pcie_rate"] or 0,
                    "ecc_uncorrectable": row["max_ecc_unc"] or 0,
                    "row_remap_failure": row["remap_fail"] or 0,
                },
                affected_entities=[f"{node}:gpu{gpu_id}"],
                tags={"node": node, "gpu_id": str(gpu_id)},
            ))
    except sqlite3.OperationalError:
        pass

    finally:
        conn.close()
    return signals'''

# -----------------------------------------------------------------------
# PATCH 2: templates.py — add three narrative functions
# -----------------------------------------------------------------------

OLD_TEMPLATE_ANCHOR = '''def narrate_gpu_failure_rate(sig: Signal) -> str:'''

NEW_TEMPLATE_ANCHOR = '''def narrate_gpu_util_gap(sig: Signal) -> str:
    m = sig.metrics
    node = m["node"]
    smi = m["avg_smi_util"]
    real = m["avg_real_util"]
    gap = m["avg_gap"]
    pattern_hint = ""
    if gap > 35:
        pattern_hint = (
            " The pipeline stages show significant idle time despite kernel "
            "activity — consider larger batch sizes, kernel fusion, or "
            "data prefetching."
        )
    return (
        f"{node} shows a {gap:.0f}-point gap between nvidia-smi utilization "
        f"({smi:.0f}%) and Real Utilization ({real:.0f}%). "
        f"The GPU appears busy but the compute pipeline is underused."
        f"{pattern_hint}"
    )


def narrate_gpu_workload_pattern(sig: Signal) -> str:
    m = sig.metrics
    node = m["node"]
    wclass = m["workload_class"]
    pct = m["dominant_pct"]
    ptype = m.get("pattern_type", "")

    if ptype == "memory-bound":
        return (
            f"{node} has been running memory-bound workloads {pct:.0f}% of the time. "
            f"GPU compute pipeline is underutilized relative to memory bandwidth. "
            f"Possible improvements: increase batch size, optimize data layout, "
            f"or use prefetching to overlap compute and data transfer."
        )
    if ptype == "idle":
        return (
            f"{node} GPU has been idle {pct:.0f}% of the sampled window. "
            f"Consider whether allocated jobs are actually using the GPU, "
            f"or whether this node could serve additional workloads."
        )
    # productive
    return (
        f"{node} is running {wclass} workloads {pct:.0f}% of the time — "
        f"GPU resources are being used effectively."
    )


def narrate_gpu_hardware_health(sig: Signal) -> str:
    m = sig.metrics
    node = m["node"]
    gpu_id = m["gpu_id"]
    status = m["health_status"]

    if status == "CRIT":
        remap = m.get("row_remap_failure", 0)
        ecc = m.get("ecc_uncorrectable", 0)
        if remap:
            return (
                f"{node} GPU {gpu_id} has a row remap failure — HBM memory is "
                f"permanently degraded. This GPU should be removed from production "
                f"and scheduled for replacement."
            )
        if ecc:
            return (
                f"{node} GPU {gpu_id} has {ecc} uncorrectable ECC error(s). "
                f"Memory integrity cannot be guaranteed. Remove from production "
                f"and investigate hardware."
            )
        return f"{node} GPU {gpu_id} is in a critical hardware state. Investigate immediately."

    if status == "HOT":
        return (
            f"{node} GPU {gpu_id} temperature is at or above the warning threshold. "
            f"Check cooling, airflow, and workload intensity. Sustained high "
            f"temperatures accelerate hardware degradation."
        )

    # WARN — PCIe
    rate = m.get("pcie_replay_rate", 0)
    return (
        f"{node} GPU {gpu_id} is logging PCIe replay errors ({rate:.3f}/s). "
        f"This indicates link instability — check the PCIe slot, riser card, "
        f"or cable. Left unaddressed, this typically escalates to link failure."
    )


def narrate_gpu_failure_rate(sig: Signal) -> str:'''

# -----------------------------------------------------------------------
# PATCH 3: templates.py — add entries to _TEMPLATE_MAP
# -----------------------------------------------------------------------

OLD_MAP_GPU = '''    "gpu_job_failure_rate": narrate_gpu_failure_rate,
    "gpu_oom": narrate_gpu_oom,'''

NEW_MAP_GPU = '''    "gpu_job_failure_rate": narrate_gpu_failure_rate,
    "gpu_oom": narrate_gpu_oom,
    "gpu_util_gap": narrate_gpu_util_gap,
    "gpu_workload_pattern": narrate_gpu_workload_pattern,
    "gpu_hardware_health": narrate_gpu_hardware_health,'''

# -----------------------------------------------------------------------
# Apply
# -----------------------------------------------------------------------
patches = [
    ('nomad/insights/signals.py',  'read_gpu_signals extended',  OLD_GPU_SIGNALS,      NEW_GPU_SIGNALS),
    ('nomad/insights/templates.py', 'GPU narrative functions',    OLD_TEMPLATE_ANCHOR,  NEW_TEMPLATE_ANCHOR),
    ('nomad/insights/templates.py', '_TEMPLATE_MAP GPU entries',  OLD_MAP_GPU,          NEW_MAP_GPU),
]

for filepath, name, old, new in patches:
    patch(filepath, old, new, name)

sys.exit(0 if ok else 1)
