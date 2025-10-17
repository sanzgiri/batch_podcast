"""
LLM Summarizer Service for Newsletter Podcast Generator.

This service provides intelligent summarization and content transformation
using Large Language Models (OpenAI GPT or Ollama local models).
"""

import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

import aiohttp

from src.lib.config import Config
from src.lib.logging import get_logger
from src.lib.exceptions import LLMError, ValidationError, ServiceError
from src.lib.utils import clean_text, truncate_text


logger = get_logger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    OLLAMA = "ollama"


@dataclass
class SummaryRequest:
    """Request for content summarization."""
    content: str
    title: Optional[str] = None
    style: str = "conversational"  # conversational, formal, casual
    target_length: str = "medium"  # short, medium, long
    focus_areas: List[str] = None
    
    def __post_init__(self):
        if self.focus_areas is None:
            self.focus_areas = []


@dataclass
class SummaryResponse:
    """Response from summarization."""
    summary: str
    title: str
    key_points: List[str]
    word_count: int
    estimated_duration_seconds: int
    provider: str
    model: str
    processing_time: float


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    @abstractmethod
    async def summarize(self, request: SummaryRequest) -> SummaryResponse:
        """Summarize content using the LLM."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM service is available."""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT client implementation."""
    
    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.llm.openai.api_key
        self.model = config.llm.openai.model
        self.base_url = config.llm.openai.base_url
        self.max_tokens = config.llm.openai.max_tokens
        self.temperature = config.llm.openai.temperature
        
        if not self.api_key:
            raise ValidationError("OpenAI API key is required")
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=aiohttp.ClientTimeout(total=60)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def summarize(self, request: SummaryRequest) -> SummaryResponse:
        """Summarize content using OpenAI GPT."""
        if not self.session:
            raise ServiceError("OpenAI client must be used as async context manager")
        
        logger.info(f"Summarizing content with OpenAI {self.model}")
        start_time = time.time()
        
        try:
            # Build the prompt
            prompt = self._build_prompt(request)
            
            # Make API request
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "response_format": {"type": "json_object"}
            }
            
            async with self.session.post(f"{self.base_url}/chat/completions", json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                
                # Parse response
                content = result["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                
                processing_time = time.time() - start_time
                
                # Estimate speech duration (average 150 words per minute)
                word_count = len(parsed["summary"].split())
                estimated_duration = int((word_count / 150) * 60)
                
                return SummaryResponse(
                    summary=parsed["summary"],
                    title=parsed["title"],
                    key_points=parsed["key_points"],
                    word_count=word_count,
                    estimated_duration_seconds=estimated_duration,
                    provider="openai",
                    model=self.model,
                    processing_time=processing_time
                )
                
        except aiohttp.ClientError as e:
            logger.error(f"OpenAI API request failed: {e}")
            raise LLMError(f"OpenAI API request failed: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            raise LLMError(f"Invalid response format from OpenAI: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI summarization: {e}")
            raise LLMError(f"OpenAI summarization failed: {e}")
    
    async def health_check(self) -> bool:
        """Check OpenAI API availability."""
        if not self.session:
            return False
        
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": 1
            }
            
            async with self.session.post(f"{self.base_url}/chat/completions", json=payload) as response:
                return response.status == 200
                
        except Exception:
            return False
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for summarization."""
        return """You are an expert content summarizer specializing in creating engaging podcast scripts from newsletter content.

Your task is to transform newsletter content into compelling podcast-style summaries that are:
- Conversational and engaging for audio consumption
- Well-structured with clear key points
- Appropriate for the target audience
- Optimized for text-to-speech conversion

Always respond with valid JSON in this exact format:
{
    "title": "Engaging podcast episode title",
    "summary": "Full podcast script text that flows naturally when spoken",
    "key_points": ["Point 1", "Point 2", "Point 3"]
}

Guidelines:
- Use natural, conversational language
- Include smooth transitions between topics
- Avoid complex punctuation that doesn't translate well to speech
- Keep sentences at moderate length for natural pacing
- Include brief introductions and conclusions for topics
- Make content accessible and engaging for audio listeners"""
    
    def _build_prompt(self, request: SummaryRequest) -> str:
        """Build the user prompt for summarization."""
        prompt_parts = [
            f"Transform this newsletter content into an engaging podcast episode summary."
        ]
        
        if request.title:
            prompt_parts.append(f"Original title: {request.title}")
        
        # Add style guidance
        style_guidance = {
            "conversational": "Use a friendly, conversational tone as if speaking directly to listeners.",
            "formal": "Use a professional, informative tone suitable for business audiences.", 
            "casual": "Use a relaxed, informal tone with personality and humor where appropriate."
        }
        prompt_parts.append(style_guidance.get(request.style, style_guidance["conversational"]))
        
        # Add length guidance
        length_guidance = {
            "short": "Create a concise summary (2-3 minutes when spoken, ~300-450 words).",
            "medium": "Create a detailed summary (4-6 minutes when spoken, ~600-900 words).",
            "long": "Create a comprehensive summary (7-10 minutes when spoken, ~1000-1500 words)."
        }
        prompt_parts.append(length_guidance.get(request.target_length, length_guidance["medium"]))
        
        # Add focus areas if specified
        if request.focus_areas:
            focus_text = ", ".join(request.focus_areas)
            prompt_parts.append(f"Pay special attention to these topics: {focus_text}")
        
        prompt_parts.append(f"\nNewsletter content:\n{request.content}")
        
        return "\n\n".join(prompt_parts)


class OllamaClient(BaseLLMClient):
    """Ollama local LLM client implementation."""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.llm.ollama.base_url
        self.model = config.llm.ollama.model
        self.temperature = config.llm.ollama.temperature
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=120)  # Longer timeout for local models
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def summarize(self, request: SummaryRequest) -> SummaryResponse:
        """Summarize content using Ollama."""
        if not self.session:
            raise ServiceError("Ollama client must be used as async context manager")
        
        logger.info(f"Summarizing content with Ollama {self.model}")
        start_time = time.time()
        
        try:
            # Build the prompt
            prompt = self._build_full_prompt(request)
            
            # Make API request
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature
                },
                "format": "json"
            }
            
            async with self.session.post(f"{self.base_url}/api/generate", json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                
                # Parse response
                content = result["response"]
                parsed = json.loads(content)
                
                processing_time = time.time() - start_time
                
                # Estimate speech duration
                word_count = len(parsed["summary"].split())
                estimated_duration = int((word_count / 150) * 60)
                
                return SummaryResponse(
                    summary=parsed["summary"],
                    title=parsed["title"],
                    key_points=parsed["key_points"],
                    word_count=word_count,
                    estimated_duration_seconds=estimated_duration,
                    provider="ollama",
                    model=self.model,
                    processing_time=processing_time
                )
                
        except aiohttp.ClientError as e:
            logger.error(f"Ollama API request failed: {e}")
            raise LLMError(f"Ollama API request failed: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Ollama response: {e}")
            raise LLMError(f"Invalid response format from Ollama: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in Ollama summarization: {e}")
            raise LLMError(f"Ollama summarization failed: {e}")
    
    async def health_check(self) -> bool:
        """Check Ollama service availability."""
        if not self.session:
            return False
        
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                return response.status == 200
                
        except Exception:
            return False
    
    def _build_full_prompt(self, request: SummaryRequest) -> str:
        """Build the complete prompt for Ollama (includes system message)."""
        system_prompt = """You are an expert content summarizer specializing in creating engaging podcast scripts from newsletter content.

Transform newsletter content into compelling podcast-style summaries that are:
- Conversational and engaging for audio consumption
- Well-structured with clear key points  
- Appropriate for the target audience
- Optimized for text-to-speech conversion

Always respond with valid JSON in this exact format:
{
    "title": "Engaging podcast episode title",
    "summary": "Full podcast script text that flows naturally when spoken",
    "key_points": ["Point 1", "Point 2", "Point 3"]
}

Guidelines:
- Use natural, conversational language
- Include smooth transitions between topics
- Avoid complex punctuation that doesn't translate well to speech
- Keep sentences at moderate length for natural pacing
- Include brief introductions and conclusions for topics
- Make content accessible and engaging for audio listeners"""
        
        user_prompt = self._build_user_prompt(request)
        
        return f"{system_prompt}\n\nUser: {user_prompt}\n\nAssistant:"
    
    def _build_user_prompt(self, request: SummaryRequest) -> str:
        """Build the user portion of the prompt."""
        prompt_parts = [
            f"Transform this newsletter content into an engaging podcast episode summary."
        ]
        
        if request.title:
            prompt_parts.append(f"Original title: {request.title}")
        
        # Add style and length guidance (same as OpenAI)
        style_guidance = {
            "conversational": "Use a friendly, conversational tone as if speaking directly to listeners.",
            "formal": "Use a professional, informative tone suitable for business audiences.",
            "casual": "Use a relaxed, informal tone with personality and humor where appropriate."
        }
        prompt_parts.append(style_guidance.get(request.style, style_guidance["conversational"]))
        
        length_guidance = {
            "short": "Create a concise summary (2-3 minutes when spoken, ~300-450 words).",
            "medium": "Create a detailed summary (4-6 minutes when spoken, ~600-900 words).",
            "long": "Create a comprehensive summary (7-10 minutes when spoken, ~1000-1500 words)."
        }
        prompt_parts.append(length_guidance.get(request.target_length, length_guidance["medium"]))
        
        if request.focus_areas:
            focus_text = ", ".join(request.focus_areas)
            prompt_parts.append(f"Pay special attention to these topics: {focus_text}")
        
        prompt_parts.append(f"\nNewsletter content:\n{request.content}")
        
        return "\n\n".join(prompt_parts)


class LLMSummarizer:
    """
    Main LLM Summarizer service with provider abstraction.
    
    Handles provider selection, fallback logic, and response processing.
    """
    
    def __init__(self, config: Config):
        """Initialize LLM Summarizer with configuration."""
        self.config = config
        self.provider = LLMProvider(config.llm.provider)
        
        # Initialize client based on provider
        if self.provider == LLMProvider.OPENAI:
            self.client = OpenAIClient(config)
        elif self.provider == LLMProvider.OLLAMA:
            self.client = OllamaClient(config)
        else:
            raise ValidationError(f"Unsupported LLM provider: {self.provider}")
        
        logger.info(f"Initialized LLM Summarizer with provider: {self.provider}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def summarize_newsletter(
        self,
        content: str,
        title: Optional[str] = None,
        style: str = "conversational",
        target_length: str = "medium",
        focus_areas: Optional[List[str]] = None
    ) -> SummaryResponse:
        """
        Main method to summarize newsletter content.
        
        Args:
            content: Newsletter content to summarize
            title: Optional original title
            style: Summary style (conversational, formal, casual)
            target_length: Target length (short, medium, long)
            focus_areas: Optional list of topics to emphasize
            
        Returns:
            SummaryResponse with generated summary and metadata
            
        Raises:
            LLMError: If summarization fails
            ValidationError: If input is invalid
        """
        if not content or not content.strip():
            raise ValidationError("Content cannot be empty")
        
        # Clean and validate content
        content = clean_text(content)
        
        if len(content.split()) < 50:
            raise ValidationError("Content too short for meaningful summarization")
        
        logger.info(
            f"Starting summarization: {len(content.split())} words, "
            f"style: {style}, length: {target_length}"
        )
        
        request = SummaryRequest(
            content=content,
            title=title,
            style=style,
            target_length=target_length,
            focus_areas=focus_areas or []
        )
        
        try:
            response = await self.client.summarize(request)
            
            logger.info(
                f"Summarization completed: {response.word_count} words, "
                f"{response.estimated_duration_seconds}s duration, "
                f"processed in {response.processing_time:.2f}s"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if the LLM service is available."""
        try:
            return await self.client.health_check()
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the current provider."""
        if self.provider == LLMProvider.OPENAI:
            return {
                "provider": "openai",
                "model": self.client.model,
                "base_url": self.client.base_url
            }
        elif self.provider == LLMProvider.OLLAMA:
            return {
                "provider": "ollama", 
                "model": self.client.model,
                "base_url": self.client.base_url
            }
        else:
            return {"provider": str(self.provider)}


# Add missing import
import time