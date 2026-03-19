# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Jo\u00e3o Tonini
"""
Tests for the AWS Cloud Collector.

Uses mocked boto3 clients -- no real AWS credentials required.
Run with: python -m pytest tests/test_aws_collector.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from typing import Any


# ── Mock boto3 before any cloud module imports ──────────────────────

mock_boto3 = MagicMock()
mock_boto3.__version__ = "0.0.0-mock"
mock_botocore = MagicMock()
sys.modules["boto3"] = mock_boto3
sys.modules["botocore"] = mock_botocore
sys.modules["botocore.exceptions"] = mock_botocore.exceptions

mock_botocore.exceptions.ClientError = type("ClientError", (Exception,), {})
mock_botocore.exceptions.NoCredentialsError = type("NoCredentialsError", (Exception,), {})
mock_botocore.exceptions.EndpointConnectionError = type("EndpointConnectionError", (Exception,), {})

from nomad.collectors.cloud.cloud_base import (
    CloudBaseCollector, CloudMetric, CloudAPIError, CANONICAL_METRICS,
)
from nomad.collectors.cloud.aws import AWSCollector, AWS_METRIC_MAP


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def aws_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "region": "us-east-1",
        "access_key_id": "test-key",
        "secret_access_key": "test-secret",
        "account_alias": "test-account",
        "lookback_minutes": 10,
        "metric_period": 300,
        "collect_cost": False,
        "collect_cw_agent_metrics": False,
        "tag_filters": {},
    }


@pytest.fixture
def mock_ec2_response() -> dict[str, Any]:
    return {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-abc123",
                        "InstanceType": "c5.4xlarge",
                        "Placement": {"AvailabilityZone": "us-east-1a"},
                        "State": {"Name": "running"},
                        "Tags": [
                            {"Key": "Name", "Value": "compute-node-01"},
                            {"Key": "Environment", "Value": "research"},
                        ],
                    },
                    {
                        "InstanceId": "i-def456",
                        "InstanceType": "p3.2xlarge",
                        "Placement": {"AvailabilityZone": "us-east-1b"},
                        "State": {"Name": "running"},
                        "Tags": [
                            {"Key": "Name", "Value": "gpu-node-01"},
                        ],
                    },
                ]
            }
        ]
    }


# ── CloudMetric tests ──────────────────────────────────────────────

class TestCloudMetric:

    def test_to_dict_minimal(self):
        m = CloudMetric(
            timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc),
            node_name="compute-node-01",
            cluster="test-account",
            metric_name="cpu_util",
            value=67.3,
            unit="percent",
            source="aws",
        )
        d = m.to_dict()
        assert d["node_name"] == "compute-node-01"
        assert d["metric_name"] == "cpu_util"
        assert d["value"] == 67.3
        assert d["source"] == "aws"
        assert "instance_type" not in d
        assert "cost_usd" not in d

    def test_to_dict_full(self):
        m = CloudMetric(
            timestamp=datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc),
            node_name="gpu-node-01",
            cluster="research-aws",
            metric_name="gpu_util",
            value=95.0,
            unit="percent",
            source="aws",
            instance_type="p3.2xlarge",
            availability_zone="us-east-1b",
            tags={"Environment": "research"},
            cost_usd=2.45,
        )
        d = m.to_dict()
        assert d["instance_type"] == "p3.2xlarge"
        assert d["cost_usd"] == 2.45
        assert "Environment" in d["tags"]


# ── Metric normalization tests ──────────────────────────────────────

class TestMetricNormalization:

    def test_canonical_names(self):
        assert AWS_METRIC_MAP["CPUUtilization"] == ("cpu_util", "percent")
        assert AWS_METRIC_MAP["NetworkIn"] == ("net_recv_bytes", "bytes")
        assert AWS_METRIC_MAP["mem_used_percent"] == ("mem_util", "percent")

    def test_gpu_metrics_mapped(self):
        assert "nvidia_smi_utilization_gpu" in AWS_METRIC_MAP
        assert AWS_METRIC_MAP["nvidia_smi_utilization_gpu"][0] == "gpu_util"

    def test_canonicalize_fallthrough(self):
        assert CANONICAL_METRICS.get("cpu_util") == "cpu_util"
        assert CANONICAL_METRICS.get("totally_unknown") is None


# ── AWS Collector tests ─────────────────────────────────────────────

class TestAWSCollector:

    def _make_collector(self, config):
        mock_ec2 = MagicMock()
        mock_cw = MagicMock()
        mock_ec2.describe_account_attributes.return_value = {}
        mock_boto3.Session.return_value.client.side_effect = (
            lambda svc, **kw: mock_ec2 if svc == "ec2" else mock_cw
        )
        collector = AWSCollector(config, db_path=":memory:")
        collector._authenticated = True
        collector._ec2_client = mock_ec2
        collector._cw_client = mock_cw
        return collector, mock_ec2, mock_cw

    def test_list_instances(self, aws_config, mock_ec2_response):
        collector, mock_ec2, _ = self._make_collector(aws_config)

        mock_paginator = MagicMock()
        mock_ec2.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [mock_ec2_response]

        # Bypass _api_call_with_retry — just execute the callable
        collector._api_call_with_retry = lambda fn, *a, **kw: fn()

        instances = collector._list_instances()

        assert len(instances) == 2
        assert instances[0]["instance_id"] == "i-abc123"
        assert instances[0]["name"] == "compute-node-01"
        assert instances[0]["instance_type"] == "c5.4xlarge"
        assert instances[1]["name"] == "gpu-node-01"

    def test_normalize_metric(self, aws_config):
        collector, _, _ = self._make_collector(aws_config)

        now = datetime.now(timezone.utc)
        raw = {
            "timestamp": now,
            "value": 67.3,
            "metric_name": "CPUUtilization",
            "namespace": "AWS/EC2",
        }
        instance = {
            "instance_id": "i-abc123",
            "instance_type": "c5.4xlarge",
            "availability_zone": "us-east-1a",
            "name": "compute-node-01",
            "tags": {"Environment": "research"},
        }

        metric = collector._normalize_metric(raw, instance)

        assert metric.metric_name == "cpu_util"
        assert metric.value == 67.3
        assert metric.unit == "percent"
        assert metric.source == "aws"
        assert metric.node_name == "compute-node-01"
        assert metric.cluster == "test-account"

    def test_store_creates_table(self, aws_config):
        import sqlite3

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()

        collector, _, _ = self._make_collector(aws_config)
        collector.db_path = tmp.name

        now = datetime.now(timezone.utc)
        data = [
            {
                "timestamp": now.isoformat(),
                "node_name": "compute-node-01",
                "cluster": "test-account",
                "metric_name": "cpu_util",
                "value": 67.3,
                "unit": "percent",
                "source": "aws",
            }
        ]

        collector.store(data)

        conn = sqlite3.connect(tmp.name)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cloud_metrics")
        count = cursor.fetchone()[0]
        cursor.execute("SELECT node_name, metric_name, value FROM cloud_metrics")
        row = cursor.fetchone()
        conn.close()
        os.unlink(tmp.name)

        assert count == 1
        assert row[0] == "compute-node-01"
        assert row[1] == "cpu_util"
        assert row[2] == 67.3


# ── Cloud base tests ────────────────────────────────────────────────

class TestCloudBaseCollector:

    def _make_cls(self):
        class _TC(CloudBaseCollector):
            name = "test"
            def _authenticate(self): pass
            def _list_instances(self): return []
            def _collect_metrics(self, s, e): return []
            def _normalize_metric(self, r, i): pass
        return _TC

    def test_credential_env_override(self):
        Cls = self._make_cls()
        os.environ["NOMAD_AWS_ACCESS_KEY_ID"] = "env-key"
        try:
            tc = Cls({"access_key_id": "config-key"}, db_path=":memory:")
            cred = tc._load_credential()
            assert cred.access_key_id == "env-key"
        finally:
            del os.environ["NOMAD_AWS_ACCESS_KEY_ID"]

    def test_retry_backoff(self):
        Cls = self._make_cls()
        tc = Cls({}, db_path=":memory:")
        tc._authenticated = True
        tc.MAX_RETRIES = 2
        tc.RETRY_BACKOFF_BASE = 0.01

        call_count = 0
        def failing_call():
            nonlocal call_count
            call_count += 1
            raise Exception("500 Internal Server Error")

        with pytest.raises(CloudAPIError):
            tc._api_call_with_retry(failing_call)

        assert call_count == 3

    def test_collect_returns_dicts(self):
        now = datetime.now(timezone.utc)

        class _MC(CloudBaseCollector):
            name = "test"
            def _authenticate(self): pass
            def _list_instances(self): return []
            def _collect_metrics(self, s, e):
                return [
                    CloudMetric(
                        timestamp=now, node_name="node-1", cluster="test",
                        metric_name="cpu_util", value=50.0,
                        unit="percent", source="test",
                    )
                ]
            def _normalize_metric(self, r, i): pass

        tc = _MC({}, db_path=":memory:")
        tc._authenticated = True
        result = tc.collect()

        assert len(result) == 1
        assert result[0]["node_name"] == "node-1"
        assert result[0]["value"] == 50.0
