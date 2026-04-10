#!/usr/bin/env python3
"""
NOMAD — Add Readiness page to dashboard

Shows: collection uptime, data freshness per collector, DB size,
rows per table, last collection timestamp, collector status.

Apply on badenpowell:
    cd ~/nomad
    python3 patch_readiness_page.py
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
# 1. Add /api/readiness backend endpoint
# =====================================================================
print("\n[1] Add /api/readiness API endpoint")

READINESS_API = '''
        elif parsed.path == '/api/readiness':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            dm = DashboardHandler.data_manager
            result = {"status": "no_database"}
            try:
                import sqlite3 as _sql
                import os as _os
                db_path = dm.db_path
                conn = _sql.connect(str(db_path), timeout=5)
                conn.row_factory = _sql.Row
                c = conn.cursor()

                # DB file size
                db_size_bytes = _os.path.getsize(str(db_path))
                db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

                # Table row counts
                tables = {}
                table_names = [r[0] for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'v_%' "
                    "AND name NOT LIKE 'schema_%' ORDER BY name"
                ).fetchall()]
                for t in table_names:
                    try:
                        cnt = c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                        tables[t] = cnt
                    except Exception:
                        tables[t] = -1

                # Collector freshness — last timestamp per data table
                collectors = {}
                collector_tables = {
                    "disk": ("filesystems", "timestamp"),
                    "slurm": ("queue_state", "timestamp"),
                    "node_state": ("node_state", "timestamp"),
                    "iostat": ("iostat_cpu", "timestamp"),
                    "mpstat": ("mpstat_core", "timestamp"),
                    "vmstat": ("vmstat", "timestamp"),
                    "gpu": ("gpu_stats", "timestamp"),
                    "nfs": ("nfs_stats", "timestamp"),
                    "jobs": ("jobs", "start_time"),
                    "groups": ("group_membership", "timestamp" if "timestamp" in
                        [r[1] for r in c.execute("PRAGMA table_info(group_membership)").fetchall()]
                        else None),
                }
                for name, (table, ts_col) in collector_tables.items():
                    if table not in table_names:
                        collectors[name] = {"status": "no_table", "rows": 0}
                        continue
                    rows = tables.get(table, 0)
                    if ts_col:
                        try:
                            last = c.execute(
                                f"SELECT MAX({ts_col}) FROM [{table}]"
                            ).fetchone()[0]
                            first = c.execute(
                                f"SELECT MIN({ts_col}) FROM [{table}]"
                            ).fetchone()[0]
                            collectors[name] = {
                                "status": "active" if rows > 0 else "empty",
                                "rows": rows,
                                "last_update": last,
                                "first_update": first,
                            }
                        except Exception:
                            collectors[name] = {"status": "error", "rows": rows}
                    else:
                        collectors[name] = {
                            "status": "active" if rows > 0 else "empty",
                            "rows": rows,
                        }

                # Collection cycles (from node_state distinct timestamps)
                try:
                    cycles = c.execute(
                        "SELECT COUNT(DISTINCT timestamp) FROM node_state"
                    ).fetchone()[0]
                except Exception:
                    cycles = 0

                # Uptime (first to last node_state)
                try:
                    r = c.execute(
                        "SELECT MIN(timestamp), MAX(timestamp) FROM node_state"
                    ).fetchone()
                    first_ts, last_ts = r[0], r[1]
                except Exception:
                    first_ts, last_ts = None, None

                # Config info
                config = dm.config or {}
                cluster_name = "unknown"
                try:
                    clusters_cfg = config.get("clusters", {})
                    if clusters_cfg:
                        cluster_name = list(clusters_cfg.values())[0].get("name", "unknown")
                except Exception:
                    pass

                result = {
                    "status": "ok",
                    "cluster_name": cluster_name,
                    "database": {
                        "path": str(db_path),
                        "size_mb": db_size_mb,
                        "size_bytes": db_size_bytes,
                    },
                    "collection": {
                        "cycles": cycles,
                        "first_timestamp": first_ts,
                        "last_timestamp": last_ts,
                    },
                    "collectors": collectors,
                    "tables": tables,
                    "data_source": dm.data_source,
                }

                conn.close()
            except Exception as e:
                result = {"status": "error", "error": str(e)}

            self.wfile.write(json.dumps(result).encode())
'''

patch(SERVER_PY,
    "        elif parsed.path == '/api/insights':",
    READINESS_API + "\n        elif parsed.path == '/api/insights':",
    "api/readiness_endpoint")


# =====================================================================
# 2. Add ReadinessPanel React component
# =====================================================================
print("\n[2] Add ReadinessPanel component")

READINESS_PANEL = '''
            const ReadinessPanel = () => {
                const [data, setData] = useState(null);
                const [loading, setLoading] = useState(true);
                useEffect(() => {
                    const load = () => fetch('/api/readiness')
                        .then(r => r.json())
                        .then(d => { setData(d); setLoading(false); })
                        .catch(() => setLoading(false));
                    load();
                    const iv = setInterval(load, 10000);
                    return () => clearInterval(iv);
                }, []);

                if (loading) return React.createElement("div", {style: {padding: "40px", textAlign: "center"}}, "Loading readiness data...");
                if (!data || data.status === "error") return React.createElement("div", {style: {padding: "40px"}}, "Could not load readiness data.");

                const cs = data.collectors || {};
                const ts = data.tables || {};
                const col = data.collection || {};
                const db = data.database || {};

                const formatBytes = (b) => {
                    if (b > 1024*1024*1024) return (b/(1024*1024*1024)).toFixed(1) + " GB";
                    if (b > 1024*1024) return (b/(1024*1024)).toFixed(1) + " MB";
                    if (b > 1024) return (b/1024).toFixed(1) + " KB";
                    return b + " B";
                };

                const formatAge = (ts) => {
                    if (!ts) return "—";
                    const diff = (Date.now() - new Date(ts).getTime()) / 1000;
                    if (diff < 60) return Math.round(diff) + "s ago";
                    if (diff < 3600) return Math.round(diff/60) + "m ago";
                    if (diff < 86400) return Math.round(diff/3600) + "h ago";
                    return Math.round(diff/86400) + "d ago";
                };

                const formatUptime = (first, last) => {
                    if (!first || !last) return "—";
                    const diff = (new Date(last).getTime() - new Date(first).getTime()) / 1000;
                    const h = Math.floor(diff / 3600);
                    const m = Math.floor((diff % 3600) / 60);
                    if (h > 24) return Math.floor(h/24) + "d " + (h%24) + "h";
                    return h + "h " + m + "m";
                };

                const collectorOrder = ["node_state", "slurm", "jobs", "disk", "iostat", "mpstat", "vmstat", "gpu", "nfs", "groups"];
                const statusColors = {active: "#22c55e", empty: "#f59e0b", no_table: "#6b7280", error: "#ef4444"};
                const statusLabels = {active: "Active", empty: "Empty", no_table: "No Table", error: "Error"};

                const cardStyle = {background: "var(--bg-secondary, #1e293b)", borderRadius: "12px", padding: "20px"};
                const labelStyle = {fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em", opacity: 0.5, marginBottom: "4px"};
                const valueStyle = {fontSize: "24px", fontWeight: 700, fontFamily: "monospace"};

                return React.createElement("div", {style: {padding: "20px", maxWidth: "1000px"}},
                    // Title
                    React.createElement("h2", {style: {fontSize: "20px", fontWeight: 600, marginBottom: "20px"}}, "System Readiness"),

                    // Summary cards row
                    React.createElement("div", {style: {display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px", marginBottom: "24px"}},
                        React.createElement("div", {style: cardStyle},
                            React.createElement("div", {style: labelStyle}, "Status"),
                            React.createElement("div", {style: {...valueStyle, fontSize: "18px", color: data.status === "ok" ? "#22c55e" : "#ef4444"}},
                                data.status === "ok" ? "Collecting" : "Error")
                        ),
                        React.createElement("div", {style: cardStyle},
                            React.createElement("div", {style: labelStyle}, "Uptime"),
                            React.createElement("div", {style: {...valueStyle, fontSize: "18px"}},
                                formatUptime(col.first_timestamp, col.last_timestamp))
                        ),
                        React.createElement("div", {style: cardStyle},
                            React.createElement("div", {style: labelStyle}, "Collection Cycles"),
                            React.createElement("div", {style: valueStyle}, col.cycles || 0)
                        ),
                        React.createElement("div", {style: cardStyle},
                            React.createElement("div", {style: labelStyle}, "Database Size"),
                            React.createElement("div", {style: {...valueStyle, fontSize: "18px"}},
                                formatBytes(db.size_bytes || 0))
                        )
                    ),

                    // Last update
                    React.createElement("div", {style: {...cardStyle, marginBottom: "24px", padding: "12px 20px", display: "flex", justifyContent: "space-between", alignItems: "center"}},
                        React.createElement("span", {style: {opacity: 0.7}}, "Last collection"),
                        React.createElement("span", {style: {fontFamily: "monospace", fontWeight: 600}},
                            col.last_timestamp ? formatAge(col.last_timestamp) + " (" + col.last_timestamp + ")" : "—")
                    ),

                    // Collectors table
                    React.createElement("h3", {style: {fontSize: "16px", fontWeight: 600, marginBottom: "12px", marginTop: "8px"}}, "Collectors"),
                    React.createElement("div", {style: {...cardStyle, padding: 0, overflow: "hidden", marginBottom: "24px"}},
                        React.createElement("table", {style: {width: "100%", borderCollapse: "collapse", fontSize: "13px"}},
                            React.createElement("thead", null,
                                React.createElement("tr", {style: {borderBottom: "1px solid var(--border, #333)"}},
                                    React.createElement("th", {style: {textAlign: "left", padding: "12px 16px", opacity: 0.6, fontWeight: 500}}, "Collector"),
                                    React.createElement("th", {style: {textAlign: "center", padding: "12px 16px", opacity: 0.6, fontWeight: 500}}, "Status"),
                                    React.createElement("th", {style: {textAlign: "right", padding: "12px 16px", opacity: 0.6, fontWeight: 500}}, "Records"),
                                    React.createElement("th", {style: {textAlign: "right", padding: "12px 16px", opacity: 0.6, fontWeight: 500}}, "Last Update"),
                                    React.createElement("th", {style: {textAlign: "right", padding: "12px 16px", opacity: 0.6, fontWeight: 500}}, "First Seen")
                                )
                            ),
                            React.createElement("tbody", null,
                                ...collectorOrder.filter(k => cs[k]).map((k, i) =>
                                    React.createElement("tr", {key: k, style: {borderBottom: i < collectorOrder.length-1 ? "1px solid var(--border, #222)" : "none"}},
                                        React.createElement("td", {style: {padding: "10px 16px", fontWeight: 500}}, k),
                                        React.createElement("td", {style: {padding: "10px 16px", textAlign: "center"}},
                                            React.createElement("span", {style: {
                                                background: (statusColors[cs[k].status] || "#6b7280") + "22",
                                                color: statusColors[cs[k].status] || "#6b7280",
                                                padding: "2px 10px", borderRadius: "4px", fontSize: "11px", fontWeight: 600
                                            }}, statusLabels[cs[k].status] || cs[k].status)
                                        ),
                                        React.createElement("td", {style: {padding: "10px 16px", textAlign: "right", fontFamily: "monospace"}},
                                            (cs[k].rows || 0).toLocaleString()),
                                        React.createElement("td", {style: {padding: "10px 16px", textAlign: "right", fontSize: "12px", opacity: 0.7}},
                                            formatAge(cs[k].last_update)),
                                        React.createElement("td", {style: {padding: "10px 16px", textAlign: "right", fontSize: "12px", opacity: 0.7}},
                                            formatAge(cs[k].first_update))
                                    )
                                )
                            )
                        )
                    ),

                    // Database path
                    React.createElement("div", {style: {...cardStyle, padding: "12px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "12px", opacity: 0.6}},
                        React.createElement("span", null, "Database"),
                        React.createElement("span", {style: {fontFamily: "monospace"}}, db.path || "—")
                    )
                );
            };
'''

# Insert before InsightsPanel
patch(SERVER_PY,
    '            const InsightsPanel = () => {',
    READINESS_PANEL + '\n            const InsightsPanel = () => {',
    "frontend/readiness_panel")


# =====================================================================
# 3. Add tab button for Readiness
# =====================================================================
print("\n[3] Add Readiness tab")

# Add after Report Issue tab
patch(SERVER_PY,
    "                                className={`tab ${activeTab === 'issue' ? 'active' : ''}`}\n"
    "                                onClick={() => { setActiveTab('issue'); setSelectedNode(null); }}",

    "                                className={`tab ${activeTab === 'issue' ? 'active' : ''}`}\n"
    "                                onClick={() => { setActiveTab('issue'); setSelectedNode(null); }}\n"
    "                            >Report Issue</a>,\n"
    "                            React.createElement('a', {\n"
    "                                className: `tab ${activeTab === 'readiness' ? 'active' : ''}`,\n"
    "                                onClick: () => { setActiveTab('readiness'); setSelectedNode(null); }",

    "tab/readiness_button")


# =====================================================================
# 4. Add Readiness panel to tab rendering
# =====================================================================
print("\n[4] Add Readiness to tab rendering")

patch(SERVER_PY,
    "                        ) : activeTab === 'issue' ? (\n"
    "                            <ReportIssuePanel />",

    "                        ) : activeTab === 'readiness' ? (\n"
    "                            <ReadinessPanel />\n"
    "                        ) : activeTab === 'issue' ? (\n"
    "                            <ReportIssuePanel />",

    "render/readiness_tab")


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
