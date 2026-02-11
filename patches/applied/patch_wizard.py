#!/usr/bin/env python3
"""
NØMADE Wizard Patcher v3
========================
Replaces the init() function in cli.py with the full setup wizard.

Usage:
    python3 patch_wizard.py /path/to/nomade/nomade/cli.py

Changes in v3:
    - Workstation groups skip headnode prompt (no headnode)
    - SSH to individual workstations tested per-department
    - SSH user prompt adapts wording to cluster type

Cumulative features:
    - Interactive setup wizard with clear instructions
    - SSH key generation and copy helper
    - Resume support (.wizard_state.json) for interrupted setups
    - Confirmation + edit/redo after each cluster
    - Auto-detection of partitions, nodes, GPUs, filesystems
    - Multi-cluster support (local + remote via SSH)
    - Workstation group support (no headnode required)
    - No local machine defaults leaked into remote config
"""

import sys
import shutil
from pathlib import Path

NEW_INIT = r'''
@cli.command()
@click.option('--system', is_flag=True, help='Install system-wide for HPC')
@click.option('--force', is_flag=True, help='Overwrite existing files')
@click.option('--quick', is_flag=True, help='Skip wizard, use auto-detected defaults')
@click.option('--no-systemd', is_flag=True, help='Skip systemd service installation')
@click.option('--no-prolog', is_flag=True, help='Skip SLURM prolog hook')
@click.pass_context
def init(ctx, system, force, quick, no_systemd, no_prolog):
    """Initialize NOMADE with an interactive setup wizard.

    \b
    The wizard walks you through configuring NØMADE for your
    HPC cluster(s). It will ask about your clusters, partitions,
    storage, and monitoring preferences.

    \b
    If the wizard is interrupted (Ctrl+C), your progress is saved
    automatically. Run 'nomade init' again to pick up where you
    left off.

    \b
    User install (default):
      ~/.config/nomade/nomade.toml   Configuration
      ~/.local/share/nomade/         Data directory

    \b
    System install (--system, requires root):
      /etc/nomade/nomade.toml        Configuration
      /var/lib/nomade/               Data directory

    \b
    Examples:
      nomade init                    Interactive wizard
      nomade init --quick            Auto-detect everything
      nomade init --force            Overwrite existing config
      sudo nomade init --system      System-wide installation
    """
    import shutil
    import subprocess as sp
    import os
    import json

    # ── Determine paths ──────────────────────────────────────────────
    if system:
        config_dir = Path('/etc/nomade')
        data_dir = Path('/var/lib/nomade')
        log_dir = Path('/var/log/nomade')
    else:
        config_dir = Path.home() / '.config' / 'nomade'
        data_dir = Path.home() / '.local' / 'share' / 'nomade'
        log_dir = data_dir / 'logs'

    config_file = config_dir / 'nomade.toml'

    # Check existing config
    if config_file.exists() and not force:
        click.echo(click.style(
            f"\n  Config already exists: {config_file}", fg="yellow"))
        if not click.confirm("  Overwrite it?", default=False):
            click.echo(
                "  Run with --force to overwrite, or edit the file directly.")
            return

    # ── Create directories ───────────────────────────────────────────
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / 'models').mkdir(exist_ok=True)
    except PermissionError:
        click.echo(click.style(
            "\n  Permission denied. Use: sudo nomade init --system",
            fg="red"))
        return

    # ── State file for resume support ────────────────────────────────
    state_file = config_dir / '.wizard_state.json'

    def save_state(state):
        """Save wizard progress so it can be resumed if interrupted."""
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            state['_timestamp'] = datetime.now().isoformat()
            state_file.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    def load_state():
        """Load saved wizard progress."""
        try:
            if state_file.exists():
                return json.loads(state_file.read_text())
        except Exception:
            pass
        return None

    def clear_state():
        """Remove state file after successful completion."""
        try:
            if state_file.exists():
                state_file.unlink()
        except Exception:
            pass

    # ── Helper: run a command locally or via SSH ─────────────────────
    def run_cmd(cmd, host=None, ssh_user=None, ssh_key=None):
        """Run a command locally or via SSH. Returns stdout or None."""
        if host:
            ssh_cmd = ["ssh", "-o", "ConnectTimeout=5",
                       "-o", "StrictHostKeyChecking=accept-new"]
            if ssh_key:
                ssh_cmd += ["-i", ssh_key]
            ssh_cmd += [f"{ssh_user}@{host}", cmd]
            full_cmd = ssh_cmd
        else:
            full_cmd = cmd.split()
        try:
            result = sp.run(full_cmd, capture_output=True, text=True,
                            timeout=15)
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def detect_partitions(host=None, ssh_user=None, ssh_key=None):
        out = run_cmd("sinfo -h -o %P", host, ssh_user, ssh_key)
        if out:
            return [l.strip().rstrip('*')
                    for l in out.split('\n') if l.strip()]
        return []

    def detect_nodes_per_partition(partition, host=None, ssh_user=None,
                                   ssh_key=None):
        out = run_cmd(f"sinfo -h -p {partition} -o %n",
                      host, ssh_user, ssh_key)
        if out:
            return sorted(set(
                l.strip() for l in out.split('\n') if l.strip()))
        return []

    def detect_gpu_nodes(host=None, ssh_user=None, ssh_key=None):
        out = run_cmd("sinfo -h -o %n,%G", host, ssh_user, ssh_key)
        if out:
            gpu = set()
            for line in out.split('\n'):
                parts = line.strip().split(',', 1)
                if len(parts) == 2 and 'gpu' in parts[1].lower():
                    gpu.add(parts[0])
            return sorted(gpu)
        return []

    def detect_filesystems(host=None, ssh_user=None, ssh_key=None):
        out = run_cmd("df -h --output=target", host, ssh_user, ssh_key)
        hpc_paths = {'/', '/home', '/scratch', '/localscratch', '/project',
                     '/work', '/data', '/shared'}
        if out:
            found = [l.strip() for l in out.split('\n')[1:]
                     if l.strip() in hpc_paths]
            return sorted(found) if found else ['/', '/home']
        return ['/', '/home']

    def has_command(cmd, host=None, ssh_user=None, ssh_key=None):
        return run_cmd(f"which {cmd}", host, ssh_user, ssh_key) is not None

    # ── Reusable collection helpers ──────────────────────────────────
    def collect_partitions(cluster, host, ssh_user, ssh_key):
        """Ask user about partitions and nodes. Modifies cluster."""
        cluster["partitions"] = {}
        is_hpc = cluster.get("type") == "hpc"
        is_remote_ws = (cluster.get("mode") == "remote"
                        and not is_hpc)

        if is_hpc:
            click.echo("  Detecting SLURM partitions... ", nl=False)
            detected = detect_partitions(host, ssh_user, ssh_key)
            gpu_nodes = detect_gpu_nodes(host, ssh_user, ssh_key)

            if detected:
                click.echo(click.style(
                    f"found {len(detected)}", fg="green"))
                click.echo()
                for p in detected:
                    click.echo(f"    • {p}")
                click.echo()
                use_all = click.confirm(
                    "  Monitor all of these partitions?", default=True)
                if use_all:
                    chosen = detected
                else:
                    click.echo()
                    click.echo("  Type the partition names you want,")
                    click.echo("  separated by commas:")
                    chosen_str = click.prompt(
                        "  Partitions",
                        default=', '.join(detected))
                    chosen = [p.strip() for p in chosen_str.split(',')
                              if p.strip()]
            else:
                click.echo(click.style(
                    "could not auto-detect", fg="yellow"))
                click.echo()
                click.echo(
                    "  NØMADE could not detect partitions automatically.")
                click.echo(
                    "  This usually means SLURM is not installed here,")
                click.echo(
                    "  or the SSH connection is not working yet.")
                click.echo()
                click.echo(
                    "  You can find partition names by running this")
                click.echo("  command on the cluster headnode:")
                click.echo('    sinfo -h -o "%P"')
                click.echo()
                click.echo(
                    "  Type your partition names separated by commas:")
                chosen_str = click.prompt("  Partitions")
                chosen = [p.strip() for p in chosen_str.split(',')
                          if p.strip()]
            click.echo()

            click.echo("  Detecting nodes per partition...")
            for p in chosen:
                nodes = detect_nodes_per_partition(
                    p, host, ssh_user, ssh_key)
                part_gpu = [n for n in nodes if n in gpu_nodes]
                if nodes:
                    gpu_info = (f" ({len(part_gpu)} with GPU)"
                                if part_gpu else "")
                    click.echo(
                        f"    {p}: {len(nodes)} nodes{gpu_info}")
                else:
                    click.echo(
                        f"    {p}: could not detect nodes automatically")
                    click.echo()
                    click.echo(f"  Type the node names for '{p}',")
                    click.echo(f"  separated by commas:")
                    click.echo(f"  (e.g., node01, node02, node03)")
                    nodes_str = click.prompt(
                        f"  Nodes for {p}", default="")
                    nodes = [n.strip() for n in nodes_str.split(',')
                             if n.strip()]
                    part_gpu = []

                cluster["partitions"][p] = {
                    "nodes": nodes,
                    "gpu_nodes": part_gpu,
                }
        else:
            # Workstation group
            click.echo(
                "  For workstation groups, you organize machines by")
            click.echo(
                "  department or lab. Each group becomes a section")
            click.echo("  in the dashboard.")
            click.echo()
            click.echo(
                "  Type your department/lab names, separated by commas:")
            click.echo("  (e.g., biology, chemistry, physics)")
            click.echo()
            depts_str = click.prompt("  Departments")
            depts = [d.strip() for d in depts_str.split(',')
                     if d.strip()]
            click.echo()

            for dept in depts:
                click.echo(f"  Type the hostnames for '{dept}',")
                click.echo(f"  separated by commas:")
                click.echo(f"  (e.g., bio-ws01, bio-ws02, bio-ws03)")
                nodes_str = click.prompt(f"  Nodes for {dept}")
                nodes = [n.strip() for n in nodes_str.split(',')
                         if n.strip()]
                cluster["partitions"][dept] = {
                    "nodes": nodes,
                    "gpu_nodes": [],
                }
                # Test SSH to first workstation in each group
                if is_remote_ws and nodes and ssh_user:
                    click.echo(
                        f"  Testing SSH to {nodes[0]}... ",
                        nl=False)
                    test = run_cmd(
                        "echo ok", nodes[0], ssh_user, ssh_key)
                    if test:
                        click.echo(click.style(
                            "✓ Connected", fg="green"))
                    else:
                        click.echo(click.style(
                            "✗ Could not connect", fg="yellow"))
                        click.echo(
                            f"    Check that {nodes[0]} is"
                            f" reachable and your SSH key"
                            f" is authorized.")
                click.echo()

    def collect_filesystems(cluster, host, ssh_user, ssh_key):
        """Ask user about filesystems. Modifies cluster."""
        # For workstation groups, probe first node instead of headnode
        probe_host = host
        if not probe_host and cluster.get("partitions"):
            first_part = next(iter(cluster["partitions"].values()), {})
            first_nodes = first_part.get("nodes", [])
            if first_nodes:
                probe_host = first_nodes[0]

        click.echo()
        click.echo(click.style("  Storage", fg="green", bold=True))
        click.echo()
        click.echo(
            "  Which filesystems should NØMADE monitor for disk")
        click.echo(
            "  usage? Common HPC paths: /, /home, /scratch,")
        click.echo("  /localscratch, /project")
        click.echo()
        detected_fs = detect_filesystems(
            probe_host, ssh_user, ssh_key)
        default_fs = ', '.join(detected_fs)
        fs_str = click.prompt(
            "  Filesystems (comma-separated)", default=default_fs)
        cluster["filesystems"] = [
            f.strip() for f in fs_str.split(',') if f.strip()]

    def collect_features(cluster, host, ssh_user, ssh_key):
        """Ask user about optional features. Modifies cluster."""
        # For workstation groups, probe first node instead of headnode
        probe_host = host
        if not probe_host and cluster.get("partitions"):
            first_part = next(iter(cluster["partitions"].values()), {})
            first_nodes = first_part.get("nodes", [])
            if first_nodes:
                probe_host = first_nodes[0]

        click.echo()
        click.echo(click.style(
            "  Optional Features", fg="green", bold=True))
        click.echo()

        has_gpu_cmd = has_command(
            "nvidia-smi", probe_host, ssh_user, ssh_key)
        if has_gpu_cmd:
            click.echo("  ✓ GPU support detected (nvidia-smi found)")
            cluster["has_gpu"] = click.confirm(
                "  Enable GPU monitoring?", default=True)
        else:
            click.echo("  ○ nvidia-smi not found (no GPU detected)")
            cluster["has_gpu"] = click.confirm(
                "  Enable GPU monitoring anyway?", default=False)

        has_nfs_cmd = has_command(
            "nfsiostat", probe_host, ssh_user, ssh_key)
        if has_nfs_cmd:
            click.echo(
                "  ✓ NFS monitoring available (nfsiostat found)")
            cluster["has_nfs"] = click.confirm(
                "  Enable NFS monitoring?", default=True)
        else:
            click.echo("  ○ nfsiostat not found (no NFS detected)")
            cluster["has_nfs"] = click.confirm(
                "  Enable NFS monitoring anyway?", default=False)

        has_jup = run_cmd(
            "pgrep -f jupyterhub",
            probe_host, ssh_user, ssh_key) is not None
        has_rst = run_cmd(
            "pgrep -f rserver",
            probe_host, ssh_user, ssh_key) is not None
        if has_jup or has_rst:
            services = []
            if has_jup:
                services.append("JupyterHub")
            if has_rst:
                services.append("RStudio Server")
            click.echo(f"  ✓ Detected: {', '.join(services)}")
            cluster["has_interactive"] = click.confirm(
                "  Enable interactive session monitoring?",
                default=True)
        else:
            click.echo(
                "  ○ No JupyterHub or RStudio Server detected")
            cluster["has_interactive"] = click.confirm(
                "  Enable interactive session monitoring?",
                default=False)

    def show_cluster_summary(cluster, is_remote):
        """Display a summary of a configured cluster."""
        click.echo(click.style(
            f"  ─── Summary: {cluster['name']} ───", fg="cyan"))
        click.echo()
        ctype_label = ("HPC cluster"
                       if cluster.get("type") == "hpc"
                       else "Workstation group")
        click.echo(f"    Type:         {ctype_label}")
        if cluster.get("host"):
            click.echo(f"    Headnode:     {cluster['host']}")
        if cluster.get("ssh_user"):
            click.echo(f"    SSH user:     {cluster['ssh_user']}")
        parts = cluster.get("partitions", {})
        part_label = ("Partition" if cluster.get("type") == "hpc"
                      else "Group")
        for pid, pdata in parts.items():
            gpu_info = (f" ({len(pdata['gpu_nodes'])} GPU)"
                        if pdata.get("gpu_nodes") else "")
            click.echo(
                f"    {part_label}:  "
                f"   {pid}"
                f" — {len(pdata['nodes'])} nodes{gpu_info}")
        click.echo(
            f"    Filesystems:  "
            f"{', '.join(cluster.get('filesystems', []))}")
        feats = []
        if cluster.get("has_gpu"):
            feats.append("GPU")
        if cluster.get("has_nfs"):
            feats.append("NFS")
        if cluster.get("has_interactive"):
            feats.append("Interactive")
        if feats:
            click.echo(f"    Monitoring:   {', '.join(feats)}")
        click.echo()

    # ── Banner ───────────────────────────────────────────────────────
    click.echo()
    click.echo(click.style(
        "  ◈ NØMADE Setup Wizard", fg="cyan", bold=True))
    click.echo(click.style(
        "  ══════════════════════════════════════", fg="cyan"))
    click.echo()

    # ── Check for previous incomplete setup ──────────────────────────
    saved = load_state()
    resume = False

    if saved and not quick:
        from datetime import datetime as dt
        try:
            ts = dt.fromisoformat(saved['_timestamp'])
            age = ts.strftime('%b %d at %H:%M')
        except Exception:
            age = "unknown time"

        click.echo("  A previous setup was interrupted.")
        click.echo()

        if saved.get('clusters'):
            click.echo("  Progress saved:")
            mode_label = ("remote (SSH)" if saved.get('is_remote')
                          else "local (headnode)")
            click.echo(f"    Mode: {mode_label}")
            for ci, c in enumerate(saved['clusters']):
                pcount = len(c.get('partitions', {}))
                click.echo(
                    f"    Cluster {ci+1}: "
                    f"{c.get('name', '?')} ({pcount} partitions)")
            remaining = (saved.get('num_clusters', 1)
                         - len(saved['clusters']))
            if remaining > 0:
                click.echo(
                    f"    {remaining} cluster(s) still to configure")
        click.echo(f"    (from {age})")
        click.echo()

        resume = click.confirm(
            "  Continue where you left off?", default=True)
        click.echo()

        if not resume:
            clear_state()
            saved = None

    if not saved or not resume:
        click.echo(
            "  This wizard will help you configure NØMADE for your")
        click.echo(
            "  HPC environment. Press Enter to accept the default")
        click.echo("  value shown in [brackets].")
        click.echo()

    # ── Collect configuration ────────────────────────────────────────
    clusters = (saved.get('clusters', [])
                if (saved and resume) else [])
    admin_email = (saved.get('admin_email', '')
                   if (saved and resume) else "")
    dash_port = (saved.get('dash_port', 8050)
                 if (saved and resume) else 8050)

    if quick:
        # ── Quick mode: auto-detect everything ───────────────────────
        click.echo("  Quick mode: auto-detecting your environment...")
        click.echo()
        hostname = run_cmd("hostname -s") or "my-cluster"
        partitions = detect_partitions()
        gpu_nodes = detect_gpu_nodes()
        filesystems = detect_filesystems()
        has_gpu = has_command("nvidia-smi")
        has_nfs = has_command("nfsiostat")
        has_jupyter = (
            run_cmd("pgrep -f jupyterhub") is not None)
        has_rstudio = (
            run_cmd("pgrep -f rserver") is not None)

        cluster = {
            "name": hostname,
            "mode": "local",
            "type": "hpc",
            "partitions": {},
            "filesystems": filesystems,
            "has_gpu": has_gpu,
            "has_nfs": has_nfs,
            "has_interactive": has_jupyter or has_rstudio,
        }
        for p in partitions:
            nodes = detect_nodes_per_partition(p)
            cluster["partitions"][p] = {
                "nodes": nodes,
                "gpu_nodes": [n for n in nodes if n in gpu_nodes],
            }
        clusters.append(cluster)

        click.echo(f"  Cluster:      {hostname}")
        click.echo(
            f"  Partitions:   "
            f"{', '.join(partitions) or 'none detected'}")
        click.echo(f"  Filesystems:  {', '.join(filesystems)}")
        click.echo(f"  GPU:          {'yes' if has_gpu else 'no'}")
        click.echo(f"  NFS:          {'yes' if has_nfs else 'no'}")
        click.echo(
            f"  Interactive:  "
            f"{'yes' if cluster['has_interactive'] else 'no'}")
        click.echo()

    else:
        # ── Interactive wizard ───────────────────────────────────────

        # Restore or ask for connection mode
        if saved and resume and 'is_remote' in saved:
            is_remote = saved['is_remote']
            num_clusters = saved.get('num_clusters', 1)
        else:
            # Step 1: Connection mode
            click.echo(click.style(
                "  Step 1: Connection Mode",
                fg="green", bold=True))
            click.echo()
            click.echo("  Where is NØMADE running?")
            click.echo()
            click.echo("    1) On the cluster headnode")
            click.echo(
                "       NØMADE has direct access to SLURM commands")
            click.echo("       like sinfo, squeue, and sacct.")
            click.echo()
            click.echo(
                "    2) On a separate machine"
                " (laptop, desktop, etc.)")
            click.echo(
                "       NØMADE will connect to your cluster(s)"
                " via SSH")
            click.echo(
                "       to run commands and collect data remotely.")
            click.echo()
            mode_choice = click.prompt(
                "  Select", type=click.IntRange(1, 2), default=1)
            is_remote = (mode_choice == 2)
            click.echo()
            save_state({
                'is_remote': is_remote, 'clusters': clusters,
                'admin_email': admin_email,
                'dash_port': dash_port})

            # ── SSH key setup helper (remote only) ───────────────────
            if is_remote:
                click.echo(click.style(
                    "  SSH Key Setup", fg="green", bold=True))
                click.echo()
                click.echo(
                    "  Remote mode requires SSH key authentication"
                    " so")
                click.echo(
                    "  NØMADE can connect to your cluster(s) without")
                click.echo(
                    "  asking for a password every time.")
                click.echo()

                ssh_dir = Path.home() / ".ssh"
                key_types = [
                    ("id_ed25519", "Ed25519 (recommended)"),
                    ("id_rsa", "RSA"),
                    ("id_ecdsa", "ECDSA"),
                ]
                found_keys = []
                for keyfile, label in key_types:
                    if (ssh_dir / keyfile).exists():
                        found_keys.append((keyfile, label))

                if found_keys:
                    click.echo("  ✓ Found existing SSH key(s):")
                    for keyfile, label in found_keys:
                        click.echo(
                            f"    • ~/.ssh/{keyfile} ({label})")
                    click.echo()
                else:
                    click.echo("  ○ No SSH keys found in ~/.ssh/")
                    click.echo()
                    click.echo(
                        "  An SSH key is like a digital ID card"
                        " that")
                    click.echo(
                        "  lets your computer prove who you are"
                        " to a")
                    click.echo(
                        "  remote server, without needing to type"
                        " a")
                    click.echo("  password.")
                    click.echo()

                    if click.confirm(
                            "  Would you like NØMADE to create one"
                            " for you?", default=True):
                        click.echo()
                        ssh_dir.mkdir(mode=0o700, exist_ok=True)
                        key_path = ssh_dir / "id_ed25519"
                        email = click.prompt(
                            "  Your email"
                            " (used as a label on the key)",
                            default=(os.getenv("USER", "user")
                                     + "@localhost"))
                        click.echo()
                        click.echo(
                            "  Generating SSH key... ", nl=False)

                        result = sp.run(
                            ["ssh-keygen", "-t", "ed25519",
                             "-C", email,
                             "-f", str(key_path), "-N", ""],
                            capture_output=True, text=True)
                        if result.returncode == 0:
                            click.echo(click.style(
                                "✓ Created", fg="green"))
                            click.echo(
                                "    Private key:"
                                " ~/.ssh/id_ed25519")
                            click.echo(
                                "    Public key: "
                                " ~/.ssh/id_ed25519.pub")
                            found_keys.append(
                                ("id_ed25519", "Ed25519"))
                        else:
                            click.echo(click.style(
                                "✗ Failed", fg="red"))
                            click.echo(
                                f"    {result.stderr.strip()}")
                            click.echo()
                            click.echo(
                                "  You can create one"
                                " manually later:")
                            click.echo(
                                '    ssh-keygen -t ed25519'
                                ' -C "your@email.com"')
                        click.echo()
                    else:
                        click.echo()
                        click.echo(
                            "  You can create one later"
                            " by running:")
                        click.echo(
                            '    ssh-keygen -t ed25519'
                            ' -C "your@email.com"')
                        click.echo()

                if found_keys:
                    click.echo(
                        "  To connect without a password, your"
                        " public")
                    click.echo(
                        "  key needs to be copied to each cluster.")
                    click.echo(
                        "  NØMADE can do this for you now.")
                    click.echo()
                    click.echo(
                        "  (This will ask for your cluster password"
                        " ONE TIME.")
                    click.echo(
                        "   After that, SSH will use the key"
                        " automatically.)")
                    click.echo()

                    if click.confirm(
                            "  Copy SSH key to your cluster(s)"
                            " now?",
                            default=True):
                        click.echo()
                        copy_host = click.prompt(
                            "  Cluster headnode hostname"
                            " (e.g., cluster.university.edu)")
                        copy_user = click.prompt(
                            "  SSH username"
                            " (your login on the cluster)")
                        click.echo()

                        key_to_copy = str(
                            ssh_dir / found_keys[0][0])
                        click.echo(
                            f"  Copying {found_keys[0][0]}"
                            f" to {copy_host}...")
                        click.echo(
                            f"  You will be asked for your"
                            f" password on {copy_host}.")
                        click.echo()

                        copy_result = sp.run(
                            ["ssh-copy-id",
                             "-i", key_to_copy + ".pub",
                             f"{copy_user}@{copy_host}"])
                        click.echo()
                        if copy_result.returncode == 0:
                            click.echo(click.style(
                                "  ✓ Key copied! Password-free"
                                " SSH is ready.", fg="green"))
                        else:
                            click.echo(click.style(
                                "  ✗ Could not copy key"
                                " automatically.",
                                fg="yellow"))
                            click.echo()
                            click.echo(
                                "  You can do it manually"
                                " later:")
                            click.echo(
                                "    ssh-copy-id your_username"
                                "@cluster.university.edu")
                        click.echo()
                    else:
                        click.echo()
                        click.echo(
                            "  No problem. Copy your key"
                            " later with:")
                        click.echo(
                            "    ssh-copy-id your_username"
                            "@cluster.university.edu")
                        click.echo()

            # Step 2: Number of clusters
            click.echo(click.style(
                "  Step 2: Clusters", fg="green", bold=True))
            click.echo()
            click.echo(
                "  How many HPC clusters or workstation groups"
                " do you")
            click.echo(
                "  want to monitor? Most sites have 1-3 clusters.")
            click.echo()
            num_clusters = click.prompt(
                "  Number of clusters",
                type=click.IntRange(1, 20), default=1)
            click.echo()
            save_state({
                'is_remote': is_remote,
                'num_clusters': num_clusters,
                'clusters': clusters,
                'admin_email': admin_email,
                'dash_port': dash_port})

        # ── Step 3: Configure each cluster ───────────────────────────
        start_from = len(clusters)

        for i in range(start_from, num_clusters):
            click.echo(click.style(
                f"  ─── Cluster {i + 1} of {num_clusters}"
                f" {'─' * 25}", fg="green"))
            click.echo()

            # Cluster name — always generic default
            default_name = f"cluster-{i + 1}"
            name = click.prompt(
                "  Cluster name", default=default_name)

            # Cluster type
            click.echo()
            click.echo("  What type of system is this?")
            click.echo(
                "    1) HPC cluster (managed by SLURM)")
            click.echo(
                "    2) Workstation group"
                " (department machines, not SLURM)")
            click.echo()
            ctype = click.prompt(
                "  Select",
                type=click.IntRange(1, 2), default=1)
            is_hpc = (ctype == 1)
            click.echo()

            cluster = {
                "name": name,
                "mode": "remote" if is_remote else "local",
                "type": "hpc" if is_hpc else "workstations",
                "partitions": {},
                "filesystems": ['/', '/home'],
                "has_gpu": False,
                "has_nfs": False,
                "has_interactive": False,
            }

            # SSH details (remote only)
            ssh_user = None
            ssh_key = None
            host = None
            if is_remote:
                if is_hpc:
                    # HPC: need a headnode to SSH into
                    click.echo("  SSH connection details:")
                    click.echo(
                        "  (NØMADE will use SSH to reach"
                        " this cluster)")
                    click.echo()
                    host = click.prompt(
                        "  Headnode hostname"
                        " (e.g., cluster.university.edu)")
                else:
                    # Workstations: no headnode, NØMADE connects
                    # directly to each machine
                    click.echo("  SSH connection details:")
                    click.echo(
                        "  For workstation groups, NØMADE connects")
                    click.echo(
                        "  directly to each machine via SSH. Just")
                    click.echo(
                        "  provide a username and key below — the")
                    click.echo(
                        "  individual machine hostnames will be set")
                    click.echo(
                        "  when you list your departments.")
                    click.echo()
                    host = None

                ssh_user = click.prompt(
                    "  SSH username"
                    " (your login on the machines)")
                default_key = str(
                    Path.home() / ".ssh" / "id_ed25519")
                if not Path(default_key).exists():
                    default_key = str(
                        Path.home() / ".ssh" / "id_rsa")
                ssh_key = click.prompt(
                    "  SSH key path", default=default_key)

                if host:
                    cluster["host"] = host
                cluster["ssh_user"] = ssh_user
                cluster["ssh_key"] = ssh_key

                # Test connection (HPC headnode only;
                # workstation nodes tested per-department)
                if host:
                    click.echo()
                    click.echo(
                        "  Testing SSH connection... ", nl=False)
                    test = run_cmd(
                        "echo ok", host, ssh_user, ssh_key)
                    if test:
                        click.echo(click.style(
                            "✓ Connected", fg="green"))
                    else:
                        click.echo(click.style(
                            "✗ Could not connect", fg="red"))
                        click.echo()
                        click.echo("  Check that:")
                        click.echo(
                            f"    - {host} is reachable"
                            f" from this machine")
                        click.echo(
                            f"    - SSH key {ssh_key} exists"
                            f" and is authorized")
                        click.echo(
                            f"    - Username '{ssh_user}'"
                            f" is correct")
                        click.echo()
                        click.echo(
                            "  You can fix these settings in the"
                            " config file later.")
                click.echo()

            # Collect partitions, filesystems, features
            collect_partitions(cluster, host, ssh_user, ssh_key)
            collect_filesystems(cluster, host, ssh_user, ssh_key)
            collect_features(cluster, host, ssh_user, ssh_key)
            click.echo()

            # ── Confirm / edit / redo loop ───────────────────────────
            while True:
                show_cluster_summary(cluster, is_remote)

                choice = click.prompt(
                    "  Is this correct?"
                    " (y)es / (e)dit / (s)tart over",
                    type=click.Choice(
                        ['y', 'e', 's'],
                        case_sensitive=False),
                    default='y')

                if choice == 'y':
                    break

                elif choice == 's':
                    # Redo entire cluster
                    click.echo()
                    click.echo(click.style(
                        f"  ─── Cluster {i + 1}"
                        f" of {num_clusters}"
                        f" (redo) {'─' * 19}",
                        fg="green"))
                    click.echo()

                    name = click.prompt(
                        "  Cluster name",
                        default=cluster["name"])
                    cluster["name"] = name

                    click.echo()
                    click.echo(
                        "  What type of system is this?")
                    click.echo(
                        "    1) HPC cluster"
                        " (managed by SLURM)")
                    click.echo(
                        "    2) Workstation group"
                        " (department machines,"
                        " not SLURM)")
                    click.echo()
                    ctype = click.prompt(
                        "  Select",
                        type=click.IntRange(1, 2),
                        default=1)
                    is_hpc = (ctype == 1)
                    cluster["type"] = (
                        "hpc" if is_hpc
                        else "workstations")
                    click.echo()

                    if is_remote:
                        if is_hpc:
                            host = click.prompt(
                                "  Headnode hostname",
                                default=cluster.get(
                                    "host", ""))
                            cluster["host"] = host
                        else:
                            host = None
                            cluster.pop("host", None)
                        ssh_user = click.prompt(
                            "  SSH username"
                            " (your login on the machines)",
                            default=cluster.get(
                                "ssh_user", ""))
                        ssh_key = click.prompt(
                            "  SSH key path",
                            default=cluster.get(
                                "ssh_key", ""))
                        cluster["ssh_user"] = ssh_user
                        cluster["ssh_key"] = ssh_key
                        click.echo()

                    collect_partitions(
                        cluster, host, ssh_user, ssh_key)
                    collect_filesystems(
                        cluster, host, ssh_user, ssh_key)
                    collect_features(
                        cluster, host, ssh_user, ssh_key)
                    click.echo()
                    continue

                elif choice == 'e':
                    click.echo()
                    click.echo(
                        "  What would you like to edit?")
                    click.echo("    1) Cluster name")
                    click.echo(
                        "    2) Partitions and nodes")
                    click.echo("    3) Filesystems")
                    click.echo(
                        "    4) Optional features"
                        " (GPU / NFS / Interactive)")
                    if is_remote:
                        click.echo(
                            "    5) SSH connection")
                    click.echo()
                    max_opt = 5 if is_remote else 4
                    edit_choice = click.prompt(
                        "  Select",
                        type=click.IntRange(1, max_opt))

                    if edit_choice == 1:
                        cluster["name"] = click.prompt(
                            "  Cluster name",
                            default=cluster["name"])

                    elif edit_choice == 2:
                        click.echo()
                        p_label = ("partitions"
                                   if cluster.get("type") == "hpc"
                                   else "groups")
                        click.echo(
                            f"  Current {p_label}:")
                        for pid, pdata in (
                                cluster[
                                    "partitions"].items()):
                            ncount = len(pdata["nodes"])
                            click.echo(
                                f"    • {pid}"
                                f" ({ncount} nodes)")
                        click.echo()
                        click.echo(
                            f"  Enter ALL {p_label} names"
                            f" you want")
                        click.echo(
                            "  (this replaces the"
                            " current list):")
                        current = ', '.join(
                            cluster["partitions"].keys())
                        new_str = click.prompt(
                            f"  {'Partitions' if cluster.get('type') == 'hpc' else 'Groups'}",
                            default=current)
                        new_parts = [
                            p.strip()
                            for p in new_str.split(',')
                            if p.strip()]

                        _h = cluster.get("host")
                        _u = cluster.get("ssh_user")
                        _k = cluster.get("ssh_key")
                        gn = detect_gpu_nodes(_h, _u, _k)

                        new_partitions = {}
                        for p in new_parts:
                            if p in cluster["partitions"]:
                                new_partitions[p] = (
                                    cluster[
                                        "partitions"][p])
                                nc = len(
                                    new_partitions[p][
                                        'nodes'])
                                click.echo(
                                    f"    {p}: keeping"
                                    f" {nc} nodes")
                            else:
                                if cluster.get("type") == "hpc":
                                    nodes = (
                                        detect_nodes_per_partition(
                                            p, _h, _u, _k))
                                    pg = [n for n in nodes
                                          if n in gn]
                                    if nodes:
                                        click.echo(
                                            f"    {p}:"
                                            f" detected"
                                            f" {len(nodes)}"
                                            f" nodes")
                                    else:
                                        click.echo(
                                            f"  Nodes for"
                                            f" '{p}',"
                                            f" comma-separated:")
                                        ns = click.prompt(
                                            f"  Nodes for {p}")
                                        nodes = [
                                            n.strip()
                                            for n in
                                            ns.split(',')
                                            if n.strip()]
                                        pg = []
                                else:
                                    click.echo(
                                        f"  Hostnames for"
                                        f" '{p}',"
                                        f" comma-separated:")
                                    ns = click.prompt(
                                        f"  Nodes for {p}")
                                    nodes = [
                                        n.strip()
                                        for n in
                                        ns.split(',')
                                        if n.strip()]
                                    pg = []
                                new_partitions[p] = {
                                    "nodes": nodes,
                                    "gpu_nodes": pg}
                        cluster["partitions"] = (
                            new_partitions)

                    elif edit_choice == 3:
                        current_fs = ', '.join(
                            cluster.get(
                                "filesystems", []))
                        fs_str = click.prompt(
                            "  Filesystems"
                            " (comma-separated)",
                            default=current_fs)
                        cluster["filesystems"] = [
                            f.strip()
                            for f in fs_str.split(',')
                            if f.strip()]

                    elif edit_choice == 4:
                        cluster["has_gpu"] = (
                            click.confirm(
                                "  Enable GPU monitoring?",
                                default=cluster.get(
                                    "has_gpu", False)))
                        cluster["has_nfs"] = (
                            click.confirm(
                                "  Enable NFS monitoring?",
                                default=cluster.get(
                                    "has_nfs", False)))
                        cluster["has_interactive"] = (
                            click.confirm(
                                "  Enable interactive"
                                " session monitoring?",
                                default=cluster.get(
                                    "has_interactive",
                                    False)))

                    elif (edit_choice == 5
                          and is_remote):
                        if is_hpc:
                            cluster["host"] = click.prompt(
                                "  Headnode hostname",
                                default=cluster.get(
                                    "host", ""))
                            host = cluster["host"]
                        cluster["ssh_user"] = (
                            click.prompt(
                                "  SSH username"
                                " (your login on"
                                " the machines)",
                                default=cluster.get(
                                    "ssh_user", "")))
                        cluster["ssh_key"] = (
                            click.prompt(
                                "  SSH key path",
                                default=cluster.get(
                                    "ssh_key", "")))
                        ssh_user = cluster["ssh_user"]
                        ssh_key = cluster["ssh_key"]

                    click.echo()
                    continue

            # Save after each confirmed cluster
            clusters.append(cluster)
            save_state({
                'is_remote': is_remote,
                'num_clusters': num_clusters,
                'clusters': clusters,
                'admin_email': admin_email,
                'dash_port': dash_port})

        # ── Alerts ───────────────────────────────────────────────────
        click.echo(click.style(
            "  Step 3: Alerts", fg="green", bold=True))
        click.echo()
        click.echo(
            "  NØMADE can send you email alerts when something"
            " needs")
        click.echo(
            "  attention (disk filling up, nodes going down,"
            " etc.).")
        click.echo(
            "  You can also view all alerts in the dashboard.")
        click.echo()
        admin_email = click.prompt(
            "  Your email address (press Enter to skip)",
            default="", show_default=False)
        click.echo()
        save_state({
            'is_remote': is_remote,
            'num_clusters': num_clusters,
            'clusters': clusters,
            'admin_email': admin_email,
            'dash_port': dash_port})

        # ── Dashboard ────────────────────────────────────────────────
        click.echo(click.style(
            "  Step 4: Dashboard", fg="green", bold=True))
        click.echo()
        click.echo(
            "  The NØMADE dashboard is a web page you open in"
            " your")
        click.echo(
            "  browser to view cluster status, node health, and")
        click.echo(
            "  alerts. It runs on a port you choose.")
        click.echo()
        dash_port = click.prompt(
            "  Dashboard port", type=int, default=8050)
        click.echo()

    # ══════════════════════════════════════════════════════════════════
    # Generate TOML config file
    # ══════════════════════════════════════════════════════════════════
    lines = []
    lines.append("# NØMADE Configuration File")
    lines.append("# Generated by: nomade init")
    lines.append(
        f"# Date:"
        f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("[general]")
    lines.append('log_level = "info"')
    lines.append(f'data_dir = "{data_dir}"')
    lines.append("")

    lines.append("[database]")
    lines.append('path = "nomade.db"')
    lines.append("")

    # Collectors
    coll_list = ["disk", "slurm", "node_state"]
    any_gpu = any(c.get("has_gpu") for c in clusters)
    any_nfs = any(c.get("has_nfs") for c in clusters)
    any_interactive = any(
        c.get("has_interactive") for c in clusters)
    if any_gpu:
        coll_list.append("gpu")
    if any_nfs:
        coll_list.append("nfs")
    if any_interactive:
        coll_list.append("interactive")

    lines.append("[collectors]")
    coll_str = ', '.join(f'"{c}"' for c in coll_list)
    lines.append(f"enabled = [{coll_str}]")
    lines.append("interval = 60")
    lines.append("")

    # Filesystems
    all_fs = set()
    for c in clusters:
        all_fs.update(c.get("filesystems", []))
    fs_items = ', '.join(f'"{f}"' for f in sorted(all_fs))
    lines.append("[collectors.disk]")
    lines.append(f"filesystems = [{fs_items}]")
    lines.append("")

    # SLURM partitions
    all_parts = set()
    for c in clusters:
        if c.get("type", "hpc") == "hpc":
            all_parts.update(
                c.get("partitions", {}).keys())
    if all_parts:
        parts_items = ', '.join(
            f'"{p}"' for p in sorted(all_parts))
        lines.append("[collectors.slurm]")
        lines.append(f"partitions = [{parts_items}]")
        lines.append("")

    if any_gpu:
        lines.append("[collectors.gpu]")
        lines.append("enabled = true")
        lines.append("")

    if any_nfs:
        lines.append("[collectors.nfs]")
        lines.append("mount_points = []")
        lines.append("")

    # Clusters
    lines.append("# ============================================")
    lines.append("# CLUSTERS")
    lines.append("# ============================================")
    lines.append("")

    for cluster in clusters:
        cid = cluster["name"].lower().replace(' ', '-')
        lines.append(f'[clusters.{cid}]')
        lines.append(f'name = "{cluster["name"]}"')
        lines.append(
            f'type = "{cluster.get("type", "hpc")}"')

        if cluster.get("mode") == "remote":
            if cluster.get("host"):
                lines.append(f'host = "{cluster["host"]}"')
            lines.append(
                f'ssh_user = "{cluster["ssh_user"]}"')
            lines.append(
                f'ssh_key = "{cluster["ssh_key"]}"')

        total_nodes = sum(
            len(p["nodes"])
            for p in cluster["partitions"].values())
        ctype_label = (
            "cluster" if cluster.get("type") == "hpc"
            else "workstation group")
        lines.append(
            f'description ='
            f' "{total_nodes}-node {ctype_label}"')
        lines.append("")

        sect_label = ("partitions"
                      if cluster.get("type") == "hpc"
                      else "groups")
        for pid, pdata in cluster["partitions"].items():
            lines.append(
                f'[clusters.{cid}.{sect_label}.{pid}]')
            desc_label = ("partition"
                          if cluster.get("type") == "hpc"
                          else "group")
            lines.append(
                f'description ='
                f' "{len(pdata["nodes"])}-node {desc_label}"')
            nodes_items = ', '.join(
                f'"{n}"' for n in pdata["nodes"])
            lines.append(f'nodes = [{nodes_items}]')
            if pdata.get("gpu_nodes"):
                gpu_items = ', '.join(
                    f'"{n}"' for n in pdata["gpu_nodes"])
                lines.append(f'gpu_nodes = [{gpu_items}]')
            lines.append("")

    # Alerts
    lines.append("# ============================================")
    lines.append("# ALERTS")
    lines.append("# ============================================")
    lines.append("")
    lines.append("[alerts]")
    lines.append("enabled = true")
    lines.append('min_severity = "warning"')
    lines.append("cooldown_minutes = 15")
    lines.append("")
    lines.append("[alerts.thresholds.disk]")
    lines.append("used_percent_warning = 80")
    lines.append("used_percent_critical = 95")
    lines.append("")

    if any_interactive:
        lines.append("[alerts.thresholds.interactive]")
        lines.append("idle_sessions_warning = 50")
        lines.append("idle_sessions_critical = 100")
        lines.append("memory_gb_warning = 32")
        lines.append("memory_gb_critical = 64")
        lines.append("")

    if admin_email:
        lines.append("[alerts.email]")
        lines.append("enabled = true")
        lines.append(
            "# Update these with your SMTP server details:")
        lines.append('smtp_server = "smtp.example.com"')
        lines.append("smtp_port = 587")
        lines.append('from_address = "nomade@example.com"')
        lines.append(f'recipients = ["{admin_email}"]')
        lines.append("")

    # Dashboard
    lines.append("# ============================================")
    lines.append("# DASHBOARD")
    lines.append("# ============================================")
    lines.append("")
    lines.append("[dashboard]")
    lines.append('host = "127.0.0.1"')
    lines.append(f"port = {dash_port}")
    lines.append("")

    # ML
    lines.append("# ============================================")
    lines.append("# ML PREDICTION")
    lines.append("# ============================================")
    lines.append("")
    lines.append("[ml]")
    lines.append("enabled = true")
    lines.append("")

    # Write the config
    config_content = '\n'.join(lines)
    config_file.write_text(config_content)

    # Clean up wizard state file
    clear_state()

    # ── Summary ──────────────────────────────────────────────────────
    click.echo(click.style(
        "  ══════════════════════════════════════", fg="cyan"))
    click.echo(click.style(
        "  ✓ NØMADE configured!", fg="green", bold=True))
    click.echo()
    click.echo(f"  Config:  {config_file}")
    click.echo(f"  Data:    {data_dir}")
    click.echo()
    click.echo("  Clusters:")
    for c in clusters:
        pcount = len(c["partitions"])
        ncount = sum(
            len(p["nodes"])
            for p in c["partitions"].values())
        if c.get("host"):
            loc = f" → {c['host']}"
        elif c.get("mode") == "remote":
            loc = " (SSH to each node)"
        else:
            loc = " (local)"
        click.echo(
            f"    • {c['name']}:"
            f" {pcount} groups,"
            f" {ncount} nodes{loc}")
    click.echo()

    features = []
    if any_gpu:
        features.append("GPU monitoring")
    if any_nfs:
        features.append("NFS monitoring")
    if any_interactive:
        features.append("interactive sessions")
    if features:
        click.echo(f"  Enabled: {', '.join(features)}")
        click.echo()

    click.echo(click.style("  What to do next:", bold=True))
    click.echo()
    click.echo(f"    1. Review your config (optional):")
    click.echo(f"         nano {config_file}")
    click.echo()
    click.echo(f"    2. Check that everything is ready:")
    click.echo(f"         nomade syscheck")
    click.echo()
    click.echo(f"    3. Start collecting data:")
    click.echo(f"         nomade collect")
    click.echo()
    click.echo(
        f"    4. Open the dashboard in your browser:")
    click.echo(f"         nomade dashboard")
    click.echo()
'''


def patch(cli_path: str):
    path = Path(cli_path)
    if not path.exists():
        print(f"ERROR: {cli_path} not found")
        sys.exit(1)

    content = path.read_text()
    lines = content.split('\n')

    # Find init function boundaries
    init_decorator_line = None
    init_def_line = None
    init_end_line = None

    for i, line in enumerate(lines):
        if 'def init(' in line and 'def init_' not in line:
            init_def_line = i
            for j in range(i - 1, max(i - 15, 0), -1):
                if '@cli.command()' in lines[j]:
                    init_decorator_line = j
                    break
            break

    if init_decorator_line is None or init_def_line is None:
        print("ERROR: Could not find init() function in cli.py")
        sys.exit(1)

    # Find end: next top-level decorator/function after init
    for i in range(init_def_line + 1, len(lines)):
        stripped = lines[i].lstrip()
        leading = len(lines[i]) - len(lines[i].lstrip())
        if leading == 0 and (
            stripped.startswith('@cli.command(')
            or stripped.startswith('@cli.group(')
            or stripped.startswith('def ')
        ):
            init_end_line = i
            break

    if init_end_line is None:
        print("ERROR: Could not find end of init() function")
        sys.exit(1)

    print(f"Found init() at lines"
          f" {init_decorator_line+1}-{init_end_line}")
    print(f"  ({init_end_line - init_decorator_line}"
          f" lines to replace)")

    # Create backup
    backup = path.with_suffix('.py.bak')
    shutil.copy(path, backup)
    print(f"Backup saved: {backup}")

    # Build new content
    before = '\n'.join(lines[:init_decorator_line])
    after = '\n'.join(lines[init_end_line:])
    new_content = (before + '\n'
                   + NEW_INIT.strip() + '\n\n\n' + after)

    path.write_text(new_content)

    new_count = new_content.count('\n')
    old_count = content.count('\n')
    print(f"Patched: {old_count} → {new_count} lines")
    print()
    print("Done! Test with:")
    print("  nomade init --force")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(
            "Usage: python3 patch_wizard.py"
            " /path/to/nomade/nomade/cli.py")
        sys.exit(1)
    patch(sys.argv[1])
