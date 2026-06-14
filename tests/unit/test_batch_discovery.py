"""Unit tests for batch-discovery primitives.

Covers pure logic in:
  - URLEnumerator.extract_issue_number
  - RSSFeedParser.filter_entries
  - BatchProcessor._dedupe_candidates / _entries_to_candidates
"""

from datetime import datetime

import pytest

from src.lib.rss_parser import FeedEntry, RSSFeedParser
from src.lib.url_enumerator import URLEnumerator
from src.services.batch_processor import BatchCandidate, BatchProcessor


class TestURLEnumeratorExtractIssueNumber:
    def test_extracts_integer_from_url(self):
        n = URLEnumerator.extract_issue_number(
            "https://www.deeplearning.ai/the-batch/issue-282/",
            "https://www.deeplearning.ai/the-batch/issue-*",
        )
        assert n == 282

    def test_extracts_without_trailing_slash(self):
        n = URLEnumerator.extract_issue_number(
            "https://example.com/issue-17",
            "https://example.com/issue-*",
        )
        assert n == 17

    def test_returns_none_when_no_match(self):
        n = URLEnumerator.extract_issue_number(
            "https://example.com/about",
            "https://example.com/issue-*",
        )
        assert n is None

    def test_returns_none_when_not_an_integer(self):
        # The pattern matches digits only; non-digit captures should not match
        n = URLEnumerator.extract_issue_number(
            "https://example.com/issue-abc",
            "https://example.com/issue-*",
        )
        assert n is None

    def test_init_requires_star_in_pattern(self):
        with pytest.raises(ValueError, match="must contain"):
            URLEnumerator("https://example.com/no-star-here")

    def test_format_url_replaces_star(self):
        e = URLEnumerator("https://example.com/n-*/")
        # Access via the same method discover_new uses internally
        assert e._format_url(42) == "https://example.com/n-42/"


class TestRSSFeedParserFilterEntries:
    def _make_entry(self, days_ago: int, title: str = "x") -> FeedEntry:
        from datetime import timedelta
        return FeedEntry(
            title=title,
            url=f"https://example.com/{title}",
            guid=f"https://example.com/{title}",
            published_date=datetime(2026, 1, 1) - timedelta(days=days_ago),
        )

    def test_sorts_newest_first(self):
        p = RSSFeedParser()
        entries = [
            self._make_entry(days_ago=10, title="old"),
            self._make_entry(days_ago=1, title="new"),
            self._make_entry(days_ago=5, title="mid"),
        ]
        out = p.filter_entries(entries)
        assert [e.title for e in out] == ["new", "mid", "old"]

    def test_limit_applies_after_sort(self):
        p = RSSFeedParser()
        entries = [
            self._make_entry(days_ago=10, title="old"),
            self._make_entry(days_ago=1, title="new"),
            self._make_entry(days_ago=5, title="mid"),
        ]
        out = p.filter_entries(entries, limit=2)
        assert [e.title for e in out] == ["new", "mid"]

    def test_from_date_filters_old_entries(self):
        p = RSSFeedParser()
        entries = [
            self._make_entry(days_ago=10, title="old"),
            self._make_entry(days_ago=1, title="new"),
        ]
        out = p.filter_entries(entries, from_date=datetime(2025, 12, 25))
        assert [e.title for e in out] == ["new"]

    def test_to_date_filters_new_entries(self):
        p = RSSFeedParser()
        entries = [
            self._make_entry(days_ago=10, title="old"),
            self._make_entry(days_ago=1, title="new"),
        ]
        out = p.filter_entries(entries, to_date=datetime(2025, 12, 25))
        assert [e.title for e in out] == ["old"]

    def test_entries_without_dates_dropped_when_filtering(self):
        p = RSSFeedParser()
        entries = [
            FeedEntry(title="dateless", url="a", guid="a"),
            self._make_entry(days_ago=1, title="new"),
        ]
        out = p.filter_entries(entries, from_date=datetime(2025, 1, 1))
        assert [e.title for e in out] == ["new"]

    def test_no_filters_preserves_all(self):
        p = RSSFeedParser()
        entries = [
            self._make_entry(days_ago=10, title="old"),
            self._make_entry(days_ago=1, title="new"),
        ]
        out = p.filter_entries(entries)
        assert len(out) == 2

    def test_empty_input_returns_empty(self):
        p = RSSFeedParser()
        assert p.filter_entries([]) == []


class TestFeedEntryBestText:
    def test_picks_longest(self):
        e = FeedEntry(
            title="t", url="u", guid="u",
            summary="short summary",
            content="much much longer content body",
        )
        assert e.best_text == "much much longer content body"

    def test_returns_only_available(self):
        e = FeedEntry(title="t", url="u", guid="u", summary="just summary")
        assert e.best_text == "just summary"

    def test_returns_none_when_both_missing(self):
        e = FeedEntry(title="t", url="u", guid="u")
        assert e.best_text is None


class TestBatchProcessorDedupe:
    def test_deduplicates_by_url(self):
        candidates = [
            BatchCandidate(url="https://a.example/1", title="A"),
            BatchCandidate(url="https://a.example/1", title="A duplicate"),
            BatchCandidate(url="https://a.example/2", title="B"),
        ]
        out = BatchProcessor._dedupe_candidates(candidates)
        assert len(out) == 2

    def test_keeps_richer_metadata_on_dedup(self):
        # If one duplicate has a date and the other doesn't, keep the one with the date.
        c1 = BatchCandidate(url="https://a.example/1", title=None)
        c2 = BatchCandidate(url="https://a.example/1", title="Real title")
        out = BatchProcessor._dedupe_candidates([c1, c2])
        assert len(out) == 1
        assert out[0].title == "Real title"

    def test_empty_input(self):
        assert BatchProcessor._dedupe_candidates([]) == []
