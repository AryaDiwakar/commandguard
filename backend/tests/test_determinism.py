"""Determinism gate: same seed ⇒ identical telemetry; different seeds differ."""
from __future__ import annotations

import hashlib
import json

from conftest import make_generator
from app.simulation.generator import MachineGenerator


def _digest(gen: MachineGenerator, n: int) -> str:
    frames = [gen.step() for _ in range(n)]
    payload = json.dumps([f.to_dict() for f in frames], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def test_same_seed_identical():
    a = _digest(make_generator(seed=101), 90)
    b = _digest(make_generator(seed=101), 90)
    assert a == b


def test_different_seed_different():
    a = _digest(make_generator(seed=101), 90)
    b = _digest(make_generator(seed=102), 90)
    assert a != b