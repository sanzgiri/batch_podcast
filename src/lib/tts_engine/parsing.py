"""Parsers — markdown books, plain text, Speaker:line dialogue.

All parsers produce a list[Chapter] of Block objects with silence injected
at structural boundaries (paragraphs, headings, quotes, turns).
"""

from __future__ import annotations

import re
from typing import Optional

from src.lib.tts_engine.blocks import Block, Chapter
from src.lib.tts_engine.text_processing import clean_inline


# ---------------------------------------------------------------------------
# Markdown -> Chapters (book mode)
# ---------------------------------------------------------------------------


def parse_markdown_book(md: str) -> list[Chapter]:
    """Parse markdown into chapters split at level-1 (#) headings."""
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    md = re.sub(r"(?s)\A---\n.*?\n---\n", "", md)
    md = re.sub(r"(?ms)^```.*?^```", "", md)
    md = re.sub(r"(?s)<!--.*?-->", "", md)

    lines = md.split("\n")
    chapters: list[Chapter] = []
    current: Optional[Chapter] = None
    para_buf: list[str] = []
    quote_buf: list[str] = []
    list_buf: list[str] = []

    has_h1 = any(re.match(r"^#\s+", ln) for ln in lines)

    def flush_para() -> None:
        nonlocal para_buf
        if para_buf and current is not None:
            t = clean_inline(" ".join(para_buf).strip())
            if t:
                current.blocks.append(Block("para", t))
            para_buf = []

    def flush_quote() -> None:
        nonlocal quote_buf
        if quote_buf and current is not None:
            t = clean_inline(" ".join(quote_buf).strip())
            if t:
                current.blocks.append(Block("silence", seconds=0.6))
                current.blocks.append(Block("quote", t))
                current.blocks.append(Block("silence", seconds=0.6))
            quote_buf = []

    def flush_list() -> None:
        nonlocal list_buf
        if list_buf and current is not None:
            items = [clean_inline(it) for it in list_buf if clean_inline(it)]
            if items:
                joined = " — ".join(items) + "."
                current.blocks.append(Block("list", joined))
            list_buf = []

    def flush_all() -> None:
        flush_para()
        flush_quote()
        flush_list()

    for ln in lines:
        m1 = re.match(r"^#\s+(.*?)\s*#*\s*$", ln) if has_h1 else None
        if m1:
            flush_all()
            current = Chapter(len(chapters) + 1, clean_inline(m1.group(1)))
            chapters.append(current)
            continue

        if current is None:
            current = Chapter(1, "Introduction")
            chapters.append(current)

        m2 = re.match(r"^##\s+(.*?)\s*#*\s*$", ln)
        if m2:
            flush_all()
            t = clean_inline(m2.group(1))
            if t:
                current.blocks.append(Block("silence", seconds=1.2))
                current.blocks.append(Block("heading", t.rstrip(".") + "."))
                current.blocks.append(Block("silence", seconds=0.5))
            continue

        m3 = re.match(r"^#{3,6}\s+(.*?)\s*#*\s*$", ln)
        if m3:
            flush_all()
            t = clean_inline(m3.group(1))
            if t:
                current.blocks.append(Block("silence", seconds=0.7))
                current.blocks.append(Block("para", t.rstrip(".") + "."))
                current.blocks.append(Block("silence", seconds=0.3))
            continue

        if re.match(r"^\s*([-*_])(?:\s*\1){2,}\s*$", ln):
            flush_all()
            current.blocks.append(Block("silence", seconds=1.5))
            continue

        if re.match(r"^\s*\|.*\|\s*$", ln):
            flush_all()
            continue

        if re.match(r"^\s{0,3}>", ln):
            flush_para()
            flush_list()
            quote_buf.append(re.sub(r"^\s{0,3}>\s?", "", ln))
            continue

        if re.match(r"^\s*([-*+]|\d+[.)])\s+", ln):
            flush_para()
            flush_quote()
            list_buf.append(re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", ln))
            continue

        if not ln.strip():
            flush_all()
            continue

        if quote_buf:
            quote_buf.append(ln)
        elif list_buf:
            list_buf[-1] = list_buf[-1] + " " + ln.strip()
        else:
            para_buf.append(ln)

    flush_all()
    return chapters


# ---------------------------------------------------------------------------
# Plain text mode (single chapter, paragraph-broken)
# ---------------------------------------------------------------------------


def parse_text(text: str) -> list[Chapter]:
    """Parse plain text or markdown into a single chapter with paragraph blocks."""
    text = re.sub(r"(?ms)^```.*?^```", "", text)
    paragraphs = re.split(r"\n\s*\n", text)
    blocks: list[Block] = []
    for p in paragraphs:
        s = clean_inline(p.strip())
        if s:
            blocks.append(Block("para", s))
            blocks.append(Block("silence", seconds=0.4))
    return [Chapter(1, "Audio", blocks)]


# ---------------------------------------------------------------------------
# Dialogue mode — "Speaker: line" turns mapped to two voices
# ---------------------------------------------------------------------------

DIALOGUE_LINE = re.compile(r"^([A-Za-z][\w\s\-]{0,30}?):\s*(.+)$")


def parse_dialogue(text: str) -> tuple[list[Chapter], dict[str, str]]:
    """Parse alternating-speaker dialogue.

    Returns:
        (chapters, speaker_keys) where speaker_keys maps speaker name
        strings in the input to 'A' / 'B' (cycling).
    """
    text = re.sub(r"(?ms)^```.*?^```", "", text)
    lines = text.split("\n")
    blocks: list[Block] = []
    speaker_keys: dict[str, str] = {}
    speaker_order: list[str] = []
    current_speaker: Optional[str] = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, current_speaker
        if current_speaker and buf:
            t = clean_inline(" ".join(buf).strip())
            if t:
                blocks.append(
                    Block("turn", t, speaker=speaker_keys[current_speaker])
                )
                blocks.append(Block("silence", seconds=0.45))
        buf = []

    for ln in lines:
        m = DIALOGUE_LINE.match(ln)
        if m:
            flush()
            name = m.group(1).strip()
            content = m.group(2).strip()
            if name not in speaker_keys:
                key = "A" if len(speaker_order) % 2 == 0 else "B"
                speaker_keys[name] = key
                speaker_order.append(name)
            current_speaker = name
            buf.append(content)
        elif ln.strip() == "":
            flush()
            current_speaker = None
        else:
            if current_speaker:
                buf.append(ln.strip())
    flush()
    return [Chapter(1, "Dialogue", blocks)], speaker_keys
