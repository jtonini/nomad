#!/usr/bin/env python3
"""
NOMADE Interactive Session Collector
Monitors RStudio and Jupyter sessions via process inspection.
No root or API tokens required.
"""

import subprocess
import os
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Configurable thresholds
IDLE_SESSION_HOURS = 24      # Sessions idle longer than this are "stale"
MEMORY_HOG_MB = 4096         # Sessions using more than this are "memory hogs"
MAX_IDLE_SESSIONS = 5        # Users with more idle sessions than this get flagged


def get_process_memory(pid: int) -> Dict[str, float]:
    """Get memory info from /proc/[pid]/status."""
    try:
        with open('/proc/{}/status'.format(pid), 'r') as f:
            content = f.read()
        
        rss = 0
        vms = 0
        
        for line in content.split('\n'):
            if line.startswith('VmRSS:'):
                rss = int(line.split()[1])  # in kB
            elif line.startswith('VmSize:'):
                vms = int(line.split()[1])  # in kB
        
        return {
            'rss_mb': round(rss / 1024, 1),
            'vms_mb': round(vms / 1024, 1)
        }
    except:
        return {'rss_mb': 0, 'vms_mb': 0}


def get_process_start_time(pid: int) -> Optional[str]:
    """Get process start time from /proc/[pid]/stat."""
    try:
        with open('/proc/stat', 'r') as f:
            for line in f:
                if line.startswith('btime'):
                    boot_time = int(line.split()[1])
                    break
        
        with open('/proc/{}/stat'.format(pid), 'r') as f:
            stat = f.read().split()
            starttime_ticks = int(stat[21])
        
        clk_tck = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
        start_seconds = boot_time + (starttime_ticks / clk_tck)
        
        return datetime.fromtimestamp(start_seconds).isoformat()
    except:
        return None


def calc_age_hours(start_time: Optional[str]) -> Optional[float]:
    """Calculate age in hours from start time."""
    if not start_time:
        return None
    try:
        start_dt = datetime.fromisoformat(start_time)
        age = datetime.now() - start_dt
        return round(age.total_seconds() / 3600, 1)
    except:
        return None


def collect_sessions() -> Dict[str, Any]:
    """Collect RStudio and Jupyter session info from running processes."""
    
    sessions = []
    
    try:
        ps_output = subprocess.check_output(
            ['ps', 'aux'],
            universal_newlines=True,
            stderr=subprocess.DEVNULL
        )
        
        for line in ps_output.strip().split('\n')[1:]:  # Skip header
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            
            cmdline = parts[10].lower()
            
            # Detect session type
            if 'rsession' in cmdline:
                session_type = 'RStudio'
            elif 'ipykernel' in cmdline:
                session_type = 'Jupyter (Python)'
            elif 'irkernel' in cmdline:
                session_type = 'Jupyter (R)'
            elif 'jupyter-lab' in cmdline or 'jupyter-notebook' in cmdline:
                session_type = 'Jupyter Server'
            else:
                continue
            
            user = parts[0]
            pid = int(parts[1])
            cpu_pct = float(parts[2])
            mem_pct = float(parts[3])
            
            mem_info = get_process_memory(pid)
            start_time = get_process_start_time(pid)
            age_hours = calc_age_hours(start_time)
            
            # Consider idle if CPU < 1% 
            is_idle = cpu_pct < 1.0
            
            sessions.append({
                'type': session_type,
                'user': user,
                'pid': pid,
                'cpu_percent': cpu_pct,
                'mem_percent': mem_pct,
                'mem_mb': mem_info['rss_mb'],
                'mem_virtual_mb': mem_info['vms_mb'],
                'start_time': start_time,
                'age_hours': age_hours,
                'is_idle': is_idle
            })
    
    except Exception as e:
        logger.warning("Failed to collect sessions: {}".format(e))
    
    return build_result(sessions)


def build_result(sessions: List[Dict]) -> Dict[str, Any]:
    """Build structured result from collected sessions."""
    
    # Group by user
    users = {}
    total_memory = 0
    idle_count = 0
    
    # Count by type
    by_type = {
        'RStudio': {'total': 0, 'idle': 0, 'memory_mb': 0},
        'Jupyter (Python)': {'total': 0, 'idle': 0, 'memory_mb': 0},
        'Jupyter (R)': {'total': 0, 'idle': 0, 'memory_mb': 0},
        'Jupyter Server': {'total': 0, 'idle': 0, 'memory_mb': 0}
    }
    
    for s in sessions:
        user = s['user']
        session_type = s['type']
        mem = s['mem_mb']
        
        if user not in users:
            users[user] = {
                'sessions': 0, 
                'memory_mb': 0, 
                'idle': 0,
                'rstudio': 0,
                'jupyter': 0
            }
        
        users[user]['sessions'] += 1
        users[user]['memory_mb'] += mem
        total_memory += mem
        
        # Track by type for user
        if session_type == 'RStudio':
            users[user]['rstudio'] += 1
        else:
            users[user]['jupyter'] += 1
        
        # Track by type overall
        if session_type in by_type:
            by_type[session_type]['total'] += 1
            by_type[session_type]['memory_mb'] += mem
        
        if s['is_idle']:
            idle_count += 1
            users[user]['idle'] += 1
            if session_type in by_type:
                by_type[session_type]['idle'] += 1
    
    # Sort users by memory
    user_list = [
        {'user': u, **stats}
        for u, stats in sorted(users.items(), key=lambda x: -x[1]['memory_mb'])
    ]
    
    # Find old idle sessions (>24h)
    stale_sessions = [
        s for s in sessions
        if s['is_idle'] and s.get('age_hours', 0) and s['age_hours'] >= IDLE_SESSION_HOURS
    ]
    
    # Find memory hogs (>4GB)
    memory_hogs = [
        s for s in sessions
        if s['mem_mb'] >= MEMORY_HOG_MB
    ]
    
    # Find users with too many idle sessions
    idle_session_hogs = [
        u for u in user_list
        if u['idle'] > MAX_IDLE_SESSIONS
    ]
    
    return {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_sessions': len(sessions),
            'idle_sessions': idle_count,
            'total_memory_mb': round(total_memory, 1),
            'total_memory_gb': round(total_memory / 1024, 2),
            'unique_users': len(users)
        },
        'by_type': by_type,
        'users': user_list,
        'sessions': sorted(sessions, key=lambda x: -x['mem_mb']),
        'alerts': {
            'stale_sessions': sorted(stale_sessions, key=lambda x: -x.get('age_hours', 0)),
            'memory_hogs': sorted(memory_hogs, key=lambda x: -x['mem_mb']),
            'idle_session_hogs': idle_session_hogs
        }
    }


def collect(config: dict = None) -> Dict[str, Any]:
    """Entry point for NOMADE collector framework."""
    return collect_sessions()


def print_report(data: Dict[str, Any]):
    """Print a human-readable report."""
    summary = data['summary']
    by_type = data['by_type']
    
    print("=" * 70)
    print("              Interactive Sessions Report")
    print("=" * 70)
    print("  Timestamp:      {}".format(data['timestamp']))
    print("  Total Sessions: {}".format(summary['total_sessions']))
    print("  Idle Sessions:  {}".format(summary['idle_sessions']))
    print("  Total Memory:   {} GB".format(summary['total_memory_gb']))
    print("  Unique Users:   {}".format(summary['unique_users']))
    print("-" * 70)
    
    # Sessions by type
    print("\n  SESSIONS BY TYPE:")
    print("  {:<20} {:>8} {:>8} {:>12}".format('Type', 'Total', 'Idle', 'Memory (MB)'))
    print("  {:<20} {:>8} {:>8} {:>12}".format('-'*20, '-'*8, '-'*8, '-'*12))
    for stype, stats in by_type.items():
        if stats['total'] > 0:
            print("  {:<20} {:>8} {:>8} {:>12.0f}".format(
                stype, stats['total'], stats['idle'], stats['memory_mb']
            ))
    
    if data['users']:
        print("\n  TOP USERS BY MEMORY:")
        print("  {:<12} {:>8} {:>8} {:>8} {:>10} {:>6}".format(
            'User', 'Sessions', 'RStudio', 'Jupyter', 'Mem (MB)', 'Idle'))
        print("  {:<12} {:>8} {:>8} {:>8} {:>10} {:>6}".format(
            '-'*12, '-'*8, '-'*8, '-'*8, '-'*10, '-'*6))
        for u in data['users'][:10]:
            print("  {:<12} {:>8} {:>8} {:>8} {:>10.0f} {:>6}".format(
                u['user'][:12], u['sessions'], u['rstudio'], u['jupyter'], 
                u['memory_mb'], u['idle']
            ))
    
    # Alerts
    alerts = data['alerts']
    
    if alerts['idle_session_hogs']:
        print("\n  [!] USERS WITH >{} IDLE SESSIONS:".format(MAX_IDLE_SESSIONS))
        for u in alerts['idle_session_hogs']:
            print("    - {}: {} idle sessions ({} RStudio, {} Jupyter), {:.0f} MB".format(
                u['user'], u['idle'], u['rstudio'], u['jupyter'], u['memory_mb']
            ))
    
    if alerts['stale_sessions']:
        print("\n  [!] STALE SESSIONS (idle >{}h): {}".format(
            IDLE_SESSION_HOURS, len(alerts['stale_sessions'])))
        for s in alerts['stale_sessions'][:5]:
            print("    - {}: {}, {:.0f}h old, {:.0f} MB".format(
                s['user'], s['type'], s['age_hours'], s['mem_mb']))
    
    if alerts['memory_hogs']:
        print("\n  [!] MEMORY HOGS (>{}GB): {}".format(
            MEMORY_HOG_MB/1024, len(alerts['memory_hogs'])))
        for s in alerts['memory_hogs'][:5]:
            print("    - {}: {}, {:.1f} GB".format(
                s['user'], s['type'], s['mem_mb']/1024))
    
    print("=" * 70)


if __name__ == '__main__':
    data = collect_sessions()
    print_report(data)
