#!/usr/bin/env python3
"""
Patch to add queue_state, iostat, mpstat, vmstat tables to nomad demo.
Run from /home/cazuza/nomad/
"""

# Read demo.py
with open("nomad/demo.py") as f:
    content = f.read()

# ────────────────────────────────────────────────
# 1. Add new methods before run_demo function
# ────────────────────────────────────────────────

NEW_METHODS = '''
    def write_queue_state(self):
        """Write demo SLURM queue state data."""
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS queue_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                partition TEXT NOT NULL,
                pending_jobs INTEGER DEFAULT 0,
                running_jobs INTEGER DEFAULT 0,
                total_jobs INTEGER DEFAULT 0
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_queue_ts ON queue_state(timestamp)")

        base_time = datetime.now() - timedelta(days=7)
        partitions = {
            "compute": {"base_running": 30, "base_pending": 8},
            "highmem": {"base_running": 5, "base_pending": 2},
            "gpu": {"base_running": 12, "base_pending": 6},
        }

        for i in range(336):  # 7 days * 48 samples/day (every 30 min)
            sample_time = base_time + timedelta(minutes=i * 30)
            hour = sample_time.hour
            weekday = sample_time.weekday()

            for part_name, cfg in partitions.items():
                # Higher activity during business hours
                if weekday < 5 and 9 <= hour < 17:
                    running = cfg["base_running"] + random.randint(-3, 8)
                    pending = cfg["base_pending"] + random.randint(0, 10)
                else:
                    running = max(1, cfg["base_running"] // 2 + random.randint(-2, 3))
                    pending = max(0, random.randint(0, 3))

                total = running + pending
                c.execute("""
                    INSERT INTO queue_state (timestamp, partition, pending_jobs, running_jobs, total_jobs)
                    VALUES (?, ?, ?, ?, ?)
                """, (sample_time.isoformat(), part_name, pending, running, total))

        conn.commit()
        conn.close()
        print(f"    Queue state: {336 * len(partitions)} samples (3 partitions x 7 days)")

    def write_iostat(self):
        """Write demo iostat CPU and device data."""
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS iostat_cpu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                user_percent REAL,
                system_percent REAL,
                iowait_percent REAL,
                idle_percent REAL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS iostat_device (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                device TEXT NOT NULL,
                read_kb_per_sec REAL,
                write_kb_per_sec REAL,
                read_await_ms REAL,
                write_await_ms REAL,
                util_percent REAL
            )
        """)

        base_time = datetime.now() - timedelta(days=7)
        devices = ["sda", "sdb", "nvme0n1"]

        for i in range(2016):  # 7 days * 288 samples/day (every 5 min)
            sample_time = base_time + timedelta(minutes=i * 5)
            hour = sample_time.hour
            weekday = sample_time.weekday()

            # CPU stats vary by time
            if weekday < 5 and 9 <= hour < 17:
                user_pct = random.uniform(15, 55)
                sys_pct = random.uniform(3, 12)
                iowait = random.uniform(1, 8)
            else:
                user_pct = random.uniform(2, 15)
                sys_pct = random.uniform(1, 5)
                iowait = random.uniform(0.1, 3)

            idle_pct = max(0, 100 - user_pct - sys_pct - iowait)

            c.execute("""
                INSERT INTO iostat_cpu (timestamp, user_percent, system_percent, iowait_percent, idle_percent)
                VALUES (?, ?, ?, ?, ?)
            """, (sample_time.isoformat(), round(user_pct, 1), round(sys_pct, 1),
                  round(iowait, 1), round(idle_pct, 1)))

            # Device stats
            for dev in devices:
                if dev == "nvme0n1":
                    read_kb = random.uniform(500, 50000)
                    write_kb = random.uniform(1000, 80000)
                    read_await = random.uniform(0.05, 0.5)
                    write_await = random.uniform(0.05, 0.8)
                    util = random.uniform(5, 40)
                else:
                    read_kb = random.uniform(100, 20000)
                    write_kb = random.uniform(200, 30000)
                    read_await = random.uniform(0.5, 5)
                    write_await = random.uniform(1, 10)
                    util = random.uniform(2, 60)

                if weekday < 5 and 9 <= hour < 17:
                    write_kb *= 1.5
                    util = min(99, util * 1.3)

                c.execute("""
                    INSERT INTO iostat_device (timestamp, device, read_kb_per_sec, write_kb_per_sec,
                                               read_await_ms, write_await_ms, util_percent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (sample_time.isoformat(), dev, round(read_kb, 1), round(write_kb, 1),
                      round(read_await, 2), round(write_await, 2), round(util, 1)))

        conn.commit()
        conn.close()
        print(f"    I/O stats: {2016} CPU samples, {2016 * len(devices)} device samples")

    def write_mpstat(self):
        """Write demo mpstat summary data."""
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS mpstat_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                num_cores INTEGER,
                avg_busy_percent REAL,
                max_busy_percent REAL,
                min_busy_percent REAL,
                std_busy_percent REAL,
                busy_spread REAL,
                imbalance_ratio REAL,
                cores_idle INTEGER,
                cores_saturated INTEGER
            )
        """)

        base_time = datetime.now() - timedelta(days=7)
        num_cores = 32

        for i in range(2016):
            sample_time = base_time + timedelta(minutes=i * 5)
            hour = sample_time.hour
            weekday = sample_time.weekday()

            if weekday < 5 and 9 <= hour < 17:
                avg_busy = random.uniform(25, 65)
                std_busy = random.uniform(10, 25)
            else:
                avg_busy = random.uniform(5, 20)
                std_busy = random.uniform(3, 12)

            max_busy = min(100, avg_busy + random.uniform(15, 35))
            min_busy = max(0, avg_busy - random.uniform(10, avg_busy * 0.8))
            spread = max_busy - min_busy
            imbalance = std_busy / max(avg_busy, 0.1)

            cores_idle = int(num_cores * max(0, (1 - avg_busy / 100)) * random.uniform(0.3, 0.7))
            cores_saturated = int(num_cores * (avg_busy / 100) * random.uniform(0, 0.2))

            c.execute("""
                INSERT INTO mpstat_summary (timestamp, num_cores, avg_busy_percent, max_busy_percent,
                                            min_busy_percent, std_busy_percent, busy_spread,
                                            imbalance_ratio, cores_idle, cores_saturated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sample_time.isoformat(), num_cores, round(avg_busy, 1), round(max_busy, 1),
                  round(min_busy, 1), round(std_busy, 1), round(spread, 1),
                  round(imbalance, 2), cores_idle, cores_saturated))

        conn.commit()
        conn.close()
        print(f"    CPU core stats: {2016} samples ({num_cores} cores)")

    def write_vmstat(self):
        """Write demo vmstat memory data."""
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS vmstat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                free_kb INTEGER,
                buffer_kb INTEGER,
                cache_kb INTEGER,
                swap_used_kb INTEGER,
                swap_in_kb INTEGER,
                swap_out_kb INTEGER,
                procs_blocked INTEGER,
                memory_pressure REAL
            )
        """)

        base_time = datetime.now() - timedelta(days=7)
        total_mem_kb = 128 * 1024 * 1024  # 128 GB

        for i in range(2016):
            sample_time = base_time + timedelta(minutes=i * 5)
            hour = sample_time.hour
            weekday = sample_time.weekday()

            if weekday < 5 and 9 <= hour < 17:
                used_pct = random.uniform(40, 80)
            else:
                used_pct = random.uniform(15, 40)

            cache_kb = int(total_mem_kb * random.uniform(0.1, 0.25))
            buffer_kb = int(total_mem_kb * random.uniform(0.01, 0.05))
            used_kb = int(total_mem_kb * used_pct / 100)
            free_kb = total_mem_kb - used_kb - cache_kb - buffer_kb
            free_kb = max(1024, free_kb)

            # Swap - occasional light usage
            if used_pct > 70 and random.random() > 0.7:
                swap_used = random.randint(1024, 512 * 1024)  # 1MB - 512MB
                swap_in = random.randint(0, 100)
                swap_out = random.randint(0, 200)
            else:
                swap_used = 0
                swap_in = 0
                swap_out = 0

            procs_blocked = random.randint(0, 2) if used_pct > 60 else 0
            pressure = min(1.0, (used_pct / 100) * random.uniform(0.8, 1.2))

            c.execute("""
                INSERT INTO vmstat (timestamp, free_kb, buffer_kb, cache_kb,
                                    swap_used_kb, swap_in_kb, swap_out_kb,
                                    procs_blocked, memory_pressure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sample_time.isoformat(), free_kb, buffer_kb, cache_kb,
                  swap_used, swap_in, swap_out, procs_blocked, round(pressure, 2)))

        conn.commit()
        conn.close()
        print(f"    Memory stats: {2016} samples")

'''

# Insert before run_demo function
content = content.replace("\ndef run_demo(", NEW_METHODS + "\ndef run_demo(")

# ────────────────────────────────────────────────
# 2. Add calls in run_demo
# ────────────────────────────────────────────────

content = content.replace(
    "    db.write_storage_state()\n",
    "    db.write_storage_state()\n"
    "    db.write_queue_state()\n"
    "    db.write_iostat()\n"
    "    db.write_mpstat()\n"
    "    db.write_vmstat()\n"
)

# Write
with open("nomad/demo.py", "w") as f:
    f.write(content)

print("✓ demo.py patched with queue_state, iostat, mpstat, vmstat generators")
print("\nNext: bump version, regenerate demo, test status")
