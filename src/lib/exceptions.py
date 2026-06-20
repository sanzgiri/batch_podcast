"""Custom exception classes for Newsletter Podcast Generator."""


class ServiceError(Exception):
    """Base exception for service-related errors."""

    pass


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


class ProcessingError(Exception):
    """Raised when the processing pipeline fails."""

    pass


class ContentExtractionError(Exception):
    """Raised when content extraction fails."""

    pass


class LLMError(ServiceError):
    """Raised when the LLM service fails."""

    pass


class TTSError(ServiceError):
    """Raised when the TTS service fails."""

    pass


class DuplicateContentError(Exception):
    """Raised when duplicate content is detected."""

    pass
