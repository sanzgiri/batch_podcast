# Data Model: Newsletter to Podcast Generator

**Date**: 2025-10-16  
**Feature**: Newsletter to Podcast Generator  
**Purpose**: Define data structures, relationships, and validation rules

## Core Entities

### Newsletter
**Purpose**: Source content for podcast episode generation

**Fields**:
- `id`: UUID, primary key
- `title`: String(500), required, newsletter title/subject
- `url`: String(2048), optional, source URL if extracted from web
- `content`: Text, required, raw newsletter content
- `extracted_content`: Text, optional, cleaned/extracted text content
- `publication_date`: DateTime, optional, original publication date
- `submitted_at`: DateTime, required, when content was submitted
- `content_hash`: String(64), required, SHA-256 hash for deduplication
- `word_count`: Integer, computed from content
- `status`: Enum(pending, processing, completed, failed), processing status

**Validation Rules**:
- Either `url` or `content` must be provided
- `content` length must be between 100 and 50,000 characters
- `url` must be valid HTTP/HTTPS URL if provided
- `title` cannot be empty if provided

**State Transitions**:
- pending → processing (when summarization starts)
- processing → completed (successful processing)
- processing → failed (processing error)
- failed → processing (retry)

### Episode
**Purpose**: Generated podcast episode with metadata and assets

**Fields**:
- `id`: UUID, primary key
- `newsletter_id`: UUID, foreign key to Newsletter
- `title`: String(500), required, episode title
- `description`: Text, required, episode description/summary
- `summary_text`: Text, required, LLM-generated summary
- `audio_file_path`: String(1024), optional, local audio file path
- `audio_url`: String(2048), optional, public cloud storage URL
- `duration_seconds`: Integer, optional, audio duration
- `file_size_bytes`: Integer, optional, audio file size
- `publication_date`: DateTime, required, episode publish date
- `created_at`: DateTime, required, episode creation timestamp
- `updated_at`: DateTime, required, last update timestamp
- `status`: Enum(draft, generating_audio, uploading, published, failed)
- `llm_service_used`: String(100), which LLM service was used
- `tts_service_used`: String(100), which TTS service was used

**Validation Rules**:
- `title` and `description` cannot be empty
- `duration_seconds` must be positive if provided
- `file_size_bytes` must be positive if provided
- `publication_date` cannot be in the future
- Valid status transitions must be enforced

**State Transitions**:
- draft → generating_audio (TTS starts)
- generating_audio → uploading (audio complete, upload starts)
- uploading → published (upload complete, RSS updated)
- Any status → failed (error occurred)
- failed → generating_audio (retry)

**Relationships**:
- Many-to-one with Newsletter (one newsletter → multiple episode attempts)

### PodcastFeed
**Purpose**: RSS feed configuration and metadata

**Fields**:
- `id`: UUID, primary key
- `title`: String(500), required, podcast title
- `description`: Text, required, podcast description
- `author`: String(200), required, podcast author/creator
- `email`: String(320), optional, contact email
- `language`: String(10), default 'en', language code
- `category`: String(100), optional, iTunes category
- `image_url`: String(2048), optional, podcast artwork URL
- `website_url`: String(2048), optional, podcast website
- `rss_url`: String(2048), required, RSS feed public URL
- `created_at`: DateTime, required, feed creation timestamp
- `updated_at`: DateTime, required, last update timestamp
- `last_build_date`: DateTime, required, RSS last build date
- `is_active`: Boolean, default true, feed status

**Validation Rules**:
- `title`, `description`, `author` cannot be empty
- `email` must be valid email format if provided
- `language` must be valid ISO language code
- All URLs must be valid HTTP/HTTPS format
- `rss_url` must be publicly accessible

**Relationships**:
- One-to-many with Episode (via episode_feed relationship)

### ServiceConfig
**Purpose**: User preferences for AI service providers

**Fields**:
- `id`: UUID, primary key
- `user_id`: String(100), required, user identifier (future multi-user)
- `llm_provider`: Enum(openai, ollama), required, LLM service choice
- `llm_config`: JSON, required, LLM-specific configuration
- `tts_provider`: Enum(unreal_speech, kokoro, chatterbox), required, TTS service choice
- `tts_config`: JSON, required, TTS-specific configuration
- `storage_provider`: Enum(s3, gcs, local), required, storage choice
- `storage_config`: JSON, required, storage configuration
- `created_at`: DateTime, required
- `updated_at`: DateTime, required
- `is_active`: Boolean, default true

**Validation Rules**:
- Each config JSON must match provider schema
- Required API keys/credentials must be present in config
- Storage configuration must include required connection parameters

**Configuration Schemas**:

**OpenAI Config**:
```json
{
  "api_key": "string",
  "model": "gpt-3.5-turbo|gpt-4",
  "max_tokens": 4000,
  "temperature": 0.7
}
```

**Ollama Config**:
```json
{
  "base_url": "http://localhost:11434",
  "model": "llama2|mistral|codellama",
  "timeout": 300
}
```

**Unreal Speech Config**:
```json
{
  "api_key": "string",
  "voice_id": "string",
  "bitrate": "320k|192k|128k",
  "speed": 1.0,
  "pitch": 1.0
}
```

**S3 Config**:
```json
{
  "access_key": "string",
  "secret_key": "string",
  "bucket": "string",
  "region": "string",
  "endpoint_url": "string"
}
```

## Relationships Summary

```
Newsletter (1) ─── (many) Episode
PodcastFeed (1) ─── (many) Episode  
ServiceConfig (1) ─── (1) User [future]
```

## Database Schema Considerations

### Indexes
- `Newsletter.content_hash` (unique, for deduplication)
- `Newsletter.submitted_at` (for chronological queries)
- `Episode.newsletter_id` (foreign key lookup)
- `Episode.publication_date` (for RSS feed ordering)
- `Episode.status` (for processing queries)

### Data Retention
- Keep newsletter content for 90 days after episode publication
- Maintain episode metadata indefinitely
- Archive old episodes after 2 years (configurable)

### Backup Strategy
- Daily automated backups of SQLite database
- Separate backup of audio files in cloud storage
- Point-in-time recovery capability

## Migration Strategy

### Initial Schema
- Create all tables with proper constraints
- Add initial indexes and foreign keys
- Seed default podcast feed configuration

### Version Management
- Use Alembic for database migrations
- Version all schema changes
- Rollback capability for failed migrations