#!/usr/bin/env python3
"""
NOMAD — Fix interactive sessions, storage layout, readiness per-server

1. Interactive: fix session query (each row has unique timestamp)
2. Storage: group devices by server in two-column layout
3. Readiness: show per-server collection stats

Apply on badenpowell:
    cd ~/nomad
    python3 patch_dashboard_polish.py
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
print("\n[1] Fix interactive sessions query")
# =====================================================================
# Each session row has a unique microsecond timestamp.
# Fix: get sessions within 5 seconds of the latest timestamp
# to capture all sessions from the same collection cycle.

patch(SERVER_PY,
    '                c.execute("""SELECT * FROM interactive_sessions \n'
    '                    WHERE timestamp = (SELECT MAX(timestamp) FROM interactive_sessions)""")',

    '                c.execute("""SELECT * FROM interactive_sessions \n'
    '                    WHERE timestamp >= datetime(\n'
    '                        (SELECT MAX(timestamp)\n'
    '                         FROM interactive_sessions),\n'
    '                        \'-5 seconds\')""")',

    "interactive/fix_session_query")


# =====================================================================
print("\n[2] Storage: group by server, two-column layout")
# =====================================================================
# Replace the flat device list with grouped-by-server layout

patch(SERVER_PY,
    '                    React.createElement("div", {style: eduStyles.section}, "Storage Devices"),\n'
    '                    devices.map((dev, i) =>\n'
    '                        React.createElement("div", {key: i, style: {\n'
    '                            background: "var(--card-bg)",\n'
    '                            border: "1px solid var(--border)",\n'
    '                            borderRadius: "8px",\n'
    '                            padding: "1rem",\n'
    '                            marginBottom: "1rem"\n'
    '                        }},',

    '                    React.createElement("div", {style: eduStyles.section}, "Storage Devices"),\n'
    '                    // Group devices by server\n'
    '                    (() => {\n'
    '                        const byServer = {};\n'
    '                        devices.forEach(d => {\n'
    '                            const parts = (d.hostname || "local").split(":");\n'
    '                            const srv = parts[0];\n'
    '                            if (!byServer[srv]) byServer[srv] = [];\n'
    '                            byServer[srv].push(d);\n'
    '                        });\n'
    '                        return Object.entries(byServer).map(([srv, devs]) =>\n'
    '                            React.createElement("div", {key: srv, style: {marginBottom: "1.5rem"}},\n'
    '                                React.createElement("div", {style: {fontWeight: "bold", fontSize: "1.1rem", marginBottom: "0.5rem", opacity: 0.8}}, srv),\n'
    '                                React.createElement("div", {style: {display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "0.75rem"}},\n'
    '                                    ...devs.map((dev, i) =>\n'
    '                                        React.createElement("div", {key: i, style: {\n'
    '                                            background: "var(--card-bg)",\n'
    '                                            border: "1px solid var(--border)",\n'
    '                                            borderRadius: "8px",\n'
    '                                            padding: "1rem"\n'
    '                                        }},',

    "storage/group_by_server")


# Fix closing brackets for the grouped layout
patch(SERVER_PY,
    '                            dev.pools && dev.pools.length > 0 && React.createElement("div", {style: {marginTop: "0.75rem"}},\n'
    '                                React.createElement("div", {style: {fontWeight: "bold", marginBottom: "0.5rem"}}, "ZFS Pools"),\n'
    '                                dev.pools.map((pool, j) => React.createElement("div", {key: j, style: {\n'
    '                                    display: "flex", \n'
    '                                    justifyContent: "space-between",\n'
    '                                    padding: "0.25rem 0",\n'
    '                                    borderBottom: "1px solid var(--border)"\n'
    '                                }},\n'
    '                                    React.createElement("span", null, pool.name),\n'
    '                                    React.createElement("span", null,\n'
    '                                        React.createElement("span", {style: {color: healthColor(pool.health), marginRight: "1rem"}}, pool.health),\n'
    '                                        React.createElement("span", {style: {color: usageColor(pool.capacity_pct || 0)}}, (pool.capacity_pct || 0).toFixed(1) + "%")\n'
    '                                    )\n'
    '                                ))\n'
    '                            )\n'
    '                        )\n'
    '                    )\n'
    '                );',

    '                            dev.pools && dev.pools.length > 0 && React.createElement("div", {style: {marginTop: "0.75rem"}},\n'
    '                                React.createElement("div", {style: {fontWeight: "bold", marginBottom: "0.5rem"}}, "ZFS Pools"),\n'
    '                                dev.pools.map((pool, j) => React.createElement("div", {key: j, style: {\n'
    '                                    display: "flex", \n'
    '                                    justifyContent: "space-between",\n'
    '                                    padding: "0.25rem 0",\n'
    '                                    borderBottom: "1px solid var(--border)"\n'
    '                                }},\n'
    '                                    React.createElement("span", null, pool.name),\n'
    '                                    React.createElement("span", null,\n'
    '                                        React.createElement("span", {style: {color: healthColor(pool.health), marginRight: "1rem"}}, pool.health),\n'
    '                                        React.createElement("span", {style: {color: usageColor(pool.capacity_pct || 0)}}, (pool.capacity_pct || 0).toFixed(1) + "%")\n'
    '                                    )\n'
    '                                ))\n'
    '                            )\n'
    '                        )\n'
    '                    )\n'
    '                )\n'
    '            );\n'
    '        })();\n'
    '        })()\n'
    '                );',

    "storage/close_grouped_layout")


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
