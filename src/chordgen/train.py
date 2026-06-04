"""Train mode TUI: typing practice with FSRS-backed spaced repetition.

Long-term scheduling and the in-session learning queue are delegated
to the ``fsrs`` library. This module is responsible for the TUI, the
per-word speed measurement, and the word-selection policy that
chooses what to put on screen for the next session.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fsrs import Card, Rating, Scheduler, State
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static

from chordgen.srs import (
    ProgressFile,
    get_card,
    get_reps,
    load_progress,
    make_scheduler,
    record_review,
    save_progress,
    slow_threshold_wpm,
)


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested separately from the TUI)
# ---------------------------------------------------------------------------


def decide_rating(
    had_error: bool,
    word_wpm: float | None,
    slow_threshold: float | None,
) -> Rating:
    """Map a per-word outcome onto an FSRS rating.

    - Any error -> AGAIN.
    - No speed signal (first word, flashed, etc.) -> GOOD.
    - Below threshold -> HARD; otherwise GOOD.
    """
    if had_error:
        return Rating.Again
    if word_wpm is None or slow_threshold is None:
        return Rating.Good
    if word_wpm < slow_threshold:
        return Rating.Hard
    return Rating.Good


def reinsertion_offset(rating: Rating, queue_len: int) -> int:
    """Return the index where a non-graduated word should be re-inserted
    in the practice queue.

    The word is always appended to the tail of the visible queue so the
    user has time to react to the change rather than seeing the next
    word flip instantly. ``queue_len`` is the length of the queue
    *after* popping the just-completed word.

    The ``rating`` argument is kept for API stability and future tuning.
    """
    del rating  # currently unused; kept for stable signature
    return queue_len


def compute_word_wpm(elapsed_seconds: float, word_len: int) -> float | None:
    """Per-word WPM using the standard chars/5/minutes formula. The
    trailing space is included in the character count because that's
    what triggers the commit. Returns ``None`` for non-positive
    elapsed times."""
    if elapsed_seconds <= 0 or word_len <= 0:
        return None
    chars = word_len + 1  # trailing space
    return (chars / 5.0) / (elapsed_seconds / 60.0)


# ---------------------------------------------------------------------------
# Textual app
# ---------------------------------------------------------------------------


class WordDisplay(Static):
    pass


class TrainApp(App):
    CSS_PATH = "train.css"

    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", priority=True, show=False),
    ]

    words_to_practice: reactive[list[str]] = reactive(list)

    def __init__(self, chords: list[dict[str, Any]], config: Any) -> None:
        super().__init__()
        self.chords_map = {c["word"]: c for c in chords if c["chord"]}
        self.config = config
        self.progress: ProgressFile = load_progress()
        self.scheduler: Scheduler = make_scheduler(
            relearn_steps=config.relearn_steps,
            target_retention=config.target_retention,
        )

        # Per-keystroke / per-word state.
        self.letter_index = 0
        self.flashing = False
        self.current_word_had_error = False
        self.word_first_keystroke_time: float | None = None
        self.word_had_flash = False

        # Session counters.
        self.session_words_target = self.config.words_per_session
        self.session_words_done = 0  # graduations only
        self.session_words_correct = 0  # graduations without errors
        self.session_failed_words: list[str] = []
        self.session_speed_log: list[tuple[str, float]] = []  # (word, wpm)
        self.session_chars_typed = 0
        self.session_start_time: float | None = None
        self.first_word_committed = False
        self.session_finished = False
        self.session_wpm = 0.0

        # Words that have already graduated this session — exclude
        # them from top-up candidates so a freshly-learned word
        # doesn't get re-introduced as a new pick a few words later.
        self.graduated_this_session: set[str] = set()

        self.words_to_practice = self._initial_word_list()

    # ------------------------------------------------------------------
    # Word selection
    # ------------------------------------------------------------------

    def _initial_word_list(self) -> list[str]:
        return self._select_words(
            min(
                self.config.practice_list_size,
                self.session_words_target,
            )
        )

    def _select_words(self, n: int) -> list[str]:
        """Pick up to ``n`` words to add to the practice queue.

        Priority order:
        1. Overdue (FSRS due_date <= now), sorted by retrievability ascending.
        2. Slow (per-word EWMA below the slow threshold), sorted ascending.
        3. New (no FSRS state yet), sorted by frequency descending.
        """
        if n <= 0:
            return []

        on_screen = set(self.words_to_practice)
        excluded = on_screen | self.graduated_this_session
        now = datetime.now(timezone.utc)

        threshold = slow_threshold_wpm(
            self.progress,
            self.config.slow_wpm_fraction,
            self.config.slow_min_samples,
        )

        words_state = self.progress.get("words", {})

        # Bucket 1: overdue.
        overdue: list[tuple[float, str]] = []
        for word, entry in words_state.items():
            if word not in self.chords_map or word in excluded:
                continue
            card = Card.from_dict(entry["card"])
            if card.due is None or card.due > now:
                continue
            r = self.scheduler.get_card_retrievability(card, current_datetime=now)
            overdue.append((r, word))
        overdue.sort(key=lambda t: t[0])
        overdue_words = [w for _, w in overdue]

        # Bucket 2: slow words below threshold (excluding ones already
        # picked above).
        already = excluded | set(overdue_words)
        slow_words: list[str] = []
        if threshold is not None:
            slow: list[tuple[float, str]] = []
            for word, entry in words_state.items():
                if word not in self.chords_map or word in already:
                    continue
                ewma = entry.get("wpm_ewma")
                if ewma is not None and ewma < threshold:
                    slow.append((ewma, word))
            slow.sort(key=lambda t: t[0])
            slow_words = [w for _, w in slow]

        # Bucket 3: new words by frequency.
        already = already | set(slow_words)
        new_words: list[str] = []
        sorted_chords = sorted(
            self.chords_map.values(),
            key=lambda c: float(c.get("frequency") or 0),
            reverse=True,
        )
        for chord in sorted_chords:
            w = chord["word"]
            if w in already or w in words_state:
                continue
            new_words.append(w)

        return (overdue_words + slow_words + new_words)[:n]

    def _queue_state_counts(self) -> tuple[int, int, int]:
        """Anki-style breakdown of the on-screen queue:
        (new, learning, review). ``new`` = no FSRS state yet,
        ``learning`` = card in Learning/Relearning, ``review`` = card
        already graduated to Review state."""
        new_count = 0
        learning_count = 0
        review_count = 0
        for word in self.words_to_practice:
            card = get_card(self.progress, word)
            if card is None:
                new_count += 1
            elif card.state == State.Review:
                review_count += 1
            else:
                learning_count += 1
        return new_count, learning_count, review_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield WordDisplay(id="words")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "chordgen train"
        self.update_word_display()

    def action_quit(self) -> None:
        self.exit()

    def reset_session(self) -> None:
        self.letter_index = 0
        self.flashing = False
        self.current_word_had_error = False
        self.word_first_keystroke_time = None
        self.word_had_flash = False
        self.session_words_done = 0
        self.session_words_correct = 0
        self.session_failed_words = []
        self.session_speed_log = []
        self.session_chars_typed = 0
        self.session_start_time = None
        self.first_word_committed = False
        self.session_finished = False
        self.session_wpm = 0.0
        self.graduated_this_session = set()
        self.progress = load_progress()
        self.words_to_practice = self._initial_word_list()
        self.update_word_display()

    # ------------------------------------------------------------------
    # Keyboard handling
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        if self.flashing:
            return

        if self.session_finished:
            if event.key in ("escape", "ctrl+c"):
                return
            event.stop()
            self.reset_session()
            return

        if not self.words_to_practice:
            return

        if event.key == "backspace":
            if self.letter_index > 0:
                self.letter_index -= 1
                self.update_word_display()
            event.stop()
            return

        if event.key == "ctrl+w":
            if self.letter_index > 0:
                self.letter_index = 0
                self.update_word_display()
            event.stop()
            return

        key = event.character
        if key is None or len(key) != 1:
            return

        current = self.words_to_practice[0]

        if self.letter_index < len(current):
            expected = current[self.letter_index]
            if key == expected:
                now = time.time()
                if self.session_start_time is None:
                    self.session_start_time = now
                if self.word_first_keystroke_time is None:
                    self.word_first_keystroke_time = now
                self.letter_index += 1
                self.session_chars_typed += 1
                self.update_word_display()
            else:
                self.flash_red()
            event.stop()
        else:
            if key == " ":
                self.session_chars_typed += 1
                self.complete_current_word()
            else:
                self.flash_red()
            event.stop()

    def flash_red(self) -> None:
        self.current_word_had_error = True
        self.word_had_flash = True
        self.flashing = True
        self.update_word_display()
        self.set_timer(0.5, self.clear_flash)

    def clear_flash(self) -> None:
        self.flashing = False
        self.update_word_display()

    # ------------------------------------------------------------------
    # Word completion / FSRS update
    # ------------------------------------------------------------------

    def complete_current_word(self) -> None:
        word = self.words_to_practice[0]
        had_error = self.current_word_had_error
        commit_time = time.time()

        # Per-word WPM is excluded for the very first committed word
        # (the session clock starts on its first keystroke, so its
        # elapsed is biased low) and any word whose attempt was
        # interrupted by a 0.5s flash.
        word_wpm: float | None = None
        if (
            self.first_word_committed
            and not had_error
            and not self.word_had_flash
            and self.word_first_keystroke_time is not None
        ):
            word_wpm = compute_word_wpm(
                commit_time - self.word_first_keystroke_time, len(word)
            )

        threshold = slow_threshold_wpm(
            self.progress,
            self.config.slow_wpm_fraction,
            self.config.slow_min_samples,
        )
        rating = decide_rating(had_error, word_wpm, threshold)

        card = record_review(
            self.progress,
            self.scheduler,
            word,
            rating,
            word_wpm,
            now=datetime.now(timezone.utc),
        )

        # Pop the current word.
        self.words_to_practice.pop(0)

        # Decide whether this was a graduation or an in-session re-drill.
        graduated = card.state == State.Review

        if graduated:
            self.session_words_done += 1
            self.graduated_this_session.add(word)
            if had_error:
                self.session_failed_words.append(word)
            else:
                self.session_words_correct += 1
            if word_wpm is not None and rating != Rating.Again:
                self.session_speed_log.append((word, word_wpm))

            # Top up only if there are still graduations left in the
            # session beyond what's already on screen.
            remaining_in_session = (
                self.session_words_target
                - self.session_words_done
                - len(self.words_to_practice)
            )
            if remaining_in_session > 0:
                more = self._select_words(1)
                if more:
                    self.words_to_practice.append(more[0])
        else:
            # Word still in Learning/Relearning — re-insert at the tail
            # of the visible queue so the next word doesn't flip
            # underneath the user mid-keystroke.
            insert_at = reinsertion_offset(rating, len(self.words_to_practice))
            self.words_to_practice.insert(insert_at, word)
            if had_error and word not in self.session_failed_words:
                self.session_failed_words.append(word)

        self.letter_index = 0
        self.current_word_had_error = False
        self.word_first_keystroke_time = None
        self.word_had_flash = False
        self.first_word_committed = True

        if self.session_words_done >= self.session_words_target:
            self.finish_session()
        else:
            self.update_word_display()

    def finish_session(self) -> None:
        elapsed = (
            time.time() - self.session_start_time
            if self.session_start_time
            else 0.0
        )
        if elapsed > 0:
            self.session_wpm = (self.session_chars_typed / 5.0) / (elapsed / 60.0)
        else:
            self.session_wpm = 0.0
        save_progress(self.progress)
        self.session_finished = True
        self.update_word_display()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def update_word_display(self) -> None:
        widget = self.query_one(WordDisplay)

        if self.session_finished:
            self._render_summary(widget)
            return

        if not self.words_to_practice:
            widget.update(
                Text.from_markup(
                    "[b red]No words available to practice.[/]\n\n"
                    "Run [b]chordgen gen[/] first to assign chords to words."
                )
            )
            return

        chord_strings = [
            self.chord_for_word(word, is_current=(i == 0))
            for i, word in enumerate(self.words_to_practice)
        ]

        col_widths = [
            max(len(word), len(chord_strings[i]))
            for i, word in enumerate(self.words_to_practice)
        ]

        line = Text()
        cursor_col = 0

        for i, word in enumerate(self.words_to_practice):
            if i > 0:
                line.append(" ")
            col_start = len(line)

            if i == 0:
                if self.flashing:
                    line.append(word, style="bold red reverse")
                else:
                    typed = word[: self.letter_index]
                    rest = word[self.letter_index :]
                    if typed:
                        line.append(typed, style="green")
                    if rest:
                        line.append(rest, style="bold")

                if self.letter_index < len(word):
                    cursor_col = col_start + self.letter_index
                else:
                    cursor_col = col_start + col_widths[i]
            else:
                line.append(word, style="dim")

            if len(word) < col_widths[i]:
                line.append(" " * (col_widths[i] - len(word)))

        underline = (
            Text(" " * cursor_col + "‾" + " " * max(0, len(line) - cursor_col - 1))
            if not self.flashing
            else Text(" " * len(line))
        )

        chord_line = Text()
        for i, chord in enumerate(chord_strings):
            if i > 0:
                chord_line.append(" ")
            if chord:
                style = (
                    "yellow"
                    if i == 0 and self.current_word_had_error
                    else "cyan"
                )
                chord_line.append(chord, style=style)
                if len(chord) < col_widths[i]:
                    chord_line.append(" " * (col_widths[i] - len(chord)))
            else:
                chord_line.append(" " * col_widths[i])

        new_count, learning_count, review_count = self._queue_state_counts()
        progress_text = Text()
        progress_text.append("\n\n")
        progress_text.append(str(new_count), style="blue")
        progress_text.append("  ")
        progress_text.append(str(learning_count), style="red")
        progress_text.append("  ")
        progress_text.append(str(review_count), style="green")

        rendered = Text()
        rendered.append_text(line)
        rendered.append("\n")
        rendered.append_text(underline)
        rendered.append("\n")
        rendered.append_text(chord_line)
        rendered.append_text(progress_text)
        widget.update(rendered)

    def _render_summary(self, widget: Static) -> None:
        summary = Text()
        summary.append("Session complete!\n\n", style="bold green")
        summary.append("WPM: ")
        summary.append(f"{self.session_wpm:.1f}\n", style="bold")
        summary.append("Successful: ")
        summary.append(
            f"{self.session_words_correct}/{self.session_words_done}\n",
            style="bold",
        )

        if self.session_failed_words:
            summary.append("\nFailed words:\n", style="bold")
            parts: list[str] = []
            for w in self.session_failed_words:
                chord = ""
                row = self.chords_map.get(w)
                if row is not None:
                    chord = row.get("chord") or ""
                parts.append(f"{w} ({chord})" if chord else w)
            summary.append(" ".join(parts) + "\n", style="red")

        if self.session_speed_log:
            slowest = sorted(self.session_speed_log, key=lambda t: t[1])[:5]
            summary.append("\nSlowest words:\n", style="bold")
            slow_parts: list[str] = []
            for w, wpm in slowest:
                chord = ""
                row = self.chords_map.get(w)
                if row is not None:
                    chord = row.get("chord") or ""
                head = f"{w} ({chord})" if chord else w
                slow_parts.append(f"{head} — {wpm:.0f} wpm")
            summary.append(", ".join(slow_parts) + "\n", style="yellow")

        summary.append(
            "\nPress any key to start a new session (Esc to quit).",
            style="dim",
        )
        widget.update(summary)

    def chord_for_word(self, word: str, is_current: bool) -> str:
        chord_row = self.chords_map.get(word)
        if chord_row is None:
            return ""
        chord = chord_row.get("chord") or ""
        if not chord:
            return ""

        threshold = self.config.mastery_threshold
        card = get_card(self.progress, word)
        reps = get_reps(self.progress, word)
        # Mastered = at least ``threshold`` total reviews and currently
        # in the Review state (i.e. not actively in a learning step).
        mastered = (
            card is not None
            and getattr(card, "state", None) == State.Review
            and reps >= threshold
        )

        if mastered and not (is_current and self.current_word_had_error):
            return ""
        return chord
