"""Tests for the vocab pipeline's casing + dedup behaviour.

The pipeline contract: storage = native casing, dedup = case-insensitive,
single-letter whitelist = {"a", "I"}, anything else of length 1 is dropped.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from chordgen.vocab import SOURCES, VocabRow, VocabSource
from chordgen.vocab.pipeline import build_chords_csv


def _make_fake_source(rows: list[VocabRow]) -> type[VocabSource]:
    class _FakeSource(VocabSource):
        name = "fake"

        def fetch(self, cache_dir: Path) -> Path:
            cache_dir.mkdir(parents=True, exist_ok=True)
            stub = cache_dir / "fake.txt"
            stub.write_text("")
            return stub

        def parse(self, path: Path) -> Iterator[VocabRow]:
            yield from rows

    return _FakeSource


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path) as f:
        return list(csv.DictReader(f))


def _run(monkeypatch, tmp_path: Path, rows: list[VocabRow]) -> list[dict[str, str]]:
    monkeypatch.setitem(SOURCES, "fake", _make_fake_source(rows))
    out = tmp_path / "chords.csv"
    build_chords_csv(
        source_name="fake",
        output_file=out,
        cache_dir=tmp_path / "cache",
        size=1000,
        min_frequency=0.0,
    )
    return _read_csv(out)


def test_pipeline_preserves_natural_casing_for_I(monkeypatch, tmp_path):
    written = _run(
        monkeypatch,
        tmp_path,
        [VocabRow(word="I", frequency=7.0, category="pronoun")],
    )
    assert len(written) == 1
    assert written[0]["word"] == "I"
    assert written[0]["category"] == "pronoun"


def test_pipeline_dedups_case_insensitively(monkeypatch, tmp_path):
    written = _run(
        monkeypatch,
        tmp_path,
        [
            VocabRow(word="The", frequency=6.0, category=""),
            VocabRow(word="the", frequency=5.0, category=""),
        ],
    )
    assert len(written) == 1
    # Higher-frequency form, listed first, wins. Stored verbatim.
    assert written[0]["word"] == "The"


def test_pipeline_rejects_garbage(monkeypatch, tmp_path):
    written = _run(
        monkeypatch,
        tmp_path,
        [
            VocabRow(word="don't", frequency=5.0, category=""),
            VocabRow(word="123", frequency=5.0, category=""),
            VocabRow(word="a", frequency=7.0, category=""),
            VocabRow(word="I", frequency=7.0, category="pronoun"),
            # Apostrophe-stripped contractions are tagged ``_letter``
            # by the source and dropped via the sentinel-category rule.
            VocabRow(word="s", frequency=5.0, category="_letter"),
            # Proper nouns are tagged ``_propn`` and dropped likewise.
            VocabRow(word="John", frequency=5.0, category="_propn"),
        ],
    )
    words = {row["word"] for row in written}
    assert words == {"a", "I"}
