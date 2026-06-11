"""Tests for contraction handling: scorer + output emitters.

The chord generated for ``'s`` must contain the leading apostrophe
(the prefix-lock invariant in ``find_combinations`` requires every
chord to start with the first character of the word). Users without
a comfortable apostrophe key are expected to remap it via
``gen.key_replacement: "'": x``. Every binary-output emitter
(qmk/zmk/kanata/charachorder) prepends a backspace marker for
``contraction`` rows so the apostrophe attaches cleanly to the
previously-typed word — for both leading-apostrophe forms (``'s``)
and embedded-apostrophe forms (``n't``).
"""

from __future__ import annotations

import json
from pathlib import Path

from chordgen.chord import Chord
from chordgen.config import GenOptions
from chordgen.output.charachorder import CharaChorderOutput
from chordgen.output.kanata import KanataOutput
from chordgen.output.qmk import QmkOutput
from chordgen.output.zmk import ZmkOutput
from chordgen.scorer import Scorer


def _chord(word: str, chord_str: str = "", category: str = "") -> Chord:
    c: Chord = {
        "word": word,
        "chord": chord_str,
        "category": category,
        "frequency": "7.50",
        "alt1": "",
        "alt2": "",
        "alt3": "",
        "options": None,
    }
    return c


def test_scorer_keeps_leading_apostrophe_in_candidates():
    # Chord candidates for ``'s`` must all start with ``'`` because
    # find_combinations is prefix-locked. Without a key_replacement
    # for ``'`` the keyboard scorer rejects them (-1) so no options
    # survive.
    scorer = Scorer(GenOptions())
    out = scorer.score(_chord("'s", category="contraction"))
    options = out.get("options") or []
    assert all(opt["chord"].startswith("'") for opt in options)


def test_scorer_remaps_leading_apostrophe_via_key_replacement():
    # With ``"'": x`` set, the leading apostrophe is rewritten to
    # ``x`` after combination generation, producing scorable chords
    # that still preserve the prefix-lock relative to the original
    # word (the chord's first character represents the word's first
    # character).
    scorer = Scorer(GenOptions(key_replacement={"'": "x"}))
    out = scorer.score(_chord("'s", category="contraction"))
    options = out.get("options") or []
    chords = {opt["chord"] for opt in options}
    assert chords, "expected scorable options when ``'`` is remapped"
    # Every chord starts with the remapped first character.
    assert all(c.startswith("x") for c in chords)
    # And the bare ``s`` (without the apostrophe slot) must NOT win
    # — that would violate the prefix-lock invariant.
    assert "s" not in chords


def test_scorer_keeps_embedded_apostrophe_in_candidates():
    # ``n't`` candidates are prefix-locked on ``n``; the apostrophe
    # may or may not appear in a given combination but it is never
    # silently stripped.
    scorer = Scorer(GenOptions())
    out = scorer.score(_chord("n't", category="contraction"))
    options = out.get("options") or []
    chords = {opt["chord"] for opt in options}
    assert all(c.startswith("n") for c in chords)
    # No raw ``'`` leaks through as a scorable chord without a
    # key_replacement (the keyboard rejects it).
    assert all("'" not in c for c in chords)
    # Without the apostrophe slot, ``find_combinations`` for ``n't``
    # still yields the bare-``n`` and ``nt`` paths since the
    # apostrophe character is treated like any other character — but
    # any combination containing ``'`` is dropped by the scorer.
    assert "n" in chords
    assert "nt" in chords


def test_zmk_prepends_backspace_for_apostrophe(tmp_path: Path):
    out = ZmkOutput(
        chords_file=tmp_path / "z_chords.dtsi",
        macros_file=tmp_path / "z_macros.dtsi",
    )
    out.output([_chord("'s", chord_str="s", category="contraction")])
    macros = (tmp_path / "z_macros.dtsi").read_text()
    # Backspace before apostrophe in the body of the macro.
    assert "BSPC" in macros
    bspc_idx = macros.index("BSPC")
    quot_idx = macros.index("QUOT")
    assert bspc_idx < quot_idx
    # No shifted variant for apostrophe-led words.
    assert "MACRO(s_c_s_" not in macros


def test_kanata_prepends_backspace_for_apostrophe(tmp_path: Path):
    out = KanataOutput(
        file=tmp_path / "k.kbd",
        key_mapping={"s": "s"},
    )
    out.output([_chord("'s", chord_str="s", category="contraction")])
    body = (tmp_path / "k.kbd").read_text()
    # Macro body should contain ``bspc`` before the literal ``'``.
    assert "bspc" in body
    bspc_idx = body.index("bspc")
    apos_idx = body.index(" ' ")
    assert bspc_idx < apos_idx
    # No shifted variant for apostrophe-led words: only one chord line
    # in the defchordsv2 body (excluding the wrapping ``(defchordsv2``).
    chord_lines = [
        line for line in body.splitlines() if line.startswith("  (")
    ]
    assert len(chord_lines) == 1


def test_qmk_prepends_backspace_for_apostrophe(tmp_path: Path):
    out = QmkOutput(file=tmp_path / "q.def")
    out.output([_chord("'s", chord_str="s", category="contraction")])
    body = (tmp_path / "q.def").read_text()
    # SUBS literal starts with the ``\b`` escape, then the apostrophe.
    assert '"\\b\'s ' in body
    # No shifted (capitalised) variant for apostrophe-led words.
    assert '"\'S ' not in body


def test_charachorder_prepends_backspace_for_apostrophe(tmp_path: Path):
    out = CharaChorderOutput(file=tmp_path / "cc.json")
    out.output([_chord("'s", chord_str="s", category="contraction")])
    data = json.loads((tmp_path / "cc.json").read_text())
    word_keys = data["chords"][0][1]
    # ASCII 8 (backspace) prepends the apostrophe + tail bytes.
    assert word_keys[0] == 8
    assert word_keys[1] == ord("'")
    assert word_keys[2] == ord("s")


def test_zmk_prepends_backspace_for_embedded_apostrophe(tmp_path: Path):
    # ``n't`` (don't, can't, ...) gets the same backspace prefix.
    out = ZmkOutput(
        chords_file=tmp_path / "z_chords.dtsi",
        macros_file=tmp_path / "z_macros.dtsi",
    )
    out.output([_chord("n't", chord_str="nt", category="contraction")])
    macros = (tmp_path / "z_macros.dtsi").read_text()
    assert "BSPC" in macros
    bspc_idx = macros.index("BSPC")
    quot_idx = macros.index("QUOT")
    assert bspc_idx < quot_idx
    # No shifted variant for embedded-apostrophe contractions either.
    assert "MACRO(s_c_nt_" not in macros


def test_qmk_prepends_backspace_for_embedded_apostrophe(tmp_path: Path):
    out = QmkOutput(file=tmp_path / "q.def")
    out.output([_chord("n't", chord_str="nt", category="contraction")])
    body = (tmp_path / "q.def").read_text()
    # SUBS literal starts with the ``\b`` escape, then the literal
    # ``n't`` with the apostrophe preserved.
    assert '"\\bn\'t ' in body


def test_charachorder_prepends_backspace_for_embedded_apostrophe(tmp_path: Path):
    out = CharaChorderOutput(file=tmp_path / "cc.json")
    out.output([_chord("n't", chord_str="nt", category="contraction")])
    data = json.loads((tmp_path / "cc.json").read_text())
    word_keys = data["chords"][0][1]
    assert word_keys[0] == 8
    assert word_keys[1] == ord("n")
    assert word_keys[2] == ord("'")
    assert word_keys[3] == ord("t")


def test_kanata_prepends_backspace_for_embedded_apostrophe(tmp_path: Path):
    out = KanataOutput(
        file=tmp_path / "k.kbd",
        key_mapping={"n": "n", "t": "t"},
    )
    out.output([_chord("n't", chord_str="nt", category="contraction")])
    body = (tmp_path / "k.kbd").read_text()
    assert "bspc" in body
    bspc_idx = body.index("bspc")
    apos_idx = body.index(" ' ")
    assert bspc_idx < apos_idx
