"""ffmpeg-based encoding helpers: loudnorm, MP3, M4B with chapter markers."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from src.lib.tts_engine.blocks import Chapter


def run(cmd: list[str]) -> None:
    """Run a subprocess command and raise on non-zero exit."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stdout)
        sys.stderr.write(p.stderr)
        raise RuntimeError(f"command failed: {' '.join(cmd[:3])}")


def write_wav(path: Path, audio: Any, sample_rate: int) -> None:
    """Write a mono WAV from float samples in [-1.0, 1.0].

    Accepts torch tensors (auto-detached), numpy arrays, or plain lists.
    """
    if hasattr(audio, "detach"):
        audio = audio.detach().cpu().numpy()
    audio_np = np.asarray(audio, dtype=np.float32)
    if audio_np.size == 0:
        raise ValueError("Empty audio buffer")
    audio_np = np.clip(audio_np, -1.0, 1.0)
    audio_int16 = (audio_np * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())


def loudnorm(in_wav: str | Path, out_wav: str | Path, target_lufs: float = -16.0) -> None:
    """Apply ffmpeg loudnorm filter to normalize loudness.

    Defaults:
        I  = -16 LUFS (podcast standard; use -18 for audiobook)
        TP =  -2 dBFS true peak
        LRA= 11 LU loudness range
    """
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(in_wav),
            "-af",
            f"loudnorm=I={target_lufs}:TP=-2:LRA=11",
            str(out_wav),
        ]
    )


def duration_seconds(wav_path: str | Path) -> float:
    """Return duration of a WAV file in seconds."""
    info = sf.info(str(wav_path))
    return info.frames / info.samplerate


def encode_mp3(in_wav: str | Path, out_path: str | Path) -> None:
    """Encode WAV -> MP3 (libmp3lame, VBR quality 2 = high)."""
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(in_wav),
            "-codec:a",
            "libmp3lame",
            "-qscale:a",
            "2",
            str(out_path),
        ]
    )


def build_m4b(
    chapter_wavs: list[tuple[Chapter, str]],
    out_path: str | Path,
    title: str,
    author: str,
) -> None:
    """Build an M4B (AAC in MP4 container) with chapter markers.

    chapter_wavs: list of (Chapter, wav_path) tuples in playback order.
    """
    workdir = tempfile.mkdtemp(prefix="t2a_m4b.")
    try:
        concat_list = os.path.join(workdir, "list.txt")
        with open(concat_list, "w") as fh:
            for _, w in chapter_wavs:
                fh.write(f"file '{os.path.abspath(w)}'\n")
        meta_path = os.path.join(workdir, "meta.txt")
        cursor = 0.0
        with open(meta_path, "w") as fh:
            fh.write(";FFMETADATA1\n")
            fh.write(f"title={title}\n")
            fh.write(f"artist={author}\n")
            fh.write(f"album={title}\n")
            for ch, w in chapter_wavs:
                d = duration_seconds(w)
                fh.write("[CHAPTER]\nTIMEBASE=1/1000\n")
                fh.write(f"START={int(cursor * 1000)}\nEND={int((cursor + d) * 1000)}\n")
                fh.write(f"title=Chapter {ch.number}: {ch.title}\n")
                cursor += d
        big = os.path.join(workdir, "all.wav")
        run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_list,
                "-c",
                "copy",
                big,
            ]
        )
        run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                big,
                "-i",
                meta_path,
                "-map_metadata",
                "1",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                "-f",
                "ipod",
                str(out_path),
            ]
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
