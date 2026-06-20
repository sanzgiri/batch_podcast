"""URL-pattern enumerator for newsletters without RSS feeds.

Some sites (notably The Batch on deeplearning.ai) don't expose RSS but
publish episodes at predictable URLs like:

    https://www.deeplearning.ai/the-batch/issue-282/
    https://www.deeplearning.ai/the-batch/issue-283/
    ...

This module probes those URLs to discover unprocessed issues.

Strategy:
  1. Read the URL pattern from the newsletter profile (e.g. ".../issue-*").
  2. Optionally extract the highest known issue number from the database
     (or accept a starting hint).
  3. Probe issue N+1, N+2, ... with HEAD requests until we hit consecutive
     404s (default 3 in a row \u2192 stop).
  4. Return the list of URLs that returned 200.
"""

from __future__ import annotations

import asyncio
import re

import aiohttp

from src.lib.logging import get_logger

logger = get_logger(__name__)


class URLEnumerator:
    """Probe sequential numeric URLs to discover new episodes.

    Works for any newsletter whose `url_pattern` contains a single "*" that
    represents an integer issue number, e.g.:
        https://www.deeplearning.ai/the-batch/issue-*
        https://example.com/newsletter/v*
    """

    def __init__(
        self,
        url_pattern: str,
        max_consecutive_404: int = 3,
        max_probes: int = 50,
        request_timeout: int = 15,
        delay_between_requests: float = 0.5,
    ):
        if "*" not in url_pattern:
            raise ValueError(f"url_pattern must contain '*': {url_pattern!r}")
        self.url_pattern = url_pattern
        self.max_consecutive_404 = max_consecutive_404
        self.max_probes = max_probes
        self.request_timeout = request_timeout
        self.delay_between_requests = delay_between_requests

    def _format_url(self, issue_number: int) -> str:
        return self.url_pattern.replace("*", str(issue_number))

    @staticmethod
    def extract_issue_number(url: str, pattern: str) -> int | None:
        """Extract the integer that '*' represented in a generated URL.

        >>> URLEnumerator.extract_issue_number(
        ...   "https://example.com/issue-282/", "https://example.com/issue-*"
        ... )
        282
        """
        # Convert pattern to regex: escape, then replace \* with (\d+)
        regex = re.escape(pattern).replace(r"\*", r"(\d+)")
        m = re.search(regex, url)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                return None
        return None

    async def discover_new(
        self,
        start_from: int,
        known_urls: set[str] | None = None,
    ) -> list[tuple[int, str]]:
        """Probe issue numbers from `start_from` upward, return new (n, url) pairs.

        Stops after `max_consecutive_404` consecutive 404s or `max_probes` attempts.
        Skips URLs already in `known_urls`.
        """
        if start_from < 0:
            raise ValueError(f"start_from must be >= 0, got {start_from}")

        known_urls = known_urls or set()
        discovered: list[tuple[int, str]] = []
        consecutive_404 = 0
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        headers = {"User-Agent": "BatchPodcast/0.1 (+https://github.com/sanzgiri/batch_podcast)"}

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for offset in range(1, self.max_probes + 1):
                issue_n = start_from + offset
                url = self._format_url(issue_n)

                if url in known_urls:
                    logger.debug(f"Skipping known URL: {url}")
                    consecutive_404 = 0  # known URL counts as 'exists', resets counter
                    continue

                exists = await self._url_exists(session, url)
                if exists:
                    discovered.append((issue_n, url))
                    consecutive_404 = 0
                    logger.info(f"Discovered issue #{issue_n}: {url}")
                else:
                    consecutive_404 += 1
                    if consecutive_404 >= self.max_consecutive_404:
                        logger.info(
                            f"Stopping enumeration after {consecutive_404} consecutive 404s "
                            f"(last tried: issue {issue_n})"
                        )
                        break

                # Be polite to the server
                if self.delay_between_requests > 0:
                    await asyncio.sleep(self.delay_between_requests)

        return discovered

    async def _url_exists(self, session: aiohttp.ClientSession, url: str) -> bool:
        """HEAD-check a URL. Treat 2xx as exists; everything else as missing.

        Falls back to GET if HEAD returns 405/403 (some sites block HEAD).
        """
        try:
            async with session.head(url, allow_redirects=True) as resp:
                if resp.status == 200:
                    return True
                if resp.status in (405, 403):
                    # Site doesn't allow HEAD \u2014 try a partial GET
                    async with session.get(url, allow_redirects=True) as gresp:
                        return gresp.status == 200
                return False
        except (TimeoutError, aiohttp.ClientError) as e:
            logger.debug(f"URL probe failed for {url}: {e}")
            return False
