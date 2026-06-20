"""Batch processor for newsletter auto-discovery + parallel processing.

Discovers new newsletter episodes (via RSS or URL-pattern enumeration),
filters out already-processed ones, and runs them through the full pipeline
with bounded concurrency.

Used by the `python -m src batch-process` CLI command.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from src.lib.config import Config
from src.lib.episode_tracker import EpisodeTracker
from src.lib.logging import get_logger
from src.lib.newsletter_config import NewsletterProfile, get_newsletter_config
from src.lib.rss_parser import FeedEntry, RSSFeedParser
from src.lib.url_enumerator import URLEnumerator
from src.models.newsletter import Newsletter
from src.services.newsletter_processor import NewsletterProcessor

logger = get_logger(__name__)


@dataclass
class BatchCandidate:
    """A single newsletter episode that has been discovered for processing."""

    url: str
    title: str | None = None
    published_date: datetime | None = None
    issue_number: int | None = None
    source: str = "unknown"  # 'rss' or 'enumeration'


@dataclass
class BatchResult:
    """Aggregate result of a batch run."""

    profile_id: str
    discovered: list[BatchCandidate] = field(default_factory=list)
    skipped: list[BatchCandidate] = field(default_factory=list)  # already processed
    succeeded: list[Newsletter] = field(default_factory=list)
    failed: list[tuple[BatchCandidate, str]] = field(default_factory=list)  # (candidate, error)

    @property
    def total_candidates(self) -> int:
        return len(self.discovered)

    @property
    def total_attempted(self) -> int:
        return len(self.succeeded) + len(self.failed)

    def summary(self) -> str:
        return (
            f"Batch '{self.profile_id}': "
            f"discovered={self.total_candidates}, "
            f"skipped={len(self.skipped)}, "
            f"succeeded={len(self.succeeded)}, "
            f"failed={len(self.failed)}"
        )


class BatchProcessor:
    """Orchestrate auto-discovery + parallel processing of newsletter episodes."""

    def __init__(self, config: Config, max_parallel: int = 1):
        self.config = config
        self.max_parallel = max_parallel
        self.newsletter_config = get_newsletter_config()
        self.tracker = EpisodeTracker()

    async def run(
        self,
        profile_id: str,
        latest: int | None = None,
        _all_unprocessed: bool = False,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        start_issue: int | None = None,
        dry_run: bool = False,
    ) -> BatchResult:
        """Discover and process episodes for the given newsletter profile.

        Args:
            profile_id: The newsletter profile to use (e.g. "the-batch")
            latest: If set, process only the N most recent discovered episodes
            all_unprocessed: If True, process every discovered-and-unprocessed episode
            from_date / to_date: Filter discovered RSS entries by publication date
            start_issue: For URL-pattern enumeration, start probing from issue N+1
                         (defaults to highest known issue + 1)
            dry_run: If True, discover but don't process

        Returns:
            BatchResult with discovered/skipped/succeeded/failed populated.
        """
        profile = self.newsletter_config.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Unknown newsletter profile: {profile_id}")
        if not profile.enabled:
            raise ValueError(f"Newsletter profile is disabled: {profile_id}")

        result = BatchResult(profile_id=profile_id)

        # 1. Discover candidates (RSS preferred, URL-pattern fallback)
        candidates = await self._discover(profile, profile_id, from_date, to_date, start_issue)
        result.discovered = candidates
        logger.info(f"Discovered {len(candidates)} candidate(s) for {profile_id}")

        if not candidates:
            return result

        # 2. Apply 'latest' limit (already date-sorted, newest first)
        if latest is not None and latest > 0:
            candidates = candidates[:latest]

        # 3. Filter out already-processed episodes
        known_urls = await self.tracker.get_known_urls(profile_id)
        to_process: list[BatchCandidate] = []
        for c in candidates:
            if c.url in known_urls:
                result.skipped.append(c)
                logger.info(f"Skipping already-processed: {c.url}")
            else:
                to_process.append(c)

        if not to_process:
            logger.info(f"All {len(candidates)} candidates already processed")
            return result

        # 4. Stop here if dry-run
        if dry_run:
            logger.info(f"Dry-run: would process {len(to_process)} episodes")
            return result

        # 5. Process in parallel with a semaphore
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def _process_one(candidate: BatchCandidate) -> None:
            async with semaphore:
                try:
                    async with NewsletterProcessor(self.config) as processor:
                        newsletter = await processor.process_newsletter_from_url(
                            url=candidate.url,
                            newsletter_profile_id=profile_id,
                        )
                    result.succeeded.append(newsletter)
                    logger.info(f"\u2713 Processed: {candidate.url}")
                except Exception as e:
                    err_str = str(e)
                    # Treat content-hash collisions as 'already processed'
                    if "UNIQUE constraint failed" in err_str and "content_hash" in err_str:
                        result.skipped.append(candidate)
                        logger.info(
                            f"Skipping (duplicate content): {candidate.url} — "
                            f"same content already in DB under a different URL"
                        )
                    else:
                        result.failed.append((candidate, err_str))
                        logger.error(f"\u2717 Failed: {candidate.url}: {e}")

        await asyncio.gather(*(_process_one(c) for c in to_process))

        return result

    async def _discover(
        self,
        profile: NewsletterProfile,
        profile_id: str,
        from_date: datetime | None,
        to_date: datetime | None,
        start_issue: int | None,
    ) -> list[BatchCandidate]:
        """Discover candidates via RSS (preferred) or URL-pattern enumeration."""
        candidates: list[BatchCandidate] = []

        # --- Strategy 1: RSS ---
        rss_url = profile.rss_feed
        if rss_url:
            parser = RSSFeedParser()
            entries = await parser.parse_feed(rss_url)
            entries = parser.filter_entries(entries, from_date=from_date, to_date=to_date)
            if entries:
                candidates.extend(self._entries_to_candidates(entries, profile))
                logger.info(f"RSS discovery returned {len(entries)} entries for {profile.name}")
            else:
                logger.info(f"RSS feed returned no entries (or unreachable): {rss_url}")

        # --- Strategy 2: URL-pattern enumeration ---
        # Run this if RSS gave us nothing OR if there's no RSS configured at all.
        # We always combine results and dedupe later.
        if not candidates and profile.url_pattern and "*" in profile.url_pattern:
            highest = (
                start_issue
                if start_issue is not None
                else await self.tracker.get_highest_issue_number(profile_id)
            )
            enumerator = URLEnumerator(profile.url_pattern)
            discovered = await enumerator.discover_new(start_from=highest)
            # Sort newest-first (highest issue number first) so that --latest N picks
            # the most recent issues, matching RSS-feed semantics.
            discovered.sort(key=lambda x: x[0], reverse=True)
            for issue_n, url in discovered:
                candidates.append(
                    BatchCandidate(
                        url=url,
                        issue_number=issue_n,
                        source="enumeration",
                    )
                )
            logger.info(
                f"URL-pattern enumeration found {len(discovered)} new issue(s) "
                f"starting from #{highest + 1}"
            )

        return self._dedupe_candidates(candidates)

    @staticmethod
    def _entries_to_candidates(
        entries: list[FeedEntry], profile: NewsletterProfile
    ) -> list[BatchCandidate]:
        out: list[BatchCandidate] = []
        for e in entries:
            issue_n = None
            if profile.url_pattern and "*" in profile.url_pattern:
                issue_n = URLEnumerator.extract_issue_number(e.url, profile.url_pattern)
            out.append(
                BatchCandidate(
                    url=e.url,
                    title=e.title,
                    published_date=e.published_date,
                    issue_number=issue_n,
                    source="rss",
                )
            )
        return out

    @staticmethod
    def _dedupe_candidates(candidates: list[BatchCandidate]) -> list[BatchCandidate]:
        """Remove duplicate URLs, preferring entries with more metadata."""
        seen: dict[str, BatchCandidate] = {}
        for c in candidates:
            if c.url not in seen:
                seen[c.url] = c
                continue
            # If we've already got this URL, keep the more-metadata-rich one
            existing = seen[c.url]
            if not existing.title and c.title or not existing.published_date and c.published_date:
                seen[c.url] = c
        return list(seen.values())
