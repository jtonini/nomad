# Dashboard

The NØMAD dashboard provides real-time monitoring of your HPC cluster(s).

## Launching
```bash
nomad dashboard
```

Open http://localhost:8050 in your browser.

## Tabs

### Cluster Tabs

Per-cluster views showing:
- Node status (idle, allocated, down)
- Partition utilization
- CPU and memory pressure indicators
- Active jobs count

### Network

3D job similarity network visualization:
- Jobs as nodes, colored by health
- Edges connect similar jobs
- "Safe zone" and "danger zone" regions emerge from data
- Failure clustering analysis

### Resources

Resource usage views for administrators:
- CPU hours by cluster/group
- Filter by cluster, group, and time period
- Resource consumption patterns
- Quietest hours for job scheduling

### Activity

Job activity and history:
- Recent job completions
- Failed job categories
- Interactive session monitoring (RStudio/Jupyter)

## Planned Features

- **Education Tab**: Visual proficiency trajectories and per-student breakdowns (CLI available now via `nomad edu`)

## Remote Access

By default, the dashboard only listens on localhost. For remote access:

1. **SSH Tunnel** (simple):
```bash
   ssh -L 8050:localhost:8050 user@hpc-head
```

2. **Reverse Proxy** (production):
   See [System Install](system-install.md#reverse-proxy-recommended-for-remote-access)
