# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Newsletter Podcast Generator - Convert newsletter content into podcast episodes using AI-powered summarization and text-to-speech. Built with Python 3.11+, FastAPI, and supports both local (Ollama/Kokoro) and cloud (OpenAI/Unreal Speech) AI services.

## Development Commands

### Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements-dev.txt

# Setup configuration
cp config/development.yaml.template config/development.yaml
# Edit config/development.yaml with your API keys and settings

# Initialize database
python -c "import asyncio; from src.lib.database import init_database; asyncio.run(init_database())"
```

### Testing
```bash
# Run all tests with coverage
pytest

# Run specific test categories
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only
pytest tests/contract/       # Contract tests only

# Run single test file
pytest tests/unit/test_content_extractor.py

# Run with coverage report
pytest --cov=src --cov-report=html

# Run without coverage requirements (for development)
pytest --no-cov
```

### Code Quality
```bash
# Format code
ruff format .
black .
isort .

# Lint code
ruff check .

# Type checking
mypy src/

# Run all pre-commit hooks
pre-commit run --all-files
```

### Running the Application
```bash
# Start API server (development)
python -m uvicorn src.api.main:app --reload

# Start API server (production)
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# CLI commands
python -m src process-url "https://example.com/newsletter" --wait
python -m src process-file newsletter.txt --wait
python -m src status <newsletter-id>
python -m src health
python -m src voices
```

## Architecture Overview

### Core Pipeline (User Story 1 - Implemented)

Newsletter processing follows this flow:
1. **Content Extraction** (`src/services/content_extractor.py`) - Extracts and cleans text from URLs or direct input (HTML/Markdown/Text)
2. **LLM Summarization** (`src/services/llm_summarizer.py`) - Transforms content into podcast-style script using OpenAI or Ollama
3. **TTS Generation** (`src/services/tts_generator.py`) - Converts script to audio using Unreal Speech or Kokoro
4. **Episode Storage** - Saves MP3 locally (User Story 2 will add cloud upload + RSS feed)

The `NewsletterProcessor` (`src/lib/services.py`) orchestrates the entire pipeline asynchronously.

### Service Architecture

**Provider Pattern**: AI services use abstract base classes with concrete implementations:
- `BaseLLMClient` → `OpenAIClient` / `OllamaClient`
- `BaseTTSClient` → `UnrealSpeechClient` / `KokoroClient`

All services are async context managers for proper resource management.

### Configuration System

Layered YAML configuration with Pydantic validation:
- Base config: `config/{environment}.yaml`
- Environment variables override YAML settings
- Access via `get_config()` which is cached with `@lru_cache`

Config structure in `src/lib/config.py`:
- `AIServicesConfig` → `LLMConfig` (provider-specific) + `TTSConfig` (provider-specific)
- `DatabaseConfig`, `ServerConfig`, `LoggingConfig`, `StorageConfig`, etc.

### Database Models

SQLAlchemy async models in `src/models/`:
- `Newsletter` - Source content and processing status
- `Episode` - Generated podcast episode with audio metadata
- Status tracking: `pending → extracting → summarizing → generating_audio → completed`

Models include helper properties (e.g., `formatted_duration`, `is_ready_for_publication`) and factory methods (e.g., `Episode.from_newsletter_summary()`).

### API Structure

FastAPI application in `src/api/main.py`:
- Lifespan context manager handles database initialization
- Custom error handlers for domain exceptions (`ValidationError`, `LLMError`, `TTSError`)
- Logging middleware tracks request/response timing
- Routes in `src/api/routes/newsletters.py`

Important: The API is stateful - it tracks processing jobs in the database and returns job IDs for status checking.

### Error Handling

Domain-specific exceptions in `src/lib/exceptions.py`:
- `ValidationError` → 400 response
- `ProcessingError` → 422 response
- `LLMError` / `TTSError` → 503 response
- All exceptions logged with context

## Key Development Patterns

### Async Context Managers
All service classes must be used as async context managers to ensure proper cleanup:
```python
async with ContentExtractor(config) as extractor:
    content = await extractor.extract_from_url(url)
```

### Configuration Access
Always use `get_config()` - never instantiate `Config` directly:
```python
from src.lib.config import get_config
config = get_config()
```

### Database Sessions
Use the session factory, not direct session creation:
```python
from src.lib.database import get_db_session
async with get_db_session() as db:
    newsletter = await db.get(Newsletter, newsletter_id)
```

### Logging
Use structured logging with the logger factory:
```python
from src.lib.logging import get_logger
logger = get_logger(__name__)
logger.info(f"Processing newsletter: {newsletter_id}")
```

## Testing Strategy

**TDD Approach**: Tests were written before implementation for User Story 1.

Test categories (use pytest markers):
- `@pytest.mark.unit` - Unit tests with mocked dependencies
- `@pytest.mark.integration` - Integration tests with real service calls
- `@pytest.mark.contract` - API contract tests

Mock configuration in tests:
```python
@pytest.fixture
def mock_config():
    return create_mock_config(
        llm_provider="openai",
        tts_provider="unreal_speech"
    )
```

## Configuration Notes

**Development setup**: Copy `config/development.yaml.template` to `config/development.yaml` and add your API keys.

**Required API keys** (depending on provider choice):
- OpenAI: `OPENAI_API_KEY` or set in YAML
- Unreal Speech: `UNREAL_SPEECH_API_KEY` or set in YAML

**Local services** (no API keys needed):
- Ollama: Must be running on `http://localhost:11434` with model downloaded
- Kokoro/Chatterbox: Must be running on configured port

## Project Status

**Completed**: User Story 1 (Newsletter to Podcast Pipeline)
- Content extraction from URLs and text
- LLM summarization with configurable style/length
- TTS audio generation
- Local MP3 storage with metadata

**Pending**:
- User Story 2: Podcast Feed Management (cloud storage + RSS feed)
- User Story 3: Service Configuration UI

## Important Constraints

1. **Python 3.11+ required** - Uses modern type hints (`list[str]` syntax)
2. **Coverage threshold**: 80% minimum (configured in `pyproject.toml`)
3. **Line length**: 100 characters (Black/Ruff configured)
4. **Type checking**: MyPy strict mode enabled with some library ignores
5. **Pre-commit hooks**: Must pass before commits (ruff, mypy, tests on push)

## File Organization

```
src/
├── api/              # FastAPI application and routes
├── cli/              # Command-line interface
├── lib/              # Shared utilities (config, database, logging, exceptions)
├── models/           # SQLAlchemy database models
└── services/         # Business logic (content extraction, LLM, TTS)

config/               # YAML configuration files per environment
tests/                # Test suite (unit, integration, contract, accessibility)
specs/                # Feature specifications (from Specify template)
```

## Copilot Instructions Integration

From `.github/copilot-instructions.md`:
- Commands are limited to active technologies (Python 3.11+, FastAPI, pytest, ruff)
- Follow Python 3.11+ standard conventions
- Project uses asyncio extensively - maintain async patterns
