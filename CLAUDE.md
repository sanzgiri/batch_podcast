# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Newsletter Podcast Generator - Convert newsletter content into podcast episodes using AI-powered summarization and text-to-speech. Built with Python 3.11+, FastAPI. Fully local: Ollama for LLM summarization, Kokoro for TTS (via the integrated `src/lib/tts_engine` pipeline derived from text2audio). No cloud APIs required.

**Default LLM model**: `llama3.1:8b-instruct-q4_K_M` (configurable via `config/development.yaml`). Any Ollama instruct model works — `llama3.1:8b` is a good baseline that produces solid dialogue scripts; smaller models like `qwen2.5:3b-instruct` are faster but may drop structured JSON fields.

**Smoke test**: `python scripts/smoke_test_render.py` runs an end-to-end pipeline against a hardcoded AI-news sample. Use `--skip-llm` for TTS-only iteration.

## Development Commands

### Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp config/development.yaml.template config/development.yaml
cp config/newsletters.yaml.template config/newsletters.yaml
python -c "import asyncio; from src.lib.database import init_database; asyncio.run(init_database())"
```

### Testing
```bash
pytest                                    # All tests with coverage (80% min enforced)
pytest tests/unit/                        # Unit tests only
pytest tests/integration/                 # Integration tests only
pytest tests/contract/                    # Contract tests only
pytest tests/unit/test_content_extractor.py  # Single file
pytest --no-cov                           # Skip coverage requirements
```

### Code Quality
```bash
ruff check .          # Lint
ruff format .         # Format
mypy src/             # Type checking (strict mode)
pre-commit run --all-files  # All hooks (ruff, mypy, isort; pytest runs on push)
```

### Running
```bash
python -m uvicorn src.api.main:app --reload                          # API server
python -m src process-url "https://example.com/newsletter" --wait    # Process URL
python -m src process-url "URL" --newsletter the-batch --wait        # With profile
python -m src process-file newsletter.txt --wait                     # Process file
python -m src status <newsletter-id>                                 # Check status
python -m src health                                                 # Health check
python -m src voices                                                 # List TTS voices
python -m src costs summary                                          # Cost report
```

### Database Migrations
```bash
python scripts/migrate_add_newsletter_profiles.py   # Add profile fields
python scripts/migrate_add_cost_tracking.py          # Add cost tracking fields
```

## Architecture Overview

### Core Pipeline

Newsletter processing follows this flow, orchestrated by `NewsletterProcessor` (`src/services/newsletter_processor.py`):

1. **Content Extraction** (`src/services/content_extractor.py`) - Extracts and cleans text from URLs or direct input (HTML/Markdown/Text)
2. **LLM Summarization** (`src/services/llm_summarizer.py`) - Transforms content into podcast-style script using Ollama (local) or OpenAI. Supports `mode="monologue"` (single narrator script) and `mode="dialogue"` (Host/Guest two-speaker transcript).
3. **TTS Generation** (`src/services/tts_generator.py`) - Converts script to audio using Kokoro via the bundled `src/lib/tts_engine` pipeline. Features voice blending, paragraph-level silence injection, pronunciation overrides, abbreviation expansion, dialogue alternation, and ffmpeg `loudnorm`.
4. **Episode Storage** - Saves MP3 with profile-aware file organization via `StorageManager` (`src/lib/storage.py`). The TTS engine writes directly to the storage-manager-derived path.

Status tracking through database: `pending → extracting → summarizing → generating_audio → completed`

### Service Architecture

**Provider Pattern**: AI services use abstract base classes with concrete implementations:
- `BaseLLMClient` → `OpenAIClient` / `OllamaClient`
- `BaseTTSClient` → `KokoroTTSClient` (cloud TTS providers were removed; all rendering is local)

All services are async context managers for proper resource management.

### TTS Engine (`src/lib/tts_engine`)

Local Kokoro rendering pipeline vendored from text2audio (https://github.com/sanzgiri/text2audio). Modules:
- `blocks.py` — `Block` / `Chapter` dataclasses (universal across input modes)
- `text_processing.py` — `expand_abbreviations`, `apply_pronunciations`, `clean_inline`, plus tech-tuned `ABBREVIATIONS` dict
- `parsing.py` — `parse_text`, `parse_dialogue` (Speaker:line), `parse_markdown_book`
- `rendering.py` — `parse_voice_spec`, `load_blended_voice` (weighted tensor mix), `silence`, `render_chapter_blocks`
- `encoding.py` — `loudnorm` (ffmpeg −0.5 LUFS / −2 dBFS), `encode_mp3`, `build_m4b`, `write_wav`
- `presets.py` — `load_preset`, `load_pronunciations` from bundled `data/presets/*.json` and `data/pronunciations/*.json`

Bundled presets: `podcast_two_host`, `podcast_interview`, `audiobook_warm`, `audiobook_deep`, `audiobook_british`, `story`.
Bundled pronunciation dicts: `ai_tech` (Sutskever, Karpathy, Llama, etc.), `finance`.

### Newsletter Profiles System

YAML-based per-newsletter configuration (`config/newsletters.yaml`) managed by `src/lib/newsletter_config.py`:
- Per-newsletter processing settings (length, style, focus areas, monologue/dialogue `mode`)
- Per-newsletter TTS settings (`tts:` block: preset, voice blends, pronunciation dict, loudness target)
- URL pattern matching for auto-detection of newsletter source
- Metadata extraction via regex (issue numbers, dates from URLs/content)
- Smart file organization: `data/audio/{newsletter-slug}/` with configurable naming templates
- Profile can be specified via CLI `--newsletter` flag or auto-detected from URL

Example `the-batch` profile uses `mode: dialogue` + `tts.preset: podcast_two_host` + `tts.pronunciations: ai_tech` for an NPR-style two-host podcast with correct AI-researcher name pronunciations.

### Configuration System

Layered YAML configuration with Pydantic validation:
- Base config: `config/{environment}.yaml` (app-level settings)
- Newsletter config: `config/newsletters.yaml` (per-newsletter profiles)
- Environment variables override YAML settings
- Access via `get_config()` (cached with `@lru_cache`) and `get_newsletter_config()` (global singleton)

### Cost Tracking

LLM token usage and TTS character counts tracked per episode (`src/lib/cost_tracker.py`). Episode model has fields for `llm_input_tokens`, `llm_output_tokens`, `llm_cost`, `tts_characters`, `tts_cost`, `total_cost`. LLM cost tracking is integrated; TTS character counts are recorded but cost is always 0.0 since Kokoro runs locally.

### Database Models

SQLAlchemy async models in `src/models/`:
- `Newsletter` - Source content, processing status, profile linkage (`newsletter_profile_id`, `issue_number`, `slug`)
- `Episode` - Generated podcast episode with audio metadata and cost tracking

Models include helper properties (e.g., `formatted_duration`, `is_ready_for_publication`) and factory methods (e.g., `Episode.from_newsletter_summary()`).

### API Structure

FastAPI application in `src/api/main.py`:
- Lifespan context manager handles database initialization
- Custom error handlers for domain exceptions (`ValidationError`, `LLMError`, `TTSError`)
- Logging middleware tracks request/response timing
- Routes in `src/api/routes/newsletters.py`

## Key Development Patterns

### Async Context Managers
All service classes must be used as async context managers:
```python
async with ContentExtractor(config) as extractor:
    content = await extractor.extract_from_url(url)
```

### Configuration Access
Always use the accessor functions, never instantiate directly:
```python
from src.lib.config import get_config
config = get_config()

from src.lib.newsletter_config import get_newsletter_config
newsletter_config = get_newsletter_config()
```

### Database Sessions
```python
from src.lib.database import get_db_session
async with get_db_session() as db:
    newsletter = await db.get(Newsletter, newsletter_id)
```

### Logging
```python
from src.lib.logging import get_logger
logger = get_logger(__name__)
```

### Testing
TDD approach. Test categories use pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.contract`. Async mode is `auto` (no need for `@pytest.mark.asyncio`). Use `create_mock_config()` fixture helper for mock configs.

## Important Constraints

1. **Python 3.11+ required** - Uses modern type hints (`list[str]` syntax)
2. **Coverage threshold**: 80% minimum (configured in `pyproject.toml`)
3. **Line length**: 100 characters (Ruff/Black)
4. **Type checking**: MyPy strict mode with library ignores for feedgen, mutagen, html2text, feedparser, nltk
5. **Pre-commit hooks**: ruff (lint+format), mypy, isort on commit; pytest on push
6. **asyncio_mode = "auto"** in pytest - all async tests run automatically

## Project Status

**Completed**: User Story 1 (full pipeline), Newsletter Profiles (Phase 1), Cost Tracking infrastructure (70%)
**Pending**: Cost tracking TTS integration, Phase 2 (RSS feeds & batch processing), Phase 3 (MP3 metadata & playlists)
