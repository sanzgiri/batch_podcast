"""
Text-to-Speech Generator Service for Newsletter Podcast Generator.

Uses the local Kokoro TTS backend via src.lib.tts_engine, which provides
text2audio-style realism tricks:

    • Voice blending (weighted tensor mixes of voicepacks)
    • Programmatic silence injection between paragraphs / sections / quotes
    • Pronunciation overrides + abbreviation expansion
    • Dialogue mode (alternating voices on "Speaker: line" turns)
    • ffmpeg loudnorm (broadcast standard)
    • Preset support (podcast_two_host, audiobook_warm, etc.)
"""

import asyncio
import shutil
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Any

from src.lib.config import Config
from src.lib.exceptions import ServiceError, TTSError, ValidationError
from src.lib.logging import get_logger
from src.lib.tts_engine import (
    SAMPLE_RATE,
    apply_pronunciations,
    encode_mp3,
    expand_abbreviations,
    list_presets,
    list_pronunciation_dicts,
    load_blended_voice,
    load_preset,
    load_pronunciations,
    loudnorm,
    parse_dialogue,
    parse_text,
    render_chapter_blocks,
    write_wav,
)
from src.lib.tts_engine.blocks import Chapter
from src.lib.utils import ensure_directory, generate_uuid, get_audio_duration, get_file_size

logger = get_logger(__name__)


class TTSProvider(StrEnum):
    """Supported TTS providers."""

    KOKORO_TTS = "kokoro_tts"


@dataclass
class TTSRequest:
    """Request for text-to-speech conversion.

    Most fields are optional and fall through to the client/config defaults.
    """

    text: str
    voice: str | None = None  # primary voice spec, e.g. "af_heart" or "af_heart:0.7,af_nicole:0.3"
    quote_voice: str | None = None  # secondary voice for blockquotes ("none" disables)
    voice_a: str | None = None  # dialogue mode: first speaker
    voice_b: str | None = None  # dialogue mode: second speaker
    speed: float = 1.0
    quote_speed: float = 0.85
    dialogue_speed: float = 0.95
    pitch: float = 1.0  # accepted for API compatibility; Kokoro doesn't use it
    output_format: str = "mp3"  # mp3 or wav
    quality: str = "standard"  # standard or high
    mode: str = "text"  # text | dialogue
    preset: str | None = None  # name of bundled preset (overrides voice fields if their defaults)
    pronunciations: str | None = None  # name of bundled dict OR file path
    expand_abbrev: bool = True
    target_lufs: float = -16.0  # -16 podcast / -18 audiobook
    output_path: str | None = None  # full output file path (overrides auto-naming)
    extra_pronunciations: dict[str, str] = field(default_factory=dict)


@dataclass
class TTSResponse:
    """Response from text-to-speech conversion."""

    audio_file_path: str
    duration_seconds: int
    file_size_bytes: int
    provider: str
    voice: str
    processing_time: float
    format: str
    characters: int = 0  # for cost tracking
    mode: str = "text"


class BaseTTSClient(ABC):
    """Abstract base class for TTS clients."""

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Convert text to speech."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the TTS service is available."""
        raise NotImplementedError

    @abstractmethod
    def get_available_voices(self) -> list[str]:
        """Get list of available voices."""
        raise NotImplementedError


class KokoroTTSClient(BaseTTSClient):
    """Kokoro TTS client using the text2audio-style pipeline."""

    # Curated set; Kokoro ships a few dozen, these are the ones used by presets.
    KNOWN_VOICES = [
        "af_heart",
        "af_bella",
        "af_nicole",
        "af_sarah",
        "af_kore",
        "am_michael",
        "am_adam",
        "am_fenrir",
        "bm_george",
        "bm_fable",
    ]

    def __init__(self, config: Config, output_dir: str):
        self.config = config
        self.default_voice = config.tts.kokoro_tts.voice
        self.default_lang_code = config.tts.kokoro_tts.lang_code
        self.default_speed = config.tts.kokoro_tts.speed
        self.output_dir = Path(output_dir)

        self.pipeline: Any | None = None
        self.sample_rate = SAMPLE_RATE

    async def __aenter__(self) -> "KokoroTTSClient":
        await asyncio.to_thread(self._init_pipeline)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.pipeline = None

    # ------------------------------------------------------------------ init

    def _init_pipeline(self) -> None:
        if self.pipeline is not None:
            return
        try:
            from kokoro import KPipeline  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "Kokoro is not installed. Install with: "
                "pip install 'kokoro @ git+https://github.com/hexgrad/kokoro'"
            ) from exc

        try:
            self.pipeline = KPipeline(lang_code=self.default_lang_code)
        except TypeError:
            self.pipeline = KPipeline()
        logger.info(f"Kokoro pipeline initialized (lang_code={self.default_lang_code})")

    # ------------------------------------------------------------------ public

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech using Kokoro TTS + the text2audio pipeline."""
        if not self.pipeline:
            raise ServiceError("Kokoro TTS client must be used as async context manager")

        logger.info(
            f"Synthesizing speech with Kokoro: mode={request.mode}, "
            f"{len(request.text)} chars, preset={request.preset}"
        )

        try:
            return await asyncio.to_thread(self._synthesize_sync, request)
        except Exception as exc:
            logger.error(f"Kokoro TTS synthesis failed: {exc}")
            raise TTSError(f"Kokoro TTS synthesis failed: {exc}") from exc

    async def health_check(self) -> bool:
        return self.pipeline is not None

    def get_available_voices(self) -> list[str]:
        return list(self.KNOWN_VOICES)

    # ---------------------------------------------------------------- internal

    def _resolve_preset(self, request: TTSRequest) -> TTSRequest:
        """Apply preset values to request fields that are still at defaults."""
        if not request.preset:
            return request

        try:
            preset = load_preset(request.preset)
        except FileNotFoundError as exc:
            raise ValidationError(str(exc)) from exc

        # Map preset keys (hyphenated, as used by text2audio) onto request fields
        key_map = {
            "voice": "voice",
            "quote-voice": "quote_voice",
            "voice-a": "voice_a",
            "voice-b": "voice_b",
            "speed": "speed",
            "quote-speed": "quote_speed",
            "dialogue-speed": "dialogue_speed",
        }
        defaults = TTSRequest(text="")  # for comparing against defaults
        for pkey, field_name in key_map.items():
            if pkey not in preset:
                continue
            current = getattr(request, field_name)
            default = getattr(defaults, field_name)
            if current == default or current is None:
                setattr(request, field_name, preset[pkey])
        return request

    def _build_pron_dict(self, request: TTSRequest) -> dict[str, str]:
        """Combine named/bundled pronunciation dict with any extras."""
        pron: dict[str, str] = {}
        if request.pronunciations:
            try:
                pron.update(load_pronunciations(request.pronunciations))
            except FileNotFoundError as exc:
                raise ValidationError(str(exc)) from exc
        if request.extra_pronunciations:
            pron.update(request.extra_pronunciations)
        return pron

    def _preprocess_text(self, text: str, request: TTSRequest, pron: dict[str, str]) -> str:
        if request.expand_abbrev:
            text = expand_abbreviations(text)
        text = apply_pronunciations(text, pron)
        return text

    def _build_voices(self, request: TTSRequest) -> dict[str, Any]:
        """Load and blend voices per request."""
        primary_spec = request.voice or self.default_voice
        voices: dict[str, Any] = {
            "primary": load_blended_voice(self.pipeline, primary_spec),
        }
        if request.quote_voice and request.quote_voice.lower() != "none":
            voices["quote"] = load_blended_voice(self.pipeline, request.quote_voice)
        if request.mode == "dialogue":
            voice_a = request.voice_a or primary_spec
            voice_b = request.voice_b or "am_michael"
            voices["A"] = load_blended_voice(self.pipeline, voice_a)
            voices["B"] = load_blended_voice(self.pipeline, voice_b)
            logger.info(f"[kokoro] dialogue voices: A={voice_a}  B={voice_b}")
        else:
            logger.info(
                f"[kokoro] voice={primary_spec}  "
                f"quote={request.quote_voice or 'none'}  speed={request.speed}"
            )
        return voices

    def _build_blocks_and_pre(
        self, text: str, request: TTSRequest, pron: dict[str, str]
    ) -> list[Chapter]:
        """Parse text into blocks based on mode, applying pre-processing."""
        if request.mode == "dialogue":
            chapters, speaker_keys = parse_dialogue(text)
            logger.info(f"[parse] dialogue speakers: {speaker_keys}")
        elif request.mode == "text":
            chapters = parse_text(text)
        else:
            raise ValidationError(f"Unsupported TTS mode: {request.mode}")

        # Apply text-level preprocessing per block
        for ch in chapters:
            for b in ch.blocks:
                if b.text:
                    if request.expand_abbrev:
                        b.text = expand_abbreviations(b.text)
                    b.text = apply_pronunciations(b.text, pron)
        return chapters

    def _output_path_for(self, request: TTSRequest) -> Path:
        if request.output_path:
            return Path(request.output_path)
        ensure_directory(self.output_dir)
        return self.output_dir / f"tts_{generate_uuid()}.{request.output_format}"

    def _synthesize_sync(self, request: TTSRequest) -> TTSResponse:
        start_time = time.time()

        # 1. Resolve preset (mutates request fields that are at defaults)
        request = self._resolve_preset(request)

        # 2. Build pronunciation dict
        pron = self._build_pron_dict(request)

        # 3. Parse + preprocess text into blocks
        chapters = self._build_blocks_and_pre(request.text, request, pron)
        all_blocks = [b for ch in chapters for b in ch.blocks]
        if not all_blocks:
            raise TTSError("No renderable content after parsing")
        n_para = sum(
            1 for b in all_blocks if b.kind in {"para", "turn", "quote", "heading", "list"}
        )
        logger.info(
            f"[parse] mode={request.mode}  blocks: {len(all_blocks)}  speech_units: {n_para}"
        )

        # 4. Load voices
        voices = self._build_voices(request)

        # 5. Render audio
        speed = request.speed if request.speed not in (None, 0) else self.default_speed
        audio = render_chapter_blocks(
            self.pipeline,
            all_blocks,
            voices,
            speed=speed,
            quote_speed=request.quote_speed,
            dialogue_speed=request.dialogue_speed,
        )
        if audio.size == 0:
            raise TTSError("Kokoro produced no audio samples")

        # 6. Write WAV → loudnorm → encode
        tmpdir = Path(tempfile.mkdtemp(prefix="tts_"))
        try:
            raw_wav = tmpdir / "raw.wav"
            norm_wav = tmpdir / "norm.wav"
            write_wav(raw_wav, audio, self.sample_rate)
            try:
                loudnorm(raw_wav, norm_wav, target_lufs=request.target_lufs)
            except RuntimeError as exc:
                # Don't fail render if ffmpeg loudnorm itself fails — fall back to raw.
                logger.warning(f"loudnorm failed, using raw wav: {exc}")
                shutil.copy(raw_wav, norm_wav)

            output_path = self._output_path_for(request)
            ensure_directory(output_path.parent)
            if request.output_format == "wav":
                shutil.copy(norm_wav, output_path)
            elif request.output_format == "mp3":
                encode_mp3(norm_wav, output_path)
            else:
                raise ValidationError(f"Unsupported output format: {request.output_format}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        processing_time = time.time() - start_time
        file_size = get_file_size(output_path)
        duration = get_audio_duration(output_path)
        # Character count drives cost tracking (free for local Kokoro but recorded)
        char_count = len(request.text)

        primary_voice_name = request.voice or self.default_voice
        logger.info(
            f"TTS done: {output_path.name}  mode={request.mode}  "
            f"{duration}s  {file_size} bytes  in {processing_time:.2f}s"
        )

        return TTSResponse(
            audio_file_path=str(output_path),
            duration_seconds=duration,
            file_size_bytes=file_size,
            provider="kokoro_tts",
            voice=primary_voice_name,
            processing_time=processing_time,
            format=request.output_format,
            characters=char_count,
            mode=request.mode,
        )


class TTSGenerator:
    """Main Text-to-Speech Generator with provider abstraction."""

    def __init__(self, config: Config, output_dir: str | None = None):
        self.config = config
        try:
            self.provider = TTSProvider(config.tts.provider)
        except ValueError as exc:
            raise ValidationError(
                f"Unsupported TTS provider: {config.tts.provider}. "
                "Only 'kokoro_tts' is supported (local rendering)."
            ) from exc

        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(config.storage.audio_dir)

        ensure_directory(self.output_dir)

        if self.provider == TTSProvider.KOKORO_TTS:
            self.client = KokoroTTSClient(config, str(self.output_dir))
        else:  # pragma: no cover — TTSProvider only has kokoro_tts
            raise ValidationError(f"Unsupported TTS provider: {self.provider}")

        logger.info(f"Initialized TTS Generator with provider: {self.provider}")

    async def __aenter__(self) -> "TTSGenerator":
        await self.client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def generate_speech(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "mp3",
        quality: str = "standard",
        # New text2audio-aware parameters:
        mode: str = "text",
        preset: str | None = None,
        quote_voice: str | None = None,
        voice_a: str | None = None,
        voice_b: str | None = None,
        quote_speed: float = 0.85,
        dialogue_speed: float = 0.95,
        pronunciations: str | None = None,
        extra_pronunciations: dict[str, str] | None = None,
        expand_abbrev: bool = True,
        target_lufs: float = -16.0,
        output_path: str | None = None,
    ) -> TTSResponse:
        """Generate speech from text. See TTSRequest for parameter docs."""
        if not text or not text.strip():
            raise ValidationError("Text cannot be empty")
        if not (0.5 <= speed <= 2.0):
            raise ValidationError("Speed must be between 0.5 and 2.0")
        if not (0.5 <= pitch <= 2.0):
            raise ValidationError("Pitch must be between 0.5 and 2.0")
        if output_format not in {"mp3", "wav"}:
            raise ValidationError("Output format must be 'mp3' or 'wav'")
        if quality not in {"standard", "high"}:
            raise ValidationError("Quality must be 'standard' or 'high'")
        if mode not in {"text", "dialogue"}:
            raise ValidationError("Mode must be 'text' or 'dialogue'")
        if len(text) > 500_000:
            raise ValidationError("Text too long for TTS conversion")

        logger.info(
            f"TTS start: {len(text)} chars, mode={mode}, preset={preset}, "
            f"voice={voice}, speed={speed}"
        )

        request = TTSRequest(
            text=text,
            voice=voice,
            speed=speed,
            pitch=pitch,
            output_format=output_format,
            quality=quality,
            mode=mode,
            preset=preset,
            quote_voice=quote_voice,
            voice_a=voice_a,
            voice_b=voice_b,
            quote_speed=quote_speed,
            dialogue_speed=dialogue_speed,
            pronunciations=pronunciations,
            extra_pronunciations=extra_pronunciations or {},
            expand_abbrev=expand_abbrev,
            target_lufs=target_lufs,
            output_path=output_path,
        )
        response = await self.client.synthesize(request)
        logger.info(
            f"TTS done: {response.audio_file_path}  {response.duration_seconds}s  "
            f"in {response.processing_time:.2f}s"
        )
        return response

    async def health_check(self) -> bool:
        try:
            return await self.client.health_check()
        except Exception as exc:
            logger.error(f"TTS health check failed: {exc}")
            return False

    def get_available_voices(self) -> list[str]:
        return self.client.get_available_voices()

    def get_available_presets(self) -> list[str]:
        return list_presets()

    def get_available_pronunciation_dicts(self) -> list[str]:
        return list_pronunciation_dicts()

    def get_provider_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "provider": str(self.provider),
            "available_voices": self.get_available_voices(),
            "available_presets": self.get_available_presets(),
            "available_pronunciation_dicts": self.get_available_pronunciation_dicts(),
            "output_directory": str(self.output_dir),
        }
        if self.provider == TTSProvider.KOKORO_TTS:
            info.update(
                {
                    "default_voice": self.client.default_voice,
                    "default_lang_code": self.client.default_lang_code,
                    "default_speed": self.client.default_speed,
                }
            )
        return info

    def cleanup_old_files(self, days: int = 7) -> int:
        """Delete tts_*.{mp3,wav} files in output_dir older than N days."""
        import time as time_module

        cutoff_time = time_module.time() - (days * 86400)
        deleted = 0
        try:
            for pattern in ("tts_*.mp3", "tts_*.wav"):
                for fp in self.output_dir.glob(pattern):
                    if fp.stat().st_mtime < cutoff_time:
                        fp.unlink()
                        deleted += 1
                        logger.debug(f"Deleted old audio file: {fp}")
            if deleted:
                logger.info(f"Cleaned up {deleted} old audio files")
        except Exception as exc:
            logger.error(f"Error cleaning up old files: {exc}")
        return deleted
