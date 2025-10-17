"""
Newsletter Podcast Generator package.

A comprehensive solution for converting newsletter content into podcast episodes
using AI-powered summarization and text-to-speech generation.
"""

__version__ = "0.1.0"
__author__ = "Newsletter Podcast Generator Team"
__email__ = "dev@newsletter-podcast.com"

# Import main components for easy access
# Use lazy imports to avoid importing heavy dependencies when not needed
def __getattr__(name):
    """Lazy import for package components."""
    if name == "app":
        from .api import app
        return app
    elif name == "cli":
        from .cli import cli
        return cli
    elif name == "NewsletterProcessor":
        from .services import NewsletterProcessor
        return NewsletterProcessor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["app", "cli", "NewsletterProcessor"]