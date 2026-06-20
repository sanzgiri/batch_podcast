"""
Newsletter model for Newsletter Podcast Generator.

This module defines the Newsletter SQLAlchemy model for storing
newsletter content and processing metadata.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.lib.database import Base
from src.lib.utils import count_words, generate_content_hash, generate_uuid, now_utc


class NewsletterStatus(StrEnum):
    """Newsletter processing status enumeration."""

    PENDING = "pending"
    EXTRACTING = "extracting"
    SUMMARIZING = "summarizing"
    GENERATING_AUDIO = "generating_audio"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Newsletter(Base):
    """
    Newsletter model for storing submitted newsletter content.

    This model represents a newsletter submission that will be processed
    into a podcast episode through content extraction, LLM summarization,
    and TTS generation.
    """

    __tablename__ = "newsletters"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Content fields
    title: Mapped[str] = mapped_column(String(500), index=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    extracted_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata fields
    publication_date: Mapped[datetime | None] = mapped_column(nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(default=now_utc)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    word_count: Mapped[int] = mapped_column(default=0)

    # Newsletter profile fields
    newsletter_profile_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    issue_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Link to generated episode
    episode_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Processing status
    status: Mapped[NewsletterStatus] = mapped_column(
        SQLEnum(NewsletterStatus), default=NewsletterStatus.PENDING, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Newsletter instance."""
        # Generate content hash if not provided
        if "content" in kwargs and "content_hash" not in kwargs:
            kwargs["content_hash"] = generate_content_hash(kwargs["content"])

        # Calculate word count if not provided
        if "content" in kwargs and "word_count" not in kwargs:
            kwargs["word_count"] = count_words(kwargs["content"])

        super().__init__(**kwargs)

    @property
    def is_processing(self) -> bool:
        """Check if newsletter is currently being processed."""
        return self.status == NewsletterStatus.PROCESSING

    @property
    def is_completed(self) -> bool:
        """Check if newsletter processing is completed."""
        return self.status == NewsletterStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if newsletter processing has failed."""
        return self.status == NewsletterStatus.FAILED

    @property
    def has_url(self) -> bool:
        """Check if newsletter was submitted with a URL."""
        return self.url is not None and self.url.strip() != ""

    @property
    def effective_content(self) -> str:
        """Get the effective content (extracted content if available, otherwise original)."""
        return self.extracted_content or self.content

    def update_status(self, status: NewsletterStatus) -> None:
        """Update newsletter processing status."""
        self.status = status
        self.updated_at = now_utc()

    def set_error(self, error_message: str) -> None:
        """Set error status and message."""
        self.status = NewsletterStatus.FAILED
        self.error_message = error_message
        self.updated_at = now_utc()

    def clear_error(self) -> None:
        """Clear error message."""
        self.error_message = None
        self.updated_at = now_utc()

    def set_extracted_content(self, extracted_content: str) -> None:
        """Set extracted content, update word count, and recompute content_hash.

        For URL-sourced newsletters, the original `content` field is empty until
        extraction completes. We recompute `content_hash` here so the uniqueness
        constraint protects against duplicate content (across different URLs)
        instead of trivially colliding on the empty-string hash.
        """
        self.extracted_content = extracted_content
        self.word_count = count_words(extracted_content)
        if extracted_content:
            self.content_hash = generate_content_hash(extracted_content)
        self.updated_at = now_utc()

    def to_dict(self) -> dict[str, Any]:
        """Convert newsletter to dictionary for API responses."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "extracted_content": self.extracted_content,
            "publication_date": self.publication_date.isoformat()
            if self.publication_date
            else None,
            "submitted_at": self.submitted_at.isoformat(),
            "content_hash": self.content_hash,
            "word_count": self.word_count,
            "newsletter_profile_id": self.newsletter_profile_id,
            "issue_number": self.issue_number,
            "slug": self.slug,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_submission(
        cls,
        title: str,
        content: str | None = None,
        url: str | None = None,
        publication_date: datetime | None = None,
        _user_id: str | None = None,
    ) -> "Newsletter":
        """
        Create Newsletter instance from submission data.

        Args:
            title: Newsletter title
            content: Newsletter content (required if url not provided)
            url: Newsletter URL (required if content not provided)
            publication_date: Original publication date
            user_id: Optional user ID for tracking

        Returns:
            Newsletter instance

        Raises:
            ValueError: If neither content nor url is provided
        """
        if not content and not url:
            raise ValueError("Either content or url must be provided")

        if not content:
            # Will be filled by content extraction service
            content = ""

        return cls(title=title, content=content, url=url, publication_date=publication_date)

    @classmethod
    def from_url(
        cls, url: str, title: str | None = None, _user_id: str | None = None
    ) -> "Newsletter":
        """
        Create Newsletter instance from URL.

        Args:
            url: Newsletter URL
            title: Optional title (will be extracted if not provided)
            user_id: Optional user ID for tracking

        Returns:
            Newsletter instance

        Note:
            Seeds content_hash with hash-of-URL so the database uniqueness
            constraint catches duplicate URLs at INSERT time. Once the content
            is extracted, set_extracted_content() will overwrite content_hash
            with the actual content hash so duplicate-content detection works
            across different URLs too.
        """
        return cls(
            title=title or "Untitled Newsletter",
            content="",  # Will be filled by content extraction
            url=url,
            # Seed with URL hash so we don't collide on the empty-string hash.
            content_hash=generate_content_hash(url),
        )

    @classmethod
    def from_text(
        cls,
        content: str,
        title: str | None = None,
        _content_type: str = "text",
        _user_id: str | None = None,
    ) -> "Newsletter":
        """
        Create Newsletter instance from text content.

        Args:
            content: Newsletter content
            title: Optional title
            content_type: Content type (text, html, markdown)
            user_id: Optional user ID for tracking

        Returns:
            Newsletter instance
        """
        return cls(title=title or "Untitled Newsletter", content=content, url=None)

    def __repr__(self) -> str:
        """String representation of Newsletter."""
        return (
            f"<Newsletter(id='{self.id}', title='{self.title[:50]}...', "
            f"status='{self.status.value}', word_count={self.word_count})>"
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"Newsletter: {self.title} ({self.status.value})"
