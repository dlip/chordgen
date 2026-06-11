"""Tests for the chord row helpers in chordgen.chord."""

from __future__ import annotations

from chordgen.chord import build_alt_index


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
