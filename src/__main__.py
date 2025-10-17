"""
Main entry point for Newsletter Podcast Generator.

This module provides the main entry point for the CLI when running
the package with `python -m src` or through the installed console script.
"""

from src.cli import cli

if __name__ == "__main__":
    cli()