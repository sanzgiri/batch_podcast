"""Unit tests for LLM response normalization (_normalize_parsed_response).

These tests cover the defensive parser that tolerates schema drift from
local Ollama models (which sometimes omit or rename fields).
"""

import pytest

from src.lib.exceptions import LLMError
from src.services.llm_summarizer import _normalize_parsed_response


class TestNormalizeParsedResponse:
    """The _normalize_parsed_response helper must be lenient with LLM output."""

    def test_well_formed_response_passes_through(self):
        parsed = {
            "summary": "Host: Hello.\nGuest: Hi.",
            "title": "Episode 1",
            "key_points": ["Point A", "Point B"],
        }
        result = _normalize_parsed_response(parsed)
        assert result["summary"] == "Host: Hello.\nGuest: Hi."
        assert result["title"] == "Episode 1"
        assert result["key_points"] == ["Point A", "Point B"]

    def test_missing_key_points_falls_back_to_empty_list(self):
        # llama3.1:8b often drops the key_points field
        parsed = {"summary": "Host: Hi.", "title": "Ep"}
        result = _normalize_parsed_response(parsed)
        assert result["key_points"] == []

    def test_summary_synonyms_are_accepted(self):
        # Some models emit "script" or "transcript" instead of "summary"
        for key in ("script", "transcript", "content", "text"):
            parsed = {key: "Host: Hi.", "title": "Ep"}
            result = _normalize_parsed_response(parsed)
            assert result["summary"] == "Host: Hi.", f"failed for key={key}"

    def test_title_synonyms_are_accepted(self):
        for key in ("episode_title", "headline"):
            parsed = {"summary": "Host: Hi.", key: "My Episode"}
            result = _normalize_parsed_response(parsed)
            assert result["title"] == "My Episode", f"failed for key={key}"

    def test_key_points_synonyms_are_accepted(self):
        for key in ("keypoints", "highlights", "takeaways"):
            parsed = {"summary": "Host: Hi.", "title": "Ep", key: ["A", "B"]}
            result = _normalize_parsed_response(parsed)
            assert result["key_points"] == ["A", "B"], f"failed for key={key}"

    def test_missing_title_uses_fallback(self):
        parsed = {"summary": "Host: Hi."}
        result = _normalize_parsed_response(parsed, fallback_title="Fallback Title")
        assert result["title"] == "Fallback Title"

    def test_missing_summary_raises_llmerror(self):
        parsed = {"title": "Ep", "key_points": []}
        with pytest.raises(LLMError, match="missing 'summary'"):
            _normalize_parsed_response(parsed)

    def test_empty_summary_raises_llmerror(self):
        parsed = {"summary": "   ", "title": "Ep"}
        with pytest.raises(LLMError, match="missing 'summary'"):
            _normalize_parsed_response(parsed)

    def test_non_string_summary_raises_llmerror(self):
        parsed = {"summary": ["not", "a", "string"], "title": "Ep"}
        with pytest.raises(LLMError, match="missing 'summary'"):
            _normalize_parsed_response(parsed)

    def test_key_points_non_list_coerced_to_empty(self):
        parsed = {"summary": "Host: Hi.", "title": "Ep", "key_points": "not a list"}
        result = _normalize_parsed_response(parsed)
        assert result["key_points"] == []

    def test_key_points_dict_items_stringified(self):
        # Some models emit list-of-dicts here
        parsed = {
            "summary": "Host: Hi.",
            "title": "Ep",
            "key_points": [{"point": "A"}, "B", 42],
        }
        result = _normalize_parsed_response(parsed)
        assert len(result["key_points"]) == 3
        assert all(isinstance(p, str) for p in result["key_points"])
        assert result["key_points"][1] == "B"
        assert result["key_points"][2] == "42"

    def test_key_points_truncated_at_10(self):
        parsed = {
            "summary": "Host: Hi.",
            "title": "Ep",
            "key_points": [f"Point {i}" for i in range(20)],
        }
        result = _normalize_parsed_response(parsed)
        assert len(result["key_points"]) == 10

    def test_summary_is_stripped(self):
        parsed = {"summary": "   Host: Hi.   \n", "title": "Ep"}
        result = _normalize_parsed_response(parsed)
        assert result["summary"] == "Host: Hi."

    def test_title_is_coerced_to_string_and_stripped(self):
        parsed = {"summary": "Host: Hi.", "title": 123}
        result = _normalize_parsed_response(parsed)
        # int is not a string, so fallback used
        assert result["title"] == "Untitled Episode"

    def test_summary_preferred_over_synonyms_when_both_present(self):
        parsed = {
            "summary": "real summary",
            "script": "should be ignored",
            "title": "Ep",
        }
        result = _normalize_parsed_response(parsed)
        assert result["summary"] == "real summary"


from src.services.llm_summarizer import _recover_truncated_json


class TestRecoverTruncatedJson:
    """_recover_truncated_json must salvage usable content from broken LLM JSON."""

    def test_complete_json_recovers_normally(self):
        raw = '{"title": "Ep", "summary": "Host: hi.\\nGuest: hello.", "key_points": ["a"]}'
        result = _recover_truncated_json(raw)
        assert result is not None
        assert result["summary"] == "Host: hi.\nGuest: hello."
        assert result["title"] == "Ep"

    def test_truncated_after_summary_recovers(self):
        # JSON cut off mid 'key_points' — should still recover summary + title
        raw = '{"title": "Episode 7", "summary": "Host: One.\\nGuest: Two.", "key_p'
        result = _recover_truncated_json(raw)
        assert result is not None
        assert result["summary"] == "Host: One.\nGuest: Two."
        assert result["title"] == "Episode 7"
        assert result["key_points"] == []

    def test_truncated_mid_summary_returns_none(self):
        # If we can't find a closing quote on the summary, give up.
        raw = '{"title": "Ep", "summary": "Host: this string never ends'
        result = _recover_truncated_json(raw)
        assert result is None

    def test_summary_synonyms_recovered(self):
        for key in ("script", "transcript", "content", "text"):
            raw = f'{{"{key}": "Host: hi."}}'
            result = _recover_truncated_json(raw)
            assert result is not None, f"failed for key={key}"
            assert result["summary"] == "Host: hi."

    def test_title_synonyms_recovered(self):
        for key in ("episode_title", "headline"):
            raw = f'{{"{key}": "My Ep", "summary": "Host: hi."}}'
            result = _recover_truncated_json(raw)
            assert result is not None
            assert result["title"] == "My Ep", f"failed for key={key}"

    def test_empty_string_returns_none(self):
        assert _recover_truncated_json("") is None
        assert _recover_truncated_json(None) is None  # type: ignore[arg-type]

    def test_no_summary_field_returns_none(self):
        raw = '{"title": "Ep", "key_points": ["a"]}'
        result = _recover_truncated_json(raw)
        assert result is None

    def test_handles_escaped_quotes_in_summary(self):
        raw = '{"summary": "Host: She said \\"hello\\" politely."}'
        result = _recover_truncated_json(raw)
        assert result is not None
        assert 'hello' in result["summary"]

    def test_handles_unicode_in_summary(self):
        raw = '{"summary": "Host: caf\u00e9 r\u00e9sum\u00e9 na\u00efve."}'
        result = _recover_truncated_json(raw)
        assert result is not None
        assert "caf\u00e9" in result["summary"]
