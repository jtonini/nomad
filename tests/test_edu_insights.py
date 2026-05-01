# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for nomad.edu.insights."""

import pytest
from nomad.edu.insights import (
    DEFAULT_THRESHOLDS, KEY_TO_DISPLAY, Issue, UserInsights,
    _aggregate_dimension, _classify_overall_trajectory,
    _classify_severity, _compute_dimension_trajectory,
    _load_thresholds, format_user_insights,
)
from nomad.edu.scoring import DimensionScore, JobFingerprint


def make_fp(job_id: str, scores: dict[str, tuple[float, str, str]]) -> JobFingerprint:
    """Build a synthetic JobFingerprint. scores: {short_key: (score, suggestion, detail)}."""
    fp = JobFingerprint(job_id=job_id, user="testuser")
    for key, (score, suggestion, detail) in scores.items():
        long_name = KEY_TO_DISPLAY[key]
        fp.dimensions[key] = DimensionScore(
            name=long_name,
            score=score,
            level="Needs Work" if score < 40 else "Good",
            detail=detail,
            suggestion=suggestion,
            applicable=True,
        )
    return fp


class TestSeverityClassification:
    def test_critical_requires_low_avg_and_high_ratio(self):
        assert _classify_severity(avg_score=5.0, affected_ratio=0.95) == "critical"

    def test_low_avg_low_ratio_is_high_not_critical(self):
        assert _classify_severity(avg_score=10.0, affected_ratio=0.5) == "high"

    def test_moderate_avg_is_high(self):
        assert _classify_severity(avg_score=20.0, affected_ratio=0.6) == "high"

    def test_near_threshold_avg_is_medium(self):
        assert _classify_severity(avg_score=35.0, affected_ratio=0.55) == "medium"


class TestThresholdConfig:
    def test_defaults_when_no_config(self):
        t = _load_thresholds(None)
        assert t == DEFAULT_THRESHOLDS

    def test_overrides_apply(self):
        t = _load_thresholds({"thresholds": {"cpu": 30.0, "memory": 50.0}})
        assert t["cpu"] == 30.0
        assert t["memory"] == 50.0
        assert t["time"] == DEFAULT_THRESHOLDS["time"]  # unchanged

    def test_invalid_threshold_falls_back(self):
        t = _load_thresholds({"thresholds": {"cpu": "not-a-number"}})
        assert t["cpu"] == DEFAULT_THRESHOLDS["cpu"]

    def test_unknown_dimension_ignored(self):
        t = _load_thresholds({"thresholds": {"unknown_dim": 99.0}})
        assert "unknown_dim" not in t


class TestAggregation:
    def test_systemic_dimension_surfaces(self):
        fps = [
            make_fp(f"job_{i}", {"memory": (5.0, "Try: --mem=2G", "Used 1GB of 64GB")})
            for i in range(10)
        ]
        issue = _aggregate_dimension("memory", fps, 40.0)
        assert issue is not None
        assert issue.affected_jobs == 10
        assert issue.avg_score == 5.0
        assert issue.severity == "critical"
        assert issue.representative_suggestion == "Try: --mem=2G"

    def test_non_systemic_filtered_out(self):
        # 1 of 4 below threshold = 25% < 50% systemic ratio
        fps = [
            make_fp("g1", {"memory": (80.0, "", "")}),
            make_fp("g2", {"memory": (75.0, "", "")}),
            make_fp("b1", {"memory": (10.0, "Try: --mem=2G", "")}),
            make_fp("g3", {"memory": (85.0, "", "")}),
        ]
        assert _aggregate_dimension("memory", fps, 40.0) is None

    def test_modal_suggestion_picked(self):
        fps = [
            make_fp("j1", {"memory": (5.0, "Try: --mem=2G", "")}),
            make_fp("j2", {"memory": (5.0, "Try: --mem=2G", "")}),
            make_fp("j3", {"memory": (5.0, "Try: --mem=2G", "")}),
            make_fp("j4", {"memory": (5.0, "Try: --mem=4G", "")}),
            make_fp("j5", {"memory": (5.0, "Try: --mem=8G", "")}),
        ]
        issue = _aggregate_dimension("memory", fps, 40.0)
        assert issue.representative_suggestion == "Try: --mem=2G"

    def test_inapplicable_excluded_from_total(self):
        fps = [make_fp(f"j{i}", {"memory": (5.0, "x", "y")}) for i in range(5)]
        # Add a fingerprint with no Memory dimension at all
        no_mem = JobFingerprint(job_id="no_mem", user="testuser")
        fps.append(no_mem)
        issue = _aggregate_dimension("memory", fps, 40.0)
        assert issue is not None
        assert issue.total_applicable == 5  # the no_mem fp is excluded
        assert issue.affected_jobs == 5


class TestTrajectory:
    def test_worsening_detected(self):
        fps = (
            [make_fp(f"early_{i}", {"memory": (80.0, "", "")}) for i in range(4)] +
            [make_fp(f"late_{i}", {"memory": (10.0, "x", "")}) for i in range(4)]
        )
        assert _compute_dimension_trajectory(fps, "memory") == "worsening"

    def test_improving_detected(self):
        fps = (
            [make_fp(f"early_{i}", {"memory": (10.0, "x", "")}) for i in range(4)] +
            [make_fp(f"late_{i}", {"memory": (80.0, "", "")}) for i in range(4)]
        )
        assert _compute_dimension_trajectory(fps, "memory") == "improving"

    def test_stable_when_too_few_jobs(self):
        fps = [make_fp(f"j{i}", {"memory": (50.0, "", "")}) for i in range(2)]
        assert _compute_dimension_trajectory(fps, "memory") == "stable"

    def test_overall_trajectory_uses_overall_property(self):
        # Since JobFingerprint.overall is computed from dimensions, build
        # fingerprints with declining overall scores
        fps = [
            make_fp(f"e_{i}", {"cpu": (90.0, "", ""), "memory": (90.0, "", "")})
            for i in range(4)
        ] + [
            make_fp(f"l_{i}", {"cpu": (10.0, "x", ""), "memory": (10.0, "y", "")})
            for i in range(4)
        ]
        assert _classify_overall_trajectory(fps) == "declining"


class TestFormatting:
    def test_empty_user_renders_gracefully(self):
        ui = UserInsights(username="ghost", job_count=0, window_days=90)
        text = format_user_insights(ui)
        assert "No recent jobs found for ghost" in text

    def test_no_issues_renders_clean_message(self):
        ui = UserInsights(username="great_user", job_count=10, window_days=90,
                          overall_score=85.0, overall_trajectory="stable")
        text = format_user_insights(ui)
        assert "No systemic issues detected" in text

    def test_critical_issue_in_output(self):
        ui = UserInsights(username="testuser", job_count=30, window_days=90,
                          overall_score=35.0)
        ui.issues = [Issue(
            dimension="Memory Efficiency",
            dimension_key="memory",
            affected_jobs=30,
            total_applicable=30,
            avg_score=5.0,
            representative_suggestion="Try: #SBATCH --mem=3G",
            representative_detail="Requested 200GB but peaked at 1.7GB",
            severity="critical",
            trajectory="stable",
        )]
        text = format_user_insights(ui)
        assert "[CRITICAL]" in text
        assert "Memory Efficiency" in text
        assert "Try: #SBATCH --mem=3G" in text
        assert "30/30 jobs" in text
