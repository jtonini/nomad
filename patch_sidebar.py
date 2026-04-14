#!/usr/bin/env python3
"""
NØMAÐ Dashboard — Convert top nav bar to sidebar layout.

Matches the Console's sidebar organization:
- Clusters (dynamic tabs)
- Insights (first analytics item)
- Dynamics
- Monitoring group (Network, Resources, Activity, etc.)
- Education (new)
- System (Readiness, Report Issue)
- Theme toggle at bottom

Apply on badenpowell:
    cd ~/nomad
    python3 patch_sidebar.py
"""

import sys
from pathlib import Path

SERVER_PY = Path.home() / "nomad" / "nomad" / "viz" / "server.py"

if not SERVER_PY.exists():
    print(f"Error: {SERVER_PY} not found")
    sys.exit(1)

text = SERVER_PY.read_text()

# =====================================================================
# 1. Add sidebar CSS
# =====================================================================
# Find the existing nav CSS and replace with sidebar styles

sidebar_css = """
/* ── Sidebar Layout ─────────────────────────────── */
.app-layout {
    display: flex;
    height: 100vh;
    overflow: hidden;
}

.sidebar {
    width: 220px;
    min-width: 220px;
    height: 100vh;
    overflow-y: auto;
    background: var(--bg-primary);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
}

.sidebar-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 16px 16px;
    border-bottom: 1px solid var(--border);
}

.sidebar-logo-text {
    font-size: 16px;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: #00BACF;
}

.sidebar-logo-text .oslash {
    color: #B64326;
}

.sidebar-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--text-muted);
    padding: 12px 16px 4px;
    font-weight: 600;
}

.sidebar-sep {
    height: 1px;
    background: var(--border);
    margin: 8px 12px;
}

.sidebar-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 16px;
    cursor: pointer;
    color: var(--text-secondary);
    font-size: 13px;
    border-radius: 6px;
    margin: 1px 8px;
    transition: background 0.15s, color 0.15s;
    border: none;
    background: none;
    width: calc(100% - 16px);
    text-align: left;
}

.sidebar-item:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
}

.sidebar-item.active {
    background: var(--bg-secondary);
    color: #00BACF;
    font-weight: 600;
}

.sidebar-item .badge {
    margin-left: auto;
    background: var(--red-muted, #3b1c1c);
    color: var(--red, #f87171);
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 8px;
    font-weight: 600;
}

.sidebar-footer {
    border-top: 1px solid var(--border);
    padding: 12px 16px;
}

.sidebar-theme-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    cursor: pointer;
    color: var(--text-secondary);
    font-size: 13px;
    border-radius: 6px;
    margin: 1px 8px;
    border: none;
    background: none;
    width: calc(100% - 16px);
    text-align: left;
}

.sidebar-theme-btn:hover {
    background: var(--bg-secondary);
}

.main-content {
    flex: 1;
    overflow-y: auto;
    height: 100vh;
}

/* Hide old top nav */
.header { display: none !important; }
"""

# Find where to insert the CSS — after the existing theme CSS
css_insert_marker = "/* ── Theme Variables ──"
if css_insert_marker not in text:
    # Try alternate marker
    css_insert_marker = ".header {"
    
if css_insert_marker in text:
    # Insert sidebar CSS before the header CSS
    idx = text.find(css_insert_marker)
    text = text[:idx] + sidebar_css + "\n" + text[idx:]
    print("1. Added sidebar CSS")
else:
    print("1. SKIP — CSS marker not found")

# =====================================================================
# 2. Replace the nav/header JSX with sidebar
# =====================================================================
# The current nav is inside the App component's return.
# Find the header element and replace with sidebar layout.

# Find the old header/nav structure
old_nav_start = '                        <nav className="tabs">'
old_nav_end = '                    </header>'

# We need to find and replace the entire header block.
# Instead of complex find/replace, let's inject a Sidebar component
# and wrap the main content.

# Add Sidebar component before the App's return
sidebar_component = '''
        // ── Sidebar Component ──────────────────────────────────────
        function Sidebar({ activeTab, setActiveTab, clusters, nodes, theme, setTheme, setSelectedNode }) {
            const clusterEntries = Object.entries(clusters || {}).filter(([id, c]) => c.type !== 'workstation');
            
            const items = [
                { type: 'label', text: 'CLUSTERS' },
                ...clusterEntries.map(([id, cluster]) => {
                    const clusterNodes = Object.values(nodes || {}).filter(n => n.cluster === id);
                    const downCount = clusterNodes.filter(n => n.status === 'down').length;
                    return { id, label: cluster.name, badge: downCount > 0 ? downCount : null };
                }),
                { type: 'sep' },
                { type: 'label', text: 'ANALYTICS' },
                { id: 'insights', label: 'Insights' },
                { id: 'dynamics', label: 'Dynamics' },
                { type: 'sep' },
                { type: 'label', text: 'MONITORING' },
                { id: 'network', label: 'Network View' },
                { id: 'resources', label: 'Resources' },
                { id: 'activity', label: 'Activity' },
                { id: 'interactive', label: 'Interactive' },
                { id: 'workstations', label: 'Workstations' },
                { id: 'storage', label: 'Storage' },
                { id: 'cloud', label: 'Cloud' },
                { type: 'sep' },
                { type: 'label', text: 'EDUCATION' },
                { id: 'education', label: 'Education' },
                { type: 'sep' },
                { type: 'label', text: 'SYSTEM' },
                { id: 'readiness', label: 'Readiness' },
                { id: 'issue', label: 'Report Issue' },
            ];

            return (
                <div className="sidebar">
                    <div className="sidebar-logo">
                        <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'%3E%3Cdefs%3E%3Cstyle%3E.bg%7Bfill:%230a0a12%7D.ring%7Bfill:none;stroke:%2300BACF;stroke-width:6%7D.ring-inner%7Bfill:none;stroke:%2300BACF;stroke-width:3%7D.grid%7Bstroke:%2300BACF;stroke-width:1;opacity:.3%7D.oslash%7Bfont-family:Helvetica,Arial,sans-serif;font-size:28px;fill:%23B64326;font-weight:500%7D.needle-n%7Bfill:%23B64326%7D.needle-s%7Bfill:%2300BACF%7D.node%7Bfill:%2300BACF%7D.cardinal%7Bfont-family:Helvetica,Arial,sans-serif;font-size:10px;fill:%2300BACF;font-weight:500%7D%3C/style%3E%3C/defs%3E%3Ccircle class='bg' cx='100' cy='100' r='98'/%3E%3Ccircle class='ring' cx='100' cy='100' r='95'/%3E%3Ccircle class='ring-inner' cx='100' cy='100' r='60'/%3E%3Cg class='grid'%3E%3Cline x1='100' y1='5' x2='100' y2='195'/%3E%3Cline x1='5' y1='100' x2='195' y2='100'/%3E%3Cline x1='32' y1='32' x2='168' y2='168'/%3E%3Cline x1='168' y1='32' x2='32' y2='168'/%3E%3C/g%3E%3Ccircle class='grid' cx='100' cy='100' r='78' fill='none'/%3E%3Ccircle class='node' cx='100' cy='42' r='3'/%3E%3Ccircle class='node' cx='158' cy='100' r='3'/%3E%3Ccircle class='node' cx='100' cy='158' r='3'/%3E%3Ccircle class='node' cx='42' cy='100' r='3'/%3E%3Ctext class='cardinal' x='100' y='56' text-anchor='middle'%3EN%3C/text%3E%3Ctext class='cardinal' x='146' y='104' text-anchor='middle'%3EE%3C/text%3E%3Ctext class='cardinal' x='100' y='150' text-anchor='middle'%3ES%3C/text%3E%3Ctext class='cardinal' x='54' y='104' text-anchor='middle'%3EW%3C/text%3E%3Cg transform='rotate(45,100,100)'%3E%3Cpolygon class='needle-n' points='100,65 96,100 104,100'/%3E%3Cpolygon class='needle-s' points='100,135 104,100 96,100'/%3E%3C/g%3E%3Ccircle cx='100' cy='100' r='18' fill='%230a0a12' stroke='%2300BACF' stroke-width='2'/%3E%3Ctext class='oslash' x='100' y='108' text-anchor='middle'%3E%C3%98%3C/text%3E%3C/svg%3E"
                            style={{ width: 32, height: 32, borderRadius: 6 }}
                            alt="NØMAÐ" />
                        <div>
                            <div className="sidebar-logo-text">
                                N<span className="oslash">Ø</span>MAÐ
                            </div>
                            <div style={{ fontSize: 10, letterSpacing: 2, color: 'var(--text-muted)', fontWeight: 600 }}>
                                HPC MONITOR
                            </div>
                        </div>
                    </div>
                    
                    <nav style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
                        {items.map((item, i) => {
                            if (item.type === 'label') {
                                return <div key={i} className="sidebar-label">{item.text}</div>;
                            }
                            if (item.type === 'sep') {
                                return <div key={i} className="sidebar-sep" />;
                            }
                            return (
                                <button
                                    key={item.id}
                                    className={`sidebar-item ${activeTab === item.id ? 'active' : ''}`}
                                    onClick={() => { setActiveTab(item.id); setSelectedNode(null); }}
                                >
                                    {item.label}
                                    {item.badge && <span className="badge">{item.badge}</span>}
                                </button>
                            );
                        })}
                    </nav>
                    
                    <div className="sidebar-footer">
                        <button
                            className="sidebar-theme-btn"
                            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                        >
                            {theme === 'dark' ? '☀️' : '🌙'} {theme === 'dark' ? 'Light' : 'Dark'} Theme
                        </button>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 16px' }}>
                            v1.4.0 · database ({dataSource})
                        </div>
                    </div>
                </div>
            );
        }

'''

# Insert the Sidebar component before the App's return
# Find a good insertion point — before "if (!clusters"
insert_marker = "            if (!clusters || !nodes || !jobs || !edges || !activeTab) {"
if insert_marker in text:
    text = text.replace(insert_marker, sidebar_component + "\n" + insert_marker)
    print("2. Added Sidebar component")
else:
    print("2. SKIP — insert marker not found")


# =====================================================================
# 3. Wrap the return in sidebar layout
# =====================================================================
# Replace the old header-based layout with sidebar + main content

# The old return structure starts with:
#   return (
#     <div className="container" data-theme={theme}>
#       <header className="header">
#         ...
#       </header>
#       <main className="main-area">
#         ...
#       </main>
#     </div>
#   );

# We need to change it to:
#   return (
#     <div className="app-layout" data-theme={theme}>
#       <Sidebar ... />
#       <div className="main-content">
#         <main ...>
#           ...
#         </main>
#       </div>
#     </div>
#   );

old_container = '            return (\n                <div className="container" data-theme={theme}>'
new_container = '''            return (
                <div className="app-layout" data-theme={theme}>
                    <Sidebar
                        activeTab={activeTab}
                        setActiveTab={setActiveTab}
                        clusters={clusters}
                        nodes={nodes}
                        theme={theme}
                        setTheme={setTheme}
                        setSelectedNode={setSelectedNode}
                        dataSource={dataSource}
                    />
                    <div className="main-content">'''

if old_container in text:
    text = text.replace(old_container, new_container, 1)
    print("3. Replaced container with sidebar layout")
else:
    print("3. SKIP — container pattern not found")

# Close the main-content div before the container close
# Find the closing </div> for the container
old_close = '                </div>\n            );\n        }\n        \n        function ClusterView'
new_close = '                    </div>\n                </div>\n            );\n        }\n        \n        function ClusterView'
if old_close in text:
    text = text.replace(old_close, new_close, 1)
    print("4. Closed main-content div")
else:
    print("4. SKIP — close pattern not found")


# =====================================================================
# 5. Add Education panel placeholder
# =====================================================================
# Add after the DynamicsPanel or before ReportIssuePanel

edu_panel = '''
            // Education Panel
            const EducationPanel = () => {
                return React.createElement("div", {style: eduStyles.panel},
                    React.createElement("div", {style: eduStyles.section}, "Educational Analytics"),
                    React.createElement("div", {style: {padding: "2rem", textAlign: "center", opacity: 0.6}},
                        React.createElement("div", {style: {fontSize: "1.2rem", marginBottom: "0.5rem"}}, "Coming Soon"),
                        React.createElement("div", null,
                            "Job analysis, user trajectories, and group proficiency reports. ",
                            "Use the CLI in the meantime: ",
                            React.createElement("code", null, "nomad edu explain <job_id>")
                        )
                    )
                );
            };

'''

edu_marker = "            // Dynamics Panel"
if edu_marker in text:
    text = text.replace(edu_marker, edu_panel + "            // Dynamics Panel", 1)
    print("5. Added EducationPanel")
else:
    print("5. SKIP — Dynamics Panel marker not found")

# Wire EducationPanel into the tab switch
edu_route = "activeTab === 'education' ? (\n                            <EducationPanel />\n                        ) : "
# Find where to insert — before the cluster view fallback
cluster_fallback = "                            <>\n                                <ClusterView"
if cluster_fallback in text and edu_route not in text:
    text = text.replace(
        cluster_fallback,
        "                        " + edu_route + cluster_fallback,
        1
    )
    print("6. Wired EducationPanel to tab switch")
else:
    print("6. SKIP — tab switch pattern not found")


SERVER_PY.write_text(text)
print(f"\nDone. Verify with: python3 -c \"import py_compile; py_compile.compile('{SERVER_PY}', doraise=True)\"")
