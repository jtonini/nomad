#!/usr/bin/env python3
"""Add Education API endpoints and interactive dashboard panel to NØMAÐ."""

from pathlib import Path
import sys

SERVER_PY = Path("nomad/viz/server.py")
if not SERVER_PY.exists():
    print("Run from the nomad repo root")
    sys.exit(1)

t = SERVER_PY.read_text()
count = 0

# ═══════════════════════════════════════════════════════════════
# 1. Add API endpoints before the 404 handler
# ═══════════════════════════════════════════════════════════════

api_endpoints = '''
        elif parsed.path == '/api/edu/users':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            dm = DashboardHandler.data_manager
            try:
                conn = sqlite3.connect(str(dm.db_path))
                conn.row_factory = sqlite3.Row
                users = [r[0] for r in conn.execute(
                    "SELECT DISTINCT user_name FROM jobs ORDER BY user_name"
                ).fetchall()]
                groups = []
                try:
                    groups = [r[0] for r in conn.execute(
                        "SELECT DISTINCT group_name FROM group_membership ORDER BY group_name"
                    ).fetchall()]
                except Exception:
                    pass
                conn.close()
                result = {"users": users, "groups": groups}
            except Exception as e:
                result = {"users": [], "groups": [], "error": str(e)}
            self.wfile.write(json.dumps(result).encode())
        elif parsed.path.startswith('/api/edu/trajectory'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            dm = DashboardHandler.data_manager
            params = dict(urllib.parse.parse_qsl(parsed.query))
            username = params.get('user', '')
            try:
                from nomad.edu import user_trajectory
                traj = user_trajectory(str(dm.db_path), username, days=90)
                if traj:
                    result = {
                        "username": traj.username,
                        "total_jobs": traj.total_jobs,
                        "date_range": list(traj.date_range),
                        "current_scores": traj.current_scores,
                        "improvement": traj.improvement,
                        "overall_improvement": traj.overall_improvement,
                        "windows": [
                            {"start": str(w.start), "end": str(w.end),
                             "jobs": w.jobs, "scores": w.scores}
                            for w in traj.windows
                        ] if hasattr(traj, 'windows') else [],
                    }
                else:
                    result = {"error": f"No data for user '{username}'"}
            except Exception as e:
                result = {"error": str(e)}
            self.wfile.write(json.dumps(result, default=str).encode())
        elif parsed.path.startswith('/api/edu/group'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            dm = DashboardHandler.data_manager
            params = dict(urllib.parse.parse_qsl(parsed.query))
            group_name = params.get('group', '')
            try:
                from nomad.edu import group_summary
                gs = group_summary(str(dm.db_path), group_name, days=90)
                if gs:
                    result = {
                        "group_name": gs.group_name,
                        "member_count": gs.member_count,
                        "total_jobs": gs.total_jobs,
                        "date_range": list(gs.date_range),
                        "avg_overall": gs.avg_overall,
                        "avg_improvement": gs.avg_improvement,
                        "users_improving": gs.users_improving,
                        "users_declining": gs.users_declining,
                        "users_stable": gs.users_stable,
                        "dimension_avgs": gs.dimension_avgs,
                        "dimension_improvements": gs.dimension_improvements,
                        "weakest_dimension": gs.weakest_dimension,
                        "strongest_dimension": gs.strongest_dimension,
                        "users": [
                            {"username": u.username, "total_jobs": u.total_jobs,
                             "current_scores": u.current_scores,
                             "overall_improvement": u.overall_improvement}
                            for u in gs.users
                        ],
                    }
                else:
                    result = {"error": f"No data for group '{group_name}'"}
            except Exception as e:
                result = {"error": str(e)}
            self.wfile.write(json.dumps(result, default=str).encode())
'''

old_404 = "        else:\n            self.send_error(404)"
if old_404 in t and "/api/edu/users" not in t:
    t = t.replace(old_404, api_endpoints + "        else:\n            self.send_error(404)", 1)
    count += 1
    print("1. Added edu API endpoints")

# ═══════════════════════════════════════════════════════════════
# 2. Replace placeholder EducationPanel with interactive version
# ═══════════════════════════════════════════════════════════════

# Find and replace the entire EducationPanel
old_panel_start = "            // Education Panel\n            const EducationPanel = () => {"
old_panel_end = "            const DynamicsPanel = () => {"

if old_panel_start in t:
    start_idx = t.find(old_panel_start)
    end_idx = t.find(old_panel_end)
    if end_idx > start_idx:
        new_panel = '''            // Education Panel
            const EducationPanel = () => {
                const [eduView, setEduView] = useState('overview');
                const [eduUsers, setEduUsers] = useState([]);
                const [eduGroups, setEduGroups] = useState([]);
                const [selectedUser, setSelectedUser] = useState('');
                const [selectedGroup, setSelectedGroup] = useState('');
                const [trajData, setTrajData] = useState(null);
                const [groupData, setGroupData] = useState(null);
                const [eduLoading, setEduLoading] = useState(false);

                useEffect(() => {
                    fetch('/api/edu/users')
                        .then(r => r.json())
                        .then(d => { setEduUsers(d.users || []); setEduGroups(d.groups || []); })
                        .catch(() => {});
                }, []);

                const loadTrajectory = (user) => {
                    setSelectedUser(user);
                    setEduLoading(true);
                    setTrajData(null);
                    fetch('/api/edu/trajectory?user=' + encodeURIComponent(user))
                        .then(r => r.json())
                        .then(d => { setTrajData(d); setEduLoading(false); setEduView('trajectory'); })
                        .catch(() => { setTrajData({error: 'Failed'}); setEduLoading(false); });
                };

                const loadGroup = (group) => {
                    setSelectedGroup(group);
                    setEduLoading(true);
                    setGroupData(null);
                    fetch('/api/edu/group?group=' + encodeURIComponent(group))
                        .then(r => r.json())
                        .then(d => { setGroupData(d); setEduLoading(false); setEduView('group'); })
                        .catch(() => { setGroupData({error: 'Failed'}); setEduLoading(false); });
                };

                const scoreColor = (s) => s >= 80 ? '#22c55e' : s >= 60 ? '#f59e0b' : s >= 40 ? '#B64326' : '#ef4444';
                const impColor = (v) => v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#64748b';
                const dims = ['cpu', 'memory', 'time', 'io', 'gpu'];
                const dimLabels = {cpu: 'CPU', memory: 'Memory', time: 'Time', io: 'I/O', gpu: 'GPU'};

                // Overview: select user or group
                const overviewView = React.createElement('div', null,
                    React.createElement('div', {style: {display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16}},
                        React.createElement('div', {className: 'card', style: {padding: 16}},
                            React.createElement('h3', {style: {fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--btn-text)'}}, 'User Trajectory'),
                            React.createElement('select', {
                                value: selectedUser,
                                onChange: e => { if (e.target.value) loadTrajectory(e.target.value); },
                                style: eduStyles.select
                            },
                                React.createElement('option', {value: ''}, 'Select a user...'),
                                eduUsers.map(u => React.createElement('option', {key: u, value: u}, u))
                            ),
                            React.createElement('p', {style: {fontSize: 11, color: '#64748b', marginTop: 8}},
                                eduUsers.length + ' users with job history')
                        ),
                        React.createElement('div', {className: 'card', style: {padding: 16}},
                            React.createElement('h3', {style: {fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--btn-text)'}}, 'Group Report'),
                            React.createElement('select', {
                                value: selectedGroup,
                                onChange: e => { if (e.target.value) loadGroup(e.target.value); },
                                style: eduStyles.select
                            },
                                React.createElement('option', {value: ''}, 'Select a group...'),
                                eduGroups.map(g => React.createElement('option', {key: g, value: g}, g))
                            ),
                            React.createElement('p', {style: {fontSize: 11, color: '#64748b', marginTop: 8}},
                                eduGroups.length + ' groups available')
                        )
                    )
                );

                // Trajectory view
                const trajectoryView = trajData && !trajData.error ? React.createElement('div', null,
                    React.createElement('button', {
                        onClick: () => setEduView('overview'),
                        style: {background: 'none', border: 'none', color: '#00BACF', cursor: 'pointer', fontSize: 12, marginBottom: 12}
                    }, '< Back to overview'),
                    React.createElement('div', {className: 'card', style: {padding: 16, marginBottom: 16}},
                        React.createElement('h3', {style: {fontSize: 16, fontWeight: 700, marginBottom: 4}}, trajData.username),
                        React.createElement('div', {style: {fontSize: 12, color: '#64748b', marginBottom: 16}},
                            trajData.total_jobs + ' jobs | ' + (trajData.date_range || []).join(' to ')),
                        React.createElement('div', {style: {display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap'}},
                            React.createElement('div', {style: {padding: '8px 16px', background: 'var(--bg-secondary)', borderRadius: 8, textAlign: 'center'}},
                                React.createElement('div', {style: {fontSize: 11, color: '#64748b'}}, 'Overall'),
                                React.createElement('div', {style: {fontSize: 18, fontWeight: 700, color: impColor(trajData.overall_improvement || 0)}},
                                    (trajData.overall_improvement > 0 ? '+' : '') + (trajData.overall_improvement || 0).toFixed(1) + '%')
                            ),
                            ...dims.map(d => {
                                const score = (trajData.current_scores || {})[d];
                                const imp = (trajData.improvement || {})[d];
                                return score !== undefined ? React.createElement('div', {key: d, style: {padding: '8px 16px', background: 'var(--bg-secondary)', borderRadius: 8, textAlign: 'center'}},
                                    React.createElement('div', {style: {fontSize: 11, color: '#64748b'}}, dimLabels[d] || d),
                                    React.createElement('div', {style: {fontSize: 18, fontWeight: 700, color: scoreColor(score)}}, score.toFixed(0)),
                                    imp !== undefined ? React.createElement('div', {style: {fontSize: 10, color: impColor(imp)}},
                                        (imp > 0 ? '+' : '') + imp.toFixed(1)) : null
                                ) : null;
                            })
                        ),
                        (trajData.windows || []).length > 0 ? React.createElement('div', null,
                            React.createElement('h4', {style: {fontSize: 12, fontWeight: 600, color: '#94a3b8', marginBottom: 8}}, 'Weekly Windows'),
                            React.createElement('table', {style: {fontSize: 11, borderCollapse: 'collapse', width: '100%'}},
                                React.createElement('thead', null,
                                    React.createElement('tr', null,
                                        React.createElement('th', {style: {padding: '4px 8px', color: '#64748b', textAlign: 'left'}}, 'Period'),
                                        React.createElement('th', {style: {padding: '4px 8px', color: '#64748b', textAlign: 'right'}}, 'Jobs'),
                                        ...dims.map(d => React.createElement('th', {key: d, style: {padding: '4px 8px', color: '#64748b', textAlign: 'right'}}, dimLabels[d] || d))
                                    )
                                ),
                                React.createElement('tbody', null,
                                    trajData.windows.map((w, i) => React.createElement('tr', {key: i},
                                        React.createElement('td', {style: {padding: '4px 8px', color: '#94a3b8'}}, (w.start || '').slice(5, 10) + ' - ' + (w.end || '').slice(5, 10)),
                                        React.createElement('td', {style: {padding: '4px 8px', textAlign: 'right'}}, w.jobs),
                                        ...dims.map(d => {
                                            const s = (w.scores || {})[d];
                                            return React.createElement('td', {key: d, style: {padding: '4px 8px', textAlign: 'right', color: s !== undefined ? scoreColor(s) : '#64748b'}},
                                                s !== undefined ? s.toFixed(0) : '-');
                                        })
                                    ))
                                )
                            )
                        ) : null
                    )
                ) : (trajData && trajData.error ? React.createElement('div', {style: {color: '#ef4444', padding: 16}},
                    React.createElement('button', {onClick: () => setEduView('overview'), style: {background: 'none', border: 'none', color: '#00BACF', cursor: 'pointer', fontSize: 12, marginBottom: 12}}, '< Back'),
                    'Error: ' + trajData.error) : null);

                // Group view
                const groupView = groupData && !groupData.error ? React.createElement('div', null,
                    React.createElement('button', {
                        onClick: () => setEduView('overview'),
                        style: {background: 'none', border: 'none', color: '#00BACF', cursor: 'pointer', fontSize: 12, marginBottom: 12}
                    }, '< Back to overview'),
                    React.createElement('div', {className: 'card', style: {padding: 16, marginBottom: 16}},
                        React.createElement('h3', {style: {fontSize: 16, fontWeight: 700, marginBottom: 4}}, groupData.group_name),
                        React.createElement('div', {style: {fontSize: 12, color: '#64748b', marginBottom: 16}},
                            groupData.member_count + ' members | ' + groupData.total_jobs + ' jobs | ' + (groupData.date_range || []).join(' to ')),
                        React.createElement('div', {style: {display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap'}},
                            React.createElement('div', {style: {padding: '8px 16px', background: 'var(--bg-secondary)', borderRadius: 8, textAlign: 'center'}},
                                React.createElement('div', {style: {fontSize: 11, color: '#64748b'}}, 'Avg Score'),
                                React.createElement('div', {style: {fontSize: 20, fontWeight: 700, color: scoreColor(groupData.avg_overall || 0)}},
                                    (groupData.avg_overall || 0).toFixed(0))
                            ),
                            React.createElement('div', {style: {padding: '8px 16px', background: 'var(--bg-secondary)', borderRadius: 8, textAlign: 'center'}},
                                React.createElement('div', {style: {fontSize: 11, color: '#64748b'}}, 'Improving'),
                                React.createElement('div', {style: {fontSize: 20, fontWeight: 700, color: '#22c55e'}}, groupData.users_improving || 0)
                            ),
                            React.createElement('div', {style: {padding: '8px 16px', background: 'var(--bg-secondary)', borderRadius: 8, textAlign: 'center'}},
                                React.createElement('div', {style: {fontSize: 11, color: '#64748b'}}, 'Stable'),
                                React.createElement('div', {style: {fontSize: 20, fontWeight: 700, color: '#f59e0b'}}, groupData.users_stable || 0)
                            ),
                            React.createElement('div', {style: {padding: '8px 16px', background: 'var(--bg-secondary)', borderRadius: 8, textAlign: 'center'}},
                                React.createElement('div', {style: {fontSize: 11, color: '#64748b'}}, 'Declining'),
                                React.createElement('div', {style: {fontSize: 20, fontWeight: 700, color: '#ef4444'}}, groupData.users_declining || 0)
                            ),
                            React.createElement('div', {style: {padding: '8px 16px', background: 'var(--bg-secondary)', borderRadius: 8, textAlign: 'center'}},
                                React.createElement('div', {style: {fontSize: 11, color: '#64748b'}}, 'Strongest'),
                                React.createElement('div', {style: {fontSize: 14, fontWeight: 600, color: '#22c55e'}}, dimLabels[groupData.strongest_dimension] || groupData.strongest_dimension || '-')
                            ),
                            React.createElement('div', {style: {padding: '8px 16px', background: 'var(--bg-secondary)', borderRadius: 8, textAlign: 'center'}},
                                React.createElement('div', {style: {fontSize: 11, color: '#64748b'}}, 'Weakest'),
                                React.createElement('div', {style: {fontSize: 14, fontWeight: 600, color: '#ef4444'}}, dimLabels[groupData.weakest_dimension] || groupData.weakest_dimension || '-')
                            )
                        ),
                        React.createElement('h4', {style: {fontSize: 12, fontWeight: 600, color: '#94a3b8', marginBottom: 8}}, 'Members'),
                        React.createElement('table', {style: {fontSize: 11, borderCollapse: 'collapse', width: '100%'}},
                            React.createElement('thead', null,
                                React.createElement('tr', null,
                                    React.createElement('th', {style: {padding: '4px 8px', color: '#64748b', textAlign: 'left'}}, 'User'),
                                    React.createElement('th', {style: {padding: '4px 8px', color: '#64748b', textAlign: 'right'}}, 'Jobs'),
                                    ...dims.map(d => React.createElement('th', {key: d, style: {padding: '4px 8px', color: '#64748b', textAlign: 'right'}}, dimLabels[d] || d)),
                                    React.createElement('th', {style: {padding: '4px 8px', color: '#64748b', textAlign: 'right'}}, 'Trend')
                                )
                            ),
                            React.createElement('tbody', null,
                                (groupData.users || []).map((u, i) => React.createElement('tr', {key: i, style: {cursor: 'pointer'}, onClick: () => loadTrajectory(u.username)},
                                    React.createElement('td', {style: {padding: '4px 8px', color: '#00BACF'}}, u.username),
                                    React.createElement('td', {style: {padding: '4px 8px', textAlign: 'right'}}, u.total_jobs),
                                    ...dims.map(d => {
                                        const s = (u.current_scores || {})[d];
                                        return React.createElement('td', {key: d, style: {padding: '4px 8px', textAlign: 'right', color: s !== undefined ? scoreColor(s) : '#64748b'}},
                                            s !== undefined ? s.toFixed(0) : '-');
                                    }),
                                    React.createElement('td', {style: {padding: '4px 8px', textAlign: 'right', color: impColor(u.overall_improvement || 0)}},
                                        (u.overall_improvement > 0 ? '+' : '') + (u.overall_improvement || 0).toFixed(1) + '%')
                                ))
                            )
                        )
                    )
                ) : (groupData && groupData.error ? React.createElement('div', {style: {color: '#ef4444', padding: 16}},
                    React.createElement('button', {onClick: () => setEduView('overview'), style: {background: 'none', border: 'none', color: '#00BACF', cursor: 'pointer', fontSize: 12, marginBottom: 12}}, '< Back'),
                    'Error: ' + groupData.error) : null);

                return React.createElement('div', {style: {padding: 16, maxWidth: 900}},
                    React.createElement('h2', {style: {fontSize: 18, fontWeight: 700, marginBottom: 4}}, 'Educational Analytics'),
                    React.createElement('p', {style: {fontSize: 12, color: '#64748b', marginBottom: 16}}, 'Computational proficiency tracking and development analysis'),
                    eduLoading ? React.createElement('div', {style: {padding: 20, color: '#94a3b8'}}, 'Loading...') :
                    eduView === 'trajectory' ? trajectoryView :
                    eduView === 'group' ? groupView :
                    overviewView
                );
            };

'''
        t = t[:start_idx] + new_panel + "            " + t[end_idx:]
        count += 1
        print("2. Replaced EducationPanel with interactive version")

SERVER_PY.write_text(t)
print(f"\nDone: {count} changes")
print("Verify: python3 -c \"import py_compile; py_compile.compile('nomad/viz/server.py', doraise=True)\"")
