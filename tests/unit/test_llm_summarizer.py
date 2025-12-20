"""
Unit tests for LLM summarization service.

These tests verify the LLMSummarizer service functionality
for generating summaries using different LLM providers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_summarizer_initialization():
    """Test LLMSummarizer service initialization."""
    from src.services.llm_summarizer import LLMSummarizer
    
    summarizer = LLMSummarizer()
    
    # Test service initialization
    await summarizer.initialize()
    
    assert summarizer.is_initialized is True
    assert summarizer.name == "llm_summarizer"
    assert summarizer.provider_name is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ollama_provider_initialization():
    """Test Ollama LLM provider initialization."""
    from src.services.llm_summarizer import LLMSummarizer
    
    # Mock configuration for Ollama
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.llm.provider = "ollama"
        mock_config.ai_services.llm.ollama.base_url = "http://localhost:11434"
        mock_config.ai_services.llm.ollama.model = "llama2"
        mock_config.ai_services.llm.ollama.timeout = 300
        mock_settings.return_value = mock_config
        
        summarizer = LLMSummarizer()
        await summarizer.initialize()
        
        assert summarizer.provider_name == "ollama"
        assert summarizer.provider_config["base_url"] == "http://localhost:11434"
        assert summarizer.provider_config["model"] == "llama2"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_provider_initialization():
    """Test OpenAI LLM provider initialization."""
    from src.services.llm_summarizer import LLMSummarizer
    
    # Mock configuration for OpenAI
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.llm.provider = "openai"
        mock_config.ai_services.llm.openai.api_key = "test-api-key"
        mock_config.ai_services.llm.openai.model = "gpt-3.5-turbo"
        mock_config.ai_services.llm.openai.max_tokens = 2000
        mock_settings.return_value = mock_config
        
        summarizer = LLMSummarizer()
        await summarizer.initialize()
        
        assert summarizer.provider_name == "openai"
        assert summarizer.provider_config["api_key"] == "test-api-key"
        assert summarizer.provider_config["model"] == "gpt-3.5-turbo"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_summarize_with_ollama():
    """Test content summarization using Ollama provider."""
    from src.services.llm_summarizer import LLMSummarizer
    
    newsletter_content = """
    # Weekly Technology Report
    
    This week brought significant developments in artificial intelligence and cloud computing.
    
    ## AI Developments
    - New language models show improved reasoning capabilities
    - Computer vision advances in autonomous vehicle applications
    - Natural language processing breakthroughs in translation
    
    ## Cloud Computing
    - Kubernetes adoption reaches new milestones
    - Serverless architectures gain enterprise traction
    - Multi-cloud strategies become standard practice
    
    The convergence of these technologies continues to reshape how organizations
    approach digital transformation and operational efficiency.
    """
    
    expected_summary = """This week's technology report highlights major AI and cloud computing advances. Key AI developments include improved language models, computer vision progress for autonomous vehicles, and NLP translation breakthroughs. Cloud computing sees Kubernetes reaching new adoption milestones, serverless gaining enterprise acceptance, and multi-cloud becoming standard. These converging technologies are transforming organizational digital strategies."""
    
    # Mock Ollama configuration
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.llm.provider = "ollama"
        mock_config.ai_services.llm.ollama.base_url = "http://localhost:11434"
        mock_config.ai_services.llm.ollama.model = "llama2"
        mock_settings.return_value = mock_config
        
        summarizer = LLMSummarizer()
        await summarizer.initialize()
        
        # Mock Ollama API response
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "response": expected_summary,
                "done": True
            })
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await summarizer.summarize(newsletter_content)
            
            # Verify summarization
            assert result == expected_summary
            assert len(result) < len(newsletter_content)  # Should be shorter
            assert "AI" in result or "artificial intelligence" in result
            assert "cloud" in result.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_summarize_with_openai():
    """Test content summarization using OpenAI provider."""
    from src.services.llm_summarizer import LLMSummarizer
    
    newsletter_content = """
    # Tech Industry Weekly Update
    
    Major developments this week include new AI model releases and cloud platform updates.
    Companies are investing heavily in machine learning capabilities while improving
    infrastructure scalability and security measures.
    """
    
    expected_summary = "This week's tech update covers new AI model releases and cloud platform improvements, with companies investing in ML capabilities and infrastructure security."
    
    # Mock OpenAI configuration
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.llm.provider = "openai"
        mock_config.ai_services.llm.openai.api_key = "test-key"
        mock_config.ai_services.llm.openai.model = "gpt-3.5-turbo"
        mock_settings.return_value = mock_config
        
        summarizer = LLMSummarizer()
        await summarizer.initialize()
        
        # Mock OpenAI client
        with patch('openai.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_completion = AsyncMock()
            mock_completion.choices = [
                MagicMock(message=MagicMock(content=expected_summary))
            ]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
            mock_openai.return_value = mock_client
            
            result = await summarizer.summarize(newsletter_content)
            
            assert result == expected_summary
            assert len(result) < len(newsletter_content)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_summarize_error_handling():
    """Test error handling in LLM summarization."""
    from src.services.llm_summarizer import LLMSummarizer
    from src.lib.exceptions import LLMServiceError
    
    content = "Test content for error handling scenario."
    
    # Test Ollama service error
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.llm.provider = "ollama"
        mock_config.ai_services.llm.ollama.base_url = "http://localhost:11434"
        mock_settings.return_value = mock_config
        
        summarizer = LLMSummarizer()
        await summarizer.initialize()
        
        # Mock HTTP error
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(LLMServiceError) as exc_info:
                await summarizer.summarize(content)
            
            assert "500" in str(exc_info.value)
            assert exc_info.value.provider == "ollama"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_summarize_timeout_handling():
    """Test timeout handling in LLM summarization."""
    from src.services.llm_summarizer import LLMSummarizer
    from src.lib.exceptions import LLMServiceError
    import asyncio
    
    content = "Test content for timeout scenario."
    
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.llm.provider = "ollama"
        mock_config.ai_services.llm.ollama.timeout = 1  # Very short timeout
        mock_settings.return_value = mock_config
        
        summarizer = LLMSummarizer()
        await summarizer.initialize()
        
        # Mock timeout
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError("Request timeout")
            
            with pytest.raises(LLMServiceError) as exc_info:
                await summarizer.summarize(content)
            
            assert "timeout" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_summarize_content_validation():
    """Test content validation before summarization."""
    from src.services.llm_summarizer import LLMSummarizer
    from src.lib.exceptions import ValidationError
    
    summarizer = LLMSummarizer()
    await summarizer.initialize()
    
    # Test empty content
    with pytest.raises(ValidationError):
        await summarizer.summarize("")
    
    # Test very short content
    with pytest.raises(ValidationError):
        await summarizer.summarize("Too short")
    
    # Test very long content (over limit)
    very_long_content = "Word " * 20000  # Exceeds typical token limits
    with pytest.raises(ValidationError) as exc_info:
        await summarizer.summarize(very_long_content)
    assert "too long" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_summary_prompt():
    """Test summary prompt generation."""
    from src.services.llm_summarizer import LLMSummarizer
    
    content = "Sample newsletter content about technology developments."
    
    summarizer = LLMSummarizer()
    await summarizer.initialize()
    
    prompt = summarizer._generate_summary_prompt(content)
    
    # Verify prompt structure
    assert isinstance(prompt, str)
    assert content in prompt
    assert "summarize" in prompt.lower()
    assert "newsletter" in prompt.lower()
    assert "podcast" in prompt.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_process_summary():
    """Test summary post-processing."""
    from src.services.llm_summarizer import LLMSummarizer
    
    # Test various summary formats that need cleaning
    test_cases = [
        {
            "raw_summary": "  Summary: This is the actual summary content.  ",
            "expected": "This is the actual summary content."
        },
        {
            "raw_summary": "Here's a summary:\n\nThis is the main content.\n\nEnd of summary.",
            "expected": "This is the main content."
        },
        {
            "raw_summary": "**Summary:** This is bold summary content.",
            "expected": "This is bold summary content."
        }
    ]
    
    summarizer = LLMSummarizer()
    
    for test_case in test_cases:
        result = summarizer._post_process_summary(test_case["raw_summary"])
        assert test_case["expected"] in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_check():
    """Test LLMSummarizer health check."""
    from src.services.llm_summarizer import LLMSummarizer
    
    summarizer = LLMSummarizer()
    
    # Health check before initialization
    health = await summarizer.health_check()
    assert health.is_healthy is False
    
    # Health check after initialization
    await summarizer.initialize()
    health = await summarizer.health_check()
    assert health.is_healthy is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_provider_switching():
    """Test switching between LLM providers."""
    from src.services.llm_summarizer import LLMSummarizer
    
    content = "Test content for provider switching."
    
    # Test with Ollama first
    with patch('src.lib.config.get_settings') as mock_settings:
        mock_config = MagicMock()
        mock_config.ai_services.llm.provider = "ollama"
        mock_config.ai_services.llm.ollama.base_url = "http://localhost:11434"
        mock_settings.return_value = mock_config
        
        summarizer = LLMSummarizer()
        await summarizer.initialize()
        
        assert summarizer.provider_name == "ollama"
        
        # Reinitialize with OpenAI
        mock_config.ai_services.llm.provider = "openai"
        mock_config.ai_services.llm.openai.api_key = "test-key"
        
        await summarizer.shutdown()
        await summarizer.initialize()
        
        assert summarizer.provider_name == "openai"


# Fixtures for LLM summarizer tests
@pytest.fixture
async def llm_summarizer():
    """Fixture providing initialized LLMSummarizer."""
    from src.services.llm_summarizer import LLMSummarizer
    summarizer = LLMSummarizer()
    await summarizer.initialize()
    yield summarizer
    await summarizer.shutdown()


@pytest.fixture
def sample_newsletter_content():
    """Fixture providing sample newsletter content for summarization."""
    return """
    # Weekly Developer Newsletter
    
    Welcome to this week's developer newsletter covering the latest in software engineering,
    artificial intelligence, and cloud technologies.
    
    ## Software Engineering Updates
    - New JavaScript framework releases with improved performance
    - TypeScript 5.0 introduces major language enhancements
    - React Server Components reach stable release
    - Docker Desktop updates improve container development workflow
    
    ## AI and Machine Learning
    - Large language models show improved code generation capabilities
    - Computer vision models achieve better accuracy on edge devices
    - MLOps platforms introduce new automated deployment features
    - AI-powered code review tools gain adoption in enterprises
    
    ## Cloud and Infrastructure
    - Kubernetes 1.28 brings enhanced security and performance
    - Serverless platforms reduce cold start times significantly
    - Multi-cloud management tools simplify infrastructure oversight
    - Edge computing solutions expand global availability
    
    ## Developer Tools and Practices
    - IDEs integrate more AI-powered coding assistants
    - Testing frameworks evolve with better async support
    - CI/CD pipelines incorporate advanced security scanning
    - Code quality tools provide more actionable insights
    
    These developments continue to shape how developers build, deploy, and maintain
    applications in an increasingly complex technological landscape.
    """


@pytest.fixture
def expected_summary():
    """Fixture providing expected summary format."""
    return """This week's developer newsletter highlights key advances in software engineering, AI/ML, and cloud technologies. JavaScript and TypeScript see major framework updates while React Server Components reach stability. AI improvements include better code generation and edge device vision models, plus growing MLOps automation. Cloud updates feature Kubernetes 1.28 enhancements and reduced serverless cold starts. Developer tools gain AI integration, better testing async support, and improved CI/CD security scanning."""