# CLI Reference

## Core Commands

| Command | Description |
|---------|-------------|
| `nomade init` | Setup wizard |
| `nomade collect` | Start data collection |
| `nomade dashboard` | Launch web interface |
| `nomade demo` | Demo mode with synthetic data |
| `nomade status` | System status |
| `nomade syscheck` | Verify requirements |

## Educational Analytics

| Command | Description |
|---------|-------------|
| `nomade edu explain <job_id>` | Analyze job with recommendations |
| `nomade edu trajectory <user>` | User proficiency over time |
| `nomade edu report <group>` | Group/course report |

**Options for all edu commands**:
- `--db PATH` — Database path
- `--json` — JSON output
- `--days N` — Lookback period (trajectory/report)

## Analysis

| Command | Description |
|---------|-------------|
| `nomade disk <path>` | Filesystem trends |
| `nomade jobs` | Job history |
| `nomade similarity` | Network analysis |
| `nomade alerts` | View alerts |

## ML & Prediction

| Command | Description |
|---------|-------------|
| `nomade train` | Train prediction models |
| `nomade predict` | Run predictions |
| `nomade report` | Generate ML report |

## Community Dataset

| Command | Description |
|---------|-------------|
| `nomade community export` | Export anonymized data |
| `nomade community preview` | Preview export |
| `nomade community verify` | Verify export integrity |

## Data Collection
```bash
# Continuous collection
nomade collect

# Single cycle
nomade collect --once

# Specific collectors
nomade collect -C disk,slurm,groups
```

## Global Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Config file path |
| `--db PATH` | Database path |
| `--verbose` / `-v` | Verbose output |
| `--quiet` / `-q` | Suppress output |
| `--help` | Show help |
