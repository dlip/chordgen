"""Persistence + speed-tracking layer for the chordgen train mode.

Wraps an FSRS ``Card`` per word using the official ``fsrs`` library
(open-spaced-repetition/py-fsrs), and maintains a global rolling
window of recent per-word WPM samples so the trainer can derive a
"slow" threshold relative to the user's own typing speed.

The FSRS state machine itself (Learning -> Review -> Relearning,
stability, difficulty, retrievability) is delegated entirely to the
library — we only persist its serialisable form and decide how it
maps onto our session UX.

In addition to FSRS state, this module tracks Anki-style daily
quotas (new cards introduced and reviews answered per calendar day)
and a per-word lapse counter for leech detection.
"""

from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

from fsrs import Card, Rating, Scheduler, State

from chordgen.constants import CONFIG_DIR


PROGRESS_FILE: Path = CONFIG_DIR / "progress.json"

# Bumped from v2 to add daily quotas (new_count / review_count keyed
# on calendar date) and per-word lapse tracking. Files with a
# different version are wiped on first load — the user has not
# started using the trainer with persisted state yet, so no migration
# is needed.
PROGRESS_VERSION = 3

SPEED_SAMPLES_CAP = 200
WPM_EWMA_ALPHA = 0.3


class WordProgress(TypedDict):
    card: dict
    reps: int
    lapses: int
    wpm_ewma: float | None
    last_seen_date: str | None


class DailyState(TypedDict):
    date: str
    new_count: int
    review_count: int


class ProgressFile(TypedDict):
    version: int
    speed_samples: list[float]
    daily: DailyState
    words: dict[str, WordProgress]


def _today_iso(when: datetime | None = None) -> str:
    when = datetime.now(timezone.utc) if when is None else when
    return when.date().isoformat()


def _empty_daily(when: datetime | None = None) -> DailyState:
    return {"date": _today_iso(when), "new_count": 0, "review_count": 0}


def _empty() -> ProgressFile:
    return {
        "version": PROGRESS_VERSION,
        "speed_samples": [],
        "daily": _empty_daily(),
        "words": {},
    }


def load_progress() -> ProgressFile:
    """Load progress from disk. Files with a missing or non-matching
    ``version`` are wiped so we can evolve the schema without writing
    migrations."""
    if not PROGRESS_FILE.exists():
        return _empty()
    try:
        raw = json.loads(PROGRESS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return _empty()

    if not isinstance(raw, dict) or raw.get("version") != PROGRESS_VERSION:
        try:
            os.remove(PROGRESS_FILE)
        except OSError:
            pass
        return _empty()

    raw.setdefault("speed_samples", [])
    raw.setdefault("words", {})
    raw.setdefault("daily", _empty_daily())
    return raw  # type: ignore[return-value]


def save_progress(progress: ProgressFile) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------


def make_scheduler(
    learning_steps: int = 5,
    relearn_steps: int = 3,
    target_retention: float = 0.9,
) -> Scheduler:
    """Build an FSRS scheduler configured for in-session drilling.

    ``learning_steps`` controls graduation for brand-new cards;
    ``relearn_steps`` controls re-graduation for lapsed cards. The
    1-minute spacing between steps is irrelevant in-session because
    we always loop straight back to the word; only the *count*
    matters."""
    l_steps = tuple(timedelta(minutes=1) for _ in range(max(1, int(learning_steps))))
    r_steps = tuple(timedelta(minutes=1) for _ in range(max(1, int(relearn_steps))))
    return Scheduler(
        desired_retention=float(target_retention),
        learning_steps=l_steps,
        relearning_steps=r_steps,
        enable_fuzzing=False,
    )


# ---------------------------------------------------------------------------
# Card <-> dict helpers
# ---------------------------------------------------------------------------


def get_card(progress: ProgressFile, word: str) -> Card | None:
    entry = progress["words"].get(word)
    if entry is None:
        return None
    return Card.from_dict(entry["card"])


def get_reps(progress: ProgressFile, word: str) -> int:
    entry = progress["words"].get(word)
    if entry is None:
        return 0
    return int(entry.get("reps", 0))


def get_lapses(progress: ProgressFile, word: str) -> int:
    entry = progress["words"].get(word)
    if entry is None:
        return 0
    return int(entry.get("lapses", 0))


def is_leech(progress: ProgressFile, word: str, threshold: int) -> bool:
    """Derived flag — a word is a leech once its lapse count reaches
    ``threshold``. Threshold is read from config so we don't persist
    the boolean."""
    return get_lapses(progress, word) >= threshold


# ---------------------------------------------------------------------------
# Daily quotas
# ---------------------------------------------------------------------------


def _ensure_daily_for(
    progress: ProgressFile, when: datetime
) -> DailyState:
    """Reset the daily block if the calendar date has rolled over."""
    today = _today_iso(when)
    daily = progress.get("daily")
    if daily is None or daily.get("date") != today:
        progress["daily"] = _empty_daily(when)
    return progress["daily"]


def daily_budget(
    progress: ProgressFile,
    new_words_per_day: int,
    reviews_per_day: int,
    when: datetime | None = None,
) -> tuple[int, int]:
    """Return ``(new_remaining, review_remaining)`` for today,
    rolling over the daily counters if the date has changed."""
    when = datetime.now(timezone.utc) if when is None else when
    daily = _ensure_daily_for(progress, when)
    return (
        max(0, int(new_words_per_day) - int(daily["new_count"])),
        max(0, int(reviews_per_day) - int(daily["review_count"])),
    )


# ---------------------------------------------------------------------------
# Review recording
# ---------------------------------------------------------------------------


def record_review(
    progress: ProgressFile,
    scheduler: Scheduler,
    word: str,
    rating: Rating,
    word_wpm: float | None,
    now: datetime | None = None,
) -> Card:
    """Apply ``scheduler.review_card`` to ``word`` and update speed,
    lapse, and daily-quota tracking. Returns the resulting card so
    the caller can read its ``state`` to decide whether to re-drill
    in the current session."""
    when = datetime.now(timezone.utc) if now is None else now
    today = _today_iso(when)
    daily = _ensure_daily_for(progress, when)

    existing = progress["words"].get(word)
    card_was_none = existing is None
    card = Card.from_dict(existing["card"]) if existing else Card()
    prev_state = card.state if existing else None
    card, _log = scheduler.review_card(card, rating, review_datetime=when)

    # Daily counters: count the first commit of the day per word.
    last_seen = existing.get("last_seen_date") if existing else None
    if last_seen != today:
        if card_was_none:
            daily["new_count"] += 1
        else:
            daily["review_count"] += 1

    # Lapse tracking — only count Again on a card already in Review.
    prev_lapses = int(existing.get("lapses", 0)) if existing else 0
    new_lapses = prev_lapses + (
        1 if rating == Rating.Again and prev_state == State.Review else 0
    )

    # Reps + per-word EWMA + global speed sample.
    prev_reps = int(existing.get("reps", 0)) if existing else 0
    new_reps = prev_reps + 1
    prev_ewma: float | None = existing.get("wpm_ewma") if existing else None
    if word_wpm is not None and word_wpm > 0:
        progress["speed_samples"].append(float(word_wpm))
        if len(progress["speed_samples"]) > SPEED_SAMPLES_CAP:
            del progress["speed_samples"][:-SPEED_SAMPLES_CAP]
        if prev_ewma is None:
            new_ewma: float | None = float(word_wpm)
        else:
            new_ewma = (
                WPM_EWMA_ALPHA * float(word_wpm)
                + (1 - WPM_EWMA_ALPHA) * prev_ewma
            )
    else:
        new_ewma = prev_ewma

    progress["words"][word] = {
        "card": card.to_dict(),
        "reps": new_reps,
        "lapses": new_lapses,
        "wpm_ewma": new_ewma,
        "last_seen_date": today,
    }
    return card


# ---------------------------------------------------------------------------
# Speed threshold
# ---------------------------------------------------------------------------


def slow_threshold_wpm(
    progress: ProgressFile,
    fraction: float,
    min_samples: int = 20,
) -> float | None:
    """Return ``fraction * median(speed_samples)`` once we have at
    least ``min_samples``; otherwise ``None`` (treat all correct as
    'good')."""
    samples = progress.get("speed_samples", [])
    if len(samples) < min_samples or fraction <= 0:
        return None
    return float(statistics.median(samples)) * float(fraction)
