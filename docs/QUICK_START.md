# Quick Start Guide

## Newsletter Podcast Generator - Getting Started

This guide will help you test the newsletter-to-podcast conversion pipeline.

### Prerequisites

✅ Python 3.11+ installed
✅ Virtual environment activated (`.venv`)
✅ Dependencies installed (`pip install -r requirements.txt`)
✅ `ffmpeg` and `espeak-ng` installed (`brew install ffmpeg espeak-ng` on macOS)
✅ [Ollama](https://ollama.ai) running locally with a model pulled (e.g. `ollama pull qwen2.5:3b-instruct`)

Note: Kokoro voicepacks download automatically on first TTS run.

### Configuration Setup

Before running the application, copy the templates and adjust if needed:

1. **Create configuration files:**
```bash
cp config/development.yaml.template config/development.yaml
cp config/newsletters.yaml.template config/newsletters.yaml
```

2. **Default config is fully local — Ollama + Kokoro.** Edit `config/development.yaml` only if you want to switch the LLM model or use OpenAI:

```yaml
ai_services:
  llm:
    provider: "ollama"          # local — default
    ollama:
      base_url: "http://localhost:11434"
      model: "qwen2.5:3b-instruct"
  tts:
    provider: "kokoro_tts"      # local — only option supported
    kokoro_tts:
      voice: "af_heart"
      lang_code: "a"
      speed: 1.0
```

3. **Configure per-newsletter behavior in `config/newsletters.yaml`** — e.g. `the-batch` ships configured for two-host dialogue with the `podcast_two_host` preset and `ai_tech` pronunciation dict:

```yaml
newsletters:
  the-batch:
    processing:
      length: "long"
      mode: "dialogue"            # Host/Guest two-voice script
    tts:
      preset: "podcast_two_host"  # af_heart + am_michael alternating
      pronunciations: "ai_tech"   # Sutskever, Karpathy, Llama, etc.
      target_lufs: -16.0
```

See `src/lib/tts_engine/data/presets/` and `src/lib/tts_engine/data/pronunciations/` for all bundled options.

### Database Initialization

Initialize the database:
```bash
python -c "import asyncio; from src.lib.database import init_database; asyncio.run(init_database())"
```

### Testing the CLI

#### 1. Process a Newsletter from URL
```bash
python -m src process-url "https://example.com/newsletter" --wait
```

#### 2. Process a Newsletter from File
```bash
echo "This is a test newsletter content with some interesting information." > test.txt
python -m src process-file test.txt --wait
```

#### 3. Check Processing Status
```bash
python -m src status <newsletter-id>
```

#### 4. Check Service Health
```bash
python -m src health
```

#### 5. View Available Voices, Presets, and Pronunciation Dicts
```bash
python -m src voices
```
The output now includes the available bundled presets and pronunciation dictionaries
that can be referenced from `newsletters.yaml`.

### Testing the API

#### 1. Start the API Server
```bash
python -m uvicorn src.api.main:app --reload
```

The API will be available at: http://localhost:8000

#### 2. Interactive API Documentation
Visit: http://localhost:8000/docs

#### 3. Submit a Newsletter (using curl)

From URL:
```bash
curl -X POST "http://localhost:8000/api/v1/newsletters/from-url" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/newsletter",
    "style": "conversational",
    "target_length": "medium"
  }'
```

From Text:
```bash
curl -X POST "http://localhost:8000/api/v1/newsletters/from-text" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "This is a test newsletter content.",
    "title": "Test Newsletter",
    "content_type": "text"
  }'
```

#### 4. Check Status
```bash
curl "http://localhost:8000/api/v1/newsletters/{newsletter-id}/status"
```

#### 5. Health Check
```bash
curl "http://localhost:8000/api/v1/newsletters/health"
```

### Testing with Python

Create a test script (`test_processing.py`):

```python
import asyncio
from src.lib.config import get_config
from src.services import NewsletterProcessor

async def test_processing():
    """Test newsletter processing."""
    config = get_config()
    
    async with NewsletterProcessor(config) as processor:
        # Test with sample text
        newsletter = await processor.process_newsletter_from_text(
            content="""
            Welcome to our weekly tech newsletter!
            
            This week's highlights:
            1. AI breakthroughs in natural language processing
            2. New developments in quantum computing
            3. The future of sustainable technology
            
            Read more about each topic in our full newsletter...
            """,
            title="Weekly Tech Newsletter",
            processing_options={
                "style": "conversational",
                "target_length": "medium"
            }
        )
        
        print(f"Newsletter ID: {newsletter.id}")
        print(f"Status: {newsletter.status}")
        print(f"Episode ID: {newsletter.episode_id}")
        
        if newsletter.episode_id:
            from src.models import Episode
            from src.lib.database import get_db_session
            
            async with get_db_session() as db:
                episode = await db.get(Episode, newsletter.episode_id)
                print(f"Audio file: {episode.audio_file_path}")
                print(f"Duration: {episode.formatted_duration}")

if __name__ == "__main__":
    asyncio.run(test_processing())
```

Run it:
```bash
python test_processing.py
```

### Running Tests

Run the TDD test suite:
```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/unit/test_content_extractor.py

# Integration tests only
pytest tests/integration/

# Contract tests only
pytest tests/contract/
```

### Troubleshooting

#### Import Errors
If you encounter import errors, ensure the virtual environment is activated:
```bash
source .venv/bin/activate  # On macOS/Linux
.venv\Scripts\activate     # On Windows
```

#### Configuration Errors
Check your configuration:
```bash
python -c "from src.lib.config import get_config; print(get_config())"
```

#### Database Errors
Reset the database:
```bash
rm -rf data/  # Remove old data
python -c "import asyncio; from src.lib.database import init_database; asyncio.run(init_database())"
```

#### 4. Check API Key Configuration (only if using OpenAI)
```bash
python -c "from src.lib.config import get_config; c=get_config(); print(f'OpenAI: {c.llm.openai.api_key[:10] if c.llm.openai.api_key else \"(not set)\"}')"
```

With the default Ollama+Kokoro config, no API keys are required.

### Expected Behavior

When processing completes successfully:
1. Newsletter status progresses through: `pending` → `extracting` → `summarizing` → `generating_audio` → `completed`
2. An Episode record is created with audio file details, LLM token usage, and TTS character count
3. MP3 file is generated under `data/audio/<newsletter-slug>/` (e.g. `data/audio/the-batch/the-batch-YYYY-MM-DD-issue-NNN.mp3`)
4. Audio is loudness-normalized to broadcast standard (`-16 LUFS` for podcasts)
5. For dialogue-mode profiles, voices alternate between Host and Guest at every turn
6. Logs show detailed progress information at each pipeline step

### Next Steps

Once processing is verified:
- Move to Phase 2: RSS feed parsing + batch processing CLI
- Move to Phase 3: MP3 ID3 metadata tagging + M3U playlist generation

### Support

For issues or questions:
1. Check logs in the console output (and `logs/app_dev.log`)
2. Review `STATUS.md` for current known issues
3. See `CLAUDE.md` for architecture overview
4. Examine the test files for usage examples (`tests/unit/test_tts_engine.py` covers the TTS engine surface)
5. Check configuration in `config/development.yaml` and `config/newsletters.yaml`

---

**Status:** Production-ready (Phase 1 complete; Phase 2 pending)
**Version:** 0.1.0
**Last Updated:** June 13, 2026