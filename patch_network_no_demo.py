#!/usr/bin/env python3
"""
NOMAD fix — Network View shows only real data, no demo fallback

When the DB has clusters but no completed jobs, the Network View
was generating 150 synthetic demo jobs. Now it shows an empty state
with a message instead.

Demo data is ONLY used when no database is configured at all
(e.g., running `nomad dashboard` without any config/DB).

Apply on badenpowell:
    cd ~/nomad
    python3 patch_network_no_demo.py
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
print("\n[1] Backend: no demo fallback when DB exists but has no completed jobs")
# =====================================================================

patch(SERVER_PY,
    '                else:\n'
    '                    # Use demo jobs\n'
    '                    self._jobs = generate_demo_jobs(150)\n'
    '                    self._feature_stats = compute_feature_stats(self._jobs)\n'
    '                    self._correlation_data = compute_correlation_matrix(self._jobs)\n'
    '                    self._suggested_axes = suggest_decorrelated_axes(\n'
    '                        self._feature_stats,\n'
    '                        self._correlation_data\n'
    '                    )\n'
    '                    network_result = build_similarity_network(self._jobs, method=\'cosine\', threshold=0.7)\n'
    '                    self._edges = network_result[\'edges\']\n'
    '                    self._network_stats = network_result[\'stats\']\n'
    '                    self._discretization = network_result.get(\'discretization\') or network_result.get(\'normalization\')\n'
    '                    self._clustering_quality = compute_clustering_quality(self._jobs, self._edges)\n'
    '                    logger.info("Using demo job data for network view")\n'
    '\n'
    '                    # Run ML predictions\n'
    '                    self.run_ml_predictions()',

    '                else:\n'
    '                    # No completed jobs yet — show empty network\n'
    '                    self._jobs = []\n'
    '                    self._edges = []\n'
    '                    self._network_stats = {"nodes": 0, "edges": 0}\n'
    '                    logger.info("No completed jobs in database — network view empty")',

    "backend/no_demo_jobs_fallback")


# =====================================================================
print("\n[2] Frontend: show waiting message when no jobs")
# =====================================================================

patch(SERVER_PY,
    '            // Force-directed layout computation\n'
    '            const computeForceLayout = useMemo(() => {\n'
    '                if (!jobs || !edges) return null;',

    '            // Empty state when no completed jobs\n'
    '            if (!jobs || jobs.length === 0) {\n'
    '                return (\n'
    '                    <div className="content">\n'
    '                        <div className="cluster-header">\n'
    '                            <h1 className="cluster-title">Job Network</h1>\n'
    '                            <p className="cluster-desc">3D force-directed layout — connected jobs cluster together</p>\n'
    '                        </div>\n'
    '                        <div style={{display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "60vh", color: "var(--text-muted)"}}>\n'
    '                            <div style={{fontSize: "48px", marginBottom: "16px", opacity: 0.3}}>◇</div>\n'
    '                            <div style={{fontSize: "18px", marginBottom: "8px"}}>Waiting for completed jobs</div>\n'
    '                            <div style={{fontSize: "13px", maxWidth: "400px", textAlign: "center", lineHeight: "1.6"}}>\n'
    '                                The network visualization builds from completed job data. Jobs currently running will appear here once they finish and their metrics are recorded.\n'
    '                            </div>\n'
    '                        </div>\n'
    '                    </div>\n'
    '                );\n'
    '            }\n'
    '\n'
    '            // Force-directed layout computation\n'
    '            const computeForceLayout = useMemo(() => {\n'
    '                if (!jobs || !edges) return null;',

    "frontend/network_empty_state")


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
