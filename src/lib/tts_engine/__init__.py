"""
TTS Engine — Kokoro-based audio rendering pipeline.

Adapted from text2audio (https://github.com/sanzgiri/text2audio) and integrated
into the batch_podcast Kokoro client. Provides:

    • Voice blending (weighted tensor mixes of voicepacks)
    • Programmatic silence insertion between paragraphs / sections / quotes
    • Pronunciation overrides + abbreviation expansion
    • Dialogue mode (alternating voices on "Speaker: line" turns)
    • ffmpeg loudnorm (broadcast standard)
    • Preset loading (presets/*.json) + pronunciation dicts (pronunciations/*.json)
"""

from src.lib.tts_engine.blocks import Block, Chapter
from src.lib.tts_engine.encoding import (
    build_m4b,
    encode_mp3,
    loudnorm,
    write_wav,
)
from src.lib.tts_engine.parsing import (
    parse_dialogue,
    parse_markdown_book,
    parse_text,
)
from src.lib.tts_engine.presets import (
    load_preset,
    load_pronunciations,
    list_presets,
    list_pronunciation_dicts,
)
from src.lib.tts_engine.rendering import (
    SAMPLE_RATE,
    load_blended_voice,
    parse_voice_spec,
    render_chapter_blocks,
    silence,
)
from src.lib.tts_engine.text_processing import (
    ABBREVIATIONS,
    apply_pronunciations,
    clean_inline,
    expand_abbreviations,
)

__all__ = [
    "ABBREVIATIONS",
    "Block",
    "Chapter",
    "SAMPLE_RATE",
    "apply_pronunciations",
    "build_m4b",
    "clean_inline",
    "encode_mp3",
    "expand_abbreviations",
    "list_presets",
    "list_pronunciation_dicts",
    "load_blended_voice",
    "load_preset",
    "load_pronunciations",
    "loudnorm",
    "parse_dialogue",
    "parse_markdown_book",
    "parse_text",
    "parse_voice_spec",
    "render_chapter_blocks",
    "silence",
    "write_wav",
]
