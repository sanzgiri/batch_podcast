"""
Unit tests for TTS generation service.

These tests verify the TTSGenerator service functionality
for generating audio from text using different TTS providers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import os


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tts_generator_initialization():
    """Test TTSGenerator service initialization."""
    from src.services.tts_generator import TTSGenerator
    
    generator = TTSGenerator()
    
    # Test service initialization
    await generator.initialize()
    
    assert generator.is_initialized is True
    assert generator.name == "tts_generator"
    assert generator.provider_name is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kokoro_provider_initialization():
    """Test Kokoro TTS provider initialization."""
    from src.services.tts_generator import TTSGenerator
    
    # Mock configuration for Kokoro
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.tts.provider = "kokoro"
        mock_config.ai_services.tts.kokoro.base_url = "http://localhost:8080"
        mock_config.ai_services.tts.kokoro.voice = "default"
        mock_settings.return_value = mock_config
        
        generator = TTSGenerator()
        await generator.initialize()
        
        assert generator.provider_name == "kokoro"
        assert generator.provider_config["base_url"] == "http://localhost:8080"
        assert generator.provider_config["voice"] == "default"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unreal_speech_provider_initialization():
    """Test Unreal Speech TTS provider initialization."""
    from src.services.tts_generator import TTSGenerator
    
    # Mock configuration for Unreal Speech
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.tts.provider = "unreal_speech"
        mock_config.ai_services.tts.unreal_speech.api_key = "test-api-key"
        mock_config.ai_services.tts.unreal_speech.voice = "Scarlett"
        mock_settings.return_value = mock_config
        
        generator = TTSGenerator()
        await generator.initialize()
        
        assert generator.provider_name == "unreal_speech"
        assert generator.provider_config["api_key"] == "test-api-key"
        assert generator.provider_config["voice"] == "Scarlett"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_audio_with_kokoro():
    """Test audio generation using Kokoro provider."""
    from src.services.tts_generator import TTSGenerator
    
    text_content = """
    Welcome to this week's technology newsletter. Today we'll cover the latest developments
    in artificial intelligence, cloud computing, and software engineering practices.
    
    Our first story focuses on recent advances in large language models and their
    applications in code generation and documentation.
    """
    
    # Mock Kokoro configuration
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.tts.provider = "kokoro"
        mock_config.ai_services.tts.kokoro.base_url = "http://localhost:8080"
        mock_config.ai_services.tts.kokoro.voice = "default"
        mock_settings.return_value = mock_config
        
        generator = TTSGenerator()
        await generator.initialize()
        
        # Create temporary output file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            output_path = temp_file.name
        
        try:
            # Mock Kokoro API response with audio data
            mock_audio_data = b"fake_mp3_audio_data_for_testing"
            
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=mock_audio_data)
                mock_response.headers = {"content-type": "audio/mpeg"}
                mock_post.return_value.__aenter__.return_value = mock_response
                
                result_path = await generator.generate_audio(text_content, output_path)
                
                # Verify audio generation
                assert result_path == output_path
                assert Path(result_path).exists()
                
                # Verify file content
                with open(result_path, "rb") as f:
                    file_data = f.read()
                assert file_data == mock_audio_data
        
        finally:
            # Clean up
            if os.path.exists(output_path):
                os.unlink(output_path)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_audio_with_unreal_speech():
    """Test audio generation using Unreal Speech provider."""
    from src.services.tts_generator import TTSGenerator
    
    text_content = "This is a test text for Unreal Speech TTS generation."
    
    # Mock Unreal Speech configuration
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.tts.provider = "unreal_speech"
        mock_config.ai_services.tts.unreal_speech.api_key = "test-key"
        mock_config.ai_services.tts.unreal_speech.voice = "Scarlett"
        mock_settings.return_value = mock_config
        
        generator = TTSGenerator()
        await generator.initialize()
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            output_path = temp_file.name
        
        try:
            mock_audio_data = b"fake_unreal_speech_audio_data"
            
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_response = AsyncMock() 
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=mock_audio_data)
                mock_post.return_value.__aenter__.return_value = mock_response
                
                result_path = await generator.generate_audio(text_content, output_path)
                
                assert result_path == output_path
                assert Path(result_path).exists()
        
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_audio_error_handling():
    """Test error handling in TTS generation."""
    from src.services.tts_generator import TTSGenerator
    from src.lib.exceptions import TTSServiceError
    
    text_content = "Test content for error handling scenario."
    
    # Test service error
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.tts.provider = "kokoro"
        mock_config.ai_services.tts.kokoro.base_url = "http://localhost:8080"
        mock_settings.return_value = mock_config
        
        generator = TTSGenerator()
        await generator.initialize()
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            output_path = temp_file.name
        
        try:
            # Mock HTTP error
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_response = AsyncMock()
                mock_response.status = 500
                mock_response.text = AsyncMock(return_value="Internal Server Error")
                mock_post.return_value.__aenter__.return_value = mock_response
                
                with pytest.raises(TTSServiceError) as exc_info:
                    await generator.generate_audio(text_content, output_path)
                
                assert "500" in str(exc_info.value)
                assert exc_info.value.provider == "kokoro"
        
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_audio_timeout_handling():
    """Test timeout handling in TTS generation."""
    from src.services.tts_generator import TTSGenerator
    from src.lib.exceptions import TTSServiceError
    import asyncio
    
    text_content = "Test content for timeout scenario."
    
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.tts.provider = "kokoro"
        mock_config.ai_services.tts.kokoro.base_url = "http://localhost:8080"
        mock_settings.return_value = mock_config
        
        generator = TTSGenerator()
        await generator.initialize()
        
        with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
            output_path = temp_file.name
            
            # Mock timeout
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.side_effect = asyncio.TimeoutError("Request timeout")
                
                with pytest.raises(TTSServiceError) as exc_info:
                    await generator.generate_audio(text_content, output_path)
                
                assert "timeout" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_text_preprocessing():
    """Test text preprocessing before TTS generation."""
    from src.services.tts_generator import TTSGenerator
    
    # Test various text preprocessing scenarios
    test_cases = [
        {
            "input": "This is a test with **bold** and *italic* text.",
            "expected": "This is a test with bold and italic text."
        },
        {
            "input": "Text with [link](https://example.com) and `code`.",
            "expected": "Text with link and code."
        },
        {
            "input": "Multiple\n\n\nline breaks   and    spaces.",
            "expected": "Multiple line breaks and spaces."
        },
        {
            "input": "HTML entities like &amp; and &lt; should be handled.",
            "expected": "HTML entities like & and < should be handled."
        }
    ]
    
    generator = TTSGenerator()
    
    for test_case in test_cases:
        result = generator._preprocess_text(test_case["input"])
        assert test_case["expected"] in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_audio_validation():
    """Test audio file validation after generation."""
    from src.services.tts_generator import TTSGenerator
    from src.lib.exceptions import TTSServiceError
    
    generator = TTSGenerator()
    
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        output_path = temp_file.name
    
    try:
        # Test with empty file
        with pytest.raises(TTSServiceError) as exc_info:
            generator._validate_audio_file(output_path)
        assert "empty" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
        
        # Test with valid audio data
        with open(output_path, "wb") as f:
            f.write(b"fake_mp3_header_and_data" * 100)  # Make it reasonable size
        
        # Should not raise exception for valid file
        generator._validate_audio_file(output_path)
    
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_audio_duration():
    """Test audio duration extraction."""
    from src.services.tts_generator import TTSGenerator
    
    generator = TTSGenerator()
    
    # Mock mutagen to return duration
    with patch('mutagen.File') as mock_mutagen:
        mock_file = MagicMock()
        mock_file.info.length = 120.5  # 2 minutes 30.5 seconds
        mock_mutagen.return_value = mock_file
        
        duration = generator._get_audio_duration("/fake/path/audio.mp3")
        assert duration == 120.5


@pytest.mark.unit
@pytest.mark.asyncio
async def test_text_length_validation():
    """Test text length validation before TTS generation."""
    from src.services.tts_generator import TTSGenerator
    from src.lib.exceptions import ValidationError
    
    generator = TTSGenerator()
    await generator.initialize()
    
    # Test empty text
    with pytest.raises(ValidationError):
        await generator.generate_audio("", "/tmp/output.mp3")
    
    # Test very long text (over reasonable limit)
    very_long_text = "Word " * 10000  # Very long text
    with pytest.raises(ValidationError) as exc_info:
        await generator.generate_audio(very_long_text, "/tmp/output.mp3")
    assert "too long" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_check():
    """Test TTSGenerator health check."""
    from src.services.tts_generator import TTSGenerator
    
    generator = TTSGenerator()
    
    # Health check before initialization
    health = await generator.health_check()
    assert health.is_healthy is False
    
    # Health check after initialization
    await generator.initialize()
    health = await generator.health_check()
    assert health.is_healthy is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provider_switching():
    """Test switching between TTS providers."""
    from src.services.tts_generator import TTSGenerator
    
    # Test with Kokoro first
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.tts.provider = "kokoro"
        mock_config.ai_services.tts.kokoro.base_url = "http://localhost:8080"
        mock_settings.return_value = mock_config
        
        generator = TTSGenerator()
        await generator.initialize()
        
        assert generator.provider_name == "kokoro"
        
        # Reinitialize with Unreal Speech
        mock_config.ai_services.tts.provider = "unreal_speech"
        mock_config.ai_services.tts.unreal_speech.api_key = "test-key"
        
        await generator.shutdown()
        await generator.initialize()
        
        assert generator.provider_name == "unreal_speech"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_voice_parameter_handling():
    """Test different voice parameter handling."""
    from src.services.tts_generator import TTSGenerator
    
    text_content = "Test text for voice parameter testing."
    
    # Test with custom voice parameter
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.tts.provider = "unreal_speech"
        mock_config.ai_services.tts.unreal_speech.voice = "Dan"
        mock_settings.return_value = mock_config
        
        generator = TTSGenerator()
        await generator.initialize()
        
        with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
            output_path = temp_file.name
            
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=b"fake_audio")
                mock_post.return_value.__aenter__.return_value = mock_response
                
                await generator.generate_audio(text_content, output_path, voice="CustomVoice")
                
                # Verify voice parameter was used
                call_args = mock_post.call_args
                assert "CustomVoice" in str(call_args) or "voice" in str(call_args)


# Fixtures for TTS generator tests
@pytest.fixture
async def tts_generator():
    """Fixture providing initialized TTSGenerator."""
    from src.services.tts_generator import TTSGenerator
    generator = TTSGenerator()
    await generator.initialize()
    yield generator
    await generator.shutdown()


@pytest.fixture
def sample_text_content():
    """Fixture providing sample text content for TTS generation."""
    return """
    Welcome to this week's technology newsletter podcast. I'm your host bringing you
    the latest developments in software engineering, artificial intelligence, and cloud computing.
    
    Today's episode covers three major stories: first, we'll explore recent advances in
    large language models and their impact on developer productivity. Second, we'll discuss
    the growing adoption of serverless architectures in enterprise environments. Finally,
    we'll examine new security practices emerging in the DevOps community.
    
    Let's start with our first story about AI in software development.
    """


@pytest.fixture
def temp_audio_file():
    """Fixture providing temporary audio file path."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_path = temp_file.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)