"""Unit tests for the pure helpers in chordgen.train."""

from __future__ import annotations

import random

import pytest
from fsrs import Rating

from chordgen.train import (
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


def test_reinsertion_offset_again_in_2_to_4():
    rng = random.Random(0)
    for _ in range(50):
        offset = reinsertion_offset(Rating.Again, rng)
        assert 2 <= offset <= 4


def test_reinsertion_offset_non_again_returns_5():
    rng = random.Random(0)
    assert reinsertion_offset(Rating.Hard, rng) == 5
    assert reinsertion_offset(Rating.Good, rng) == 5


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
