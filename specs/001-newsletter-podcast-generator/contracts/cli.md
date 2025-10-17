# CLI Interface Contract

## Command Structure

The CLI provides a hierarchical command structure for all newsletter-to-podcast operations:

```bash
newsletter-podcast <command> [subcommand] [options]
```

## Main Commands

### `submit` - Submit Newsletter Content

Submit newsletter content for processing into a podcast episode.

#### Subcommands

##### `submit url`
```bash
newsletter-podcast submit url <URL> [options]
```
Extract and process newsletter from a web URL.

**Arguments:**
- `URL` - Newsletter URL to extract and process

**Options:**
- `--title TEXT` - Override newsletter title
- `--output-format {json,table}` - Output format (default: table)
- `--wait` - Wait for processing completion before returning
- `--timeout INTEGER` - Timeout for --wait in seconds (default: 600)

**Examples:**
```bash
newsletter-podcast submit url https://example.com/newsletter/2025-10-16
newsletter-podcast submit url https://example.com/newsletter --title "Weekly Update" --wait
```

##### `submit text`
```bash
newsletter-podcast submit text [options]
```
Submit newsletter content directly as text.

**Options:**
- `--content TEXT` - Newsletter content (required if not using --file)
- `--file PATH` - Read content from file
- `--title TEXT` - Newsletter title
- `--publication-date TEXT` - Original publication date (ISO format)
- `--output-format {json,table}` - Output format (default: table)
- `--wait` - Wait for processing completion before returning
- `--timeout INTEGER` - Timeout for --wait in seconds (default: 600)

**Examples:**
```bash
newsletter-podcast submit text --content "Newsletter content here" --title "Weekly Update"
newsletter-podcast submit text --file newsletter.txt --publication-date "2025-10-16T10:00:00Z"
```

### `list` - List Items

List newsletters, episodes, or other resources.

#### Subcommands

##### `list newsletters`
```bash
newsletter-podcast list newsletters [options]
```

**Options:**
- `--status {pending,processing,completed,failed}` - Filter by status
- `--limit INTEGER` - Maximum items to return (default: 20)
- `--offset INTEGER` - Items to skip (default: 0)
- `--output-format {json,table,csv}` - Output format (default: table)

##### `list episodes`
```bash
newsletter-podcast list episodes [options]
```

**Options:**
- `--status {draft,generating_audio,uploading,published,failed}` - Filter by status
- `--limit INTEGER` - Maximum items to return (default: 20)
- `--offset INTEGER` - Items to skip (default: 0)
- `--output-format {json,table,csv}` - Output format (default: table)

### `get` - Get Item Details

Retrieve detailed information about specific items.

#### Subcommands

##### `get newsletter`
```bash
newsletter-podcast get newsletter <ID> [options]
```

**Arguments:**
- `ID` - Newsletter UUID

**Options:**
- `--output-format {json,yaml,table}` - Output format (default: table)
- `--include-content` - Include full content in output

##### `get episode`
```bash
newsletter-podcast get episode <ID> [options]
```

**Arguments:**
- `ID` - Episode UUID

**Options:**
- `--output-format {json,yaml,table}` - Output format (default: table)

### `download` - Download Episode Audio

Download episode audio files.

```bash
newsletter-podcast download <EPISODE_ID> [options]
```

**Arguments:**
- `EPISODE_ID` - Episode UUID

**Options:**
- `--output PATH` - Output file path (default: <episode-title>.mp3)
- `--overwrite` - Overwrite existing file
- `--progress` - Show download progress

**Examples:**
```bash
newsletter-podcast download abc123-def456 --output my-episode.mp3
newsletter-podcast download abc123-def456 --progress
```

### `status` - Check Processing Status

Check the status of newsletter processing or episode generation.

```bash
newsletter-podcast status <ID> [options]
```

**Arguments:**
- `ID` - Newsletter or Episode UUID

**Options:**
- `--watch` - Continuously monitor status until completion
- `--interval INTEGER` - Polling interval for --watch in seconds (default: 10)
- `--output-format {json,table}` - Output format (default: table)

**Examples:**
```bash
newsletter-podcast status abc123-def456
newsletter-podcast status abc123-def456 --watch --interval 5
```

### `retry` - Retry Failed Processing

Retry processing for failed newsletters or episodes.

```bash
newsletter-podcast retry <NEWSLETTER_ID> [options]
```

**Arguments:**
- `NEWSLETTER_ID` - Newsletter UUID to retry

**Options:**
- `--wait` - Wait for retry completion
- `--output-format {json,table}` - Output format (default: table)

### `config` - Configuration Management

Manage service configurations and settings.

#### Subcommands

##### `config show`
```bash
newsletter-podcast config show [options]
```
Display current configuration.

**Options:**
- `--output-format {json,yaml,table}` - Output format (default: table)
- `--section {llm,tts,storage,feed,all}` - Configuration section (default: all)

##### `config set`
```bash
newsletter-podcast config set <SECTION> <KEY> <VALUE> [options]
```
Set configuration values.

**Arguments:**
- `SECTION` - Configuration section (llm, tts, storage, feed)
- `KEY` - Configuration key
- `VALUE` - Configuration value

**Examples:**
```bash
newsletter-podcast config set llm provider openai
newsletter-podcast config set llm api_key OPENAI_API_KEY
newsletter-podcast config set tts provider unreal_speech
newsletter-podcast config set feed title "My Newsletter Podcast"
```

##### `config validate`
```bash
newsletter-podcast config validate [options]
```
Validate current configuration.

**Options:**
- `--section {llm,tts,storage,feed,all}` - Section to validate (default: all)
- `--output-format {json,table}` - Output format (default: table)

### `feed` - RSS Feed Management

Manage podcast RSS feed.

#### Subcommands

##### `feed show`
```bash
newsletter-podcast feed show [options]
```
Display RSS feed configuration and URL.

**Options:**
- `--output-format {json,yaml,table}` - Output format (default: table)

##### `feed update`
```bash
newsletter-podcast feed update [options]
```
Update RSS feed metadata.

**Options:**
- `--title TEXT` - Podcast title
- `--description TEXT` - Podcast description
- `--author TEXT` - Podcast author
- `--email TEXT` - Contact email
- `--language TEXT` - Language code (default: en)
- `--category TEXT` - iTunes category
- `--image-url TEXT` - Podcast artwork URL
- `--website-url TEXT` - Podcast website URL

##### `feed rebuild`
```bash
newsletter-podcast feed rebuild [options]
```
Force rebuild of RSS feed from current episodes.

**Options:**
- `--output-format {json,table}` - Output format (default: table)

### `health` - Health Check

Check service health and connectivity.

```bash
newsletter-podcast health [options]
```

**Options:**
- `--output-format {json,table}` - Output format (default: table)
- `--service {database,llm,tts,storage,all}` - Specific service to check (default: all)

## Global Options

These options are available for all commands:

- `--config PATH` - Configuration file path (default: ~/.newsletter-podcast/config.yaml)
- `--verbose, -v` - Verbose output
- `--quiet, -q` - Quiet output (errors only)
- `--help, -h` - Show help message

## Output Formats

### Table Format (Default)
Human-readable tabular output with columns and headers.

### JSON Format
Structured JSON output for programmatic use.

### YAML Format
Human-readable YAML output (where supported).

### CSV Format
Comma-separated values for data export (list commands only).

## Exit Codes

- `0` - Success
- `1` - General error
- `2` - Invalid arguments or options
- `3` - Configuration error
- `4` - Service unavailable
- `5` - Resource not found
- `6` - Processing timeout
- `7` - Authentication/authorization error

## Configuration File

Default configuration file location: `~/.newsletter-podcast/config.yaml`

Example configuration structure:
```yaml
llm:
  provider: openai
  api_key: OPENAI_API_KEY
  model: gpt-3.5-turbo
  
tts:
  provider: unreal_speech
  api_key: us-abc123...
  voice_id: default
  
storage:
  provider: s3
  access_key: AKIA...
  secret_key: secret...
  bucket: my-podcast-bucket
  region: us-east-1

feed:
  title: My Newsletter Podcast
  description: Weekly newsletter converted to audio
  author: John Doe
  email: john@example.com
```

## Environment Variables

Configuration can be overridden with environment variables:

- `NP_CONFIG_FILE` - Configuration file path
- `NP_LLM_PROVIDER` - LLM provider
- `NP_LLM_API_KEY` - LLM API key
- `NP_TTS_PROVIDER` - TTS provider  
- `NP_TTS_API_KEY` - TTS API key
- `NP_STORAGE_PROVIDER` - Storage provider
- `NP_STORAGE_ACCESS_KEY` - Storage access key
- `NP_STORAGE_SECRET_KEY` - Storage secret key
- `NP_STORAGE_BUCKET` - Storage bucket name