"""
Shared fixtures/conftest for integration tests.

Policy (per the bug-fix plan): integration tests require a running MongoDB
instance. When it is not reachable they are *skipped* (not failed) so that
the unit-test suite remains green in environments without infrastructure.
"""
from __future__ import annotations

import os

import pytest


def _mongo_is_reachable() -> bool:
    """Best-effort synchronous ping against the configured MongoDB URI."""
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/jobplatform")
    try:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=1500)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_mongo():
    """Skip every integration test in this tree when MongoDB is unavailable."""
    if not _mongo_is_reachable():
        pytest.skip("MongoDB not available — integration tests require running infra")
