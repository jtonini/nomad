# Installation

## Quick Install
```bash
pip install nomade-hpc
```

## From Source
```bash
git clone https://github.com/jtonini/nomade.git
cd nomade
pip install -e .
```

## Requirements

### Required

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.9+ | Core runtime |
| SQLite | 3.35+ | Data storage |
| sysstat | any | `iostat`, `mpstat` collectors |

### Optional

| Component | Purpose |
|-----------|---------|
| SLURM | Job-level analytics, queue monitoring |
| nvidia-smi | GPU monitoring |
| nfsiostat | NFS I/O metrics |

## Verify Installation
```bash
# Check requirements
nomade syscheck

# Test with demo data
nomade demo
```

## Installation Types

### User Install (Default)

For personal use or testing:
```bash
pip install nomade-hpc
nomade init
```

**Paths**:
```
~/.config/nomade/nomade.toml    # Configuration
~/.local/share/nomade/          # Database, models, logs
```

### System Install

For production cluster-wide deployment:
```bash
sudo pip install nomade-hpc
sudo nomade init --system
```

**Paths**:
```
/etc/nomade/nomade.toml         # Configuration
/var/lib/nomade/                # Database, models
/var/log/nomade/                # Logs
```

See [System Install](system-install.md) for detailed permissions and setup.

## Virtual Environment

Recommended for isolated installation:
```bash
python -m venv ~/nomade-env
source ~/nomade-env/bin/activate
pip install nomade-hpc
```

## Conda Environment
```bash
conda create -n nomade python=3.11
conda activate nomade
pip install nomade-hpc
```

## Development Install

For contributing:
```bash
git clone https://github.com/jtonini/nomade.git
cd nomade
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Upgrading
```bash
pip install --upgrade nomade-hpc
```

## Uninstalling
```bash
pip uninstall nomade-hpc

# Optional: remove data
rm -rf ~/.config/nomade ~/.local/share/nomade
```
