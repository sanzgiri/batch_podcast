"""
Text-to-Speech Generator Service for Newsletter Podcast Generator.

This service provides text-to-speech conversion using the local Kokoro TTS
backend (kokoro_tts).
"""

import asyncio
import tempfile
import time
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import nltk
from nltk.tokenize import sent_tokenize
from pydub import AudioSegment

from src.lib.config import Config
from src.lib.exceptions import TTSError, ValidationError, ServiceError
from src.lib.logging import get_logger
from src.lib.utils import ensure_directory, generate_uuid, get_audio_duration, get_file_size

# Download NLTK data for sentence tokenization (quiet mode)
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)

logger = get_logger(__name__)


class TTSProvider(str, Enum):
    """Supported TTS providers."""
    KOKORO_TTS = "kokoro_tts"


@dataclass
class TTSRequest:
    """Request for text-to-speech conversion."""
    text: str
    voice: Optional[str] = None
    speed: float = 1.0
    pitch: float = 1.0
    output_format: str = "mp3"  # mp3, wav
    quality: str = "standard"  # standard, high


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
    """Kokoro TTS client implementation (local library)."""

    def __init__(self, config: Config, output_dir: str):
        self.config = config
        self.default_voice = config.tts.kokoro_tts.voice
        self.default_lang_code = config.tts.kokoro_tts.lang_code
        self.default_speed = config.tts.kokoro_tts.speed
        self.output_dir = Path(output_dir)

        self.backend_type: Optional[str] = None
        self.backend = None
        self.sample_rate = 24000
        self.voices = [self.default_voice]

    async def __aenter__(self):
        """Async context manager entry."""
        await asyncio.to_thread(self._init_backend)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.backend = None

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech using Kokoro TTS."""
        if not self.backend:
            raise ServiceError("Kokoro TTS client must be used as async context manager")

        logger.info(f"Synthesizing speech with Kokoro TTS: {len(request.text)} chars")

        try:
            return await asyncio.to_thread(self._synthesize_sync, request)
        except Exception as exc:
            logger.error(f"Unexpected error in Kokoro TTS synthesis: {exc}")
            raise TTSError(f"Kokoro TTS synthesis failed: {exc}") from exc

    async def health_check(self) -> bool:
        """Check Kokoro availability."""
        return self.backend is not None

    def get_available_voices(self) -> list[str]:
        """Get list of available voices."""
        return self.voices.copy()

    def _load_kokoro_backend(self) -> Tuple[str, type]:
        try:
            from kokoro import KPipeline  # type: ignore
            return "pipeline", KPipeline
        except Exception:
            pass
        try:
            from kokoro import KModel  # type: ignore
            return "model", KModel
        except Exception as exc:
            raise ImportError(
                "Kokoro is not installed. Install it before using kokoro_tts."
            ) from exc

    def _init_backend(self) -> None:
        if self.backend is not None:
            return

        self.backend_type, backend_cls = self._load_kokoro_backend()
        if self.backend_type == "pipeline":
            try:
                self.backend = backend_cls(lang_code=self.default_lang_code)
            except TypeError:
                self.backend = backend_cls()
        else:
            self.backend = backend_cls()

        self.sample_rate = getattr(self.backend, "sample_rate", getattr(self.backend, "sr", 24000))

    def _chunk_text(self, text: str, max_chars: int = 950) -> List[str]:
        """Split text into chunks under max_chars using sentence boundaries."""
        sentences = sent_tokenize(text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_chars:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())

                if len(sentence) > max_chars:
                    words = sentence.split()
                    current_chunk = ""
                    for word in words:
                        if len(current_chunk) + len(word) + 1 <= max_chars:
                            current_chunk += word + " "
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = word + " "
                else:
                    current_chunk = sentence + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _write_wav(self, path: Path, audio, sample_rate: int) -> None:
        """Write mono WAV from float samples in [-1.0, 1.0]."""
        try:
            import numpy as np  # Optional dependency; Kokoro typically brings it in.

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
            return
        except Exception:
            pass

        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        if hasattr(audio, "tolist"):
            audio = audio.tolist()
        if not audio:
            raise ValueError("Empty audio buffer")
        from array import array

        pcm = array("h")
        for sample in audio:
            if sample > 1.0:
                sample = 1.0
            elif sample < -1.0:
                sample = -1.0
            pcm.append(int(sample * 32767.0))
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm.tobytes())

    def _synthesize_chunk(
        self,
        text: str,
        temp_dir: Path,
        chunk_index: int,
        voice: str,
        speed: float
    ) -> List[Path]:
        chunk_files: List[Path] = []

        if self.backend_type == "pipeline":
            try:
                generator = self.backend(text, voice=voice, speed=speed, split_pattern=r"\n+")
            except TypeError:
                try:
                    generator = self.backend(text, voice=voice, speed=speed)
                except TypeError:
                    generator = self.backend(text)

            for part_index, (_, _, audio) in enumerate(generator, start=1):
                file_name = temp_dir / f"audio_chunk_{chunk_index}_{part_index}.wav"
                self._write_wav(file_name, audio, self.sample_rate)
                chunk_files.append(file_name)
        else:
            try:
                audio = self.backend.generate(text, voice=voice)
            except TypeError:
                audio = self.backend.generate(text)
            file_name = temp_dir / f"audio_chunk_{chunk_index}.wav"
            self._write_wav(file_name, audio, self.sample_rate)
            chunk_files.append(file_name)

        return chunk_files

    def _export_audio(self, chunk_files: List[Path], output_format: str) -> Path:
        combined = AudioSegment.empty()
        for chunk_file in chunk_files:
            combined += AudioSegment.from_file(chunk_file)

        filename = f"tts_{generate_uuid()}.{output_format}"
        output_dir = Path(self.output_dir)
        output_path = output_dir / filename
        ensure_directory(output_path.parent)
        combined.export(str(output_path), format=output_format)
        return output_path

    def _synthesize_sync(self, request: TTSRequest) -> TTSResponse:
        start_time = time.time()

        voice = request.voice or self.default_voice
        speed = request.speed if request.speed != 0 else self.default_speed

        chunks = self._chunk_text(request.text)
        logger.info(f"Split text into {len(chunks)} chunks for Kokoro TTS")

        temp_dir = Path(tempfile.mkdtemp(prefix="tts_chunks_"))
        chunk_files: List[Path] = []

        try:
            for index, chunk_text in enumerate(chunks, start=1):
                logger.info(f"Processing chunk {index}/{len(chunks)}: {len(chunk_text)} chars")
                chunk_files.extend(
                    self._synthesize_chunk(
                        chunk_text,
                        temp_dir,
                        index,
                        voice,
                        speed
                    )
                )

            if not chunk_files:
                raise TTSError("No audio chunks generated")

            output_path = self._export_audio(chunk_files, request.output_format)
            processing_time = time.time() - start_time

            file_size = get_file_size(output_path)
            duration = get_audio_duration(output_path)

            logger.info(
                f"TTS completed: {output_path.name}, "
                f"{duration}s duration, {file_size} bytes, "
                f"processed in {processing_time:.2f}s"
            )

            return TTSResponse(
                audio_file_path=str(output_path),
                duration_seconds=duration,
                file_size_bytes=file_size,
                provider="kokoro_tts",
                voice=voice,
                processing_time=processing_time,
                format=request.output_format
            )
        finally:
            for chunk_file in chunk_files:
                try:
                    chunk_file.unlink()
                except Exception as exc:
                    logger.warning(f"Could not delete chunk file {chunk_file}: {exc}")
            try:
                temp_dir.rmdir()
            except Exception as exc:
                logger.warning(f"Could not remove temp directory {temp_dir}: {exc}")


class TTSGenerator:
    """
    Main Text-to-Speech Generator service with provider abstraction.

    Handles provider selection, file management, and response processing.
    """

    def __init__(self, config: Config, output_dir: Optional[str] = None):
        """Initialize TTS Generator with configuration."""
        self.config = config
        self.provider = TTSProvider(config.tts.provider)

        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(config.storage.audio_dir)

        ensure_directory(self.output_dir)

        if self.provider == TTSProvider.KOKORO_TTS:
            self.client = KokoroTTSClient(config, str(self.output_dir))
        else:
            raise ValidationError(f"Unsupported TTS provider: {self.provider}")

        logger.info(f"Initialized TTS Generator with provider: {self.provider}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def generate_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 1.0,
        output_format: str = "mp3",
        quality: str = "standard"
    ) -> TTSResponse:
        """
        Main method to generate speech from text.

        Args:
            text: Text to convert to speech
            voice: Voice to use (provider-specific)
            speed: Speech speed (0.5-2.0)
            pitch: Speech pitch (0.5-2.0)
            output_format: Audio format (mp3, wav)
            quality: Audio quality (standard, high)

        Returns:
            TTSResponse with generated audio file and metadata

        Raises:
            TTSError: If synthesis fails
            ValidationError: If input is invalid
        """
        if not text or not text.strip():
            raise ValidationError("Text cannot be empty")

        if not (0.5 <= speed <= 2.0):
            raise ValidationError("Speed must be between 0.5 and 2.0")

        if not (0.5 <= pitch <= 2.0):
            raise ValidationError("Pitch must be between 0.5 and 2.0")

        if output_format not in ["mp3", "wav"]:
            raise ValidationError("Output format must be 'mp3' or 'wav'")

        if quality not in ["standard", "high"]:
            raise ValidationError("Quality must be 'standard' or 'high'")

        if len(text) > 500000:
            raise ValidationError("Text too long for TTS conversion")

        logger.info(
            f"Starting TTS generation: {len(text)} chars, "
            f"voice: {voice}, speed: {speed}, pitch: {pitch}"
        )

        request = TTSRequest(
            text=text,
            voice=voice,
            speed=speed,
            pitch=pitch,
            output_format=output_format,
            quality=quality
        )

        response = await self.client.synthesize(request)

        logger.info(
            f"TTS generation completed: {response.audio_file_path}, "
            f"{response.duration_seconds}s duration, "
            f"processed in {response.processing_time:.2f}s"
        )

        return response

    async def health_check(self) -> bool:
        """Check if the TTS service is available."""
        try:
            return await self.client.health_check()
        except Exception as exc:
            logger.error(f"TTS health check failed: {exc}")
            return False

    def get_available_voices(self) -> list[str]:
        """Get list of available voices for current provider."""
        return self.client.get_available_voices()

    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the current provider."""
        info = {
            "provider": str(self.provider),
            "available_voices": self.get_available_voices(),
            "output_directory": str(self.output_dir)
        }

        if self.provider == TTSProvider.KOKORO_TTS:
            info.update({
                "default_voice": self.client.default_voice,
                "default_lang_code": self.client.default_lang_code,
                "default_speed": self.client.default_speed
            })

        return info

    def cleanup_old_files(self, days: int = 7) -> int:
        """
        Clean up old audio files.

        Args:
            days: Delete files older than this many days

        Returns:
            Number of files deleted
        """
        import time as time_module

        cutoff_time = time_module.time() - (days * 24 * 60 * 60)
        deleted_count = 0

        try:
            for file_path in self.output_dir.glob("tts_*.mp3"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old audio file: {file_path}")

            for file_path in self.output_dir.glob("tts_*.wav"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old audio file: {file_path}")

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old audio files")

        except Exception as exc:
            logger.error(f"Error cleaning up old files: {exc}")

        return deleted_count
