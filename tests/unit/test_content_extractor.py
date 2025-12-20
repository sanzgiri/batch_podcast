"""
Unit tests for content extraction service.

These tests verify the ContentExtractor service functionality
for extracting and cleaning content from various sources.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any


@pytest.mark.unit
@pytest.mark.asyncio
async def test_content_extractor_initialization():
    """Test ContentExtractor service initialization."""
    # Should fail until ContentExtractor is implemented
    from src.services.content_extractor import ContentExtractor
    
    extractor = ContentExtractor()
    
    # Test service initialization
    await extractor.initialize()
    
    assert extractor.is_initialized is True
    assert extractor.name == "content_extractor"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_from_url_success():
    """Test successful content extraction from URL."""
    from src.services.content_extractor import ContentExtractor
    
    # Mock HTML content
    mock_html = """
    <html>
    <head><title>Test Newsletter</title></head>
    <body>
        <article>
            <h1>Weekly Tech Update</h1>
            <p>This is the main content of the newsletter with important
               technology news and updates for developers.</p>
            <p>Additional paragraph with more detailed information about
               recent developments in the software industry.</p>
        </article>
        <footer>Footer content that should be filtered out</footer>
    </body>
    </html>
    """
    
    expected_content = """Weekly Tech Update

This is the main content of the newsletter with important technology news and updates for developers.

Additional paragraph with more detailed information about recent developments in the software industry."""
    
    extractor = ContentExtractor()
    await extractor.initialize()
    
    # Mock HTTP request
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=mock_html)
        mock_get.return_value.__aenter__.return_value = mock_response
        
        result = await extractor.extract_from_url("https://example.com/newsletter")
        
        # Verify extraction
        assert isinstance(result, str)
        assert "Weekly Tech Update" in result
        assert "main content of the newsletter" in result
        assert "Footer content" not in result  # Should filter out footer
        assert len(result.strip()) > 50  # Should have substantial content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_from_url_with_different_content_types():
    """Test content extraction from different HTML structures."""
    from src.services.content_extractor import ContentExtractor
    
    test_cases = [
        # Blog post structure
        {
            "html": """
            <html><body>
                <div class="post-content">
                    <h1>Blog Post Title</h1>
                    <div class="content">
                        <p>Blog post content here</p>
                    </div>
                </div>
            </body></html>
            """,
            "expected_content": ["Blog Post Title", "Blog post content here"]
        },
        # Newsletter structure
        {
            "html": """
            <html><body>
                <div id="newsletter">
                    <h2>Newsletter Headline</h2>
                    <section>
                        <p>Newsletter section content</p>
                    </section>
                </div>
            </body></html>
            """,
            "expected_content": ["Newsletter Headline", "Newsletter section content"]
        },
        # Article structure
        {
            "html": """
            <html><body>
                <main>
                    <article>
                        <header><h1>Article Title</h1></header>
                        <p>Article body content with important information</p>
                    </article>
                </main>
            </body></html>
            """,
            "expected_content": ["Article Title", "Article body content"]
        }
    ]
    
    extractor = ContentExtractor()
    await extractor.initialize()
    
    for i, test_case in enumerate(test_cases):
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=test_case["html"])
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await extractor.extract_from_url(f"https://example.com/test{i}")
            
            # Verify expected content is present
            for expected in test_case["expected_content"]:
                assert expected in result, f"Expected '{expected}' in extracted content"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_from_url_error_handling():
    """Test error handling in URL content extraction."""
    from src.services.content_extractor import ContentExtractor
    from src.lib.exceptions import ContentExtractionError
    
    extractor = ContentExtractor()
    await extractor.initialize()
    
    # Test HTTP error
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_get.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(ContentExtractionError) as exc_info:
            await extractor.extract_from_url("https://example.com/not-found")
        
        assert "404" in str(exc_info.value)
        assert exc_info.value.details["status_code"] == 404


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_from_url_timeout_handling():
    """Test timeout handling in URL content extraction."""
    from src.services.content_extractor import ContentExtractor
    from src.lib.exceptions import ContentExtractionError
    import asyncio
    
    extractor = ContentExtractor()
    await extractor.initialize()
    
    # Mock timeout
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.side_effect = asyncio.TimeoutError("Request timeout")
        
        with pytest.raises(ContentExtractionError) as exc_info:
            await extractor.extract_from_url("https://slow-example.com/newsletter")
        
        assert "timeout" in str(exc_info.value).lower()


@pytest.mark.unit
def test_clean_html_content():
    """Test HTML content cleaning functionality."""
    from src.services.content_extractor import ContentExtractor
    
    # Test various HTML cleaning scenarios
    test_cases = [
        {
            "html": "<p>Simple paragraph</p>",
            "expected": "Simple paragraph"
        },
        {
            "html": "<div><h1>Title</h1><p>Content</p></div>",
            "expected": "Title\n\nContent"
        },
        {
            "html": "<script>alert('evil')</script><p>Safe content</p>",
            "expected": "Safe content"
        },
        {
            "html": "<style>body{color:red}</style><p>Content</p>",
            "expected": "Content"
        },
        {
            "html": "<p>Content with <a href='#'>link</a> and <strong>bold</strong></p>",
            "expected": "Content with link and bold"
        }
    ]
    
    extractor = ContentExtractor()
    
    for test_case in test_cases:
        result = extractor._clean_html_content(test_case["html"])
        assert test_case["expected"] in result.strip()


@pytest.mark.unit
def test_extract_main_content():
    """Test main content extraction from complex HTML."""
    from src.services.content_extractor import ContentExtractor
    
    complex_html = """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <nav>Navigation menu that should be ignored</nav>
        <aside>Sidebar content to ignore</aside>
        <main>
            <article>
                <h1>Main Article Title</h1>
                <p>This is the main content that should be extracted.</p>
                <p>Additional paragraph with important information.</p>
            </article>
        </main>
        <div class="ads">Advertisement content to ignore</div>
        <footer>Footer content to ignore</footer>
    </body>
    </html>
    """
    
    extractor = ContentExtractor()
    result = extractor._extract_main_content(complex_html)
    
    # Should extract main content
    assert "Main Article Title" in result
    assert "main content that should be extracted" in result
    assert "Additional paragraph" in result
    
    # Should ignore navigation, sidebar, ads, footer
    assert "Navigation menu" not in result
    assert "Sidebar content" not in result
    assert "Advertisement content" not in result
    assert "Footer content" not in result


@pytest.mark.unit
def test_validate_extracted_content():
    """Test content validation after extraction."""
    from src.services.content_extractor import ContentExtractor
    from src.lib.exceptions import ValidationError
    
    extractor = ContentExtractor()
    
    # Test valid content
    valid_content = "This is valid content with sufficient length for newsletter processing and validation requirements."
    assert extractor._validate_content(valid_content) is True
    
    # Test too short content
    short_content = "Too short"
    with pytest.raises(ValidationError) as exc_info:
        extractor._validate_content(short_content)
    assert "content too short" in str(exc_info.value).lower()
    
    # Test empty content
    with pytest.raises(ValidationError):
        extractor._validate_content("")
    
    # Test whitespace-only content
    with pytest.raises(ValidationError):
        extractor._validate_content("   \n  \t  ")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_with_rate_limiting():
    """Test rate limiting in content extraction."""
    from src.services.content_extractor import ContentExtractor
    
    extractor = ContentExtractor()
    await extractor.initialize()
    
    # Test multiple rapid requests
    urls = [f"https://example.com/page{i}" for i in range(5)]
    
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<p>Test content</p>")
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Should handle multiple requests without errors
        tasks = [extractor.extract_from_url(url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert all("Test content" in result for result in results)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_check():
    """Test ContentExtractor health check."""
    from src.services.content_extractor import ContentExtractor
    
    extractor = ContentExtractor()
    
    # Health check before initialization
    health = await extractor.health_check()
    assert health.is_healthy is False
    
    # Health check after initialization
    await extractor.initialize()
    health = await extractor.health_check()
    assert health.is_healthy is True
    assert "healthy" in health.message.lower()


# Fixtures for content extractor tests
@pytest.fixture
async def content_extractor():
    """Fixture providing initialized ContentExtractor."""
    from src.services.content_extractor import ContentExtractor
    extractor = ContentExtractor()
    await extractor.initialize()
    yield extractor
    await extractor.shutdown()


@pytest.fixture
def sample_html_content():
    """Fixture providing sample HTML content."""
    return """
    <html>
    <head><title>Sample Newsletter</title></head>
    <body>
        <main>
            <h1>Weekly Technology Newsletter</h1>
            <section>
                <h2>AI Developments</h2>
                <p>Recent advances in artificial intelligence have shown
                   promising results in natural language processing.</p>
            </section>
            <section>
                <h2>Cloud Computing</h2>
                <p>Cloud adoption continues to accelerate as organizations
                   seek scalable and cost-effective solutions.</p>
            </section>
        </main>
    </body>
    </html>
    """


@pytest.fixture
def expected_clean_content():
    """Fixture providing expected clean content."""
    return """Weekly Technology Newsletter

AI Developments

Recent advances in artificial intelligence have shown promising results in natural language processing.

Cloud Computing

Cloud adoption continues to accelerate as organizations seek scalable and cost-effective solutions."""