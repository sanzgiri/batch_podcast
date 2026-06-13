"""Text preprocessing — abbreviations, pronunciation overrides, inline markdown."""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Abbreviation expansion (tech-industry tuned)
# ---------------------------------------------------------------------------

ABBREVIATIONS: dict[str, str] = {
    r"\be\.g\.": "for example",
    r"\bi\.e\.": "that is",
    r"\betc\.": "and so on",
    r"\bvs\.": "versus",
    r"\bcf\.": "compare",
    r"\bw\.r\.t\.": "with respect to",
    r"\bAI\b": "A.I.",
    r"\bUS\b": "U.S.",
    r"\bUK\b": "U.K.",
    r"\bEU\b": "E.U.",
    r"\bUN\b": "U.N.",
    r"\bGDP\b": "G.D.P.",
    r"\bCEO\b": "C.E.O.",
    r"\bCFO\b": "C.F.O.",
    r"\bCTO\b": "C.T.O.",
    r"\bCOO\b": "C.O.O.",
    r"\bSaaS\b": "Sass",
    r"\bAPI\b": "A.P.I.",
    r"\bAPIs\b": "A.P.I.s",
    r"\bMCP\b": "M.C.P.",
    r"\bRSP\b": "R.S.P.",
    r"\bIPO\b": "I.P.O.",
    r"\bM&A\b": "mergers and acquisitions",
    r"\bR&D\b": "research and development",
    r"\bGDPR\b": "G.D.P.R.",
    r"\bFDA\b": "F.D.A.",
    r"\bSEC\b": "S.E.C.",
    r"\bIRS\b": "I.R.S.",
    r"\bNBA\b": "N.B.A.",
    r"\bNFL\b": "N.F.L.",
    r"\bNYC\b": "New York City",
    r"\bLLM\b": "L.L.M.",
    r"\bLLMs\b": "L.L.M.s",
    r"\bGPU\b": "G.P.U.",
    r"\bGPUs\b": "G.P.U.s",
    r"\bCPU\b": "C.P.U.",
    r"\bRL\b": "R.L.",
    r"\bRLHF\b": "R.L.H.F.",
}


def expand_abbreviations(text: str) -> str:
    """Replace abbreviations with TTS-friendly spelled-out forms."""
    for pat, repl in ABBREVIATIONS.items():
        text = re.sub(pat, repl, text)
    return text


def apply_pronunciations(text: str, pron: dict[str, str]) -> str:
    """Apply pronunciation overrides (key respelled phonetically).

    Longer keys are applied first so that multi-word entries
    (e.g. 'Tyler Cowen') win over substring matches.
    """
    if not pron:
        return text
    for key in sorted(pron.keys(), key=len, reverse=True):
        if key.startswith("_"):  # skip comment keys like "_comment"
            continue
        text = re.sub(r"\b" + re.escape(key) + r"\b", pron[key], text)
    return text


def clean_inline(s: str) -> str:
    """Strip inline markdown markup, keep human-readable text."""
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[\^[^\]]+\]", "", s)
    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"(?<![A-Za-z0-9_])_{1,3}(.+?)_{1,3}(?![A-Za-z0-9_])", r"\1", s)
    s = re.sub(r"~~(.+?)~~", r"\1", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()
