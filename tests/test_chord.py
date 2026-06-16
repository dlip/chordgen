"""Tests for the chord row helpers in chordgen.chord."""

from __future__ import annotations

import pytest

from chordgen.chord import build_alt_index, validate_chords


def test_build_alt_index_maps_alt_forms_to_base_slot_and_chord():
    chords = [
        {
            "word": "car",
            "chord": "ca",
            "alt1": "cars",
            "alt2": "carred",
            "alt3": "carring",
        },
    ]
    idx = build_alt_index(chords)
    assert idx == {
        "cars": ("car", 1, "ca"),
        "carred": ("car", 2, "ca"),
        "carring": ("car", 3, "ca"),
    }


def test_build_alt_index_skips_empty_and_self_alts():
    chords = [
        {
            "word": "set",
            "chord": "st",
            "alt1": "",
            "alt2": "set",  # identity — no alt slot generated
            "alt3": "sets",
        },
    ]
    idx = build_alt_index(chords)
    assert idx == {"sets": ("set", 3, "st")}


def test_build_alt_index_skips_rows_with_no_chord():
    chords = [
        {"word": "the", "chord": "", "alt1": "thes", "alt2": "", "alt3": ""},
    ]
    assert build_alt_index(chords) == {}


def test_build_alt_index_keeps_first_occurrence_on_collision():
    chords = [
        {"word": "car", "chord": "ca", "alt1": "cars", "alt2": "", "alt3": ""},
        {"word": "cur", "chord": "cu", "alt1": "cars", "alt2": "", "alt3": ""},
    ]
    idx = build_alt_index(chords)
    assert idx["cars"] == ("car", 1, "ca")


def test_validate_chords_accepts_distinct_chords():
    chords = [
        {"word": "the", "chord": "te"},
        {"word": "and", "chord": "ad"},
    ]
    # Should not raise.
    validate_chords(chords)


def test_validate_chords_ignores_empty_chords():
    chords = [
        {"word": "the", "chord": ""},
        {"word": "and", "chord": ""},
    ]
    validate_chords(chords)


def test_validate_chords_raises_on_anagram_collision():
    # Chords are compared by their sorted characters, so ``te`` and
    # ``et`` collide even though the raw strings differ.
    chords = [
        {"word": "the", "chord": "te"},
        {"word": "yet", "chord": "et"},
    ]
    with pytest.raises(Exception) as exc:
        validate_chords(chords)
    assert "yet" in str(exc.value)


def test_validate_chords_raises_on_exact_duplicate():
    chords = [
        {"word": "the", "chord": "te"},
        {"word": "their", "chord": "te"},
    ]
    with pytest.raises(Exception):
        validate_chords(chords)
