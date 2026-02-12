# Quick Start

## Try Without HPC
```bash
pip install nomade-hpc
nomade demo
```

This launches a dashboard at http://localhost:8050 with synthetic data.

## Production Setup

### 1. Install
```bash
pip install nomade-hpc
```

### 2. Configure
```bash
nomade init
```

Follow the wizard to configure your cluster(s).

### 3. Collect Data
```bash
nomade collect
```

Leave running (or set up as systemd service).

### 4. View Dashboard
```bash
nomade dashboard
```

Open http://localhost:8050

## First Commands to Try
```bash
# System status
nomade status

# Disk usage trends
nomade disk /home

# Recent jobs
nomade jobs --user $USER

# Educational analytics (if you have job data)
nomade edu explain <job_id>
```

## Next Steps

- [Configuration](config.md) — Customize collectors and alerts
- [Dashboard](dashboard.md) — Navigate the web interface
- [Educational Analytics](edu.md) — Track proficiency development
- [CLI Reference](cli.md) — All available commands
