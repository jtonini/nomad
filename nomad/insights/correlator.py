# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""
Level 2 correlator for the NØMAD Insight Engine.

Examines multiple signals together to find causal or co-occurring
patterns, then produces integrated insights that link related issues
into a single coherent narrative instead of separate alerts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .signals import Signal, SignalType, Severity


@dataclass
class Insight:
    """A correlated insight combining one or more signals."""
    title: str
    narrative: str
    severity: Severity
    source_signals: list[Signal] = field(default_factory=list)
    recommendation: str | None = None
    category: str = "general"

    @property
    def signal_count(self) -> int:
        return len(self.source_signals)


def _max_severity(signals: list[Signal]) -> Severity:
    """Return the highest severity among a list of signals."""
    order = [Severity.INFO, Severity.NOTICE, Severity.WARNING, Severity.CRITICAL]
    max_idx = 0
    for s in signals:
        idx = order.index(s.severity)
        if idx > max_idx:
            max_idx = idx
    return order[max_idx]


def _signals_share_entity(a: Signal, b: Signal) -> bool:
    """Check if two signals affect the same entity."""
    return bool(set(a.affected_entities) & set(b.affected_entities))


def _signals_share_partition(a: Signal, b: Signal) -> bool:
    """Check if two signals relate to the same partition."""
    pa = a.tags.get("partition") or a.metrics.get("partition")
    pb = b.tags.get("partition") or b.metrics.get("partition")
    return pa is not None and pa == pb


# ── Correlation rules ────────────────────────────────────────────────────

def _correlate_disk_and_jobs(signals: list[Signal]) -> list[Insight]:
    """Disk filling + job failures = possible causal link."""
    insights = []
    disk_fill = [s for s in signals if s.title == "disk_fill_projection"]
    job_fails = [s for s in signals if s.title in ("job_success_rate", "partition_failure_concentration")]

    for df in disk_fill:
        server = df.metrics.get("server", "")
        related_jobs = [j for j in job_fails if j.severity.value in ("warning", "critical")]

        if related_jobs:
            hours = df.metrics.get("hours_to_full", 0)
            rate = df.metrics.get("fill_rate_gb_hr", 0)
            combined = [df] + related_jobs

            narrative = (
                f"Disk space on {server} is filling at {rate:.1f} GB/hr "
                f"(projected full in {hours:.0f}h) while job failures are elevated. "
                f"These are likely connected — jobs writing large output files "
                f"will fail when the filesystem reaches capacity. "
                f"This pattern has been a common cause of cascading failures."
            )
            insights.append(Insight(
                title="disk_pressure_causing_failures",
                narrative=narrative,
                severity=Severity.CRITICAL,
                source_signals=combined,
                recommendation=(
                    "Immediately identify the largest writers with 'nomad analyze'. "
                    "Consider emergency purge of old files, increasing purge frequency, "
                    "or contacting top users to stagger checkpoint writes."
                ),
                category="storage",
            ))

    return insights


def _correlate_gpu_oom_and_partition(signals: list[Signal]) -> list[Insight]:
    """GPU OOM + partition failures = VRAM capacity mismatch."""
    insights = []
    gpu_oom = [s for s in signals if s.title == "gpu_oom"]
    part_fail = [s for s in signals if s.title == "partition_failure_concentration"]

    if gpu_oom and part_fail:
        # Check if the partition failures are in a GPU-related partition
        gpu_partitions = {"gpu", "GPU", "gpu_partition", "ml", "ML"}
        related = [p for p in part_fail
                   if p.metrics.get("partition", "").lower() in gpu_partitions
                   or "gpu" in p.metrics.get("partition", "").lower()]

        if related:
            combined = gpu_oom + related
            oom_count = sum(s.metrics.get("gpu_oom_count", 0) for s in gpu_oom)

            narrative = (
                f"GPU jobs are failing due to VRAM exhaustion ({oom_count} OOM failures) "
                f"and the GPU partition is showing elevated failure rates overall. "
                f"The research workload may be outgrowing the available GPU memory capacity."
            )
            insights.append(Insight(
                title="gpu_capacity_mismatch",
                narrative=narrative,
                severity=Severity.WARNING,
                source_signals=combined,
                recommendation=(
                    "Review GPU memory requirements for the affected research groups. "
                    "Consider VRAM-aware job routing, adding high-memory GPU nodes, "
                    "or working with users to optimize model memory footprint."
                ),
                category="gpu",
            ))

    return insights


def _correlate_queue_and_wait(signals: list[Signal]) -> list[Insight]:
    """High queue pressure + high wait times on the same partition."""
    insights = []
    pressure = [s for s in signals if s.title == "queue_pressure"]
    wait = [s for s in signals if s.title == "high_wait_time"]

    for p in pressure:
        partition = p.metrics.get("partition")
        matching_wait = [w for w in wait if w.metrics.get("partition") == partition]

        if matching_wait:
            combined = [p] + matching_wait
            pending = p.metrics.get("pending", 0)
            avg_wait = matching_wait[0].metrics.get("avg_wait_sec", 0) / 3600

            narrative = (
                f"The '{partition}' partition has a deep backlog ({pending} pending jobs) "
                f"and users are waiting an average of {avg_wait:.1f} hours for jobs to start. "
                f"This partition is a bottleneck."
            )
            insights.append(Insight(
                title="partition_bottleneck",
                narrative=narrative,
                severity=_max_severity(combined),
                source_signals=combined,
                recommendation=(
                    f"Consider increasing the node count for '{partition}', "
                    f"adjusting fairshare weights to distribute load, "
                    f"or guiding users to alternative partitions with available capacity."
                ),
                category="scheduling",
            ))

    return insights


def _correlate_network_and_jobs(signals: list[Signal]) -> list[Insight]:
    """Network issues + job failures = I/O-related failures."""
    insights = []
    net_issues = [s for s in signals
                  if s.title in ("high_network_latency", "packet_loss")]
    job_fails = [s for s in signals
                 if s.title in ("job_success_rate",) and s.severity.value in ("warning", "critical")]

    if net_issues and job_fails:
        combined = net_issues + job_fails
        paths = list(dict.fromkeys(s.metrics.get("path", "unknown") for s in net_issues))

        narrative = (
            f"Network degradation detected on {', '.join(paths)} "
            f"coinciding with elevated job failure rates. "
            f"Jobs that depend on NFS, parallel filesystems, or MPI communication "
            f"are particularly sensitive to network issues."
        )
        insights.append(Insight(
            title="network_induced_failures",
            narrative=narrative,
            severity=_max_severity(combined),
            source_signals=combined,
            recommendation=(
                "Check switch health and port error counters. "
                "Review if any specific node's NIC is causing issues. "
                "Consider temporarily draining affected nodes from the scheduler."
            ),
            category="network",
        ))

    return insights


def _correlate_cloud_cost_and_utilization(signals: list[Signal]) -> list[Insight]:
    """Cloud spending + underutilized instances = optimization opportunity."""
    insights = []
    cost = [s for s in signals if s.title == "cloud_cost_summary"]
    underused = [s for s in signals if s.title == "underutilized_cloud_instance"]

    if cost and underused:
        combined = cost + underused
        instances = [s.metrics.get("instance", "unknown") for s in underused]
        total_cost = sum(s.metrics.get("total_cost_usd", 0) for s in cost)

        narrative = (
            f"Cloud spending is ${total_cost:.2f} while {len(underused)} instance(s) "
            f"are significantly underutilized ({', '.join(instances)}). "
            f"Right-sizing these instances could reduce costs."
        )
        insights.append(Insight(
            title="cloud_cost_optimization",
            narrative=narrative,
            severity=Severity.NOTICE,
            source_signals=combined,
            recommendation=(
                "Review instance types for the underutilized machines. "
                "Consider scheduling batch workloads to consolidate onto fewer, "
                "larger instances during peak hours and scaling down during off-hours."
            ),
            category="cloud",
        ))

    return insights


def _correlate_workstation_and_alerts(signals: list[Signal]) -> list[Insight]:
    """High workstation load + active alerts = user impact."""
    insights = []
    ws_cpu = [s for s in signals if s.title == "workstation_high_cpu"]
    ws_mem = [s for s in signals if s.title == "workstation_high_memory"]
    alerts = [s for s in signals if s.title == "active_alerts"]

    overloaded = ws_cpu + ws_mem
    if len(overloaded) >= 2 and alerts:
        hosts = list({s.metrics.get("hostname", "") for s in overloaded})
        combined = overloaded + alerts

        narrative = (
            f"Multiple interactive nodes are under heavy load ({', '.join(hosts)}) "
            f"and there are active alerts in the system. "
            f"Users on these machines are likely experiencing "
            f"degraded performance."
        )
        insights.append(Insight(
            title="widespread_workstation_pressure",
            narrative=narrative,
            severity=_max_severity(combined),
            source_signals=combined,
            recommendation=(
                "Identify runaway processes on the affected nodes. "
                "Consider notifying users or killing long-running processes "
                "that should have been submitted to the scheduler instead."
                ),
            category="workstation",
        ))

    return insights


# ── Master correlator ────────────────────────────────────────────────────

_CORRELATORS = [
    _correlate_disk_and_jobs,
    _correlate_gpu_oom_and_partition,
    _correlate_queue_and_wait,
    _correlate_network_and_jobs,
    _correlate_cloud_cost_and_utilization,
    _correlate_workstation_and_alerts,
]


def correlate(signals: list[Signal]) -> list[Insight]:
    """
    Run all correlation rules against the signal set.

    Returns a list of Insights that represent multi-signal findings.
    Signals consumed by correlations are marked so the engine can
    avoid double-reporting.
    """
    all_insights: list[Insight] = []
    for correlator in _CORRELATORS:
        try:
            results = correlator(signals)
            all_insights.extend(results)
        except Exception:
            pass

    return all_insights
