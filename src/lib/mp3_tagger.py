"""MP3 ID3 tag writer.

Uses mutagen to embed ID3v2 tags on generated podcast episodes so podcast
apps (Apple Podcasts, Pocket Casts, Overcast) display rich metadata.

Tags written:
  TIT2  title           Episode title (e.g. "The Batch - Issue 282")
  TPE1  artist          Podcast author (from profile.podcast_metadata.author)
  TALB  album           Podcast name (from profile.podcast_metadata.title)
  TDRC  date            Publication date
  TCON  genre           Category
  TLAN  language        Language
  COMM  comment         Newsletter summary / description
  WOAS  website         Source website
  WOAR  artist-website  Author website (if different)
  APIC  cover art       Embedded cover image (if image_url is reachable)

Idempotent: re-tagging an already-tagged file overwrites the existing
ID3 frames (mutagen behavior).
"""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import suppress
from datetime import datetime
from pathlib import Path

import aiohttp
from mutagen.id3 import (
    APIC,
    COMM,
    ID3,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TLAN,
    TPE1,
    TRCK,
    WOAR,
    WOAS,
)
from mutagen.mp3 import MP3

from src.lib.logging import get_logger
from src.lib.newsletter_config import PodcastMetadata

logger = get_logger(__name__)


class MP3Tagger:
    """Write rich ID3v2 tags onto a generated MP3 episode."""

    def __init__(self, cover_cache_dir: Path | None = None):
        # Optional on-disk cache for cover art so we don't re-fetch per episode.
        self.cover_cache_dir = cover_cache_dir
        if cover_cache_dir:
            cover_cache_dir.mkdir(parents=True, exist_ok=True)
        self._cover_bytes_cache: dict[str, bytes | None] = {}

    async def tag_episode(
        self,
        audio_file: Path,
        *,
        episode_title: str,
        podcast: PodcastMetadata,
        episode_description: str | None = None,
        publication_date: datetime | None = None,
        track_number: int | None = None,
    ) -> None:
        """Write ID3 tags onto `audio_file` in place."""
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        # Cover art fetch is async (network); everything else is fast/sync.
        cover_bytes: bytes | None = None
        cover_mime: str | None = None
        if podcast.image_url:
            cover_bytes, cover_mime = await self._get_cover_bytes(podcast.image_url)

        # Run mutagen writes in a thread; small but real sync I/O.
        await asyncio.to_thread(
            self._write_tags_sync,
            audio_file=audio_file,
            episode_title=episode_title,
            podcast=podcast,
            episode_description=episode_description,
            publication_date=publication_date,
            track_number=track_number,
            cover_bytes=cover_bytes,
            cover_mime=cover_mime,
        )
        logger.info(f'Tagged MP3: {audio_file.name} - "{episode_title}"')

    @staticmethod
    def _write_tags_sync(
        audio_file: Path,
        episode_title: str,
        podcast: PodcastMetadata,
        episode_description: str | None,
        publication_date: datetime | None,
        track_number: int | None,
        cover_bytes: bytes | None,
        cover_mime: str | None,
    ) -> None:
        try:
            audio = MP3(str(audio_file), ID3=ID3)
        except Exception as e:
            logger.warning(f"Could not open MP3 for tagging ({audio_file}): {e}")
            return

        if audio.tags is None:
            with suppress(Exception):
                audio.add_tags()

        tags = audio.tags
        if tags is None:
            logger.warning(f"Could not create tags for {audio_file}")
            return

        # Clear existing frames we're about to set so re-tagging is clean.
        for frame_id in (  # type: ignore[unreachable]
            "TIT2",
            "TPE1",
            "TALB",
            "TDRC",
            "TCON",
            "TLAN",
            "COMM",
            "WOAS",
            "WOAR",
            "APIC",
            "TRCK",
        ):
            tags.delall(frame_id)

        tags.add(TIT2(encoding=3, text=episode_title))
        tags.add(TPE1(encoding=3, text=podcast.author))
        tags.add(TALB(encoding=3, text=podcast.title))
        if publication_date:
            tags.add(TDRC(encoding=3, text=publication_date.strftime("%Y-%m-%d")))
        tags.add(TCON(encoding=3, text=podcast.category))
        tags.add(TLAN(encoding=3, text=podcast.language))

        if episode_description:
            tags.add(
                COMM(
                    encoding=3,
                    lang="eng",
                    desc="description",
                    text=episode_description[:4000],
                )
            )

        if podcast.website_url:
            tags.add(WOAS(url=podcast.website_url))
            tags.add(WOAR(url=podcast.website_url))

        if track_number is not None:
            tags.add(TRCK(encoding=3, text=str(track_number)))

        if cover_bytes and cover_mime:
            tags.add(
                APIC(
                    encoding=3,
                    mime=cover_mime,
                    type=3,  # 3 = front cover
                    desc="Cover",
                    data=cover_bytes,
                )
            )

        audio.save(v2_version=3)

    async def _get_cover_bytes(self, image_url: str) -> tuple[bytes | None, str | None]:
        """Fetch (and cache) cover image bytes + mime type."""
        if image_url in self._cover_bytes_cache:
            cached = self._cover_bytes_cache[image_url]
            if cached is None:
                return None, None
            return cached, self._guess_mime(image_url)

        # On-disk cache lookup
        if self.cover_cache_dir:
            cache_path = self.cover_cache_dir / self._cache_filename(image_url)
            if cache_path.exists():
                data = cache_path.read_bytes()
                self._cover_bytes_cache[image_url] = data
                return data, self._guess_mime(image_url)

        # Fetch
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            headers = {"User-Agent": "BatchPodcast/0.1"}
            async with (
                aiohttp.ClientSession(timeout=timeout, headers=headers) as s,
                s.get(image_url) as resp,
            ):
                if resp.status != 200:
                    logger.warning(f"Cover art fetch returned HTTP {resp.status}: {image_url}")
                    self._cover_bytes_cache[image_url] = None
                    return None, None
                data = await resp.read()
                mime = resp.headers.get("Content-Type", self._guess_mime(image_url))
                mime = mime.split(";")[0].strip()
        except (TimeoutError, aiohttp.ClientError) as e:
            logger.warning(f"Cover art fetch failed for {image_url}: {e}")
            self._cover_bytes_cache[image_url] = None
            return None, None

        if len(data) > 5 * 1024 * 1024:
            logger.warning(
                f"Cover art is unusually large ({len(data)} bytes); skipping: {image_url}"
            )
            self._cover_bytes_cache[image_url] = None
            return None, None

        self._cover_bytes_cache[image_url] = data

        if self.cover_cache_dir:
            cache_path = self.cover_cache_dir / self._cache_filename(image_url)
            try:
                cache_path.write_bytes(data)
            except OSError as e:
                logger.debug(f"Could not cache cover image to disk: {e}")

        return data, mime

    @staticmethod
    def _guess_mime(url: str) -> str:
        url_lower = url.lower()
        if url_lower.endswith(".png"):
            return "image/png"
        if url_lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if url_lower.endswith(".webp"):
            return "image/webp"
        if url_lower.endswith(".gif"):
            return "image/gif"
        return "image/jpeg"

    @staticmethod
    def _cache_filename(url: str) -> str:
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        ext = ""
        for cand in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            if url.lower().endswith(cand):
                ext = cand
                break
        return f"cover-{h}{ext or '.bin'}"
