"""
Newsletter model for Newsletter Podcast Generator.

This module defines the Newsletter SQLAlchemy model for storing
newsletter content and processing metadata.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, String, Text, Integer, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from src.lib.database import Base
from src.lib.utils import generate_uuid, generate_content_hash, now_utc, count_words


class NewsletterStatus(str, Enum):
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
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # Content fields
    title = Column(String(500), nullable=False, index=True)
    url = Column(String(2048), nullable=True)
    content = Column(Text, nullable=False)
    extracted_content = Column(Text, nullable=True)
    
    # Metadata fields
    publication_date = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    word_count = Column(Integer, nullable=False, default=0)

    # Newsletter profile fields
    newsletter_profile_id = Column(String(100), nullable=True, index=True)  # e.g., "the-batch"
    issue_number = Column(String(50), nullable=True)  # e.g., "323"
    slug = Column(String(100), nullable=True)  # e.g., "the-batch"
    
    # Processing status
    status = Column(
        SQLEnum(NewsletterStatus),
        nullable=False,
        default=NewsletterStatus.PENDING,
        index=True
    )
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        onupdate=now_utc
    )
    
    def __init__(self, **kwargs):
        """Initialize Newsletter instance."""
        # Generate content hash if not provided
        if 'content' in kwargs and 'content_hash' not in kwargs:
            kwargs['content_hash'] = generate_content_hash(kwargs['content'])
        
        # Calculate word count if not provided
        if 'content' in kwargs and 'word_count' not in kwargs:
            kwargs['word_count'] = count_words(kwargs['content'])
        
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
    
    def set_extracted_content(self, extracted_content: str) -> None:
        """Set extracted content and update word count."""
        self.extracted_content = extracted_content
        self.word_count = count_words(extracted_content)
        self.updated_at = now_utc()
    
    def to_dict(self) -> dict:
        """Convert newsletter to dictionary for API responses."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "extracted_content": self.extracted_content,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "submitted_at": self.submitted_at.isoformat(),
            "content_hash": self.content_hash,
            "word_count": self.word_count,
            "newsletter_profile_id": self.newsletter_profile_id,
            "issue_number": self.issue_number,
            "slug": self.slug,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_submission(
        cls,
        title: str,
        content: Optional[str] = None,
        url: Optional[str] = None,
        publication_date: Optional[datetime] = None,
        user_id: Optional[str] = None
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
        
        return cls(
            title=title,
            content=content,
            url=url,
            publication_date=publication_date
        )
    
    @classmethod
    def from_url(
        cls,
        url: str,
        title: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> "Newsletter":
        """
        Create Newsletter instance from URL.
        
        Args:
            url: Newsletter URL
            title: Optional title (will be extracted if not provided)
            user_id: Optional user ID for tracking
            
        Returns:
            Newsletter instance
        """
        return cls(
            title=title or "Untitled Newsletter",
            content="",  # Will be filled by content extraction
            url=url
        )
    
    @classmethod
    def from_text(
        cls,
        content: str,
        title: Optional[str] = None,
        content_type: str = "text",
        user_id: Optional[str] = None
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
        return cls(
            title=title or "Untitled Newsletter",
            content=content,
            url=None
        )
    
    def __repr__(self) -> str:
        """String representation of Newsletter."""
        return (
            f"<Newsletter(id='{self.id}', title='{self.title[:50]}...', "
            f"status='{self.status.value}', word_count={self.word_count})>"
        )
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"Newsletter: {self.title} ({self.status.value})"