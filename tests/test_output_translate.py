"""Tests for the ``translate_keys`` / ``translate_chord`` error paths.

Both the QMK and Kanata emitters refuse to silently drop a key they
can't map: QMK raises on a non-alphanumeric key with no configured
code, and Kanata raises on any key missing from ``key_mapping``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chordgen.chord import Chord
from chordgen.output.kanata import KanataOutput
from chordgen.output.qmk import QmkOutput


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


def test_qmk_translate_keys_maps_alnum_and_configured_codes():
    out = QmkOutput()
    # ``'`` resolves via the built-in qmk_key_codes table; ``a`` falls
    # through to the generic KC_A path.
    assert out.translate_keys("a") == ["KC_SFT_A"]
    assert out.translate_keys("'") == ["KC_QUOT"]


def test_qmk_translate_keys_raises_on_unknown_symbol():
    out = QmkOutput()
    with pytest.raises(Exception) as exc:
        out.translate_keys("!")
    assert "!" in str(exc.value)


def test_kanata_raises_on_unmapped_key(tmp_path: Path):
    # ``key_mapping`` is empty by default, so every letter is unmapped.
    out = KanataOutput(file=tmp_path / "k.kbd")
    with pytest.raises(Exception) as exc:
        out.output([_chord("the", "te")])
    assert "No key_map" in str(exc.value)
