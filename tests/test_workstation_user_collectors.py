# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""
Tests for per-user workstation collectors: cgroup_probe and pacct.

These tests are self-contained — they build fake cgroup trees and synthesize
pacct records in memory. They do not require root, do not require the psacct
package, and do not contact any remote host.

Run standalone:    python3 tests/test_workstation_user_collectors.py
Run via pytest:    pytest tests/test_workstation_user_collectors.py -v
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import asdict
from pathlib import Path


from nomad.collectors import cgroup_probe
from nomad.collectors.cgroup_probe import (
    PROBE_VERSION,
    UserCgroupSnapshot,
    _parse_user_uid,
    _read_cpu_stat,
    _read_int,
    _read_io_stat,
    probe_users,
)
from nomad.collectors.pacct import (
    ACCT_V3_FORMAT,
    ACCT_V3_SIZE,
    AFORK,
    ASU,
    PacctFormatError,
    decode_comp_t,
    parse_pacct,
)


# =============================================================================
# Helpers
# =============================================================================

def _encode_comp_t(value: int) -> int:
    """Inverse of decode_comp_t. For synthesizing pacct records in tests."""
    if value == 0:
        return 0
    exponent = 0
    while value >= (1 << 13):
        value >>= 3
        exponent += 1
        if exponent > 7:
            raise ValueError("value too large for comp_t")
    return (exponent << 13) | (value & 0x1FFF)


def _build_pacct_v3_record(
    *, flag=0, tty=0, exitcode=0, uid=1000, gid=1000, pid=12345, ppid=1,
    btime=1700000000, etime=3.5, utime_ticks=200, stime_ticks=100,
    mem_kb=8192, io_chars=1024, rw=0, minflt=0, majflt=0, swaps=0,
    comm=b"python3",
) -> bytes:
    comm_padded = (comm + b"\x00" * 16)[:16]
    return struct.pack(
        ACCT_V3_FORMAT,
        flag, 3, tty, exitcode, uid, gid, pid, ppid, btime, etime,
        _encode_comp_t(utime_ticks), _encode_comp_t(stime_ticks),
        _encode_comp_t(mem_kb), _encode_comp_t(io_chars), _encode_comp_t(rw),
        _encode_comp_t(minflt), _encode_comp_t(majflt), _encode_comp_t(swaps),
        comm_padded,
    )


class _FakeCgroupBuilder:
    def __init__(self, tmpdir: Path):
        self.root = tmpdir
        self.user_slice = tmpdir / "user.slice"
        self.user_slice.mkdir(parents=True, exist_ok=True)

    def add_user(
        self, uid: int, *,
        cpu_usage_usec=1_000_000, cpu_user_usec=600_000, cpu_system_usec=400_000,
        memory_current=1024 * 1024 * 100, memory_peak=1024 * 1024 * 200,
        io_read_bytes=4096, io_write_bytes=8192, io_devices=None,
        pids_current=5,
        skip_cpu_stat=False, skip_memory_current=False, skip_memory_peak=False,
        skip_io_stat=False, skip_pids=False,
    ) -> Path:
        d = self.user_slice / f"user-{uid}.slice"
        d.mkdir(exist_ok=True)
        if not skip_cpu_stat:
            (d / "cpu.stat").write_text(
                f"usage_usec {cpu_usage_usec}\n"
                f"user_usec {cpu_user_usec}\n"
                f"system_usec {cpu_system_usec}\n"
                "nr_periods 0\nnr_throttled 0\nthrottled_usec 0\n"
            )
        if not skip_memory_current:
            (d / "memory.current").write_text(f"{memory_current}\n")
        if not skip_memory_peak and memory_peak is not None:
            (d / "memory.peak").write_text(f"{memory_peak}\n")
        if not skip_io_stat:
            devices = io_devices or [("8:0", io_read_bytes, io_write_bytes)]
            (d / "io.stat").write_text(
                "".join(
                    f"{dev} rbytes={rb} wbytes={wb} rios=10 wios=20\n"
                    for dev, rb, wb in devices
                )
            )
        if not skip_pids:
            (d / "pids.current").write_text(f"{pids_current}\n")
        return d


# =============================================================================
# pacct parser tests
# =============================================================================

class TestCompT(unittest.TestCase):
    def test_zero_roundtrip(self):
        self.assertEqual(decode_comp_t(_encode_comp_t(0)), 0)

    def test_small_values(self):
        for v in [1, 100, 1000, 8191]:
            self.assertEqual(decode_comp_t(_encode_comp_t(v)), v)

    def test_large_values_approximate(self):
        for v in [100000, 1_000_000, 10_000_000]:
            encoded = _encode_comp_t(v)
            decoded = decode_comp_t(encoded)
            self.assertLessEqual(abs(decoded - v) / v, 0.125)


class TestPacctParser(unittest.TestCase):
    def test_record_size_is_64(self):
        self.assertEqual(ACCT_V3_SIZE, 64)

    def test_single_record_roundtrip(self):
        data = _build_pacct_v3_record(
            pid=42, ppid=1, uid=0, gid=0, btime=1700000000, etime=10.5,
            utime_ticks=500, stime_ticks=250, mem_kb=16384,
            io_chars=2048, comm=b"sleep",
        )
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data); path = f.name
        try:
            records = list(parse_pacct(path))
            self.assertEqual(len(records), 1)
            r = records[0]
            self.assertEqual(r.pid, 42)
            self.assertEqual(r.command, "sleep")
            self.assertAlmostEqual(r.elapsed_seconds, 10.5, places=2)
            self.assertAlmostEqual(r.cpu_user_seconds, 5.0, places=2)
            self.assertAlmostEqual(r.cpu_system_seconds, 2.5, places=2)
            self.assertEqual(r.memory_avg_kb, 16384)
        finally:
            Path(path).unlink()

    def test_multiple_records(self):
        data = b"".join(
            _build_pacct_v3_record(pid=i, comm=f"cmd{i}".encode())
            for i in range(1, 6)
        )
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data); path = f.name
        try:
            parsed = list(parse_pacct(path))
            self.assertEqual([r.pid for r in parsed], [1, 2, 3, 4, 5])
        finally:
            Path(path).unlink()

    def test_since_filter(self):
        data = b"".join([
            _build_pacct_v3_record(pid=1, btime=1700000000, etime=10),
            _build_pacct_v3_record(pid=2, btime=1700000000, etime=20),
            _build_pacct_v3_record(pid=3, btime=1700000000, etime=30),
        ])
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data); path = f.name
        try:
            parsed = list(parse_pacct(path, since=1700000015))
            self.assertEqual([r.pid for r in parsed], [2, 3])
        finally:
            Path(path).unlink()

    def test_max_records(self):
        data = b"".join(_build_pacct_v3_record(pid=i) for i in range(1, 11))
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data); path = f.name
        try:
            parsed = list(parse_pacct(path, max_records=3))
            self.assertEqual(len(parsed), 3)
        finally:
            Path(path).unlink()

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            self.assertEqual(list(parse_pacct(path)), [])
        finally:
            Path(path).unlink()

    def test_partial_trailing_record_ignored(self):
        data = _build_pacct_v3_record(pid=99) + b"\x00" * 20
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data); path = f.name
        try:
            self.assertEqual(len(list(parse_pacct(path))), 1)
        finally:
            Path(path).unlink()

    def test_unsupported_version_raises(self):
        bad = struct.pack("=BB", 0, 2) + b"\x00" * (ACCT_V3_SIZE - 2)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(bad); path = f.name
        try:
            with self.assertRaises(PacctFormatError):
                list(parse_pacct(path))
        finally:
            Path(path).unlink()

    def test_flags_preserved(self):
        data = _build_pacct_v3_record(flag=AFORK | ASU, comm=b"sudo")
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data); path = f.name
        try:
            r = next(parse_pacct(path))
            self.assertTrue(r.flags & AFORK)
            self.assertTrue(r.flags & ASU)
        finally:
            Path(path).unlink()

    def test_non_utf8_command(self):
        data = _build_pacct_v3_record(comm=b"\xff\xfe\x80bad")
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data); path = f.name
        try:
            r = next(parse_pacct(path))
            self.assertIsInstance(r.command, str)
        finally:
            Path(path).unlink()


# =============================================================================
# cgroup probe tests
# =============================================================================

class TestCgroupReaders(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_read_int(self):
        p = self.tmpdir / "val"; p.write_text("42\n")
        self.assertEqual(_read_int(p), 42)

    def test_read_int_missing_returns_none(self):
        self.assertIsNone(_read_int(self.tmpdir / "nope"))

    def test_read_int_malformed_returns_none(self):
        p = self.tmpdir / "bad"; p.write_text("not a number\n")
        self.assertIsNone(_read_int(p))

    def test_read_cpu_stat(self):
        p = self.tmpdir / "cpu.stat"
        p.write_text("usage_usec 1000\nuser_usec 600\nsystem_usec 400\nnr_periods 0\n")
        r = _read_cpu_stat(p)
        self.assertEqual(r["usage_usec"], 1000)
        self.assertEqual(r["user_usec"], 600)

    def test_read_cpu_stat_ignores_unparseable(self):
        p = self.tmpdir / "cpu.stat"
        p.write_text("usage_usec 1000\nsome_future_field weird\nuser_usec 600\n")
        r = _read_cpu_stat(p)
        self.assertEqual(r["usage_usec"], 1000)
        self.assertNotIn("some_future_field", r)

    def test_read_io_stat_sums_across_devices(self):
        p = self.tmpdir / "io.stat"
        p.write_text(
            "8:0 rbytes=100 wbytes=200 rios=1 wios=2\n"
            "8:16 rbytes=300 wbytes=400 rios=3 wios=4\n"
            "259:0 rbytes=500 wbytes=600 rios=5 wios=6\n"
        )
        r, w = _read_io_stat(p)
        self.assertEqual(r, 900)
        self.assertEqual(w, 1200)

    def test_parse_user_uid(self):
        self.assertEqual(_parse_user_uid("user-1001.slice"), 1001)
        self.assertEqual(_parse_user_uid("user-0.slice"), 0)
        self.assertIsNone(_parse_user_uid("session-c1.scope"))
        self.assertIsNone(_parse_user_uid("user-abc.slice"))


class TestCgroupProbe(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.builder = _FakeCgroupBuilder(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_no_user_slice_returns_empty(self):
        empty = Path(tempfile.mkdtemp())
        try:
            self.assertEqual(probe_users(cgroup_root=empty), [])
        finally:
            shutil.rmtree(empty)

    def test_single_user(self):
        self.builder.add_user(uid=0)  # UID 0 always resolves to 'root'
        snaps = probe_users(cgroup_root=self.tmpdir, hostname="h", now=1700000000)
        self.assertEqual(len(snaps), 1)
        s = snaps[0]
        self.assertEqual(s.uid, 0)
        self.assertEqual(s.username, "root")
        self.assertEqual(s.cpu_usage_usec, 1_000_000)
        self.assertEqual(s.memory_current_bytes, 100 * 1024 * 1024)
        self.assertEqual(s.probe_version, PROBE_VERSION)

    def test_multiple_users_sorted(self):
        for uid in [1002, 0, 1001]:
            self.builder.add_user(uid=uid)
        snaps = probe_users(cgroup_root=self.tmpdir, hostname="h")
        self.assertEqual([s.uid for s in snaps], [0, 1001, 1002])

    def test_missing_memory_peak(self):
        # Kernels < 5.19 don't expose memory.peak
        self.builder.add_user(uid=0, memory_peak=None)
        snaps = probe_users(cgroup_root=self.tmpdir)
        self.assertIsNone(snaps[0].memory_peak_bytes)
        self.assertIsNotNone(snaps[0].memory_current_bytes)

    def test_missing_io_stat(self):
        self.builder.add_user(uid=0, skip_io_stat=True)
        snaps = probe_users(cgroup_root=self.tmpdir)
        self.assertIsNone(snaps[0].io_read_bytes)
        self.assertIsNone(snaps[0].io_write_bytes)

    def test_non_user_slice_dirs_ignored(self):
        (self.tmpdir / "user.slice" / "session-c1.scope").mkdir()
        self.builder.add_user(uid=1001)
        snaps = probe_users(cgroup_root=self.tmpdir)
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].uid, 1001)

    def test_session_epoch_changes_on_slice_recreate(self):
        d = self.builder.add_user(uid=1001)
        snap1 = probe_users(cgroup_root=self.tmpdir)[0]
        time.sleep(1.1)
        shutil.rmtree(d)
        self.builder.add_user(uid=1001)
        snap2 = probe_users(cgroup_root=self.tmpdir)[0]
        self.assertGreater(snap2.session_epoch, snap1.session_epoch)

    def test_output_is_json_serializable(self):
        self.builder.add_user(uid=0)
        snaps = probe_users(cgroup_root=self.tmpdir)
        json.dumps(asdict(snaps[0]))  # must not raise

    def test_subprocess_invocation(self):
        """Simulates SSH use: `ssh host python3 /path/cgroup_probe.py ...`"""
        self.builder.add_user(uid=0, memory_current=999)
        self.builder.add_user(uid=1001)
        probe_file = Path(cgroup_probe.__file__)
        result = subprocess.run(
            [sys.executable, str(probe_file),
             "--fake-root", str(self.tmpdir),
             "--hostname", "ssh-test"],
            capture_output=True, text=True, check=True,
        )
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2)
        parsed = [json.loads(ln) for ln in lines]
        self.assertEqual(parsed[0]["memory_current_bytes"], 999)
        self.assertEqual(parsed[0]["hostname"], "ssh-test")


if __name__ == "__main__":
    unittest.main(verbosity=2)
