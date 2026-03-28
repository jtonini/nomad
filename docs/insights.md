# Insight Engine

The NØMAD Insight Engine translates analytical output into actionable, human-readable narratives. Instead of presenting raw numbers, charts, and threshold alerts, the engine explains **what is happening**, **why it matters**, and **what to do about it**.

## The Distinction

| Layer | Example | Role |
|-------|---------|------|
| **Alerts** | `WARN: /scratch usage 92%` | Reactive threshold triggers |
| **Reports** | `94.2% success rate this week` | Backward-looking, descriptive |
| **Insights** | `The scratch filesystem is filling at 5 GB/hr because GPU jobs are writing large checkpoints. At this rate, /scratch will be full by 2am.` | Interpretive, forward-looking |

Reports provide evidence. Insights provide understanding. Both coexist.

## Quick Start
```bash
# Generate demo data with stress scenarios
nomad demo --no-launch

# Get a concise operational briefing
nomad insights brief --db ~/nomad_demo.db --cluster demo-cluster --hours 168

# Full detailed report
nomad insights detail --db ~/nomad_demo.db --hours 168

# JSON output (for API/Console integration)
nomad insights json --db ~/nomad_demo.db

# Slack-formatted message
nomad insights slack --db ~/nomad_demo.db --cluster demo-cluster

# Email digest
nomad insights digest --db ~/nomad_demo.db --period daily
```

## How It Works

The engine runs a four-step pipeline:
```
DB tables → Signal Readers → Template Narration → Correlation Engine → Output
              (Level 1)         (Level 1)            (Level 2)
```

### Step 1: Signal Readers

Eight domain-specific readers query the database and produce typed `Signal` objects with severity, metrics, and affected entities.

| Reader | Data Source | Signals Produced |
|--------|------------|------------------|
| Jobs | `jobs` | Success rate, partition failures, OOM, timeouts, trend |
| Disk | `storage_state` | Filesystem usage, fill rate projection |
| GPU | `jobs` (GPU subset) | GPU job failure rate, GPU OOM |
| Queue | `queue_state`, `jobs` | Queue pressure, wait times |
| Network | `network_perf` | Latency, packet loss |
| Alerts | `alerts` | Active alert count, flapping detection |
| Cloud | `cloud_metrics` | Cost summary, underutilized instances |
| Workstation | `workstation_state` | CPU/memory pressure |

### Step 2: Template Narration (Level 1)

Each signal is passed through a narrative template that produces a human-readable sentence. Templates adjust tone based on severity:

- **Info**: "1,200 jobs processed, 96% success rate."
- **Warning**: "850 jobs, 82% success rate -- below the 90% baseline."
- **Critical**: "400 jobs, only 65% succeeded -- well below normal."

There are 19 templates covering all signal types.

### Step 3: Correlation Engine (Level 2)

The engine examines multiple signals together to find causal or co-occurring patterns. Instead of three separate alerts, it produces one coherent finding:

| Correlation Rule | Signals Combined | Insight |
|-----------------|-----------------|---------|
| Disk pressure + job failures | `disk_fill_projection` + `job_success_rate` | Cascading failure risk |
| GPU OOM + partition failures | `gpu_oom` + `partition_failure_concentration` | VRAM capacity mismatch |
| Queue pressure + wait times | `queue_pressure` + `high_wait_time` | Partition bottleneck |
| Network issues + job failures | `high_network_latency` + `job_success_rate` | I/O-related failures |
| Cloud cost + underutilization | `cloud_cost_summary` + `underutilized_instance` | Cost optimization |
| Workstation overload + alerts | `workstation_high_cpu` + `active_alerts` | User impact |

Correlated insights include a **recommendation** with specific actions.

### Step 4: Output Formatting

| Format | Use Case |
|--------|----------|
| CLI brief | Concise terminal briefing |
| CLI detail | Full report with metrics |
| JSON | API and Console integration |
| Slack | Channel notifications (supports webhook) |
| Email digest | Daily/weekly summaries |

## CLI Reference

All commands accept `--db PATH`, `--hours N`, and `--cluster NAME`.

### `nomad insights brief`

Concise operational briefing with health assessment, correlated findings, and individual signals.

### `nomad insights detail`

Full report with all signals, metrics, and affected entities.

### `nomad insights json`

JSON output for programmatic use:
```json
{
  "overall_health": "degraded",
  "signal_count": 15,
  "insight_count": 3,
  "insights": [...],
  "signals": [...]
}
```

### `nomad insights slack`

Slack-formatted message. Add `--webhook URL` to post directly.

### `nomad insights digest`

Email digest with `--period daily|weekly`.

## Dashboard Integration

Available in `nomad dashboard` as the **Insights** tab, and through the `/api/insights` endpoint.

## Architecture
```
nomad/insights/
    engine.py         — InsightEngine orchestrator
    signals.py        — 8 signal readers
    templates.py      — 19 narrative templates
    correlator.py     — 6 correlation rules
    formatters.py     — Output formatters
    inject_stress.py  — Demo stress scenarios
```

## Implementation Levels

| Level | Description | Status |
|-------|-------------|--------|
| **Level 1** | Template-based narratives | Implemented |
| **Level 2** | Multi-signal correlation | Implemented |
| **Level 3** | LLM-powered interpretation | Planned (CSSI Year 2-3) |

## Programmatic Use
```python
from nomad.insights import InsightEngine

engine = InsightEngine("/path/to/nomad.db", hours=168, cluster_name="mycluster")

print(engine.overall_health)    # "good", "nominal", "degraded", "impaired"
print(engine.signal_count)
data = engine.to_dict()         # Python dict
print(engine.to_slack())        # Slack markdown
subject, body = engine.to_email("daily")
```
