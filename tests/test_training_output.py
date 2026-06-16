"""Tests for the TrainingOutput emitter.

TrainingOutput writes alternating word / chord lines, flushing a block
every 10 chorded rows. Rows without a chord are skipped and the chord
column is padded so words and chords line up visually.
"""

from __future__ import annotations

from pathlib import Path

from chordgen.chord import Chord
from chordgen.output.training import TrainingOutput


def _chord(word: str, chord_str: str) -> Chord:
    return {
        "word": word,
        "chord": chord_str,
        "category": "",
        "frequency": "5.00",
        "alt1": "",
        "alt2": "",
        "alt3": "",
        "options": None,
    }


def test_flushes_block_every_ten_chords(tmp_path: Path):
    out = TrainingOutput(file=tmp_path / "training.txt")
    chords = [_chord(f"word{i}", f"w{i}") for i in range(10)]
    out.output(chords)

    lines = (tmp_path / "training.txt").read_text().splitlines()
    # One word line + one chord line for the full block of ten.
    assert len(lines) == 2
    assert lines[0].split() == [f"word{i}" for i in range(10)]
    assert lines[1].split() == [f"w{i}" for i in range(10)]


def test_partial_block_under_ten_is_not_written(tmp_path: Path):
    out = TrainingOutput(file=tmp_path / "training.txt")
    out.output([_chord("the", "te"), _chord("and", "ad")])

    # Only nine-or-fewer rows: the block never reaches the flush point.
    assert (tmp_path / "training.txt").read_text() == ""


def test_rows_without_chord_are_skipped(tmp_path: Path):
    out = TrainingOutput(file=tmp_path / "training.txt")
    chords = [_chord("skipme", "")]
    chords += [_chord(f"word{i}", f"w{i}") for i in range(10)]
    out.output(chords)

    lines = (tmp_path / "training.txt").read_text().splitlines()
    assert "skipme" not in lines[0]
    assert lines[0].split() == [f"word{i}" for i in range(10)]


def test_chord_column_padded_to_word_width(tmp_path: Path):
    out = TrainingOutput(file=tmp_path / "training.txt")
    chords = [_chord("internationalization", "in")]
    chords += [_chord(f"w{i}", f"c{i}") for i in range(9)]
    out.output(chords)

    lines = (tmp_path / "training.txt").read_text().splitlines()
    # The chord ``in`` is padded so the next chord aligns under the
    # start of the following word.
    word_line, chord_line = lines[0], lines[1]
    first_word = word_line.split(" ")[0]
    assert chord_line.startswith("in" + " " * (len(first_word) + 1 - len("in")))
