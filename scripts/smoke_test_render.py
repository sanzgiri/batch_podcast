#!/usr/bin/env python3
"""
End-to-end smoke test for the new TTS pipeline.

Runs the full pipeline against a hardcoded sample of AI-newsletter content:
  raw text  -->  LLM (Ollama, dialogue mode)  -->  Kokoro TTS (podcast preset)
              -->  ai_tech pronunciations + loudnorm  -->  MP3

Writes the result to data/audio/smoke-test/smoke-test.mp3 and opens it.

Usage:
    python scripts/smoke_test_render.py                  # default: dialogue + ai_tech
    python scripts/smoke_test_render.py --mode monologue # single-voice version
    python scripts/smoke_test_render.py --no-open        # don't auto-open the MP3
    python scripts/smoke_test_render.py --skip-llm       # use canned script (faster iteration)
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path so we can import src.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.lib.config import get_config
from src.lib.logging import get_logger
from src.services.llm_summarizer import LLMSummarizer
from src.services.tts_generator import TTSGenerator

logger = get_logger(__name__)


SAMPLE_NEWSLETTER = """\
The Batch — Issue 999 — Smoke Test

NVIDIA released a new GPU that doubles inference throughput for large language
models. The H300 features 192 GB of HBM3e memory and 4 TB/s of bandwidth,
making it well-suited for serving 70B-parameter models like Llama-3.1.

Meanwhile, Anthropic published research from Sutskever's former collaborators
showing that mechanistic interpretability scales with model size. Karpathy
commented on X that the results are "the most exciting interpretability
paper of the year." DeepSeek also released V3, a 671B-parameter MoE model
that matches GPT-4o on many benchmarks at 1/10th the API cost.

In policy news, the EU AI Act's general-purpose AI provisions go into effect
next month. Companies deploying systems above 10^25 FLOPS must register with
the AI Office and submit safety evaluations. Hassabis at DeepMind expressed
cautious support, while Andreessen called the regulation "premature."

Finally, RAG pipelines continue to dominate enterprise deployments. A new
benchmark from Stanford shows that hybrid retrieval (BM25 + dense embeddings)
outperforms pure vector search by 12% on average across 50 enterprise QA
datasets.
"""

# Pre-generated dialogue script for --skip-llm mode (saves ~30s when iterating
# on TTS-only tuning).
CANNED_DIALOGUE_SCRIPT = """\
Host: Welcome back to The Batch, your weekly look at the world of AI. \
I'm here today to walk you through some of the biggest stories shaping \
our field this week. There's quite a bit to unpack, so let's dive right in.

Guest: Thanks for having me. I'm excited to chat about this week's news \
because it really does span the full stack, from hardware all the way up \
to policy.

Host: Let's start with the hardware. NVIDIA dropped a new GPU called the \
H300. What makes it different from what we've seen before?

Guest: The H300 is a serious upgrade. It comes with 192 gigabytes of HBM3e \
memory and 4 terabytes per second of bandwidth. That doubles the inference \
throughput for large language models compared to the previous generation. \
For anyone serving 70 billion parameter models like Llama 3.1, this is a \
game changer.

Host: Speaking of cutting-edge research, Anthropic published an interesting \
paper this week. What's the headline?

Guest: It comes out of work by former collaborators of Sutskever, and it \
shows that mechanistic interpretability actually scales with model size. \
Karpathy called it the most exciting interpretability paper of the year on X. \
The implications for AI safety research are significant.

Host: And DeepSeek made some noise as well, right?

Guest: Yes, DeepSeek released V3, which is a 671 billion parameter mixture \
of experts model. It matches GPT-4o on many benchmarks, but here's the \
kicker, the API cost is roughly one tenth of GPT-4o. That's going to put \
real pricing pressure on the frontier labs.

Host: Let's switch gears to policy. The EU AI Act is finally kicking in.

Guest: Right, the general-purpose AI provisions go into effect next month. \
Any company deploying systems above 10 to the 25 FLOPS has to register \
with the AI Office and submit safety evaluations. Hassabis at DeepMind \
expressed cautious support. Andreessen, on the other hand, called the \
regulation premature.

Host: Finally, what's new on the deployment side?

Guest: RAG pipelines continue to dominate enterprise AI. Stanford published \
a benchmark showing that hybrid retrieval, that's BM25 combined with dense \
embeddings, outperforms pure vector search by 12 percent on average across \
50 enterprise QA datasets. So if you're building enterprise RAG, hybrid \
retrieval is the way to go.

Host: Great roundup. That's a wrap for this week's Batch. Thanks for joining.

Guest: Thanks for having me.
"""


async def run_smoke_test(mode: str, skip_llm: bool, open_when_done: bool) -> Path:
    config = get_config()

    print("=" * 70)
    print("BATCH PODCAST — SMOKE TEST RENDER")
    print("=" * 70)
    print(f"  LLM provider: {config.llm.provider}")
    print(f"  LLM model:    {config.llm.ollama.model}")
    print(f"  TTS provider: {config.tts.provider}")
    print(f"  TTS voice:    {config.tts.kokoro_tts.voice}")
    print(f"  Mode:         {mode}")
    print(f"  Skip LLM:     {skip_llm}")
    print("=" * 70)

    # --- 1. LLM ----------------------------------------------------------
    if skip_llm and mode == "dialogue":
        print("\n[1/2] Using canned dialogue script (--skip-llm)")
        script_text = CANNED_DIALOGUE_SCRIPT
        print(f"      Script length: {len(script_text)} chars")
    else:
        print(f"\n[1/2] Generating {mode} script via {config.llm.ollama.model}...")
        t0 = time.time()
        async with LLMSummarizer(config) as llm:
            response = await llm.summarize_newsletter(
                content=SAMPLE_NEWSLETTER,
                title="The Batch — Issue 999 — Smoke Test",
                style="conversational",
                target_length="medium",
                mode=mode,
            )
        elapsed = time.time() - t0
        script_text = response.summary
        print(f"      LLM done in {elapsed:.1f}s")
        print(f"      Script length: {len(script_text)} chars")
        if hasattr(response, "input_tokens") and response.input_tokens:
            print(f"      Tokens: in={response.input_tokens} out={response.output_tokens}")
        print()
        print("--- LLM OUTPUT (first 800 chars) ---")
        print(script_text[:800] + ("..." if len(script_text) > 800 else ""))
        print("--- end LLM output ---")

    # --- 2. TTS ----------------------------------------------------------
    output_dir = Path("data/audio/smoke-test")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"smoke-test-{mode}.mp3"
    if output_path.exists():
        output_path.unlink()

    if mode == "dialogue":
        tts_kwargs = dict(
            mode="dialogue",
            preset="podcast_two_host",
            pronunciations="ai_tech",
            target_lufs=-16.0,
            dialogue_speed=0.95,
        )
    else:
        tts_kwargs = dict(
            mode="text",
            voice="af_heart",
            pronunciations="ai_tech",
            target_lufs=-16.0,
            speed=1.0,
        )

    print(f"\n[2/2] Rendering audio: preset/voice = "
          f"{tts_kwargs.get('preset') or tts_kwargs.get('voice')}, "
          f"pronunciations=ai_tech")
    print("      (first run will download Kokoro voicepacks — be patient)")
    t0 = time.time()
    async with TTSGenerator(config) as tts:
        tts_response = await tts.generate_speech(
            text=script_text,
            output_format="mp3",
            output_path=str(output_path),
            **tts_kwargs,
        )
    elapsed = time.time() - t0
    print(f"      TTS done in {elapsed:.1f}s")
    print(f"      Audio file: {tts_response.audio_file_path}")
    print(f"      Duration:   {tts_response.duration_seconds:.1f}s "
          f"(~{tts_response.duration_seconds/60:.1f} min)")
    print(f"      Size:       {tts_response.file_size_bytes/1024:.0f} KB")

    if not Path(tts_response.audio_file_path).exists():
        print(f"\n[FAIL] Output file does not exist: {tts_response.audio_file_path}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("SUCCESS")
    print(f"  Listen to: {tts_response.audio_file_path}")
    print("=" * 70)

    if open_when_done and shutil.which("open"):
        subprocess.run(["open", tts_response.audio_file_path], check=False)

    return Path(tts_response.audio_file_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["dialogue", "monologue"], default="dialogue")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Use canned dialogue script (skips LLM, only valid with dialogue mode)")
    parser.add_argument("--no-open", action="store_true",
                        help="Do not auto-open the MP3 when done")
    args = parser.parse_args()

    if args.skip_llm and args.mode != "dialogue":
        print("Warning: --skip-llm only works with --mode dialogue; ignoring.", file=sys.stderr)
        args.skip_llm = False

    try:
        asyncio.run(run_smoke_test(
            mode=args.mode,
            skip_llm=args.skip_llm,
            open_when_done=not args.no_open,
        ))
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
