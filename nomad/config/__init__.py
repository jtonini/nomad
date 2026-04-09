# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""NOMADE configuration handling."""

from pathlib import Path

DEFAULT_CONFIG_PATHS = [
    Path.home() / '.config' / 'nomad' / 'nomad.toml',
    Path('/etc/nomad/nomad.toml'),
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


def resolve_cluster_name(config: dict) -> str:
    """Resolve cluster name from config, trying all known paths.

    Resolution order:
      1. config['clusters'] -- wizard-generated format (first cluster name)
      2. config['cluster_name'] -- legacy top-level key
      3. config['cluster']['name'] -- another legacy path
      4. hostname via socket.gethostname()
      5. 'default' as ultimate fallback
    """
    import socket

    # 1. Wizard format: [clusters.<id>] name = "..."
    clusters = config.get('clusters', {})
    if clusters:
        first_id = next(iter(clusters))
        name = clusters[first_id].get('name', first_id)
        if name:
            return name

    # 2. Legacy top-level key
    name = config.get('cluster_name')
    if name:
        return name

    # 3. Another legacy path
    name = config.get('cluster', {}).get('name')
    if name:
        return name

    # 4. Hostname
    try:
        hostname = socket.gethostname().split('.')[0]
        if hostname:
            return hostname
    except Exception:
        pass

    return 'default'


def resolve_all_cluster_names(config: dict) -> list[str]:
    """Return all cluster names from config.

    For multi-cluster setups returns all names from [clusters.*].
    For single-cluster legacy configs returns a one-element list.
    """
    clusters = config.get('clusters', {})
    if clusters:
        return [c.get('name', cid) for cid, c in clusters.items()]
    return [resolve_cluster_name(config)]
