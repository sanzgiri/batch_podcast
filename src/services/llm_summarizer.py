"""
LLM Summarizer Service for Newsletter Podcast Generator.

This service provides intelligent summarization and content transformation
using Large Language Models (OpenAI GPT or Ollama local models).
"""

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from types import TracebackType
from typing import Any

import aiohttp

from src.lib.config import Config
from src.lib.exceptions import LLMError, ServiceError, ValidationError
from src.lib.logging import get_logger
from src.lib.utils import clean_text

logger = get_logger(__name__)


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    OPENAI = "openai"
    OLLAMA = "ollama"


# ---------------------------------------------------------------------------
# Shared prompt builders (used by both OpenAI and Ollama clients)
# ---------------------------------------------------------------------------

_MONOLOGUE_SYSTEM_PROMPT = """You are an expert content summarizer specializing in creating engaging podcast scripts from newsletter content.

Your task is to transform newsletter content into compelling podcast-style summaries that are:
- Comprehensive and thorough, covering ALL major sections and topics
- Conversational and engaging for audio consumption
- Well-structured with clear organization and flow
- Appropriate for the target audience
- Optimized for text-to-speech conversion

Always respond with valid JSON in this exact format:
{
    "title": "Engaging podcast episode title",
    "summary": "Full podcast script text that flows naturally when spoken",
    "key_points": ["Point 1", "Point 2", "Point 3"]
}

Guidelines:
- Identify and cover ALL major sections, articles, or topics in the newsletter
- Use natural, conversational language
- Include smooth transitions between topics
- Avoid complex punctuation that doesn't translate well to speech
- Keep sentences at moderate length for natural pacing
- Structure content with introduction, detailed coverage of each section, and conclusion
- Make content accessible and engaging for audio listeners
- Don't just highlight key points - provide thorough coverage of all substantive content"""


_DIALOGUE_SYSTEM_PROMPT = """You are an expert podcast scriptwriter. You transform newsletter content into
engaging two-host podcast conversations between a Host and a Guest.

The Host introduces topics, asks insightful questions, and keeps the conversation flowing.
The Guest is the subject-matter expert who explains concepts, gives concrete examples,
and provides analysis. Both voices feel natural — no monologues, real back-and-forth.

CRITICAL OUTPUT FORMAT — the "summary" field MUST be a Speaker:line transcript like:

    Host: Welcome back to the show. Today we're talking about...
    Guest: Glad to be here. Yeah, the big story this week is...
    Host: Right. So tell me — what does that actually mean for developers?
    Guest: Three things. First, ...

Rules for the transcript:
- Each line begins with "Host:" or "Guest:" (use exactly these names, no others)
- One speaker per line; alternate frequently (every 2-4 sentences, not whole paragraphs)
- Use natural conversational fillers: "Yeah", "Right", "So", "I mean", "That's interesting"
- The Host asks short, sharp questions. The Guest gives the substantive answers.
- Cover ALL major sections of the newsletter — no skipping topics
- Use em-dashes (—) for natural pauses inside long sentences
- Spell out abbreviations occasionally ("A.I." not just "AI") — but not every time
- Avoid SSML, stage directions, or parentheticals like (thoughtful pause). They get read aloud.

Always respond with valid JSON in this exact format:
{
    "title": "Engaging podcast episode title",
    "summary": "Host: ...\\nGuest: ...\\nHost: ...\\nGuest: ...",
    "key_points": ["Point 1", "Point 2", "Point 3"]
}

The "summary" must contain ONLY the Host:/Guest: transcript — no intro paragraph,
no section headings, no narrator text outside of a speaker turn."""


def _build_system_prompt(mode: str) -> str:
    """Return the system prompt for the given output mode."""
    if mode == "dialogue":
        return _DIALOGUE_SYSTEM_PROMPT
    return _MONOLOGUE_SYSTEM_PROMPT


def _recover_truncated_json(raw: str) -> dict[str, Any] | None:
    """Best-effort recovery from a truncated/malformed JSON LLM response.

    Local models sometimes hit num_predict mid-string. The dialogue inside
    the 'summary' field is usually still useful even if the trailing keys
    (e.g. 'key_points') got chopped.

    Returns a dict with whatever fields could be recovered, or None if
    nothing usable was found.
    """
    if not raw:
        return None

    summary_pat = re.compile(
        r'"(?:summary|script|transcript|content|text)"\s*:\s*"((?:[^"\\]|\\.)*)"',
        re.DOTALL,
    )
    title_pat = re.compile(
        r'"(?:title|episode_title|headline)"\s*:\s*"((?:[^"\\]|\\.)*)"',
        re.DOTALL,
    )

    m_summary = summary_pat.search(raw)
    if not m_summary:
        return None

    try:
        summary = json.loads(f'"{m_summary.group(1)}"')
    except json.JSONDecodeError:
        summary = m_summary.group(1).replace("\\n", "\n").replace('\\"', '"')

    if not summary or not summary.strip():
        return None

    title = ""
    m_title = title_pat.search(raw)
    if m_title:
        try:
            title = json.loads(f'"{m_title.group(1)}"')
        except json.JSONDecodeError:
            title = m_title.group(1)

    return {"summary": summary, "title": title, "key_points": []}


def _normalize_parsed_response(
    parsed: dict[str, Any], fallback_title: str = "Untitled Episode"
) -> dict[str, Any]:
    """Normalize an LLM JSON response, tolerating missing/renamed fields.

    Smaller local models (e.g. llama3.1:8b) often omit or rename fields. This
    accepts common variations and ensures the three required fields exist.
    """
    # "summary" — the actual script body. Try common synonyms.
    summary = (
        parsed.get("summary")
        or parsed.get("script")
        or parsed.get("transcript")
        or parsed.get("content")
        or parsed.get("text")
        or ""
    )
    if not summary or not isinstance(summary, str) or not summary.strip():
        raise LLMError(
            "LLM response missing 'summary' (or synonym: script/transcript/content). "
            f"Got keys: {sorted(parsed.keys())}"
        )

    # "title" — fall back to the request title.
    title = (
        parsed.get("title")
        or parsed.get("episode_title")
        or parsed.get("headline")
        or fallback_title
    )
    if not isinstance(title, str):
        title = fallback_title

    # "key_points" — fall back to empty list (it's metadata, not user-facing).
    key_points = (
        parsed.get("key_points")
        or parsed.get("keypoints")
        or parsed.get("highlights")
        or parsed.get("takeaways")
        or []
    )
    if not isinstance(key_points, list):
        key_points = []
    # Coerce items to strings (some models emit dicts here).
    key_points = [str(p) if not isinstance(p, str) else p for p in key_points][:10]

    return {"summary": summary.strip(), "title": str(title).strip(), "key_points": key_points}


def _build_user_prompt(request: "SummaryRequest") -> str:
    """Build the user-side prompt for either monologue or dialogue mode."""
    if request.mode == "dialogue":
        prompt_parts = [
            "Transform this newsletter content into a two-host podcast conversation.",
            "",
            "IMPORTANT:",
            "- Use ONLY 'Host:' and 'Guest:' as speaker labels (exactly those names).",
            "- Alternate frequently — short turns, real back-and-forth, not long monologues.",
            "- Cover ALL major sections / articles / topics from the newsletter. Do not skip any.",
            "- Open with the Host welcoming listeners and previewing what's coming up.",
            "- For each major topic: Host introduces or asks; Guest gives the substantive take.",
            "- Close with the Host wrapping up and thanking the Guest.",
            "",
            "Voice rules — this will be read by a TTS system:",
            '- Spell numbers in words when they\'re short ("three things" not "3 things").',
            "- Use em-dashes (—) for natural mid-sentence pauses.",
            "- Avoid bracketed stage directions like (laughs) or (thoughtful pause) — they get read aloud.",
            "- Avoid markdown formatting (no **bold**, no bullet lists, no headings).",
        ]
    else:
        prompt_parts = [
            "Transform this newsletter content into a comprehensive podcast episode.",
            "",
            "IMPORTANT: This should be a thorough walkthrough, not just highlights.",
            "Identify ALL major sections, articles, or topics in the newsletter and cover each one.",
            "",
            "Structure your podcast as follows:",
            "1. Brief introduction welcoming listeners",
            "2. Overview of what topics will be covered",
            "3. Detailed coverage of EACH section/article with:",
            "   - Clear section introduction",
            "   - Main points and key information",
            "   - Relevant details, examples, or context",
            "   - Smooth transition to next section",
            "4. Brief conclusion summarizing the episode",
            "",
            "Do NOT skip sections or only highlight a few items. Cover everything substantive.",
        ]

    if request.title:
        prompt_parts.append(f"\nOriginal newsletter title: {request.title}")

    style_guidance = {
        "conversational": "Use a friendly, conversational tone as if speaking directly to listeners.",
        "formal": "Use a professional, informative tone suitable for business audiences.",
        "casual": "Use a relaxed, informal tone with personality and humor where appropriate.",
    }
    prompt_parts.append(style_guidance.get(request.style, style_guidance["conversational"]))

    length_guidance = {
        "short": "Aim for ~5-7 minutes when spoken. Cover main sections concisely but don't skip content.",
        "medium": "Aim for ~10-15 minutes when spoken. Give each section proper attention with details.",
        "long": "Aim for ~20-30 minutes when spoken. Provide comprehensive, thorough coverage of all content.",
    }
    prompt_parts.append(length_guidance.get(request.target_length, length_guidance["medium"]))

    if request.focus_areas:
        focus_text = ", ".join(request.focus_areas)
        prompt_parts.append(f"\nPay special attention to these topics: {focus_text}")

    prompt_parts.append(f"\nNewsletter content:\n{request.content}")
    return "\n\n".join(prompt_parts)


@dataclass
class SummaryRequest:
    """Request for content summarization."""

    content: str
    title: str | None = None
    style: str = "conversational"  # conversational, formal, casual
    target_length: str = "medium"  # short, medium, long
    focus_areas: list[str] | None = None
    mode: str = "monologue"  # monologue (single narrator) or dialogue (two hosts)
    host_a_name: str = "Host"
    host_b_name: str = "Guest"

    def __post_init__(self) -> None:
        if self.focus_areas is None:
            self.focus_areas = []


@dataclass
class SummaryResponse:
    """Response from summarization."""

    summary: str
    title: str
    key_points: list[str]
    word_count: int
    estimated_duration_seconds: int
    provider: str
    model: str
    processing_time: float
    # Cost tracking
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


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

        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "OpenAIClient":
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=60),
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
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
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "response_format": {"type": "json_object"},
            }

            async with self.session.post(
                f"{self.base_url}/chat/completions", json=payload
            ) as response:
                response.raise_for_status()
                result = await response.json()

                # Parse response
                content = result["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                parsed = _normalize_parsed_response(
                    parsed, fallback_title=request.title or "Untitled Episode"
                )

                processing_time = time.time() - start_time

                # Estimate speech duration (average 150 words per minute)
                word_count = len(parsed["summary"].split())
                estimated_duration = int((word_count / 150) * 60)

                # Extract token usage and calculate cost
                usage = result.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

                # Calculate cost using cost tracker
                from src.lib.cost_tracker import LLMUsage

                llm_usage = LLMUsage.calculate(
                    provider="openai",
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

                return SummaryResponse(
                    summary=parsed["summary"],
                    title=parsed["title"],
                    key_points=parsed["key_points"],
                    word_count=word_count,
                    estimated_duration_seconds=estimated_duration,
                    provider="openai",
                    model=self.model,
                    processing_time=processing_time,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=llm_usage.total_cost,
                )

        except aiohttp.ClientError as e:
            logger.error(f"OpenAI API request failed: {e}")
            raise LLMError(f"OpenAI API request failed: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            raise LLMError(f"Invalid response format from OpenAI: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI summarization: {e}")
            raise LLMError(f"OpenAI summarization failed: {e}") from e

    async def health_check(self) -> bool:
        """Check OpenAI API availability."""
        if not self.session:
            return False

        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": 1,
            }

            async with self.session.post(
                f"{self.base_url}/chat/completions", json=payload
            ) as response:
                return response.status == 200

        except Exception:
            return False

    def _get_system_prompt(self) -> str:
        """Get the system prompt for summarization."""
        return _build_system_prompt("monologue")

    def _build_prompt(self, request: SummaryRequest) -> str:
        """Build the user prompt for summarization."""
        return _build_user_prompt(request)


class OllamaClient(BaseLLMClient):
    """Ollama local LLM client implementation."""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.llm.ollama.base_url
        self.model = config.llm.ollama.model
        self.temperature = config.llm.ollama.temperature
        self.num_ctx = config.llm.ollama.num_ctx
        self.num_predict = config.llm.ollama.num_predict
        self.timeout = config.llm.ollama.timeout

        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "OllamaClient":
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
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
                    "temperature": self.temperature,
                    "num_ctx": self.num_ctx,
                    "num_predict": self.num_predict,
                },
                "format": "json",
            }

            async with self.session.post(f"{self.base_url}/api/generate", json=payload) as response:
                response.raise_for_status()
                result = await response.json()

                # Parse response — with recovery for truncated JSON.
                content = result["response"]
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError as je:
                    recovered = _recover_truncated_json(content)
                    if recovered is None:
                        logger.error(
                            f"Ollama returned malformed JSON (no recovery possible): {je}"
                            f" — first 200 chars: {content[:200]!r}"
                        )
                        raise
                    logger.warning(
                        f"Ollama JSON truncated at char {je.pos}; "
                        f"recovered summary of {len(recovered['summary'])} chars. "
                        f"Consider raising num_predict in config."
                    )
                    parsed = recovered
                parsed = _normalize_parsed_response(
                    parsed, fallback_title=request.title or "Untitled Episode"
                )

                processing_time = time.time() - start_time

                # Estimate speech duration
                word_count = len(parsed["summary"].split())
                estimated_duration = int((word_count / 150) * 60)

                # Extract token usage if available (Ollama provides this)
                input_tokens = result.get("prompt_eval_count", 0)
                output_tokens = result.get("eval_count", 0)
                total_tokens = input_tokens + output_tokens

                # Local models have zero cost
                from src.lib.cost_tracker import LLMUsage

                llm_usage = LLMUsage.calculate(
                    provider="ollama",
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

                return SummaryResponse(
                    summary=parsed["summary"],
                    title=parsed["title"],
                    key_points=parsed["key_points"],
                    word_count=word_count,
                    estimated_duration_seconds=estimated_duration,
                    provider="ollama",
                    model=self.model,
                    processing_time=processing_time,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=llm_usage.total_cost,  # Will be 0.0 for local
                )

        except aiohttp.ClientError as e:
            logger.error(f"Ollama API request failed: {e}")
            raise LLMError(f"Ollama API request failed: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Ollama response: {e}")
            raise LLMError(f"Invalid response format from Ollama: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in Ollama summarization: {e}")
            raise LLMError(f"Ollama summarization failed: {e}") from e

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
        system_prompt = _build_system_prompt(request.mode)
        user_prompt = _build_user_prompt(request)
        return f"{system_prompt}\n\nUser: {user_prompt}\n\nAssistant:"

    def _build_user_prompt(self, request: SummaryRequest) -> str:
        """Build the user portion of the prompt."""
        return _build_user_prompt(request)


class LLMSummarizer:
    """
    Main LLM Summarizer service with provider abstraction.

    Handles provider selection, fallback logic, and response processing.
    """

    def __init__(self, config: Config):
        """Initialize LLM Summarizer with configuration."""
        self.config = config
        self.provider = LLMProvider(config.llm.provider)
        self.client: OpenAIClient | OllamaClient

        # Initialize client based on provider
        if self.provider == LLMProvider.OPENAI:
            self.client = OpenAIClient(config)
        else:
            self.client = OllamaClient(config)

        logger.info(f"Initialized LLM Summarizer with provider: {self.provider}")

    async def __aenter__(self) -> "LLMSummarizer":
        """Async context manager entry."""
        await self.client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def summarize_newsletter(
        self,
        content: str,
        title: str | None = None,
        style: str = "conversational",
        target_length: str = "medium",
        focus_areas: list[str] | None = None,
        mode: str = "monologue",
    ) -> SummaryResponse:
        """
        Main method to summarize newsletter content.

        Args:
            content: Newsletter content to summarize
            title: Optional original title
            style: Summary style (conversational, formal, casual)
            target_length: Target length (short, medium, long)
            focus_areas: Optional list of topics to emphasize
            mode: Script mode - 'monologue' (single narrator) or 'dialogue' (Host/Guest)

        Returns:
            SummaryResponse with generated summary and metadata

        Raises:
            LLMError: If summarization fails
            ValidationError: If input is invalid
        """
        if not content or not content.strip():
            raise ValidationError("Content cannot be empty")

        if mode not in {"monologue", "dialogue"}:
            raise ValidationError("mode must be 'monologue' or 'dialogue'")

        # Clean and validate content
        content = clean_text(content)

        if len(content.split()) < 50:
            raise ValidationError("Content too short for meaningful summarization")

        logger.info(
            f"Starting summarization: {len(content.split())} words, "
            f"style: {style}, length: {target_length}, mode: {mode}"
        )

        request = SummaryRequest(
            content=content,
            title=title,
            style=style,
            target_length=target_length,
            focus_areas=focus_areas or [],
            mode=mode,
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

    def get_provider_info(self) -> dict[str, Any]:
        """Get information about the current provider."""
        provider = "openai" if self.provider == LLMProvider.OPENAI else "ollama"
        return {
            "provider": provider,
            "model": self.client.model,
            "base_url": self.client.base_url,
        }
