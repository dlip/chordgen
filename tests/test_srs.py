"""Tests for the persistence + speed-tracking layer in chordgen.srs."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fsrs import Rating, State

from chordgen import srs


@pytest.fixture
def progress_file(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    monkeypatch.setattr(srs, "PROGRESS_FILE", path)
    return path


@pytest.fixture
def scheduler():
    return srs.make_scheduler(relearn_steps=1, target_retention=0.9)


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------


def test_load_progress_missing_file_returns_empty_v3(progress_file):
    progress = srs.load_progress()
    assert progress["version"] == 3
    assert progress["speed_samples"] == []
    assert progress["words"] == {}
    assert progress["daily"]["new_count"] == 0
    assert progress["daily"]["review_count"] == 0


def test_load_progress_drops_legacy_file_with_wrong_version(progress_file):
    legacy = {
        "version": 2,
        "speed_samples": [40.0],
        "words": {"the": {"card": {}, "reps": 1, "wpm_ewma": 40.0}},
    }
    progress_file.write_text(json.dumps(legacy))

    progress = srs.load_progress()

    assert progress["version"] == 3
    assert progress["words"] == {}
    assert progress["speed_samples"] == []
    # The bad file should be removed from disk.
    assert not progress_file.exists()


def test_save_then_load_round_trips(progress_file, scheduler):
    progress = srs.load_progress()
    srs.record_review(progress, scheduler, "the", Rating.Good, 50.0)
    srs.save_progress(progress)

    reloaded = srs.load_progress()
    assert reloaded["words"]["the"]["reps"] == 1
    assert reloaded["words"]["the"]["lapses"] == 0
    assert reloaded["words"]["the"]["wpm_ewma"] == 50.0
    assert reloaded["speed_samples"] == [50.0]
    assert reloaded["daily"]["new_count"] == 1
    assert reloaded["daily"]["review_count"] == 0


# ---------------------------------------------------------------------------
# record_review
# ---------------------------------------------------------------------------


def test_record_review_creates_card_for_new_word(progress_file, scheduler):
    progress = srs.load_progress()
    card = srs.record_review(progress, scheduler, "hello", Rating.Good, None)

    assert "hello" in progress["words"]
    assert progress["words"]["hello"]["reps"] == 1
    # With relearn_steps=1, a single Good graduates the card.
    assert card.state == State.Review


def test_record_review_again_returns_relearning_card_after_review(
    progress_file, scheduler
):
    progress = srs.load_progress()
    # Graduate first.
    card = srs.record_review(progress, scheduler, "hello", Rating.Good, None)
    assert card.state == State.Review

    # Then lapse.
    later = datetime.now(timezone.utc) + timedelta(days=2)
    card = srs.record_review(
        progress, scheduler, "hello", Rating.Again, None, now=later
    )
    assert card.state == State.Relearning
    assert progress["words"]["hello"]["reps"] == 2


def test_record_review_appends_speed_sample_only_when_provided(
    progress_file, scheduler
):
    progress = srs.load_progress()
    srs.record_review(progress, scheduler, "a", Rating.Good, None)
    srs.record_review(progress, scheduler, "b", Rating.Good, 0.0)
    srs.record_review(progress, scheduler, "c", Rating.Good, 30.0)

    assert progress["speed_samples"] == [30.0]


def test_record_review_caps_speed_samples_at_200(progress_file, scheduler):
    progress = srs.load_progress()
    for i in range(250):
        srs.record_review(progress, scheduler, f"w{i}", Rating.Good, float(i + 1))

    assert len(progress["speed_samples"]) == srs.SPEED_SAMPLES_CAP
    # The oldest 50 samples should have been dropped.
    assert progress["speed_samples"][0] == 51.0
    assert progress["speed_samples"][-1] == 250.0


def test_record_review_updates_wpm_ewma_with_alpha_03(progress_file, scheduler):
    progress = srs.load_progress()

    srs.record_review(progress, scheduler, "hello", Rating.Good, 40.0)
    assert progress["words"]["hello"]["wpm_ewma"] == 40.0

    srs.record_review(progress, scheduler, "hello", Rating.Good, 60.0)
    expected = 0.3 * 60.0 + 0.7 * 40.0
    assert progress["words"]["hello"]["wpm_ewma"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# slow_threshold_wpm
# ---------------------------------------------------------------------------


def test_slow_threshold_returns_none_below_min_samples():
    progress = {"version": 2, "speed_samples": [40.0] * 5, "words": {}}
    assert srs.slow_threshold_wpm(progress, 0.7, min_samples=20) is None


def test_slow_threshold_is_fraction_of_median():
    samples = list(range(1, 21))  # median = 10.5
    progress = {"version": 2, "speed_samples": [float(s) for s in samples], "words": {}}

    threshold = srs.slow_threshold_wpm(progress, 0.7, min_samples=20)
    assert threshold == pytest.approx(10.5 * 0.7)


def test_slow_threshold_returns_none_when_fraction_zero():
    progress = {"version": 2, "speed_samples": [40.0] * 30, "words": {}}
    assert srs.slow_threshold_wpm(progress, 0.0, min_samples=20) is None


# ---------------------------------------------------------------------------
# Daily quotas
# ---------------------------------------------------------------------------


def test_daily_budget_initially_full(progress_file):
    progress = srs.load_progress()
    new_left, review_left = srs.daily_budget(progress, 10, 200)
    assert new_left == 10
    assert review_left == 200


def test_record_review_increments_new_count_for_first_seen(
    progress_file, scheduler
):
    progress = srs.load_progress()
    srs.record_review(progress, scheduler, "hello", Rating.Good, None)
    assert progress["daily"]["new_count"] == 1
    assert progress["daily"]["review_count"] == 0


def test_record_review_increments_review_on_next_day(
    progress_file, scheduler
):
    progress = srs.load_progress()
    today = datetime.now(timezone.utc)
    srs.record_review(progress, scheduler, "hello", Rating.Good, None, now=today)
    # Roll the date forward; same-card review should now count as review.
    tomorrow = today + timedelta(days=2)
    srs.record_review(
        progress, scheduler, "hello", Rating.Good, None, now=tomorrow
    )
    assert progress["daily"]["date"] == tomorrow.date().isoformat()
    assert progress["daily"]["new_count"] == 0
    assert progress["daily"]["review_count"] == 1


def test_record_review_does_not_double_count_same_day(
    progress_file, scheduler
):
    progress = srs.load_progress()
    srs.record_review(progress, scheduler, "hello", Rating.Good, None)
    # In-session re-drill of the same word doesn't increment again.
    srs.record_review(progress, scheduler, "hello", Rating.Again, None)
    assert progress["daily"]["new_count"] == 1
    assert progress["daily"]["review_count"] == 0


def test_daily_budget_clamps_to_zero_when_overshot(progress_file, scheduler):
    progress = srs.load_progress()
    for i in range(15):
        srs.record_review(progress, scheduler, f"w{i}", Rating.Good, None)
    new_left, _ = srs.daily_budget(progress, 10, 200)
    assert new_left == 0


# ---------------------------------------------------------------------------
# Lapses / leeches
# ---------------------------------------------------------------------------


def test_record_review_increments_lapses_only_on_review_lapse(
    progress_file, scheduler
):
    progress = srs.load_progress()
    # Graduate.
    srs.record_review(progress, scheduler, "hello", Rating.Good, None)
    assert srs.get_lapses(progress, "hello") == 0

    # Lapse from Review state.
    later = datetime.now(timezone.utc) + timedelta(days=2)
    srs.record_review(
        progress, scheduler, "hello", Rating.Again, None, now=later
    )
    assert srs.get_lapses(progress, "hello") == 1

    # Again while still in Relearning is *not* a fresh lapse.
    srs.record_review(
        progress, scheduler, "hello", Rating.Again, None, now=later
    )
    assert srs.get_lapses(progress, "hello") == 1


def test_is_leech_triggers_at_threshold(progress_file, scheduler):
    progress = srs.load_progress()
    srs.record_review(progress, scheduler, "hello", Rating.Good, None)

    when = datetime.now(timezone.utc)
    for i in range(3):
        when = when + timedelta(days=2)
        srs.record_review(
            progress, scheduler, "hello", Rating.Again, None, now=when
        )
        # bring it back to Review so the next Again counts as a lapse
        when = when + timedelta(minutes=10)
        srs.record_review(
            progress, scheduler, "hello", Rating.Good, None, now=when
        )
        when = when + timedelta(minutes=10)
        srs.record_review(
            progress, scheduler, "hello", Rating.Good, None, now=when
        )

    assert srs.get_lapses(progress, "hello") >= 3
    assert srs.is_leech(progress, "hello", threshold=3)
    assert not srs.is_leech(progress, "hello", threshold=99)
