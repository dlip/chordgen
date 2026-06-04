import time
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static
from textual.reactive import reactive

from chordgen.srs import load_progress, save_progress, update_progress


class WordDisplay(Static):
    pass


class TrainApp(App):
    CSS_PATH = "train.css"

    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", priority=True, show=False),
    ]

    words_to_practice: reactive[list[str]] = reactive(list)

    def __init__(self, chords, config):
        super().__init__()
        self.chords_map = {c["word"]: c for c in chords if c["chord"]}
        self.config = config
        self.progress = load_progress()
        self.letter_index = 0
        self.flashing = False
        self.current_word_had_error = False

        # Session state
        self.session_words_target = self.config.words_per_session
        self.session_words_done = 0
        self.session_chars_typed = 0
        self.session_start_time: float | None = None
        self.session_finished = False
        self.session_wpm = 0.0

        self.words_to_practice = self.get_words_to_practice(
            min(
                self.config.practice_list_size,
                self.session_words_target,
            )
        )

    def get_words_to_practice(self, n: int) -> list[str]:
        # Prioritize overdue words
        now = time.time()
        overdue_words = [
            word
            for word, data in self.progress.items()
            if data["next_practice_due"] <= now and word in self.chords_map
        ]
        overdue_words.sort(key=lambda w: self.progress[w]["next_practice_due"])

        # Add new words if needed
        new_words: list[str] = []
        already = set(overdue_words) | set(self.words_to_practice)
        if len(overdue_words) < n:
            # Sort all chords by frequency (descending)
            sorted_chords = sorted(
                self.chords_map.values(),
                key=lambda c: float(c.get("frequency") or 0),
                reverse=True,
            )
            for chord in sorted_chords:
                w = chord["word"]
                if w in already:
                    continue
                if w not in self.progress:
                    new_words.append(w)
                if len(overdue_words) + len(new_words) >= n:
                    break

        return (overdue_words + new_words)[:n]

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
        self.session_words_done = 0
        self.session_chars_typed = 0
        self.session_start_time = None
        self.session_finished = False
        self.session_wpm = 0.0
        self.letter_index = 0
        self.flashing = False
        self.current_word_had_error = False
        self.progress = load_progress()
        self.words_to_practice = self.get_words_to_practice(
            min(
                self.config.practice_list_size,
                self.session_words_target,
            )
        )
        self.update_word_display()

    def on_key(self, event) -> None:
        if self.flashing:
            return

        # Session over: any key restarts.
        if self.session_finished:
            if event.key in ("escape", "ctrl+c"):
                return
            event.stop()
            self.reset_session()
            return

        if not self.words_to_practice:
            return

        # Handle editing keys explicitly (these have no `character`).
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

        # Start the WPM clock on the first valid character key only.
        current = self.words_to_practice[0]

        if self.letter_index < len(current):
            expected = current[self.letter_index]
            if key == expected:
                if self.session_start_time is None:
                    self.session_start_time = time.time()
                self.letter_index += 1
                self.session_chars_typed += 1
                self.update_word_display()
            else:
                self.flash_red()
            event.stop()
        else:
            # Awaiting trailing space to commit the word
            if key == " ":
                self.session_chars_typed += 1
                self.complete_current_word()
            else:
                self.flash_red()
            event.stop()

    def flash_red(self) -> None:
        self.current_word_had_error = True
        self.flashing = True
        self.update_word_display()
        self.set_timer(0.5, self.clear_flash)

    def clear_flash(self) -> None:
        self.flashing = False
        self.update_word_display()

    def complete_current_word(self) -> None:
        word = self.words_to_practice[0]
        update_progress(self.progress, word, not self.current_word_had_error)

        self.words_to_practice.pop(0)
        # Only top up the queue if there are still words remaining in the
        # session beyond what's already on screen.
        remaining_in_session = (
            self.session_words_target
            - self.session_words_done
            - 1  # the word about to be committed
        )
        if remaining_in_session > len(self.words_to_practice):
            next_word = self.get_words_to_practice(1)
            if next_word:
                self.words_to_practice.append(next_word[0])

        self.letter_index = 0
        self.current_word_had_error = False
        self.session_words_done += 1

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
        # Standard WPM: chars / 5 / minutes.
        if elapsed > 0:
            self.session_wpm = (self.session_chars_typed / 5) / (elapsed / 60)
        else:
            self.session_wpm = 0.0

        save_progress(self.progress)
        self.session_finished = True
        self.update_word_display()

    def update_word_display(self) -> None:
        widget = self.query_one(WordDisplay)

        if self.session_finished:
            widget.update(
                Text.from_markup(
                    f"[b green]Session complete![/]\n\n"
                    f"WPM: [b]{self.session_wpm:.1f}[/]\n"
                    f"Words: [b]{self.session_words_done}[/]\n\n"
                    f"[dim]Press any key to start a new session "
                    f"(Esc to quit).[/]"
                )
            )
            return

        if not self.words_to_practice:
            widget.update(
                Text.from_markup(
                    "[b red]No words available to practice.[/]\n\n"
                    "Run [b]chordgen gen[/] first to assign chords to words."
                )
            )
            return

        # Compute the chord text shown under each word (may be empty
        # for mastered words). Column widths must accommodate both.
        chord_strings: list[str] = []
        for i, word in enumerate(self.words_to_practice):
            chord_strings.append(self.chord_for_word(word, is_current=(i == 0)))

        col_widths = [
            max(len(word), len(chord_strings[i]))
            for i, word in enumerate(self.words_to_practice)
        ]

        # Top line: words. Track where the current word starts and where
        # the cursor underscore should land.
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
                    # Awaiting trailing space — underscore lands on the
                    # separator after the current word column.
                    cursor_col = col_start + col_widths[i]
            else:
                line.append(word, style="dim")

            # Pad to the column width.
            if len(word) < col_widths[i]:
                line.append(" " * (col_widths[i] - len(word)))

        # Cursor underscore line.
        underline = Text(
            " " * cursor_col + "‾" + " " * max(0, len(line) - cursor_col - 1)
        ) if not self.flashing else Text(" " * len(line))

        # Chord line: each chord aligned under its word column.
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

        progress_text = Text(
            f"\n\n[{self.session_words_done}/{self.session_words_target}]",
            style="dim",
        )

        rendered = Text()
        rendered.append_text(line)
        rendered.append("\n")
        rendered.append_text(underline)
        rendered.append("\n")
        rendered.append_text(chord_line)
        rendered.append_text(progress_text)
        widget.update(rendered)

    def chord_for_word(self, word: str, is_current: bool) -> str:
        chord_row = self.chords_map.get(word)
        if chord_row is None:
            return ""
        chord = chord_row.get("chord") or ""
        if not chord:
            return ""

        threshold = self.config.mastery_threshold
        streak = self.progress.get(word, {}).get("correct_in_a_row", 0)
        mastered = streak >= threshold

        # Mastered words hide their chord, except the current word when
        # the user has made a mistake on this attempt.
        if mastered and not (is_current and self.current_word_had_error):
            return ""
        return chord

