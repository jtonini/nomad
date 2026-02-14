#!/usr/bin/env python3
"""
NOMADE HPC Analytics Patcher
==============================
Adds resource footprint tab and activity heatmap tab
to the NOMADE dashboard (server.py).

Usage:
    python3 patch_hpc_analytics.py /path/to/nomad/

Patches:
    1. nomad/collectors/__init__.py  - register GroupCollector
    2. nomad/cli.py                  - wire GroupCollector into collect()
    3. nomad/viz/server.py           - API endpoints + React tabs

Prerequisites:
    - Copy groups.py into nomad/collectors/groups.py
    - Then run this patch
"""

import sys
import shutil
from pathlib import Path


def patch_collectors_init(nomad_dir):
    """Add GroupCollector to collectors/__init__.py."""
    path = nomad_dir / 'collectors' / '__init__.py'
    if not path.exists():
        print(f"  ! {path} not found")
        return False

    content = path.read_text()
    changes = 0

    if 'GroupCollector' not in content:
        # Add import
        marker = "from .nfs import NFSCollector"
        if marker in content:
            content = content.replace(
                marker,
                marker + "\nfrom .groups import GroupCollector")
            changes += 1
        else:
            print("  ! Could not find NFS import marker")

        # Add to __all__
        marker = "'NFSCollector',"
        if marker in content:
            content = content.replace(
                marker,
                marker + "\n    'GroupCollector',")
            changes += 1
        elif "'NFSCollector'" in content:
            content = content.replace(
                "'NFSCollector'",
                "'NFSCollector',\n    'GroupCollector'")
            changes += 1

    if changes > 0:
        path.write_text(content)
        print(f"  + collectors/__init__.py ({changes} edits)")
    else:
        print("  = collectors/__init__.py (already patched)")
    return True


def patch_cli(nomad_dir):
    """Wire GroupCollector into cli.py collect() command."""
    path = nomad_dir / 'cli.py'
    if not path.exists():
        print(f"  ! {path} not found")
        return False

    content = path.read_text()
    changes = 0

    # Add import
    if 'GroupCollector' not in content:
        marker = "from nomad.collectors.nfs import NFSCollector"
        if marker in content:
            content = content.replace(
                marker,
                marker + "\n"
                "from nomad.collectors.groups import GroupCollector")
            changes += 1
        else:
            print("  ! Could not find NFS import in cli.py")

    # Add wiring
    wiring = '''
    # Group membership and job accounting collector
    groups_config = config.get('collectors', {}).get('groups', {})
    if not collector or 'groups' in collector:
        if groups_config.get('enabled', True):
            groups_config['clusters'] = config.get('clusters', {})
            collectors.append(GroupCollector(groups_config, db_path))
'''

    if "'groups' in collector" not in content:
        # Insert before interactive session collector
        marker = "    # Interactive session collector"
        if marker in content:
            content = content.replace(
                marker,
                wiring.rstrip() + "\n\n" + marker)
            changes += 1
        else:
            # Try after NFS block
            marker2 = "collectors.append(NFSCollector(nfs_config, db_path))"
            if marker2 in content:
                idx = content.index(marker2) + len(marker2)
                content = content[:idx] + "\n" + wiring + content[idx:]
                changes += 1

    if changes > 0:
        backup = path.with_suffix('.py.bak')
        shutil.copy(path, backup)
        path.write_text(content)
        print(f"  + cli.py ({changes} edits)")
    else:
        print("  = cli.py (already patched)")
    return True


def patch_server(nomad_dir):
    """Add API endpoints and React tabs to viz/server.py."""
    path = nomad_dir / 'viz' / 'server.py'
    if not path.exists():
        print(f"  ! viz/server.py not found")
        return False

    content = path.read_text()
    backup = path.with_suffix('.py.bak')
    shutil.copy(path, backup)
    print(f"  Backup: {backup.name}")
    changes = 0

    # ─────────────────────────────────────────────────────────────
    # 1. Insert Python API helper functions before DashboardHandler
    # ─────────────────────────────────────────────────────────────
    if 'query_resource_footprint' not in content:
        marker = "class DashboardHandler"
        if marker in content:
            idx = content.index(marker)
            content = content[:idx] + API_HELPERS + "\n\n" + content[idx:]
            changes += 1
            print("    + API helper functions")
        else:
            print("    ! Could not find DashboardHandler class")

    # ─────────────────────────────────────────────────────────────
    # 2. Insert API endpoints before send_error(404)
    # ─────────────────────────────────────────────────────────────
    if '/api/footprint' not in content:
        marker = "        else:\n            self.send_error(404)"
        if marker in content:
            content = content.replace(
                marker,
                API_ENDPOINTS + marker,
                1)
            changes += 1
            print("    + API endpoints")
        else:
            print("    ! Could not find send_error(404)")

    # ─────────────────────────────────────────────────────────────
    # 3. Insert tab buttons after "Network View" tab
    # ─────────────────────────────────────────────────────────────
    if "activeTab === 'resources'" not in content:
        # The exact text from server.py
        marker = (
            "                            >\n"
            "                                Network View\n"
            "                            </div>\n"
            "                        </nav>")
        if marker in content:
            tab_buttons = (
                "                            >\n"
                "                                Network View\n"
                "                            </div>\n"
                "                            <div\n"
                "                                className={`tab ${activeTab === 'resources' ? 'active' : ''}`}\n"
                "                                onClick={() => { setActiveTab('resources'); setSelectedNode(null); }}\n"
                "                            >\n"
                "                                Resources\n"
                "                            </div>\n"
                "                            <div\n"
                "                                className={`tab ${activeTab === 'activity' ? 'active' : ''}`}\n"
                "                                onClick={() => { setActiveTab('activity'); setSelectedNode(null); }}\n"
                "                            >\n"
                "                                Activity\n"
                "                            </div>\n"
                "                        </nav>")
            content = content.replace(marker, tab_buttons, 1)
            changes += 1
            print("    + Tab buttons (Resources, Activity)")
        else:
            # Try flexible match
            if "Network View" in content and "</nav>" in content:
                # Find "Network View" tab closing </div> followed by </nav>
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'Network View' in line:
                        # Find the next </nav>
                        for j in range(i, min(i + 5, len(lines))):
                            if '</nav>' in lines[j]:
                                insert = (
                                    '                            <div\n'
                                    '                                className={`tab ${activeTab === \'resources\' ? \'active\' : \'\'}`}\n'
                                    '                                onClick={() => { setActiveTab(\'resources\'); setSelectedNode(null); }}\n'
                                    '                            >\n'
                                    '                                Resources\n'
                                    '                            </div>\n'
                                    '                            <div\n'
                                    '                                className={`tab ${activeTab === \'activity\' ? \'active\' : \'\'}`}\n'
                                    '                                onClick={() => { setActiveTab(\'activity\'); setSelectedNode(null); }}\n'
                                    '                            >\n'
                                    '                                Activity\n'
                                    '                            </div>')
                                lines.insert(j, insert)
                                content = '\n'.join(lines)
                                changes += 1
                                print("    + Tab buttons (line-based)")
                                break
                        break
            if "activeTab === 'resources'" not in content:
                print("    ! Could not insert tab buttons")

    # ─────────────────────────────────────────────────────────────
    # 4. Extend conditional rendering (add resources/activity)
    # ─────────────────────────────────────────────────────────────
    if '<ResourcesPanel' not in content:
        # server.py goes:  activeTab === 'network' ? ( <NetworkView .../> ) : ( <>
        # We need to add resources and activity between network and default
        old_render = (
            "                        ) : (\n"
            "                            <>\n"
            "                                <ClusterView")
        new_render = (
            "                        ) : activeTab === 'resources' ? (\n"
            "                            <ResourcesPanel />\n"
            "                        ) : activeTab === 'activity' ? (\n"
            "                            <ActivityPanel />\n"
            "                        ) : (\n"
            "                            <>\n"
            "                                <ClusterView")
        if old_render in content:
            content = content.replace(old_render, new_render, 1)
            changes += 1
            print("    + Conditional rendering")
        else:
            print("    ! Could not find render block")
            print("      Looking for: ) : ( <> <ClusterView")

    # ─────────────────────────────────────────────────────────────
    # 5. Insert React component definitions before App useState
    # ─────────────────────────────────────────────────────────────
    if 'const ResourcesPanel' not in content:
        marker = "const [activeTab, setActiveTab] = useState(null);"
        if marker in content:
            idx = content.index(marker)
            # Walk backward to find a good insertion point
            # (before the App component function)
            search_back = content[max(0, idx - 500):idx]
            # Find the last function/const declaration
            insert_idx = idx  # Default: right before activeTab
            for lookback in ['const App', 'function App']:
                if lookback in search_back:
                    lb_idx = search_back.rindex(lookback)
                    insert_idx = max(0, idx - 500) + lb_idx
                    break

            content = (content[:insert_idx]
                       + REACT_COMPONENTS + "\n\n            "
                       + content[insert_idx:])
            changes += 1
            print("    + React components (ResourcesPanel, ActivityPanel)")
        else:
            print("    ! Could not find activeTab useState")

    if changes > 0:
        path.write_text(content)
        print(f"  + server.py ({changes} edits)")
    else:
        print("  = server.py (already patched)")
    return True


# =====================================================================
# API HELPERS (Python - inserted before DashboardHandler)
# =====================================================================
API_HELPERS = r'''
def query_resource_footprint(db_path, cluster='all', group='all', days=30):
    """Query resource footprint from job_accounting + group_membership."""
    import sqlite3 as _sql
    from datetime import datetime as _dt, timedelta as _td
    start = (_dt.now() - _td(days=int(days))).strftime('%Y-%m-%dT00:00:00')
    conn = _sql.connect(str(db_path))
    conn.row_factory = _sql.Row
    c = conn.cursor()
    tables = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    empty = {
        'groups': [], 'users': [],
        'totals': {'cpu_hours': 0, 'gpu_hours': 0, 'jobs': 0, 'users': 0},
        'filters': {'clusters': [], 'groups': []},
    }
    if 'job_accounting' not in tables:
        conn.close()
        return empty
    where = ["submit_time >= ?"]
    params = [start]
    if cluster != 'all':
        where.append("cluster = ?")
        params.append(cluster)
    c.execute("""
        SELECT username, cluster,
               SUM(cpu_hours) as cpu_hours,
               SUM(gpu_hours) as gpu_hours,
               COUNT(*) as jobs
        FROM job_accounting
        WHERE """ + " AND ".join(where) + """
        GROUP BY username, cluster
    """, params)
    user_rows = c.fetchall()
    grp_map = {}
    if 'group_membership' in tables:
        c.execute("SELECT username, group_name FROM group_membership")
        for row in c.fetchall():
            grp_map.setdefault(row['username'], []).append(row['group_name'])
    users = []
    user_set = set()
    for row in user_rows:
        u = row['username']
        user_set.add(u)
        ugroups = grp_map.get(u, [])
        if group != 'all' and group not in ugroups:
            continue
        users.append({
            'username': u, 'cluster': row['cluster'],
            'cpu_hours': round(row['cpu_hours'] or 0, 1),
            'gpu_hours': round(row['gpu_hours'] or 0, 1),
            'jobs': row['jobs'], 'groups': ugroups,
        })
    gtotals = {}
    for u in users:
        for g in u['groups']:
            if g not in gtotals:
                gtotals[g] = {'name': g, 'cpu_hours': 0,
                              'gpu_hours': 0, 'jobs': 0, 'users': set()}
            gtotals[g]['cpu_hours'] += u['cpu_hours']
            gtotals[g]['gpu_hours'] += u['gpu_hours']
            gtotals[g]['jobs'] += u['jobs']
            gtotals[g]['users'].add(u['username'])
    glist = sorted(gtotals.values(), key=lambda x: x['cpu_hours'], reverse=True)
    for g in glist:
        g['users'] = len(g['users'])
    c.execute("SELECT DISTINCT cluster FROM job_accounting")
    avail_clusters = [r[0] for r in c.fetchall()]
    avail_groups = sorted(gtotals.keys())
    conn.close()
    return {
        'groups': glist[:50],
        'users': sorted(users, key=lambda x: x['cpu_hours'], reverse=True)[:100],
        'totals': {
            'cpu_hours': round(sum(u['cpu_hours'] for u in users), 1),
            'gpu_hours': round(sum(u['gpu_hours'] for u in users), 1),
            'jobs': sum(u['jobs'] for u in users),
            'users': len(user_set),
        },
        'filters': {'clusters': avail_clusters, 'groups': avail_groups},
    }


def query_activity_heatmap(db_path, cluster='all', group='all', days=30):
    """Query activity heatmap from job_accounting submit times."""
    import sqlite3 as _sql
    from datetime import datetime as _dt, timedelta as _td
    start = (_dt.now() - _td(days=int(days))).strftime('%Y-%m-%dT00:00:00')
    conn = _sql.connect(str(db_path))
    conn.row_factory = _sql.Row
    c = conn.cursor()
    tables = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    empty = {
        'grid': [[0]*24 for _ in range(7)], 'max_value': 0,
        'total_jobs': 0, 'busiest': None, 'quietest': None,
        'filters': {'clusters': [], 'groups': []},
    }
    if 'job_accounting' not in tables:
        conn.close()
        return empty
    group_users = None
    if group != 'all' and 'group_membership' in tables:
        c.execute(
            "SELECT username FROM group_membership WHERE group_name = ?",
            (group,))
        group_users = set(r[0] for r in c.fetchall())
    where = ["submit_time >= ?", "submit_time IS NOT NULL"]
    params = [start]
    if cluster != 'all':
        where.append("cluster = ?")
        params.append(cluster)
    c.execute("""
        SELECT submit_time, username
        FROM job_accounting WHERE """ + " AND ".join(where) + """
    """, params)
    grid = [[0]*24 for _ in range(7)]
    total = 0
    for row in c.fetchall():
        if group_users is not None and row['username'] not in group_users:
            continue
        try:
            dt = _dt.strptime(row['submit_time'][:19], '%Y-%m-%dT%H:%M:%S')
            grid[dt.weekday()][dt.hour] += 1
            total += 1
        except (ValueError, TypeError):
            continue
    max_val = 0
    busiest = {'day': 'Monday', 'hour': 0, 'count': 0}
    quietest = {'day': 'Monday', 'hour': 0, 'count': 999999}
    dnames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
              'Friday', 'Saturday', 'Sunday']
    for di in range(7):
        for hi in range(24):
            v = grid[di][hi]
            if v > max_val:
                max_val = v
                busiest = {'day': dnames[di], 'hour': hi, 'count': v}
            if v < quietest['count']:
                quietest = {'day': dnames[di], 'hour': hi, 'count': v}
    if quietest['count'] == 999999:
        quietest['count'] = 0
    c.execute("SELECT DISTINCT cluster FROM job_accounting")
    avail_clusters = [r[0] for r in c.fetchall()]
    avail_groups = []
    if 'group_membership' in tables:
        c.execute(
            "SELECT DISTINCT group_name FROM group_membership ORDER BY group_name")
        avail_groups = [r[0] for r in c.fetchall()]
    conn.close()
    return {
        'grid': grid, 'max_value': max_val, 'total_jobs': total,
        'busiest': busiest, 'quietest': quietest,
        'filters': {'clusters': avail_clusters, 'groups': avail_groups},
    }
'''

# =====================================================================
# API ENDPOINTS (inserted before send_error(404))
# =====================================================================
API_ENDPOINTS = r'''        elif parsed.path.startswith('/api/footprint'):
            query = parse_qs(parsed.query)
            fp_cluster = query.get('cluster', ['all'])[0]
            fp_group = query.get('group', ['all'])[0]
            fp_days = int(query.get('days', [30])[0])
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            dm = DashboardHandler.data_manager
            result = query_resource_footprint(
                dm.db_path, fp_cluster, fp_group, fp_days)
            self.wfile.write(json.dumps(result).encode())
        elif parsed.path.startswith('/api/heatmap'):
            query = parse_qs(parsed.query)
            hm_cluster = query.get('cluster', ['all'])[0]
            hm_group = query.get('group', ['all'])[0]
            hm_days = int(query.get('days', [30])[0])
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            dm = DashboardHandler.data_manager
            result = query_activity_heatmap(
                dm.db_path, hm_cluster, hm_group, hm_days)
            self.wfile.write(json.dumps(result).encode())
        elif parsed.path == '/api/groups':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            dm = DashboardHandler.data_manager
            try:
                import sqlite3 as _sql
                conn = _sql.connect(str(dm.db_path))
                conn.row_factory = _sql.Row
                c = conn.cursor()
                c.execute("""
                    SELECT group_name, cluster, COUNT(*) as members
                    FROM group_membership
                    GROUP BY group_name, cluster
                    ORDER BY group_name
                """)
                groups = [dict(r) for r in c.fetchall()]
                conn.close()
            except Exception:
                groups = []
            self.wfile.write(json.dumps({'groups': groups}).encode())
'''

# =====================================================================
# REACT COMPONENTS (inserted before App component)
# =====================================================================
REACT_COMPONENTS = r'''
            const eduStyles = {
                panel: { padding: '24px', maxWidth: '1200px', margin: '0 auto' },
                filterBar: { display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap' },
                select: { padding: '8px 12px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.05)', color: '#e0e0e0', fontSize: '14px', cursor: 'pointer' },
                cards: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px', marginBottom: '32px' },
                card: { background: 'rgba(255,255,255,0.04)', borderRadius: '10px', padding: '20px', textAlign: 'center', border: '1px solid rgba(255,255,255,0.06)' },
                cardValue: { fontSize: '28px', fontWeight: '700', color: '#e0e0e0', fontVariantNumeric: 'tabular-nums' },
                cardLabel: { fontSize: '12px', color: '#808080', marginTop: '4px', textTransform: 'uppercase', letterSpacing: '0.5px' },
                section: { fontSize: '16px', fontWeight: '600', color: '#c0c0c0', marginBottom: '16px', marginTop: '8px' },
                barRow: { display: 'flex', alignItems: 'center', marginBottom: '8px', gap: '12px' },
                barLabel: { width: '140px', fontSize: '13px', color: '#c0c0c0', textAlign: 'right', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
                barTrack: { flex: 1, height: '22px', background: 'rgba(255,255,255,0.04)', borderRadius: '4px', overflow: 'hidden' },
                barFill: { height: '100%', background: 'linear-gradient(90deg, #22c55e, #4ade80)', borderRadius: '4px', transition: 'width 0.3s', minWidth: '2px' },
                barValue: { width: '160px', fontSize: '12px', color: '#808080', flexShrink: 0 },
                table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
                th: { textAlign: 'left', padding: '10px 12px', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#808080', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', cursor: 'pointer', userSelect: 'none' },
                thNum: { textAlign: 'right', padding: '10px 12px', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#808080', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', cursor: 'pointer', userSelect: 'none' },
                td: { padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.04)', color: '#c0c0c0' },
                tdNum: { padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.04)', color: '#c0c0c0', textAlign: 'right', fontVariantNumeric: 'tabular-nums' },
                loading: { padding: '60px', textAlign: 'center', color: '#808080', fontSize: '15px' },
                hmRow: { display: 'flex', gap: '2px', marginBottom: '2px' },
                hmDayLabel: { width: '40px', fontSize: '11px', color: '#808080', textAlign: 'right', paddingRight: '8px', lineHeight: '20px', flexShrink: 0 },
                hmCell: { width: '100%', maxWidth: '40px', height: '20px', borderRadius: '3px', cursor: 'default', flex: 1 },
                hmHeader: { display: 'flex', gap: '2px', marginBottom: '4px' },
                hmHourLabel: { width: '100%', maxWidth: '40px', fontSize: '9px', color: '#606060', textAlign: 'center', flex: 1 },
                hmLabelCell: { width: '40px', paddingRight: '8px', flexShrink: 0 },
                legend: { display: 'flex', alignItems: 'center', gap: '8px', marginTop: '16px', justifyContent: 'center' },
                legendLabel: { fontSize: '11px', color: '#606060' },
                legendBar: { display: 'flex', gap: '1px', borderRadius: '3px', overflow: 'hidden' },
            };

            const ResourcesPanel = () => {
                const [data, setData] = useState(null);
                const [filters, setFilters] = useState({cluster: 'all', group: 'all', days: '30'});
                const [sort, setSort] = useState({by: 'cpu_hours', dir: 'desc'});
                useEffect(() => {
                    const {cluster, group, days} = filters;
                    fetch('/api/footprint?cluster=' + cluster + '&group=' + group + '&days=' + days)
                        .then(r => r.json()).then(setData).catch(() => setData(null));
                }, [filters]);
                if (!data) return React.createElement('div', {style: eduStyles.loading}, 'Loading resource data...');
                const maxCpu = Math.max(...data.groups.map(g => g.cpu_hours), 1);
                const sorted_users = [...(data.users || [])].sort((a, b) => {
                    if (sort.by === 'username') return sort.dir === 'asc' ? a.username.localeCompare(b.username) : b.username.localeCompare(a.username);
                    return sort.dir === 'desc' ? (b[sort.by] || 0) - (a[sort.by] || 0) : (a[sort.by] || 0) - (b[sort.by] || 0);
                });
                const doSort = (col) => setSort({by: col, dir: sort.by === col && sort.dir === 'desc' ? 'asc' : 'desc'});
                const arrow = (col) => sort.by === col ? (sort.dir === 'asc' ? ' ^' : ' v') : '';
                const FilterBar = () => React.createElement('div', {style: eduStyles.filterBar},
                    React.createElement('select', {value: filters.cluster, onChange: e => setFilters({...filters, cluster: e.target.value}), style: eduStyles.select},
                        React.createElement('option', {value: 'all'}, 'All Clusters'),
                        (data.filters.clusters || []).map(c => React.createElement('option', {key: c, value: c}, c))
                    ),
                    React.createElement('select', {value: filters.group, onChange: e => setFilters({...filters, group: e.target.value}), style: eduStyles.select},
                        React.createElement('option', {value: 'all'}, 'All Groups'),
                        (data.filters.groups || []).map(g => React.createElement('option', {key: g, value: g}, g))
                    ),
                    React.createElement('select', {value: filters.days, onChange: e => setFilters({...filters, days: e.target.value}), style: eduStyles.select},
                        React.createElement('option', {value: '7'}, 'Last 7 days'),
                        React.createElement('option', {value: '30'}, 'Last 30 days'),
                        React.createElement('option', {value: '90'}, 'Last 90 days'),
                        React.createElement('option', {value: '365'}, 'Last year')
                    )
                );
                return React.createElement('div', {style: eduStyles.panel},
                    React.createElement(FilterBar),
                    React.createElement('div', {style: eduStyles.cards},
                        React.createElement('div', {style: eduStyles.card},
                            React.createElement('div', {style: eduStyles.cardValue}, Math.round(data.totals.cpu_hours).toLocaleString()),
                            React.createElement('div', {style: eduStyles.cardLabel}, 'CPU-hours')
                        ),
                        React.createElement('div', {style: eduStyles.card},
                            React.createElement('div', {style: eduStyles.cardValue}, Math.round(data.totals.gpu_hours).toLocaleString()),
                            React.createElement('div', {style: eduStyles.cardLabel}, 'GPU-hours')
                        ),
                        React.createElement('div', {style: eduStyles.card},
                            React.createElement('div', {style: eduStyles.cardValue}, (data.totals.jobs || 0).toLocaleString()),
                            React.createElement('div', {style: eduStyles.cardLabel}, 'Jobs')
                        ),
                        React.createElement('div', {style: eduStyles.card},
                            React.createElement('div', {style: eduStyles.cardValue}, data.totals.users || 0),
                            React.createElement('div', {style: eduStyles.cardLabel}, 'Users')
                        )
                    ),
                    data.groups.length > 0 && React.createElement('div', null,
                        React.createElement('div', {style: eduStyles.section}, 'Resource Usage by Group'),
                        React.createElement('div', {style: {marginBottom: '32px'}},
                            data.groups.map(g => React.createElement('div', {key: g.name, style: eduStyles.barRow},
                                React.createElement('div', {style: eduStyles.barLabel, title: g.name}, g.name),
                                React.createElement('div', {style: eduStyles.barTrack},
                                    React.createElement('div', {style: {...eduStyles.barFill, width: (g.cpu_hours / maxCpu * 100) + '%'}})
                                ),
                                React.createElement('div', {style: eduStyles.barValue},
                                    Math.round(g.cpu_hours).toLocaleString() + ' CPU-hrs' +
                                    (g.gpu_hours > 0 ? ' / ' + Math.round(g.gpu_hours).toLocaleString() + ' GPU-hrs' : '') +
                                    ' (' + g.users + ' users)'
                                )
                            ))
                        )
                    ),
                    React.createElement('div', {style: eduStyles.section}, 'User Breakdown'),
                    React.createElement('table', {style: eduStyles.table},
                        React.createElement('thead', null,
                            React.createElement('tr', null,
                                React.createElement('th', {style: eduStyles.th, onClick: () => doSort('username')}, 'User' + arrow('username')),
                                React.createElement('th', {style: eduStyles.thNum, onClick: () => doSort('cpu_hours')}, 'CPU-hrs' + arrow('cpu_hours')),
                                React.createElement('th', {style: eduStyles.thNum, onClick: () => doSort('gpu_hours')}, 'GPU-hrs' + arrow('gpu_hours')),
                                React.createElement('th', {style: eduStyles.thNum, onClick: () => doSort('jobs')}, 'Jobs' + arrow('jobs')),
                                React.createElement('th', {style: eduStyles.th}, 'Groups')
                            )
                        ),
                        React.createElement('tbody', null,
                            sorted_users.slice(0, 50).map(u => React.createElement('tr', {key: u.username + u.cluster},
                                React.createElement('td', {style: eduStyles.td}, u.username),
                                React.createElement('td', {style: eduStyles.tdNum}, Math.round(u.cpu_hours).toLocaleString()),
                                React.createElement('td', {style: eduStyles.tdNum}, Math.round(u.gpu_hours).toLocaleString()),
                                React.createElement('td', {style: eduStyles.tdNum}, u.jobs),
                                React.createElement('td', {style: eduStyles.td}, (u.groups || []).join(', '))
                            ))
                        )
                    )
                );
            };

            const ActivityPanel = () => {
                const [data, setData] = useState(null);
                const [filters, setFilters] = useState({cluster: 'all', group: 'all', days: '30'});
                useEffect(() => {
                    const {cluster, group, days} = filters;
                    fetch('/api/heatmap?cluster=' + cluster + '&group=' + group + '&days=' + days)
                        .then(r => r.json()).then(setData).catch(() => setData(null));
                }, [filters]);
                if (!data) return React.createElement('div', {style: eduStyles.loading}, 'Loading activity data...');
                const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
                const getColor = (v) => {
                    if (!v) return 'rgba(255,255,255,0.03)';
                    const i = Math.min(v / (data.max_value || 1), 1);
                    return 'rgb(' + Math.round(20 + i * 20) + ',' + Math.round(40 + i * 180) + ',' + Math.round(20 + i * 60) + ')';
                };
                const FilterBar = () => React.createElement('div', {style: eduStyles.filterBar},
                    React.createElement('select', {value: filters.cluster, onChange: e => setFilters({...filters, cluster: e.target.value}), style: eduStyles.select},
                        React.createElement('option', {value: 'all'}, 'All Clusters'),
                        (data.filters.clusters || []).map(c => React.createElement('option', {key: c, value: c}, c))
                    ),
                    React.createElement('select', {value: filters.group, onChange: e => setFilters({...filters, group: e.target.value}), style: eduStyles.select},
                        React.createElement('option', {value: 'all'}, 'All Groups'),
                        (data.filters.groups || []).map(g => React.createElement('option', {key: g, value: g}, g))
                    ),
                    React.createElement('select', {value: filters.days, onChange: e => setFilters({...filters, days: e.target.value}), style: eduStyles.select},
                        React.createElement('option', {value: '7'}, 'Last 7 days'),
                        React.createElement('option', {value: '30'}, 'Last 30 days'),
                        React.createElement('option', {value: '90'}, 'Last 90 days'),
                        React.createElement('option', {value: '365'}, 'Last year')
                    )
                );
                return React.createElement('div', {style: eduStyles.panel},
                    React.createElement(FilterBar),
                    React.createElement('div', {style: eduStyles.cards},
                        React.createElement('div', {style: eduStyles.card},
                            React.createElement('div', {style: eduStyles.cardValue}, (data.total_jobs || 0).toLocaleString()),
                            React.createElement('div', {style: eduStyles.cardLabel}, 'Total Jobs')
                        ),
                        data.busiest && React.createElement('div', {style: eduStyles.card},
                            React.createElement('div', {style: eduStyles.cardValue}, data.busiest.day + ' ' + data.busiest.hour + ':00'),
                            React.createElement('div', {style: eduStyles.cardLabel}, 'Busiest Hour (' + data.busiest.count + ' jobs)')
                        ),
                        data.quietest && React.createElement('div', {style: eduStyles.card},
                            React.createElement('div', {style: eduStyles.cardValue}, data.quietest.day + ' ' + data.quietest.hour + ':00'),
                            React.createElement('div', {style: eduStyles.cardLabel}, 'Quietest Hour')
                        )
                    ),
                    React.createElement('div', {style: eduStyles.section}, 'Job Submissions by Day and Hour'),
                    React.createElement('div', {style: {marginBottom: '32px'}},
                        React.createElement('div', {style: eduStyles.hmHeader},
                            React.createElement('div', {style: eduStyles.hmLabelCell}),
                            Array.from({length: 24}, (_, i) => React.createElement('div', {key: i, style: eduStyles.hmHourLabel}, i % 3 === 0 ? i + 'h' : ''))
                        ),
                        data.grid.map((row, di) => React.createElement('div', {key: di, style: eduStyles.hmRow},
                            React.createElement('div', {style: eduStyles.hmDayLabel}, dayNames[di]),
                            row.map((v, hi) => React.createElement('div', {
                                key: hi,
                                style: {...eduStyles.hmCell, backgroundColor: getColor(v)},
                                title: dayNames[di] + ' ' + hi + ':00 -- ' + v + ' jobs'
                            }))
                        ))
                    ),
                    React.createElement('div', {style: eduStyles.legend},
                        React.createElement('span', {style: eduStyles.legendLabel}, 'Less'),
                        React.createElement('div', {style: eduStyles.legendBar},
                            [0, 0.2, 0.4, 0.6, 0.8, 1.0].map(i => React.createElement('div', {
                                key: i,
                                style: {width: '16px', height: '12px', backgroundColor: 'rgb(' + Math.round(20+i*20) + ',' + Math.round(40+i*180) + ',' + Math.round(20+i*60) + ')'}
                            }))
                        ),
                        React.createElement('span', {style: eduStyles.legendLabel}, 'More')
                    )
                );
            };

'''


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python3 patch_hpc_analytics.py"
            " /path/to/nomad/")
        print()
        print("Prerequisites:")
        print("  1. Copy groups.py to"
              " nomad/collectors/groups.py")
        print("  2. Then run this patch")
        sys.exit(1)

    nomad_dir = Path(sys.argv[1])

    # Handle both /path/to/nomad/ and /path/to/nomad/nomad/
    if (nomad_dir / 'collectors').exists():
        pass
    elif (nomad_dir / 'nomad' / 'collectors').exists():
        nomad_dir = nomad_dir / 'nomad'
    else:
        print(f"ERROR: Could not find collectors/ in {nomad_dir}")
        sys.exit(1)

    # Check that groups.py exists
    groups_py = nomad_dir / 'collectors' / 'groups.py'
    if not groups_py.exists():
        print(f"ERROR: {groups_py} not found")
        print()
        print("Copy groups.py first:")
        print(f"  cp groups.py {groups_py}")
        sys.exit(1)

    # Check that server.py exists
    server_py = nomad_dir / 'viz' / 'server.py'
    if not server_py.exists():
        print(f"ERROR: {server_py} not found")
        sys.exit(1)

    print()
    print("NOMADE HPC Analytics Patch")
    print("=" * 40)
    print(f"Target: {nomad_dir}")
    print()

    ok1 = patch_collectors_init(nomad_dir)
    ok2 = patch_cli(nomad_dir)
    ok3 = patch_server(nomad_dir)

    print()
    if ok1 and ok2 and ok3:
        print("Done! New features:")
        print("  - Group membership collector")
        print("  - Resources tab (resource footprint)")
        print("  - Activity tab (submission heatmap)")
        print()
        print("Test:")
        print("  nomad collect -C groups --once")
        print("  nomad dashboard")
    else:
        print("Some patches may need manual attention.")


if __name__ == '__main__':
    main()
