"""Drill mode TUI: typing-speed practice on graduated words.

Drill mode is a focused speed test on words that have already
graduated to the FSRS Review state in ``progress.json``. It is
read-only: the schedule, lapse counters, and daily quotas in
``progress.json`` are not touched. Use ``chordgen train`` for
SRS-backed learning; ``chordgen drill`` is for warming up your
fingers on the words you already know.

Words are picked by random shuffle from the graduated pool. Each
session ends after a fixed number of words (``drill.mode = count``)
or a fixed amount of time (``drill.mode = time``). When the session
finishes a summary screen reports WPM, accuracy, and any words you
fumbled along the way.
"""

from __future__ import annotations

import random
import time
from typing import Any

from fsrs import State
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static

from chordgen.srs import get_card, load_progress
from chordgen.keyboard_view import render_keyboard


class WordDisplay(Static):
    pass


class DrillApp(App):
    CSS_PATH = "train.css"

    BINDINGS = [
        Binding("tab", "restart", "Restart", priority=True),
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
        custom_words: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.chords_map = {c["word"]: c for c in chords if c["chord"]}
        self.config = config
        self.keyboard_layout = keyboard_layout
        self.keyboard_kind = keyboard_kind
        self._initial_theme = initial_theme
        self._on_theme_change = on_theme_change
        self.custom_words = custom_words
        if custom_words is not None:
            self.graduated_pool = self._filter_custom_words(custom_words)
        else:
            self.graduated_pool = self._collect_graduated(load_progress())

        # Per-keystroke / per-word state.
        self.letter_index = 0
        self.flashing = False
        self.current_word_had_error = False

        # Session stats.
        self.session_words_done = 0
        self.session_words_correct = 0
        self.session_failed_words: list[str] = []
        self.session_chars_typed = 0
        self.session_start_time: float | None = None
        self.session_finished = False
        self.session_wpm = 0.0

        self.words_to_practice = self._initial_word_list()
        self._timer_handle = None

    # ------------------------------------------------------------------
    # Pool / queue
    # ------------------------------------------------------------------

    def _collect_graduated(self, progress) -> list[str]:
        """Return the list of words whose FSRS card is in Review state
        and that still have a chord assigned in chords.csv."""
        out: list[str] = []
        for word in progress.get("words", {}):
            if word not in self.chords_map:
                continue
            card = get_card(progress, word)
            if card is not None and card.state == State.Review:
                out.append(word)
        return out

    def _filter_custom_words(self, words: list[str]) -> list[str]:
        """Return only the words from ``words`` that have a chord
        assigned in chords.csv. Words without a chord are silently
        dropped."""
        return [w for w in words if w in self.chords_map]

    def _initial_word_list(self) -> list[str]:
        if not self.graduated_pool:
            return []
        return self._draw_random(self.config.show_words)

    def _draw_random(self, n: int) -> list[str]:
        if not self.graduated_pool:
            return []
        n = min(n, len(self.graduated_pool))
        return random.sample(self.graduated_pool, n)

    def _draw_one(self) -> str | None:
        if not self.graduated_pool:
            return None
        return random.choice(self.graduated_pool)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield WordDisplay(id="words")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "chordgen drill"
        if self._initial_theme:
            try:
                self.theme = self._initial_theme
            except Exception:
                pass
        self.update_word_display()

    def watch_theme(self, theme: str) -> None:
        if self._on_theme_change is not None and theme:
            self._on_theme_change(theme)

    def action_quit(self) -> None:
        self.exit()

    def action_restart(self) -> None:
        self.reset_session()

    def reset_session(self) -> None:
        self.letter_index = 0
        self.flashing = False
        self.current_word_had_error = False
        self.session_words_done = 0
        self.session_words_correct = 0
        self.session_failed_words = []
        self.session_chars_typed = 0
        self.session_start_time = None
        self.session_finished = False
        self.session_wpm = 0.0
        # Re-load progress in case the user has just trained more
        # words since launching the drill.
        if self.custom_words is not None:
            self.graduated_pool = self._filter_custom_words(self.custom_words)
        else:
            self.graduated_pool = self._collect_graduated(load_progress())
        self.words_to_practice = self._initial_word_list()
        if self._timer_handle is not None:
            self._timer_handle.stop()
            self._timer_handle = None
        self.update_word_display()

    # ------------------------------------------------------------------
    # Keyboard handling
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        if self.flashing:
            return

        if self.session_finished:
            # Tab/Esc/Ctrl+C are handled by bindings; ignore other
            # trailing keystrokes so they don't do anything
            # surprising.
            event.stop()
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
                    self._start_timer_if_needed()
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

    def _start_timer_if_needed(self) -> None:
        # Tick the display once a second so the timer countdown (in
        # time mode) and the running WPM (in either mode) stay live
        # while the user is typing.
        if self._timer_handle is None:
            self._timer_handle = self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if self.session_finished:
            return
        if self.config.mode == "time" and self._time_remaining() <= 0:
            self.finish_session()
        else:
            self.update_word_display()

    def flash_red(self) -> None:
        self.current_word_had_error = True
        self.flashing = True
        self.update_word_display()
        self.set_timer(0.5, self.clear_flash)

    def clear_flash(self) -> None:
        self.flashing = False
        self.update_word_display()

    # ------------------------------------------------------------------
    # Word completion
    # ------------------------------------------------------------------

    def complete_current_word(self) -> None:
        word = self.words_to_practice[0]
        had_error = self.current_word_had_error

        self.session_words_done += 1
        if had_error:
            self.session_failed_words.append(word)
        else:
            self.session_words_correct += 1

        # Pop and top up.
        self.words_to_practice.pop(0)
        nxt = self._draw_one()
        if nxt is not None:
            self.words_to_practice.append(nxt)

        self.letter_index = 0
        self.current_word_had_error = False

        if self.config.mode == "count" and self.session_words_done >= self.config.count:
            self.finish_session()
        else:
            self.update_word_display()

    def finish_session(self) -> None:
        if self.session_finished:
            return
        elapsed = (
            time.time() - self.session_start_time
            if self.session_start_time
            else 0.0
        )
        if elapsed > 0:
            self.session_wpm = (self.session_chars_typed / 5.0) / (elapsed / 60.0)
        else:
            self.session_wpm = 0.0
        self.session_finished = True
        if self._timer_handle is not None:
            self._timer_handle.stop()
            self._timer_handle = None
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
            if self.custom_words is not None:
                widget.update(
                    Text.from_markup(
                        "[b yellow]No drillable words.[/]\n\n"
                        "None of the words you supplied have a chord "
                        "assigned in chords.csv."
                    )
                )
            else:
                widget.update(
                    Text.from_markup(
                        "[b yellow]No graduated words to drill yet.[/]\n\n"
                        "Run [b]chordgen train[/] until some words have "
                        "graduated to FSRS Review state, then come back."
                    )
                )
            return

        chord_strings = [
            self._chord_for_word(word, is_current=(i == 0))
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
                style = "yellow" if i == 0 and self.current_word_had_error else "cyan"
                chord_line.append(chord, style=style)
                if len(chord) < col_widths[i]:
                    chord_line.append(" " * (col_widths[i] - len(chord)))
            else:
                chord_line.append(" " * col_widths[i])

        progress_text = Text()
        if self.config.mode == "count":
            progress_text.append(
                f"{self.session_words_done}/{self.config.count}", style="cyan"
            )
        else:
            remaining = self._time_remaining()
            progress_text.append(f"{remaining:.0f}s", style="cyan")
        progress_text.append("  ")
        progress_text.append(f"{self._running_wpm():.0f} wpm", style="dim")

        # Pad each word-line on the left so the current word's column
        # sits at the centre of the rendered block. The pad width is
        # the total width of the trailing words (col widths + the
        # single space separators between them).
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

        # ASCII keyboard view. Drill only reveals chords after a
        # mistake, so highlights mirror that rule.
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

    def _time_remaining(self) -> float:
        if self.session_start_time is None:
            return float(self.config.time_seconds)
        spent = time.time() - self.session_start_time
        return max(0.0, float(self.config.time_seconds) - spent)

    def _running_wpm(self) -> float:
        if self.session_start_time is None:
            return 0.0
        elapsed = time.time() - self.session_start_time
        if elapsed <= 0:
            return 0.0
        return (self.session_chars_typed / 5.0) / (elapsed / 60.0)

    def _chord_for_word(self, word: str, is_current: bool) -> str:
        # Drill mode hides chords by default — these are graduated
        # words you already know — but reveals the chord for the
        # current word once you stumble on it, the same way train
        # mode does for mastered words.
        row = self.chords_map.get(word)
        if row is None:
            return ""
        if not (is_current and self.current_word_had_error):
            return ""
        return row.get("chord") or ""

    def _render_summary(self, widget: Static) -> None:
        summary = Text()
        summary.append("Drill complete!\n\n", style="bold green")
        summary.append("WPM: ")
        summary.append(f"{self.session_wpm:.1f}\n", style="bold")
        summary.append("Accuracy: ")
        if self.session_words_done > 0:
            acc = 100.0 * self.session_words_correct / self.session_words_done
        else:
            acc = 0.0
        summary.append(
            f"{self.session_words_correct}/{self.session_words_done} "
            f"({acc:.0f}%)\n",
            style="bold",
        )

        if self.session_failed_words:
            summary.append("\nFailed words:\n", style="bold")
            parts: list[str] = []
            seen: set[str] = set()
            for w in self.session_failed_words:
                if w in seen:
                    continue
                seen.add(w)
                row = self.chords_map.get(w)
                chord = (row or {}).get("chord") or ""
                parts.append(f"{w} ({chord})" if chord else w)
            summary.append(" ".join(parts) + "\n", style="red")

        summary.append(
            "\nPress Tab to drill again (Esc to quit).",
            style="dim",
        )
        widget.update(summary)
