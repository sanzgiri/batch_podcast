"""
Seed the database with sample episodes from popular ML/AI blogs.

Uses:
- ContentExtractor to fetch real blog content
- Ollama (local) for LLM summarization
- gTTS for text-to-speech audio generation

Usage:
    source .venv/bin/activate
    python scripts/seed_sample_episodes.py
"""

import asyncio
import json
import sys
from pathlib import Path

import aiohttp

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.lib.config import get_config
from src.lib.database import init_database, get_db_session
from src.lib.logging import get_logger, setup_logging
from src.lib.utils import generate_uuid, generate_content_hash, now_utc, count_words
from src.models import Newsletter, NewsletterStatus, Episode, EpisodeStatus

logger = get_logger(__name__)

# Sample blog posts from popular ML/AI sources
SAMPLE_URLS = [
    {
        "url": "https://lilianweng.github.io/posts/2024-11-28-reward-hacking/",
        "title": "Reward Hacking in RLHF",
        "source": "Lil'Log (Lilian Weng)",
    },
    {
        "url": "https://jalammar.github.io/illustrated-transformer/",
        "title": "The Illustrated Transformer",
        "source": "Jay Alammar",
    },
    {
        "url": "https://huggingface.co/blog/gemma3",
        "title": "Welcome Gemma 3",
        "source": "Hugging Face Blog",
    },
    {
        "url": "https://sebastianraschka.com/blog/2025/understanding-reasoning-llms.html",
        "title": "Understanding Reasoning LLMs",
        "source": "Sebastian Raschka",
    },
]


async def extract_content(url: str) -> tuple[str, str]:
    """Extract content from URL using ContentExtractor."""
    from src.services.content_extractor import ContentExtractor

    config = get_config()
    async with ContentExtractor(config) as extractor:
        result = await extractor.extract_from_url(url)
        return result.title or "Untitled", result.content


async def summarize_with_ollama(content: str, title: str) -> dict:
    """Summarize content by calling Ollama API directly."""
    config = get_config()
    base_url = config.llm.ollama.base_url
    model = config.llm.ollama.model

    prompt = f"""You are a podcast script writer. Convert this blog post into an engaging podcast script.

Write a natural, conversational podcast script (~3-5 minutes when spoken) covering the key ideas.
Start with a brief intro, cover the main points, and end with a takeaway.
Do NOT use markdown formatting. Write plain text meant to be spoken aloud.

Blog title: {title}

Blog content:
{content[:4000]}

Podcast script:"""

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7},
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{base_url}/api/generate", json=payload) as resp:
            resp.raise_for_status()
            result = await resp.json()

    summary = result.get("response", "").strip()
    input_tokens = result.get("prompt_eval_count", 0)
    output_tokens = result.get("eval_count", 0)

    return {
        "summary": summary,
        "title": f"{title} - Podcast",
        "word_count": len(summary.split()),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": 0.0,
        "provider": "ollama",
        "model": model,
    }


def generate_audio_gtts(text: str, output_path: Path) -> dict:
    """Generate audio using gTTS."""
    from gtts import gTTS

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # gTTS has a practical limit; truncate very long texts
    tts_text = text[:5000] if len(text) > 5000 else text

    tts = gTTS(text=tts_text, lang="en")
    tts.save(str(output_path))

    # Get file info
    file_size = output_path.stat().st_size

    # Estimate duration (~150 words per minute for TTS)
    words = len(tts_text.split())
    estimated_duration = int(words / 150 * 60)

    # Try to get real duration if mutagen is available
    try:
        from mutagen.mp3 import MP3

        audio = MP3(str(output_path))
        estimated_duration = int(audio.info.length)
    except Exception:
        pass

    return {
        "file_path": str(output_path),
        "duration_seconds": estimated_duration,
        "file_size_bytes": file_size,
        "characters": len(tts_text),
    }


async def process_one(entry: dict, index: int) -> bool:
    """Process a single blog post end-to-end."""
    url = entry["url"]
    source = entry["source"]
    print(f"\n{'='*60}")
    print(f"[{index+1}/{len(SAMPLE_URLS)}] Processing: {entry['title']}")
    print(f"  Source: {source}")
    print(f"  URL: {url}")
    print(f"{'='*60}")

    try:
        # Step 1: Extract content
        print("  Step 1: Extracting content...")
        title, content = await extract_content(url)
        word_count = count_words(content)
        print(f"    Extracted {word_count} words, title: {title[:60]}")

        if word_count < 50:
            print(f"    SKIP: Too little content ({word_count} words)")
            return False

        # Truncate very long content for the small model
        if word_count > 3000:
            content = " ".join(content.split()[:3000])
            print(f"    Truncated to ~3000 words for summarization")

        # Step 2: Summarize with Ollama
        print("  Step 2: Summarizing with Ollama...")
        summary_data = await summarize_with_ollama(content, title)
        print(f"    Summary: {len(summary_data['summary'])} chars")
        print(f"    Tokens: {summary_data['input_tokens']} in / {summary_data['output_tokens']} out")

        # Step 3: Generate audio with gTTS
        print("  Step 3: Generating audio with gTTS...")
        audio_dir = Path("data/audio/samples")
        slug = title.lower()[:40].replace(" ", "-").replace("/", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        audio_path = audio_dir / f"{slug}.mp3"

        audio_data = generate_audio_gtts(summary_data["summary"], audio_path)
        print(f"    Audio: {audio_data['duration_seconds']}s, {audio_data['file_size_bytes']} bytes")

        # Step 4: Insert into database
        print("  Step 4: Saving to database...")
        async with get_db_session() as db:
            newsletter = Newsletter(
                title=title,
                url=url,
                content=content,
                extracted_content=content,
                word_count=word_count,
                status=NewsletterStatus.COMPLETED,
            )
            db.add(newsletter)
            await db.commit()
            await db.refresh(newsletter)

            episode = Episode(
                newsletter_id=newsletter.id,
                title=f"{title} - Podcast",
                description=f"AI-generated podcast from {source}: {title}",
                summary_text=summary_data["summary"],
                audio_file_path=audio_data["file_path"],
                duration_seconds=audio_data["duration_seconds"],
                file_size_bytes=audio_data["file_size_bytes"],
                status=EpisodeStatus.COMPLETED.value,
                llm_provider=summary_data["provider"],
                llm_model=summary_data["model"],
                tts_provider="gtts",
                tts_voice="en",
                llm_input_tokens=summary_data["input_tokens"],
                llm_output_tokens=summary_data["output_tokens"],
                llm_cost=summary_data["cost"],
                tts_characters=audio_data["characters"],
                tts_cost=0.0,
                total_cost=summary_data["cost"],
            )
            db.add(episode)

            newsletter.episode_id = episode.id
            newsletter.update_status(NewsletterStatus.COMPLETED)

            await db.commit()
            print(f"    Newsletter ID: {newsletter.id}")
            print(f"    Episode ID: {episode.id}")

        print(f"  DONE")
        return True

    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    print("Newsletter Podcast Generator - Sample Seeder")
    print("=" * 60)

    # Init config and logging
    config = get_config()
    setup_logging(config)
    print(f"LLM provider: {config.llm.provider} ({config.llm.ollama.model})")

    # Init database
    await init_database()
    print("Database initialized")

    # Process each URL
    successes = 0
    for i, entry in enumerate(SAMPLE_URLS):
        ok = await process_one(entry, i)
        if ok:
            successes += 1

    print(f"\n{'='*60}")
    print(f"Done! {successes}/{len(SAMPLE_URLS)} episodes created successfully.")
    print(f"Launch the UI to browse them: python -m src.ui.app")


if __name__ == "__main__":
    asyncio.run(main())
