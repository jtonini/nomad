# Quick Start

## Try Without HPC
```bash
pip install nomad-hpc
nomad demo
```

This launches a dashboard at http://localhost:8050 with synthetic data.

## Production Setup

### 1. Install
```bash
pip install nomad-hpc
```

### 2. Configure
```bash
nomad init
```

Follow the wizard to configure your cluster(s).

### 3. Collect Data
```bash
nomad collect
```

Leave running (or set up as systemd service).

### 4. View Dashboard
```bash
nomad dashboard
```

Open http://localhost:8050

## First Commands to Try
```bash
# System status
nomad status

# Disk usage trends
nomad disk /home

# Recent jobs
nomad jobs --user $USER

# Educational analytics (if you have job data)
nomad edu explain <job_id>
```

## Next Steps

- [Configuration](config.md) — Customize collectors and alerts
- [Dashboard](dashboard.md) — Navigate the web interface
- [Educational Analytics](edu.md) — Track proficiency development
- [CLI Reference](cli.md) — All available commands
