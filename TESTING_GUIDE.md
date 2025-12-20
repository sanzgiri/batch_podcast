# Testing Guide - Phase 1

## Phase 1 Features to Test

1. ✅ Newsletter configuration system
2. ✅ Smart file organization
3. ✅ Newsletter profile auto-detection
4. ✅ Metadata extraction (issue numbers)
5. ✅ Cost tracking (LLM + TTS)
6. ✅ Cost reporting CLI

## Pre-Test Setup

```bash
# 1. Ensure database is migrated
python scripts/migrate_add_newsletter_profiles.py
python scripts/migrate_add_cost_tracking.py

# 2. Verify newsletter configuration
cat config/newsletters.yaml

# 3. Check data directories
ls -la data/audio/
```

## Test 1: Basic Newsletter Processing with Profile

**Objective:** Process a newsletter using the configured "the-batch" profile

```bash
# Process with explicit profile
python -m src process-url \
  "https://www.deeplearning.ai/the-batch/issue-323/" \
  --newsletter the-batch \
  --wait
```

**Expected Results:**
- ✓ Newsletter auto-assigned to "the-batch" profile
- ✓ Issue number extracted: "323"
- ✓ File saved to: `data/audio/the-batch/the-batch-YYYY-MM-DD-issue-323.mp3`
- ✓ Length: "long" (20-30 min comprehensive coverage)
- ✓ Cost information logged in console

**Verification:**
```bash
# Check file location
ls -la data/audio/the-batch/

# Check database
sqlite3 data/newsletter_podcast_local.db "
SELECT
    newsletter_profile_id,
    issue_number,
    slug,
    status
FROM newsletters
ORDER BY created_at DESC
LIMIT 1;"

# Check cost tracking
sqlite3 data/newsletter_podcast_local.db "
SELECT
    llm_total_tokens,
    llm_cost,
    tts_characters,
    tts_cost,
    total_cost
FROM episodes
ORDER BY created_at DESC
LIMIT 1;"
```

## Test 2: Auto-Detection from URL

**Objective:** Verify newsletter profile auto-detects from URL pattern

```bash
# Process without --newsletter flag (should auto-detect)
python -m src process-url \
  "https://www.deeplearning.ai/the-batch/issue-325/" \
  --wait
```

**Expected Results:**
- ✓ Profile auto-detected as "the-batch" from URL pattern
- ✓ Same file organization applied
- ✓ Issue number: "325"

**Verification:**
```bash
sqlite3 data/newsletter_podcast_local.db "
SELECT newsletter_profile_id, issue_number
FROM newsletters
WHERE url LIKE '%issue-325%';"
```

## Test 3: Override Profile Settings

**Objective:** Verify CLI options override profile defaults

```bash
# Profile has length="long", but override with medium
python -m src process-url \
  "https://www.deeplearning.ai/the-batch/issue-326/" \
  --newsletter the-batch \
  --length medium \
  --wait
```

**Expected Results:**
- ✓ Uses "medium" length instead of profile's "long"
- ✓ Shorter audio (~10-15 min vs 20-30 min)
- ✓ Still uses profile's file organization

## Test 4: Newsletter Without Profile

**Objective:** Process a newsletter that doesn't match any profile

```bash
# Random URL not in any profile
python -m src process-url \
  "https://example.com/newsletter/test" \
  --wait
```

**Expected Results:**
- ✓ No profile assigned (newsletter_profile_id = NULL)
- ✓ File saved to: `data/audio/uncategorized/newsletter-{id}.mp3`
- ✓ Uses default settings (medium length, conversational style)

## Test 5: Cost Tracking Verification

**Objective:** Verify cost tracking is working for all providers

### Test 5a: OpenAI + Unreal Speech (Paid APIs)

```bash
# Process with OpenAI + Unreal Speech (default)
python -m src process-url "https://www.deeplearning.ai/the-batch/issue-327/" --wait

# Check costs were recorded
sqlite3 data/newsletter_podcast_local.db "
SELECT
    llm_provider,
    llm_model,
    llm_input_tokens,
    llm_output_tokens,
    llm_cost,
    tts_provider,
    tts_characters,
    tts_cost,
    total_cost
FROM episodes
ORDER BY created_at DESC
LIMIT 1;"
```

**Expected Results:**
- ✓ `llm_cost` > 0 (OpenAI GPT-4o-mini: ~$0.0001-0.001 range)
- ✓ `tts_cost` > 0 (Unreal Speech: ~$0.001-0.01 range)
- ✓ `total_cost` = llm_cost + tts_cost
- ✓ Token counts populated
- ✓ Character counts populated

### Test 5b: Ollama + Kokoro (Local/Free)

*Only if you have Ollama/Kokoro running locally*

```bash
# Change config to use local providers
# Edit config/development.yaml:
#   llm.provider: ollama
#   tts.provider: kokoro

python -m src process-url "URL" --wait

# Check costs
sqlite3 data/newsletter_podcast_local.db "
SELECT llm_cost, tts_cost, total_cost
FROM episodes
ORDER BY created_at DESC
LIMIT 1;"
```

**Expected Results:**
- ✓ `llm_cost` = 0.00 (local Ollama)
- ✓ `tts_cost` = 0.00 (local Kokoro)
- ✓ `total_cost` = 0.00
- ✓ Token/character counts still tracked

## Test 6: Cost Reporting CLI

**Objective:** Verify cost reporting commands work

### Test 6a: Summary Report

```bash
# Show cost summary
python -m src costs summary

# Filter by newsletter
python -m src costs summary --newsletter the-batch

# Date range
python -m src costs summary --from 2025-12-01 --to 2025-12-31

# Limit results
python -m src costs summary --limit 5
```

**Expected Output:**
- Table with columns: Date, Title, LLM Tokens, LLM Cost, TTS Chars, TTS Cost, Total Cost
- Totals row at bottom
- Formatted currency values ($X.XXXX)

### Test 6b: Episode Details

```bash
# Get episode ID from database
EPISODE_ID=$(sqlite3 data/newsletter_podcast_local.db \
  "SELECT id FROM episodes ORDER BY created_at DESC LIMIT 1;")

# Show detailed breakdown
python -m src costs episode $EPISODE_ID
```

**Expected Output:**
- Episode metadata
- LLM section: provider, model, tokens, cost
- TTS section: provider, voice, characters, cost
- Total cost highlighted

### Test 6c: Overall Totals

```bash
python -m src costs totals
```

**Expected Output:**
- Total episodes processed
- Total LLM tokens & cost
- Total TTS characters & cost
- Overall total cost
- Average cost per episode
- Breakdown by newsletter profile

## Test 7: File Organization

**Objective:** Verify file naming and organization

```bash
# Process 3 episodes from same newsletter
python -m src process-url "https://www.deeplearning.ai/the-batch/issue-323/" --newsletter the-batch --wait
python -m src process-url "https://www.deeplearning.ai/the-batch/issue-324/" --newsletter the-batch --wait
python -m src process-url "https://www.deeplearning.ai/the-batch/issue-325/" --newsletter the-batch --wait

# Check file organization
ls -lh data/audio/the-batch/
```

**Expected Results:**
```
data/audio/the-batch/
├── the-batch-2025-12-19-issue-323.mp3
├── the-batch-2025-12-19-issue-324.mp3
└── the-batch-2025-12-19-issue-325.mp3
```

- ✓ All files in same folder
- ✓ Consistent naming pattern
- ✓ Issue numbers in filenames
- ✓ Dates in filenames

## Test 8: Metadata Extraction

**Objective:** Verify issue number extraction works

```bash
# Process and check metadata
python -m src process-url "https://www.deeplearning.ai/the-batch/issue-999/" --newsletter the-batch --wait

sqlite3 data/newsletter_podcast_local.db "
SELECT
    url,
    issue_number,
    slug
FROM newsletters
WHERE url LIKE '%issue-999%';"
```

**Expected Results:**
- ✓ `issue_number` = "999"
- ✓ `slug` = "the-batch"
- ✓ Extracted from URL using regex pattern

## Test 9: Status Tracking

**Objective:** Verify status command shows correct information

```bash
# Get newsletter ID
NEWSLETTER_ID=$(sqlite3 data/newsletter_podcast_local.db \
  "SELECT id FROM newsletters ORDER BY created_at DESC LIMIT 1;")

# Check status
python -m src status $NEWSLETTER_ID
```

**Expected Output:**
- Newsletter details
- Processing status: COMPLETED
- Episode information
- Cost information (if available)

## Test 10: Edge Cases

### Test 10a: Very Short Content

```bash
# Process minimal content
echo "This is a test newsletter." > /tmp/test.txt
python -m src process-file /tmp/test.txt --wait
```

**Expected:**
- Should fail with validation error (content too short)

### Test 10b: Same Newsletter Twice

```bash
# Process same URL twice
python -m src process-url "https://www.deeplearning.ai/the-batch/issue-323/" --wait
python -m src process-url "https://www.deeplearning.ai/the-batch/issue-323/" --wait
```

**Expected:**
- Second attempt fails with duplicate error (content_hash constraint)

### Test 10c: Invalid Newsletter Profile

```bash
python -m src process-url "URL" --newsletter nonexistent --wait
```

**Expected:**
- Warning logged about profile not found
- Processes anyway without profile

## Success Criteria

All tests should pass with:
- ✅ Correct file organization
- ✅ Metadata properly extracted and stored
- ✅ Cost tracking functional with realistic values
- ✅ Cost reporting commands working
- ✅ Profile auto-detection working
- ✅ Override settings working
- ✅ Error handling graceful

## Troubleshooting

### Database Schema Issues

```bash
# Re-run migrations
python scripts/migrate_add_newsletter_profiles.py
python scripts/migrate_add_cost_tracking.py

# Verify schema
sqlite3 data/newsletter_podcast_local.db ".schema episodes"
sqlite3 data/newsletter_podcast_local.db ".schema newsletters"
```

### Missing Configuration

```bash
# Check configuration exists
ls -l config/newsletters.yaml

# If missing, copy template
cp config/newsletters.yaml.template config/newsletters.yaml
```

### Cost Tracking Not Working

```bash
# Check episode has cost data
sqlite3 data/newsletter_podcast_local.db "
SELECT * FROM episodes WHERE id = 'episode-id';"

# Check logs for errors
tail -50 logs/app_dev.log | grep -i cost
```

## Performance Benchmarks

Expected processing times and costs (OpenAI GPT-4o-mini + Unreal Speech):

| Newsletter Size | Processing Time | LLM Cost | TTS Cost | Total Cost |
|----------------|-----------------|----------|----------|------------|
| Short (500 words) | 30-60s | $0.0001-0.0003 | $0.001-0.003 | $0.001-0.004 |
| Medium (1500 words) | 60-120s | $0.0003-0.0008 | $0.003-0.008 | $0.004-0.010 |
| Long (3500 words) | 120-240s | $0.0008-0.0020 | $0.008-0.020 | $0.010-0.025 |

*Costs based on December 2024 pricing. Actual costs may vary.*

## Next Steps After Testing

Once all tests pass:
1. Review `DEVELOPMENT.md` for Phase 2 implementation plan
2. Consider implementing RSS feed parsing (Phase 2)
3. Set up scheduled processing for automated newsletter conversion
4. Implement playlist generation (Phase 3)

