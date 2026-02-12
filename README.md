# NØMADE

**NØde MAnagement DEvice** — Lightweight HPC monitoring, visualization, and predictive analytics.

> *"Travels light, adapts to its environment, and doesn't need permanent infrastructure."*

[![PyPI](https://img.shields.io/pypi/v/nomade-hpc.svg)](https://pypi.org/project/nomade-hpc/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18614517.svg)](https://doi.org/10.5281/zenodo.18614517)

---

📖 **[Full Documentation](https://jtonini.github.io/nomade/)** — Installation guides, configuration, CLI reference, network methodology, ML framework, and more.

---

## Quick Start

```bash
pip install nomade-hpc
nomade demo                    # Try with synthetic data
```

For production:
```bash
nomade init                    # Configure for your cluster
nomade collect                 # Start data collection
nomade dashboard               # Launch web interface
```

---

## Features

| Feature | Description | Command |
|---------|-------------|---------|
| **Dashboard** | Real-time multi-cluster monitoring with partition views | `nomade dashboard` |
| **Educational Analytics** | Track computational proficiency development | `nomade edu explain <job>` |
| **Alerts** | Threshold + predictive alerts (email, Slack, webhook) | `nomade alerts` |
| **ML Prediction** | Job failure prediction using similarity networks | `nomade predict` |
| **Community Export** | Anonymized datasets for cross-institutional research | `nomade community export` |
| **Interactive Sessions** | Monitor RStudio/Jupyter sessions | `nomade report-interactive` |
| **Derivative Analysis** | Detect accelerating trends before thresholds | Built into alerts |

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                         NØMADE                             │
├──────────────┬──────────────┬──────────────┬───────────────┤
│  Collectors  │   Analysis   │     Viz      │    Alerts     │
├──────────────┼──────────────┼──────────────┼───────────────┤
│ disk         │ derivatives  │ dashboard    │ thresholds    │
│ iostat       │ similarity   │ network 3D   │ predictive    │
│ slurm        │ ML ensemble  │ partitions   │ email/slack   │
│ gpu          │ edu scoring  │ edu views    │ webhooks      │
│ nfs          │              │              │               │
└──────────────┴──────────────┴──────────────┴───────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  SQLite Database  │
                    └───────────────────┘
```

---

## CLI Reference

### Core Commands
```bash
nomade init                    # Setup wizard
nomade collect                 # Start collectors
nomade dashboard               # Web interface
nomade demo                    # Demo mode
nomade status                  # System status
```

### Educational Analytics
```bash
nomade edu explain <job_id>    # Job analysis with recommendations
nomade edu trajectory <user>   # User proficiency over time
nomade edu report <group>      # Course/group report
```

### Analysis & Prediction
```bash
nomade disk /path              # Filesystem trends
nomade jobs --user <user>      # Job history
nomade similarity              # Network analysis
nomade train                   # Train ML models
nomade predict                 # Run predictions
```

### Community & Alerts
```bash
nomade community export        # Export anonymized data
nomade community preview       # Preview export
nomade alerts                  # View alerts
nomade alerts --unresolved     # Unresolved only
```

---

## Installation

### From PyPI
```bash
pip install nomade-hpc
```

### From Source
```bash
git clone https://github.com/jtonini/nomade.git
cd nomade && pip install -e .
```

### Requirements
- Python 3.9+
- SQLite 3.35+
- sysstat package (`iostat`, `mpstat`)
- Optional: SLURM, nvidia-smi, nfsiostat

### System Check
```bash
nomade syscheck
```

---

## Documentation

📖 **[jtonini.github.io/nomade](https://jtonini.github.io/nomade/)**

- [Installation & Configuration](https://jtonini.github.io/nomade/installation/)
- [System Install (`--system`)](https://jtonini.github.io/nomade/system-install/)
- [Dashboard Guide](https://jtonini.github.io/nomade/dashboard/)
- [Educational Analytics](https://jtonini.github.io/nomade/edu/)
- [Network Methodology](https://jtonini.github.io/nomade/network/)
- [ML Framework](https://jtonini.github.io/nomade/ml/)
- [Proficiency Scoring](https://jtonini.github.io/nomade/proficiency/)
- [CLI Reference](https://jtonini.github.io/nomade/cli/)
- [Configuration Options](https://jtonini.github.io/nomade/config/)

---

## License

Dual-licensed:
- **AGPL v3** — Free for academic, educational, and open-source use
- **Commercial License** — Available for proprietary deployments

---

## Citation

```bibtex
@software{nomade2026,
  author = {Tonini, João Filipe Riva},
  title = {NØMADE: Lightweight HPC Monitoring with Machine Learning-Based Failure Prediction},
  year = {2026},
  url = {https://github.com/jtonini/nomade},
  doi = {10.5281/zenodo.18614517}
}
```

---

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

---

## Contact

- **Author**: João Tonini
- **Email**: jtonini@richmond.edu
- **Issues**: [GitHub Issues](https://github.com/jtonini/nomade/issues)
