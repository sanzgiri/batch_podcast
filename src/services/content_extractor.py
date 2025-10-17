"""
Content Extractor Service for Newsletter Podcast Generator.

This service extracts and cleans text content from various newsletter formats,
handling HTML, markdown, and plain text with intelligent content detection
and processing.
"""

import re
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

import aiohttp
from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify
import html2text

from src.lib.config import Config
from src.lib.logging import get_logger
from src.lib.exceptions import ContentExtractionError, ValidationError
from src.lib.utils import clean_text, is_valid_url, truncate_text


logger = get_logger(__name__)


@dataclass
class ExtractedContent:
    """Container for extracted newsletter content."""
    
    title: str
    content: str
    summary: str
    word_count: int
    content_type: str  # 'html', 'markdown', 'text'
    source_url: Optional[str] = None
    author: Optional[str] = None
    publication_date: Optional[str] = None
    images: list[str] = None
    links: list[str] = None
    
    def __post_init__(self):
        if self.images is None:
            self.images = []
        if self.links is None:
            self.links = []


class ContentExtractor:
    """
    Service for extracting and cleaning newsletter content.
    
    Handles various input formats and provides intelligent content extraction
    with configurable cleaning and processing options.
    """
    
    def __init__(self, config: Config):
        """Initialize ContentExtractor with configuration."""
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Content extraction settings
        self.max_content_length = config.content.max_content_length
        self.min_content_length = config.content.min_content_length
        self.remove_ads = config.content.remove_ads
        self.preserve_links = config.content.preserve_links
        
        # HTML to text converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = not self.preserve_links
        self.html_converter.ignore_images = True
        self.html_converter.body_width = 0  # No line wrapping
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Newsletter-Podcast-Generator/1.0 (+https://example.com)'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def extract_from_url(self, url: str) -> ExtractedContent:
        """
        Extract content from a newsletter URL.
        
        Args:
            url: Newsletter URL to extract content from
            
        Returns:
            ExtractedContent with extracted and cleaned content
            
        Raises:
            ContentExtractionError: If extraction fails
            ValidationError: If URL is invalid
        """
        if not is_valid_url(url):
            raise ValidationError(f"Invalid URL format: {url}")
        
        if not self.session:
            raise ContentExtractionError("ContentExtractor must be used as async context manager")
        
        logger.info(f"Extracting content from URL: {url}")
        
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                html_content = await response.text()
                
                # Extract content from HTML
                extracted = await self._extract_from_html(
                    html_content, 
                    source_url=url
                )
                
                logger.info(
                    f"Successfully extracted content from {url}: "
                    f"{extracted.word_count} words, type: {extracted.content_type}"
                )
                
                return extracted
                
        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch URL {url}: {e}")
            raise ContentExtractionError(f"Failed to fetch content from {url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error extracting from URL {url}: {e}")
            raise ContentExtractionError(f"Content extraction failed: {e}")
    
    async def extract_from_text(
        self, 
        content: str, 
        content_type: str = "text",
        title: Optional[str] = None
    ) -> ExtractedContent:
        """
        Extract content from raw text/HTML/markdown.
        
        Args:
            content: Raw content string
            content_type: Type of content ('html', 'markdown', 'text')
            title: Optional title (will be extracted if not provided)
            
        Returns:
            ExtractedContent with processed content
            
        Raises:
            ContentExtractionError: If extraction fails
            ValidationError: If content is invalid
        """
        if not content or not content.strip():
            raise ValidationError("Content cannot be empty")
        
        logger.info(f"Extracting content from {content_type} text ({len(content)} chars)")
        
        try:
            if content_type.lower() == "html":
                return await self._extract_from_html(content, title=title)
            elif content_type.lower() == "markdown":
                return await self._extract_from_markdown(content, title=title)
            else:
                return await self._extract_from_plain_text(content, title=title)
                
        except Exception as e:
            logger.error(f"Failed to extract from {content_type} content: {e}")
            raise ContentExtractionError(f"Content extraction failed: {e}")
    
    async def _extract_from_html(
        self, 
        html_content: str, 
        source_url: Optional[str] = None,
        title: Optional[str] = None
    ) -> ExtractedContent:
        """Extract content from HTML."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            self._remove_unwanted_elements(soup)
            
            # Extract metadata
            extracted_title = title or self._extract_title(soup)
            author = self._extract_author(soup)
            pub_date = self._extract_publication_date(soup)
            
            # Extract main content
            main_content = self._extract_main_content(soup)
            
            # Convert HTML to clean text
            clean_content = self.html_converter.handle(str(main_content))
            clean_content = clean_text(clean_content)
            
            # Validate content length
            self._validate_content_length(clean_content)
            
            # Extract images and links
            images = self._extract_images(main_content, source_url)
            links = self._extract_links(main_content, source_url)
            
            # Generate summary
            summary = self._generate_summary(clean_content)
            
            return ExtractedContent(
                title=extracted_title,
                content=clean_content,
                summary=summary,
                word_count=len(clean_content.split()),
                content_type="html",
                source_url=source_url,
                author=author,
                publication_date=pub_date,
                images=images,
                links=links
            )
            
        except Exception as e:
            logger.error(f"HTML content extraction failed: {e}")
            raise ContentExtractionError(f"Failed to parse HTML content: {e}")
    
    async def _extract_from_markdown(
        self, 
        markdown_content: str, 
        title: Optional[str] = None
    ) -> ExtractedContent:
        """Extract content from Markdown."""
        try:
            # Convert markdown to HTML first for consistent processing
            html_content = markdownify(markdown_content, convert=['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            
            # Extract title from first heading if not provided
            if not title:
                title_match = re.search(r'^#\s+(.+)$', markdown_content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else "Untitled Newsletter"
            
            # Clean content
            clean_content = clean_text(markdown_content)
            
            # Validate content length
            self._validate_content_length(clean_content)
            
            # Extract links
            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            links = [match.group(2) for match in re.finditer(link_pattern, markdown_content)]
            
            # Extract images
            image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
            images = [match.group(2) for match in re.finditer(image_pattern, markdown_content)]
            
            # Generate summary
            summary = self._generate_summary(clean_content)
            
            return ExtractedContent(
                title=title,
                content=clean_content,
                summary=summary,
                word_count=len(clean_content.split()),
                content_type="markdown",
                images=images,
                links=links
            )
            
        except Exception as e:
            logger.error(f"Markdown content extraction failed: {e}")
            raise ContentExtractionError(f"Failed to parse Markdown content: {e}")
    
    async def _extract_from_plain_text(
        self, 
        text_content: str, 
        title: Optional[str] = None
    ) -> ExtractedContent:
        """Extract content from plain text."""
        try:
            # Clean content
            clean_content = clean_text(text_content)
            
            # Extract title from first line if not provided
            if not title:
                lines = clean_content.split('\n')
                title = lines[0].strip() if lines else "Untitled Newsletter"
                if len(title) > 100:  # If first line is too long, truncate
                    title = truncate_text(title, 100)
            
            # Validate content length
            self._validate_content_length(clean_content)
            
            # Extract URLs
            url_pattern = r'https?://[^\s<>"\'{}|\\^`\[\]]+[^\s<>"\'{}|\\^`\[\].,;:!?)]'
            links = re.findall(url_pattern, text_content)
            
            # Generate summary
            summary = self._generate_summary(clean_content)
            
            return ExtractedContent(
                title=title,
                content=clean_content,
                summary=summary,
                word_count=len(clean_content.split()),
                content_type="text",
                links=links
            )
            
        except Exception as e:
            logger.error(f"Plain text content extraction failed: {e}")
            raise ContentExtractionError(f"Failed to parse plain text content: {e}")
    
    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """Remove unwanted HTML elements."""
        # Elements to remove completely
        unwanted_tags = [
            'script', 'style', 'nav', 'footer', 'header', 'aside',
            'iframe', 'object', 'embed', 'form', 'input', 'button'
        ]
        
        for tag_name in unwanted_tags:
            for element in soup.find_all(tag_name):
                element.decompose()
        
        # Remove elements with common ad/navigation classes
        if self.remove_ads:
            ad_patterns = [
                'ad', 'advertisement', 'promo', 'sponsor', 'banner',
                'nav', 'navigation', 'menu', 'sidebar', 'widget',
                'social', 'share', 'comment', 'footer', 'header'
            ]
            
            for pattern in ad_patterns:
                # Remove by class
                for element in soup.find_all(class_=lambda x: x and pattern in x.lower()):
                    element.decompose()
                
                # Remove by id
                for element in soup.find_all(id=lambda x: x and pattern in x.lower()):
                    element.decompose()
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract title from HTML."""
        # Try different title sources in order of preference
        title_selectors = [
            'h1',
            'title',
            '[property="og:title"]',
            '[name="twitter:title"]',
            '.title',
            '.headline'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True) if hasattr(element, 'get_text') else element.get('content', '')
                if title and len(title.strip()) > 0:
                    return clean_text(title)[:200]  # Limit title length
        
        return "Untitled Newsletter"
    
    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract author from HTML."""
        author_selectors = [
            '[rel="author"]',
            '[property="article:author"]',
            '[name="author"]',
            '.author',
            '.byline'
        ]
        
        for selector in author_selectors:
            element = soup.select_one(selector)
            if element:
                author = element.get_text(strip=True) if hasattr(element, 'get_text') else element.get('content', '')
                if author and len(author.strip()) > 0:
                    return clean_text(author)[:100]
        
        return None
    
    def _extract_publication_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract publication date from HTML."""
        date_selectors = [
            '[property="article:published_time"]',
            '[property="article:modified_time"]',
            '[name="publish-date"]',
            'time[datetime]',
            '.date',
            '.published'
        ]
        
        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                date = element.get('datetime') or element.get('content') or element.get_text(strip=True)
                if date and len(date.strip()) > 0:
                    return date.strip()
        
        return None
    
    def _extract_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Extract main content area from HTML."""
        # Try different content area selectors
        content_selectors = [
            'article',
            '[role="main"]',
            'main',
            '.content',
            '.post-content',
            '.entry-content',
            '.article-content',
            '#content'
        ]
        
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content and content.get_text(strip=True):
                return content
        
        # Fallback: remove obvious non-content and return body
        body = soup.find('body') or soup
        return body
    
    def _extract_images(self, content: BeautifulSoup, base_url: Optional[str] = None) -> list[str]:
        """Extract image URLs from content."""
        images = []
        
        for img in content.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src:
                # Convert relative URLs to absolute
                if base_url and not src.startswith(('http://', 'https://')):
                    src = urljoin(base_url, src)
                
                if is_valid_url(src):
                    images.append(src)
        
        return list(set(images))  # Remove duplicates
    
    def _extract_links(self, content: BeautifulSoup, base_url: Optional[str] = None) -> list[str]:
        """Extract links from content."""
        links = []
        
        for link in content.find_all('a', href=True):
            href = link.get('href')
            if href:
                # Convert relative URLs to absolute
                if base_url and not href.startswith(('http://', 'https://')):
                    href = urljoin(base_url, href)
                
                if is_valid_url(href):
                    links.append(href)
        
        return list(set(links))  # Remove duplicates
    
    def _validate_content_length(self, content: str) -> None:
        """Validate content length against configured limits."""
        word_count = len(content.split())
        
        if word_count < self.min_content_length:
            raise ValidationError(
                f"Content too short: {word_count} words "
                f"(minimum: {self.min_content_length})"
            )
        
        if word_count > self.max_content_length:
            logger.warning(
                f"Content exceeds maximum length: {word_count} words "
                f"(maximum: {self.max_content_length}), truncating"
            )
            # Truncate to max length
            words = content.split()[:self.max_content_length]
            content = ' '.join(words)
    
    def _generate_summary(self, content: str, max_length: int = 300) -> str:
        """Generate a summary from content."""
        # Simple extractive summary: first paragraph or sentences up to max_length
        sentences = re.split(r'[.!?]+', content)
        summary = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(summary + sentence) > max_length:
                break
                
            summary += sentence + ". "
        
        return summary.strip() or truncate_text(content, max_length)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return {
            "max_content_length": self.max_content_length,
            "min_content_length": self.min_content_length,
            "remove_ads": self.remove_ads,
            "preserve_links": self.preserve_links
        }