"""Persistence + speed-tracking layer for the chordgen learn mode.

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
import logging
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from fsrs import Card, Rating, Scheduler, State

from chordgen.constants import CONFIG_DIR


PROGRESS_FILE: Path = CONFIG_DIR / "progress.json"

# v4 replaces macro-burst timing with separate throughput/recall samples.
# Older cards and quotas migrate in memory; loading never rewrites a file.
PROGRESS_VERSION = 4
SpeedMode = Literal["throughput", "recall"]

SPEED_SAMPLES_CAP = 200
WPM_EWMA_ALPHA = 0.3


class WordProgress(TypedDict):
    card: dict
    reps: int
    lapses: int
    wpm_ewma: float | None
    last_seen_date: str | None
    recall_wpm_ewma: NotRequired[float | None]
    recall_seconds: NotRequired[list[float]]
    mapping: NotRequired[str]


class DailyState(TypedDict):
    date: str
    new_count: int
    review_count: int


class ProgressFile(TypedDict):
    version: int
    speed_samples: list[float]
    recall_speed_samples: NotRequired[list[float]]
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
        "recall_speed_samples": [],
        "daily": _empty_daily(),
        "words": {},
    }


def load_progress() -> ProgressFile:
    """Read progress, migrating known versions without changing the file.

    Unknown versions and unreadable files are left untouched. Legacy speed
    samples are not comparable to activation-to-commit measurements.
    """
    if not PROGRESS_FILE.exists():
        return _empty()
    try:
        raw = json.loads(PROGRESS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return _empty()

    if not isinstance(raw, dict) or raw.get("version") not in (2, 3, PROGRESS_VERSION):
        return _empty()

    raw.setdefault("words", {})
    raw.setdefault("daily", _empty_daily())
    if raw["version"] != PROGRESS_VERSION:
        raw["speed_samples"] = []
        for entry in raw["words"].values():
            entry["wpm_ewma"] = None
            entry.setdefault("lapses", 0)
            entry.setdefault("last_seen_date", None)
        raw["version"] = PROGRESS_VERSION
    raw.setdefault("speed_samples", [])
    raw.setdefault("recall_speed_samples", [])
    return raw  # type: ignore[return-value]


def save_progress(progress: ProgressFile) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------


def make_scheduler(
    learning_steps: int = 5,
    relearn_steps: int = 2,
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


def mapping_matches(entry: WordProgress, fingerprint: str) -> bool:
    """Legacy cards have no identity; keep them until one-time binding."""
    return not entry.get("mapping") or entry["mapping"] == fingerprint


def reconcile_mappings(progress: ProgressFile, fingerprints: dict[str, str]) -> list[str]:
    """Bind legacy identities and retire changed cards, in memory only."""
    changed: list[str] = []
    legacy: list[str] = []
    for word, fingerprint in fingerprints.items():
        entry = progress["words"].get(word)
        if entry is None:
            continue
        if not mapping_matches(entry, fingerprint):
            del progress["words"][word]
            changed.append(word)
        elif not entry.get("mapping"):
            entry["mapping"] = fingerprint
            legacy.append(word)
    if legacy:
        logging.warning("Binding %d legacy cards to current mappings; original mappings are unknown.", len(legacy))
    if changed:
        logging.warning("Changed mappings need relearning: %s", ", ".join(changed))
        # Global samples have no word identity, so cannot remove just the
        # changed mappings' observations. Recalibrate thresholds safely.
        progress["speed_samples"] = []
        progress["recall_speed_samples"] = []
    return changed


def progress_entry_error(entry: object) -> str | None:
    """Validate a saved card for read-only reports without repairing it."""
    try:
        if not isinstance(entry, dict) or not isinstance(entry.get("card"), dict):
            raise ValueError("missing card object")
        if entry.get("mapping") is not None and not isinstance(entry["mapping"], str):
            raise ValueError("mapping identity must be a string")
        Card.from_dict(entry["card"])
        for key in ("reps", "lapses"):
            if key in entry and (type(entry[key]) is not int or entry[key] < 0):
                raise ValueError(f"{key} must be a nonnegative integer")
        for key in ("wpm_ewma", "recall_wpm_ewma"):
            if entry.get(key) is not None and not isinstance(entry[key], (int, float)):
                raise ValueError(f"{key} must be numeric or null")
        if "recall_seconds" in entry and not isinstance(entry["recall_seconds"], list):
            raise ValueError("recall_seconds must be a list")
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError) as exc:
        return str(exc)
    return None


def get_card(progress: ProgressFile, word: str, fingerprint: str | None = None) -> Card | None:
    entry = progress["words"].get(word)
    if entry is None or (fingerprint is not None and not mapping_matches(entry, fingerprint)):
        return None
    return Card.from_dict(entry["card"])


def learned_words(progress: ProgressFile, fingerprints: dict[str, str]) -> set[str]:
    return {
        word for word, fingerprint in fingerprints.items()
        if (card := get_card(progress, word, fingerprint)) is not None
        and card.state == State.Review
    }


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
    *,
    speed_mode: SpeedMode = "throughput",
    elapsed_seconds: float | None = None,
    fingerprint: str | None = None,
) -> Card:
    """Apply ``scheduler.review_card`` to ``word`` and update speed,
    lapse, and daily-quota tracking. Returns the resulting card so
    the caller can read its ``state`` to decide whether to re-drill
    in the current session."""
    if fingerprint is not None:
        reconcile_mappings(progress, {word: fingerprint})
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
    ewma_key = "recall_wpm_ewma" if speed_mode == "recall" else "wpm_ewma"
    samples_key = "recall_speed_samples" if speed_mode == "recall" else "speed_samples"
    prev_ewma: float | None = existing.get(ewma_key) if existing else None
    if word_wpm is not None and word_wpm > 0:
        samples = progress.setdefault(samples_key, [])
        samples.append(float(word_wpm))
        if len(samples) > SPEED_SAMPLES_CAP:
            del samples[:-SPEED_SAMPLES_CAP]
        if prev_ewma is None:
            new_ewma: float | None = float(word_wpm)
        else:
            new_ewma = (
                WPM_EWMA_ALPHA * float(word_wpm)
                + (1 - WPM_EWMA_ALPHA) * prev_ewma
            )
    else:
        new_ewma = prev_ewma

    entry = dict(existing or {})
    entry.update({
        "card": card.to_dict(),
        "reps": new_reps,
        "lapses": new_lapses,
        "last_seen_date": today,
        ewma_key: new_ewma,
    })
    entry.setdefault("wpm_ewma", None)
    if fingerprint is not None:
        entry["mapping"] = fingerprint
    if (speed_mode == "recall" and word_wpm is not None and word_wpm > 0
            and elapsed_seconds is not None and elapsed_seconds > 0):
        observations = entry.setdefault("recall_seconds", [])
        observations.append(float(elapsed_seconds))
        del observations[:-SPEED_SAMPLES_CAP]
    progress["words"][word] = entry
    return card


# ---------------------------------------------------------------------------
# Speed threshold
# ---------------------------------------------------------------------------


def slow_threshold_wpm(
    progress: ProgressFile,
    fraction: float,
    min_samples: int = 20,
    *,
    speed_mode: SpeedMode = "throughput",
) -> float | None:
    """Return ``fraction * median(speed_samples)`` once we have at
    least ``min_samples``; otherwise ``None`` (treat all correct as
    'good')."""
    key = "recall_speed_samples" if speed_mode == "recall" else "speed_samples"
    samples = progress.get(key, [])
    if len(samples) < min_samples or fraction <= 0:
        return None
    return float(statistics.median(samples)) * float(fraction)
