# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""
NØMAD Edu — Educational Analytics for HPC

Bridges the gap between infrastructure monitoring and educational outcomes
by capturing per-job behavioral fingerprints that enable administrators and
faculty to measure the development of computational proficiency over time.
"""

from nomad.edu.scoring import score_job, JobFingerprint
from nomad.edu.explain import explain_job
from nomad.edu.progress import user_trajectory, group_summary

__all__ = [
    "score_job",
    "JobFingerprint",
    "explain_job",
    "user_trajectory",
    "group_summary",
]

# Storage functions for proficiency tracking
from nomad.edu.storage import (
    init_proficiency_table,
    save_proficiency_score,
    get_user_proficiency_history,
    get_group_proficiency_stats,
)
