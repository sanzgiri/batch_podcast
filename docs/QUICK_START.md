# Quick Start Guide - User Story 1

## Newsletter Podcast Generator - Getting Started

This guide will help you test the newly implemented User Story 1 functionality for converting newsletters to podcast episodes.

### Prerequisites

✅ Python 3.9+ installed
✅ Virtual environment activated (`.venv`)
✅ Dependencies installed (completed)

### Configuration Setup

Before running the application, you need to configure the AI services:

1. **Create a configuration file:**
```bash
cp config/development.yaml.example config/development.yaml
```

2. **Add your API keys to `config/development.yaml` or environment variables:**

For OpenAI (recommended for testing):
```yaml
ai_services:
  llm:
    provider: "openai"
    openai:
      api_key: "your-openai-api-key-here"
      model: "gpt-5-nano"
  tts:
    provider: "unreal_speech"
    unreal_speech:
      api_key: "your-unreal-speech-api-key-here"
```

For local services (Ollama + Kokoro):
```yaml
ai_services:
  llm:
    provider: "ollama"
    ollama:
      base_url: "http://localhost:11434"
      model: "llama2"
  tts:
    provider: "kokoro"
    kokoro:
      base_url: "http://localhost:8080"
```

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

#### 5. View Available Voices
```bash
python -m src voices
```

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

#### API Key Issues
Verify your API keys are set:
```bash
python -c "from src.lib.config import get_config; c=get_config(); print(f'OpenAI: {c.llm.openai.api_key[:10]}... TTS: {c.tts.unreal_speech.api_key[:10]}...')"
```

### Expected Behavior

When processing completes successfully:
1. Newsletter status progresses through: `pending` → `extracting` → `summarizing` → `generating_audio` → `completed`
2. An Episode record is created with audio file details
3. MP3 file is generated in the configured audio directory (default: `./data/audio/`)
4. Logs show detailed progress information

### Next Steps

Once User Story 1 is verified:
- Move to User Story 2: Podcast Feed Management (cloud upload + RSS)
- Move to User Story 3: Service Configuration UI
- Complete Phase 6: Production polish

### Support

For issues or questions:
1. Check logs in the console output
2. Review the completion documentation in `docs/USER_STORY_1_COMPLETION.md`
3. Examine the test files for usage examples
4. Check configuration in `config/development.yaml`

---

**Status:** Ready for testing
**Version:** 0.1.0
**Last Updated:** October 16, 2025