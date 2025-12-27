# Newsletter Podcast Generator

Transform your favorite newsletters into engaging podcast episodes using AI-powered summarization and text-to-speech technology.

## Overview

Newsletter Podcast Generator is a Python-based application that automatically converts newsletter content into podcast audio files. Simply provide a newsletter URL or text content, and the system will extract the content, generate a podcast-style script, and create an MP3 audio file ready for listening.

## Features

- **Flexible Content Input**: Process newsletters from URLs or direct text input (HTML, Markdown, or plain text)
- **AI-Powered Summarization**: Transform newsletter content into natural podcast scripts using LLM technology
- **High-Quality Audio**: Generate professional podcast audio with text-to-speech engines
- **Multiple AI Providers**: Choose between cloud LLMs (OpenAI) or local alternatives (Ollama) with local Kokoro TTS
- **RESTful API**: FastAPI-based API for programmatic access
- **CLI Interface**: Command-line tools for batch processing and automation
- **Async Processing**: Non-blocking architecture for efficient processing
- **Status Tracking**: Monitor processing progress through the database

## Prerequisites

- Python 3.11 or higher
- SQLite (included with Python)
- (Optional) Ollama for local LLM processing
- (Optional) Kokoro TTS for local audio generation

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd batch_podcast
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements-dev.txt
```

### 4. Configure the Application

```bash
# Copy the template configuration
cp config/development.yaml.template config/development.yaml

# Edit the configuration file with your settings
# Add API keys for cloud LLM services (if using OpenAI)
```

### 5. Initialize Database

```bash
python -c "import asyncio; from src.lib.database import init_database; asyncio.run(init_database())"
```

## Configuration

The application uses YAML-based configuration with environment-specific files in the `config/` directory.

### AI Service Providers

**LLM Options:**
- **OpenAI** (Cloud): Requires `OPENAI_API_KEY`
- **Ollama** (Local): Requires Ollama running on `http://localhost:11434`

**TTS Options:**
- **Kokoro TTS** (Local): Requires the Kokoro Python package

Edit `config/development.yaml` to select your preferred providers and add necessary API keys.

## Usage

### API Server

Start the FastAPI development server:

```bash
uvicorn src.api.main:app --reload
```

The API will be available at `http://localhost:8000`. View interactive docs at `http://localhost:8000/docs`.

#### API Endpoints

**Process Newsletter from URL:**
```bash
POST /api/v1/newsletters/process
{
  "url": "https://example.com/newsletter"
}
```

**Process Newsletter from Content:**
```bash
POST /api/v1/newsletters/process
{
  "content": "Newsletter text content here..."
}
```

**Check Processing Status:**
```bash
GET /api/v1/newsletters/{newsletter_id}
```

**List All Newsletters:**
```bash
GET /api/v1/newsletters
```

### Command-Line Interface

**Process from URL:**
```bash
python -m src process-url "https://example.com/newsletter" --wait
```

**Process from File:**
```bash
python -m src process-file newsletter.txt --wait
```

**Check Status:**
```bash
python -m src status <newsletter-id>
```

**Health Check:**
```bash
python -m src health
```

**List Available Voices:**
```bash
python -m src voices
```

## Architecture

### Processing Pipeline

1. **Content Extraction** - Extracts and cleans text from URLs or direct input
2. **LLM Summarization** - Transforms content into podcast-style script
3. **TTS Generation** - Converts script to audio (MP3)
4. **Episode Storage** - Saves audio file with metadata

### Core Components

- **API Layer** (`src/api/`) - FastAPI application and routes
- **Services** (`src/services/`) - Business logic for content extraction, LLM, and TTS
- **Models** (`src/models/`) - SQLAlchemy database models
- **CLI** (`src/cli/`) - Command-line interface
- **Lib** (`src/lib/`) - Shared utilities (config, database, logging, exceptions)

### Database Models

- **Newsletter** - Source content and processing status
- **Episode** - Generated podcast episode with audio metadata

Status flow: `pending → extracting → summarizing → generating_audio → completed`

## Development

### Code Formatting

```bash
# Format code
ruff format .
black .
isort .
```

### Linting

```bash
# Lint code
ruff check .

# Type checking
mypy src/
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests
pytest tests/contract/       # API contract tests
```

### Pre-commit Hooks

```bash
# Run all pre-commit hooks
pre-commit run --all-files
```

## Project Status

### Completed

- **User Story 1**: Newsletter to Podcast Pipeline
  - Content extraction from URLs and text
  - LLM summarization with configurable style/length
  - TTS audio generation
  - Local MP3 storage with metadata

### Roadmap

- **User Story 2**: Podcast Feed Management (cloud storage + RSS feed)
- **User Story 3**: Service Configuration UI

## Technology Stack

- **Python 3.11+** - Modern Python with latest type hints
- **FastAPI** - High-performance async web framework
- **SQLAlchemy** - Async ORM for database operations
- **Pydantic** - Data validation and settings management
- **pytest** - Testing framework
- **Ruff** - Fast Python linter and formatter

## Contributing

1. Ensure Python 3.11+ is installed
2. Install development dependencies: `pip install -r requirements-dev.txt`
3. Run tests before committing: `pytest`
4. Follow code style guidelines (enforced by pre-commit hooks)
5. Maintain 80% minimum code coverage

## License

[Add your license information here]

## Support

For issues, questions, or contributions, please [add contact information or repository issue tracker link].
