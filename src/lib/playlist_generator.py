"""M3U / M3U8 playlist generator.

Writes per-newsletter playlists that group all episodes of a single podcast
into a single playable list. Plays directly in VLC, Apple Music, iTunes,
foobar2000, etc.

Two formats supported:
  M3U   (ASCII, legacy)
  M3U8  (UTF-8, modern; recommended)

We use the extended M3U format (#EXTM3U) so player UIs show episode titles
instead of just filenames.

Example output:

    #EXTM3U
    #EXTINF:196,The Batch - Issue 282
    ../audio/the-batch/the-batch-2026-06-14-issue-282.mp3
    #EXTINF:208,The Batch - Issue 283
    ../audio/the-batch/the-batch-2026-06-14-issue-283.mp3
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PlaylistEntry:
    """A single entry in a playlist."""

    audio_path: Path
    title: str
    duration_seconds: int = -1  # -1 = unknown


class PlaylistGenerator:
    """Generate M3U/M3U8 playlists for podcast episodes."""

    @staticmethod
    def write(
        entries: Iterable[PlaylistEntry],
        output_path: Path,
        *,
        relative_to: Path | None = None,
        format: str = "m3u8",
    ) -> int:
        """Write a playlist file from the given entries.

        Args:
            entries: Iterable of PlaylistEntry objects (ordered).
            output_path: Where to write the .m3u or .m3u8 file. Parent dir
                created if missing.
            relative_to: If given, audio paths are written relative to this
                directory. If None, absolute paths are written. Most podcast
                apps prefer relative paths so playlists are portable.
            format: 'm3u' (ASCII) or 'm3u8' (UTF-8). M3U8 is recommended.

        Returns:
            The number of entries written.
        """
        if format not in {"m3u", "m3u8"}:
            raise ValueError(f"format must be 'm3u' or 'm3u8', got {format!r}")

        entries_list = list(entries)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = ["#EXTM3U"]
        for entry in entries_list:
            audio = entry.audio_path
            if relative_to is not None:
                try:
                    audio = Path(_relpath(audio, relative_to))
                except ValueError:
                    # Different drives on Windows etc; fall back to absolute.
                    audio = audio.resolve()

            # #EXTINF:<duration>,<title>
            lines.append(f"#EXTINF:{entry.duration_seconds},{entry.title}")
            lines.append(str(audio))

        encoding = "utf-8" if format == "m3u8" else "ascii"
        # Strip non-ASCII for M3U format
        if format == "m3u":
            lines = [line.encode("ascii", "replace").decode("ascii") for line in lines]

        output_path.write_text("\n".join(lines) + "\n", encoding=encoding)
        return len(entries_list)


def _relpath(target: Path, start: Path) -> str:
    """Return a POSIX-style relative path from `start` to `target`."""
    import os

    rel = os.path.relpath(str(target), start=str(start))
    # Always use forward slashes in playlists for cross-platform portability
    return rel.replace("\\", "/")
