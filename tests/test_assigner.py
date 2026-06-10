"""Tests for the assigner's pool-eligibility rules.

Covers the fix that exempts contractions from ``min_word_length`` in
``assign_chords`` — mirroring the scorer, which already scored them,
but the assigner then silently dropped them from the pool.
"""

from __future__ import annotations

from chordgen.assigner import assign_chords
from chordgen.chord import Chord, Option
from chordgen.config import GenOptions


def _chord(
    word: str,
    options: list[Option],
    category: str = "",
    frequency: str = "5.00",
) -> Chord:
    return {
        "word": word,
        "chord": "",
        "category": category,
        "frequency": frequency,
        "alt1": "",
        "alt2": "",
        "alt3": "",
        "options": options,
    }


def test_contraction_exempt_from_min_word_length():
    opts = GenOptions(min_word_length=3)
    chords = [
        _chord(
            "'s",
            [{"chord": "xs", "score": 5}],
            category="contraction",
            frequency="7.00",
        ),
        _chord("the", [{"chord": "te", "score": 5}], frequency="7.50"),
    ]
    assign_chords(chords, opts)
    assert chords[0]["chord"] == "xs"
    assert chords[1]["chord"] == "te"


def test_short_non_contraction_still_dropped():
    opts = GenOptions(min_word_length=3)
    chords = [
        _chord("ab", [{"chord": "ab", "score": 5}], frequency="6.00"),
        _chord("abc", [{"chord": "abc", "score": 5}], frequency="5.00"),
    ]
    assign_chords(chords, opts)
    assert chords[0]["chord"] == ""
    assert chords[1]["chord"] == "abc"
