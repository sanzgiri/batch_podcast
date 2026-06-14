"""Unit tests for playlist + podcast-feed generators."""

from datetime import datetime
from pathlib import Path

import pytest

from src.lib.newsletter_config import PodcastMetadata
from src.lib.playlist_generator import PlaylistEntry, PlaylistGenerator
from src.lib.podcast_feed import FeedEpisode, PodcastFeedGenerator


# ---------------------------------------------------------------------------
# PlaylistGenerator
# ---------------------------------------------------------------------------


class TestPlaylistGenerator:
    def test_writes_m3u8_with_header(self, tmp_path: Path):
        entries = [
            PlaylistEntry(audio_path=tmp_path / "a.mp3", title="Track A", duration_seconds=120),
            PlaylistEntry(audio_path=tmp_path / "b.mp3", title="Track B", duration_seconds=240),
        ]
        out = tmp_path / "playlist.m3u8"
        n = PlaylistGenerator.write(entries, out)
        assert n == 2
        content = out.read_text(encoding="utf-8")
        assert content.startswith("#EXTM3U\n")
        assert "#EXTINF:120,Track A" in content
        assert "#EXTINF:240,Track B" in content
        assert "a.mp3" in content
        assert "b.mp3" in content

    def test_relative_paths(self, tmp_path: Path):
        audio_dir = tmp_path / "audio" / "the-batch"
        audio_dir.mkdir(parents=True)
        playlist_dir = tmp_path / "playlists"
        playlist_dir.mkdir()
        entry = PlaylistEntry(
            audio_path=audio_dir / "ep1.mp3", title="Ep1", duration_seconds=60,
        )
        out = playlist_dir / "p.m3u8"
        PlaylistGenerator.write([entry], out, relative_to=playlist_dir)
        content = out.read_text(encoding="utf-8")
        # Should contain a relative path with ../, not an absolute path
        assert "../audio/the-batch/ep1.mp3" in content
        assert str(audio_dir) not in content

    def test_empty_entries_writes_just_header(self, tmp_path: Path):
        out = tmp_path / "empty.m3u8"
        n = PlaylistGenerator.write([], out)
        assert n == 0
        assert out.read_text() == "#EXTM3U\n"

    def test_unicode_title_in_m3u8(self, tmp_path: Path):
        e = PlaylistEntry(
            audio_path=tmp_path / "x.mp3", title="\u00e9pisode caf\u00e9 \u2014 1", duration_seconds=60,
        )
        out = tmp_path / "p.m3u8"
        PlaylistGenerator.write([e], out, format="m3u8")
        content = out.read_text(encoding="utf-8")
        assert "\u00e9pisode caf\u00e9" in content

    def test_m3u_format_strips_non_ascii(self, tmp_path: Path):
        e = PlaylistEntry(
            audio_path=tmp_path / "x.mp3", title="\u00e9pisode caf\u00e9", duration_seconds=60,
        )
        out = tmp_path / "p.m3u"
        PlaylistGenerator.write([e], out, format="m3u")
        content = out.read_text(encoding="ascii")
        # Non-ASCII should be replaced (mutagen-style ?)
        assert "?" in content

    def test_invalid_format_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="must be"):
            PlaylistGenerator.write([], tmp_path / "x.m3u8", format="xml")

    def test_creates_parent_directory(self, tmp_path: Path):
        deep = tmp_path / "a" / "b" / "c" / "p.m3u8"
        assert not deep.parent.exists()
        PlaylistGenerator.write([], deep)
        assert deep.exists()

    def test_unknown_duration_is_minus_one(self, tmp_path: Path):
        e = PlaylistEntry(audio_path=tmp_path / "x.mp3", title="x")
        # Default duration is -1; ensure that's what's written
        out = tmp_path / "p.m3u8"
        PlaylistGenerator.write([e], out)
        assert "#EXTINF:-1,x" in out.read_text()


# ---------------------------------------------------------------------------
# PodcastFeedGenerator
# ---------------------------------------------------------------------------


class TestPodcastFeedGenerator:
    @pytest.fixture
    def podcast(self) -> PodcastMetadata:
        return PodcastMetadata(
            title="Test Podcast",
            description="A test podcast for unit tests",
            author="Test Author",
            email="test@example.com",
            category="Technology",
            language="en-us",
            website_url="https://example.com",
        )

    @pytest.fixture
    def episode(self, tmp_path: Path) -> FeedEpisode:
        audio = tmp_path / "ep1.mp3"
        audio.write_bytes(b"fake audio")
        return FeedEpisode(
            title="Episode 1",
            description="Test episode description",
            audio_file_path=audio,
            duration_seconds=300,
            publication_date=datetime(2026, 6, 14, 10, 0, 0),
            guid="https://example.com/ep1",
            file_size_bytes=42,
            episode_url="https://example.com/ep1",
        )

    def test_writes_valid_xml(self, tmp_path: Path, podcast, episode):
        out = tmp_path / "feed.xml"
        n = PodcastFeedGenerator().write_feed(podcast, [episode], out)
        assert n == 1
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<rss" in content
        assert "<channel>" in content
        assert "Test Podcast" in content
        assert "Episode 1" in content
        # iTunes extensions present
        assert "itunes:author" in content
        assert "itunes:duration" in content

    def test_sorts_episodes_newest_first(self, tmp_path: Path, podcast):
        ep_old = FeedEpisode(
            title="Old", description="x",
            audio_file_path=tmp_path / "old.mp3",
            duration_seconds=60,
            publication_date=datetime(2025, 1, 1),
            guid="old", file_size_bytes=1,
        )
        ep_new = FeedEpisode(
            title="New", description="x",
            audio_file_path=tmp_path / "new.mp3",
            duration_seconds=60,
            publication_date=datetime(2026, 6, 1),
            guid="new", file_size_bytes=1,
        )
        # Pass in old, new order; output should be new, old
        out = tmp_path / "feed.xml"
        PodcastFeedGenerator().write_feed(podcast, [ep_old, ep_new], out)
        content = out.read_text(encoding="utf-8")
        new_pos = content.find("<title>New</title>")
        old_pos = content.find("<title>Old</title>")
        assert new_pos > 0
        assert old_pos > 0
        assert new_pos < old_pos, "Newer episode should appear before older one"

    def test_enclosure_with_base_url(self, tmp_path: Path, podcast, episode):
        out = tmp_path / "feed.xml"
        PodcastFeedGenerator().write_feed(
            podcast, [episode], out, base_url="https://podcasts.example.com",
        )
        content = out.read_text(encoding="utf-8")
        # Episode audio file is at tmp_path/ep1.mp3, feed is at tmp_path/feed.xml,
        # so relative path is "ep1.mp3"
        assert 'url="https://podcasts.example.com/ep1.mp3"' in content
        assert 'type="audio/mpeg"' in content

    def test_enclosure_without_base_url_uses_file_uri(self, tmp_path: Path, podcast, episode):
        out = tmp_path / "feed.xml"
        PodcastFeedGenerator().write_feed(podcast, [episode], out)
        content = out.read_text(encoding="utf-8")
        assert "file://" in content
        assert "ep1.mp3" in content

    def test_format_duration_hh_mm_ss(self):
        f = PodcastFeedGenerator._format_duration
        assert f(0) == "00:00:00"
        assert f(59) == "00:00:59"
        assert f(60) == "00:01:00"
        assert f(3600) == "01:00:00"
        assert f(3661) == "01:01:01"
        assert f(-1) == "00:00:00"

    def test_naive_datetime_is_treated_as_utc(self):
        f = PodcastFeedGenerator._tzaware
        naive = datetime(2026, 6, 14, 10, 0, 0)
        aware = f(naive)
        assert aware.tzinfo is not None

    def test_creates_parent_directory(self, tmp_path: Path, podcast, episode):
        deep = tmp_path / "a" / "b" / "feed.xml"
        assert not deep.parent.exists()
        PodcastFeedGenerator().write_feed(podcast, [episode], deep)
        assert deep.exists()
