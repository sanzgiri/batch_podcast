"""Voice loading, blending, and chapter-block rendering with Kokoro."""

from __future__ import annotations

from typing import Any

import numpy as np

from src.lib.tts_engine.blocks import Block

SAMPLE_RATE = 24000


# ---------------------------------------------------------------------------
# Voice spec parsing + blending
# ---------------------------------------------------------------------------


def parse_voice_spec(spec: str) -> list[tuple[str, float]]:
    """Parse a voice spec like 'af_heart:0.7,af_nicole:0.3' into weighted tuples.

    Weights are normalized to sum=1.0. Single names default to weight 1.0.
    Returns [] for empty/None/'none' specs.
    """
    if not spec or spec.lower() == "none":
        return []
    out: list[tuple[str, float]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            n, w = part.split(":", 1)
            out.append((n.strip(), float(w)))
        else:
            out.append((part, 1.0))
    tot = sum(w for _, w in out) or 1.0
    return [(n, w / tot) for n, w in out]


def load_blended_voice(pipeline: Any, spec: str) -> Any | None:
    """Load and blend voicepacks per spec.

    pipeline must be a KPipeline instance with load_voice().
    Returns a single tensor (single voice) or weighted sum (blend), or None.
    """
    parts = parse_voice_spec(spec)
    if not parts:
        return None
    if len(parts) == 1 and abs(parts[0][1] - 1.0) < 1e-6:
        return pipeline.load_voice(parts[0][0])
    blended = None
    for name, w in parts:
        v = pipeline.load_voice(name)
        blended = v * w if blended is None else blended + v * w
    return blended


# ---------------------------------------------------------------------------
# Audio rendering
# ---------------------------------------------------------------------------


def silence(seconds: float) -> np.ndarray:
    """Generate N seconds of silence at SAMPLE_RATE."""
    return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.float32)


def render_text(pipeline: Any, text: str, voice: Any, speed: float) -> np.ndarray:
    """Render a single string through Kokoro and return float32 mono samples."""
    pieces: list[np.ndarray] = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        a = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
        pieces.append(a.astype(np.float32))
    return np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)


def render_chapter_blocks(
    pipeline: Any,
    blocks: list[Block],
    voices: dict[str, Any],
    speed: float,
    quote_speed: float,
    dialogue_speed: float,
) -> np.ndarray:
    """Render a list of Blocks into a single concatenated waveform.

    voices: dict with keys 'primary', 'quote' (optional), 'A', 'B' (dialogue mode).
    """
    parts: list[np.ndarray] = []
    for b in blocks:
        if b.kind == "silence":
            parts.append(silence(b.seconds))
        elif b.kind == "quote" and voices.get("quote") is not None:
            parts.append(render_text(pipeline, b.text, voices["quote"], quote_speed))
        elif b.kind == "turn":
            v = voices.get(b.speaker, voices.get("primary"))
            parts.append(render_text(pipeline, b.text, v, dialogue_speed))
        else:
            # 'para', 'heading', 'list', or fallback
            sp = max(0.78, speed - 0.05) if b.kind == "heading" else speed
            parts.append(render_text(pipeline, b.text, voices["primary"], sp))
            parts.append(silence(0.4))
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
