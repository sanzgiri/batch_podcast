# Contract tests

This directory is reserved for FastAPI contract tests (request/response shape, status codes, error formats).

The original `test_newsletter_api.py` (deleted June 14, 2026) was a TDD scaffold against an aspirational FastAPI surface that never materialized in the code. Its 8 tests had been failing on `main` since the project started.

When real contract tests are written here, register the `contract` marker on each test and they'll be selectable via `pytest -m contract`.
