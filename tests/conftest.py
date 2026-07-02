"""Shared pytest fixtures — the single source of truth for test isolation.

Why this file exists
────────────────────
The backend test suite used to be fragile to *collection order*: a hand-picked
subset of integration tests failed (cross-account 403 checks flipping to 200,
JWT-protected POSTs returning 401) while the full suite passed. Two shared
process-globals were responsible; this conftest neutralises both centrally so
there is exactly ONE isolation mechanism (replacing the per-file module-level
bootstrap and the per-file ``_reset_db`` fixtures the integration modules used
to carry).

1. ``JWT_SECRET`` — the actual culprit behind the order-dependent failures.
   ``backend.security._secret()`` reads ``os.environ["JWT_SECRET"]`` on *every*
   call, with a dev fallback when unset. Several integration modules create
   access tokens at *import* time (e.g. ``_TOKEN_A = create_access_token(...)``).
   Some modules set ``JWT_SECRET`` at import, others don't — so the secret used
   to *sign* a token depended on which module imported first, while the secret
   used to *validate* it (at run time) depended on which module set
   ``JWT_SECRET`` last. In full alphabetical order the ``test_auth_*`` modules
   import first and pin the secret before any token is signed, so signing and
   validation agree. In an arbitrary subset a non-auth module could sign with
   the dev fallback and then have its token rejected at run time → exactly the
   reported 403→200 / 401 failures. Assigning ``JWT_SECRET`` here, at conftest
   import (pytest imports the rootdir conftest before any test module), makes
   signing and validation always agree regardless of order.

2. ``backend.db`` process-globals (``DB_PATH`` / ``_client`` / ``SUPABASE_URL``
   / ``SUPABASE_KEY``). These are module-level and shared across all tests. The
   autouse fixture below points every test at its own private SQLite file and
   forces the Supabase-free SQLite fallback, so no test can read another's data
   or reach the real Supabase project.
"""

import os

import pytest

# Secret used by the whole suite. MUST be assigned before any test module is
# imported, because several modules sign tokens at import time and
# security._secret() reads this per call. (16+ chars — security._secret rejects
# anything shorter.)
_TEST_JWT_SECRET = "test-secret-at-least-16-chars-long-xxxx"

# Env that must never leak a real backend into the tests. Cleared at import so
# backend.db, when first imported by a test module, can't pick up real creds or
# a serverless flag from the ambient environment.
_CLEAR_ENV = (
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_KEY_1",
    "SUPABASE_SERVICE_ROLE_KEY",
    "VERCEL",
    "AWS_LAMBDA_FUNCTION_NAME",
)

os.environ["JWT_SECRET"] = _TEST_JWT_SECRET
for _k in _CLEAR_ENV:
    os.environ.pop(_k, None)

import backend.db as _db  # noqa: E402  — imported only after the env above is set

# Captured before any test can monkeypatch it (test_patient_context_cache
# reassigns db.get_supabase by direct attribute assignment). Restored per test
# so one test's pollution can't leak into later ones.
_ORIG_GET_SUPABASE = _db.get_supabase


@pytest.fixture(autouse=True)
def _isolate_backend(tmp_path):
    """Give every test a private SQLite DB and a clean, Supabase-free db state."""
    os.environ["JWT_SECRET"] = _TEST_JWT_SECRET
    for k in _CLEAR_ENV:
        os.environ.pop(k, None)

    # db.py ships hardcoded Supabase defaults, so clearing the env is not enough
    # to force the SQLite fallback — the module globals must be blanked too.
    _db.SUPABASE_URL = ""
    _db.SUPABASE_KEY = ""
    _db.get_supabase = _ORIG_GET_SUPABASE
    _db._client = None
    _db.DB_PATH = str(tmp_path / "test.db")
    _db._init_db()
    yield
