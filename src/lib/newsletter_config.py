"""
Newsletter Configuration Module

Handles newsletter-specific configuration and profiles.
"""

import re
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class ProcessingConfig(BaseModel):
    """Processing settings for newsletter content."""

    length: str = Field(default="medium", description="Target podcast length")
    style: str = Field(default="conversational", description="Podcast style")
    focus_areas: list[str] = Field(default_factory=list, description="Topics to emphasize")
    mode: str = Field(
        default="monologue",
        description="Script mode: 'monologue' (single narrator) or 'dialogue' (two hosts)",
    )

    @field_validator("length")
    @classmethod
    def validate_length(cls, v: str) -> str:
        """Validate length option."""
        valid_lengths = ["short", "medium", "long"]
        if v not in valid_lengths:
            raise ValueError(f"Length must be one of {valid_lengths}")
        return v

    @field_validator("style")
    @classmethod
    def validate_style(cls, v: str) -> str:
        """Validate style option."""
        valid_styles = ["conversational", "formal", "casual"]
        if v not in valid_styles:
            raise ValueError(f"Style must be one of {valid_styles}")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        valid_modes = ["monologue", "dialogue"]
        if v not in valid_modes:
            raise ValueError(f"Mode must be one of {valid_modes}")
        return v


class TTSProfileConfig(BaseModel):
    """Per-newsletter TTS rendering settings.

    Settings here are passed through to the Kokoro pipeline
    (src.services.tts_generator.TTSGenerator.generate_speech).
    """

    preset: str | None = Field(
        default=None,
        description="Named preset from src/lib/tts_engine/data/presets/*.json",
    )
    voice: str | None = Field(
        default=None,
        description="Primary voice spec, e.g. 'af_heart' or 'af_heart:0.7,af_nicole:0.3'",
    )
    quote_voice: str | None = Field(
        default=None, description="Secondary voice for blockquotes ('none' to disable)"
    )
    voice_a: str | None = Field(default=None, description="Dialogue mode: first speaker voice")
    voice_b: str | None = Field(default=None, description="Dialogue mode: second speaker voice")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    quote_speed: float = Field(default=0.85, ge=0.5, le=2.0)
    dialogue_speed: float = Field(default=0.95, ge=0.5, le=2.0)
    pronunciations: str | None = Field(
        default=None,
        description="Bundled dict name (e.g. 'ai_tech') or path to a JSON file",
    )
    extra_pronunciations: dict[str, str] = Field(
        default_factory=dict,
        description="Inline pronunciation overrides merged on top of the dict",
    )
    expand_abbrev: bool = Field(default=True, description="Expand abbreviations (GPU -> G.P.U.)")
    target_lufs: float = Field(
        default=-16.0, description="loudnorm target: -16 podcast, -18 audiobook"
    )


class OutputConfig(BaseModel):
    """Output settings for generated podcasts."""

    folder: str = Field(..., description="Subfolder for audio files")
    naming_template: str = Field(
        default="{slug}-{date}", description="Template for filename generation"
    )


class PodcastMetadata(BaseModel):
    """Podcast metadata for RSS feeds and ID3 tags."""

    title: str = Field(..., description="Podcast title")
    description: str = Field(..., description="Podcast description")
    author: str = Field(..., description="Podcast author")
    email: str | None = Field(default=None, description="Contact email")
    category: str = Field(default="Technology", description="Podcast category")
    language: str = Field(default="en-us", description="Language code")
    image_url: str | None = Field(default=None, description="Cover art URL")
    website_url: str | None = Field(default=None, description="Website URL")


class ExtractionPattern(BaseModel):
    """Pattern for extracting metadata from URLs or content."""

    pattern: str | None = Field(default=None, description="Regex pattern")
    source: str = Field(default="url", description="Source: url or content")

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Validate source option."""
        valid_sources = ["url", "content"]
        if v not in valid_sources:
            raise ValueError(f"Source must be one of {valid_sources}")
        return v


class ExtractionConfig(BaseModel):
    """Configuration for metadata extraction."""

    issue_number: ExtractionPattern | None = None
    date: ExtractionPattern | None = None
    title: ExtractionPattern | None = None


class NewsletterProfile(BaseModel):
    """Complete newsletter profile configuration."""

    name: str = Field(..., description="Newsletter display name")
    enabled: bool = Field(default=True, description="Enable processing")
    rss_feed: str | None = Field(default=None, description="RSS feed URL")
    url_pattern: str | None = Field(default=None, description="URL pattern for matching")
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    tts: TTSProfileConfig = Field(default_factory=TTSProfileConfig)
    output: OutputConfig
    podcast_metadata: PodcastMetadata
    extraction: ExtractionConfig | None = Field(default=None)

    def matches_url(self, url: str) -> bool:
        """Check if a URL matches this newsletter's pattern."""
        if not self.url_pattern:
            return False

        # Convert wildcard pattern to regex
        pattern = self.url_pattern.replace("*", ".*")
        pattern = f"^{pattern}$"

        return bool(re.match(pattern, url))

    def extract_metadata(self, url: str, content: str | None = None) -> dict[str, str | None]:
        """Extract metadata from URL and/or content."""
        metadata: dict[str, str | None] = {
            "issue_number": None,
            "date": None,
            "title": None,
        }

        if not self.extraction:
            return metadata

        # Extract issue number
        if self.extraction.issue_number:
            source_text = url if self.extraction.issue_number.source == "url" else content
            if source_text and self.extraction.issue_number.pattern:
                match = re.search(self.extraction.issue_number.pattern, source_text)
                if match:
                    metadata["issue_number"] = match.group(1) if match.groups() else match.group(0)

        # Extract date
        if self.extraction.date:
            source_text = url if self.extraction.date.source == "url" else content
            if source_text and self.extraction.date.pattern:
                match = re.search(self.extraction.date.pattern, source_text)
                if match:
                    metadata["date"] = match.group(1) if match.groups() else match.group(0)

        # Extract title
        if self.extraction.title:
            source_text = url if self.extraction.title.source == "url" else content
            if source_text and self.extraction.title.pattern:
                match = re.search(self.extraction.title.pattern, source_text)
                if match:
                    metadata["title"] = match.group(1) if match.groups() else match.group(0)

        return metadata

    def generate_filename(
        self,
        slug: str,
        date: str | None = None,
        issue: str | None = None,
        title: str | None = None,
        newsletter_id: str | None = None,
    ) -> str:
        """Generate filename from template."""
        # Prepare variables
        variables = {
            "slug": slug,
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "datetime": datetime.now().strftime("%Y-%m-%d-%H%M%S"),
            "issue": issue or "",
            "title": self._sanitize_filename(title) if title else "",
            "id": newsletter_id or "",
        }

        # Apply template
        filename = self.output.naming_template.format(**variables)

        # Clean up any empty parts (e.g., if issue is empty)
        filename = re.sub(r"-+", "-", filename)  # Remove duplicate dashes
        filename = filename.strip("-")  # Remove leading/trailing dashes

        return f"{filename}.mp3"

    @staticmethod
    def _sanitize_filename(text: str) -> str:
        """Sanitize text for use in filename."""
        # Remove/replace invalid characters
        text = re.sub(r'[<>:"/\\|?*]', "", text)
        text = re.sub(r"\s+", "-", text)
        return text.lower()


class NewsletterConfig(BaseModel):
    """Root configuration for all newsletters."""

    newsletters: dict[str, NewsletterProfile]

    @classmethod
    def load_from_file(cls, config_path: Path) -> "NewsletterConfig":
        """Load newsletter configuration from YAML file."""
        if not config_path.exists():
            # Return empty config if file doesn't exist
            return cls(newsletters={})

        with open(config_path) as f:
            data = yaml.safe_load(f)

        return cls(**data)

    def get_profile(self, profile_id: str) -> NewsletterProfile | None:
        """Get newsletter profile by ID."""
        return self.newsletters.get(profile_id)

    def get_enabled_profiles(self) -> dict[str, NewsletterProfile]:
        """Get all enabled newsletter profiles."""
        return {k: v for k, v in self.newsletters.items() if v.enabled}

    def find_profile_by_url(self, url: str) -> tuple[str, NewsletterProfile] | None:
        """Find newsletter profile that matches a URL."""
        for profile_id, profile in self.newsletters.items():
            if profile.enabled and profile.matches_url(url):
                return (profile_id, profile)
        return None


# Global newsletter config instance
_newsletter_config: NewsletterConfig | None = None


def get_newsletter_config(config_path: Path | None = None) -> NewsletterConfig:
    """Get or load newsletter configuration."""
    global _newsletter_config

    if _newsletter_config is None:
        if config_path is None:
            # Default path
            config_path = Path(__file__).parent.parent.parent / "config" / "newsletters.yaml"

        _newsletter_config = NewsletterConfig.load_from_file(config_path)

    return _newsletter_config


def reload_newsletter_config(config_path: Path | None = None) -> NewsletterConfig:
    """Reload newsletter configuration from file."""
    global _newsletter_config
    _newsletter_config = None
    return get_newsletter_config(config_path)
