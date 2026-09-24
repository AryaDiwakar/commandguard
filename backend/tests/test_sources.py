"""Data-source contract tests for replay and future live ingestion."""
from __future__ import annotations

import pytest

from app.schemas.telemetry import TelemetryFrame
from app.telemetry.source import HttpLiveDataSource, LiveDataSourceStub, ReplayDataSource


def test_replay_source_is_deterministic_and_read_only():
    frames = [TelemetryFrame(machine_id="MX-101", timestamp_ms=index) for index in range(2)]
    source = ReplayDataSource(frames)
    assert source.mode == "REPLAY"
    assert source.next_frame().timestamp_ms == 0
    assert source.next_frame().timestamp_ms == 1
    with pytest.raises(StopIteration):
        source.next_frame()


def test_live_stub_accepts_queued_frames():
    source = LiveDataSourceStub()
    frame = TelemetryFrame(machine_id="MX-101", timestamp_ms=10)
    with pytest.raises(StopIteration):
        source.next_frame()
    source.push(frame)
    assert source.next_frame().timestamp_ms == 10
    assert source.next_frame().timestamp_ms == 10


def test_http_live_adapter_normalizes_approved_gateway_payload():
    import httpx

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"Machine_ID": "MX-101", "timestamp_ms": 5, "Engine_Hours": 2.0}))
    source = HttpLiveDataSource("https://gateway.example", client=httpx.Client(transport=transport))
    frame = source.next_frame()
    assert source.mode == "LIVE"
    assert frame.machine_id == "MX-101"
    assert frame.engine_hours == 2.0
