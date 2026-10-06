import os
import tempfile

_tmpdir = tempfile.mkdtemp(prefix="cg_p1_")
os.environ["COMMANDGUARD_DB_URL"] = f"sqlite:///{_tmpdir}/test.db"

import pytest  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def make_generator(seed: int = 7, machine_id: str = "MX-101", speed: float = 1.0):
    from app.simulation.generator import MachineGenerator

    return MachineGenerator(machine_id=machine_id, seed=seed, session_id=f"S-{machine_id}-{seed}", speed=speed)