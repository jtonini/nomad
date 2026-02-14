# CLI Reference

## Core Commands

| Command | Description |
|---------|-------------|
| `nomad init` | Setup wizard |
| `nomad collect` | Start data collection |
| `nomad dashboard` | Launch web interface |
| `nomad demo` | Demo mode with synthetic data |
| `nomad status` | System status |
| `nomad syscheck` | Verify requirements |

## Educational Analytics

| Command | Description |
|---------|-------------|
| `nomad edu explain <job_id>` | Analyze job with recommendations |
| `nomad edu trajectory <user>` | User proficiency over time |
| `nomad edu report <group>` | Group/course report |

**Options for all edu commands**:
- `--db PATH` — Database path
- `--json` — JSON output
- `--days N` — Lookback period (trajectory/report)

## Analysis

| Command | Description |
|---------|-------------|
| `nomad disk <path>` | Filesystem trends |
| `nomad jobs` | Job history |
| `nomad similarity` | Network analysis |
| `nomad alerts` | View alerts |

## ML & Prediction

| Command | Description |
|---------|-------------|
| `nomad train` | Train prediction models |
| `nomad predict` | Run predictions |
| `nomad report` | Generate ML report |

## Community Dataset

| Command | Description |
|---------|-------------|
| `nomad community export` | Export anonymized data |
| `nomad community preview` | Preview export |
| `nomad community verify` | Verify export integrity |

## Data Collection
```bash
# Continuous collection
nomad collect

# Single cycle
nomad collect --once

# Specific collectors
nomad collect -C disk,slurm,groups
```

## Global Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Config file path |
| `--db PATH` | Database path |
| `--verbose` / `-v` | Verbose output |
| `--quiet` / `-q` | Suppress output |
| `--help` | Show help |
