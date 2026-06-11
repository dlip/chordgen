"""Tests for ``GenOptions.key_replacement``.

Covers the validator (now permissive on the source side so users can
remap punctuation like ``'``) and the scorer's per-character rewrite
that actually applies the mapping when generating chord candidates.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from chordgen.chord import Chord
from chordgen.config import GenOptions
from chordgen.scorer import Scorer


def _chord(word: str, category: str = "") -> Chord:
    return {
        "word": word,
        "chord": "",
        "category": category,
        "frequency": "5.00",
        "alt1": "",
        "alt2": "",
        "alt3": "",
        "options": None,
    }


def test_validator_accepts_apostrophe_key():
    # Punctuation keys are allowed on the source side so users can
    # remap characters that aren't on every keyboard layout.
    opts = GenOptions(key_replacement={"'": "x"})
    assert opts.key_replacement == {"'": "x"}


def test_validator_rejects_uppercase_key():
    # Chord candidates are generated from the lowercased word, so
    # an uppercase source key would never match anything.
    with pytest.raises(ValidationError):
        GenOptions(key_replacement={"Q": "k"})


def test_validator_rejects_whitespace_key():
    with pytest.raises(ValidationError):
        GenOptions(key_replacement={" ": "x"})


def test_validator_rejects_multi_char_key():
    with pytest.raises(ValidationError):
        GenOptions(key_replacement={"qu": "k"})


def test_validator_still_rejects_punctuation_value():
    # The replacement must be a real letter on the keyboard.
    with pytest.raises(ValidationError):
        GenOptions(key_replacement={"'": "'"})


def test_scorer_applies_apostrophe_replacement():
    # ``o'clock`` is a noun (not a contraction), so the scorer keeps
    # the apostrophe in the chord candidates. With ``"'": "x"`` the
    # chord-character ``'`` is rewritten to ``x`` before keyboard
    # scoring, letting an apostrophe-bearing chord actually get a
    # finite score.
    opts = GenOptions(key_replacement={"'": "x"})
    scorer = Scorer(opts)
    out = scorer.score(_chord("o'clock", category="noun"))
    options = out.get("options") or []
    chords = {opt["chord"] for opt in options}
    # No raw apostrophe should leak through into a scored chord.
    assert not any("'" in c for c in chords)
    # And at least one chord should contain the rewritten ``x``.
    assert any("x" in c for c in chords)
