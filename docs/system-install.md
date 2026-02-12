# System Install

This guide covers deploying NØMADE system-wide for production HPC environments.

## Overview

System install differs from user install in several ways:

| Aspect | User Install | System Install |
|--------|--------------|----------------|
| Config location | `~/.config/nomade/` | `/etc/nomade/` |
| Data location | `~/.local/share/nomade/` | `/var/lib/nomade/` |
| Log location | `~/.local/share/nomade/logs/` | `/var/log/nomade/` |
| Permissions | User only | Controlled by file permissions |
| Service | Manual or user systemd | System systemd unit |
| Dashboard access | localhost only | Configurable (proxy recommended) |

## Installation

### Prerequisites
```bash
# Install as root or with sudo
sudo pip install nomade-hpc

# Or system-wide from source
sudo pip install /path/to/nomade/
```

### Initialize System Configuration
```bash
sudo nomade init --system
```

This creates:

| Path | Purpose | Permissions |
|------|---------|-------------|
| `/etc/nomade/` | Configuration directory | `root:root 755` |
| `/etc/nomade/nomade.toml` | Main configuration | `root:root 644` |
| `/var/lib/nomade/` | Data directory | `root:nomade 750` |
| `/var/lib/nomade/nomade.db` | SQLite database | `root:nomade 660` |
| `/var/log/nomade/` | Log directory | `root:nomade 750` |

### Required Permissions

**Running as root**: Full access to all paths.

**Running as service user** (recommended):
```bash
# Create nomade group
sudo groupadd nomade

# Create service user
sudo useradd -r -g nomade -d /var/lib/nomade -s /sbin/nologin nomade

# Set ownership
sudo chown -R nomade:nomade /var/lib/nomade
sudo chown -R nomade:nomade /var/log/nomade
sudo chown root:nomade /etc/nomade/nomade.toml
sudo chmod 640 /etc/nomade/nomade.toml
```

**Wheel group access** (for admin users):
```bash
# Allow wheel group to read config
sudo chown root:wheel /etc/nomade/nomade.toml
sudo chmod 640 /etc/nomade/nomade.toml

# Allow wheel group to read database
sudo chown nomade:wheel /var/lib/nomade/nomade.db
sudo chmod 660 /var/lib/nomade/nomade.db
```

## Files Modified/Accessed

### Configuration Files

| File | Read/Write | Purpose |
|------|------------|---------|
| `/etc/nomade/nomade.toml` | R | Main configuration |
| `/etc/nomade/clusters/*.toml` | R | Per-cluster configs (optional) |

### Data Files

| File | Read/Write | Purpose |
|------|------------|---------|
| `/var/lib/nomade/nomade.db` | RW | SQLite database |
| `/var/lib/nomade/models/` | RW | ML model files |
| `/var/lib/nomade/cache/` | RW | Temporary cache |

### Log Files

| File | Read/Write | Purpose |
|------|------------|---------|
| `/var/log/nomade/nomade.log` | W | Main application log |
| `/var/log/nomade/collector.log` | W | Collector logs |
| `/var/log/nomade/alerts.log` | W | Alert dispatch logs |

### System Files Read

| File | Purpose |
|------|---------|
| `/proc/*/io` | Per-process I/O stats |
| `/proc/meminfo` | Memory information |
| `/proc/loadavg` | System load |
| `/sys/class/thermal/` | Temperature sensors |

### External Commands Executed

| Command | Package | Purpose |
|---------|---------|---------|
| `iostat` | sysstat | Disk I/O metrics |
| `mpstat` | sysstat | CPU metrics |
| `vmstat` | procps | Memory/swap metrics |
| `df` | coreutils | Filesystem usage |
| `nvidia-smi` | nvidia-driver | GPU metrics (optional) |
| `nfsiostat` | nfs-utils | NFS metrics (optional) |
| `squeue` | slurm | Job queue (optional) |
| `sinfo` | slurm | Node info (optional) |
| `sacct` | slurm | Job accounting (optional) |

## Systemd Service

### Create Service Unit
```bash
sudo cat > /etc/systemd/system/nomade-collector.service << 'UNIT'
[Unit]
Description=NØMADE HPC Monitoring Collector
After=network.target slurmd.service

[Service]
Type=simple
User=nomade
Group=nomade
ExecStart=/usr/local/bin/nomade collect
Restart=always
RestartSec=30

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/nomade /var/log/nomade
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
```

### Enable and Start
```bash
sudo systemctl daemon-reload
sudo systemctl enable nomade-collector
sudo systemctl start nomade-collector
sudo systemctl status nomade-collector
```

### Dashboard Service (Optional)
```bash
sudo cat > /etc/systemd/system/nomade-dashboard.service << 'UNIT'
[Unit]
Description=NØMADE Dashboard
After=network.target nomade-collector.service

[Service]
Type=simple
User=nomade
Group=nomade
ExecStart=/usr/local/bin/nomade dashboard --host 127.0.0.1 --port 8050
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
```

## Web Dashboard Access

### Localhost Only (Default)

Dashboard binds to `127.0.0.1:8050` by default. Access via SSH tunnel:
```bash
# On your local machine
ssh -L 8050:localhost:8050 user@hpc-head-node

# Then open http://localhost:8050 in browser
```

### Reverse Proxy (Recommended for Remote Access)

Using Apache:
```apache
# /etc/httpd/conf.d/nomade.conf
<VirtualHost *:443>
    ServerName hpc.example.edu
    
    SSLEngine on
    SSLCertificateFile /etc/pki/tls/certs/server.crt
    SSLCertificateKeyFile /etc/pki/tls/private/server.key
    
    <Location /nomade>
        ProxyPass http://127.0.0.1:8050/
        ProxyPassReverse http://127.0.0.1:8050/
        
        # Require authentication
        AuthType Basic
        AuthName "NØMADE Dashboard"
        AuthUserFile /etc/httpd/.htpasswd
        Require valid-user
    </Location>
</VirtualHost>
```

Using nginx:
```nginx
# /etc/nginx/conf.d/nomade.conf
server {
    listen 443 ssl;
    server_name hpc.example.edu;
    
    ssl_certificate /etc/ssl/certs/server.crt;
    ssl_certificate_key /etc/ssl/private/server.key;
    
    location /nomade/ {
        proxy_pass http://127.0.0.1:8050/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # WebSocket support (for live updates)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Authentication
        auth_basic "NØMADE Dashboard";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
}
```

## SLURM Integration

### Prolog/Epilog Hooks

For per-job metrics collection:
```bash
# Copy hook scripts
sudo cp /path/to/nomade/scripts/prolog.sh /etc/slurm/prolog.d/nomade.sh
sudo cp /path/to/nomade/scripts/epilog.sh /etc/slurm/epilog.d/nomade.sh

# Make executable
sudo chmod +x /etc/slurm/prolog.d/nomade.sh
sudo chmod +x /etc/slurm/epilog.d/nomade.sh

# Restart SLURM controller
sudo systemctl restart slurmctld
```

### Prolog Script
```bash
#!/bin/bash
# /etc/slurm/prolog.d/nomade.sh
/usr/local/bin/nomade job-start $SLURM_JOB_ID 2>/dev/null || true
```

### Epilog Script
```bash
#!/bin/bash
# /etc/slurm/epilog.d/nomade.sh
/usr/local/bin/nomade job-end $SLURM_JOB_ID 2>/dev/null || true
```

## Multi-Cluster Setup

For monitoring multiple clusters from one head node:
```toml
# /etc/nomade/nomade.toml

[clusters.spydur]
name = "Spydur"
type = "slurm"
ssh_host = "spydur-head"
partitions = ["compute", "gpu", "highmem"]

[clusters.arachne]
name = "Arachne"
type = "slurm"
ssh_host = "arachne-head"
partitions = ["standard", "large"]
```

## Security Considerations

### Database Access

The SQLite database contains job metadata including usernames. Restrict access:
```bash
# Only nomade user and wheel group can read
sudo chmod 660 /var/lib/nomade/nomade.db
sudo chown nomade:wheel /var/lib/nomade/nomade.db
```

### Configuration Secrets

If using Slack/email alerts, config contains credentials:
```bash
# Restrict config file
sudo chmod 640 /etc/nomade/nomade.toml
sudo chown root:nomade /etc/nomade/nomade.toml
```

### Dashboard Authentication

Always use authentication for remote dashboard access. Never expose port 8050 directly to the network.

## Troubleshooting

### Permission Denied
```
PermissionError: [Errno 13] Permission denied: '/var/lib/nomade/nomade.db'
```

**Solution**: Check ownership and permissions:
```bash
sudo chown nomade:nomade /var/lib/nomade/nomade.db
sudo chmod 660 /var/lib/nomade/nomade.db
```

### Collector Not Starting

Check systemd logs:
```bash
sudo journalctl -u nomade-collector -f
```

### SLURM Commands Failing

Ensure the nomade user can run SLURM commands:
```bash
sudo -u nomade squeue
```

May need to add nomade user to appropriate groups or configure SLURM ACLs.
