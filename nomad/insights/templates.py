# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""
Narrative templates for the NØMAD Insight Engine.

Each template is a callable that receives a Signal and returns a
human-readable narrative string. Templates are selected based on
signal type and severity, with conditional logic for context-dependent
phrasing.
"""
from __future__ import annotations

from .signals import Signal, SignalType, Severity


def _fmt_hours(h: float) -> str:
    """Format hours into human-readable duration."""
    if h < 1:
        return f"{h * 60:.0f} minutes"
    if h < 24:
        return f"{h:.0f} hours"
    days = h / 24
    if days < 7:
        return f"{days:.1f} days"
    return f"{days / 7:.1f} weeks"


def _severity_word(sev: Severity) -> str:
    """Opening tone word for severity."""
    return {
        Severity.INFO: "",
        Severity.NOTICE: "Note:",
        Severity.WARNING: "Warning:",
        Severity.CRITICAL: "CRITICAL:",
    }[sev]


# ── Template functions ───────────────────────────────────────────────────

def narrate_job_success_rate(sig: Signal) -> str:
    m = sig.metrics
    rate = m["success_rate"]
    total = m["total"]
    hours = m["hours"]
    failed = m["failed"]
    oom = m["oom"]
    timed_out = m["timed_out"]

    parts = []
    if rate >= 95:
        parts.append(f"{total:,} jobs processed in the last {_fmt_hours(hours)}, {rate:.1f}% success rate.")
    elif rate >= 90:
        parts.append(f"{total:,} jobs in the last {_fmt_hours(hours)}, {rate:.1f}% success rate — slightly below target.")
    elif rate >= 80:
        parts.append(f"{total:,} jobs in the last {_fmt_hours(hours)}, {rate:.1f}% success rate — below the 90% baseline.")
    else:
        parts.append(f"{total:,} jobs in the last {_fmt_hours(hours)}, only {rate:.1f}% succeeded — well below normal.")

    # Break down failure modes
    failures = []
    if failed > 0:
        failures.append(f"{failed} failed")
    if timed_out > 0:
        failures.append(f"{timed_out} timed out")
    if oom > 0:
        failures.append(f"{oom} ran out of memory")
    if failures:
        parts.append(f"Breakdown: {', '.join(failures)}.")

    return " ".join(parts)


def narrate_partition_failures(sig: Signal) -> str:
    m = sig.metrics
    partition = m["partition"]
    failures = m["failures"]
    pct = m["pct"]

    if pct > 10:
        return (
            f"Failures are concentrated in the '{partition}' partition — "
            f"{failures} failures accounting for {pct:.1f}% of all jobs. "
            f"Investigate whether resource limits or node health in this partition "
            f"are contributing."
        )
    return (
        f"The '{partition}' partition has {failures} recent failures ({pct:.1f}% of jobs). "
        f"Worth monitoring."
    )


def narrate_oom(sig: Signal) -> str:
    m = sig.metrics
    count = m["oom_count"]
    users = m.get("top_users", [])

    text = f"{count} jobs failed due to insufficient memory."
    if users:
        text += f" Most affected users: {', '.join(users)}."
    text += " Recommendation: check requested vs. actual memory and adjust --mem flags."
    return text


def narrate_timeout(sig: Signal) -> str:
    m = sig.metrics
    count = m["timeout_count"]
    return (
        f"{count} jobs exceeded their time limit. "
        f"Common causes: underestimated wall time, I/O bottlenecks, or "
        f"competing workloads. Review with 'nomad edu explain <job_id>'."
    )


def narrate_job_rate_trend(sig: Signal) -> str:
    m = sig.metrics
    prev = m["previous_rate"]
    curr = m["current_rate"]
    delta = m["delta"]

    if delta > 0:
        return (
            f"Success rate is improving: {prev:.1f}% in the previous period to "
            f"{curr:.1f}% now ({delta:+.1f} percentage points)."
        )
    return (
        f"Success rate is declining: {prev:.1f}% in the previous period to "
        f"{curr:.1f}% now ({delta:+.1f} percentage points). Investigate recent changes."
    )


def narrate_filesystem_usage(sig: Signal) -> str:
    m = sig.metrics
    server = m.get("server") or m.get("hostname", "unknown")
    usage = m.get("usage_pct") or m.get("usage_percent", 0)
    avail = m.get("avail_gb") or m.get("free_gb", 0)

    if usage >= 90:
        return f"{server} is at {usage:.0f}% capacity with only {avail:.0f} GB remaining. Immediate attention needed."
    if usage >= 80:
        return f"{server} is at {usage:.0f}% capacity ({avail:.0f} GB remaining). Approaching critical threshold."
    return f"{server} is at {usage:.0f}% ({avail:.0f} GB free). Above normal but not yet critical."


def narrate_disk_fill_projection(sig: Signal) -> str:
    m = sig.metrics
    server = m.get("server") or m.get("hostname", "unknown")
    rate = m["fill_rate_gb_hr"]
    hours = m["hours_to_full"]

    if hours < 12:
        urgency = "Urgent"
    elif hours < 24:
        urgency = "Important"
    else:
        urgency = "Note"

    return (
        f"{urgency}: {server} is filling at {rate:.1f} GB/hr and will reach capacity "
        f"in approximately {_fmt_hours(hours)}. "
        f"Recommendation: identify large writers and consider purge or quota adjustments."
    )


def narrate_gpu_failure_rate(sig: Signal) -> str:
    m = sig.metrics
    rate = m["fail_rate"]
    failed = m["failed"]
    total = m["total_gpu_jobs"]
    return (
        f"{rate:.0f}% of GPU jobs are failing ({failed}/{total}). "
        f"GPU partition issues disproportionately affect research groups "
        f"running ML training and simulation workloads."
    )


def narrate_gpu_oom(sig: Signal) -> str:
    m = sig.metrics
    count = m["gpu_oom_count"]
    total = m["total_gpu_jobs"]
    return (
        f"{count} GPU jobs ran out of VRAM (of {total} total GPU jobs). "
        f"Users may be requesting insufficient GPU memory or running models "
        f"too large for the available hardware. "
        f"Consider VRAM-aware scheduling or routing large jobs to high-memory GPU nodes."
    )


def narrate_queue_pressure(sig: Signal) -> str:
    m = sig.metrics
    partition = m["partition"]
    pending = m["pending"]
    running = m["running"]
    ratio = m["ratio"]

    if ratio > 5:
        return (
            f"Heavy backlog in '{partition}': {pending} jobs waiting with only "
            f"{running} running ({ratio:.1f}x ratio). Users will experience significant delays."
        )
    return (
        f"'{partition}' has elevated queue pressure: {pending} pending vs "
        f"{running} running ({ratio:.1f}x ratio)."
    )


def narrate_high_wait_time(sig: Signal) -> str:
    m = sig.metrics
    partition = m["partition"]
    avg = m["avg_wait_sec"] / 3600
    mx = m["max_wait_sec"] / 3600
    return (
        f"Average wait time in '{partition}' is {avg:.1f} hours (longest: {mx:.1f} hours). "
        f"Consider whether fairshare weights need adjustment or if the partition "
        f"needs additional resources."
    )


def narrate_network_latency(sig: Signal) -> str:
    m = sig.metrics
    path = m["path"]
    avg = m["avg_latency"]
    peak = m["max_latency"]
    return (
        f"Network path '{path}' showing elevated latency: {avg:.1f}ms average, "
        f"{peak:.1f}ms peak. This can impact NFS-dependent jobs and parallel workloads."
    )


def narrate_packet_loss(sig: Signal) -> str:
    m = sig.metrics
    path = m["path"]
    avg = m["avg_loss"]
    return (
        f"Packet loss detected on '{path}': {avg:.2f}% average. "
        f"Even small packet loss degrades MPI and distributed training performance significantly."
    )


def narrate_active_alerts(sig: Signal) -> str:
    m = sig.metrics
    total = m["total_active"]
    crit = m["critical"]
    warn = m["warning"]
    resolved = m["resolved_recently"]

    parts = [f"{total} active alerts"]
    if crit:
        parts.append(f"{crit} critical")
    if warn:
        parts.append(f"{warn} warning")
    text = f"{', '.join(parts)}."
    if resolved:
        text += f" ({resolved} alerts resolved recently.)"
    return text


def narrate_flapping_alert(sig: Signal) -> str:
    m = sig.metrics
    metric = m["metric"]
    count = m["trigger_count"]
    return (
        f"The '{metric}' alert has triggered {count} times recently — "
        f"this suggests an oscillating condition rather than a one-time event. "
        f"Review the threshold or investigate the underlying cause."
    )


def narrate_cloud_cost(sig: Signal) -> str:
    m = sig.metrics
    cost = m["total_cost_usd"]
    hours = m["hours"]
    daily = cost * (24 / hours) if hours > 0 else cost
    return f"Cloud compute spending: ${cost:.2f} over the last {_fmt_hours(hours)} (projected ${daily:.2f}/day)."


def narrate_underutilized_instance(sig: Signal) -> str:
    m = sig.metrics
    instance = m["instance"]
    cpu = m["avg_cpu"]
    return (
        f"Cloud instance '{instance}' is averaging only {cpu:.1f}% CPU utilization. "
        f"Consider downsizing to a smaller instance type or consolidating workloads to reduce cost."
    )


def narrate_workstation_cpu(sig: Signal) -> str:
    m = sig.metrics
    host = m["hostname"]
    avg = m["avg_cpu"]
    return (
        f"'{host}' is running at {avg:.0f}% average CPU. "
        f"Users on this node may experience degraded interactive performance."
    )


def narrate_workstation_memory(sig: Signal) -> str:
    m = sig.metrics
    host = m["hostname"]
    avg = m["avg_mem"]
    return (
        f"'{host}' at {avg:.0f}% memory utilization. "
        f"Risk of OOM kills for user processes. Check for runaway processes."
    )


# ── Template dispatch ────────────────────────────────────────────────────

_TEMPLATE_MAP: dict[str, callable] = {
    "job_success_rate": narrate_job_success_rate,
    "partition_failure_concentration": narrate_partition_failures,
    "oom_failures": narrate_oom,
    "timeout_failures": narrate_timeout,
    "job_rate_trend": narrate_job_rate_trend,
    "filesystem_usage": narrate_filesystem_usage,
    "disk_fill_projection": narrate_disk_fill_projection,
    "gpu_job_failure_rate": narrate_gpu_failure_rate,
    "gpu_oom": narrate_gpu_oom,
    "queue_pressure": narrate_queue_pressure,
    "high_wait_time": narrate_high_wait_time,
    "high_network_latency": narrate_network_latency,
    "packet_loss": narrate_packet_loss,
    "active_alerts": narrate_active_alerts,
    "flapping_alert": narrate_flapping_alert,
    "cloud_cost_summary": narrate_cloud_cost,
    "underutilized_cloud_instance": narrate_underutilized_instance,
    "workstation_high_cpu": narrate_workstation_cpu,
    "workstation_high_memory": narrate_workstation_memory,
}


def narrate(signal: Signal) -> str:
    """Convert a signal into a narrative string using the appropriate template."""
    template = _TEMPLATE_MAP.get(signal.title)
    if template:
        return template(signal)
    # Fallback: use the signal's detail field directly
    return signal.detail
