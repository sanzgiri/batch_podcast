# Quickstart Guide: Newsletter to Podcast Generator

**Date**: 2025-10-16  
**Purpose**: Quick setup and testing scenarios for the newsletter-to-podcast application

## Prerequisites

### System Requirements
- Python 3.11 or higher
- 4GB RAM minimum (8GB recommended for local AI services)
- 10GB disk space for audio files and models
- Internet connection (for cloud AI services and RSS hosting)

### Optional Local AI Services
- **Ollama** (for local LLM): Download from https://ollama.ai/
- **Kokoro TTS** (for local TTS): Docker container or local installation

## Installation

### 1. Install Application
```bash
# Clone repository
git clone <repository-url>
cd newsletter-podcast-generator

# Install dependencies
pip install -r requirements.txt

# Install application
pip install -e .
```

### 2. Initialize Configuration
```bash
# Create configuration directory
mkdir -p ~/.newsletter-podcast

# Initialize default configuration
newsletter-podcast config init
```

### 3. Configure Services

#### Option A: Cloud Services (Quick Start)
```bash
# Set OpenAI for LLM
newsletter-podcast config set llm provider openai
newsletter-podcast config set llm api_key "OPENAI_API_KEY"

# Set Unreal Speech for TTS
newsletter-podcast config set tts provider unreal_speech
newsletter-podcast config set tts api_key "your-unreal-speech-key"

# Set cloud storage
newsletter-podcast config set storage provider s3
newsletter-podcast config set storage access_key "AKIA..."
newsletter-podcast config set storage secret_key "your-secret"
newsletter-podcast config set storage bucket "your-bucket"
newsletter-podcast config set storage region "us-east-1"
```

#### Option B: Local Services (Privacy-Focused)
```bash
# Install and start Ollama
ollama pull llama2
ollama serve &

# Configure local LLM
newsletter-podcast config set llm provider ollama
newsletter-podcast config set llm base_url "http://localhost:11434"
newsletter-podcast config set llm model "llama2"

# Configure local TTS (assuming Kokoro running on port 8080)
newsletter-podcast config set tts provider kokoro
newsletter-podcast config set tts base_url "http://localhost:8080"

# Use local file storage
newsletter-podcast config set storage provider local
newsletter-podcast config set storage base_path "/var/podcast-files"
```

### 4. Configure Podcast Feed
```bash
# Set podcast metadata
newsletter-podcast config set feed title "My Newsletter Podcast"
newsletter-podcast config set feed description "Weekly newsletter insights in audio form"
newsletter-podcast config set feed author "Your Name"
newsletter-podcast config set feed email "your-email@example.com"
newsletter-podcast config set feed language "en"
```

### 5. Validate Configuration
```bash
# Check all services
newsletter-podcast health

# Validate configuration
newsletter-podcast config validate
```

## Basic Usage Scenarios

### Scenario 1: Process Newsletter from URL

**Goal**: Convert a web newsletter into a podcast episode

```bash
# Submit newsletter URL
newsletter-podcast submit url "https://example.com/newsletter/latest" \
  --title "Weekly Tech Update" \
  --wait

# Check processing status
newsletter-podcast status <newsletter-id>

# List episodes
newsletter-podcast list episodes

# Download generated audio
newsletter-podcast download <episode-id> --output "tech-update.mp3"
```

**Expected Results**:
- Newsletter content extracted from URL
- Content summarized by LLM service
- Audio generated from summary
- MP3 file uploaded to configured storage
- Episode available in RSS feed

### Scenario 2: Process Newsletter from Text File

**Goal**: Convert local newsletter content into a podcast episode

```bash
# Create sample newsletter content
cat > newsletter.txt << EOF
# Weekly Newsletter - October 16, 2025

## Top Stories

This week we're covering the latest developments in AI technology,
including new breakthroughs in natural language processing and 
computer vision applications. The industry continues to evolve
rapidly with several major announcements from leading tech companies.

## Key Updates

- OpenAI releases new model with improved reasoning capabilities
- Google announces advances in multimodal AI systems  
- Microsoft integrates AI features across productivity suite
- Startups raise significant funding for AI infrastructure

## Analysis

The pace of AI development shows no signs of slowing down.
Organizations are increasingly adopting these technologies
to improve efficiency and create new user experiences.
EOF

# Submit text content
newsletter-podcast submit text --file newsletter.txt \
  --title "Weekly AI Newsletter" \
  --publication-date "2025-10-16T10:00:00Z" \
  --wait

# Monitor progress
newsletter-podcast status <newsletter-id> --watch

# Get episode details
newsletter-podcast get episode <episode-id>
```

**Expected Results**:
- Text content processed and summarized
- Natural-sounding audio generated
- Episode metadata correctly populated
- Audio file accessible via download

### Scenario 3: RSS Feed Integration

**Goal**: Verify podcast feed works with podcast apps

```bash
# Update feed metadata
newsletter-podcast feed update \
  --title "Tech News Digest" \
  --description "Weekly technology news and analysis in audio format" \
  --author "Tech Analyst" \
  --category "Technology"

# Show feed information
newsletter-podcast feed show

# Get RSS feed URL
RSS_URL=$(newsletter-podcast feed show --output-format json | jq -r '.rss_url')

# Test RSS feed validation
curl -s "$RSS_URL" | xmllint --format -

# Force rebuild feed
newsletter-podcast feed rebuild
```

**Expected Results**:
- Valid RSS 2.0 XML feed generated
- iTunes podcast tags included
- All published episodes listed
- Feed validates with podcast directories

### Scenario 4: Service Configuration Testing

**Goal**: Test switching between local and cloud AI services

```bash
# Test current configuration
newsletter-podcast health --service all

# Switch to different LLM provider
newsletter-podcast config set llm provider ollama
newsletter-podcast health --service llm

# Process newsletter with new configuration
newsletter-podcast submit text --content "Test content for local processing" \
  --title "Configuration Test" \
  --wait

# Switch back to cloud provider
newsletter-podcast config set llm provider openai
newsletter-podcast health --service llm

# Compare processing results
newsletter-podcast list episodes --output-format table
```

**Expected Results**:
- Services switch correctly based on configuration
- Processing completes with both local and cloud services
- Episodes generated with appropriate service attribution

### Scenario 5: Error Handling and Retry

**Goal**: Test system resilience and error recovery

```bash
# Submit newsletter that might cause processing errors
newsletter-podcast submit text --content "Very short content." \
  --title "Error Test" \
  --wait

# Check for processing failures
newsletter-podcast list newsletters --status failed

# Retry failed processing
newsletter-podcast retry <newsletter-id> --wait

# Monitor retry progress
newsletter-podcast status <newsletter-id> --watch
```

**Expected Results**:
- System handles processing errors gracefully
- Clear error messages provided to user
- Retry mechanism recovers from transient failures
- Appropriate logging for debugging

## Performance Testing

### Load Testing
```bash
# Submit multiple newsletters concurrently
for i in {1..5}; do
  newsletter-podcast submit text \
    --content "Newsletter content $i with sufficient length for processing..." \
    --title "Load Test Episode $i" &
done

# Monitor processing
newsletter-podcast list newsletters --status processing

# Wait for completion
wait

# Verify all episodes generated
newsletter-podcast list episodes
```

### Large Content Testing
```bash
# Test with maximum content size (approach 10,000 words)
# Create large newsletter file
python -c "
content = 'This is a comprehensive newsletter covering multiple topics. ' * 500
with open('large_newsletter.txt', 'w') as f:
    f.write(content)
print(f'Created file with {len(content.split())} words')
"

# Submit large content
newsletter-podcast submit text --file large_newsletter.txt \
  --title "Large Content Test" \
  --wait --timeout 1200

# Verify processing within performance targets
newsletter-podcast get episode <episode-id>
```

## Integration Testing

### Podcast App Testing
1. Get RSS feed URL: `newsletter-podcast feed show`
2. Add feed to podcast app (Apple Podcasts, Overcast, Spotify)
3. Verify episodes appear correctly
4. Test episode playback and metadata display

### Storage Integration Testing
```bash
# Test cloud storage connectivity
newsletter-podcast health --service storage

# Verify audio file accessibility
EPISODE_ID=$(newsletter-podcast list episodes -n 1 --output-format json | jq -r '.items[0].id')
newsletter-podcast download $EPISODE_ID --output test-download.mp3

# Verify file integrity
file test-download.mp3
ffprobe test-download.mp3
```

## Troubleshooting

### Common Issues

**Configuration Errors**:
```bash
# Validate configuration
newsletter-podcast config validate

# Check service connectivity
newsletter-podcast health
```

**Processing Failures**:
```bash
# Check logs (application-specific log location)
tail -f ~/.newsletter-podcast/logs/app.log

# Retry with verbose output
newsletter-podcast retry <newsletter-id> --verbose
```

**Storage Issues**:
```bash
# Test storage connectivity
newsletter-podcast health --service storage

# Check storage configuration
newsletter-podcast config show --section storage
```

### Support Information

For additional support and detailed logging:
- Enable verbose mode: `--verbose` flag
- Check log files in `~/.newsletter-podcast/logs/`
- Validate configuration: `newsletter-podcast config validate`
- Test service health: `newsletter-podcast health`

## Next Steps

After completing the quickstart scenarios:

1. **Production Setup**: Configure production-grade storage and monitoring
2. **Automation**: Set up scheduled newsletter processing
3. **Scaling**: Consider distributed processing for high-volume usage
4. **Customization**: Adjust LLM prompts and TTS settings for your content style
5. **Monitoring**: Implement comprehensive logging and alerting