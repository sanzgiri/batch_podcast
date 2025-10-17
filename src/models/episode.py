"""
Episode model for Newsletter Podcast Generator.

This module defines the Episode SQLAlchemy model for storing
generated podcast episodes and their metadata.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.lib.database import Base
from src.lib.utils import generate_uuid, now_utc, format_duration, format_file_size


class EpisodeStatus(str, Enum):
    """Episode processing status enumeration."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PUBLISHED = "published"


class Episode(Base):
    """
    Episode model for storing generated podcast episodes.
    
    This model represents a podcast episode generated from a newsletter,
    including the audio file, metadata, and publication information.
    """
    
    __tablename__ = "episodes"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # Foreign key to newsletter
    newsletter_id = Column(String(36), ForeignKey("newsletters.id"), nullable=False, index=True)
    
    # Episode content
    title = Column(String(500), nullable=False, index=True)
    description = Column(Text, nullable=False)
    summary_text = Column(Text, nullable=False)
    
    # Audio file information
    audio_file_path = Column(String(1024), nullable=True)
    audio_url = Column(String(2048), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    
    # Publication information
    publication_date = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    
    # Processing status
    status = Column(String(20), nullable=False, default=EpisodeStatus.PENDING.value, index=True)
    
    # Processing metadata
    llm_provider = Column(String(50), nullable=True)
    llm_model = Column(String(100), nullable=True)
    tts_provider = Column(String(50), nullable=True)
    tts_voice = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        onupdate=now_utc
    )
    
    # Relationship to newsletter
    newsletter = relationship("Newsletter", backref="episodes")
    
    def __init__(self, **kwargs):
        """Initialize Episode instance."""
        super().__init__(**kwargs)
    
    @property
    def status_enum(self) -> EpisodeStatus:
        """Get status as enum."""
        return EpisodeStatus(self.status)
    
    @property
    def is_completed(self) -> bool:
        """Check if episode generation is completed."""
        return self.status == EpisodeStatus.COMPLETED.value
    
    @property
    def is_published(self) -> bool:
        """Check if episode is published."""
        return self.status == EpisodeStatus.PUBLISHED.value
    
    @property
    def has_audio(self) -> bool:
        """Check if episode has audio file."""
        return self.audio_file_path is not None
    
    @property
    def formatted_duration(self) -> Optional[str]:
        """Get formatted duration string (MM:SS or HH:MM:SS)."""
        if self.duration_seconds is None:
            return None
        return format_duration(self.duration_seconds)
    
    @property
    def formatted_file_size(self) -> Optional[str]:
        """Get formatted file size string."""
        if self.file_size_bytes is None:
            return None
        return format_file_size(self.file_size_bytes)
    
    @property
    def is_ready_for_publication(self) -> bool:
        """Check if episode is ready for publication."""
        return (
            self.status == EpisodeStatus.COMPLETED.value and
            self.has_audio and
            self.audio_url is not None
        )
    
    def update_status(self, status: EpisodeStatus) -> None:
        """Update episode processing status."""
        self.status = status.value
        self.updated_at = now_utc()
    
    def set_audio_info(
        self,
        audio_file_path: str,
        duration_seconds: Optional[int] = None,
        file_size_bytes: Optional[int] = None
    ) -> None:
        """Set audio file information."""
        self.audio_file_path = audio_file_path
        if duration_seconds is not None:
            self.duration_seconds = duration_seconds
        if file_size_bytes is not None:
            self.file_size_bytes = file_size_bytes
        self.updated_at = now_utc()
    
    def set_audio_url(self, audio_url: str) -> None:
        """Set public audio URL."""
        self.audio_url = audio_url
        self.updated_at = now_utc()
    
    def set_ai_providers(
        self,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        tts_provider: Optional[str] = None,
        tts_voice: Optional[str] = None
    ) -> None:
        """Set AI provider information."""
        if llm_provider is not None:
            self.llm_provider = llm_provider
        if llm_model is not None:
            self.llm_model = llm_model
        if tts_provider is not None:
            self.tts_provider = tts_provider
        if tts_voice is not None:
            self.tts_voice = tts_voice
        self.updated_at = now_utc()
    
    def mark_published(self) -> None:
        """Mark episode as published."""
        self.status = EpisodeStatus.PUBLISHED.value
        self.updated_at = now_utc()
    
    def to_dict(self) -> dict:
        """Convert episode to dictionary for API responses."""
        return {
            "id": self.id,
            "newsletter_id": self.newsletter_id,
            "title": self.title,
            "description": self.description,
            "summary_text": self.summary_text,
            "audio_file_path": self.audio_file_path,
            "audio_url": self.audio_url,
            "duration_seconds": self.duration_seconds,
            "formatted_duration": self.formatted_duration,
            "file_size_bytes": self.file_size_bytes,
            "formatted_file_size": self.formatted_file_size,
            "publication_date": self.publication_date.isoformat(),
            "status": self.status,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "tts_provider": self.tts_provider,
            "tts_voice": self.tts_voice,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    def to_rss_item_dict(self) -> dict:
        """Convert episode to dictionary for RSS feed items."""
        return {
            "title": self.title,
            "description": self.description,
            "guid": self.id,
            "pub_date": self.publication_date,
            "duration": self.formatted_duration,
            "file_size": self.file_size_bytes,
            "audio_url": self.audio_url,
            "episode_url": f"/episodes/{self.id}"
        }
    
    @classmethod
    def from_newsletter_summary(
        cls,
        newsletter_id: str,
        title: str,
        summary_text: str,
        description: Optional[str] = None
    ) -> "Episode":
        """
        Create Episode instance from newsletter summary.
        
        Args:
            newsletter_id: ID of the source newsletter
            title: Episode title
            summary_text: LLM-generated summary text
            description: Episode description (defaults to summary preview)
            
        Returns:
            Episode instance
        """
        if description is None:
            # Use first 200 characters of summary as description
            description = summary_text[:200] + "..." if len(summary_text) > 200 else summary_text
        
        return cls(
            newsletter_id=newsletter_id,
            title=title,
            description=description,
            summary_text=summary_text
        )
    
    def __repr__(self) -> str:
        """String representation of Episode."""
        return (
            f"<Episode(id='{self.id}', title='{self.title[:50]}...', "
            f"status='{self.status}', duration={self.formatted_duration})>"
        )
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"Episode: {self.title} ({self.status})"