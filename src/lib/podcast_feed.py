"""Podcast RSS feed generator.

Builds an iTunes-compatible RSS 2.0 feed from a list of podcast episodes.
Once written to disk, the feed can be served by any HTTP server (or just
opened directly in apps that accept file:// URLs).

Apple Podcasts spec: https://help.apple.com/itc/podcasts_connect/#/itcb54353390

We emit:
  - Standard RSS 2.0 channel + item fields (title, link, description, etc.)
  - iTunes extension fields (itunes:author, itunes:summary, itunes:image,
    itunes:explicit, itunes:duration, itunes:category)
  - Optional enclosure URLs (if you serve the MP3s, set base_url)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from feedgen.feed import FeedGenerator

from src.lib.newsletter_config import PodcastMetadata


@dataclass
class FeedEpisode:
    """A single episode for the podcast RSS feed."""

    title: str
    description: str
    audio_file_path: Path  # local path to the MP3
    duration_seconds: int
    publication_date: datetime
    guid: str  # unique stable id (e.g. newsletter URL)
    file_size_bytes: int = 0
    episode_url: str | None = None  # original article URL


class PodcastFeedGenerator:
    """Generate an iTunes-compatible RSS feed from podcast episodes."""

    def write_feed(
        self,
        podcast: PodcastMetadata,
        episodes: list[FeedEpisode],
        output_path: Path,
        *,
        base_url: str | None = None,
        feed_url: str | None = None,
    ) -> int:
        """Write an RSS XML feed to `output_path`.

        Args:
            podcast: Podcast-level metadata (title, author, image, ...)
            episodes: Episodes (any order; sorted newest-first when written)
            output_path: Path to the .xml / .rss file to write
            base_url: If given, build absolute MP3 URLs as
                f"{base_url}/{relative_path_from_output_dir}". If None,
                enclosure URLs use file:// paths (useful for local testing,
                not for actual subscriptions).
            feed_url: Self-referencing URL for the feed itself. Optional but
                podcast apps appreciate it for re-discovery.

        Returns:
            Number of episodes written.
        """
        fg = FeedGenerator()
        fg.load_extension("podcast")

        # --- Channel-level ---
        fg.title(podcast.title)
        fg.description(podcast.description)
        fg.author({"name": podcast.author, "email": podcast.email or ""})
        fg.language(podcast.language)
        # RSS 2.0 requires a <link> at channel level. Fall back to feed_url →
        # a synthetic example.com URL so the file is always valid.
        link_target = podcast.website_url or feed_url or "https://example.com/podcast"
        fg.link(href=link_target, rel="alternate")
        if feed_url:
            fg.link(href=feed_url, rel="self")
        if podcast.image_url:
            fg.logo(podcast.image_url)
            fg.image(podcast.image_url, title=podcast.title)

        # iTunes extensions
        fg.podcast.itunes_author(podcast.author)
        fg.podcast.itunes_summary(podcast.description)
        fg.podcast.itunes_category(podcast.category)
        fg.podcast.itunes_explicit("no")
        if podcast.image_url:
            fg.podcast.itunes_image(podcast.image_url)

        # --- Per-episode ---
        # Sort newest-first; that's the convention podcast apps expect.
        episodes_sorted = sorted(episodes, key=lambda e: e.publication_date, reverse=True)

        for ep in episodes_sorted:
            fe = fg.add_entry(order="append")
            fe.title(ep.title)
            fe.description(ep.description)
            fe.guid(ep.guid, permalink=False)
            fe.pubDate(self._tzaware(ep.publication_date))

            if ep.episode_url:
                fe.link(href=ep.episode_url)

            # Build enclosure URL (the link to the actual MP3)
            enclosure_url = self._build_enclosure_url(ep.audio_file_path, output_path, base_url)
            if enclosure_url:
                fe.enclosure(
                    url=enclosure_url,
                    length=str(ep.file_size_bytes),
                    type="audio/mpeg",
                )

            # iTunes extensions on the episode
            fe.podcast.itunes_duration(self._format_duration(ep.duration_seconds))
            fe.podcast.itunes_summary(ep.description)
            fe.podcast.itunes_author(podcast.author)
            fe.podcast.itunes_explicit("no")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        rss_xml = fg.rss_str(pretty=True)
        output_path.write_bytes(rss_xml)
        return len(episodes_sorted)

    @staticmethod
    def _tzaware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    @staticmethod
    def _format_duration(seconds: int) -> str:
        if seconds < 0:
            return "00:00:00"
        hh = seconds // 3600
        mm = (seconds % 3600) // 60
        ss = seconds % 60
        return f"{hh:02d}:{mm:02d}:{ss:02d}"

    @staticmethod
    def _build_enclosure_url(audio_path: Path, feed_path: Path, base_url: str | None) -> str | None:
        if base_url:
            # Compute the audio file's path relative to the feed's parent dir.
            import os

            rel = os.path.relpath(str(audio_path), start=str(feed_path.parent))
            rel = rel.replace("\\", "/")
            # URL-encode each path segment (preserve slashes)
            encoded = "/".join(quote(part) for part in rel.split("/"))
            return f"{base_url.rstrip('/')}/{encoded}"

        # No base URL -> emit a file:// URL (useful for local-only podcast players)
        try:
            abs_path = audio_path.resolve()
            return abs_path.as_uri()
        except (ValueError, OSError):
            return None
