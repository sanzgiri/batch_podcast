# Integration tests

This directory is reserved for end-to-end integration tests that exercise multiple services together (extraction → LLM → TTS → DB).

The original `test_newsletter_processing.py` (deleted June 14, 2026) was a TDD scaffold against an aspirational pipeline API. Its 7 tests had been failing on `main` since the project started.

The actual end-to-end verification is currently performed by `scripts/smoke_test_render.py`, which is the right tool for this job: it exercises the full pipeline against live Ollama + live Kokoro and produces an audible MP3 you can validate by ear. Integration tests should NOT mock these components because that defeats the purpose — the bugs we've found so far were all in the integration layer.

Register the `integration` marker on each test placed here and they'll be selectable via `pytest -m integration`.
