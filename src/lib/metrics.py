"""Simple in-memory metrics for Newsletter Podcast Generator."""

from collections import defaultdict

_counters: dict[str, int] = defaultdict(int)
_timings: dict[str, list[float]] = defaultdict(list)


def increment_counter(name: str) -> None:
    """Increment a named counter."""
    _counters[name] += 1


def record_processing_time(name: str, duration: float) -> None:
    """Record a processing time measurement."""
    _timings[name].append(duration)


def get_counter(name: str) -> int:
    """Get current value of a counter."""
    return _counters[name]


def get_timings(name: str) -> list[float]:
    """Get all recorded timings for a metric."""
    return _timings[name]
