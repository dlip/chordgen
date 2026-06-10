"""Tests for the drill personal-best leaderboard and the helpers
that key it."""

from datetime import datetime, timezone
from types import SimpleNamespace

from chordgen.config import Config
from chordgen.drill import (
    DrillApp,
    _empty_scores,
    record_drill_score,
    top_scores,
)
from chordgen.keyboard_view import resolve_layout_key


def test_record_drill_score_inserts_when_below_capacity():
    s = _empty_scores()
    when = datetime(2026, 6, 5, tzinfo=timezone.utc)
    assert record_drill_score(s, "standard:qwerty", 50.0, when=when) is True
    assert top_scores(s, "standard:qwerty") == [
        {"wpm": 50.0, "date": "2026-06-05"},
    ]


def test_record_drill_score_only_records_pb():
    s = _empty_scores()
    when = datetime(2026, 6, 5, tzinfo=timezone.utc)
    for w in [50.0, 60.0, 55.0, 40.0, 70.0, 45.0]:
        record_drill_score(s, "k", w, when=when)
    entries = top_scores(s, "k")
    # 50 was first (PB); 60 beat it (PB); 70 beat it (PB).
    # 55, 40, 45 never beat the current #1 so they are not recorded.
    assert [e["wpm"] for e in entries] == [70.0, 60.0, 50.0]
    # All PBs stored (no cap); display limits to SCORES_TOP_N.
    assert len(entries) == 3


def test_record_drill_score_rejects_when_not_pb():
    s = _empty_scores()
    when = datetime(2026, 6, 5, tzinfo=timezone.utc)
    for w in [50.0, 60.0, 55.0, 40.0, 70.0]:
        record_drill_score(s, "k", w, when=when)
    # Leaderboard is [70, 60, 50] (55, 40 never beat #1).
    # 65 beats 70? No, so it's not a PB.
    assert record_drill_score(s, "k", 65.0, when=when) is False
    assert record_drill_score(s, "k", 35.0, when=when) is False
    assert [e["wpm"] for e in top_scores(s, "k")] == [70.0, 60.0, 50.0]


def test_record_drill_score_rejects_zero_or_negative():
    s = _empty_scores()
    assert record_drill_score(s, "k", 0.0) is False
    assert record_drill_score(s, "k", -10.0) is False
    assert top_scores(s, "k") == []


def test_record_drill_score_partitions_by_layout_key():
    s = _empty_scores()
    when = datetime(2026, 6, 5, tzinfo=timezone.utc)
    record_drill_score(s, "standard:qwerty", 50.0, when=when)
    record_drill_score(s, "directional:charachorder", 90.0, when=when)
    assert [e["wpm"] for e in top_scores(s, "standard:qwerty")] == [50.0]
    assert [e["wpm"] for e in top_scores(s, "directional:charachorder")] == [90.0]


def test_resolve_layout_key_uses_layout_name_for_builtin_layouts():
    cfg = Config()
    cfg.gen.keyboard.type = "standard"
    cfg.gen.keyboard.standard.layout = "qwerty"
    assert resolve_layout_key(cfg) == "standard:qwerty"


def test_resolve_layout_key_uses_custom_layout_name_when_layout_is_custom():
    cfg = Config()
    cfg.gen.keyboard.type = "standard"
    cfg.gen.keyboard.standard.layout = "custom"
    cfg.gen.keyboard.standard.custom_layout_name = "colemak-mod"
    assert resolve_layout_key(cfg) == "standard:colemak-mod"


def test_resolve_layout_key_falls_back_to_custom_when_name_blank():
    cfg = Config()
    cfg.gen.keyboard.type = "standard"
    cfg.gen.keyboard.standard.layout = "custom"
    cfg.gen.keyboard.standard.custom_layout_name = ""
    assert resolve_layout_key(cfg) == "standard:custom"


def test_resolve_layout_key_directional_custom_layout_name():
    cfg = Config()
    cfg.gen.keyboard.type = "directional"
    cfg.gen.keyboard.directional.layout = "custom"
    cfg.gen.keyboard.directional.custom_layout_name = "my-svalboard"
    assert resolve_layout_key(cfg) == "directional:my-svalboard"


def test_drill_on_key_rejects_lowercase_for_uppercase_word():
    """Typing lowercase ``i`` against a stored ``"I"`` is rejected —
    chords output the correct casing, so the drill comparison is
    strictly case-sensitive."""

    flashed = []
    # Bypass DrillApp.__init__ (which expects a Textual app context)
    # and bind on_key onto a minimal stub carrying just the state
    # the method touches.
    stub = SimpleNamespace(
        session_finished=False,
        words_to_practice=["I"],
        letter_index=0,
        session_chars_typed=0,
        session_start_time=None,
        _start_timer_if_needed=lambda: None,
        update_word_display=lambda: None,
        flash_red=lambda: flashed.append(True),
    )
    event = SimpleNamespace(
        key="i",
        character="i",
        stop=lambda: None,
    )
    DrillApp.on_key(stub, event)
    assert stub.letter_index == 0
    assert stub.session_chars_typed == 0
    assert flashed == [True]


def test_drill_on_key_accepts_exact_case_uppercase():
    """Typing uppercase ``I`` against a stored ``"I"`` advances."""

    stub = SimpleNamespace(
        session_finished=False,
        words_to_practice=["I"],
        letter_index=0,
        session_chars_typed=0,
        session_start_time=None,
        _start_timer_if_needed=lambda: None,
        update_word_display=lambda: None,
        flash_red=lambda: None,
    )
    event = SimpleNamespace(
        key="I",
        character="I",
        stop=lambda: None,
    )
    DrillApp.on_key(stub, event)
    assert stub.letter_index == 1
    assert stub.session_chars_typed == 1
