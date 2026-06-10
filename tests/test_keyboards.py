"""Tests for the keyboard scoring models (standard + directional).

Covers two fixes:

- StandardKeyboard: same-finger middle+bottom row pairs now receive the
  ``same_column_chord_penalty`` (previously only top+middle was
  penalised and top+bottom rejected).
- DirectionalKeyboard: ``get_directional_changes`` previously always
  returned 0, making ``directional_change_penalty`` dead config. It now
  returns the real change count, and ``-1`` rejects such chords.
"""

from __future__ import annotations

from chordgen.keyboards.directional import DirectionalKeyboardOptions
from chordgen.keyboards.standard import StandardKeyboardOptions


def _standard(**overrides):
    return StandardKeyboardOptions(layout="qwerty", **overrides).create()


def _directional(**overrides):
    return DirectionalKeyboardOptions(layout="charachorder", **overrides).create()


# ---------------------------------------------------------------------
# StandardKeyboard: same-column pairs
# ---------------------------------------------------------------------


def test_top_middle_same_column_penalised():
    # qwerty `q` (top) + `a` (middle) share the pinky column.
    base = _standard(same_column_chord_penalty=0).score("qa")
    penalised = _standard(same_column_chord_penalty=2).score("qa")
    assert base >= 0
    assert penalised == base + 2


def test_middle_bottom_same_column_penalised():
    # qwerty `a` (middle) + `z` (bottom) share the pinky column. This
    # pair previously slipped through with no penalty.
    base = _standard(same_column_chord_penalty=0).score("az")
    penalised = _standard(same_column_chord_penalty=2).score("az")
    assert base >= 0
    assert penalised == base + 2


def test_middle_bottom_same_column_rejected_when_disabled():
    assert _standard(same_column_chord_penalty=-1).score("az") == -1


def test_top_bottom_same_column_always_rejected():
    assert _standard(same_column_chord_penalty=2).score("qz") == -1


# ---------------------------------------------------------------------
# DirectionalKeyboard: directional changes
# ---------------------------------------------------------------------


def test_directional_changes_counted():
    kb = _directional()
    # charachorder: `u` is a down-position key, `i` an in-position key,
    # both on the left hand -> one directional change.
    assert kb.get_directional_changes("ui") == 1
    # `e` (left hand, down) + `t` (right hand, down): no change within
    # either hand.
    assert kb.get_directional_changes("et") == 0


def test_directional_change_penalty_applied():
    base = _directional(directional_change_penalty=0).score("ui")
    penalised = _directional(directional_change_penalty=2).score("ui")
    assert base >= 0
    assert penalised == base + 2


def test_directional_change_penalty_not_applied_without_change():
    base = _directional(directional_change_penalty=0).score("et")
    penalised = _directional(directional_change_penalty=2).score("et")
    assert penalised == base


def test_directional_change_disable_rejects():
    kb = _directional(directional_change_penalty=-1)
    assert kb.score("ui") == -1
    assert kb.score("et") >= 0
