import pytest
from fastapi.testclient import TestClient

from payments_lite.app import create_app

ALICE = {"Authorization": "Bearer fixture-token-alice"}
BOB = {"Authorization": "Bearer fixture-token-bob"}


@pytest.fixture
def client():
    return TestClient(create_app())
