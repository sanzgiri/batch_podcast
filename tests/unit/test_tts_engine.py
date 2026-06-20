"""Unit tests for src.lib.tts_engine — text2audio-derived pipeline."""

import json

import pytest

from src.lib.tts_engine import (
    ABBREVIATIONS,
    apply_pronunciations,
    clean_inline,
    expand_abbreviations,
    list_presets,
    list_pronunciation_dicts,
    load_preset,
    load_pronunciations,
    parse_dialogue,
    parse_markdown_book,
    parse_text,
    parse_voice_spec,
    silence,
)
from src.lib.tts_engine.rendering import SAMPLE_RATE

# ---------------------------------------------------------------------------
# Text preprocessing
# ---------------------------------------------------------------------------


class TestExpandAbbreviations:
    def test_expands_tech_acronyms(self):
        assert expand_abbreviations("Test GPU") == "Test G.P.U."
        assert expand_abbreviations("Test LLM") == "Test L.L.M."
        assert expand_abbreviations("Test API") == "Test A.P.I."

    def test_expands_business_acronyms(self):
        assert expand_abbreviations("Our CEO said") == "Our C.E.O. said"
        assert expand_abbreviations("EU regulation") == "E.U. regulation"

    def test_expands_latin_abbrevs(self):
        # GPT is NOT in the ABBREVIATIONS dict (it's not an initialism in the dict)
        assert expand_abbreviations("models, e.g. these") == "models, for example these"
        assert expand_abbreviations("models, i.e. LLMs") == "models, that is L.L.M.s"

    def test_no_change_when_no_abbrevs(self):
        text = "This is plain prose with no acronyms."
        assert expand_abbreviations(text) == text

    def test_word_boundary_only(self):
        # "API" inside "RAPID" should not match
        result = expand_abbreviations("RAPID development")
        assert "A.P.I." not in result

    def test_abbreviations_dict_is_dict(self):
        assert isinstance(ABBREVIATIONS, dict)
        assert len(ABBREVIATIONS) > 20


class TestApplyPronunciations:
    def test_basic_replacement(self):
        pron = {"Sutskever": "Sootskehver"}
        assert apply_pronunciations("Sutskever said", pron) == "Sootskehver said"

    def test_word_boundary(self):
        pron = {"AI": "A.I."}
        # "AIDS" should not match "AI"
        result = apply_pronunciations("AIDS research", pron)
        assert result == "AIDS research"

    def test_longest_key_first(self):
        # "Tyler Cowen" should win over "Cowen"
        pron = {"Cowen": "wrong", "Tyler Cowen": "Tyler Coh-wen"}
        result = apply_pronunciations("Tyler Cowen wrote", pron)
        assert result == "Tyler Coh-wen wrote"

    def test_empty_dict_returns_input(self):
        assert apply_pronunciations("Hello", {}) == "Hello"

    def test_comment_keys_ignored(self):
        # Keys starting with _ are treated as comments
        pron = {"_comment": "this should be skipped", "Test": "TST"}
        result = apply_pronunciations("This is a Test of _comment", pron)
        assert "TST" in result
        # The literal underscore-comment must NOT be substituted into the text
        assert "this should be skipped" not in result


class TestCleanInline:
    def test_strips_bold(self):
        assert clean_inline("**bold**") == "bold"

    def test_strips_italic(self):
        assert clean_inline("*italic*") == "italic"

    def test_strips_links(self):
        assert clean_inline("[click here](http://x.com)") == "click here"

    def test_strips_code(self):
        assert clean_inline("a `code` snippet") == "a code snippet"

    def test_strips_urls(self):
        # clean_inline removes URLs and collapses runs of whitespace
        assert clean_inline("see https://example.com today") == "see today"


# ---------------------------------------------------------------------------
# Voice spec parsing
# ---------------------------------------------------------------------------


class TestParseVoiceSpec:
    def test_single_voice(self):
        result = parse_voice_spec("af_heart")
        assert result == [("af_heart", 1.0)]

    def test_blend_normalized(self):
        result = parse_voice_spec("af_heart:0.7,af_nicole:0.3")
        assert result == [("af_heart", 0.7), ("af_nicole", 0.3)]

    def test_blend_unnormalized_weights(self):
        # 7,3 should normalize to 0.7,0.3
        result = parse_voice_spec("af_heart:7,af_nicole:3")
        assert result == pytest.approx([("af_heart", 0.7), ("af_nicole", 0.3)])

    def test_empty_returns_empty_list(self):
        assert parse_voice_spec("") == []
        assert parse_voice_spec("none") == []
        assert parse_voice_spec("NONE") == []


# ---------------------------------------------------------------------------
# Parsing — text, dialogue, markdown
# ---------------------------------------------------------------------------


class TestParseText:
    def test_paragraphs_become_blocks(self):
        chapters = parse_text("Para one.\n\nPara two.\n\nPara three.")
        assert len(chapters) == 1
        # Each paragraph gets a para block + silence block
        para_blocks = [b for b in chapters[0].blocks if b.kind == "para"]
        assert len(para_blocks) == 3
        assert para_blocks[0].text == "Para one."

    def test_silence_between_paragraphs(self):
        chapters = parse_text("One.\n\nTwo.")
        silences = [b for b in chapters[0].blocks if b.kind == "silence"]
        assert len(silences) >= 1
        assert all(s.seconds > 0 for s in silences)

    def test_drops_code_fences(self):
        text = "Before.\n\n```\ncode here\n```\n\nAfter."
        chapters = parse_text(text)
        para_text = " ".join(b.text for b in chapters[0].blocks if b.kind == "para")
        assert "code here" not in para_text


class TestParseDialogue:
    def test_simple_two_speaker(self):
        text = "Host: Welcome.\nGuest: Thanks."
        chapters, keys = parse_dialogue(text)
        assert keys == {"Host": "A", "Guest": "B"}
        turns = [b for b in chapters[0].blocks if b.kind == "turn"]
        assert len(turns) == 2
        assert turns[0].speaker == "A"
        assert turns[0].text == "Welcome."
        assert turns[1].speaker == "B"
        assert turns[1].text == "Thanks."

    def test_speaker_continues_on_new_lines(self):
        text = "Host: First sentence.\nMore from host.\n\nGuest: My response."
        chapters, keys = parse_dialogue(text)
        turns = [b for b in chapters[0].blocks if b.kind == "turn"]
        assert len(turns) == 2
        assert "First sentence" in turns[0].text
        assert "More from host" in turns[0].text

    def test_silence_inserted_between_turns(self):
        text = "Host: A.\nGuest: B."
        chapters, _ = parse_dialogue(text)
        silences = [b for b in chapters[0].blocks if b.kind == "silence"]
        assert len(silences) >= 1


class TestParseMarkdownBook:
    def test_h1_creates_chapters(self):
        md = "# Chapter One\n\nText.\n\n# Chapter Two\n\nMore text."
        chapters = parse_markdown_book(md)
        assert len(chapters) == 2
        assert chapters[0].title == "Chapter One"
        assert chapters[1].title == "Chapter Two"

    def test_blockquote_becomes_quote_block(self):
        md = "# Chapter\n\nIntro.\n\n> A famous quote.\n\nMore text."
        chapters = parse_markdown_book(md)
        quotes = [b for b in chapters[0].blocks if b.kind == "quote"]
        assert len(quotes) == 1
        assert "famous quote" in quotes[0].text

    def test_list_joined_with_em_dashes(self):
        md = "# Ch\n\n- one\n- two\n- three"
        chapters = parse_markdown_book(md)
        lists = [b for b in chapters[0].blocks if b.kind == "list"]
        assert len(lists) == 1
        assert "—" in lists[0].text


# ---------------------------------------------------------------------------
# Presets and pronunciations
# ---------------------------------------------------------------------------


class TestPresets:
    def test_list_presets_includes_bundled(self):
        presets = list_presets()
        assert "podcast_two_host" in presets
        assert "audiobook_warm" in presets

    def test_load_known_preset(self):
        preset = load_preset("podcast_two_host")
        assert "voice-a" in preset
        assert "voice-b" in preset

    def test_load_unknown_preset_raises(self):
        with pytest.raises(FileNotFoundError):
            load_preset("nonexistent_preset_xyz")


class TestPronunciations:
    def test_list_pronunciations_includes_bundled(self):
        dicts = list_pronunciation_dicts()
        assert "ai_tech" in dicts
        assert "finance" in dicts

    def test_load_ai_tech(self):
        pron = load_pronunciations("ai_tech")
        assert "Sutskever" in pron
        # The _comment key must be stripped
        assert "_comment" not in pron

    def test_load_unknown_raises(self):
        with pytest.raises(FileNotFoundError):
            load_pronunciations("nonexistent_dict_xyz")

    def test_load_from_file_path(self, tmp_path):
        custom = tmp_path / "my_pron.json"
        custom.write_text(json.dumps({"Foo": "bar"}))
        pron = load_pronunciations(str(custom))
        assert pron == {"Foo": "bar"}


# ---------------------------------------------------------------------------
# Silence generation (rendering)
# ---------------------------------------------------------------------------


class TestSilence:
    def test_silence_length_matches_seconds(self):
        s = silence(1.0)
        assert len(s) == SAMPLE_RATE

    def test_silence_is_zeros(self):
        s = silence(0.5)
        assert s.sum() == 0

    def test_zero_seconds(self):
        s = silence(0.0)
        assert len(s) == 0
