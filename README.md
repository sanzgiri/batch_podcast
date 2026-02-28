# RecastAI

**URL in, podcast out.** Transform blog posts, newsletters, and articles into listenable podcast episodes — fully automated, fully local.

RecastAI scrapes written content, rewrites it as a natural conversational script using an LLM, and generates audio with text-to-speech. Browse and play your episodes in a Gradio web UI.

## Quick Start

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp config/development.yaml.template config/development.yaml
# Edit config/development.yaml — set your LLM/TTS provider

# Initialize database
python -c "import asyncio; from src.lib.database import init_database; asyncio.run(init_database())"

# Seed with sample episodes (requires Ollama running locally)
python scripts/seed_sample_episodes.py

# Launch the UI
python -m src.ui.app
# Open http://localhost:7860
```

## How It Works

```
URL/Text → Content Extraction → LLM Summarization → Text-to-Speech → MP3 Episode
```

1. **Content Extraction** — Fetches and cleans HTML/Markdown/text from any URL
2. **LLM Summarization** — Rewrites content as a conversational podcast script
3. **TTS Generation** — Converts the script to spoken audio (MP3)
4. **Storage & Playback** — Saves episodes to SQLite with a Gradio UI for browsing and playback

## Features

- **Multiple AI Providers** — OpenAI or Ollama (local) for LLM; Kokoro (local), gTTS, or Unreal Speech for TTS
- **Runs Entirely Local** — Ollama + Kokoro/gTTS = no API keys, no cloud, no cost
- **Newsletter Profiles** — Per-source config with URL pattern matching, metadata extraction, smart file naming
- **Web UI** — Gradio-based episode browser with audio player and script viewer
- **REST API** — FastAPI endpoints for programmatic access
- **CLI** — Command-line tools for processing and batch automation
- **Cost Tracking** — Per-episode LLM token and TTS character cost tracking

## Usage

### Web UI (Gradio)

```bash
python -m src.ui.app
# Opens at http://localhost:7860
```

### CLI

```bash
python -m src process-url "https://example.com/article" --wait
python -m src process-url "URL" --newsletter the-batch --wait   # with profile
python -m src process-file article.txt --wait
python -m src status <newsletter-id>
python -m src health
python -m src voices
python -m src costs summary
```

### API Server

```bash
uvicorn src.api.main:app --reload
# API at http://localhost:8000, docs at http://localhost:8000/docs
```

## Configuration

YAML-based config in `config/development.yaml`:

- **LLM**: `openai` (cloud, needs API key) or `ollama` (local, free)
- **TTS**: `kokoro_tts` (local, needs PyTorch), `gtts` (free, uses Google), or `unreal_speech` (cloud)
- **Storage**: Local SQLite + filesystem

Newsletter profiles in `config/newsletters.yaml` for per-source settings (processing style, output naming, metadata extraction).

## Architecture

```
src/
├── api/              # FastAPI application and routes
├── cli/              # Command-line interface
├── lib/              # Config, database, logging, exceptions, metrics
├── models/           # SQLAlchemy models (Newsletter, Episode)
├── services/         # Content extraction, LLM, TTS, pipeline orchestration
└── ui/               # Gradio web interface
```

## Prerequisites

- Python 3.11+
- For local LLM: [Ollama](https://ollama.ai) running with a model (e.g., `ollama pull qwen2.5:3b-instruct`)
- For local TTS: Kokoro (requires PyTorch) or gTTS (lightweight, uses Google's API)

## Technology Stack

Python 3.11+ · FastAPI · SQLAlchemy (async) · Pydantic · Gradio · Ollama · Kokoro/gTTS

## License

MIT
