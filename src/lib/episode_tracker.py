"""Episode deduplication tracker.

Prevents reprocessing newsletters that are already in the database. Checks
by URL, content hash, GUID (from RSS), or (title + publication_date) tuple.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from sqlalchemy import or_, select

from src.lib.database import get_db_session
from src.lib.logging import get_logger
from src.models.newsletter import Newsletter

logger = get_logger(__name__)


class EpisodeTracker:
    """Track which newsletter URLs / contents / GUIDs are already processed."""

    async def get_known_urls(self, newsletter_profile_id: Optional[str] = None) -> set[str]:
        """Return the set of URLs already stored in the database.

        If newsletter_profile_id is given, restrict to that profile.
        """
        async with get_db_session() as db:
            stmt = select(Newsletter.url).where(Newsletter.url.is_not(None))
            if newsletter_profile_id:
                stmt = stmt.where(Newsletter.newsletter_profile_id == newsletter_profile_id)
            result = await db.execute(stmt)
            return {row[0] for row in result.all() if row[0]}

    async def get_highest_issue_number(self, newsletter_profile_id: str) -> int:
        """Return the largest issue_number stored for this profile, or 0 if none."""
        async with get_db_session() as db:
            stmt = (
                select(Newsletter.issue_number)
                .where(Newsletter.newsletter_profile_id == newsletter_profile_id)
                .where(Newsletter.issue_number.is_not(None))
            )
            result = await db.execute(stmt)
            issues: list[int] = []
            for (n,) in result.all():
                try:
                    issues.append(int(n))
                except (TypeError, ValueError):
                    continue
            return max(issues) if issues else 0

    async def is_processed(
        self,
        url: Optional[str] = None,
        guid: Optional[str] = None,
        content: Optional[str] = None,
        title: Optional[str] = None,
        publication_date: Optional[datetime] = None,
    ) -> bool:
        """Return True iff *any* of the given identifiers matches an existing newsletter.

        Checked in priority order: URL > content_hash > (title + publication_date).
        GUID is not stored on Newsletter today; we use URL as the GUID proxy.
        """
        if not any((url, guid, content, title)):
            return False

        async with get_db_session() as db:
            clauses = []

            if url:
                clauses.append(Newsletter.url == url)
            if guid and guid != url:
                # If GUID is a URL, treat it as one. Otherwise no field stores GUIDs today.
                if guid.startswith("http"):
                    clauses.append(Newsletter.url == guid)

            if content:
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                clauses.append(Newsletter.content_hash == content_hash)

            if title and publication_date:
                clauses.append(
                    (Newsletter.title == title)
                    & (Newsletter.publication_date == publication_date)
                )

            if not clauses:
                return False

            stmt = select(Newsletter.id).where(or_(*clauses)).limit(1)
            result = await db.execute(stmt)
            return result.scalar_one_or_none() is not None
