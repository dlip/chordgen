"""Tests for the gen pipeline's ignore-words handling."""

from chordgen.gen import _merge_ignored, _split_ignored


def test_split_ignored_separates_case_insensitively():
    chords = [
        {"word": "ho"},
        {"word": "Oi"},
        {"word": "dog"},
        {"word": "Cat"},
    ]
    active, ignored = _split_ignored(chords, ["ho", "oi"])
    assert [c["word"] for c in active] == ["dog", "Cat"]
    assert [(i, c["word"]) for i, c in ignored] == [(0, "ho"), (1, "Oi")]


def test_split_ignored_passes_through_when_empty():
    chords = [{"word": "ho"}, {"word": "dog"}]
    active, ignored = _split_ignored(chords, [])
    assert active is chords
    assert ignored == []


def test_merge_ignored_preserves_order_and_clears_chord_alts():
    active = [
        {"word": "dog", "chord": "dg", "alt1": "", "alt2": "", "alt3": ""},
    ]
    ignored = [
        (0, {"word": "ho", "chord": "h", "alt1": "", "alt2": "", "alt3": "", "debug": "x"}),
        (2, {"word": "oi", "chord": "oi", "alt1": "", "alt2": "", "alt3": ""}),
    ]
    merged = _merge_ignored(active, ignored)
    assert [c["word"] for c in merged] == ["ho", "dog", "oi"]
    assert merged[0]["chord"] == ""
    assert merged[0]["alt1"] == ""
    assert merged[0].get("debug") == ""
    assert merged[2]["chord"] == ""
