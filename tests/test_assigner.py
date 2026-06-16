"""Tests for the assigner's pool-eligibility rules.

Covers the fix that exempts contractions from ``min_word_length`` in
``assign_chords`` — mirroring the scorer, which already scored them,
but the assigner then silently dropped them from the pool.
"""

from __future__ import annotations

from chordgen.assigner import assign_chords, _parse_freq, _split_into_tiers
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


def test_split_into_tiers_no_cutoffs_is_single_pass():
    pool = [_chord(f"w{i}", []) for i in range(5)]
    assert _split_into_tiers(pool, []) == [(0, 5)]


def test_split_into_tiers_partitions_at_cutoffs():
    pool = [_chord(f"w{i}", []) for i in range(10)]
    assert _split_into_tiers(pool, [3, 7]) == [(0, 3), (3, 7), (7, 10)]


def test_split_into_tiers_clamps_cutoffs_to_pool_length():
    pool = [_chord(f"w{i}", []) for i in range(4)]
    # A cutoff beyond the pool is clamped; the trailing tier is empty.
    assert _split_into_tiers(pool, [2, 99]) == [(0, 2), (2, 4), (4, 4)]


def test_parse_freq_returns_parsed_value_when_above_floor():
    assert _parse_freq(_chord("x", [], frequency="5.50"), floor=1.0) == 5.5


def test_parse_freq_floors_low_values():
    assert _parse_freq(_chord("x", [], frequency="0.10"), floor=1.0) == 1.0


def test_parse_freq_falls_back_on_missing_or_invalid():
    assert _parse_freq(_chord("x", [], frequency=""), floor=2.0) == 2.0
    assert _parse_freq(_chord("x", [], frequency="abc"), floor=2.0) == 2.0
