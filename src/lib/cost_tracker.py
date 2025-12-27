"""
Cost tracking for AI service usage.

Tracks token usage (LLM) and character usage (TTS) with cost calculations.
"""

from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime
from enum import Enum


class LLMProvider(str, Enum):
    """LLM provider names."""
    OPENAI = "openai"
    OLLAMA = "ollama"


class TTSProvider(str, Enum):
    """TTS provider names."""
    KOKORO_TTS = "kokoro_tts"


# Pricing in USD per unit
# Updated as of December 2024
LLM_PRICING = {
    "openai": {
        "gpt-4o": {
            "input": 2.50 / 1_000_000,   # $2.50 per 1M input tokens
            "output": 10.00 / 1_000_000,  # $10.00 per 1M output tokens
        },
        "gpt-4o-mini": {
            "input": 0.150 / 1_000_000,   # $0.15 per 1M input tokens
            "output": 0.600 / 1_000_000,  # $0.60 per 1M output tokens
        },
        "gpt-4-turbo": {
            "input": 10.00 / 1_000_000,
            "output": 30.00 / 1_000_000,
        },
        "gpt-3.5-turbo": {
            "input": 0.50 / 1_000_000,
            "output": 1.50 / 1_000_000,
        },
    },
    "ollama": {
        # Local models have no API cost
        "default": {
            "input": 0.0,
            "output": 0.0,
        }
    }
}

TTS_PRICING = {
    "kokoro_tts": {
        # Local TTS has no API cost
        "cost_per_char": 0.0,
    }
}


@dataclass
class LLMUsage:
    """LLM usage tracking."""
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float

    @classmethod
    def calculate(
        cls,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> "LLMUsage":
        """Calculate costs from token usage."""
        total_tokens = input_tokens + output_tokens

        # Get pricing
        if provider in LLM_PRICING:
            model_pricing = LLM_PRICING[provider].get(
                model,
                LLM_PRICING[provider].get("default", {"input": 0.0, "output": 0.0})
            )
        else:
            model_pricing = {"input": 0.0, "output": 0.0}

        input_cost = input_tokens * model_pricing["input"]
        output_cost = output_tokens * model_pricing["output"]
        total_cost = input_cost + output_cost

        return cls(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost
        )


@dataclass
class TTSUsage:
    """TTS usage tracking."""
    provider: str
    voice: str
    characters: int
    cost: float

    @classmethod
    def calculate(
        cls,
        provider: str,
        voice: str,
        characters: int
    ) -> "TTSUsage":
        """Calculate costs from character usage."""
        # Get pricing
        if provider in TTS_PRICING:
            cost_per_char = TTS_PRICING[provider]["cost_per_char"]
        else:
            cost_per_char = 0.0

        cost = characters * cost_per_char

        return cls(
            provider=provider,
            voice=voice,
            characters=characters,
            cost=cost
        )


@dataclass
class ProcessingCosts:
    """Combined processing costs for a newsletter."""
    llm_usage: Optional[LLMUsage] = None
    tts_usage: Optional[TTSUsage] = None

    @property
    def total_cost(self) -> float:
        """Calculate total cost."""
        cost = 0.0
        if self.llm_usage:
            cost += self.llm_usage.total_cost
        if self.tts_usage:
            cost += self.tts_usage.cost
        return cost

    @property
    def llm_cost(self) -> float:
        """Get LLM cost."""
        return self.llm_usage.total_cost if self.llm_usage else 0.0

    @property
    def tts_cost(self) -> float:
        """Get TTS cost."""
        return self.tts_usage.cost if self.tts_usage else 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        result = {
            "total_cost": self.total_cost,
            "llm_cost": self.llm_cost,
            "tts_cost": self.tts_cost,
        }

        if self.llm_usage:
            result["llm"] = {
                "provider": self.llm_usage.provider,
                "model": self.llm_usage.model,
                "input_tokens": self.llm_usage.input_tokens,
                "output_tokens": self.llm_usage.output_tokens,
                "total_tokens": self.llm_usage.total_tokens,
                "input_cost": self.llm_usage.input_cost,
                "output_cost": self.llm_usage.output_cost,
                "total_cost": self.llm_usage.total_cost,
            }

        if self.tts_usage:
            result["tts"] = {
                "provider": self.tts_usage.provider,
                "voice": self.tts_usage.voice,
                "characters": self.tts_usage.characters,
                "cost": self.tts_usage.cost,
            }

        return result


def get_llm_pricing_info() -> Dict:
    """Get current LLM pricing information."""
    return LLM_PRICING.copy()


def get_tts_pricing_info() -> Dict:
    """Get current TTS pricing information."""
    return TTS_PRICING.copy()


def estimate_llm_cost(
    provider: str,
    model: str,
    input_text: str,
    estimated_output_tokens: int = 1000
) -> float:
    """
    Estimate LLM cost from input text.

    Args:
        provider: LLM provider name
        model: Model name
        input_text: Input text to estimate tokens from
        estimated_output_tokens: Estimated output token count

    Returns:
        Estimated cost in USD
    """
    # Rough estimation: 1 token ≈ 4 characters
    estimated_input_tokens = len(input_text) // 4

    usage = LLMUsage.calculate(
        provider=provider,
        model=model,
        input_tokens=estimated_input_tokens,
        output_tokens=estimated_output_tokens
    )

    return usage.total_cost


def estimate_tts_cost(
    provider: str,
    text: str
) -> float:
    """
    Estimate TTS cost from text.

    Args:
        provider: TTS provider name
        text: Text to convert to speech

    Returns:
        Estimated cost in USD
    """
    characters = len(text)

    usage = TTSUsage.calculate(
        provider=provider,
        voice="default",
        characters=characters
    )

    return usage.cost
