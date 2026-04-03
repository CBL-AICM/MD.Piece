"""Shared fixtures for MD.Piece tests."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture()
def mock_supabase():
    """Mock the Supabase client so tests run without a live database.

    Patches ``get_supabase`` in every module that imports it so the mock is
    used regardless of ``from backend.db import get_supabase`` semantics.
    """
    mock_client = MagicMock()

    # Patch in backend.db AND in every router that does
    # ``from backend.db import get_supabase``
    targets = [
        "backend.db.get_supabase",
        "backend.routers.patients.get_supabase",
        "backend.routers.doctors.get_supabase",
        "backend.routers.symptoms.get_supabase",
        "backend.routers.records.get_supabase",
    ]

    patches = [patch(t, return_value=mock_client) for t in targets]
    for p in patches:
        p.start()

    yield mock_client

    for p in patches:
        p.stop()


@pytest.fixture()
def client(mock_supabase):
    """FastAPI TestClient with mocked Supabase."""
    from backend.main import app

    return TestClient(app)
