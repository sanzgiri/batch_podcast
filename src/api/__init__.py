"""
API package for Newsletter Podcast Generator.

This package contains FastAPI application and route definitions
for the REST API interface.
"""

from .main import app, create_app

__all__ = ["app", "create_app"]