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


def test_orphaned_alt_is_recovered_and_reruns_preserve_relationships():
    base = _chord("this", [], category="demonstrative")
    base["alt1"] = "that"
    alt = _chord("that", [{"chord": "ta", "score": 1}])
    for _ in range(2):
        report = assign_chords([base, alt], GenOptions())
        assert alt["chord"] == "ta"
        assert report.no_options == ["this"]
        assert report.alt_covered == []
        assert base["alt1"] == "that"


def test_collision_blocked_base_does_not_suppress_alt():
    pin = _chord("pin", [], frequency="")
    pin["chord"] = "ab"
    base = _chord("base", [{"chord": "ba", "score": 1}])
    base["alt1"] = "forms"
    alt = _chord("forms", [{"chord": "fm", "score": 1}])
    report = assign_chords([pin, base, alt], GenOptions())
    assert pin["chord"] == "ab"
    assert alt["chord"] == "fm"
    assert report.no_options == ["base"]


def test_assigned_or_pinned_base_covers_alt():
    for pinned in (False, True):
        base = _chord("base", [{"chord": "bs", "score": 1}],
                      frequency="" if pinned else "5")
        if pinned:
            base["chord"] = "bs"
        base["alt1"] = base["alt2"] = "forms"
        alt = _chord("forms", [{"chord": "fm", "score": 1}])
        report = assign_chords([base, alt], GenOptions())
        assert base["chord"] == "bs"
        assert alt["chord"] == ""
        assert report.alt_covered == ["forms"]
        assert report.no_options == []


def test_recovery_handles_chain_and_cycle():
    for cycle in (False, True):
        first = _chord("first", [])
        second = _chord("second", [{"chord": "sc", "score": 1}])
        third = _chord("third", [{"chord": "th", "score": 1}])
        first["alt1"] = "second"
        second["alt1"] = "third"
        if cycle:
            third["alt1"] = "first"
        report = assign_chords([first, second, third], GenOptions())
        assert second["chord"] == "sc"
        assert third["chord"] == ""
        assert report.alt_covered == ["third"]
        assert report.no_options == ["first"]


def test_shared_alt_uses_any_assigned_owner():
    first = _chord("first", [])
    second = _chord("second", [{"chord": "sc", "score": 1}])
    first["alt1"] = second["alt1"] = "forms"
    alt = _chord("forms", [{"chord": "fm", "score": 1}])
    report = assign_chords([first, second, alt], GenOptions())
    assert report.alt_covered == ["forms"]
    assert not alt["chord"]


def test_short_base_and_discarded_duplicate_cannot_suppress_forms():
    short = _chord("ab", [])
    short["alt1"] = "forms"
    first = _chord("base", [])
    duplicate = _chord("BASE", [])
    duplicate["alt1"] = "forms"
    alt = _chord("forms", [{"chord": "fm", "score": 1}])
    report = assign_chords([short, first, duplicate, alt], GenOptions())
    assert alt["chord"] == "fm"
    assert report.duplicate == ["base"]


def test_recovery_respects_minimum_chord_length_and_uniqueness():
    base = _chord("base", [])
    base["alt1"] = "first"
    base["alt2"] = "second"
    first = _chord("first", [{"chord": "x", "score": 0},
                             {"chord": "ab", "score": 1}])
    second = _chord("second", [{"chord": "ba", "score": 1}])
    report = assign_chords([base, first, second], GenOptions(min_chord_length=2))
    assigned = [c["chord"] for c in (base, first, second) if c["chord"]]
    assert len(assigned) == 1
    assert len(assigned[0]) == 2
    assert len(report.no_options) == 2
