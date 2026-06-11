"""Tests for the ``chordgen add`` interactive flow.

Covers the pure helpers (chord filtering, validation, alt collision
filtering, atomic write) and the end-to-end loop with mocked
``input``/``print`` to drive the prompts deterministically.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from chordgen.add import (
    _build_existing_chord_keys,
    _build_existing_words,
    _buffer_status,
    _collision_free_options,
    _detect_category,
    _filter_alt_collisions,
    _resolve_buffer,
    _validate_custom_chord,
    _write_chords_atomically,
    add_words,
)
from chordgen.chord import Chord
from chordgen.config import GenOptions


def _row(
    word: str,
    chord: str = "",
    *,
    category: str = "",
    frequency: str = "",
    alt1: str = "",
    alt2: str = "",
    alt3: str = "",
) -> Chord:
    return {
        "word": word,
        "chord": chord,
        "category": category,
        "frequency": frequency,
        "alt1": alt1,
        "alt2": alt2,
        "alt3": alt3,
        "options": None,
    }


def _seed_csv(path: Path, rows: list[Chord]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["word", "chord", "category", "frequency", "alt1", "alt2", "alt3"],
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path) as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_build_existing_words_includes_alt_slots():
    chords = [
        _row("car", chord="ca", alt1="cars", alt2="", alt3=""),
        _row("set", chord="se", alt1="sets", alt2="setting", alt3=""),
    ]
    assert _build_existing_words(chords) == {
        "car",
        "cars",
        "set",
        "sets",
        "setting",
    }


def test_build_existing_chord_keys_uses_sorted_keys():
    chords = [_row("car", chord="ac"), _row("be", chord="be")]
    # Sorted-key collapses ``ac`` and ``ca`` to the same key.
    assert _build_existing_chord_keys(chords) == {"ac", "be"}


def test_collision_free_options_filters_short_and_collisions():
    options = [
        {"chord": "a", "score": 1},   # below min_chord_length
        {"chord": "au", "score": 2},  # collides via sorted-key
        {"chord": "av", "score": 3},
        {"chord": "aw", "score": 4},
        {"chord": "ax", "score": 5},
    ]
    out = _collision_free_options(
        options,
        existing_chord_keys={"au"},
        min_chord_length=2,
        max_show=2,
    )
    assert [o["chord"] for o in out] == ["av", "aw"]


def test_collision_free_options_preserves_score_order():
    options = [
        {"chord": "ab", "score": 5},
        {"chord": "ac", "score": 1},
        {"chord": "ad", "score": 3},
    ]
    out = _collision_free_options(
        options,
        existing_chord_keys=set(),
        min_chord_length=2,
        max_show=10,
    )
    assert [o["chord"] for o in out] == ["ab", "ac", "ad"]


def test_detect_category_closed_class_lookup():
    assert _detect_category("can") == "modal"
    assert _detect_category("this") == "demonstrative"
    assert _detect_category("one") == "number"


def test_detect_category_open_class_via_pattern_en():
    # ``run`` is unambiguously a verb in pattern.en's POS tagger.
    assert _detect_category("run") == "verb"
    # ``apple`` is a noun.
    assert _detect_category("apple") == "noun"


def test_detect_category_empty_input_returns_empty():
    # Empty/whitespace input produces no tag — defensive path.
    assert _detect_category("") == ""


def test_validate_custom_chord_rejects_short(monkeypatch):
    opts = GenOptions(min_chord_length=2)
    keyboard = opts.keyboard.get_keyboard()
    ok, reason = _validate_custom_chord(
        "a", "apple", keyboard, opts, existing_chord_keys=set()
    )
    assert not ok
    assert "min_chord_length" in (reason or "")


def test_validate_custom_chord_rejects_first_letter_mismatch():
    opts = GenOptions(min_chord_length=2)
    keyboard = opts.keyboard.get_keyboard()
    ok, reason = _validate_custom_chord(
        "xy", "apple", keyboard, opts, existing_chord_keys=set()
    )
    assert not ok
    assert "first letter" in (reason or "")


def test_validate_custom_chord_rejects_collision():
    opts = GenOptions(min_chord_length=2)
    keyboard = opts.keyboard.get_keyboard()
    ok, reason = _validate_custom_chord(
        "ap", "apple", keyboard, opts, existing_chord_keys={"ap"}
    )
    assert not ok
    assert "collides" in (reason or "")


def test_validate_custom_chord_accepts_viable():
    opts = GenOptions(min_chord_length=2)
    keyboard = opts.keyboard.get_keyboard()
    ok, reason = _validate_custom_chord(
        "ap", "apple", keyboard, opts, existing_chord_keys=set()
    )
    assert ok
    assert reason is None


def test_resolve_buffer_handles_empty_digit_and_custom():
    opts = GenOptions(min_chord_length=2)
    keyboard = opts.keyboard.get_keyboard()
    options = [{"chord": "ap", "score": 1}, {"chord": "ae", "score": 2}]

    # Empty buffer -> top option.
    assert _resolve_buffer("", "apple", options, keyboard, opts, set()) == "ap"
    # Digit in range -> indexed option.
    assert _resolve_buffer("2", "apple", options, keyboard, opts, set()) == "ae"
    # Digit out of range -> None.
    assert _resolve_buffer("9", "apple", options, keyboard, opts, set()) is None
    # Custom chord that validates.
    assert _resolve_buffer("aw", "apple", options, keyboard, opts, set()) == "aw"
    # Custom chord that doesn't validate (wrong first letter).
    assert _resolve_buffer("xy", "apple", options, keyboard, opts, set()) is None


def test_colour_buffer_uses_red_when_invalid_green_when_valid():
    opts = GenOptions(min_chord_length=2)
    keyboard = opts.keyboard.get_keyboard()

    # Single-letter chord is below min_chord_length -> invalid with reason.
    valid, reason = _buffer_status(
        "a", "apple", [], keyboard, opts, existing_chord_keys=set()
    )
    assert not valid
    assert "min_chord_length" in (reason or "")

    # Two-letter valid chord -> valid, no reason.
    valid, reason = _buffer_status(
        "ap", "apple", [], keyboard, opts, existing_chord_keys=set()
    )
    assert valid
    assert reason is None

    # Out-of-range numeric index -> invalid with helpful reason.
    options = [{"chord": "ap", "score": 1}]
    valid, reason = _buffer_status(
        "9", "apple", options, keyboard, opts, existing_chord_keys=set()
    )
    assert not valid
    assert "1..1" in (reason or "")


def test_filter_alt_collisions_drops_only_colliding_slots():
    row = _row(
        "set", chord="se", alt1="sets", alt2="setting", alt3="settings",
    )
    _filter_alt_collisions(row, existing_words={"sets"})
    assert row["alt1"] == ""
    assert row["alt2"] == "setting"
    assert row["alt3"] == "settings"


def test_write_chords_atomically_round_trips(tmp_path: Path):
    rows = [
        _row("car", chord="ca", category="noun", frequency="6.5", alt1="cars"),
        _row("set", chord="se", category="verb", frequency="6.0"),
    ]
    out = tmp_path / "chords.csv"
    _write_chords_atomically(rows, out)
    read = _read_csv(out)
    assert [r["word"] for r in read] == ["car", "set"]
    assert read[0]["chord"] == "ca"
    assert read[0]["alt1"] == "cars"
    # No leftover ``.tmp`` file.
    assert not (tmp_path / "chords.csv.tmp").exists()


# ---------------------------------------------------------------------------
# End-to-end add_words
# ---------------------------------------------------------------------------


def _make_options(tmp_path: Path) -> GenOptions:
    """Build GenOptions pointed at a per-test chords.csv."""
    return GenOptions(file=tmp_path / "chords.csv", min_chord_length=2)


def test_add_words_skips_existing_word(tmp_path: Path):
    opts = _make_options(tmp_path)
    _seed_csv(opts.file, [_row("apple", chord="ap", alt1="apples")])

    output: list[str] = []
    inputs = iter([])
    add_words(
        ["apple"],
        opts,
        input_fn=lambda prompt: next(inputs),
        output_fn=output.append,
    )

    assert any("already in chords.csv" in line for line in output)
    rows = _read_csv(opts.file)
    assert [r["word"] for r in rows] == ["apple"]


def test_add_words_skips_existing_alt(tmp_path: Path):
    opts = _make_options(tmp_path)
    _seed_csv(opts.file, [_row("apple", chord="ap", alt1="apples")])

    output: list[str] = []
    inputs = iter([])
    add_words(
        ["apples"],
        opts,
        input_fn=lambda prompt: next(inputs),
        output_fn=output.append,
    )

    assert any("already in chords.csv" in line for line in output)
    # No new row written.
    rows = _read_csv(opts.file)
    assert [r["word"] for r in rows] == ["apple"]


def test_add_words_appends_with_default_inputs(tmp_path: Path):
    opts = _make_options(tmp_path)
    _seed_csv(opts.file, [])

    output: list[str] = []
    # Empty replies for both prompts: accept auto category, accept top chord.
    inputs = iter(["", ""])
    add_words(
        ["banana"],
        opts,
        input_fn=lambda prompt: next(inputs),
        output_fn=output.append,
    )

    rows = _read_csv(opts.file)
    assert len(rows) == 1
    assert rows[0]["word"] == "banana"
    # Reserved row: chord set, frequency empty.
    assert rows[0]["chord"]
    assert rows[0]["frequency"] == ""
    # Category was auto-detected as a noun and alt1 filled.
    assert rows[0]["category"] == "noun"
    assert rows[0]["alt1"] == "bananas"


def test_add_words_rewrites_csv_after_each_word(tmp_path: Path):
    opts = _make_options(tmp_path)
    _seed_csv(opts.file, [])

    snapshots: list[int] = []

    def echo(line: str) -> None:
        # Capture how many rows are on disk after every printed
        # "+ word -> ..." summary.
        if line.startswith("+ "):
            snapshots.append(len(_read_csv(opts.file)))

    inputs = iter(["", "", "", ""])
    add_words(
        ["banana", "carrot"],
        opts,
        input_fn=lambda prompt: next(inputs),
        output_fn=echo,
    )

    # CSV grew incrementally — first add produced 1 row on disk,
    # second add produced 2.
    assert snapshots == [1, 2]


def test_add_words_drops_alt_that_collides_with_existing_word(tmp_path: Path):
    opts = _make_options(tmp_path)
    # Pre-seed with ``bananas`` so the alt slot for ``banana`` collides.
    _seed_csv(opts.file, [_row("bananas", chord="bs", category="noun")])

    output: list[str] = []
    inputs = iter(["", ""])
    add_words(
        ["banana"],
        opts,
        input_fn=lambda prompt: next(inputs),
        output_fn=output.append,
    )

    rows = _read_csv(opts.file)
    banana_row = next(r for r in rows if r["word"] == "banana")
    # ``bananas`` is dropped; alt2/alt3 might still have been generated
    # but for noun category there are no other forms.
    assert banana_row["alt1"] == ""
