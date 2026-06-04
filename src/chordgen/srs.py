"""Persistence + speed-tracking layer for the chordgen train mode.

Wraps an FSRS ``Card`` per word using the official ``fsrs`` library
(open-spaced-repetition/py-fsrs), and maintains a global rolling
window of recent per-word WPM samples so the trainer can derive a
"slow" threshold relative to the user's own typing speed.

The FSRS state machine itself (Learning -> Review -> Relearning,
stability, difficulty, retrievability) is delegated entirely to the
library — we only persist its serialisable form and decide how it
maps onto our session UX.
"""

from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

from fsrs import Card, Rating, Scheduler

from chordgen.constants import CONFIG_DIR


PROGRESS_FILE: Path = CONFIG_DIR / "progress.json"

# Bumped from the legacy correct-streak schema. Anything older is
# wiped on first load — the user has not started using the trainer
# with persisted state, so no migration is needed.
PROGRESS_VERSION = 2

SPEED_SAMPLES_CAP = 200
WPM_EWMA_ALPHA = 0.3


class WordProgress(TypedDict):
    card: dict
    reps: int
    wpm_ewma: float | None


class ProgressFile(TypedDict):
    version: int
    speed_samples: list[float]
    words: dict[str, WordProgress]


def _empty() -> ProgressFile:
    return {"version": PROGRESS_VERSION, "speed_samples": [], "words": {}}


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
    return raw  # type: ignore[return-value]


def save_progress(progress: ProgressFile) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------


def make_scheduler(
    relearn_steps: int = 3,
    target_retention: float = 0.9,
) -> Scheduler:
    """Build an FSRS scheduler configured for in-session drilling.

    ``relearn_steps`` becomes a tuple of 1-minute steps for both
    ``learning_steps`` and ``relearning_steps``. The 1-minute spacing
    is irrelevant in-session because we always loop straight back to
    the word; only the *count* matters."""
    n = max(1, int(relearn_steps))
    steps = tuple(timedelta(minutes=1) for _ in range(n))
    return Scheduler(
        desired_retention=float(target_retention),
        learning_steps=steps,
        relearning_steps=steps,
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


def _store_card(
    progress: ProgressFile,
    word: str,
    card: Card,
    reps: int,
    wpm_ewma: float | None,
) -> None:
    progress["words"][word] = {
        "card": card.to_dict(),
        "reps": reps,
        "wpm_ewma": wpm_ewma,
    }


def get_reps(progress: ProgressFile, word: str) -> int:
    entry = progress["words"].get(word)
    if entry is None:
        return 0
    return int(entry.get("reps", 0))


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
    """Apply ``scheduler.review_card`` to ``word`` and update speed
    tracking. Returns the resulting card so the caller can read its
    ``state`` to decide whether to re-drill in the current session."""
    when = datetime.now(timezone.utc) if now is None else now

    existing = progress["words"].get(word)
    card = Card.from_dict(existing["card"]) if existing else Card()
    card, _log = scheduler.review_card(card, rating, review_datetime=when)

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

    _store_card(progress, word, card, new_reps, new_ewma)
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
