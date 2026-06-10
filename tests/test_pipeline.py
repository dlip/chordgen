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
    assert _rewrite_contraction_tail("t", "_propn") == ("t", "_propn")


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


def test_subtlex_retags_closed_class_words():
    # Demonstratives retag from determiner ("") to demonstrative.
    assert _rewrite_contraction_tail("this", "") == ("this", "demonstrative")
    assert _rewrite_contraction_tail("those", "") == ("those", "demonstrative")
    # Modals retag from verb to modal so pattern.en doesn't conjugate
    # them into nonsense like canned/canning.
    assert _rewrite_contraction_tail("can", "verb") == ("can", "modal")
    assert _rewrite_contraction_tail("would", "verb") == ("would", "modal")
    # Numbers retag from number ("") to number.
    assert _rewrite_contraction_tail("one", "") == ("one", "number")
    assert _rewrite_contraction_tail("first", "adjective") == ("first", "number")


def test_subtlex_retag_skips_propn_sentinel():
    # ``Will`` is also a name in SUBTLEX. The retag must not override
    # the ``_propn`` sentinel or the proper-noun filter would leak
    # name rows into the vocab as modals.
    assert _rewrite_contraction_tail("will", "_propn") == ("will", "_propn")


def test_subtlex_drops_contraction_stems():
    # SUBTLEX leaves apostrophe-stripped contraction stems behind when
    # it splits ``can't`` -> ``ca`` + ``n't``, ``won't`` -> ``wo`` +
    # ``n't``, ``ain't`` -> ``ai`` + ``n't``. The stems on their own
    # aren't real words; they get a dedicated drop-sentinel so the
    # pipeline filters them at ingest. Casing is preserved on the
    # ``word`` side because the sentinel is what triggers the drop.
    for stem in ("ca", "wo", "ai"):
        word, category = _rewrite_contraction_tail(stem, "verb")
        assert category.startswith("_"), stem
        assert category == "_contraction_stem", stem
    # Uppercase variants still hit the case-folded lookup.
    for stem in ("CA", "Wo", "Ai"):
        _, category = _rewrite_contraction_tail(stem, "verb")
        assert category == "_contraction_stem", stem


def test_pipeline_drops_contraction_stems(monkeypatch, tmp_path):
    # End-to-end: contraction-stem rows are flagged with the
    # ``_contraction_stem`` sentinel by the SUBTLEX adapter and the
    # pipeline's ``_DROP_PREFIX`` filter prunes them before write.
    written = _run(
        monkeypatch,
        tmp_path,
        [
            VocabRow(word="ca", frequency=6.0, category="_contraction_stem"),
            VocabRow(word="wo", frequency=6.0, category="_contraction_stem"),
            VocabRow(word="ai", frequency=6.0, category="_contraction_stem"),
            VocabRow(word="dog", frequency=5.0, category="noun"),
        ],
    )
    words = {row["word"] for row in written}
    assert words == {"dog"}


def test_subtlex_drops_non_words():
    # ``co`` is a hyphenation prefix; ``na``/``da`` are colloquial
    # subtitle residue. None of the three should survive ingest.
    for stem in ("co", "na", "da"):
        word, category = _rewrite_contraction_tail(stem, "noun")
        assert category.startswith("_"), stem
        assert category == "_non_word", stem
    # Casing doesn't matter — the lookup is case-folded.
    for stem in ("CO", "Na", "DA"):
        _, category = _rewrite_contraction_tail(stem, "noun")
        assert category == "_non_word", stem


def test_pipeline_drops_non_words(monkeypatch, tmp_path):
    written = _run(
        monkeypatch,
        tmp_path,
        [
            VocabRow(word="co", frequency=6.0, category="_non_word"),
            VocabRow(word="na", frequency=6.0, category="_non_word"),
            VocabRow(word="da", frequency=6.0, category="_non_word"),
            VocabRow(word="dog", frequency=5.0, category="noun"),
        ],
    )
    words = {row["word"] for row in written}
    assert words == {"dog"}


def test_subtlex_clears_interjection_verb_category():
    # SUBTLEX mis-tags ``eh`` as ``verb`` which then sends it through
    # the conjugator and produces nonsense like ``ehs``/``ehed``/
    # ``ehing``. The retag clears the category so no alts are
    # generated, but the word still flows through.
    assert _rewrite_contraction_tail("eh", "verb") == ("eh", "")
    assert _rewrite_contraction_tail("Eh", "verb") == ("Eh", "")
