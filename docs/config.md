# Configuration

NØMADE uses TOML configuration files.

## Configuration Locations

| Install Type | Path |
|--------------|------|
| User | `~/.config/nomade/nomade.toml` |
| System | `/etc/nomade/nomade.toml` |

## Example Configuration
```toml
# nomade.toml

[general]
cluster_name = "spydur"
data_dir = "/var/lib/nomade"
log_level = "INFO"

[database]
path = "/var/lib/nomade/nomade.db"

[collectors]
enabled = ["disk", "iostat", "slurm", "gpu", "nfs"]
interval = 60  # seconds

[collectors.disk]
filesystems = ["/", "/home", "/scratch"]
quota_enabled = true

[collectors.slurm]
partitions = ["compute", "gpu", "highmem"]

[dashboard]
host = "127.0.0.1"
port = 8050

[alerts]
enabled = true

[alerts.email]
enabled = true
smtp_host = "smtp.example.edu"
from_addr = "nomade@example.edu"
to_addrs = ["admin@example.edu"]

[alerts.slack]
enabled = true
webhook_url = "https://hooks.slack.com/services/..."

[alerts.thresholds]
disk_warning = 85
disk_critical = 95
gpu_temp_warning = 80

[ml]
enabled = true
similarity_threshold = 0.7
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NOMADE_CONFIG` | Config file path |
| `NOMADE_DB` | Database path |
| `NOMADE_LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) |

## Collectors

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed collector documentation.
