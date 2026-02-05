#!/usr/bin/env python3
"""
NOMADE Edu Features Patcher
============================
Adds group membership collector wiring, resource footprint tab,
and activity heatmap tab to the NOMADE dashboard.

Usage:
    python3 patch_edu_features.py /path/to/nomade/

Patches:
    1. nomade/collectors/__init__.py  - register GroupCollector
    2. nomade/cli.py                  - wire GroupCollector into collect()
    3. nomade/viz/dashboard.py        - API endpoints + React tabs

Prerequisites:
    - Copy groups.py into nomade/collectors/groups.py
    - Then run this patch
"""

import sys
import shutil
from pathlib import Path


# =====================================================================
# NEW CODE TO INSERT
# =====================================================================

# -- For collectors/__init__.py --
GROUPS_IMPORT = "from .groups import GroupCollector"
GROUPS_ALLALL = "'GroupCollector'"

# -- For cli.py --
CLI_IMPORT = "from nomade.collectors.groups import GroupCollector"

CLI_WIRING = '''
    # Group membership and job accounting collector
    groups_config = config.get('collectors', {}).get('groups', {})
    if not collector or 'groups' in collector:
        if groups_config.get('enabled', True):
            groups_config['clusters'] = config.get('clusters', {})
            collectors.append(GroupCollector(groups_config, db_path))
'''

# -- For dashboard.py: Python API helper functions --
API_HELPERS = r'''

def query_resource_footprint(db_path, cluster='all', group='all', days=30):
    """Query resource footprint from job_accounting + group_membership."""
    from datetime import datetime as _dt, timedelta as _td
    start = (_dt.now() - _td(days=int(days))).strftime('%Y-%m-%dT00:00:00')
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
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
    c.execute(f"""
        SELECT username, cluster,
               SUM(cpu_hours) as cpu_hours,
               SUM(gpu_hours) as gpu_hours,
               COUNT(*) as jobs
        FROM job_accounting
        WHERE {" AND ".join(where)}
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
        'groups': glist[:20],
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
    from datetime import datetime as _dt, timedelta as _td
    start = (_dt.now() - _td(days=int(days))).strftime('%Y-%m-%dT00:00:00')
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
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
    c.execute(f"""
        SELECT submit_time, username
        FROM job_accounting WHERE {" AND ".join(where)}
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
            "SELECT DISTINCT group_name FROM group_membership"
            " ORDER BY group_name")
        avail_groups = [r[0] for r in c.fetchall()]
    conn.close()
    return {
        'grid': grid, 'max_value': max_val, 'total_jobs': total,
        'busiest': busiest, 'quietest': quietest,
        'filters': {'clusters': avail_clusters, 'groups': avail_groups},
    }

'''

# -- For dashboard.py: API endpoint handlers --
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
                conn = sqlite3.connect(str(dm.db_path))
                conn.row_factory = sqlite3.Row
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

# -- For dashboard.py: new React tab buttons (after Interactive tab) --
TAB_BUTTONS = r'''
                            <div
                                className={`tab ${activeTab === 'resources' ? 'active' : ''}`}
                                onClick={() => { setActiveTab('resources'); setSelectedNode(null); }}
                            >
                                Resources
                            </div>
                            <div
                                className={`tab ${activeTab === 'activity' ? 'active' : ''}`}
                                onClick={() => { setActiveTab('activity'); setSelectedNode(null); }}
                            >
                                Activity
                            </div>'''

# -- For dashboard.py: conditional rendering extension --
RENDER_OLD = (
    ") : activeTab === 'interactive' ? (\n"
    "                            <InteractiveView />\n"
    "                        ) : ("
)

RENDER_NEW = (
    ") : activeTab === 'interactive' ? (\n"
    "                            <InteractiveView />\n"
    "                        ) : activeTab === 'resources' ? (\n"
    "                            <ResourcesPanel />\n"
    "                        ) : activeTab === 'activity' ? (\n"
    "                            <ActivityPanel />\n"
    "                        ) : ("
)

# -- For dashboard.py: React component definitions --
# These get inserted before the App component declaration
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
                barChart: { marginBottom: '32px' },
                barRow: { display: 'flex', alignItems: 'center', marginBottom: '8px', gap: '12px' },
                barLabel: { width: '140px', fontSize: '13px', color: '#c0c0c0', textAlign: 'right', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
                barTrack: { flex: 1, height: '22px', background: 'rgba(255,255,255,0.04)', borderRadius: '4px', overflow: 'hidden' },
                barFill: { height: '100%', background: 'linear-gradient(90deg, #22c55e, #4ade80)', borderRadius: '4px', transition: 'width 0.3s', minWidth: '2px' },
                barGpu: { height: '100%', background: 'linear-gradient(90deg, #3b82f6, #60a5fa)', borderRadius: '4px', transition: 'width 0.3s', minWidth: '2px' },
                barValue: { width: '130px', fontSize: '12px', color: '#808080', flexShrink: 0 },
                table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
                th: { textAlign: 'left', padding: '10px 12px', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#808080', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', cursor: 'pointer', userSelect: 'none' },
                thNum: { textAlign: 'right', padding: '10px 12px', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#808080', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', cursor: 'pointer', userSelect: 'none' },
                td: { padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.04)', color: '#c0c0c0' },
                tdNum: { padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.04)', color: '#c0c0c0', textAlign: 'right', fontVariantNumeric: 'tabular-nums' },
                loading: { padding: '60px', textAlign: 'center', color: '#808080', fontSize: '15px' },
                heatmap: { marginBottom: '32px' },
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
                const maxGpu = Math.max(...data.groups.map(g => g.gpu_hours), 1);
                const sorted_users = [...(data.users || [])].sort((a, b) => {
                    if (sort.by === 'username') return sort.dir === 'asc' ? a.username.localeCompare(b.username) : b.username.localeCompare(a.username);
                    return sort.dir === 'desc' ? (b[sort.by] || 0) - (a[sort.by] || 0) : (a[sort.by] || 0) - (b[sort.by] || 0);
                });
                const doSort = (col) => setSort({by: col, dir: sort.by === col && sort.dir === 'desc' ? 'asc' : 'desc'});
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
                        React.createElement('div', {style: eduStyles.barChart},
                            data.groups.map(g => React.createElement('div', {key: g.name, style: eduStyles.barRow},
                                React.createElement('div', {style: eduStyles.barLabel}, g.name),
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
                                React.createElement('th', {style: eduStyles.th, onClick: () => doSort('username')}, 'User' + (sort.by === 'username' ? (sort.dir === 'asc' ? ' \u25B2' : ' \u25BC') : '')),
                                React.createElement('th', {style: eduStyles.thNum, onClick: () => doSort('cpu_hours')}, 'CPU-hrs' + (sort.by === 'cpu_hours' ? (sort.dir === 'asc' ? ' \u25B2' : ' \u25BC') : '')),
                                React.createElement('th', {style: eduStyles.thNum, onClick: () => doSort('gpu_hours')}, 'GPU-hrs' + (sort.by === 'gpu_hours' ? (sort.dir === 'asc' ? ' \u25B2' : ' \u25BC') : '')),
                                React.createElement('th', {style: eduStyles.thNum, onClick: () => doSort('jobs')}, 'Jobs' + (sort.by === 'jobs' ? (sort.dir === 'asc' ? ' \u25B2' : ' \u25BC') : '')),
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
                    React.createElement('div', {style: eduStyles.heatmap},
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


# =====================================================================
# PATCH FUNCTIONS
# =====================================================================

def patch_collectors_init(nomade_dir):
    """Add GroupCollector to collectors/__init__.py."""
    path = nomade_dir / 'collectors' / '__init__.py'
    if not path.exists():
        print(f"  ! {path} not found")
        return False

    content = path.read_text()
    changes = 0

    # Add import
    if 'GroupCollector' not in content:
        marker = "from .nfs import NFSCollector"
        if marker in content:
            content = content.replace(
                marker,
                marker + "\n" + GROUPS_IMPORT)
            changes += 1
        else:
            print("  ! Could not find NFS import marker")

    # Add to __all__
    if "'GroupCollector'" not in content:
        marker = "'NFSCollector',"
        if marker in content:
            content = content.replace(
                marker,
                marker + "\n    " + GROUPS_ALLALL + ",")
            changes += 1
        else:
            # Try without trailing comma
            marker2 = "'NFSCollector'"
            if marker2 in content:
                content = content.replace(
                    marker2,
                    marker2 + ",\n    " + GROUPS_ALLALL)
                changes += 1

    if changes > 0:
        path.write_text(content)
        print(f"  + collectors/__init__.py ({changes} edits)")
        return True
    else:
        print("  = collectors/__init__.py (already patched)")
        return True


def patch_cli(nomade_dir):
    """Wire GroupCollector into cli.py collect() command."""
    path = nomade_dir / 'cli.py'
    if not path.exists():
        print(f"  ! {path} not found")
        return False

    content = path.read_text()
    changes = 0

    # Add import
    if 'GroupCollector' not in content:
        marker = "from nomade.collectors.nfs import NFSCollector"
        if marker in content:
            content = content.replace(
                marker,
                marker + "\n" + CLI_IMPORT)
            changes += 1
        else:
            print("  ! Could not find NFS import in cli.py")

    # Add wiring (insert after NFS collector block)
    if "'groups' in collector" not in content:
        # Find the interactive session collector comment
        # and insert before it
        marker = "    # Interactive session collector"
        if marker in content:
            content = content.replace(
                marker,
                CLI_WIRING.rstrip() + "\n\n" + marker)
            changes += 1
        else:
            # Try inserting after NFS block
            marker2 = "collectors.append(NFSCollector(nfs_config, db_path))"
            if marker2 in content:
                # Find the end of the NFS if-block
                idx = content.index(marker2) + len(marker2)
                content = (content[:idx] + "\n"
                           + CLI_WIRING + content[idx:])
                changes += 1
            else:
                print("  ! Could not find insertion point for"
                      " collector wiring")

    if changes > 0:
        backup = path.with_suffix('.py.bak')
        shutil.copy(path, backup)
        path.write_text(content)
        print(f"  + cli.py ({changes} edits)")
        return True
    else:
        print("  = cli.py (already patched)")
        return True


def patch_dashboard(nomade_dir):
    """Add API endpoints and React tabs to dashboard.py."""
    path = nomade_dir / 'viz' / 'dashboard.py'
    if not path.exists():
        print(f"  ! {path} not found")
        return False

    content = path.read_text()
    changes = 0

    # 1. Insert API helper functions before DashboardHandler class
    if 'query_resource_footprint' not in content:
        marker = "class DashboardHandler"
        if marker in content:
            idx = content.index(marker)
            content = (content[:idx]
                       + API_HELPERS
                       + "\n" + content[idx:])
            changes += 1
            print("    + API helper functions")
        else:
            print("    ! Could not find DashboardHandler class")

    # 2. Insert API endpoints before send_error(404)
    if '/api/footprint' not in content:
        marker = "        else:\n            self.send_error(404)"
        if marker in content:
            content = content.replace(
                marker,
                API_ENDPOINTS + marker)
            changes += 1
            print("    + API endpoints (/api/footprint,"
                  " /api/heatmap, /api/groups)")
        else:
            print("    ! Could not find send_error(404) marker")

    # 3. Insert tab buttons after Interactive tab
    if "activeTab === 'resources'" not in content:
        marker = (
            "                                Interactive\n"
            "                            </div>")
        # Also try with different whitespace
        markers = [
            marker,
            "Interactive\n                            </div>",
        ]
        inserted = False
        for m in markers:
            if m in content:
                content = content.replace(
                    m, m + TAB_BUTTONS, 1)
                changes += 1
                inserted = True
                print("    + Tab buttons (Resources, Activity)")
                break
        if not inserted:
            # Try line-based approach
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if ('Interactive' in line
                        and '</div>' in line):
                    lines.insert(i + 1, TAB_BUTTONS)
                    content = '\n'.join(lines)
                    changes += 1
                    inserted = True
                    print("    + Tab buttons (line-based)")
                    break
                if ('Interactive' in line
                        and i + 1 < len(lines)
                        and '</div>' in lines[i + 1]):
                    lines.insert(i + 2, TAB_BUTTONS)
                    content = '\n'.join(lines)
                    changes += 1
                    inserted = True
                    print("    + Tab buttons (line-based, 2-line)")
                    break
            if not inserted:
                print("    ! Could not find Interactive tab marker")

    # 4. Extend conditional rendering
    if "activeTab === 'resources'" not in content:
        # Already handled above in tab buttons check
        pass

    if "<ResourcesPanel />" not in content:
        if RENDER_OLD in content:
            content = content.replace(RENDER_OLD, RENDER_NEW, 1)
            changes += 1
            print("    + Conditional rendering"
                  " (Resources, Activity)")
        else:
            # Try with flexible whitespace
            import re
            pattern = (
                r"\)\s*:\s*activeTab\s*===\s*'interactive'\s*\?\s*\(\s*"
                r"<InteractiveView\s*/>\s*\)\s*:\s*\(")
            match = re.search(pattern, content)
            if match:
                old = match.group(0)
                new = old.replace(
                    ") : (",
                    ") : activeTab === 'resources' ? (\n"
                    "                            "
                    "<ResourcesPanel />\n"
                    "                        "
                    ") : activeTab === 'activity' ? (\n"
                    "                            "
                    "<ActivityPanel />\n"
                    "                        ) : (")
                content = content.replace(old, new, 1)
                changes += 1
                print("    + Conditional rendering (regex)")
            else:
                print("    ! Could not find rendering marker")

    # 5. Insert React component definitions before App component
    if 'ResourcesPanel' not in content or 'const ResourcesPanel' not in content:
        # Find the App component by looking for activeTab useState
        lines = content.split('\n')
        insert_idx = None
        for i, line in enumerate(lines):
            if ('const [activeTab, setActiveTab]' in line
                    or 'const [activeTab,' in line):
                # Go backward to find App declaration
                for j in range(i - 1, max(i - 10, 0), -1):
                    if ('const App' in lines[j]
                            or 'function App' in lines[j]):
                        insert_idx = j
                        break
                if insert_idx is None:
                    # Insert 2 lines before activeTab
                    insert_idx = max(i - 2, 0)
                break

        if insert_idx is not None:
            lines.insert(insert_idx, REACT_COMPONENTS)
            content = '\n'.join(lines)
            changes += 1
            print("    + React components"
                  " (ResourcesPanel, ActivityPanel)")
        else:
            print("    ! Could not find App component for"
                  " React insertion")
            print("      Manual: Insert ResourcesPanel and"
                  " ActivityPanel before App")

    if changes > 0:
        backup = path.with_suffix('.py.bak')
        shutil.copy(path, backup)
        path.write_text(content)
        print(f"  + dashboard.py ({changes} edits)")
        return True
    else:
        print("  = dashboard.py (already patched or"
              " needs manual edits)")
        return True


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python3 patch_edu_features.py"
            " /path/to/nomade/")
        print()
        print("Prerequisites:")
        print("  1. Copy groups.py to"
              " nomade/collectors/groups.py")
        print("  2. Then run this patch")
        sys.exit(1)

    nomade_dir = Path(sys.argv[1])

    # Handle both /path/to/nomade/ and /path/to/nomade/nomade/
    if (nomade_dir / 'collectors').exists():
        pass  # Already pointing to nomade/nomade/
    elif (nomade_dir / 'nomade' / 'collectors').exists():
        nomade_dir = nomade_dir / 'nomade'
    else:
        print(f"ERROR: Could not find collectors/ in {nomade_dir}")
        sys.exit(1)

    # Check that groups.py exists
    groups_py = nomade_dir / 'collectors' / 'groups.py'
    if not groups_py.exists():
        print(f"ERROR: {groups_py} not found")
        print()
        print("Copy groups.py first:")
        print(f"  cp groups.py {groups_py}")
        sys.exit(1)

    print()
    print("NOMADE Edu Features Patch")
    print("=" * 40)
    print()

    ok1 = patch_collectors_init(nomade_dir)
    ok2 = patch_cli(nomade_dir)
    ok3 = patch_dashboard(nomade_dir)

    print()
    if ok1 and ok2 and ok3:
        print("Done! New features:")
        print("  - Group membership collector"
              " (nomade collect -C groups)")
        print("  - /api/footprint endpoint")
        print("  - /api/heatmap endpoint")
        print("  - /api/groups endpoint")
        print("  - Resources tab in dashboard")
        print("  - Activity tab in dashboard")
        print()
        print("Test:")
        print("  nomade collect -C groups --once")
        print("  nomade dashboard")
    else:
        print("Some patches may need manual attention."
              " Check output above.")


if __name__ == '__main__':
    main()
