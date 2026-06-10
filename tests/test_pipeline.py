"""Tests for the vocab pipeline's casing + dedup behaviour.

The pipeline contract: storage = native casing, dedup = case-insensitive,
plain alphabetic words pass through, and an optional leading apostrophe
is allowed for SUBTLEX-split contraction tails (``'s``, ``'re``, ...).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from chordgen.vocab import SOURCES, VocabRow, VocabSource
from chordgen.vocab.pipeline import build_chords_csv
from chordgen.vocab.subtlex import _rewrite_contraction_tail


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
            VocabRow(word="123", frequency=5.0, category=""),
            VocabRow(word="a", frequency=7.0, category=""),
            VocabRow(word="I", frequency=7.0, category="pronoun"),
            # Lone letters that aren't real words (``e``, ``b``, ...)
            # are dropped — SUBTLEX-UK tags them ``unclassified`` and
            # they're subtitle artefacts (grades, spelling letters)
            # rather than lexemes.
            VocabRow(word="e", frequency=4.9, category=""),
            VocabRow(word="B", frequency=4.0, category=""),
            # Apostrophe-prefixed contraction tails (set upstream by the
            # SUBTLEX rewrite hook) flow through.
            VocabRow(word="'s", frequency=7.5, category="contraction"),
            # Kept-intact contractions like ``n't`` flow through.
            VocabRow(word="n't", frequency=6.9, category="contraction"),
            # Genuine apostrophe words flow through too — emitters
            # treat them literally based on category, not on ``'``.
            VocabRow(word="o'clock", frequency=4.6, category="adverb"),
            # Multi-apostrophe garbage is still rejected.
            VocabRow(word="''abc''", frequency=4.0, category=""),
            # Proper nouns are tagged ``_propn`` and dropped.
            VocabRow(word="John", frequency=5.0, category="_propn"),
        ],
    )
    words = {row["word"] for row in written}
    assert words == {"a", "I", "'s", "n't", "o'clock"}


def test_subtlex_rewrites_contraction_tails():
    # SUBTLEX-split contraction tails are rewritten to apostrophe-led
    # surface forms with the ``contraction`` category.
    assert _rewrite_contraction_tail("s", "verb") == ("'s", "contraction")
    assert _rewrite_contraction_tail("re", "verb") == ("'re", "contraction")
    assert _rewrite_contraction_tail("ll", "verb") == ("'ll", "contraction")
    assert _rewrite_contraction_tail("ve", "verb") == ("'ve", "contraction")
    assert _rewrite_contraction_tail("m", "verb") == ("'m", "contraction")
    assert _rewrite_contraction_tail("d", "verb") == ("'d", "contraction")
    # ``t`` is tagged ``name`` upstream which would map to ``_propn``;
    # the rewrite still reclaims it so it isn't dropped as a proper noun.
    assert _rewrite_contraction_tail("t", "_propn") == ("'t", "contraction")


def test_subtlex_retags_kept_intact_contractions():
    # ``n't`` (don't, can't, won't, ...) is kept intact by SUBTLEX
    # under POS=adverb. Retag it as ``contraction`` so the alt
    # generator skips it and emitters apply the backspace prefix.
    assert _rewrite_contraction_tail("n't", "adverb") == ("n't", "contraction")
    # Casing is normalised to lower.
    assert _rewrite_contraction_tail("N'T", "adverb") == ("n't", "contraction")


def test_subtlex_passes_through_non_tails():
    # Plain words are untouched. ``S`` (a real word in some corpora)
    # case-folds to a tail key and still gets rewritten — that's an
    # acceptable false positive given the rarity of bare ``S``.
    assert _rewrite_contraction_tail("hello", "verb") == ("hello", "verb")
    assert _rewrite_contraction_tail("they", "pronoun") == ("they", "pronoun")
    # ``o'clock`` and similar embedded-apostrophe words pass through
    # unchanged — they're filtered out at the pipeline level instead.
    assert _rewrite_contraction_tail("o'clock", "adverb") == ("o'clock", "adverb")
