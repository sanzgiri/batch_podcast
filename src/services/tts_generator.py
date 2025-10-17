"""
Text-to-Speech Generator Service for Newsletter Podcast Generator.

This service provides high-quality text-to-speech conversion using
multiple providers (Unreal Speech API and Kokoro local TTS).
"""

import os
import asyncio
import tempfile
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, BinaryIO, List
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import aiohttp
import aiofiles
import nltk
from nltk.tokenize import sent_tokenize
from pydub import AudioSegment

from src.lib.config import Config
from src.lib.logging import get_logger
from src.lib.exceptions import TTSError, ValidationError, ServiceError
from src.lib.utils import ensure_directory, generate_uuid, get_file_size, get_audio_duration

# Download NLTK data for sentence tokenization (quiet mode)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)

logger = get_logger(__name__)


class TTSProvider(str, Enum):
    """Supported TTS providers."""
    UNREAL_SPEECH = "unreal_speech"
    KOKORO = "kokoro"


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
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the TTS service is available."""
        pass
    
    @abstractmethod
    def get_available_voices(self) -> list[str]:
        """Get list of available voices."""
        pass


class UnrealSpeechClient(BaseTTSClient):
    """Unreal Speech API client implementation."""
    
    def __init__(self, config: Config, output_dir: str):
        self.config = config
        self.api_key = config.tts.unreal_speech.api_key
        self.base_url = config.tts.unreal_speech.base_url
        self.default_voice = config.tts.unreal_speech.voice
        self.output_dir = Path(output_dir)
        
        if not self.api_key:
            raise ValidationError("Unreal Speech API key is required")
        
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Voice mapping
        self.voices = {
            "scarlett": "Scarlett",
            "dan": "Dan", 
            "liv": "Liv",
            "will": "Will",
            "amy": "Amy"
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=aiohttp.ClientTimeout(total=300)  # 5 minutes for long audio
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def _chunk_text(self, text: str, max_chars: int = 950) -> List[str]:
        """
        Split text into chunks under max_chars using sentence boundaries.
        
        Args:
            text: Text to chunk
            max_chars: Maximum characters per chunk (default 950 to stay under 1000 limit)
            
        Returns:
            List of text chunks
        """
        sentences = sent_tokenize(text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence would exceed limit, save current chunk and start new one
            if len(current_chunk) + len(sentence) + 1 <= max_chars:  # +1 for space
                current_chunk += sentence + " "
            else:
                # If current chunk has content, save it
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # If single sentence exceeds max_chars, split it further
                if len(sentence) > max_chars:
                    # Split long sentence by character count
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
        
        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech using Unreal Speech API."""
        if not self.session:
            raise ServiceError("Unreal Speech client must be used as async context manager")
        
        logger.info(f"Synthesizing speech with Unreal Speech: {len(request.text)} chars")
        start_time = asyncio.get_event_loop().time()
        
        # Check if text needs chunking (Unreal Speech has 1000 char limit)
        max_chars = 950  # Safety margin below 1000
        needs_chunking = len(request.text) > max_chars
        
        if needs_chunking:
            logger.info(f"Text exceeds {max_chars} chars, splitting into chunks...")
            return await self._synthesize_chunked(request)
        else:
            return await self._synthesize_single(request, start_time)
    
    async def _synthesize_single(self, request: TTSRequest, start_time: float = None) -> TTSResponse:
        """Synthesize a single text chunk."""
        if start_time is None:
            start_time = asyncio.get_event_loop().time()
        
        try:
            # Validate and prepare request
            voice = request.voice or self.default_voice
            if voice not in self.voices:
                voice = self.default_voice
            
            # Create output file path
            filename = f"tts_{generate_uuid()}.{request.output_format}"
            output_path = self.output_dir / filename
            ensure_directory(output_path.parent)
            
            # Prepare API request
            # Convert voice to lowercase for lookup, or use directly if already valid
            voice_id = self.voices.get(voice.lower(), voice) if isinstance(voice, str) else self.voices.get("liv", "Liv")
            
            # Map output format to Unreal Speech codec
            codec_map = {
                "mp3": "libmp3lame",
                "wav": "pcm_s16le",
                "mulaw": "pcm_mulaw"
            }
            codec = codec_map.get(request.output_format, "libmp3lame")
            
            # Build payload - only include optional parameters if they differ from defaults
            payload = {
                "Text": request.text,
                "VoiceId": voice_id,
                "Bitrate": "192k" if request.quality == "high" else "128k",
                "Codec": codec
            }
            
            # Only add Speed and Pitch if they're not default values
            # Note: Unreal Speech API may not support these parameters on all endpoints
            if request.speed != 1.0:
                payload["Speed"] = str(request.speed)
            if request.pitch != 1.0:
                payload["Pitch"] = str(request.pitch)
            
            # Make API request
            async with self.session.post(f"{self.base_url}/stream", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Unreal Speech API error: {response.status} - {error_text}")
                    logger.error(f"Request payload: {payload}")
                response.raise_for_status()
                
                # Stream audio data to file
                async with aiofiles.open(output_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            # Get file info
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
                provider="unreal_speech",
                voice=voice,
                processing_time=processing_time,
                format=request.output_format
            )
            
        except aiohttp.ClientError as e:
            logger.error(f"Unreal Speech API request failed: {e}")
            raise TTSError(f"Unreal Speech API request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in Unreal Speech synthesis: {e}")
            raise TTSError(f"TTS synthesis failed: {e}")
    
    async def _synthesize_chunked(self, request: TTSRequest) -> TTSResponse:
        """Synthesize long text by chunking and concatenating audio."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Split text into chunks
            chunks = self._chunk_text(request.text)
            logger.info(f"Split text into {len(chunks)} chunks for processing")
            
            # Create temp directory for chunk audio files
            temp_dir = Path(tempfile.mkdtemp(prefix="tts_chunks_"))
            chunk_files = []
            
            try:
                # Generate audio for each chunk
                for i, chunk_text in enumerate(chunks):
                    logger.info(f"Processing chunk {i+1}/{len(chunks)}: {len(chunk_text)} chars")
                    
                    # Create chunk request
                    chunk_request = TTSRequest(
                        text=chunk_text,
                        voice=request.voice,
                        speed=request.speed,
                        pitch=request.pitch,
                        output_format=request.output_format,
                        quality=request.quality
                    )
                    
                    # Generate audio for this chunk
                    chunk_response = await self._synthesize_single(chunk_request, start_time)
                    chunk_files.append(chunk_response.audio_file_path)
                    
                    # Rate limiting - wait 1 second between requests
                    if i < len(chunks) - 1:
                        await asyncio.sleep(1)
                
                # Concatenate all audio files using pydub
                logger.info(f"Concatenating {len(chunk_files)} audio files...")
                combined = AudioSegment.empty()
                for chunk_file in chunk_files:
                    audio_segment = AudioSegment.from_mp3(chunk_file) if request.output_format == "mp3" else AudioSegment.from_file(chunk_file)
                    combined += audio_segment
                
                # Create final output file
                filename = f"tts_{generate_uuid()}.{request.output_format}"
                output_path = self.output_dir / filename
                ensure_directory(output_path.parent)
                
                # Export concatenated audio
                combined.export(str(output_path), format=request.output_format)
                
                processing_time = asyncio.get_event_loop().time() - start_time
                
                # Get file info
                file_size = get_file_size(output_path)
                duration = get_audio_duration(output_path)
                
                logger.info(
                    f"Chunked TTS completed: {output_path.name}, "
                    f"{duration}s duration, {file_size} bytes, "
                    f"processed in {processing_time:.2f}s from {len(chunks)} chunks"
                )
                
                return TTSResponse(
                    audio_file_path=str(output_path),
                    duration_seconds=duration,
                    file_size_bytes=file_size,
                    provider="unreal_speech",
                    voice=request.voice or self.default_voice,
                    processing_time=processing_time,
                    format=request.output_format
                )
                
            finally:
                # Clean up temporary chunk files
                logger.info("Cleaning up temporary chunk files...")
                for chunk_file in chunk_files:
                    try:
                        Path(chunk_file).unlink()
                    except Exception as e:
                        logger.warning(f"Could not delete chunk file {chunk_file}: {e}")
                try:
                    temp_dir.rmdir()
                except Exception as e:
                    logger.warning(f"Could not remove temp directory {temp_dir}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in chunked TTS synthesis: {e}")
            raise TTSError(f"Chunked TTS synthesis failed: {e}")
    
    async def health_check(self) -> bool:
        """Check Unreal Speech API availability."""
        if not self.session:
            return False
        
        try:
            # Test with minimal request
            payload = {"Text": "Test", "VoiceId": "Scarlett"}
            async with self.session.post(f"{self.base_url}/stream", json=payload) as response:
                return response.status == 200
                
        except Exception:
            return False
    
    def get_available_voices(self) -> list[str]:
        """Get list of available voices."""
        return list(self.voices.keys())


class KokoroClient(BaseTTSClient):
    """Kokoro local TTS client implementation."""
    
    def __init__(self, config: Config, output_dir: str):
        self.config = config
        self.base_url = config.tts.kokoro.base_url
        self.default_voice = config.tts.kokoro.voice
        self.output_dir = Path(output_dir)
        
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Available voices (example - adjust based on actual Kokoro setup)
        self.voices = [
            "female_1", "female_2", "male_1", "male_2", 
            "neutral_1", "neutral_2"
        ]
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech using Kokoro local TTS."""
        if not self.session:
            raise ServiceError("Kokoro client must be used as async context manager")
        
        logger.info(f"Synthesizing speech with Kokoro: {len(request.text)} chars")
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Validate and prepare request
            voice = request.voice or self.default_voice
            if voice not in self.voices:
                voice = self.default_voice
            
            # Create output file path
            filename = f"tts_{generate_uuid()}.{request.output_format}"
            output_path = self.output_dir / filename
            ensure_directory(output_path.parent)
            
            # Prepare API request
            payload = {
                "text": request.text,
                "voice": voice,
                "speed": request.speed,
                "pitch": request.pitch,
                "format": request.output_format
            }
            
            # Make API request
            async with self.session.post(f"{self.base_url}/synthesize", json=payload) as response:
                response.raise_for_status()
                
                # Save audio data
                audio_data = await response.read()
                async with aiofiles.open(output_path, 'wb') as f:
                    await f.write(audio_data)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            # Get file info
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
                provider="kokoro",
                voice=voice,
                processing_time=processing_time,
                format=request.output_format
            )
            
        except aiohttp.ClientError as e:
            logger.error(f"Kokoro API request failed: {e}")
            raise TTSError(f"Kokoro API request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in Kokoro synthesis: {e}")
            raise TTSError(f"TTS synthesis failed: {e}")
    
    async def health_check(self) -> bool:
        """Check Kokoro service availability."""
        if not self.session:
            return False
        
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                return response.status == 200
                
        except Exception:
            return False
    
    def get_available_voices(self) -> list[str]:
        """Get list of available voices."""
        return self.voices.copy()


class TTSGenerator:
    """
    Main Text-to-Speech Generator service with provider abstraction.
    
    Handles provider selection, file management, and response processing.
    """
    
    def __init__(self, config: Config, output_dir: Optional[str] = None):
        """Initialize TTS Generator with configuration."""
        self.config = config
        self.provider = TTSProvider(config.tts.provider)
        
        # Set up output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(config.storage.audio_dir)
        
        ensure_directory(self.output_dir)
        
        # Initialize client based on provider
        if self.provider == TTSProvider.UNREAL_SPEECH:
            self.client = UnrealSpeechClient(config, str(self.output_dir))
        elif self.provider == TTSProvider.KOKORO:
            self.client = KokoroClient(config, str(self.output_dir))
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
        
        # Validate parameters
        if not (0.5 <= speed <= 2.0):
            raise ValidationError("Speed must be between 0.5 and 2.0")
        
        if not (0.5 <= pitch <= 2.0):
            raise ValidationError("Pitch must be between 0.5 and 2.0")
        
        if output_format not in ["mp3", "wav"]:
            raise ValidationError("Output format must be 'mp3' or 'wav'")
        
        if quality not in ["standard", "high"]:
            raise ValidationError("Quality must be 'standard' or 'high'")
        
        # Check text length
        if len(text) > 500000:  # 500K chars limit
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
        
        try:
            response = await self.client.synthesize(request)
            
            logger.info(
                f"TTS generation completed: {response.audio_file_path}, "
                f"{response.duration_seconds}s duration, "
                f"processed in {response.processing_time:.2f}s"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if the TTS service is available."""
        try:
            return await self.client.health_check()
        except Exception as e:
            logger.error(f"TTS health check failed: {e}")
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
        
        if self.provider == TTSProvider.UNREAL_SPEECH:
            info.update({
                "base_url": self.client.base_url,
                "default_voice": self.client.default_voice
            })
        elif self.provider == TTSProvider.KOKORO:
            info.update({
                "base_url": self.client.base_url,
                "default_voice": self.client.default_voice
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
        import time
        
        cutoff_time = time.time() - (days * 24 * 60 * 60)
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
            
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
        
        return deleted_count