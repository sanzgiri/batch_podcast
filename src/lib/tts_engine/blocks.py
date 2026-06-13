"""Block model — universal across input modes (text / book / dialogue)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Block:
    """A unit of content to render.

    kind:
        'para'     — regular paragraph (primary voice)
        'quote'    — blockquote (quote voice if set, else primary)
        'silence'  — N seconds of silence (uses .seconds)
        'heading'  — section heading (slightly slower primary voice)
        'list'     — list flattened to prose with em-dashes
        'turn'     — dialogue turn (uses .speaker = 'A' or 'B')
    """

    kind: str
    text: str = ""
    seconds: float = 0.0
    speaker: str = ""  # 'A' or 'B' for dialogue turns


@dataclass
class Chapter:
    """A logical chapter — used for book mode (chapters) and text/dialogue
    modes (single 'chapter' wrapping all blocks)."""

    number: int
    title: str
    blocks: list[Block] = field(default_factory=list)
