"""
Utility functions for Newsletter Podcast Generator.

This module provides common utility functions used throughout the application.
"""

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import html2text
from bs4 import BeautifulSoup


def generate_uuid() -> str:
    """Generate a new UUID4 as string."""
    return str(uuid.uuid4())


def generate_content_hash(content: str) -> str:
    """Generate SHA-256 hash of content for deduplication."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def now_utc() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable format (MM:SS or HH:MM:SS)."""
    if seconds < 3600:  # Less than 1 hour
        minutes, secs = divmod(seconds, 60)
        return f"{minutes:02d}:{secs:02d}"
    else:  # 1 hour or more
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_duration(duration_str: str) -> int:
    """Parse duration string (MM:SS or HH:MM:SS) to seconds."""
    parts = duration_str.split(':')
    
    if len(parts) == 2:  # MM:SS
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    elif len(parts) == 3:  # HH:MM:SS
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError(f"Invalid duration format: {duration_str}")


def format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human-readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def is_valid_url(url: str) -> bool:
    """Check if a string is a valid URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters."""
    # Remove invalid characters for filesystem
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Replace spaces with underscores
    sanitized = re.sub(r'\s+', '_', sanitized)
    
    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Ensure it's not empty and not too long
    if not sanitized:
        sanitized = "untitled"
    
    return sanitized[:255]  # Limit to 255 characters


def extract_title_from_content(content: str, max_length: int = 100) -> str:
    """Extract title from content (first line or sentence)."""
    # Clean HTML if present
    if '<' in content and '>' in content:
        soup = BeautifulSoup(content, 'html.parser')
        content = soup.get_text()
    
    # Get first line or sentence
    lines = content.strip().split('\n')
    first_line = lines[0].strip()
    
    # If first line is too short, try to get a better title
    if len(first_line) < 20 and len(lines) > 1:
        # Look for a longer line
        for line in lines[1:5]:  # Check next 4 lines
            line = line.strip()
            if len(line) > 20:
                first_line = line
                break
    
    # Clean and truncate
    title = re.sub(r'\s+', ' ', first_line)
    if len(title) > max_length:
        title = title[:max_length].rsplit(' ', 1)[0] + '...'
    
    return title or "Untitled"


def html_to_text(html_content: str) -> str:
    """Convert HTML content to clean text."""
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.ignore_emphasis = True
    h.body_width = 0  # Don't wrap lines
    
    return h.handle(html_content).strip()


def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace and formatting."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove markdown-style formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
    text = re.sub(r'`(.*?)`', r'\1', text)        # Code
    
    # Remove extra newlines but preserve paragraph breaks
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()


def count_words(text: str) -> int:
    """Count words in text."""
    # Remove HTML tags if present
    if '<' in text:
        text = html_to_text(text)
    
    # Simple word count
    words = text.split()
    return len(words)


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length, breaking at word boundaries."""
    if len(text) <= max_length:
        return text
    
    # Find last space before max_length
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + suffix


def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure directory exists, creating it if necessary."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_extension(filename: str) -> str:
    """Get file extension from filename."""
    return Path(filename).suffix.lower()


def is_audio_file(filename: str) -> bool:
    """Check if file is an audio file based on extension."""
    audio_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'}
    return get_file_extension(filename) in audio_extensions


def get_file_size(file_path: Union[str, Path]) -> int:
    """Get file size in bytes."""
    try:
        return Path(file_path).stat().st_size
    except (FileNotFoundError, OSError):
        return 0


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def format_duration(seconds: int) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS format."""
    if seconds < 0:
        return "0:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def get_audio_duration(file_path: Union[str, Path]) -> int:
    """Get audio file duration in seconds using ffprobe."""
    import subprocess

    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(file_path)
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            duration_float = float(result.stdout.strip())
            return round(duration_float)

        return 0

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError, FileNotFoundError):
        # ffprobe not available or file not found, try using mutagen as fallback
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(str(file_path))
            if audio and audio.info:
                return round(audio.info.length)
        except Exception:
            pass

        return 0


async def get_audio_duration_async(file_path: Union[str, Path]) -> int:
    """Get audio file duration in seconds using ffprobe (async version)."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_audio_duration, file_path)


async def get_file_size_async(file_path: Union[str, Path]) -> int:
    """Get file size in bytes (async version)."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_file_size, file_path)


def create_slug(text: str, max_length: int = 50) -> str:
    """Create URL-friendly slug from text."""
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    
    # Truncate if too long
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('-')
    
    return slug or 'untitled'


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple dictionaries, with later ones taking precedence."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get value from dictionary with dot notation support."""
    keys = key.split('.')
    current = data
    
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return default
    
    return current


def filter_dict(data: Dict[str, Any], allowed_keys: List[str]) -> Dict[str, Any]:
    """Filter dictionary to only include allowed keys."""
    return {k: v for k, v in data.items() if k in allowed_keys}


def validate_email(email: str) -> bool:
    """Validate email address format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """Mask sensitive data showing only first and last few characters."""
    if len(data) <= visible_chars * 2:
        return '*' * len(data)
    
    return f"{data[:visible_chars]}***{data[-visible_chars:]}"


class Timer:
    """Simple timer utility for measuring execution time."""
    
    def __init__(self) -> None:
        """Initialize timer."""
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
    
    def start(self) -> None:
        """Start the timer."""
        import time
        self._start_time = time.time()
        self._end_time = None
    
    def stop(self) -> float:
        """Stop the timer and return elapsed time."""
        import time
        if self._start_time is None:
            raise ValueError("Timer not started")
        
        self._end_time = time.time()
        return self._end_time - self._start_time
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time (stops timer if not already stopped)."""
        if self._start_time is None:
            raise ValueError("Timer not started")
        
        if self._end_time is None:
            return self.stop()
        
        return self._end_time - self._start_time
    
    def __enter__(self) -> 'Timer':
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        if self._end_time is None:
            self.stop()