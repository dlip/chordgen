"""Unit tests for the pure helpers in chordgen.learn."""

from __future__ import annotations

import pytest
from fsrs import Rating

from chordgen.learn import (
    build_chords_map,
    compute_word_wpm,
    decide_rating,
    reinsertion_offset,
)


# ---------------------------------------------------------------------------
# decide_rating
# ---------------------------------------------------------------------------


def test_decide_rating_error_always_yields_again():
    assert decide_rating(True, None, None) == Rating.Again
    assert decide_rating(True, 100.0, 50.0) == Rating.Again
    assert decide_rating(True, 10.0, 50.0) == Rating.Again


def test_decide_rating_no_speed_signal_yields_good():
    assert decide_rating(False, None, 50.0) == Rating.Good


def test_decide_rating_threshold_none_yields_good_even_when_slow():
    assert decide_rating(False, 5.0, None) == Rating.Good


def test_decide_rating_below_threshold_yields_hard():
    assert decide_rating(False, 30.0, 50.0) == Rating.Hard


def test_decide_rating_at_or_above_threshold_yields_good():
    assert decide_rating(False, 50.0, 50.0) == Rating.Good
    assert decide_rating(False, 75.0, 50.0) == Rating.Good


# ---------------------------------------------------------------------------
# reinsertion_offset
# ---------------------------------------------------------------------------


def test_reinsertion_offset_appends_to_tail():
    # Index returned should equal queue length so list.insert places
    # the word at the very end of the visible queue.
    for queue_len in [0, 1, 5, 9]:
        for rating in (Rating.Again, Rating.Hard, Rating.Good):
            assert reinsertion_offset(rating, queue_len) == queue_len


# ---------------------------------------------------------------------------
# compute_word_wpm
# ---------------------------------------------------------------------------


def test_compute_word_wpm_uses_chars_plus_trailing_space():
    # 5-char word + 1 trailing space = 6 chars / 5 = 1.2 word
    # over 6 seconds (0.1 minute) => 12 wpm.
    wpm = compute_word_wpm(elapsed_seconds=6.0, word_len=5)
    assert wpm == pytest.approx(12.0)


def test_compute_word_wpm_zero_or_negative_elapsed_returns_none():
    assert compute_word_wpm(0.0, 5) is None
    assert compute_word_wpm(-1.0, 5) is None


def test_compute_word_wpm_zero_word_len_returns_none():
    assert compute_word_wpm(1.0, 0) is None


# ---------------------------------------------------------------------------
# build_chords_map
# ---------------------------------------------------------------------------


def test_build_chords_map_excludes_contractions():
    """Contractions (``'s``, ``n't``, ...) are output appendages — they
    aren't typed standalone, so learn mode must not surface them.
    Words with non-contraction apostrophes (``o'clock``) and unassigned
    chords are also handled."""

    chords = [
        {"word": "the", "chord": "th", "category": "function"},
        {"word": "'s", "chord": "s", "category": "contraction"},
        {"word": "n't", "chord": "nt", "category": "contraction"},
        {"word": "o'clock", "chord": "oc", "category": "noun"},
        {"word": "unchorded", "chord": "", "category": "noun"},
    ]
    assert set(build_chords_map(chords).keys()) == {"the", "o'clock"}


@pytest.mark.parametrize("recall", [False, True])
def test_activation_timing_includes_delay_before_macro(tmp_path, monkeypatch, recall):
    import asyncio
    from types import SimpleNamespace
    from chordgen import learn, srs
    from chordgen.config import LearnOptions

    monkeypatch.setattr(srs, "PROGRESS_FILE", tmp_path / "progress.json")
    clock = SimpleNamespace(now=10.0)
    monkeypatch.setattr(learn, "time", SimpleNamespace(monotonic=lambda: clock.now))
    app = learn.LearnApp([
        {"word": "hello", "chord": "hl", "frequency": "6"},
        {"word": "world", "chord": "wd", "frequency": "5"},
    ], LearnOptions(show_words=2, learning_steps=1), recall=recall)
    # Force unassisted prompts without modifying FSRS selection policy.
    monkeypatch.setattr(app, "chord_for_word", lambda *a, **kw: "")

    async def exercise():
        async with app.run_test() as pilot:
            display = str(app.query_one(learn.WordDisplay).render())
            assert ("world" not in display) == recall
            assert app.word_started_at == 10.0
            clock.now = 12.0
            app.update_word_display()
            assert app.word_started_at == 10.0
            await pilot.press(*"hello", "space")
            entry = app.progress["words"]["hello"]
            key = "recall_wpm_ewma" if recall else "wpm_ewma"
            assert entry[key] == pytest.approx(36.0)
            if recall:
                assert entry["recall_seconds"] == [2.0]
            assert app.word_started_at == 12.0
            clock.now = 15.0
            await pilot.press(*"world", "space")
            assert app.progress["words"]["world"][key] == pytest.approx(24.0)

    asyncio.run(exercise())


def test_assisted_recall_and_errors_do_not_enter_speed_history(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from chordgen import learn, srs
    from chordgen.config import LearnOptions

    monkeypatch.setattr(srs, "PROGRESS_FILE", tmp_path / "progress.json")
    clock = SimpleNamespace(now=10.0)
    monkeypatch.setattr(learn, "time", SimpleNamespace(monotonic=lambda: clock.now))
    app = learn.LearnApp([
        {"word": "hello", "chord": "hl", "frequency": "6"},
        {"word": "world", "chord": "wd", "frequency": "5"},
    ], LearnOptions(show_words=2, learning_steps=1), recall=True)

    async def exercise():
        async with app.run_test() as pilot:
            assert app.word_was_assisted
            clock.now = 12.0
            await pilot.press(*"hello", "space")
            assert app.progress["recall_speed_samples"] == []
            await pilot.press("x", "w", "backspace")
            assert app.word_started_at == 12.0
            clock.now = 15.0
            await pilot.press(*"world", "space")
            assert app.progress["recall_speed_samples"] == []
            assert app.progress["words"]["world"]["card"]["state"] != 2
            assert not app.flashing
            assert app._flash_timer is None

    asyncio.run(exercise())
