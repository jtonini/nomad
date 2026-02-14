# Installation

## Quick Install
```bash
pip install nomad-hpc
```

## From Source
```bash
git clone https://github.com/jtonini/nomad.git
cd nomad
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
nomad syscheck

# Test with demo data
nomad demo
```

## Installation Types

### User Install (Default)

For personal use or testing:
```bash
pip install nomad-hpc
nomad init
```

**Paths**:
```
~/.config/nomad/nomad.toml    # Configuration
~/.local/share/nomad/          # Database, models, logs
```

### System Install

For production cluster-wide deployment:
```bash
sudo pip install nomad-hpc
sudo nomad init --system
```

**Paths**:
```
/etc/nomad/nomad.toml         # Configuration
/var/lib/nomad/                # Database, models
/var/log/nomad/                # Logs
```

See [System Install](system-install.md) for detailed permissions and setup.

## Virtual Environment

Recommended for isolated installation:
```bash
python -m venv ~/nomad-env
source ~/nomad-env/bin/activate
pip install nomad-hpc
```

## Conda Environment
```bash
conda create -n nomad python=3.11
conda activate nomad
pip install nomad-hpc
```

## Development Install

For contributing:
```bash
git clone https://github.com/jtonini/nomad.git
cd nomad
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Upgrading
```bash
pip install --upgrade nomad-hpc
```

## Uninstalling
```bash
pip uninstall nomad-hpc

# Optional: remove data
rm -rf ~/.config/nomad ~/.local/share/nomad
```
