# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""NOMADE configuration handling."""

from pathlib import Path

DEFAULT_CONFIG_PATHS = [
    Path.home() / '.config' / 'nomade' / 'nomade.toml',
    Path('/etc/nomade/nomade.toml'),
]

def find_config() -> Path | None:
    """Find the first existing config file."""
    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            return path
    return None

def get_default_config_path() -> Path:
    """Get path to packaged default config."""
    return Path(__file__).parent / 'default.toml'
