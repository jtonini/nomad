#!/usr/bin/env python3
"""
NOMAD fix — Dashboard shows running and pending jobs

The dashboard only counted COMPLETED/FAILED jobs. Running jobs from squeue
were collected into the DB but not displayed.

Changes:
  1. Backend: job_stats includes running/pending counts per node
  2. Backend: node data includes jobs_running and jobs_pending fields
  3. Frontend: stats bar shows RUNNING and PENDING alongside completed
  4. Frontend: per-node shows running job count instead of "0 jobs"

Apply on badenpowell:
    cd ~/nomad
    python3 patch_dashboard_running_jobs.py
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
print("\n[1] Backend path 1: add running/pending to job_stats")
# =====================================================================

patch(SERVER_PY,
    '                # Get job statistics per node from jobs table\n'
    '                job_stats = {}\n'
    '                try:\n'
    '                    job_rows = conn.execute("""\n'
    '                        SELECT \n'
    '                            node_list,\n'
    '                            state,\n'
    '                            COUNT(*) as count\n'
    '                        FROM jobs\n'
    '                        WHERE start_time > datetime(\'now\', \'-1 day\')\n'
    '                        GROUP BY node_list, state\n'
    '                    """).fetchall()\n'
    '\n'
    '                    for row in job_rows:\n'
    '                        if row[\'node_list\']:\n'
    '                            for node in row[\'node_list\'].split(\',\'):\n'
    '                                node = node.strip()\n'
    '                                if node not in job_stats:\n'
    '                                    job_stats[node] = {\'success\': 0, \'failed\': 0}\n'
    '                                if row[\'state\'] == \'COMPLETED\':\n'
    '                                    job_stats[node][\'success\'] += row[\'count\']\n'
    '                                elif row[\'state\'] in (\'FAILED\', \'TIMEOUT\', \'OUT_OF_MEMORY\'):\n'
    '                                    job_stats[node][\'failed\'] += row[\'count\']\n'
    '                except:\n'
    '                    pass',

    '                # Get job statistics per node from jobs table\n'
    '                job_stats = {}\n'
    '                try:\n'
    '                    job_rows = conn.execute("""\n'
    '                        SELECT \n'
    '                            node_list,\n'
    '                            state,\n'
    '                            COUNT(*) as count\n'
    '                        FROM jobs\n'
    '                        GROUP BY node_list, state\n'
    '                    """).fetchall()\n'
    '\n'
    '                    for row in job_rows:\n'
    '                        if row[\'node_list\']:\n'
    '                            for node in row[\'node_list\'].split(\',\'):\n'
    '                                node = node.strip()\n'
    '                                if node not in job_stats:\n'
    '                                    job_stats[node] = {\'success\': 0, \'failed\': 0, \'running\': 0, \'pending\': 0}\n'
    '                                if row[\'state\'] == \'COMPLETED\':\n'
    '                                    job_stats[node][\'success\'] += row[\'count\']\n'
    '                                elif row[\'state\'] in (\'FAILED\', \'TIMEOUT\', \'OUT_OF_MEMORY\'):\n'
    '                                    job_stats[node][\'failed\'] += row[\'count\']\n'
    '                                elif row[\'state\'] == \'RUNNING\':\n'
    '                                    job_stats[node][\'running\'] += row[\'count\']\n'
    '                                elif row[\'state\'] == \'PENDING\':\n'
    '                                    job_stats[node][\'pending\'] += row[\'count\']\n'
    '                except:\n'
    '                    pass',

    "backend/job_stats_running_p1")


# =====================================================================
print("\n[2] Backend path 1: add running/pending to node data")
# =====================================================================

patch(SERVER_PY,
    '                        "jobs_today": total_jobs,\n'
    '                        "jobs_success": stats[\'success\'],\n'
    '                        "jobs_failed": stats[\'failed\'],',

    '                        "jobs_today": total_jobs,\n'
    '                        "jobs_running": stats.get(\'running\', 0),\n'
    '                        "jobs_pending": stats.get(\'pending\', 0),\n'
    '                        "jobs_success": stats[\'success\'],\n'
    '                        "jobs_failed": stats[\'failed\'],',

    "backend/node_data_running_p1")


# =====================================================================
print("\n[3] Backend path 2: add running/pending to job_stats")
# =====================================================================

patch(SERVER_PY,
    '                    try:\n'
    '                        job_rows = conn.execute("""\n'
    '                            SELECT \n'
    '                                node_list, state, failure_reason,\n'
    '                                COUNT(*) as count\n'
    '                            FROM jobs\n'
    '                            GROUP BY node_list, state, failure_reason\n'
    '                        """).fetchall()\n'
    '\n'
    '                        for row in job_rows:\n'
    '                            if row[\'node_list\']:\n'
    '                                node = row[\'node_list\'].strip()\n'
    '                                if node not in job_stats:\n'
    '                                    job_stats[node] = {\'success\': 0, \'failed\': 0, \'failures\': {}}\n'
    '                                if row[\'state\'] == \'COMPLETED\':\n'
    '                                    job_stats[node][\'success\'] += row[\'count\']\n'
    '                                else:\n'
    '                                    job_stats[node][\'failed\'] += row[\'count\']',

    '                    try:\n'
    '                        job_rows = conn.execute("""\n'
    '                            SELECT \n'
    '                                node_list, state, failure_reason,\n'
    '                                COUNT(*) as count\n'
    '                            FROM jobs\n'
    '                            GROUP BY node_list, state, failure_reason\n'
    '                        """).fetchall()\n'
    '\n'
    '                        for row in job_rows:\n'
    '                            if row[\'node_list\']:\n'
    '                                node = row[\'node_list\'].strip()\n'
    '                                if node not in job_stats:\n'
    '                                    job_stats[node] = {\'success\': 0, \'failed\': 0, \'running\': 0, \'pending\': 0, \'failures\': {}}\n'
    '                                if row[\'state\'] == \'COMPLETED\':\n'
    '                                    job_stats[node][\'success\'] += row[\'count\']\n'
    '                                elif row[\'state\'] == \'RUNNING\':\n'
    '                                    job_stats[node][\'running\'] += row[\'count\']\n'
    '                                elif row[\'state\'] == \'PENDING\':\n'
    '                                    job_stats[node][\'pending\'] += row[\'count\']\n'
    '                                else:\n'
    '                                    job_stats[node][\'failed\'] += row[\'count\']',

    "backend/job_stats_running_p2")


# =====================================================================
print("\n[4] Frontend: stats bar adds RUNNING and PENDING")
# =====================================================================

patch(SERVER_PY,
    '            const stats = useMemo(() => {\n'
    '                const online = nodes.filter(n => n.status === \'online\');\n'
    '                const totalJobs = online.reduce((sum, n) => sum + (n.jobs_today || 0), 0);\n'
    '                const successJobs = online.reduce((sum, n) => sum + (n.jobs_success || 0), 0);\n'
    '                const avgSuccess = online.length > 0 \n'
    '                    ? online.reduce((sum, n) => sum + (n.success_rate || 0), 0) / online.length \n'
    '                    : 0;\n'
    '                return {\n'
    '                    online: online.length,\n'
    '                    down: nodes.length - online.length,\n'
    '                    totalJobs,\n'
    '                    successJobs,\n'
    '                    failedJobs: totalJobs - successJobs,\n'
    '                    avgSuccess\n'
    '                };\n'
    '            }, [nodes]);',

    '            const stats = useMemo(() => {\n'
    '                const online = nodes.filter(n => n.status === \'online\');\n'
    '                const runningJobs = online.reduce((sum, n) => sum + (n.jobs_running || 0), 0);\n'
    '                const pendingJobs = online.reduce((sum, n) => sum + (n.jobs_pending || 0), 0);\n'
    '                const successJobs = online.reduce((sum, n) => sum + (n.jobs_success || 0), 0);\n'
    '                const failedJobs = online.reduce((sum, n) => sum + (n.jobs_failed || 0), 0);\n'
    '                const totalCompleted = successJobs + failedJobs;\n'
    '                const avgSuccess = totalCompleted > 0\n'
    '                    ? successJobs / totalCompleted\n'
    '                    : (runningJobs > 0 ? 1.0 : 0);\n'
    '                return {\n'
    '                    online: online.length,\n'
    '                    down: nodes.length - online.length,\n'
    '                    runningJobs,\n'
    '                    pendingJobs,\n'
    '                    successJobs,\n'
    '                    failedJobs,\n'
    '                    avgSuccess\n'
    '                };\n'
    '            }, [nodes]);',

    "frontend/stats_computation")


# =====================================================================
print("\n[5] Frontend: stats bar display")
# =====================================================================

patch(SERVER_PY,
    '                        <div className="stat">\n'
    '                            <div className="stat-value">{stats.totalJobs.toLocaleString()}</div>\n'
    '                            <div className="stat-label">Jobs Today</div>\n'
    '                        </div>\n'
    '                        <div className="stat">\n'
    '                            <div className="stat-value green">{stats.successJobs.toLocaleString()}</div>\n'
    '                            <div className="stat-label">Succeeded</div>\n'
    '                        </div>\n'
    '                        <div className="stat">\n'
    '                            <div className="stat-value red">{stats.failedJobs.toLocaleString()}</div>\n'
    '                            <div className="stat-label">Failed</div>\n'
    '                        </div>',

    '                        <div className="stat">\n'
    '                            <div className="stat-value" style={{color: stats.runningJobs > 0 ? "#3b82f6" : "inherit"}}>{stats.runningJobs.toLocaleString()}</div>\n'
    '                            <div className="stat-label">Running</div>\n'
    '                        </div>\n'
    '                        <div className="stat">\n'
    '                            <div className="stat-value" style={{color: stats.pendingJobs > 0 ? "#f59e0b" : "inherit"}}>{stats.pendingJobs.toLocaleString()}</div>\n'
    '                            <div className="stat-label">Pending</div>\n'
    '                        </div>\n'
    '                        <div className="stat">\n'
    '                            <div className="stat-value green">{stats.successJobs.toLocaleString()}</div>\n'
    '                            <div className="stat-label">Succeeded</div>\n'
    '                        </div>\n'
    '                        <div className="stat">\n'
    '                            <div className="stat-value red">{stats.failedJobs.toLocaleString()}</div>\n'
    '                            <div className="stat-label">Failed</div>\n'
    '                        </div>',

    "frontend/stats_display")


# =====================================================================
print("\n[6] Frontend: per-node shows running jobs")
# =====================================================================

# Node card text: "0 jobs" -> "12 running" or "0 jobs"
patch(SERVER_PY,
    "{node.status === 'down' ? (node.slurm_state || 'OFFLINE') : `${node.jobs_today || 0} jobs`}",

    "{node.status === 'down' ? (node.slurm_state || 'OFFLINE') : (node.jobs_running > 0 ? `${node.jobs_running} running` : `${node.jobs_today || 0} jobs`)}",

    "frontend/node_card_running")


# =====================================================================
print("\n[7] Frontend: partition summary shows running jobs")
# =====================================================================

# Partition header: "0 jobs  0 ok  0 fail" -> include running
patch(SERVER_PY,
    '                            const totalJobs = partNodes.reduce((s, n) => s + (n.jobs_today || 0), 0);',

    '                            const totalRunning = partNodes.reduce((s, n) => s + (n.jobs_running || 0), 0);\n'
    '                            const totalJobs = partNodes.reduce((s, n) => s + (n.jobs_today || 0), 0);',

    "frontend/partition_running_count")


# Check if there's a partition summary line to update
text = SERVER_PY.read_text()
if "0 ok" in text and "totalJobs}" in text:
    # Find and update the partition job summary
    old_part_summary = '{totalJobs} jobs'
    if old_part_summary in text:
        patch(SERVER_PY,
            '{totalJobs} jobs',
            '{totalRunning > 0 ? `${totalRunning} running` : `${totalJobs} jobs`}',
            "frontend/partition_summary_text")


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
