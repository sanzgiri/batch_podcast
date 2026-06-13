# RecastAI

**URL in, podcast out.** Transform blog posts, newsletters, and articles into listenable podcast episodes — fully automated, fully local.

RecastAI scrapes written content, rewrites it as a natural conversational script using an LLM, and generates audio with text-to-speech. Browse and play your episodes in a Gradio web UI.

**100% local.** Ollama for summarization, Kokoro for TTS. No API keys, no cloud, no cost.

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

- **Fully Local AI** — Ollama (LLM) + Kokoro (TTS). No API keys, no cloud, no cost.
- **Production-quality TTS** — Voice blending, programmatic silence injection, ffmpeg loudness normalization (broadcast standard), and pronunciation overrides via the integrated [text2audio](https://github.com/sanzgiri/text2audio)-derived `src/lib/tts_engine`.
- **Two-host dialogue mode** — Generates Host/Guest scripts and renders them with alternating voices for NPR-style podcasts.
- **Bundled presets** — `podcast_two_host`, `podcast_interview`, `audiobook_warm`, `audiobook_deep`, `audiobook_british`, `story`.
- **Bundled pronunciation dicts** — `ai_tech` (Sutskever, Karpathy, Llama, etc.), `finance` (Cowen, Munger, Berkshire, etc.). Easy to extend.
- **Tech-aware abbreviation expansion** — GPU → G.P.U., LLM → L.L.M., etc. so acronyms read correctly.
- **Newsletter Profiles** — Per-source config with URL pattern matching, metadata extraction, smart file naming, per-newsletter voice/dialogue settings.
- **Web UI** — Gradio-based episode browser with audio player and script viewer
- **REST API** — FastAPI endpoints for programmatic access
- **CLI** — Command-line tools for processing and batch automation
- **Cost Tracking** — Per-episode LLM token tracking (TTS is free — Kokoro runs locally)

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

- **LLM**: `ollama` (local, default — needs Ollama running) or `openai` (cloud, needs API key)
- **TTS**: `kokoro_tts` (local, default — needs Kokoro voicepacks; downloaded on first run)
- **Storage**: Local SQLite + filesystem

Newsletter profiles in `config/newsletters.yaml` configure per-source settings:

- **Processing**: `length`, `style`, `mode` (`monologue` | `dialogue`), `focus_areas`
- **TTS**: `preset`, `voice`, `voice_a`/`voice_b` (dialogue), `pronunciations`, `target_lufs`
- **Output**: subfolder, filename template, metadata extraction patterns

Example (`the-batch`):

```yaml
the-batch:
  processing:
    mode: dialogue              # Host/Guest two-voice transcript
    length: long
  tts:
    preset: podcast_two_host    # af_heart + am_michael alternating
    pronunciations: ai_tech     # Sutskever, Karpathy, Llama, etc.
    target_lufs: -16.0          # podcast loudness standard
```

## Architecture

```
src/
├── api/              # FastAPI application and routes
├── cli/              # Command-line interface
├── lib/              # Config, database, logging, exceptions, metrics, storage
│   └── tts_engine/   # Local Kokoro pipeline (vendored from text2audio)
│       ├── blocks.py         # Block/Chapter dataclasses
│       ├── text_processing.py # abbreviations, pronunciations, markdown cleanup
│       ├── parsing.py        # text/dialogue/markdown-book parsers
│       ├── rendering.py      # voice loading + blending, render_chapter_blocks
│       ├── encoding.py       # ffmpeg loudnorm, MP3, M4B with chapter markers
│       ├── presets.py        # preset + pronunciation-dict loaders
│       └── data/             # bundled presets/*.json + pronunciations/*.json
├── models/           # SQLAlchemy models (Newsletter, Episode)
├── services/         # Content extraction, LLM, TTS, pipeline orchestration
└── ui/               # Gradio web interface
```

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) running with a model (e.g., `ollama pull qwen2.5:3b-instruct`)
- `ffmpeg` and `espeak-ng` installed (`brew install ffmpeg espeak-ng` on macOS)
- Kokoro voicepacks download automatically on first TTS run (~few hundred MB, one-time)

## Technology Stack

Python 3.11+ · FastAPI · SQLAlchemy (async) · Pydantic · Gradio · Ollama · Kokoro · ffmpeg

## License

MIT
