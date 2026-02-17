"""
NØMAD Diagnostics Module

Provides unified diagnostics for HPC infrastructure:
- Nodes (HPC compute nodes)
- Workstations (departmental machines)
- NAS (storage devices)
- Network (network paths and performance)
"""

from .node import diagnose_node, format_diagnostic as format_node_diagnostic
from .workstation import diagnose_workstation, format_diagnostic as format_workstation_diagnostic
from .storage import diagnose_storage, format_diagnostic as format_storage_diagnostic
from .network import diagnose_network, format_diagnostic as format_network_diagnostic

__all__ = [
    'diagnose_node',
    'diagnose_workstation', 
    'diagnose_storage',
    'diagnose_network',
    'format_node_diagnostic',
    'format_workstation_diagnostic',
    'format_storage_diagnostic',
    'format_network_diagnostic',
]
