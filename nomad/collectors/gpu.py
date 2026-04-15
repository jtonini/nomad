# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
from __future__ import annotations

"""
NØMAD GPU Collector

Collects NVIDIA GPU metrics from nvidia-smi.
Gracefully skips if no GPUs available.
"""

import logging
import os
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .base import BaseCollector, registry

logger = logging.getLogger(__name__)


@dataclass
class GPUStats:
    """NVIDIA GPU statistics."""
    gpu_index: int
    gpu_name: str

    # Utilization
    gpu_util_percent: float
    memory_util_percent: float

    # Memory (MB)
    memory_used_mb: int
    memory_total_mb: int
    memory_free_mb: int

    # Temperature and power
    temperature_c: int
    power_draw_w: float
    power_limit_w: float

    # Processes
    compute_processes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            'gpu_index': self.gpu_index,
            'gpu_name': self.gpu_name,
            'gpu_util_percent': self.gpu_util_percent,
            'memory_util_percent': self.memory_util_percent,
            'memory_used_mb': self.memory_used_mb,
            'memory_total_mb': self.memory_total_mb,
            'memory_free_mb': self.memory_free_mb,
            'temperature_c': self.temperature_c,
            'power_draw_w': self.power_draw_w,
            'power_limit_w': self.power_limit_w,
            'compute_processes': self.compute_processes,
        }


@registry.register
class GPUCollector(BaseCollector):
    """
    Collector for NVIDIA GPU statistics from nvidia-smi.
    
    Gracefully skips if nvidia-smi is not available or no GPUs present.
    
    Collected data:
        - GPU utilization percentage
        - Memory utilization and usage
        - Temperature
        - Power draw
        - Process count
    """

    name = "gpu"
    description = "NVIDIA GPU statistics"
    default_interval = 60

    def __init__(self, config: dict[str, Any], db_path: str):
        super().__init__(config, db_path)

        self._gpu_available = None  # Lazy check
        # SSH mode config: gpu_nodes list and ssh_user
        gpu_config = self.config
        self._gpu_nodes = gpu_config.get('gpu_nodes', [])
        self._ssh_user = gpu_config.get('ssh_user', os.getenv('USER', ''))
        if self._gpu_nodes:
            logger.info(f"GPUCollector SSH mode: {len(self._gpu_nodes)} nodes configured")
        logger.info("GPUCollector initialized")


    def _run_command_ssh(self, cmd: str, host: str) -> str | None:
        """Run a command on a remote host via SSH.

        Uses BatchMode=yes to fail fast if key auth is not set up.
        Modeled on WorkstationCollector.run_command().
        """
        ssh_cmd = [
            'ssh',
            '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            f'{self._ssh_user}@{host}',
            cmd
        ]
        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            if result.returncode != 0:
                logger.debug(f"SSH to {host} failed (rc={result.returncode}): {result.stderr.strip()}")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"SSH to {host} timed out after 30s")
            return None
        except Exception as e:
            logger.debug(f"SSH to {host} error: {e}")
            return None

    def _get_nvidia_smi_cmd(self) -> str:
        """Return the nvidia-smi query command string."""
        nvidia_path = self.config.get('collectors', {}).get('gpu', {}).get(
            'nvidia_smi_path', 'nvidia-smi'
        )
        return (
            f"{nvidia_path} --query-gpu="
            "index,name,utilization.gpu,utilization.memory,"
            "memory.used,memory.total,memory.free,"
            "temperature.gpu,power.draw,power.limit "
            "--format=csv,noheader,nounits"
        )

    def _check_gpu_available(self) -> bool:
        """Check if GPUs are available locally or via SSH nodes."""
        if self._gpu_available is not None:
            return self._gpu_available

        # SSH mode: verify connectivity to at least one GPU node
        if self._gpu_nodes:
            cmd = self._get_nvidia_smi_cmd()
            for node in self._gpu_nodes:
                output = self._run_command_ssh(cmd, node)
                if output:
                    self._gpu_available = True
                    logger.info(f"GPU SSH mode verified via {node}")
                    return True
            self._gpu_available = False
            logger.warning(f"GPU SSH mode: none of {self._gpu_nodes} responded to nvidia-smi")
            return False

        # Local mode: try running nvidia-smi directly
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=count', '--format=csv,noheader'],
                capture_output=True, text=True, timeout=5
            )
            self._gpu_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._gpu_available = False

        if not self._gpu_available:
            logger.info("No NVIDIA GPUs detected - GPU collector will be skipped")
        return self._gpu_available

    def collect(self) -> list[dict[str, Any]]:
        """Collect GPU statistics from nvidia-smi, locally or via SSH."""
        if not self._check_gpu_available():
            return []

        all_records = []

        if self._gpu_nodes:
            # SSH mode: collect from each configured GPU node
            cmd = self._get_nvidia_smi_cmd()
            for node in self._gpu_nodes:
                output = self._run_command_ssh(cmd, node)
                if output:
                    records = self._parse_nvidia_output(output, hostname=node)
                    all_records.extend(records)
                    logger.debug(f"Collected {len(records)} GPU records from {node}")
                else:
                    logger.warning(f"Failed to collect GPU data from {node}")
        else:
            # Local mode: run nvidia-smi directly
            try:
                result = subprocess.run(
                    self._get_nvidia_smi_cmd().split(),
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0 and result.stdout.strip():
                    hostname = socket.gethostname().split('.')[0]
                    all_records = self._parse_nvidia_output(
                        result.stdout, hostname=hostname
                    )
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.error(f"nvidia-smi failed: {e}")
                self._gpu_available = False

        return all_records

    def _parse_nvidia_output(self, output: str, hostname: str = '') -> list[dict[str, Any]]:
        """Parse nvidia-smi CSV output."""
        records = []
        timestamp = datetime.now()

        for line in output.strip().split('\n'):
            if not line.strip():
                continue

            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 10:
                continue

            try:
                stats = GPUStats(
                    gpu_index=int(parts[0]),
                    gpu_name=parts[1],
                    gpu_util_percent=float(parts[2]) if parts[2] != '[N/A]' else 0,
                    memory_util_percent=float(parts[3]) if parts[3] != '[N/A]' else 0,
                    memory_used_mb=int(float(parts[4])) if parts[4] != '[N/A]' else 0,
                    memory_total_mb=int(float(parts[5])) if parts[5] != '[N/A]' else 0,
                    memory_free_mb=int(float(parts[6])) if parts[6] != '[N/A]' else 0,
                    temperature_c=int(float(parts[7])) if parts[7] != '[N/A]' else 0,
                    power_draw_w=float(parts[8]) if parts[8] != '[N/A]' else 0,
                    power_limit_w=float(parts[9]) if parts[9] != '[N/A]' else 0,
                    compute_processes=0,  # Will be updated
                )

                records.append({
                    'type': 'gpu',
                    'timestamp': timestamp.isoformat(),
                    'node_name': hostname,
                    **stats.to_dict()
                })

            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse GPU line: {e}")
                continue

        return records

    def store(self, data: list[dict[str, Any]]) -> None:
        """Store GPU statistics in database."""

        if not data:
            return

        with self.get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gpu_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    gpu_index INTEGER,
                    gpu_name TEXT,
                    gpu_util_percent REAL,
                    memory_util_percent REAL,
                    memory_used_mb INTEGER,
                    memory_total_mb INTEGER,
                    memory_free_mb INTEGER,
                    temperature_c INTEGER,
                    power_draw_w REAL,
                    power_limit_w REAL,
                    compute_processes INTEGER
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_gpu_stats_ts 
                ON gpu_stats(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_gpu_stats_gpu 
                ON gpu_stats(gpu_index, timestamp)
            """)

            for record in data:
                if record.get('type') == 'gpu':
                    conn.execute(
                        """
                        INSERT INTO gpu_stats 
                        (timestamp, node_name, gpu_index, gpu_name, gpu_util_percent, memory_util_percent,
                         memory_used_mb, memory_total_mb, memory_free_mb,
                         temperature_c, power_draw_w, power_limit_w, compute_processes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record['timestamp'],
                            record['gpu_index'],
                            record['gpu_name'],
                            record['gpu_util_percent'],
                            record['memory_util_percent'],
                            record['memory_used_mb'],
                            record['memory_total_mb'],
                            record['memory_free_mb'],
                            record['temperature_c'],
                            record['power_draw_w'],
                            record['power_limit_w'],
                            record['compute_processes'],
                        )
                    )

            conn.commit()
            logger.debug(f"Stored {len(data)} GPU records")
