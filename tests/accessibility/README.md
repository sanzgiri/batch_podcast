# Accessibility tests

This directory is reserved for WCAG 2.1 AA conformance tests of the Gradio web UI.

The original `test_accessibility.py` (deleted June 14, 2026) was a TDD scaffold that imported a non-existent `get_settings` symbol and assumed a running web server at `http://localhost:8000`. Its 3 tests had been failing on `main` since the project started.

When real accessibility tests are written here, register the `accessibility` marker on each test (add it to `pyproject.toml`'s `markers` list first to avoid the unknown-marker warning).
