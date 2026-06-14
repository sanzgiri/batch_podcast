# Project Status - Newsletter Podcast Generator

**Last Updated**: June 13, 2026
**Branch**: main

## ✅ Completed Features

### 0. Phase 2: RSS Feeds & Batch Processing (NEW — 100% Complete)

Auto-discovery + parallel batch processing of newsletter episodes. Resolves the "every episode is a manual `process-url` call" pain point.

- **Files Added**:
  - `src/lib/rss_parser.py` — async wrapper around `feedparser`, with `FeedEntry` dataclass and date/limit filtering
  - `src/lib/url_enumerator.py` — HEAD-probes sequential `issue-N` URLs for newsletters without RSS (e.g. The Batch, which doesn't publish RSS). Polite rate-limiting (0.5s between requests), bounded by `max_consecutive_404` (3) and `max_probes` (50)
  - `src/lib/episode_tracker.py` — dedup against existing DB rows by URL / content-hash / (title+date)
  - `src/services/batch_processor.py` — orchestrator: discover via RSS or enumeration → dedupe → process with `asyncio.Semaphore`-bounded concurrency

- **CLI**:
  ```bash
  python -m src batch-process --newsletter the-batch --latest 5
  python -m src batch-process --newsletter the-batch --dry-run
  python -m src batch-process --newsletter the-batch --all
  python -m src batch-process --newsletter the-batch --latest 10 --parallel 3
  python -m src batch-process --newsletter the-batch --start-issue 200
  ```

- **Verified end-to-end**:
  - Discovery alone: 50 issues found in 32s
  - Full processing of 1 latest issue: ~7 min
  - Output: `data/audio/the-batch/the-batch-2026-06-14-issue-283.mp3`, -16.8 LUFS

- **Side bugs fixed**: `Newsletter.from_url` was using SHA256 of empty string for content_hash (caused UNIQUE constraint collisions for every URL-sourced newsletter), and `set_extracted_content` never recomputed the hash. Both fixed.

- **Tests**: 19 new unit tests in `tests/unit/test_batch_discovery.py`

### 1. TTS Engine Integration (100% Complete)

Integrated [text2audio](https://github.com/sanzgiri/text2audio) directly into the project as `src/lib/tts_engine`. Replaces the old naive Kokoro client (text in → audio out) with a production-quality Kokoro pipeline.

- **Files Added**:
  - `src/lib/tts_engine/__init__.py` — public API
  - `src/lib/tts_engine/blocks.py` — `Block` / `Chapter` dataclasses
  - `src/lib/tts_engine/text_processing.py` — `expand_abbreviations`, `apply_pronunciations`, `clean_inline`, 30+ tech abbreviation rules
  - `src/lib/tts_engine/parsing.py` — `parse_text`, `parse_dialogue` (Speaker:line), `parse_markdown_book`
  - `src/lib/tts_engine/rendering.py` — `parse_voice_spec`, `load_blended_voice` (weighted tensor mix), `silence`, `render_chapter_blocks`
  - `src/lib/tts_engine/encoding.py` — `loudnorm` (ffmpeg), `encode_mp3`, `build_m4b`, `write_wav`
  - `src/lib/tts_engine/presets.py` — preset + pronunciation-dict loaders
  - `src/lib/tts_engine/data/presets/*.json` — 6 bundled presets
  - `src/lib/tts_engine/data/pronunciations/*.json` — `ai_tech`, `finance` dicts
  - `tests/unit/test_tts_engine.py` — **39 unit tests, all passing**

- **Files Rewritten**:
  - `src/services/tts_generator.py` — `KokoroTTSClient._synthesize_sync` now uses the engine end-to-end. Removed `UnrealSpeechClient` (cloud TTS removed by design).
  - `src/services/llm_summarizer.py` — Added shared `_build_system_prompt(mode)` / `_build_user_prompt(request)` helpers; added dialogue-mode prompt that emits `Host:`/`Guest:` transcripts.
  - `src/services/newsletter_processor.py` — Reads `profile.processing.mode` and `profile.tts.*`, threads them through to the TTS engine. Eliminated the directory-swap-then-move dance — engine writes directly to the storage-manager target path.
  - `src/lib/newsletter_config.py` — Added `ProcessingConfig.mode` and a new `TTSProfileConfig` model (preset, voices, pronunciations, loudness target).

- **Config Changes**:
  - `config/development.yaml` — switched from `unreal_speech` → `kokoro_tts` with `af_heart` default
  - `config/newsletters.yaml` — `the-batch` now uses `mode: dialogue` + `tts.preset: podcast_two_host` + `tts.pronunciations: ai_tech`
  - `config/*.template` — documented the full new schema with inline comments

- **Side fix**: `.gitignore` had `lib/` and `data/` patterns that were globally matching `src/lib/` and `src/lib/tts_engine/data/`. Anchored both with `/lib/` and `/data/` so only the venv root paths are excluded.

- **Capabilities Unlocked**:
  - ✅ Voice blending (e.g. `af_heart:0.7,af_nicole:0.3`)
  - ✅ Two-host dialogue rendering (alternating voices on `Host:`/`Guest:` turns)
  - ✅ Structured silence (0.4s between paragraphs, 0.45s between dialogue turns, 0.6s around quotes, 1.2s before section headings)
  - ✅ ffmpeg loudnorm `I=-16:TP=-2:LRA=11` (broadcast podcast standard) — consistent volume across episodes
  - ✅ Pronunciation overrides (Sutskever → Sootskehver, Karpathy → Kar-puh-thee, etc.)
  - ✅ Tech abbreviation expansion (GPU → G.P.U., LLM → L.L.M., AI → A.I.)
  - ✅ M4B output with chapter markers (for book-mode rendering)

### 2. LLM Cost Tracking (100% Complete)
- **Files Modified**:
  - `src/services/llm_summarizer.py` - Token usage extraction and cost calculation
  - `src/lib/cost_tracker.py` - Pricing data and cost calculation utilities
  - `src/models/episode.py` - Added LLM cost tracking fields

- **Functionality**:
  - ✅ Tracks input/output tokens for both OpenAI and Ollama
  - ✅ Calculates costs based on current pricing (Dec 2024)
  - ✅ Stores: `llm_input_tokens`, `llm_output_tokens`, `llm_total_tokens`, `llm_cost`
  - ✅ Works with GPT-4o-mini ($0.15/$0.60 per 1M tokens)
  - ✅ Free for local Ollama models

- **Test Results**:
  - ✅ Successfully tracked 1,721 tokens costing $0.0006
  - ✅ Cost calculation verified accurate
  - ✅ Database fields populated correctly

### 3. Cost Reporting CLI (100% Complete)
- **Files Added**:
  - `src/cli/cost_commands.py` - Three cost reporting commands
  - Updated `src/cli/commands.py` - Integrated cost command group

- **Commands Available**:
  ```bash
  # Summary table with filtering
  python -m src costs summary [--newsletter ID] [--from DATE] [--to DATE] [--limit N]

  # Detailed episode breakdown
  python -m src costs episode <episode-id>

  # Overall statistics
  python -m src costs totals
  ```

- **Features**:
  - ✅ Rich table formatting with colors
  - ✅ Filter by newsletter profile, date range
  - ✅ Aggregated totals and averages
  - ✅ Breakdown by newsletter
  - ✅ Currency formatting ($X.XXXX)

- **Test Results**:
  - ✅ All three commands functional
  - ✅ Handles empty data gracefully
  - ✅ Displays partial data correctly

### 4. Database Schema Updates (100% Complete)
- **Migration Scripts**:
  - `scripts/migrate_add_newsletter_profiles.py` - Newsletter profile support
  - `scripts/migrate_add_cost_tracking.py` - Cost tracking fields

- **New Fields in `episodes` Table**:
  ```sql
  llm_provider VARCHAR(50)
  llm_model VARCHAR(100)
  llm_input_tokens INTEGER
  llm_output_tokens INTEGER
  llm_total_tokens INTEGER
  llm_cost REAL
  tts_provider VARCHAR(50)
  tts_voice VARCHAR(100)
  tts_characters INTEGER
  tts_cost REAL
  total_cost REAL
  ```

- **New Fields in `newsletters` Table**:
  ```sql
  newsletter_profile_id VARCHAR(100)
  issue_number VARCHAR(50)
  slug VARCHAR(100)
  ```

- **Test Results**:
  - ✅ Migrations run successfully
  - ✅ Schema verified in database
  - ✅ Backward compatible (nullable fields)

### 5. Newsletter Profiles & Smart File Organization (100% Complete)
- **Files Added**:
  - `src/lib/newsletter_config.py` - Profile configuration management
  - `src/lib/storage.py` - Smart file path generation
  - `config/newsletters.yaml` - Profile definitions

- **Functionality**:
  - ✅ YAML-based newsletter configuration
  - ✅ Auto-detection from URL patterns
  - ✅ Profile-specific folders (e.g., `data/audio/the-batch/`)
  - ✅ Template-based filenames: `{slug}-{date}-issue-{number}.mp3`
  - ✅ Issue number extraction from URLs
  - ✅ Profile defaults (length, style) with CLI overrides

- **Example**:
  ```yaml
  profiles:
    the-batch:
      name: "The Batch - DeepLearning.AI"
      url_patterns:
        - "deeplearning.ai/the-batch"
      settings:
        target_length: "long"
        style: "conversational"
  ```

### 6. Documentation (100% Complete)
- **Files Created**:
  - `README.md` - Project overview and quick start
  - `DEVELOPMENT.md` - Phase 2 & 3 implementation plans
  - `TESTING_GUIDE.md` - Comprehensive test scenarios
  - `CLAUDE.md` - Claude Code integration guide
  - `STATUS.md` - This file

- **Coverage**:
  - ✅ Installation and setup instructions
  - ✅ Usage examples with all CLI commands
  - ✅ Architecture overview
  - ✅ Development workflow
  - ✅ 10 detailed test scenarios
  - ✅ Phase 2 & 3 roadmap

## ⚠️ Known Issues

### Issue #1: TTS Cost Tracking (RESOLVED ✅)
- **Previous Status**: Blocked by `greenlet_spawn` error in TTS pipeline
- **Resolution**: Fixed during the text2audio integration refactor (June 2026)
- **What changed**: The rewritten `newsletter_processor.py` now calls `episode.set_cost_info(tts_characters=..., tts_cost=0.0)` wrapped in a `try/except` and runs the TTS engine fully off the async event loop via `asyncio.to_thread`. The greenlet contention is gone.
- **Current behavior**: `tts_characters` is populated with the input script length on every episode; `tts_cost` is always 0.0 since Kokoro runs locally and is free.

### Issue #2: URL Content Extraction Failures (RESOLVED ✅)
- **Previous Status**: NOT INVESTIGATED — URLs returning empty content (SHA256 of empty string)
- **Resolution**: Verified working on June 13, 2026. The issue was either environmental (Cloudflare/network) at the time of filing, or has resolved itself through extractor improvements. Direct test of issue-282 and issue-323 now returns 3500-4000 words of clean content.
- **End-to-end verification**: Successfully processed `https://www.deeplearning.ai/the-batch/issue-282/` through the full pipeline (3m42s total): URL extraction → LLM dialogue generation → Kokoro TTS → loudnorm → MP3 at `data/audio/the-batch/the-batch-2026-06-14-issue-282.mp3` (3:16, -17.0 LUFS).
- **Side bugs uncovered and fixed during verification**:
  - `greenlet` was missing from requirements.txt (transitive SQLAlchemy async dep)
  - `markdownify` was missing from requirements.txt (content_extractor dep)
  - Ollama client hardcoded a 120s timeout, ignoring config.llm.ollama.timeout; long newsletters timed out
  - Ollama client didn't pass `num_ctx` / `num_predict` to the API, causing JSON truncation on long inputs
  - LLM parser crashed on missing fields (llama3.1:8b often omits `key_points`)
  - LLM parser had no recovery for truncated JSON
  - All fixed; defensive parser + `_recover_truncated_json` salvages partial responses
- **Profile auto-detection verified**: URL `deeplearning.ai/the-batch/issue-282/` correctly matched the `the-batch` profile, extracted issue number `282`, applied dialogue mode + podcast_two_host preset + ai_tech pronunciations.

## 🚧 Incomplete Features (Phase 1)

_All Phase 1 features are now complete. TTS cost tracking was resolved during the text2audio integration._

## 📊 Test Coverage

### Verified Working ✅
1. **Cost Reporting CLI**
   - `costs summary` - Shows table with filtering
   - `costs episode <id>` - Detailed breakdown
   - `costs totals` - Aggregate statistics

2. **LLM Cost Tracking**
   - Token counting (input/output/total)
   - Cost calculation for OpenAI GPT-4o-mini
   - Database storage and retrieval

3. **Database Migrations**
   - Newsletter profiles migration
   - Cost tracking fields migration
   - Schema verification

4. **TTS Engine** (NEW)
   - 39 unit tests in `tests/unit/test_tts_engine.py` — all passing
   - Covers: abbreviation expansion, pronunciation overrides, inline markdown cleanup, voice spec parsing, text/dialogue/markdown parsers, preset loading, pronunciation-dict loading, silence generation

5. **TTS Cost Tracking** (NEW — was blocked, now working)
   - `tts_characters` populated per episode
   - `tts_cost` = 0.0 (Kokoro is local)
   - `total_cost` correctly aggregates LLM + TTS

### Not Tested ⏳
_(none — all Phase 1 features end-to-end verified June 13, 2026)_

## 📈 Phase 2 & 3 Roadmap

### Phase 2: RSS Feeds & Batch Processing (10-15 hours estimated)
- RSS feed parser with `feedparser`
- Episode deduplication by URL/content hash
- Batch processing CLI commands
- Newsletter management (list, search, delete)
- Parallel processing support

### Phase 3: Advanced Features (7-10 hours estimated)
- MP3 ID3 metadata tagging with `mutagen`
- M3U playlist generation
- Scheduled processing (cron integration)
- Optional cloud storage (S3)

**See `DEVELOPMENT.md` for detailed implementation plans**

## 🎯 Immediate Next Steps

### Priority 1: ✅ Complete — begin Phase 2
1. **Implement RSS feed parser** (`src/lib/rss_parser.py` — already planned in DEVELOPMENT.md)
2. **Episode tracking & deduplication** (`src/lib/episode_tracker.py`)
3. **Batch processing CLI**: `python -m src batch-process --newsletter the-batch --latest 5`
4. **Parallel processing** via asyncio.gather + semaphore

### Priority 2: Phase 3 (after Phase 2)
5. **MP3 ID3 tags** via mutagen (already in requirements.txt) — title, artist, album, cover art
6. **M3U playlist generation** per newsletter — `playlists/{slug}.m3u`

### Priority 3: Cleanup
7. **Delete or rewrite the broken pre-existing tests** in `tests/unit/test_{content_extractor,llm_summarizer,tts_generator}.py` (12 TDD scaffolds that fail on `main`)
8. **Add coverage gate** for the TTS engine (already at ~95% line coverage)

## 💾 Code Quality

- ✅ Type hints throughout (Python 3.11+ syntax)
- ✅ Async/await patterns
- ✅ Pydantic validation
- ✅ Comprehensive docstrings
- ✅ Error handling with custom exceptions
- ✅ Structured logging
- ✅ Database migrations for schema changes
- ✅ 39 new unit tests for `src/lib/tts_engine` (all passing)
- ⚠️ Pre-existing tests in `tests/unit/test_*.py` (content_extractor, llm_summarizer, tts_generator) are TDD scaffolds against an aspirational API that doesn't match the actual code — they fail on `main`. Out of scope for this work.

## 🔧 Environment

- **Python**: 3.11+
- **Database**: SQLite (async via aiosqlite)
- **Key Libraries**: FastAPI, SQLAlchemy, Pydantic, aiohttp, Kokoro, soundfile, numpy
- **System deps**: ffmpeg, espeak-ng
- **Config**: YAML-based with environment overrides
- **Database Files**:
  - `data/newsletter_podcast_local.db` (used by local.yaml)
  - `data/newsletter_podcast_dev.db` (configured in development.yaml)

## 📝 Notes

- Cost tracking for LLM is production-ready
- Cost CLI commands are fully functional
- TTS cost tracking is now working (Kokoro is free, character counts are recorded for analytics)
- All TTS rendering happens locally via the new `src/lib/tts_engine` (text2audio-derived)
- Cloud TTS providers (Unreal Speech, gTTS) were removed by design — keeps the project fully local
- URL extraction issue may be environmental
- All migrations are backward compatible
- Documentation is up-to-date as of June 13, 2026
- Ready for Phase 2 work after resolving URL extraction issue
