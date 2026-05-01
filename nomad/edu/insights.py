# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""
NØMAD Edu Insights — User-Facing Recommendation Aggregator

Aggregates per-job recommendations (already computed in scoring.py) into a
structured summary across a user's recent jobs. Powers `nomad edu me` for
self-service users who want to know "how am I doing on this cluster?"
without combing through individual job analyses.

Design (per threshold baseline 2026-05-01):
  - Threshold default = 40 across all dimensions, aligned with the
    "Needs Work" boundary in scoring.py. Configurable via TOML.
  - Surface only dimensions where >50% of recent jobs score below threshold.
    Below that ratio, the issue is occasional rather than systemic.
  - Group by dimension, not recommendation text. Users want to know "I have
    a memory problem", not a list of recommendation strings that vary by job.
  - Pick a representative recommendation: the most common SLURM directive
    suggested across the affected jobs.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from nomad.edu.progress import _load_user_jobs, _score_jobs
from nomad.edu.scoring import JobFingerprint

logger = logging.getLogger(__name__)


# ── Defaults (per threshold baseline 2026-05-01) ─────────────────────

DEFAULT_THRESHOLDS: dict[str, float] = {
    "cpu":    40.0,
    "memory": 40.0,
    "time":   40.0,
    "io":     40.0,
    "gpu":    40.0,
}

# Surface a dimension only if at least this fraction of recent jobs score
# below threshold on it. Below 50%, the issue is occasional rather than
# systemic and not worth a "this is your top issue" framing.
DEFAULT_SYSTEMIC_RATIO = 0.5

# Severity bands based on (avg_score relative to threshold) AND (affected
# fraction). The bands are heuristic — tuned to be useful prose, not strict
# math. A dimension is "critical" only if it's both badly-scored on average
# AND affecting most jobs.
SEVERITY_CRITICAL_AVG = 15.0   # avg_score below this is severe
SEVERITY_HIGH_AVG     = 30.0   # avg_score below this is concerning
SEVERITY_CRITICAL_RATIO = 0.8  # affecting >80% of jobs


# ── Data classes ─────────────────────────────────────────────────────

@dataclass
class Issue:
    """One systemic recommendation across a user's recent jobs."""
    dimension: str               # e.g., "Memory Efficiency"
    dimension_key: str           # e.g., "memory" — matches DEFAULT_THRESHOLDS
    affected_jobs: int           # jobs with applicable score < threshold
    total_applicable: int        # jobs where this dimension was scored at all
    avg_score: float             # mean score across affected jobs
    representative_suggestion: str  # most common SLURM directive
    representative_detail: str   # most common detail text
    severity: str                # "critical" / "high" / "medium"
    trajectory: str              # "improving" / "stable" / "worsening"

    @property
    def affected_ratio(self) -> float:
        return (self.affected_jobs / self.total_applicable
                if self.total_applicable else 0.0)


@dataclass
class UserInsights:
    """Aggregate insight summary for a user across recent jobs."""
    username: str
    job_count: int               # total scored jobs in window
    window_days: int
    issues: list[Issue] = field(default_factory=list)  # sorted by severity
    overall_trajectory: str = "stable"  # improving / stable / declining
    overall_score: float = 0.0   # mean of per-job overall scores

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


# ── Configuration ────────────────────────────────────────────────────

def _load_thresholds(config: dict[str, Any] | None = None) -> dict[str, float]:
    """
    Load thresholds, preferring config over defaults. Config shape:
        {"thresholds": {"cpu": 30.0, "memory": 50.0, ...}}
    Unspecified dimensions fall back to DEFAULT_THRESHOLDS.
    """
    thresholds = dict(DEFAULT_THRESHOLDS)
    if config and isinstance(config.get("thresholds"), dict):
        for key, value in config["thresholds"].items():
            if key in thresholds:
                try:
                    thresholds[key] = float(value)
                except (TypeError, ValueError):
                    logger.warning(
                        f"Invalid threshold for {key}: {value!r}; using default"
                    )
    return thresholds


# ── Mapping between DimensionScore.name and short keys ───────────────

# scoring.py keys the JobFingerprint.dimensions dict with short names
# ("cpu", "memory", etc.). The DimensionScore.name field carries the
# human-readable long name ("Memory Efficiency"). We use the short keys
# for lookup and the long name for display.
KEY_TO_DISPLAY = {
    "cpu":    "CPU Efficiency",
    "memory": "Memory Efficiency",
    "time":   "Time Estimation",
    "io":     "I/O Awareness",
    "gpu":    "GPU Utilization",
}


# ── Aggregation ──────────────────────────────────────────────────────

def _compute_dimension_trajectory(
    fingerprints: list[JobFingerprint],
    dim_key: str,
) -> str:
    """
    Look at the dimension score over the user's job timeline (oldest to
    newest) and classify the trajectory. Uses the simple "first half vs
    second half" comparison — adequate for this granularity, no need for
    regression.
    """
    if dim_key not in KEY_TO_DISPLAY:
        return "stable"
    scores = []
    for fp in fingerprints:
        d = fp.dimensions.get(dim_key)
        if d is not None and d.applicable:
            scores.append(d.score)
    if len(scores) < 4:
        return "stable"  # not enough data to trend
    midpoint = len(scores) // 2
    first_half = sum(scores[:midpoint]) / midpoint
    second_half = sum(scores[midpoint:]) / (len(scores) - midpoint)
    delta = second_half - first_half
    if delta > 5:
        return "improving"
    if delta < -5:
        return "worsening"
    return "stable"


def _classify_severity(avg_score: float, affected_ratio: float) -> str:
    """Classify into critical / high / medium based on score and prevalence."""
    if avg_score <= SEVERITY_CRITICAL_AVG and affected_ratio >= SEVERITY_CRITICAL_RATIO:
        return "critical"
    if avg_score <= SEVERITY_HIGH_AVG:
        return "high"
    return "medium"


def _aggregate_dimension(
    dim_key: str,
    fingerprints: list[JobFingerprint],
    threshold: float,
) -> Issue | None:
    """
    Build an Issue for one dimension across the fingerprints, or None if
    the dimension isn't systemically a problem.
    """
    dim_name = KEY_TO_DISPLAY.get(dim_key, dim_key)
    affected_scores: list[float] = []
    suggestions: list[str] = []
    details: list[str] = []
    total_applicable = 0

    for fp in fingerprints:
        d = fp.dimensions.get(dim_key)
        if d is None or not d.applicable:
            continue
        total_applicable += 1
        if d.score < threshold:
            affected_scores.append(d.score)
            if d.suggestion:
                suggestions.append(d.suggestion)
            if d.detail:
                details.append(d.detail)

    if total_applicable == 0:
        return None

    affected_ratio = len(affected_scores) / total_applicable
    if affected_ratio < DEFAULT_SYSTEMIC_RATIO:
        return None  # not systemic; ignore

    avg_score = sum(affected_scores) / len(affected_scores)

    # Pick the most common suggestion as representative. If suggestions vary
    # widely (lots of distinct strings), this still picks the modal one,
    # which is a reasonable proxy for "the typical advice for this user".
    rep_suggestion = ""
    if suggestions:
        rep_suggestion = Counter(suggestions).most_common(1)[0][0]
    rep_detail = ""
    if details:
        rep_detail = Counter(details).most_common(1)[0][0]

    return Issue(
        dimension=dim_name,
        dimension_key=dim_key,
        affected_jobs=len(affected_scores),
        total_applicable=total_applicable,
        avg_score=avg_score,
        representative_suggestion=rep_suggestion,
        representative_detail=rep_detail,
        severity=_classify_severity(avg_score, affected_ratio),
        trajectory=_compute_dimension_trajectory(fingerprints, dim_key),
    )


def _classify_overall_trajectory(fingerprints: list[JobFingerprint]) -> str:
    """First-half vs second-half on the overall score."""
    if len(fingerprints) < 4:
        return "stable"
    overall_scores = [fp.overall for fp in fingerprints]
    midpoint = len(overall_scores) // 2
    first_half = sum(overall_scores[:midpoint]) / midpoint
    second_half = sum(overall_scores[midpoint:]) / (len(overall_scores) - midpoint)
    delta = second_half - first_half
    if delta > 5:
        return "improving"
    if delta < -5:
        return "declining"
    return "stable"


# ── Public API ───────────────────────────────────────────────────────

def user_insights(
    db_path: str,
    username: str,
    days: int = 90,
    config: dict[str, Any] | None = None,
) -> UserInsights:
    """
    Compute systemic insights for a user across recent jobs.

    Args:
        db_path: path to NØMAD SQLite database
        username: user to analyze
        days: lookback window in days (default 90, matches trajectory)
        config: optional config dict, may contain {"thresholds": {...}}

    Returns:
        UserInsights with issues sorted by severity (critical first).
        Empty issues list if user has no systemic problems or no data.
    """
    thresholds = _load_thresholds(config)
    rows = _load_user_jobs(db_path, username, days=days)
    fingerprints = _score_jobs(rows)

    insights = UserInsights(
        username=username,
        job_count=len(fingerprints),
        window_days=days,
    )

    if not fingerprints:
        return insights  # no data for this user

    insights.overall_score = sum(fp.overall for fp in fingerprints) / len(fingerprints)
    insights.overall_trajectory = _classify_overall_trajectory(fingerprints)

    issues: list[Issue] = []
    for dim_key in KEY_TO_DISPLAY:
        issue = _aggregate_dimension(
            dim_key, fingerprints,
            threshold=thresholds[dim_key],
        )
        if issue is not None:
            issues.append(issue)

    # Sort: critical first, then high, then medium; within each tier, lowest
    # avg_score first (worse problems surface first within a tier).
    severity_rank = {"critical": 0, "high": 1, "medium": 2}
    issues.sort(key=lambda i: (severity_rank[i.severity], i.avg_score))
    insights.issues = issues

    return insights


# ── Formatting ───────────────────────────────────────────────────────

def format_user_insights(insights: UserInsights, detailed: bool = False) -> str:
    """
    Render UserInsights as text suitable for terminal output.
    detailed=True includes per-dimension trajectory and detail blurbs.
    """
    lines: list[str] = []

    if insights.job_count == 0:
        return (f"No recent jobs found for {insights.username} "
                f"in the last {insights.window_days} days.\n"
                f"If you've run jobs recently, ensure the cluster's "
                f"job_metrics collector is current (>= v1.5.6).")

    # Header
    lines.append(f"  Your NØMAD Profile — {insights.username}")
    lines.append(f"  {'─' * 56}")
    lines.append(f"  {insights.job_count} jobs in the last {insights.window_days} days")
    lines.append(f"  Overall score: {insights.overall_score:.1f} / 100  "
                 f"({insights.overall_trajectory})")
    lines.append("")

    # Issues
    if not insights.issues:
        lines.append("  No systemic issues detected.")
        lines.append("  Either you're doing great, or your jobs vary too much")
        lines.append("  to flag any single dimension.")
        return "\n".join(lines)

    lines.append(f"  Top issues across your recent jobs:")
    lines.append(f"  {'─' * 56}")
    for issue in insights.issues:
        traj_arrow = {
            "improving": "↑ improving",
            "stable":    "→ stable",
            "worsening": "↓ worsening",
        }.get(issue.trajectory, issue.trajectory)
        sev_marker = {
            "critical": "[CRITICAL]",
            "high":     "[HIGH]    ",
            "medium":   "[MEDIUM]  ",
        }.get(issue.severity, "[?]       ")
        lines.append(f"")
        lines.append(f"  {sev_marker} {issue.dimension} — {traj_arrow}")
        lines.append(
            f"    {issue.affected_jobs}/{issue.total_applicable} jobs scored below "
            f"threshold (avg score: {issue.avg_score:.1f})"
        )
        if detailed and issue.representative_detail:
            lines.append(f"    Typical issue: {issue.representative_detail}")
        if issue.representative_suggestion:
            # Indent suggestion text by 4 spaces, preserving line breaks
            for sug_line in issue.representative_suggestion.split("\n"):
                lines.append(f"      {sug_line}")

    if not detailed:
        lines.append("")
        lines.append(f"  Run with --detailed for per-dimension trajectory and details.")
        lines.append(f"  Run `nomad edu explain <job_id>` for a single-job analysis.")

    return "\n".join(lines)
