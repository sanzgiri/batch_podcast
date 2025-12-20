# Newsletter Podcast Generator - Development Guide

## Table of Contents
1. [Implementation Status](#implementation-status)
2. [Phase 1: Newsletter Profiles & Smart Organization](#phase-1-newsletter-profiles--smart-organization)
3. [Cost Tracking](#cost-tracking)
4. [Phase 2: RSS Feeds & Batch Processing](#phase-2-rss-feeds--batch-processing)
5. [Phase 3: Advanced Features](#phase-3-advanced-features)
6. [Test Plans](#test-plans)

---

## Implementation Status

### ✅ Completed
- Phase 1: Newsletter Profiles & Smart File Organization (100%)
- Cost Tracking Infrastructure (70% - needs service integration)

### 🚧 In Progress
- Cost tracking service integration
- Documentation

### 📋 Planned
- Phase 2: RSS Feeds & Batch Processing
- Phase 3: MP3 Metadata & Playlists

---

## Phase 1: Newsletter Profiles & Smart Organization

### Status: ✅ COMPLETED

### What Was Implemented

#### 1. Newsletter Configuration System
**Files Created:**
- `config/newsletters.yaml` - Active configuration
- `config/newsletters.yaml.template` - Template with documentation
- `src/lib/newsletter_config.py` - Pydantic models and config loader

**Features:**
- YAML-based newsletter profiles
- Per-newsletter settings:
  - Processing (length, style, focus areas)
  - Output (folder, naming template)
  - Metadata extraction (regex patterns for issue numbers, dates)
  - Podcast metadata (title, author, description, etc.)
- Profile matching via URL patterns
- Auto-detection of newsletter from URL

#### 2. Smart File Organization
**Files Created/Modified:**
- `src/lib/storage.py` - Storage manager for organized file paths

**Features:**
- Newsletter-specific folders: `data/audio/{newsletter-slug}/`
- Intelligent filename generation from templates
- Variables supported: `{slug}`, `{date}`, `{issue}`, `{title}`, `{id}`
- Example: `the-batch-2025-12-19-issue-323.mp3`
- Fallback to `uncategorized/` for one-off newsletters

#### 3. Database Schema Updates
**Files Modified:**
- `src/models/newsletter.py` - Added profile fields
- Migration: `scripts/migrate_add_newsletter_profiles.py`

**New Fields:**
- `newsletter_profile_id` - Links to profile configuration
- `issue_number` - Extracted issue number
- `slug` - Newsletter slug for file naming

#### 4. Enhanced CLI
**Files Modified:**
- `src/cli/commands.py` - Added `--newsletter` flag

**Usage:**
```bash
# Explicit profile
python -m src process-url "URL" --newsletter the-batch --wait

# Auto-detect from URL
python -m src process-url "https://www.deeplearning.ai/the-batch/issue-323/" --wait

# Override profile settings
python -m src process-url "URL" --newsletter the-batch --length medium --wait
```

#### 5. Service Integration
**Files Modified:**
- `src/services/newsletter_processor.py` - Profile-aware processing

**Features:**
- Automatic profile detection from URL
- Metadata extraction using configured patterns
- Profile-based processing defaults
- Smart file path generation with storage manager

### Configuration Example

```yaml
newsletters:
  the-batch:
    name: "The Batch - AI News by DeepLearning.AI"
    enabled: true
    rss_feed: "https://www.deeplearning.ai/the-batch/feed/"
    url_pattern: "https://www.deeplearning.ai/the-batch/issue-*"

    processing:
      length: "long"
      style: "conversational"
      focus_areas: []

    output:
      folder: "the-batch"
      naming_template: "{slug}-{date}-issue-{issue}"

    podcast_metadata:
      title: "The Batch Podcast"
      description: "AI news from DeepLearning.AI"
      author: "Andrew Ng / DeepLearning.AI"
      category: "Technology"

    extraction:
      issue_number:
        pattern: "issue-(\\d+)"
        source: "url"
```

### Testing Phase 1

```bash
# 1. Setup configuration
cp config/newsletters.yaml.template config/newsletters.yaml
# Edit config/newsletters.yaml with your settings

# 2. Run migration
python scripts/migrate_add_newsletter_profiles.py

# 3. Test with a configured newsletter
python -m src process-url "https://www.deeplearning.ai/the-batch/issue-323/" \
  --newsletter the-batch --wait

# 4. Verify file organization
ls -la data/audio/the-batch/

# 5. Check database for profile info
sqlite3 data/newsletter_podcast_local.db \
  "SELECT newsletter_profile_id, issue_number, slug FROM newsletters;"
```

---

## Cost Tracking

### Status: 🚧 70% COMPLETE

### What Was Implemented

#### 1. Cost Tracking Infrastructure
**Files Created:**
- `src/lib/cost_tracker.py` - Cost calculation utilities

**Features:**
- LLM pricing data (OpenAI GPT-4o, GPT-4o-mini, GPT-3.5-turbo)
- TTS pricing data (Unreal Speech, Kokoro)
- Cost calculation from token/character counts
- Support for local providers (zero cost)

**Pricing (as of Dec 2024):**
```python
LLM_PRICING = {
    "openai": {
        "gpt-4o": {
            "input": $0.0000025/token,   # $2.50/1M tokens
            "output": $0.00001/token      # $10.00/1M tokens
        },
        "gpt-4o-mini": {
            "input": $0.00000015/token,  # $0.15/1M tokens
            "output": $0.0000006/token    # $0.60/1M tokens
        }
    }
}

TTS_PRICING = {
    "unreal_speech": {
        "cost_per_char": $0.000001  # $1/1M characters
    }
}
```

#### 2. Database Schema Updates
**Files Modified:**
- `src/models/episode.py` - Added cost tracking fields
- Migration: `scripts/migrate_add_cost_tracking.py`

**New Fields:**
- `llm_input_tokens`, `llm_output_tokens`, `llm_total_tokens`
- `llm_cost`
- `tts_characters`
- `tts_cost`
- `total_cost`

**New Method:**
```python
episode.set_cost_info(
    llm_input_tokens=1500,
    llm_output_tokens=800,
    llm_cost=0.0045,
    tts_characters=4500,
    tts_cost=0.0045
)
```

### What Needs To Be Done

#### 1. LLM Service Integration
**File to Modify:** `src/services/llm_summarizer.py`

**Changes Needed:**
```python
# In OpenAIClient.summarize():
# Extract token usage from API response
usage = result.get("usage", {})
input_tokens = usage.get("prompt_tokens", 0)
output_tokens = usage.get("completion_tokens", 0)

# Calculate costs
from src.lib.cost_tracker import LLMUsage
llm_usage = LLMUsage.calculate(
    provider="openai",
    model=self.model,
    input_tokens=input_tokens,
    output_tokens=output_tokens
)

# Add to SummaryResponse
response = SummaryResponse(
    ...existing fields...,
    input_tokens=input_tokens,
    output_tokens=output_tokens,
    cost=llm_usage.total_cost
)
```

#### 2. TTS Service Integration
**File to Modify:** `src/services/tts_generator.py`

**Changes Needed:**
```python
# In UnrealSpeechClient.synthesize():
# Track character count
characters = len(request.text)

# Calculate cost
from src.lib.cost_tracker import TTSUsage
tts_usage = TTSUsage.calculate(
    provider="unreal_speech",
    voice=request.voice or self.default_voice,
    characters=characters
)

# Add to TTSResponse
response = TTSResponse(
    ...existing fields...,
    characters=characters,
    cost=tts_usage.cost
)
```

#### 3. Newsletter Processor Integration
**File to Modify:** `src/services/newsletter_processor.py`

**Changes Needed:**
```python
# After LLM summarization:
episode.set_cost_info(
    llm_input_tokens=summary_response.input_tokens,
    llm_output_tokens=summary_response.output_tokens,
    llm_cost=summary_response.cost
)

# After TTS generation:
episode.set_cost_info(
    tts_characters=tts_response.characters,
    tts_cost=tts_response.cost
)
```

#### 4. Cost Reporting Utility
**File to Create:** `src/cli/cost_report.py`

**Features to Implement:**
- Cost breakdown by newsletter
- Cost breakdown by date range
- Total costs summary
- Per-episode cost details
- Export to CSV

**CLI Command:**
```bash
# Show cost summary
python -m src costs summary

# Show costs for specific newsletter
python -m src costs --newsletter the-batch

# Show costs for date range
python -m src costs --from 2025-01-01 --to 2025-01-31

# Export to CSV
python -m src costs --export costs_report.csv
```

### Testing Cost Tracking

```bash
# 1. Run migration
python scripts/migrate_add_cost_tracking.py

# 2. Process a newsletter and check costs
python -m src process-url "URL" --newsletter the-batch --wait

# 3. Query database for cost info
sqlite3 data/newsletter_podcast_local.db \
  "SELECT llm_total_tokens, llm_cost, tts_characters, tts_cost, total_cost FROM episodes;"

# 4. Generate cost report (once implemented)
python -m src costs summary
```

---

## Phase 2: RSS Feeds & Batch Processing

### Status: 📋 PLANNED

### Overview
Implement RSS feed parsing for auto-discovery of newsletter episodes and batch processing capabilities.

### Components to Implement

#### 1. RSS Feed Parser
**File to Create:** `src/lib/rss_parser.py`

**Functionality:**
- Parse RSS/Atom feeds
- Extract episode information (title, URL, date, content)
- Handle different feed formats
- Support pagination/limits

**Dependencies:**
```python
# Add to requirements.txt
feedparser>=6.0.10
```

**Implementation:**
```python
import feedparser
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class FeedEntry:
    """Represents an entry in an RSS feed."""
    title: str
    url: str
    published_date: Optional[datetime]
    content: Optional[str]
    summary: Optional[str]
    guid: str

class RSSFeedParser:
    """Parse RSS feeds for newsletter episodes."""

    async def parse_feed(self, feed_url: str) -> List[FeedEntry]:
        """Parse feed and return list of entries."""
        feed = feedparser.parse(feed_url)

        entries = []
        for entry in feed.entries:
            entries.append(FeedEntry(
                title=entry.get('title', 'Untitled'),
                url=entry.get('link', ''),
                published_date=self._parse_date(entry.get('published')),
                content=entry.get('content', [{}])[0].get('value'),
                summary=entry.get('summary'),
                guid=entry.get('id', entry.get('link'))
            ))

        return entries

    def filter_entries(
        self,
        entries: List[FeedEntry],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[FeedEntry]:
        """Filter entries by date range and limit."""
        # Implementation
        pass
```

#### 2. Episode Tracking & Deduplication
**File to Create:** `src/lib/episode_tracker.py`

**Functionality:**
- Track which episodes have been processed
- Prevent duplicate processing based on:
  - URL (content_hash in newsletters table)
  - GUID from RSS feed
  - Publication date + title combination
- Mark episodes as processed
- Query for unprocessed episodes

**Implementation:**
```python
class EpisodeTracker:
    """Track processed episodes to prevent duplicates."""

    async def is_processed(
        self,
        url: Optional[str] = None,
        guid: Optional[str] = None,
        title: Optional[str] = None,
        publication_date: Optional[datetime] = None
    ) -> bool:
        """Check if episode already processed."""
        # Check against newsletters table
        pass

    async def get_unprocessed_entries(
        self,
        entries: List[FeedEntry],
        newsletter_profile_id: str
    ) -> List[FeedEntry]:
        """Filter to only unprocessed entries."""
        pass

    async def mark_as_processed(
        self,
        newsletter_id: str,
        entry: FeedEntry
    ) -> None:
        """Mark entry as processed."""
        pass
```

#### 3. Batch Processing CLI Commands
**File to Modify:** `src/cli/commands.py`

**New Commands:**

```bash
# Process latest N episodes from RSS feed
python -m src batch-process --newsletter the-batch --latest 5

# Process all unprocessed episodes
python -m src batch-process --newsletter the-batch --all

# Process episodes from date range
python -m src batch-process --newsletter the-batch \
  --from 2025-01-01 --to 2025-01-31

# Process specific issue number
python -m src batch-process --newsletter the-batch --issue 323

# Dry run (show what would be processed)
python -m src batch-process --newsletter the-batch --latest 5 --dry-run

# Process with parallelization
python -m src batch-process --newsletter the-batch --latest 10 --parallel 3
```

**Implementation:**
```python
@cli.command()
@click.option("--newsletter", required=True, help="Newsletter profile ID")
@click.option("--latest", type=int, help="Process N latest episodes")
@click.option("--all", is_flag=True, help="Process all unprocessed episodes")
@click.option("--from", "from_date", help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", help="End date (YYYY-MM-DD)")
@click.option("--issue", help="Specific issue number")
@click.option("--dry-run", is_flag=True, help="Show what would be processed")
@click.option("--parallel", type=int, default=1, help="Number of parallel jobs")
@click.option("--skip-existing", is_flag=True, default=True, help="Skip already processed")
def batch_process(...):
    """Process multiple newsletter episodes in batch."""
    # 1. Load newsletter profile
    # 2. Parse RSS feed if configured
    # 3. Filter entries based on options
    # 4. Check for already processed
    # 5. Process each entry (with parallelization if requested)
    # 6. Report results
    pass
```

#### 4. Newsletter Management CLI
**New Commands:**

```bash
# List configured newsletters
python -m src newsletters list

# Show details for specific newsletter
python -m src newsletters show the-batch

# List episodes for newsletter
python -m src newsletters episodes the-batch

# Check for new episodes without processing
python -m src newsletters check the-batch

# Enable/disable newsletter
python -m src newsletters enable the-batch
python -m src newsletters disable the-batch
```

**Implementation:**
```python
@cli.group()
def newsletters():
    """Manage newsletter configurations."""
    pass

@newsletters.command()
def list():
    """List all configured newsletters."""
    # Show table with: ID, Name, Enabled, RSS Feed, Last Processed
    pass

@newsletters.command()
@click.argument("newsletter_id")
def show(newsletter_id):
    """Show details for a newsletter."""
    # Show full configuration + statistics
    pass

@newsletters.command()
@click.argument("newsletter_id")
@click.option("--limit", type=int, default=10)
def episodes(newsletter_id, limit):
    """List episodes for a newsletter."""
    # Query database for episodes with this profile_id
    pass

@newsletters.command()
@click.argument("newsletter_id")
def check(newsletter_id):
    """Check RSS feed for new episodes."""
    # Parse RSS and show what's new vs processed
    pass
```

#### 5. Parallel Processing Support
**File to Create:** `src/lib/parallel_processor.py`

**Functionality:**
- Process multiple newsletters concurrently
- Respect max_concurrent_jobs from config
- Handle errors gracefully per job
- Provide progress reporting

**Implementation:**
```python
import asyncio
from typing import List, Callable, Any

class ParallelProcessor:
    """Process multiple items in parallel with concurrency control."""

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def process_items(
        self,
        items: List[Any],
        processor_func: Callable,
        on_progress: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ) -> List[Any]:
        """
        Process items in parallel with concurrency limit.

        Args:
            items: Items to process
            processor_func: Async function to process each item
            on_progress: Optional callback for progress updates
            on_error: Optional callback for error handling

        Returns:
            List of results (None for failed items)
        """
        async def process_with_semaphore(item):
            async with self.semaphore:
                try:
                    result = await processor_func(item)
                    if on_progress:
                        on_progress(item, result)
                    return result
                except Exception as e:
                    if on_error:
                        on_error(item, e)
                    return None

        tasks = [process_with_semaphore(item) for item in items]
        return await asyncio.gather(*tasks)
```

### Database Schema Changes

No new tables needed. Existing schema supports batch processing:
- `newsletters.newsletter_profile_id` - Link to profile
- `newsletters.content_hash` - Prevents duplicates
- `newsletters.url` - Track source URLs

Optional enhancement - add tracking table:
```sql
CREATE TABLE processed_episodes (
    id VARCHAR(36) PRIMARY KEY,
    newsletter_profile_id VARCHAR(100) NOT NULL,
    rss_guid VARCHAR(500),
    url VARCHAR(2048),
    published_date DATETIME,
    processed_at DATETIME NOT NULL,
    newsletter_id VARCHAR(36),
    FOREIGN KEY(newsletter_id) REFERENCES newsletters(id),
    UNIQUE(newsletter_profile_id, rss_guid)
);
```

### Implementation Order

1. **RSS Parser** (1-2 hours)
   - Install feedparser
   - Implement RSSFeedParser class
   - Unit tests with sample feeds

2. **Episode Tracker** (2-3 hours)
   - Implement deduplication logic
   - Database queries for processed episodes
   - Unit tests

3. **Newsletter Management CLI** (2-3 hours)
   - `newsletters list/show/episodes/check` commands
   - Table formatting with rich
   - Integration tests

4. **Batch Processing CLI** (3-4 hours)
   - `batch-process` command with all options
   - Integration with RSS parser and tracker
   - Progress reporting
   - Integration tests

5. **Parallel Processing** (2-3 hours)
   - Implement ParallelProcessor
   - Integration with batch-process
   - Concurrency tests

**Total Estimate:** 10-15 hours

---

## Phase 3: Advanced Features

### Status: 📋 PLANNED

### Components to Implement

#### 1. MP3 ID3 Metadata Tagging
**File to Create:** `src/lib/id3_tagger.py`

**Dependencies:**
```python
# Add to requirements.txt
mutagen>=1.47.0
```

**Functionality:**
- Write ID3v2 tags to MP3 files
- Include: title, artist, album, year, genre, cover art, description
- Support podcast-specific tags (iTunes)

**Implementation:**
```python
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, APIC, COMM
from mutagen.mp3 import MP3
from pathlib import Path
from typing import Optional

class ID3Tagger:
    """Write ID3 metadata to MP3 files."""

    def tag_episode(
        self,
        file_path: Path,
        title: str,
        artist: str,
        album: str,
        year: Optional[int] = None,
        genre: str = "Podcast",
        description: Optional[str] = None,
        cover_image_path: Optional[Path] = None
    ) -> None:
        """Write ID3 tags to MP3 file."""
        audio = MP3(file_path, ID3=ID3)

        # Add ID3 tags if they don't exist
        try:
            audio.add_tags()
        except:
            pass

        # Standard tags
        audio.tags["TIT2"] = TIT2(encoding=3, text=title)
        audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
        audio.tags["TALB"] = TALB(encoding=3, text=album)
        audio.tags["TCON"] = TCON(encoding=3, text=genre)

        if year:
            audio.tags["TDRC"] = TDRC(encoding=3, text=str(year))

        if description:
            audio.tags["COMM"] = COMM(
                encoding=3,
                lang='eng',
                desc='Description',
                text=description
            )

        # Cover art
        if cover_image_path and cover_image_path.exists():
            with open(cover_image_path, 'rb') as img:
                audio.tags["APIC"] = APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,  # Cover (front)
                    desc='Cover',
                    data=img.read()
                )

        audio.save()
```

**Integration:**
```python
# In newsletter_processor.py, after TTS generation:
from src.lib.id3_tagger import ID3Tagger

if newsletter_profile:
    tagger = ID3Tagger()
    tagger.tag_episode(
        file_path=Path(tts_response.audio_file_path),
        title=episode.title,
        artist=newsletter_profile.podcast_metadata.author,
        album=newsletter_profile.podcast_metadata.title,
        year=datetime.now().year,
        description=episode.description,
        cover_image_path=Path(newsletter_profile.podcast_metadata.image_url) if newsletter_profile.podcast_metadata.image_url else None
    )
```

#### 2. M3U Playlist Generation
**File to Create:** `src/lib/playlist_generator.py`

**Functionality:**
- Generate M3U/M3U8 playlists per newsletter
- Update playlist when new episodes added
- Support extended M3U format with metadata

**Implementation:**
```python
from pathlib import Path
from typing import List
from src.models import Episode

class PlaylistGenerator:
    """Generate M3U playlists for newsletters."""

    def generate_m3u(
        self,
        episodes: List[Episode],
        output_path: Path,
        playlist_title: str,
        extended: bool = True
    ) -> None:
        """Generate M3U playlist file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            if extended:
                f.write("#EXTM3U\n")
                f.write(f"#PLAYLIST:{playlist_title}\n\n")

            for episode in episodes:
                if extended:
                    f.write(f"#EXTINF:{episode.duration_seconds},{episode.title}\n")
                f.write(f"{episode.audio_file_path}\n")

    def update_newsletter_playlist(
        self,
        newsletter_profile_id: str,
        newsletter_profile: NewsletterProfile,
        storage_manager: StorageManager
    ) -> Path:
        """Generate/update playlist for a newsletter."""
        # Get all completed episodes for this newsletter
        # Generate M3U file
        # Save to newsletter folder
        pass
```

**CLI Command:**
```bash
# Generate playlist for newsletter
python -m src playlists generate the-batch

# Generate for all newsletters
python -m src playlists generate --all

# Auto-update playlists after processing
python -m src batch-process --newsletter the-batch --latest 5 --update-playlist
```

#### 3. Scheduled Processing (Cron Integration)
**File to Create:** `src/cli/scheduler.py`

**Functionality:**
- Cron-compatible command for scheduled runs
- Process new episodes from configured newsletters
- Send email/slack notifications on completion/errors
- Log results to file

**Implementation:**
```bash
# Cron entry (daily at 6 AM)
0 6 * * * cd /path/to/batch_podcast && .venv/bin/python -m src scheduled-run

# Or with specific newsletter
0 6 * * * cd /path/to/batch_podcast && .venv/bin/python -m src scheduled-run --newsletter the-batch
```

**Command Implementation:**
```python
@cli.command()
@click.option("--newsletter", help="Specific newsletter or all if not specified")
@click.option("--notify-email", help="Email for completion notification")
@click.option("--notify-slack", help="Slack webhook URL")
@click.option("--log-file", default="logs/scheduled_run.log", help="Log file path")
def scheduled_run(newsletter, notify_email, notify_slack, log_file):
    """Run scheduled processing of newsletters."""
    # 1. Load enabled newsletters (or specific one)
    # 2. For each newsletter with RSS feed:
    #    - Check for new episodes
    #    - Process new episodes
    # 3. Log results
    # 4. Send notifications
    pass
```

### Implementation Order

1. **ID3 Tagging** (2-3 hours)
   - Install mutagen
   - Implement ID3Tagger class
   - Integration with newsletter processor
   - Tests with sample MP3s

2. **Playlist Generation** (2-3 hours)
   - Implement PlaylistGenerator
   - CLI commands
   - Auto-update logic
   - Tests

3. **Scheduled Processing** (3-4 hours)
   - Implement scheduled-run command
   - Notification system
   - Logging
   - Cron documentation
   - Tests

**Total Estimate:** 7-10 hours

---

## Test Plans

### Phase 1: Newsletter Profiles & Smart Organization

#### Unit Tests

**`tests/unit/test_newsletter_config.py`**
```python
def test_newsletter_profile_validation():
    """Test newsletter profile Pydantic validation."""
    # Valid profile
    # Invalid length/style values
    # Missing required fields

def test_url_pattern_matching():
    """Test URL pattern matching logic."""
    # Matching URLs
    # Non-matching URLs
    # Wildcard patterns

def test_metadata_extraction():
    """Test regex-based metadata extraction."""
    # Extract issue number from URL
    # Extract from content
    # Handle missing patterns

def test_filename_generation():
    """Test filename template generation."""
    # All variables provided
    # Missing variables (graceful handling)
    # Special character sanitization
```

**`tests/unit/test_storage_manager.py`**
```python
def test_output_directory_creation():
    """Test directory creation logic."""
    # With profile
    # Without profile (uncategorized)
    # Nested directories

def test_filename_sanitization():
    """Test special character handling."""
    # Spaces → dashes
    # Invalid filename characters removed
    # Unicode handling

def test_relative_path_conversion():
    """Test path conversion for database storage."""
    # Absolute to relative
    # Already relative paths
```

#### Integration Tests

**`tests/integration/test_newsletter_profiles.py`**
```python
async def test_process_with_profile():
    """Test end-to-end processing with profile."""
    # Configure test profile
    # Process newsletter URL
    # Verify profile_id stored
    # Verify issue_number extracted
    # Verify file in correct folder with correct name

async def test_profile_auto_detection():
    """Test automatic profile detection from URL."""
    # URL matches pattern
    # Profile auto-assigned
    # Metadata extracted

async def test_profile_overrides():
    """Test explicit options override profile defaults."""
    # Profile has length="long"
    # CLI specifies --length medium
    # Verify medium used
```

### Phase 2: RSS Feeds & Batch Processing

#### Unit Tests

**`tests/unit/test_rss_parser.py`**
```python
def test_parse_rss_feed():
    """Test RSS feed parsing."""
    # Valid RSS 2.0
    # Valid Atom
    # Invalid feed (error handling)

def test_parse_dates():
    """Test date parsing from various formats."""
    # RFC 2822
    # ISO 8601
    # Missing dates

def test_filter_entries():
    """Test entry filtering logic."""
    # Date range filtering
    # Limit application
    # Empty results
```

**`tests/unit/test_episode_tracker.py`**
```python
async def test_duplicate_detection():
    """Test duplicate episode detection."""
    # Same URL
    # Same GUID
    # Different representations of same content

async def test_unprocessed_filtering():
    """Test filtering to unprocessed episodes."""
    # All new
    # All processed
    # Mixed
```

#### Integration Tests

**`tests/integration/test_batch_processing.py`**
```python
async def test_batch_process_latest():
    """Test processing latest N episodes."""
    # Mock RSS feed with 10 entries
    # Process latest 5
    # Verify 5 processed
    # Verify correct ones selected

async def test_skip_existing():
    """Test skipping already processed episodes."""
    # Process feed first time
    # Process again with --skip-existing
    # Verify no duplicates

async def test_parallel_processing():
    """Test concurrent episode processing."""
    # Process 5 episodes with --parallel 3
    # Verify all processed
    # Verify concurrency limit respected
```

### Phase 3: Advanced Features

#### Unit Tests

**`tests/unit/test_id3_tagger.py`**
```python
def test_write_id3_tags():
    """Test writing ID3 tags."""
    # Create test MP3
    # Write tags
    # Read back and verify

def test_cover_art_embedding():
    """Test embedding cover art."""
    # With JPEG
    # With PNG
    # Missing image (graceful)
```

**`tests/unit/test_playlist_generator.py`**
```python
def test_m3u_generation():
    """Test M3U playlist generation."""
    # Standard M3U
    # Extended M3U
    # Empty playlist

def test_playlist_update():
    """Test updating existing playlist."""
    # Add new episodes
    # Remove deleted episodes
    # Maintain order
```

#### Integration Tests

**`tests/integration/test_id3_metadata.py`**
```python
async def test_metadata_after_processing():
    """Test metadata written during processing."""
    # Process newsletter
    # Check MP3 has correct ID3 tags
    # Verify all fields present

async def test_playlist_auto_update():
    """Test playlist updates after new episodes."""
    # Process first episode
    # Check playlist created
    # Process second episode
    # Check playlist updated
```

### Test Data

**`tests/fixtures/sample_feeds/`**
- `the-batch-sample.xml` - Sample RSS feed
- `tech-weekly-sample.atom` - Sample Atom feed

**`tests/fixtures/sample_content/`**
- `sample-newsletter.html` - Test newsletter HTML
- `sample-cover.jpg` - Test podcast cover art

**`tests/fixtures/configs/`**
- `test-newsletters.yaml` - Test newsletter config

### Coverage Requirements

- **Unit Tests:** 90%+ coverage
- **Integration Tests:** Critical paths covered
- **Contract Tests:** All API endpoints

### Running Tests

```bash
# All tests
pytest

# Specific phase
pytest tests/unit/test_newsletter_config.py
pytest tests/integration/test_newsletter_profiles.py

# With coverage
pytest --cov=src --cov-report=html

# Specific markers
pytest -m unit
pytest -m integration
pytest -m contract
```

---

## Summary

### Completed Features
✅ Newsletter configuration system
✅ Smart file organization
✅ Database schema for profiles
✅ Enhanced CLI with --newsletter flag
✅ Cost tracking infrastructure (70%)

### Ready for Implementation
📋 Phase 2: RSS feeds & batch processing (10-15 hours)
📋 Phase 3: MP3 metadata & playlists (7-10 hours)
📋 Cost tracking integration (2-3 hours)

### Total Estimated Effort
- Phase 2: 10-15 hours
- Phase 3: 7-10 hours
- Cost tracking completion: 2-3 hours
- **Total: 19-28 hours**

### Next Steps
1. Complete cost tracking integration
2. Implement Phase 2 RSS parsing
3. Implement Phase 2 batch processing
4. Implement Phase 3 features
5. Comprehensive testing
6. Documentation updates
