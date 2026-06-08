"""Learn mode TUI: typing practice with FSRS-backed spaced repetition.

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
    daily_budget,
    get_card,
    get_reps,
    load_progress,
    make_scheduler,
    record_review,
    save_progress,
    slow_threshold_wpm,
)
from chordgen.keyboard_view import render_keyboard


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


class LearnApp(App):
    CSS_PATH = "learn.css"

    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", priority=True, show=False),
    ]

    words_to_practice: reactive[list[str]] = reactive(list)

    def __init__(
        self,
        chords: list[dict[str, Any]],
        config: Any,
        keyboard_layout: list[list[str]] | None = None,
        keyboard_kind: str = "standard",
        initial_theme: str | None = None,
        on_theme_change: Any = None,
    ) -> None:
        super().__init__()
        self.chords_map = {c["word"]: c for c in chords if c["chord"]}
        self.config = config
        self.keyboard_layout = keyboard_layout
        self.keyboard_kind = keyboard_kind
        self._initial_theme = initial_theme
        self._on_theme_change = on_theme_change
        self.progress: ProgressFile = load_progress()
        self.scheduler: Scheduler = make_scheduler(
            learning_steps=config.learning_steps,
            relearn_steps=config.relearn_steps,
            target_retention=config.target_retention,
        )

        # Per-keystroke / per-word state.
        self.letter_index = 0
        self.flashing = False
        self.current_word_had_error = False
        self.word_first_keystroke_time: float | None = None
        self.word_had_flash = False

        # Session counters (session WPM is no longer surfaced — the
        # learn mode is about long-term FSRS retention, not speed
        # tests; for speed practice see ``chordgen drill``).
        self.session_chars_typed = 0
        self.session_start_time: float | None = None
        self.first_word_committed = False

        # Words that have already graduated this session — exclude
        # them from top-up candidates so a freshly-learned word
        # doesn't get re-introduced as a new pick a few words later.
        self.graduated_this_session: set[str] = set()

        self.words_to_practice = self._initial_word_list()

    # ------------------------------------------------------------------
    # Word selection
    # ------------------------------------------------------------------

    def _initial_word_list(self) -> list[str]:
        return self._select_words(self.config.show_words)

    def _daily_budget(self) -> tuple[int, int]:
        """Daily budget *minus* what is already on the screen, so the
        selector doesn't double-count words it just placed.

        Words on screen with no FSRS state count against the new
        budget; on-screen graduated words count against the review
        budget. In-flight Learning/Relearning words don't count
        because they were already booked when they were first
        introduced this session."""
        new_left, review_left = daily_budget(
            self.progress,
            self.config.new_words_per_day,
            self.config.reviews_per_day,
        )
        for w in self.words_to_practice:
            card = get_card(self.progress, w)
            if card is None:
                new_left -= 1
            elif card.state == State.Review:
                review_left -= 1
        return max(0, new_left), max(0, review_left)

    def _select_words(self, n: int) -> list[str]:
        """Pick up to ``n`` words to add to the practice queue, honouring
        the day's ``new_words_per_day`` and ``reviews_per_day`` budgets.

        Priority order:
        1. Overdue (FSRS due_date <= now), sorted by retrievability ascending.
           Capped by remaining review budget.
        2. Slow (per-word EWMA below the slow threshold), sorted ascending.
           Capped by remaining review budget.
        3. New (no FSRS state yet), sorted by frequency descending.
           Capped by remaining new budget.
        """
        if n <= 0:
            return []

        new_left, review_left = self._daily_budget()
        if new_left <= 0 and review_left <= 0:
            return []

        excluded = set(self.words_to_practice) | self.graduated_this_session
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()

        threshold = slow_threshold_wpm(
            self.progress,
            self.config.slow_wpm_fraction,
            self.config.slow_min_samples,
        )

        words_state = self.progress.get("words", {})

        # Bucket 1: overdue (review). Words already reviewed today
        # are buried until tomorrow even if FSRS schedules them
        # sooner — otherwise a freshly-graduated card can pop right
        # back onto the queue minutes later.
        # Due-check uses calendar date (like Anki), not wall-clock
        # time, so a card due later today still appears.
        overdue: list[tuple[float, str]] = []
        for word, entry in words_state.items():
            if word not in self.chords_map or word in excluded:
                continue
            if entry.get("last_seen_date") == today:
                continue
            card = Card.from_dict(entry["card"])
            if card.due is None:
                continue
            if card.due.date() > now.date():
                continue
            r = self.scheduler.get_card_retrievability(card, current_datetime=now)
            overdue.append((r, word))
        overdue.sort(key=lambda t: t[0])
        overdue_words = [w for _, w in overdue][:review_left]
        review_left -= len(overdue_words)

        # Bucket 2: slow words (also review). Same bury-today rule
        # applies.
        already = excluded | set(overdue_words)
        slow_words: list[str] = []
        if threshold is not None and review_left > 0:
            slow: list[tuple[float, str]] = []
            for word, entry in words_state.items():
                if word not in self.chords_map or word in already:
                    continue
                if entry.get("last_seen_date") == today:
                    continue
                ewma = entry.get("wpm_ewma")
                if ewma is not None and ewma < threshold:
                    slow.append((ewma, word))
            slow.sort(key=lambda t: t[0])
            slow_words = [w for _, w in slow][:review_left]

        # Bucket 3: new words by frequency (capped by new budget).
        already = already | set(slow_words)
        new_words: list[str] = []
        if new_left > 0:
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
                if len(new_words) >= new_left:
                    break

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
        self.title = "chordgen learn"
        if self._initial_theme:
            try:
                self.theme = self._initial_theme
            except Exception:
                # Theme name unknown to this Textual version; fall
                # back to the default rather than crashing the TUI.
                pass
        self.update_word_display()

    def watch_theme(self, theme: str) -> None:
        # Persist the user's selection from the command palette so it
        # carries across runs.
        if self._on_theme_change is not None and theme:
            self._on_theme_change(theme)

    def action_quit(self) -> None:
        self.exit()

    def reset_session(self) -> None:
        self.letter_index = 0
        self.flashing = False
        self.current_word_had_error = False
        self.word_first_keystroke_time = None
        self.word_had_flash = False
        self.session_chars_typed = 0
        self.session_start_time = None
        self.first_word_committed = False
        self.graduated_this_session = set()
        self.progress = load_progress()
        self.words_to_practice = self._initial_word_list()
        self.update_word_display()

    # ------------------------------------------------------------------
    # Keyboard handling
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
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
        # Persist after every commit so daily counters and FSRS state
        # survive an unexpected quit. Anki behaves the same way.
        save_progress(self.progress)

        # Pop the current word.
        self.words_to_practice.pop(0)

        # Decide whether this was a graduation or an in-session re-drill.
        graduated = card.state == State.Review

        if graduated:
            self.graduated_this_session.add(word)

            # Top up from the day's remaining budget. ``_select_words``
            # already enforces the per-day caps.
            more = self._select_words(1)
            if more:
                self.words_to_practice.append(more[0])
        else:
            # Word still in Learning/Relearning — re-insert at the tail
            # of the visible queue so the next word doesn't flip
            # underneath the user mid-keystroke.
            insert_at = reinsertion_offset(rating, len(self.words_to_practice))
            self.words_to_practice.insert(insert_at, word)

        self.letter_index = 0
        self.current_word_had_error = False
        self.word_first_keystroke_time = None
        self.word_had_flash = False
        self.first_word_committed = True

        self.update_word_display()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def update_word_display(self) -> None:
        widget = self.query_one(WordDisplay)

        if not self.words_to_practice:
            new_left, review_left = daily_budget(
                self.progress,
                self.config.new_words_per_day,
                self.config.reviews_per_day,
            )
            if new_left == 0 and review_left == 0:
                widget.update(
                    Text.from_markup(
                        "[b green]No more words due today![/]\n\n"
                        "You've hit both your new-word and review "
                        "quotas. Come back tomorrow."
                    )
                )
            elif new_left == 0:
                widget.update(
                    Text.from_markup(
                        "[b green]No more words due today![/]\n\n"
                        "You've introduced all the new words allowed "
                        "today and have nothing overdue to review. "
                        "Come back tomorrow."
                    )
                )
            else:
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
        for i, word in enumerate(self.words_to_practice):
            if i > 0:
                line.append(" ")

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
            else:
                line.append(word, style="dim")

            if len(word) < col_widths[i]:
                line.append(" " * (col_widths[i] - len(word)))

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
        progress_text.append(str(new_count), style="blue")
        progress_text.append("  ")
        progress_text.append(str(learning_count), style="red")
        progress_text.append("  ")
        progress_text.append(str(review_count), style="green")

        # Pad each word-line on the left so the current word's column
        # sits at the centre of the rendered block. The pad width is
        # the total width of the trailing words (including their
        # separator spaces); see the geometry in the drill renderer
        # for the derivation.
        trailing_width = sum(col_widths[1:]) + max(0, len(self.words_to_practice) - 1)
        pad = " " * trailing_width

        padded_line = Text()
        padded_line.append(pad)
        padded_line.append_text(line)

        padded_chord_line = Text()
        padded_chord_line.append(pad)
        padded_chord_line.append_text(chord_line)

        rendered = Text()
        rendered.append_text(progress_text)
        rendered.append("\n\n")
        rendered.append_text(padded_line)
        rendered.append("\n")
        rendered.append_text(padded_chord_line)

        # ASCII keyboard view. Highlight the chord keys only when the
        # current word's chord is actually being shown above (i.e.
        # chord_strings[0] is non-empty).
        if self.keyboard_layout is not None:
            highlights: set[str] = set()
            current_chord = chord_strings[0] if chord_strings else ""
            if current_chord:
                highlights = set(current_chord)
            kb = render_keyboard(
                self.keyboard_layout, highlights, kind=self.keyboard_kind
            )
            if kb.plain:
                rendered.append("\n\n")
                rendered.append_text(kb)

        widget.update(rendered)

    def chord_for_word(self, word: str, is_current: bool) -> str:
        chord_row = self.chords_map.get(word)
        if chord_row is None:
            return ""
        chord = chord_row.get("chord") or ""
        if not chord:
            return ""

        mastery_threshold = self.config.mastery_threshold
        show_chord_threshold = self.config.show_chord_steps
        card = get_card(self.progress, word)
        reps = get_reps(self.progress, word)

        # During initial learning (brand-new cards), the chord is
        # shown for the first ``show_chord_steps`` consecutive
        # correct reps and hidden thereafter. An error resets the
        # FSRS step counter to zero, which brings the chord back.
        if card is not None and card.state == State.Learning:
            if (card.step or 0) >= show_chord_threshold and not (
                is_current and self.current_word_had_error
            ):
                return ""

        # Mastered = at least ``mastery_threshold`` total reviews and
        # currently in the Review state (i.e. not actively in a
        # learning / relearning step).
        mastered = (
            card is not None
            and getattr(card, "state", None) == State.Review
            and reps >= mastery_threshold
        )

        if mastered and not (is_current and self.current_word_had_error):
            return ""
        return chord
