#!/usr/bin/env python3
"""
NOMAD fix — Dashboard shows configured partitions, running jobs per node,
user info for running jobs, no double-counting.

Issues:
  1. Dashboard shows ALL partitions from node_state, not just configured ones
  2. Per-node cards show "0 jobs" — job_stats query filters by end_time (completed only)
  3. Top users query filters by end_time — misses running jobs
  4. Header double-counts jobs because nodes appear in multiple partitions

Apply on badenpowell:
    cd ~/nomad
    python3 patch_dashboard_jobs_fix.py
"""

import sys
from pathlib import Path

REPO = Path.home() / "nomad"
SERVER_PY = REPO / "nomad" / "viz" / "server.py"

if not SERVER_PY.exists():
    print(f"Error: {SERVER_PY} not found")
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
print("\n[1] Fix top_users: include RUNNING jobs, not just completed")
# =====================================================================

# First top_users query (job_accounting table)
patch(SERVER_PY,
    '                    try:\n'
    '                        user_rows = conn.execute("""\n'
    '                            SELECT username, COUNT(*) as job_count\n'
    '                            FROM job_accounting\n'
    '                            WHERE node_list LIKE ?\n'
    "                            AND end_time > datetime('now', '-1 day')\n"
    '                            GROUP BY username\n'
    '                            ORDER BY job_count DESC\n'
    '                            LIMIT 5\n'
    '                        """, (f\'%{node_name}%\',)).fetchall()',

    '                    try:\n'
    '                        user_rows = conn.execute("""\n'
    '                            SELECT username, COUNT(*) as job_count\n'
    '                            FROM job_accounting\n'
    '                            WHERE node_list LIKE ?\n'
    "                            AND (end_time > datetime('now', '-1 day')\n"
    "                                 OR end_time IS NULL)\n"
    '                            GROUP BY username\n'
    '                            ORDER BY job_count DESC\n'
    '                            LIMIT 5\n'
    '                        """, (f\'%{node_name}%\',)).fetchall()',

    "backend/top_users_accounting")

# Second top_users query (jobs table)
patch(SERVER_PY,
    '                            SELECT user_name as username, COUNT(*) as job_count\n'
    '                                FROM jobs\n'
    '                                WHERE node_list LIKE ?\n'
    "                                AND end_time > datetime('now', '-1 day')\n"
    '                                GROUP BY user_name\n'
    '                                ORDER BY job_count DESC\n'
    '                                LIMIT 5',

    '                            SELECT user_name as username, COUNT(*) as job_count\n'
    '                                FROM jobs\n'
    '                                WHERE node_list LIKE ?\n'
    "                                AND (state = 'RUNNING' OR state = 'PENDING'\n"
    "                                     OR end_time > datetime('now', '-1 day'))\n"
    '                                GROUP BY user_name\n'
    '                                ORDER BY job_count DESC\n'
    '                                LIMIT 5',

    "backend/top_users_jobs")


# =====================================================================
print("\n[2] Fix node sidebar: show Running/Pending counts")
# =====================================================================

patch(SERVER_PY,
    '                                <div className="detail-section-title">Job Statistics</div>\n'
    '                                <div className="detail-row">\n'
    '                                    <span className="detail-label">Jobs Today</span>\n'
    '                                    <span className="detail-value">{node.jobs_today || 0}</span>\n'
    '                                </div>\n'
    '                                <div className="detail-row">\n'
    '                                    <span className="detail-label">Succeeded</span>\n'
    '                                    <span className="detail-value green">{node.jobs_success || 0}</span>\n'
    '                                </div>\n'
    '                                <div className="detail-row">\n'
    '                                    <span className="detail-label">Failed</span>\n'
    '                                    <span className="detail-value red">{node.jobs_failed || 0}</span>\n'
    '                                </div>',

    '                                <div className="detail-section-title">Job Statistics</div>\n'
    '                                <div className="detail-row">\n'
    '                                    <span className="detail-label">Running</span>\n'
    '                                    <span className="detail-value" style={{color: "#3b82f6"}}>{node.jobs_running || 0}</span>\n'
    '                                </div>\n'
    '                                <div className="detail-row">\n'
    '                                    <span className="detail-label">Pending</span>\n'
    '                                    <span className="detail-value" style={{color: "#f59e0b"}}>{node.jobs_pending || 0}</span>\n'
    '                                </div>\n'
    '                                <div className="detail-row">\n'
    '                                    <span className="detail-label">Succeeded</span>\n'
    '                                    <span className="detail-value green">{node.jobs_success || 0}</span>\n'
    '                                </div>\n'
    '                                <div className="detail-row">\n'
    '                                    <span className="detail-label">Failed</span>\n'
    '                                    <span className="detail-value red">{node.jobs_failed || 0}</span>\n'
    '                                </div>',

    "frontend/sidebar_running")


# =====================================================================
print("\n[3] Fix header: count unique jobs, not sum across partitions")
# =====================================================================

# The header sums jobs_running across all nodes, but nodes appear in multiple
# partitions so the same node (and its jobs) gets counted multiple times.
# Fix: use a Set of unique node names to avoid double-counting.

patch(SERVER_PY,
    '                const runningJobs = online.reduce((sum, n) => sum + (n.jobs_running || 0), 0);\n'
    '                const pendingJobs = online.reduce((sum, n) => sum + (n.jobs_pending || 0), 0);\n'
    '                const successJobs = online.reduce((sum, n) => sum + (n.jobs_success || 0), 0);\n'
    '                const failedJobs = online.reduce((sum, n) => sum + (n.jobs_failed || 0), 0);',

    '                // Deduplicate nodes (same node appears in multiple partitions)\n'
    '                const seen = new Set();\n'
    '                let runningJobs = 0, pendingJobs = 0, successJobs = 0, failedJobs = 0;\n'
    '                online.forEach(n => {\n'
    '                    if (!seen.has(n.name)) {\n'
    '                        seen.add(n.name);\n'
    '                        runningJobs += (n.jobs_running || 0);\n'
    '                        pendingJobs += (n.jobs_pending || 0);\n'
    '                        successJobs += (n.jobs_success || 0);\n'
    '                        failedJobs += (n.jobs_failed || 0);\n'
    '                    }\n'
    '                });',

    "frontend/dedup_header_counts")


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
