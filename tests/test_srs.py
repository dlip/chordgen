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


def test_load_progress_missing_file_returns_empty_v2(progress_file):
    progress = srs.load_progress()
    assert progress == {
        "version": 2,
        "speed_samples": [],
        "words": {},
    }


def test_load_progress_drops_legacy_file_with_wrong_version(progress_file):
    legacy = {
        "the": {
            "correct_in_a_row": 3,
            "last_practiced": 0,
            "next_practice_due": 0,
        }
    }
    progress_file.write_text(json.dumps(legacy))

    progress = srs.load_progress()

    assert progress["version"] == 2
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
    assert reloaded["words"]["the"]["wpm_ewma"] == 50.0
    assert reloaded["speed_samples"] == [50.0]


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
