# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Newsletter Podcast Generator - Convert newsletter content into podcast episodes using AI-powered summarization and text-to-speech. Built with Python 3.11+, FastAPI, and supports both local (Ollama/Kokoro) and cloud (OpenAI/Unreal Speech) AI services.

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
2. **LLM Summarization** (`src/services/llm_summarizer.py`) - Transforms content into podcast-style script using OpenAI or Ollama
3. **TTS Generation** (`src/services/tts_generator.py`) - Converts script to audio using Kokoro (local) or Unreal Speech (cloud)
4. **Episode Storage** - Saves MP3 with profile-aware file organization via `StorageManager` (`src/lib/storage.py`)

Status tracking through database: `pending → extracting → summarizing → generating_audio → completed`

### Service Architecture

**Provider Pattern**: AI services use abstract base classes with concrete implementations:
- `BaseLLMClient` → `OpenAIClient` / `OllamaClient`
- `BaseTTSClient` → `UnrealSpeechClient` / `KokoroClient`

All services are async context managers for proper resource management.

### Newsletter Profiles System

YAML-based per-newsletter configuration (`config/newsletters.yaml`) managed by `src/lib/newsletter_config.py`:
- Per-newsletter processing settings (length, style, focus areas)
- URL pattern matching for auto-detection of newsletter source
- Metadata extraction via regex (issue numbers, dates from URLs/content)
- Smart file organization: `data/audio/{newsletter-slug}/` with configurable naming templates
- Profile can be specified via CLI `--newsletter` flag or auto-detected from URL

### Configuration System

Layered YAML configuration with Pydantic validation:
- Base config: `config/{environment}.yaml` (app-level settings)
- Newsletter config: `config/newsletters.yaml` (per-newsletter profiles)
- Environment variables override YAML settings
- Access via `get_config()` (cached with `@lru_cache`) and `get_newsletter_config()` (global singleton)

### Cost Tracking

LLM token usage and TTS character counts tracked per episode (`src/lib/cost_tracker.py`). Episode model has fields for `llm_input_tokens`, `llm_output_tokens`, `llm_cost`, `tts_characters`, `tts_cost`, `total_cost`. LLM cost tracking is integrated; TTS cost tracking is TODO.

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
