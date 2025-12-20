"""
Storage utilities for organizing audio files.

Handles smart file organization based on newsletter profiles.
"""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.lib.config import Config
from src.lib.newsletter_config import NewsletterProfile
from src.lib.logging import get_logger
from src.lib.utils import generate_uuid

logger = get_logger(__name__)


class StorageManager:
    """Manages audio file storage with newsletter-aware organization."""

    def __init__(self, config: Config):
        """Initialize storage manager."""
        self.config = config
        self.base_audio_dir = Path(config.storage.audio_dir)
        self.ensure_base_directory()

    def ensure_base_directory(self) -> None:
        """Ensure base audio directory exists."""
        self.base_audio_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured base directory exists: {self.base_audio_dir}")

    def get_output_directory(
        self,
        newsletter_profile: Optional[NewsletterProfile] = None
    ) -> Path:
        """
        Get output directory for audio files.

        Args:
            newsletter_profile: Optional newsletter profile for organization

        Returns:
            Path to output directory
        """
        if newsletter_profile and newsletter_profile.output.folder:
            # Use newsletter-specific folder
            output_dir = self.base_audio_dir / newsletter_profile.output.folder
        else:
            # Use uncategorized folder for one-off newsletters
            output_dir = self.base_audio_dir / "uncategorized"

        # Ensure directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Output directory: {output_dir}")

        return output_dir

    def generate_filename(
        self,
        newsletter_profile: Optional[NewsletterProfile] = None,
        newsletter_id: Optional[str] = None,
        slug: Optional[str] = None,
        issue_number: Optional[str] = None,
        title: Optional[str] = None,
        date: Optional[str] = None,
    ) -> str:
        """
        Generate filename for audio file.

        Args:
            newsletter_profile: Newsletter profile with naming template
            newsletter_id: Newsletter database ID
            slug: Newsletter slug (e.g., "the-batch")
            issue_number: Issue number (e.g., "323")
            title: Newsletter title
            date: Date string (YYYY-MM-DD format)

        Returns:
            Filename for the audio file
        """
        if newsletter_profile:
            # Use profile's naming template
            filename = newsletter_profile.generate_filename(
                slug=slug or newsletter_id or "newsletter",
                date=date,
                issue=issue_number,
                title=title,
                newsletter_id=newsletter_id,
            )
        else:
            # Fallback to generic naming
            if newsletter_id:
                filename = f"newsletter-{newsletter_id[:8]}.mp3"
            else:
                filename = f"tts_{generate_uuid()}.mp3"

        logger.debug(f"Generated filename: {filename}")
        return filename

    def get_audio_file_path(
        self,
        newsletter_profile: Optional[NewsletterProfile] = None,
        newsletter_id: Optional[str] = None,
        slug: Optional[str] = None,
        issue_number: Optional[str] = None,
        title: Optional[str] = None,
        date: Optional[str] = None,
    ) -> Path:
        """
        Get complete path for audio file.

        Args:
            newsletter_profile: Newsletter profile
            newsletter_id: Newsletter database ID
            slug: Newsletter slug
            issue_number: Issue number
            title: Newsletter title
            date: Date string

        Returns:
            Complete path for the audio file
        """
        output_dir = self.get_output_directory(newsletter_profile)
        filename = self.generate_filename(
            newsletter_profile=newsletter_profile,
            newsletter_id=newsletter_id,
            slug=slug,
            issue_number=issue_number,
            title=title,
            date=date,
        )

        file_path = output_dir / filename
        logger.info(f"Audio file path: {file_path}")

        return file_path

    def get_relative_path(self, absolute_path: Path) -> str:
        """
        Get path relative to base audio directory.

        Args:
            absolute_path: Absolute file path

        Returns:
            Relative path string for database storage
        """
        try:
            relative = absolute_path.relative_to(Path.cwd())
            return str(relative)
        except ValueError:
            # If not relative to cwd, return absolute path
            return str(absolute_path)

    def list_audio_files(
        self,
        newsletter_profile: Optional[NewsletterProfile] = None
    ) -> list[Path]:
        """
        List audio files in directory.

        Args:
            newsletter_profile: Optional profile to list files for specific newsletter

        Returns:
            List of audio file paths
        """
        output_dir = self.get_output_directory(newsletter_profile)

        audio_files = []
        for ext in [".mp3", ".wav"]:
            audio_files.extend(output_dir.glob(f"*{ext}"))

        return sorted(audio_files, key=lambda p: p.stat().st_mtime, reverse=True)

    def cleanup_old_files(
        self,
        days: int = 7,
        newsletter_profile: Optional[NewsletterProfile] = None
    ) -> int:
        """
        Clean up old audio files.

        Args:
            days: Delete files older than this many days
            newsletter_profile: Optional profile to clean specific newsletter folder

        Returns:
            Number of files deleted
        """
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        deleted_count = 0

        audio_files = self.list_audio_files(newsletter_profile)

        for file_path in audio_files:
            if file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")

        logger.info(f"Cleaned up {deleted_count} old audio files")
        return deleted_count

    def get_storage_stats(self, newsletter_profile: Optional[NewsletterProfile] = None) -> dict:
        """
        Get storage statistics.

        Args:
            newsletter_profile: Optional profile for specific newsletter stats

        Returns:
            Dictionary with storage statistics
        """
        output_dir = self.get_output_directory(newsletter_profile)
        audio_files = self.list_audio_files(newsletter_profile)

        total_size = sum(f.stat().st_size for f in audio_files)

        return {
            "directory": str(output_dir),
            "file_count": len(audio_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }


def ensure_directory(directory: Path) -> None:
    """
    Ensure directory exists.

    Args:
        directory: Directory path to ensure exists
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
