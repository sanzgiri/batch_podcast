"""
Integration tests for newsletter processing pipeline.

These tests verify the end-to-end flow from newsletter submission
to audio episode generation, testing the integration of all User Story 1 components.
"""

import pytest
import asyncio
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_newsletter_processing_pipeline():
    """Test complete newsletter processing from submission to audio generation."""
    # This is the main integration test for User Story 1
    # It should FAIL initially until all components are implemented
    
    # Test newsletter content
    newsletter_content = """
    # Weekly Tech Update
    
    This week in technology we saw major developments in AI and cloud computing.
    OpenAI released new models with improved capabilities for text generation.
    
    ## Key Highlights
    - New AI models show 30% improvement in accuracy
    - Cloud adoption continues to grow across enterprises  
    - Cybersecurity threats evolved with new attack vectors
    
    The implications for developers and businesses are significant as these
    technologies reshape how we build and deploy applications.
    """
    
    # Expected processing stages
    expected_stages = [
        "content_extraction",
        "llm_summarization", 
        "tts_generation",
        "file_storage"
    ]
    
    # This will fail until services are implemented
    from src.services.newsletter_processor import NewsletterProcessor
    from src.models.newsletter import Newsletter
    from src.models.episode import Episode
    
    processor = NewsletterProcessor()
    
    # Process newsletter
    result = await processor.process_newsletter(
        title="Weekly Tech Update",
        content=newsletter_content
    )
    
    # Verify processing result
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "newsletter" in result, "Result should contain newsletter"
    assert "episode" in result, "Result should contain episode"
    
    newsletter = result["newsletter"]
    episode = result["episode"]
    
    # Verify newsletter was created
    assert isinstance(newsletter, Newsletter), "Newsletter should be Newsletter instance"
    assert newsletter.title == "Weekly Tech Update"
    assert newsletter.content == newsletter_content
    assert newsletter.status == "completed"
    assert newsletter.word_count > 50  # Should have extracted words
    
    # Verify episode was created
    assert isinstance(episode, Episode), "Episode should be Episode instance" 
    assert episode.newsletter_id == newsletter.id
    assert episode.title is not None, "Episode should have a title"
    assert episode.summary_text is not None, "Episode should have summary"
    assert episode.audio_file_path is not None, "Episode should have audio file"
    assert episode.duration_seconds > 0, "Episode should have duration"
    
    # Verify audio file exists
    audio_path = Path(episode.audio_file_path)
    assert audio_path.exists(), "Audio file should exist on disk"
    assert audio_path.suffix == ".mp3", "Audio file should be MP3"


@pytest.mark.integration  
@pytest.mark.asyncio
async def test_newsletter_processing_with_url():
    """Test newsletter processing with URL content extraction."""
    
    # Mock URL content
    mock_html_content = """
    <html>
    <head><title>Tech Newsletter</title></head>
    <body>
        <h1>This Week in Tech</h1>
        <p>Major breakthroughs in artificial intelligence continue to reshape
           the technology landscape. Companies are investing heavily in AI
           research and development to stay competitive.</p>
        <p>Cloud computing adoption accelerated as organizations recognize
           the benefits of scalable infrastructure and reduced operational costs.</p>
    </body>
    </html>
    """
    
    expected_text_content = "This Week in Tech\n\nMajor breakthroughs in artificial intelligence continue to reshape the technology landscape. Companies are investing heavily in AI research and development to stay competitive.\n\nCloud computing adoption accelerated as organizations recognize the benefits of scalable infrastructure and reduced operational costs."
    
    from src.services.newsletter_processor import NewsletterProcessor
    
    processor = NewsletterProcessor()
    
    # Mock the content extraction
    with patch('src.services.content_extractor.ContentExtractor.extract_from_url') as mock_extract:
        mock_extract.return_value = expected_text_content
        
        result = await processor.process_newsletter(
            title="Tech Newsletter",
            url="https://example.com/tech-newsletter"
        )
        
        # Verify URL was processed
        newsletter = result["newsletter"]
        assert newsletter.url == "https://example.com/tech-newsletter"
        assert newsletter.extracted_content == expected_text_content
        assert newsletter.content == expected_text_content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_newsletter_processing_error_handling():
    """Test error handling in newsletter processing pipeline."""
    
    from src.services.newsletter_processor import NewsletterProcessor
    from src.lib.exceptions import ProcessingError, LLMServiceError
    
    processor = NewsletterProcessor()
    
    # Test LLM service failure
    with patch('src.services.llm_summarizer.LLMSummarizer.summarize') as mock_summarize:
        mock_summarize.side_effect = LLMServiceError("LLM service unavailable")
        
        with pytest.raises(ProcessingError) as exc_info:
            await processor.process_newsletter(
                title="Test Newsletter",
                content="This is test content for error handling scenario."
            )
        
        assert "LLM service unavailable" in str(exc_info.value)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_newsletter_processing():
    """Test concurrent processing of multiple newsletters."""
    
    from src.services.newsletter_processor import NewsletterProcessor
    
    processor = NewsletterProcessor()
    
    # Create multiple newsletters to process concurrently
    newsletters = [
        {
            "title": f"Newsletter {i}",
            "content": f"This is the content for newsletter {i} with sufficient length for processing and validation requirements."
        }
        for i in range(3)
    ]
    
    # Process all newsletters concurrently
    tasks = [
        processor.process_newsletter(**newsletter)
        for newsletter in newsletters
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Verify all processing completed successfully
    assert len(results) == 3, "Should have 3 results"
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            pytest.fail(f"Newsletter {i} processing failed: {result}")
        
        assert "newsletter" in result
        assert "episode" in result
        assert result["newsletter"].title == f"Newsletter {i}"


@pytest.mark.integration
@pytest.mark.asyncio  
async def test_processing_performance_requirements():
    """Test that processing meets performance requirements."""
    import time
    
    from src.services.newsletter_processor import NewsletterProcessor
    
    processor = NewsletterProcessor()
    
    # Medium-sized newsletter content (similar to real newsletters)
    content = """
    # Technology Weekly Update
    
    This week brought significant developments across multiple technology sectors.
    Artificial intelligence continues to advance with new breakthroughs in natural
    language processing and computer vision capabilities.
    
    ## AI Developments
    - Large language models show improved reasoning capabilities
    - Computer vision models achieve better accuracy on complex tasks
    - Edge AI deployment becomes more accessible for enterprises
    
    ## Cloud Computing Trends  
    - Multi-cloud strategies gain adoption among large enterprises
    - Serverless architectures handle more complex use cases
    - Container orchestration platforms evolve with better security
    
    ## Cybersecurity Updates
    - Zero-trust architectures become standard practice
    - AI-powered threat detection improves response times  
    - Supply chain security receives increased attention
    
    The convergence of these technologies creates new opportunities while
    introducing novel challenges for organizations worldwide.
    """ * 5  # Repeat to simulate longer newsletter
    
    start_time = time.time()
    
    result = await processor.process_newsletter(
        title="Performance Test Newsletter",
        content=content
    )
    
    processing_time = time.time() - start_time
    
    # Performance requirements from plan.md: 10min newsletter processing
    assert processing_time < 600, f"Processing took {processing_time:.2f}s, should be < 600s"
    
    # Verify quality of result despite performance focus
    newsletter = result["newsletter"]
    episode = result["episode"]
    
    assert newsletter.status == "completed"
    assert len(episode.summary_text) > 100, "Summary should be substantial"
    assert episode.duration_seconds > 30, "Audio should be reasonable length"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_processing_with_different_ai_providers():
    """Test processing with different AI service providers."""
    
    from src.services.newsletter_processor import NewsletterProcessor
    from src.lib.config import get_settings
    
    processor = NewsletterProcessor()
    content = "This is test content for AI provider testing with sufficient length for validation."
    
    # Test with different LLM providers
    llm_providers = ["ollama", "openai"]
    tts_providers = ["kokoro_tts"]
    
    for llm_provider in llm_providers:
        for tts_provider in tts_providers:
            # Mock configuration
            with patch('src.lib.config.get_settings') as mock_settings:
                mock_config = MagicMock()
                mock_config.ai_services.llm.provider = llm_provider
                mock_config.ai_services.tts.provider = tts_provider
                mock_settings.return_value = mock_config
                
                # Mock service responses
                with patch('src.services.llm_summarizer.LLMSummarizer.summarize') as mock_summarize, \
                     patch('src.services.tts_generator.TTSGenerator.generate_audio') as mock_tts:
                    
                    mock_summarize.return_value = f"Summary by {llm_provider}"
                    mock_tts.return_value = "/tmp/test_audio.mp3"
                    
                    result = await processor.process_newsletter(
                        title=f"Test with {llm_provider}-{tts_provider}",
                        content=content
                    )
                    
                    # Verify provider-specific processing
                    episode = result["episode"] 
                    assert llm_provider.lower() in episode.summary_text.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_newsletter_deduplication():
    """Test that duplicate newsletters are properly detected."""
    
    from src.services.newsletter_processor import NewsletterProcessor
    from src.lib.exceptions import DuplicateContentError
    
    processor = NewsletterProcessor()
    content = "This is unique content for deduplication testing with sufficient length."
    
    # Process first newsletter
    result1 = await processor.process_newsletter(
        title="First Newsletter",
        content=content
    )
    
    # Try to process same content again
    with pytest.raises(DuplicateContentError) as exc_info:
        await processor.process_newsletter(
            title="Duplicate Newsletter", 
            content=content
        )
    
    # Verify error contains reference to existing newsletter
    assert result1["newsletter"].id in str(exc_info.value.details.get("existing_id", ""))


# Fixtures for integration tests
@pytest.fixture
async def newsletter_processor():
    """Fixture providing configured newsletter processor."""
    from src.services.newsletter_processor import NewsletterProcessor
    processor = NewsletterProcessor()
    await processor.initialize()
    yield processor
    await processor.shutdown()


@pytest.fixture
def sample_newsletter_content():
    """Fixture providing sample newsletter content."""
    return """
    # Weekly Technology Report
    
    This week's report covers the latest developments in software engineering,
    artificial intelligence, and cloud computing platforms.
    
    ## Software Engineering
    - New frameworks for better developer productivity
    - Improved testing methodologies and automation tools
    - Enhanced security practices for application development
    
    ## Artificial Intelligence  
    - Advances in machine learning model efficiency
    - Better natural language understanding capabilities
    - Improved computer vision for practical applications
    
    ## Cloud Computing
    - Enhanced container orchestration features
    - Better cost optimization tools and practices
    - Improved security and compliance capabilities
    
    These developments continue to shape how organizations build and
    deploy technology solutions in an increasingly digital world.
    """


@pytest.fixture
def mock_ai_services():
    """Fixture providing mock AI services."""
    with patch('src.services.llm_summarizer.LLMSummarizer') as mock_llm, \
         patch('src.services.tts_generator.TTSGenerator') as mock_tts:
        
        # Configure mock responses
        mock_llm.return_value.summarize = AsyncMock(return_value="Mocked summary")
        mock_tts.return_value.generate_audio = AsyncMock(return_value="/tmp/mock_audio.mp3")
        
        yield {
            "llm": mock_llm.return_value,
            "tts": mock_tts.return_value
        }
