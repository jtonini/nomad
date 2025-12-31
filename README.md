# NØMADE

**NØde MAnagement DEvice** — A lightweight HPC monitoring and predictive analytics tool.

> *"Travels light, adapts to its environment, and doesn't need permanent infrastructure."*

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

---

## Overview

NØMADE is a lightweight, self-contained monitoring and prediction system for HPC clusters. Unlike heavyweight monitoring solutions that require complex infrastructure, NØMADE is designed to be deployed quickly, run with minimal resources, and provide actionable insights through both real-time alerts and predictive analytics.

### Key Features

- **Real-time Monitoring**: Track disk usage, SLURM queues, node health, license servers, and job metrics
- **Derivative Analysis**: Detect accelerating trends before they become critical (not just threshold alerts)
- **Predictive Analytics**: ML-based job health prediction using similarity networks
- **Actionable Recommendations**: Data-driven defaults and user-specific suggestions
- **3D Visualization**: Interactive network visualization with safe/danger zones
- **Lightweight**: SQLite database, minimal dependencies, no external services required

### Philosophy

NØMADE is inspired by nomadic principles:
- **Travels light**: Minimal dependencies, single SQLite database, no complex infrastructure
- **Adapts to its environment**: Configurable collectors, flexible alert rules, cluster-agnostic
- **Leaves no trace**: Clean uninstall, no system modifications required (except optional SLURM hooks)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              NØMADE                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      ALERT DISPATCHER                           │    │
│  │             Email · Slack · Webhook · Dashboard                 │    │
│  └─────────────────────────────┬───────────────────────────────────┘    │
│                                │                                        │
│  ┌─────────────────────────────┴───────────────────────────────────┐    │
│  │                      ALERT ENGINE                               │    │
│  │       Rules · Derivatives · Deduplication · Cooldowns           │    │
│  └─────────────────────────────┬───────────────────────────────────┘    │
│                                │                                        │
│         ┌──────────────────────┴──────────────────────┐                 │
│         ▼                                             ▼                 │
│  ┌─────────────────────┐                ┌─────────────────────────┐     │
│  │  MONITORING ENGINE  │                │   PREDICTION ENGINE     │     │
│  │  Threshold-based    │                │   Similarity networks   │     │
│  │  Immediate alerts   │                │   17-dim feature space  │     │
│  └─────────┬───────────┘                └─────────────┬───────────┘     │
│            │                                          │                 │
│            └──────────────────┬───────────────────────┘                 │
│                               │                                         │
│  ┌────────────────────────────┴────────────────────────────────────┐    │
│  │                         DATA LAYER                              │    │
│  │            SQLite · Time-series · Job History · I/O Samples     │    │
│  └────────────────────────────┬────────────────────────────────────┘    │
│                               │                                         │
│  ┌────────────────────────────┴─────────────────────────────────────┐   │
│  │                        COLLECTORS                                │   │
│  │  disk│slurm│job_metrics│iostat│mpstat│vmstat│node_state│gpu│nfs  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Collection Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         NØMADE Data Collection                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SYSTEM COLLECTORS (every 60s):                                              │
│  ┌──────────────┬─────────────────────────────────────────────────────────┐  │
│  │ disk         │ Filesystem usage (total, used, free, projections)       │  │
│  │ iostat       │ Device I/O: %iowait, utilization, latency               │  │
│  │ mpstat       │ Per-core CPU: utilization, imbalance detection          │  │
│  │ vmstat       │ Memory pressure, swap activity, blocked processes       │  │
│  │ nfs          │ NFS I/O: ops/sec, throughput, RTT, retransmissions      │  │
│  │ gpu          │ NVIDIA GPU: utilization, memory, temperature, power     │  │
│  └──────────────┴─────────────────────────────────────────────────────────┘  │
│                                                                              │
│  SLURM COLLECTORS (every 60s):                                               │
│  ┌──────────────┬─────────────────────────────────────────────────────────┐  │
│  │ slurm        │ Queue state: pending, running, partition stats          │  │
│  │ job_metrics  │ sacct data: CPU/mem efficiency, health scores           │  │
│  │ node_state   │ Node allocation, drain reasons, CPU load, memory        │  │
│  └──────────────┴─────────────────────────────────────────────────────────┘  │
│                                                                              │
│  JOB MONITOR (every 30s):                                                    │
│  ┌──────────────┬─────────────────────────────────────────────────────────┐  │
│  │ job_monitor  │ Per-job I/O: NFS vs local writes from /proc/[pid]/io    │  │
│  └──────────────┴─────────────────────────────────────────────────────────┘  │
│                                                                              │
│  FEATURE VECTOR (17 dimensions for similarity analysis):                     │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  From sacct:              From iostat:           From vmstat:          │  │
│  │   1. health_score          11. avg_iowait         17. memory_pressure  │  │
│  │   2. cpu_efficiency        12. peak_iowait        18. swap_activity    │  │
│  │   3. memory_efficiency     13. device_util        19. procs_blocked    │  │
│  │   4. used_gpu                                                          │  │
│  │   5. had_swap             From mpstat:                                 │  │
│  │                            14. avg_core_busy                           │  │
│  │  From job_monitor:         15. imbalance_ratio                         │  │
│  │   6. total_write_gb        16. max_core_busy                           │  │
│  │   7. write_rate_mbps                                                   │  │
│  │   8. nfs_ratio                                                         │  │
│  │   9. runtime_minutes                                                   │  │
│  │  10. write_intensity                                                   │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Collector Details

| Collector | Source | Data Collected | Graceful Skip |
|-----------|--------|----------------|---------------|
| `disk` | `shutil.disk_usage` | Filesystem total/used/free, projections | No |
| `slurm` | `squeue`, `sinfo` | Queue depth, partition stats, wait times | No |
| `job_metrics` | `sacct` | Job history, CPU/mem efficiency, health scores | No |
| `iostat` | `iostat -x` | %iowait, device utilization, latency | No |
| `mpstat` | `mpstat -P ALL` | Per-core CPU, imbalance ratio, saturation | No |
| `vmstat` | `vmstat` | Memory pressure, swap, blocked processes | No |
| `node_state` | `scontrol show node` | Node allocation, drain reasons, CPU load | No |
| `gpu` | `nvidia-smi` | GPU util, memory, temp, power | Yes (if no GPU) |
| `nfs` | `nfsiostat` | NFS ops/sec, throughput, RTT | Yes (if no NFS) |
| `job_monitor` | `/proc/[pid]/io` | Per-job NFS vs local I/O attribution | No |

### Two Engines, One System

1. **Monitoring Engine**: Real-time threshold and derivative-based alerts
   - Catches immediate issues (disk full, node down, stuck jobs)
   - Uses first and second derivatives for early warning
   - "Your disk fill rate is *accelerating* — full in 3 days, not 10"

2. **Prediction Engine**: Pattern-based ML analytics
   - Catches patterns before they become issues
   - Uses job similarity networks and health prediction
   - "Jobs with your I/O pattern have 72% failure rate"

---

## Monitoring Capabilities

### Disk Storage
- Filesystem usage monitoring (/, /home, /scratch, /project)
- Per-user and per-group quota tracking
- Fill rate calculation and projection
- **Derivative analysis**: Detect accelerating growth before thresholds trigger
- Orphan file and stale data detection
- Localscratch cleanup verification

### SLURM Queue
- Queue depth and wait time tracking
- Stuck and zombie job detection
- Node drain status monitoring
- Fairshare imbalance alerts
- Pending job analysis (why is my job waiting?)
- Job array health monitoring

### Node Health
- Node up/down/drain status
- Hardware error detection (ECC, GPU, disk)
- Temperature monitoring (CPU, GPU)
- NFS mount health
- Service status (slurmctld, slurmd, munge)
- Network connectivity checks

### License Servers
- FlexLM and RLM license tracking
- Real-time availability monitoring
- Usage pattern analysis
- Server connectivity alerts
- Expiration warnings

### Job Metrics
- Per-job resource usage (CPU, memory, GPU)
- I/O patterns (NFS vs local storage)
- Runtime and efficiency metrics
- Collected via SLURM prolog/epilog hooks

---

## Prediction Capabilities

### 17-Dimension Feature Vector

NØMADE builds job similarity networks using a comprehensive feature vector that captures multiple aspects of job behavior:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Feature Vector Architecture                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  JOB OUTCOME (from sacct):                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  health_score      │ 0.0 (catastrophic) → 1.0 (perfect)             │    │
│  │  cpu_efficiency    │ actual/requested CPU utilization               │    │
│  │  memory_efficiency │ actual/requested memory utilization            │    │
│  │  used_gpu          │ job utilized GPU resources                     │    │
│  │  had_swap          │ job triggered swap usage                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  I/O BEHAVIOR (from job_monitor):                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  total_write_gb    │ total data written during job                  │    │
│  │  write_rate_mbps   │ peak write throughput                          │    │
│  │  nfs_ratio         │ NFS writes / total writes (0-1)                │    │
│  │  runtime_minutes   │ job duration                                   │    │
│  │  write_intensity   │ GB written per minute                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  SYSTEM I/O STATE (from iostat, correlated to job runtime):                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  avg_iowait        │ average %iowait during job                     │    │
│  │  peak_iowait       │ maximum %iowait spike                          │    │
│  │  device_util       │ average device utilization                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  CPU DISTRIBUTION (from mpstat, correlated to job runtime):                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  avg_core_busy     │ average CPU utilization across cores           │    │
│  │  imbalance_ratio   │ std/avg busy (higher = more imbalance)         │    │
│  │  max_core_busy     │ hottest core utilization                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  MEMORY PRESSURE (from vmstat, correlated to job runtime):                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  memory_pressure   │ composite pressure indicator (0-1)             │    │
│  │  swap_activity     │ peak swap in+out (KB/s)                        │    │
│  │  procs_blocked     │ avg processes blocked on I/O                   │    │ 
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Quantitative Similarity Network

- **Raw quantitative metrics**: No arbitrary thresholds or binary labels
- **Non-redundant features**: `vram_gb > 0` implies GPU used (no separate flag)
- **Cosine similarity**: Z-score normalized feature vectors, threshold ≥ 0.7
- **Continuous health score**: 0 (catastrophic) → 1 (perfect), not binary
- **Time-correlated system state**: iostat/mpstat/vmstat data aligned to job runtime

### Simulation & Validation

- **Generative model**: Learn distributions from empirical data
- **Simulation cloud**: Thousands of synthetic jobs for coverage validation
- **Anomaly detection**: Real jobs outside simulation bounds
- **Temporal drift**: Monitor for model staleness

### Error Analysis & Defaults

- **Type 1 errors** (false alarms): Predicted failure, actually succeeded
- **Type 2 errors** (missed failures): Predicted success, actually failed
- **Threshold optimization**: Balance alert fatigue vs missed problems
- **Data-driven defaults**: "Use localscratch → +23% success rate"

### Visualization

- **3D network visualization**: Three.js interactive display
- **Axes**: NFS Write / Local Write / I/O Wait
- **Safe zone**: Low NFS, high local, low I/O wait (green region)
- **Danger zone**: High NFS, low local, high I/O wait (red region)
- **Real-time tracking**: Watch jobs move through feature space

---

## Derivative Analysis

A key innovation in NØMADE is the use of first and second derivatives for early warning:

```
VALUE (0th derivative):     "Disk is at 850 GB"
FIRST DERIVATIVE:           "Disk is filling at 15 GB/day"  
SECOND DERIVATIVE:          "Fill rate is ACCELERATING at 3 GB/day²"
```

### Why Second Derivatives Matter

Traditional threshold alerts only trigger when a value crosses a limit. By monitoring the second derivative (acceleration), NØMADE can detect:

- **Exponential growth**: Before linear projections underestimate
- **Sudden changes**: Spikes in usage patterns
- **Developing problems**: I/O storms, memory leaks, cascading failures

### Applications

| Metric | Accelerating (d²>0) | Decelerating (d²<0) |
|--------|---------------------|---------------------|
| Disk usage | ! Exponential fill | OK Cleanup in progress |
| Queue depth | ! System issue | OK Draining normally |
| Failure rate |  Cascading problem | OK Issue resolving |
| NFS latency | ! I/O storm developing | OK Load decreasing |
| Job memory | ! Memory leak / OOM | OK Normal variation |
| GPU temp | ! Cooling issue | OK Throttling working |

---

## Installation

### Requirements

- Python 3.9+
- SQLite 3.35+
- SLURM (for queue and job monitoring)
- sysstat package (iostat, mpstat)
- procps package (vmstat) - usually pre-installed

Optional:
- nvidia-smi (for GPU monitoring)
- nfs-common with nfsiostat (for NFS monitoring)
- Root access (for cgroup metrics)

### System Check

After installation, verify all requirements:

```bash
nomade syscheck
```

Expected output:
```
NØMADE System Check
════════════════════════════════════════
Python:
  OK Version 3.10.12 (requires >=3.9)
  OK Required packages installed
SLURM:
  OK sinfo available
  OK squeue available
  OK sacct available
  OK sstat available
  OK slurmdbd enabled
  OK JobAcctGather configured
System Tools:
  OK iostat available
  OK mpstat available
  OK vmstat available
  ○ nvidia-smi not found (no GPU monitoring)
  ○ nfsiostat not found (no NFS monitoring)
  OK /proc/[pid]/io accessible
Database:
  OK SQLite available
  OK Database: /var/lib/nomade/nomade.db
  OK Schema version: 2
Config:
  OK Config: /etc/nomade/nomade.toml
────────────────────────────────────────
OK All checks passed!
```

### Quick Start

**Try it now (no HPC required):**
```bash
pip install nomade-hpc
nomade demo
```

This generates synthetic data and launches the dashboard at http://localhost:5000

**For production HPC deployment:**
```bash
pip install nomade-hpc
nomade init
nomade collect    # Start data collection
nomade dashboard  # Launch web interface
```

**Or install from source:**
```bash
git clone https://github.com/jtonini/nomade.git
cd nomade
pip install -e .
nomade demo  # Test with synthetic data
```
```

### SLURM Integration (Optional)

For per-job metrics collection, install prolog/epilog hooks:

```bash
# Copy hooks to SLURM configuration
sudo cp scripts/prolog.sh /etc/slurm/prolog.d/nomade.sh
sudo cp scripts/epilog.sh /etc/slurm/epilog.d/nomade.sh

# Update slurm.conf
# Prolog=/etc/slurm/prolog.d/*
# Epilog=/etc/slurm/epilog.d/*

# Restart SLURM
sudo systemctl restart slurmctld
```

---

## Configuration

NØMADE uses a TOML configuration file:

```toml
# nomade.toml

[general]
cluster_name = "mycluster"
data_dir = "/var/lib/nomade"
log_level = "INFO"

[collectors]
# All collectors enabled by default
# Set enabled = false to disable specific collectors

[collectors.disk]
enabled = true
filesystems = ["/", "/home", "/scratch", "/localscratch"]

[collectors.slurm]
enabled = true
partitions = ["standard", "debug", "gpu", "highmem"]

[collectors.job_metrics]
enabled = true
lookback_hours = 24
min_runtime_seconds = 10

[collectors.iostat]
enabled = true
# devices = ["sda", "nvme0n1"]  # Optional: specific devices only

[collectors.mpstat]
enabled = true
store_per_core = true
store_summary = true

[collectors.vmstat]
enabled = true

[collectors.node_state]
enabled = true
# nodes = ["node001", "node002"]  # Optional: specific nodes only

[collectors.gpu]
enabled = true  # Gracefully skipped if no nvidia-smi

[collectors.nfs]
enabled = true  # Gracefully skipped if no nfsiostat

[monitor]
# Job I/O monitor settings
sample_interval = 30
nfs_paths = ["/home", "/scratch", "/project"]
local_paths = ["/localscratch", "/tmp", "/dev/shm"]
port = 27001

[alerts]
# Alert dispatch configuration
email_enabled = true
email_to = ["admin@example.edu"]
email_from = "nomade@cluster.example.edu"
smtp_host = "smtp.example.edu"

slack_enabled = false
slack_webhook = ""

# Alert thresholds
disk_warning_percent = 85
disk_critical_percent = 95
queue_stuck_days = 7
gpu_temp_warning = 83

[alerts.derivatives]
# Second derivative thresholds
disk_acceleration_warning = 1.0  # GB/day²
queue_acceleration_warning = 5   # jobs/hour²

[prediction]
# Prediction engine settings
enabled = true
similarity_threshold = 0.7
health_threshold = 0.5
retrain_interval_days = 7

[dashboard]
host = "0.0.0.0"
port = 8080
```

---

## Usage

### Command Line Interface

```bash
# System status overview
nomade status              # Full system status with all metrics
nomade syscheck            # Verify system requirements

# Data collection
nomade collect --once      # Single collection cycle
nomade collect --interval 60   # Continuous collection
nomade collect -C disk,slurm   # Specific collectors only

# Job I/O monitoring
nomade monitor             # Monitor running jobs for I/O
nomade monitor --once      # Single snapshot
nomade monitor -i 30       # 30-second interval

# Analysis
nomade disk /home --hours 24   # Filesystem trend analysis
nomade jobs --user jsmith      # Recent job history
nomade similarity              # Job similarity analysis
nomade similarity --find-similar 12345  # Find similar jobs
nomade similarity --export viz.json     # Export for visualization

# Alerts
nomade alerts              # View recent alerts
nomade alerts --unresolved # Only unresolved alerts
```

### Bash Helper Functions

Source the helper script for convenient shortcuts:

```bash
source ~/nomade/scripts/nomade.sh
nhelp      # Show all commands
```

| Command | Description |
|---------|-------------|
| `nstatus` | Quick status overview |
| `nwatch [s]` | Live status updates (every s seconds) |
| `ndisk PATH` | Filesystem trend analysis |
| `njobs` | Recent job history |
| `nsimilarity` | Job similarity analysis |
| `nalerts` | View alerts |
| `ncollect` | Run data collection |
| `nmonitor` | Job I/O monitoring |
| `nsyscheck` | System requirements check |
| `nlog` | Tail collection log |

### Status Output

```
═══ NØMADE Status ═══

Filesystems:
  /                    [██████████░░░░░░░░░░] 51.4% (34.02/66.26 GB)
  /home                [██████████░░░░░░░░░░] 51.4% (34.02/66.26 GB)
Queue:
  standard        Running:   4  Pending:  12
  gpu             Running:   2  Pending:   3
I/O:
  CPU iowait:    2.3%
  CPU user/sys:  45.2% / 3.1%
  vda          util: 15.2% write: 1240 KB/s  latency: 4.2ms
CPU Cores:
  Cores:         32
  Avg busy:      48.2%
  Range:         12.0% - 98.5% (spread: 86.5%)
  Imbalance:     0.42 (std/avg)
  Saturated:     4 (>95% busy)
Memory:
  Free:          12.45 GB
  Cache:         48.23 GB
  Swap used:     128 MB
  Pressure:      0.15
Nodes:
  node001         MIXED        CPU: 28/32 (88%)  Mem: 92%  Load: 27.4
  node002         ALLOCATED    CPU: 32/32 (100%) Mem: 98%  Load: 31.2
  node003         DRAIN        CPU: 0/32 (0%)    Mem: 0%   Load: 0.01
    └─ Reason: GPU memory errors - investigating
Collection:
  disk            1440 runs  100% success
  iostat          1440 runs  100% success
  mpstat          1440 runs  100% success
  vmstat          1440 runs  100% success
  slurm           1440 runs  100% success
  job_metrics     1440 runs  100% success
  node_state      1440 runs  100% success
```

### Python API

```python
from nomade import Nomade

# Initialize
nm = Nomade(config_path='nomade.toml')

# Get current disk status
disk_status = nm.collectors.disk.get_status()
for fs in disk_status:
    print(f"{fs['path']}: {fs['used_pct']:.1f}%")
    
# Analyze trends
analysis = nm.analysis.analyze_disk('/scratch')
print(f"Fill rate: {analysis['first_derivative']:.1f} GB/day")
print(f"Acceleration: {analysis['second_derivative']:.2f} GB/day²")
print(f"Trend: {analysis['trend']}")

# Predict job health
prediction = nm.prediction.predict_job(job_metrics)
print(f"Predicted health: {prediction['health']:.2f}")
print(f"Risk level: {prediction['risk_level']}")
print(f"Recommendations: {prediction['recommendations']}")

# Get recommendations for a user
recs = nm.prediction.recommend_for_user('alice')
for rec in recs:
    print(f"- {rec['message']}")
```

---

## Repository Structure

```
nomade/
├── README.md                 # This file
├── LICENSE                   # AGPL v3
├── pyproject.toml           # Package configuration
├── requirements.txt         # Dependencies
├── nomade.toml.example      # Example configuration
│
├── nomade/                  # Main package
│   ├── __init__.py
│   ├── cli.py               # Command-line interface
│   ├── daemon.py            # Main monitoring daemon
│   ├── config.py            # Configuration handling
│   │
│   ├── collectors/          # Data collectors
│   │   ├── __init__.py
│   │   ├── base.py          # Base collector class
│   │   ├── disk.py          # Disk & quota monitoring
│   │   ├── slurm.py         # SLURM queue & jobs
│   │   ├── nodes.py         # Node health
│   │   ├── licenses.py      # License servers
│   │   ├── jobs.py          # Per-job metrics
│   │   └── network.py       # Network monitoring
│   │
│   ├── db/                  # Database layer
│   │   ├── __init__.py
│   │   ├── schema.sql       # SQLite schema
│   │   ├── models.py        # Data models
│   │   └── queries.py       # Common queries
│   │
│   ├── analysis/            # Analysis utilities
│   │   ├── __init__.py
│   │   ├── derivatives.py   # Derivative calculations
│   │   ├── projections.py   # Trend projections
│   │   └── timeseries.py    # Time-series utilities
│   │
│   ├── alerts/              # Alert system
│   │   ├── __init__.py
│   │   ├── engine.py        # Alert evaluation
│   │   ├── rules.py         # Alert rule definitions
│   │   └── dispatch.py      # Email/Slack/webhook
│   │
│   ├── prediction/          # ML prediction
│   │   ├── __init__.py
│   │   ├── similarity.py    # Cosine similarity
│   │   ├── network.py       # Similarity network
│   │   ├── health.py        # Health score prediction
│   │   ├── simulation.py    # Simulation model
│   │   ├── errors.py        # Type 1/2 error analysis
│   │   └── recommendations.py  # Defaults generation
│   │
│   └── viz/                 # Visualization
│       ├── __init__.py
│       ├── dashboard.py     # Web dashboard
│       └── static/          # React frontend
│           ├── index.html
│           └── components/
│               ├── Network3D.jsx
│               ├── DiskStatus.jsx
│               ├── QueueStatus.jsx
│               └── Alerts.jsx
│
├── scripts/                 # Utility scripts
│   ├── prolog.sh           # SLURM prolog hook
│   ├── epilog.sh           # SLURM epilog hook
│   └── install_hooks.sh    # Hook installer
│
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── test_collectors.py
│   ├── test_analysis.py
│   ├── test_alerts.py
│   └── test_prediction.py
│
└── docs/                    # Documentation
    ├── installation.md
    ├── configuration.md
    ├── collectors.md
    ├── alerts.md
    ├── prediction.md
    └── api.md
```

---

## Theoretical Background

NØMADE's prediction engine is inspired by biogeographical network analysis, particularly the work of Vilhena & Antonelli (2015) on mapping biomes using species occurrence data.

### Biogeography → HPC Analogy

| Biogeography | HPC Infrastructure |
|--------------|-------------------|
| Species | Jobs |
| Geographic regions | Resources (nodes, storage) |
| Biomes | Emergent behavior clusters |
| Species ranges | Job resource usage patterns |
| Transition zones | Domain boundaries (CPU↔GPU, NFS↔local) |

### Key Insight

Just as biogeographical regions emerge from species distribution data rather than being predefined, NØMADE allows behavior patterns to emerge from job metrics rather than imposing arbitrary categories.

### Dual-View Analysis

1. **Data space**: Jobs as points in feature space, clustered by similarity
2. **Real space**: Jobs mapped to physical resources, showing actual infrastructure usage

---

## Roadmap

### Phase 1: Monitoring Foundation ✓
- [x] Design architecture
- [x] Define data model
- [x] Implement collectors (disk, SLURM, GPU, NFS, iostat, vmstat, mpstat)
- [x] Implement alert engine
- [x] Basic dashboard

### Phase 2: Prediction Engine ✓
- [x] Cosine similarity network (default), Simpson available for biogeographical analysis
- [x] Failure classification (8 classes: SUCCESS, TIMEOUT, FAILED, OOM, etc.)
- [x] Simulation framework (VM-based SLURM simulation)
- [x] Clustering analysis (assortativity, SES.MNTD, neighborhood purity)
- [x] Hotspot detection (failure-correlated feature bins)

### Phase 3: Visualization ✓
- [x] 3D network visualization (Three.js force-directed layout)
- [x] Interactive dashboard with cluster/network views
- [x] PCA view for emergent patterns
- [x] Clustering quality panel
- [x] ML Risk panel with high-risk job display

### Phase 4: Advanced ML ✓
- [x] GNN for network-aware prediction (PyTorch Geometric)
- [x] LSTM for temporal pattern detection
- [x] Autoencoder for anomaly detection (100% precision)
- [x] Ensemble methods (weighted voting)
- [x] Model persistence (save/load from database)
- [x] CLI commands (train, predict, report)
- [ ] Real-time scoring hook (SLURM prolog)
- [ ] Continuous learning pipeline

### Phase 5: Community
- [ ] Multi-cluster federation
- [ ] Anonymized data sharing
- [ ] Community benchmarks
- [ ] JOSS/SoftwareX paper submission

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone and install in development mode
git clone https://github.com/jtonini/nomade.git
cd nomade
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .

# Build documentation
cd docs && make html
```

---

## License

NOMADE is dual-licensed:

- **AGPL v3**: Free for academic, educational, and open-source use
- **Commercial License**: Available for proprietary/commercial deployments

See [LICENSE](LICENSE) for details.

---

## Citation

If you use NOMADE in your research, please cite:

```bibtex
@software{nomade2026,
  author = {Tonini, Joao},
  title = {NOMADE: A Lightweight HPC Monitoring and Prediction Tool},
  year = {2026},
  url = {https://github.com/jtonini/nomade}
}
```

---

## Acknowledgments

- Biogeographical network analysis inspired by Vilhena & Antonelli (2015)

---

## Contact

- **Author**: João Tonini
- **Email**: jtonini@richmond.edu
- **Issues**: [GitHub Issues](https://github.com/jtonini/nomade/issues)
