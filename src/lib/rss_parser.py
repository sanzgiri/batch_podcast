"""RSS / Atom feed parser for newsletter auto-discovery.

Thin async wrapper around feedparser. Used by BatchProcessor to discover
new newsletter episodes without manual URL entry.

Newsletters without RSS (e.g. The Batch on deeplearning.ai) can use the
URL-pattern enumerator in src.lib.url_enumerator instead.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

import aiohttp
import feedparser

from src.lib.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FeedEntry:
    """A single entry from an RSS/Atom feed."""

    title: str
    url: str
    guid: str
    published_date: datetime | None = None
    summary: str | None = None
    content: str | None = None

    @property
    def best_text(self) -> str | None:
        """Return the longest of content / summary, or None."""
        candidates = [c for c in (self.content, self.summary) if c]
        if not candidates:
            return None
        return max(candidates, key=len)


class RSSFeedParser:
    """Async RSS/Atom feed parser.

    feedparser is sync; we run it in a thread to avoid blocking the event loop.
    """

    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds

    async def parse_feed(self, feed_url: str) -> list[FeedEntry]:
        """Fetch and parse a feed, returning structured entries.

        Returns an empty list if the feed is empty, malformed, or unreachable.
        Does not raise on parse errors \u2014 logs and returns [].
        """
        logger.info(f"Fetching RSS feed: {feed_url}")

        # Fetch the bytes with aiohttp (better timeout/headers than urllib)
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            headers = {
                "User-Agent": "BatchPodcast/0.1 (+https://github.com/sanzgiri/batch_podcast)"
            }
            async with (
                aiohttp.ClientSession(timeout=timeout, headers=headers) as session,
                session.get(feed_url) as resp,
            ):
                if resp.status != 200:
                    logger.warning(f"RSS feed returned HTTP {resp.status}: {feed_url}")
                    return []
                body = await resp.read()
        except (TimeoutError, aiohttp.ClientError) as e:
            logger.warning(f"Failed to fetch RSS feed {feed_url}: {e}")
            return []

        # Parse in a thread (feedparser is sync + can be slow on big feeds)
        parsed = await asyncio.to_thread(feedparser.parse, body)

        if parsed.bozo and parsed.bozo_exception:
            logger.warning(
                f"Feed parser flagged {feed_url} as malformed: "
                f"{parsed.bozo_exception}. Continuing anyway."
            )

        entries: list[FeedEntry] = []
        for raw in parsed.entries:
            url = raw.get("link", "").strip()
            if not url:
                continue

            entry = FeedEntry(
                title=raw.get("title", "Untitled").strip(),
                url=url,
                guid=raw.get("id") or url,
                published_date=self._parse_date(raw),
                summary=self._extract_summary(raw),
                content=self._extract_content(raw),
            )
            entries.append(entry)

        logger.info(f"Parsed {len(entries)} entries from {feed_url}")
        return entries

    @staticmethod
    def _parse_date(raw) -> datetime | None:
        # feedparser exposes parsed dates as struct_time tuples.
        for key in ("published_parsed", "updated_parsed", "created_parsed"):
            t = raw.get(key)
            if t:
                try:
                    return datetime(*t[:6])
                except (TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _extract_content(raw) -> str | None:
        # Atom: <content type="html">...</content>; RSS: <content:encoded>
        content_list = raw.get("content")
        if content_list and isinstance(content_list, list):
            return content_list[0].get("value")
        return None

    @staticmethod
    def _extract_summary(raw) -> str | None:
        return raw.get("summary") or raw.get("description")

    def filter_entries(
        self,
        entries: list[FeedEntry],
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int | None = None,
    ) -> list[FeedEntry]:
        """Filter entries by date range, then sort newest-first and apply limit."""
        out = list(entries)

        if from_date or to_date:

            def in_range(e: FeedEntry) -> bool:
                if e.published_date is None:
                    return False
                if from_date and e.published_date < from_date:
                    return False
                return not (to_date and e.published_date > to_date)

            out = [e for e in out if in_range(e)]

        # Newest first \u2014 entries with no date sink to the end.
        out.sort(key=lambda e: e.published_date or datetime.min, reverse=True)

        if limit is not None and limit > 0:
            out = out[:limit]

        return out
