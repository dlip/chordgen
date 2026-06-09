"""Book mode: type your way through a .txt or .epub.

Unlike learn and drill, book mode is open-ended. The user types
through a long-form text file at their own pace, position is
auto-resumed across sessions, and the only running stat is a
sliding-window WPM. Words for which the user has already
graduated a chord (FSRS Review state) are highlighted so the user
can practise applying their learned chords in real prose; the
chord itself is hidden until the user mistypes the word, mirroring
drill mode's reveal-on-stumble UX.

The module bundles four concerns:

- ``BookToken`` / ``Book`` / :func:`load_book` — the parser
  (``.txt``, ``.md``, ``.epub``).
- :func:`load_book_state` / :func:`get_resume_index` /
  :func:`set_resume_index` — per-book cursor persistence in
  ``~/.config/chordgen/books.json``.
- :class:`WpmWindow` — sliding-window WPM helper.
- :class:`BookApp` — the Textual TUI.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fsrs import State
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static

from chordgen.constants import CONFIG_DIR
from chordgen.keyboard_view import render_keyboard
from chordgen.srs import get_card, load_progress


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


_WORD_KEY_RE = re.compile(r"[^a-z']+")

# Fallback line count used before the #book-text widget has been
# laid out (i.e. before ``_visible_lines()`` can read the real
# height from the widget).
_DEFAULT_VISIBLE_LINES = 7


# Map of non-typeable characters → ASCII replacements. Applied to all
# book text so users typing on a plain QWERTY-style layout don't get
# stuck on smart quotes, em dashes, accented vowels, ligatures, etc.
# Anything not in this table is preserved as-is — non-alpha tokens
# still render, they just won't match ``.isalpha()`` for chord lookup.
_TYPEABLE_REPLACEMENTS: dict[str, str] = {
    # Whitespace
    "\u00a0": " ",  # non-breaking space
    "\u2009": " ",  # thin space
    "\u202f": " ",  # narrow no-break space
    "\u200b": "",   # zero-width space
    "\u200c": "",   # zero-width non-joiner
    "\u200d": "",   # zero-width joiner
    "\ufeff": "",   # BOM / zero-width no-break space
    # Dashes / hyphens
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
    # Quotes
    "\u2018": "'",  # left single
    "\u2019": "'",  # right single / apostrophe
    "\u201a": "'",  # single low-9
    "\u201b": "'",  # single high-reversed-9
    "\u201c": '"',  # left double
    "\u201d": '"',  # right double
    "\u201e": '"',  # double low-9
    "\u201f": '"',  # double high-reversed-9
    "\u2032": "'",  # prime
    "\u2033": '"',  # double prime
    "\u00ab": '"',  # «
    "\u00bb": '"',  # »
    # Ellipsis / bullets
    "\u2026": "...",
    "\u2022": ".",
    "\u2023": ".",
    "\u2043": "-",
    "\u25e6": ".",
    # Symbols
    "\u2122": "TM",
    "\u00a9": "(c)",
    "\u00ae": "(R)",
    "\u00b0": " degrees",
    "\u00d7": "x",
    "\u00f7": "/",
    # Latin ligatures
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
    # Lowercase accented Latin
    "à": "a", "á": "a", "â": "a", "ã": "a", "ä": "a", "å": "a", "ā": "a",
    "ă": "a", "ą": "a",
    "æ": "ae",
    "ç": "c", "ć": "c", "č": "c", "ĉ": "c", "ċ": "c",
    "ď": "d", "đ": "d", "ð": "d",
    "è": "e", "é": "e", "ê": "e", "ë": "e", "ē": "e", "ĕ": "e",
    "ė": "e", "ę": "e", "ě": "e",
    "ĝ": "g", "ğ": "g", "ġ": "g", "ģ": "g",
    "ĥ": "h", "ħ": "h",
    "ì": "i", "í": "i", "î": "i", "ï": "i", "ĩ": "i", "ī": "i",
    "ĭ": "i", "į": "i", "ı": "i",
    "ĵ": "j",
    "ķ": "k",
    "ĺ": "l", "ļ": "l", "ľ": "l", "ŀ": "l", "ł": "l",
    "ñ": "n", "ń": "n", "ņ": "n", "ň": "n", "ŋ": "n",
    "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ö": "o", "ø": "o",
    "ō": "o", "ŏ": "o", "ő": "o",
    "œ": "oe",
    "ŕ": "r", "ŗ": "r", "ř": "r",
    "ś": "s", "ŝ": "s", "ş": "s", "š": "s", "ș": "s",
    "ß": "ss",
    "ţ": "t", "ť": "t", "ŧ": "t", "ț": "t",
    "ù": "u", "ú": "u", "û": "u", "ü": "u", "ũ": "u", "ū": "u",
    "ŭ": "u", "ů": "u", "ű": "u", "ų": "u",
    "ŵ": "w",
    "ý": "y", "ÿ": "y", "ŷ": "y",
    "ź": "z", "ż": "z", "ž": "z",
    "þ": "th",
    # Uppercase counterparts (kept simple — preserve case when easy)
    "À": "A", "Á": "A", "Â": "A", "Ã": "A", "Ä": "A", "Å": "A", "Ā": "A",
    "Ă": "A", "Ą": "A",
    "Æ": "AE",
    "Ç": "C", "Ć": "C", "Č": "C", "Ĉ": "C", "Ċ": "C",
    "Ď": "D", "Đ": "D", "Ð": "D",
    "È": "E", "É": "E", "Ê": "E", "Ë": "E", "Ē": "E", "Ĕ": "E",
    "Ė": "E", "Ę": "E", "Ě": "E",
    "Ĝ": "G", "Ğ": "G", "Ġ": "G", "Ģ": "G",
    "Ĥ": "H", "Ħ": "H",
    "Ì": "I", "Í": "I", "Î": "I", "Ï": "I", "Ĩ": "I", "Ī": "I",
    "Ĭ": "I", "Į": "I", "İ": "I",
    "Ĵ": "J",
    "Ķ": "K",
    "Ĺ": "L", "Ļ": "L", "Ľ": "L", "Ŀ": "L", "Ł": "L",
    "Ñ": "N", "Ń": "N", "Ņ": "N", "Ň": "N", "Ŋ": "N",
    "Ò": "O", "Ó": "O", "Ô": "O", "Õ": "O", "Ö": "O", "Ø": "O",
    "Ō": "O", "Ŏ": "O", "Ő": "O",
    "Œ": "OE",
    "Ŕ": "R", "Ŗ": "R", "Ř": "R",
    "Ś": "S", "Ŝ": "S", "Ş": "S", "Š": "S", "Ș": "S",
    "Ţ": "T", "Ť": "T", "Ŧ": "T", "Ț": "T",
    "Ù": "U", "Ú": "U", "Û": "U", "Ü": "U", "Ũ": "U", "Ū": "U",
    "Ŭ": "U", "Ů": "U", "Ű": "U", "Ų": "U",
    "Ŵ": "W",
    "Ý": "Y", "Ÿ": "Y", "Ŷ": "Y",
    "Ź": "Z", "Ż": "Z", "Ž": "Z",
    "Þ": "Th",
}

_TYPEABLE_TABLE = str.maketrans(
    {k: v for k, v in _TYPEABLE_REPLACEMENTS.items() if len(k) == 1}
)


def normalise_typeable(text: str) -> str:
    """Replace non-typeable characters (smart quotes, em dashes,
    accented Latin, ligatures, etc.) with plain ASCII equivalents so
    a user on a basic QWERTY layout can actually type the text."""
    return text.translate(_TYPEABLE_TABLE)


def _word_key(text: str) -> str | None:
    """Lowercase + strip outer punctuation, returning the chord-lookup
    key for ``text`` or ``None`` if there is no alpha core."""
    lowered = text.lower()
    # Strip leading/trailing non-alpha (keep apostrophes).
    stripped = _WORD_KEY_RE.sub(" ", lowered).strip()
    # Stripping above also collapses interior punctuation; reduce
    # spaces and rebuild a single token.
    parts = [p for p in stripped.split(" ") if p]
    if not parts:
        return None
    candidate = parts[0] if len(parts) == 1 else "".join(parts)
    # Trim leading/trailing apostrophes — they're rarely useful and
    # rarely present in chord lists.
    candidate = candidate.strip("'")
    return candidate or None


@dataclass
class BookToken:
    text: str
    is_word: bool
    paragraph: int
    word_key: str | None = None


@dataclass
class Book:
    title: str
    tokens: list[BookToken] = field(default_factory=list)
    paragraph_starts: list[int] = field(default_factory=list)


def _tokenise_paragraphs(paragraphs: list[str]) -> tuple[list[BookToken], list[int]]:
    """Convert a list of paragraph strings into a flat token list and
    the index of the first token of each paragraph."""
    tokens: list[BookToken] = []
    para_starts: list[int] = []
    for p_idx, para in enumerate(paragraphs):
        para_starts.append(len(tokens))
        for raw in para.split():
            is_word = any(c.isalpha() for c in raw)
            tokens.append(
                BookToken(
                    text=raw,
                    is_word=is_word,
                    paragraph=p_idx,
                    word_key=_word_key(raw) if is_word else None,
                )
            )
    return tokens, para_starts


def _split_text_into_paragraphs(text: str) -> list[str]:
    # Normalise newlines, collapse runs of >=2 newlines into paragraph
    # breaks, replace lone newlines with spaces.
    text = normalise_typeable(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_paragraphs = re.split(r"\n\s*\n+", text)
    cleaned: list[str] = []
    for p in raw_paragraphs:
        flat = re.sub(r"\s+", " ", p).strip()
        if flat:
            cleaned.append(flat)
    return cleaned


def _load_text_file(path: Path) -> Book:
    text = path.read_text(encoding="utf-8", errors="replace")
    paragraphs = _split_text_into_paragraphs(text)
    tokens, para_starts = _tokenise_paragraphs(paragraphs)
    return Book(title=path.stem, tokens=tokens, paragraph_starts=para_starts)


def _load_epub_file(path: Path) -> Book:
    # Imported lazily so users without ebooklib installed can still
    # use the rest of chordgen.
    from bs4 import BeautifulSoup
    from ebooklib import epub, ITEM_DOCUMENT

    book_obj = epub.read_epub(str(path))

    # Title from metadata, fall back to file stem.
    title = path.stem
    title_meta = book_obj.get_metadata("DC", "title")
    if title_meta:
        title = title_meta[0][0] or title

    paragraphs: list[str] = []
    for item in book_obj.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text("\n")
        paragraphs.extend(_split_text_into_paragraphs(text))

    tokens, para_starts = _tokenise_paragraphs(paragraphs)
    return Book(title=title, tokens=tokens, paragraph_starts=para_starts)


def load_book(path: Path) -> Book:
    """Load ``path`` as a Book. ``.txt`` / ``.md`` are read as plain
    text; ``.epub`` files are parsed with ``ebooklib``."""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ""}:
        return _load_text_file(path)
    if suffix == ".epub":
        return _load_epub_file(path)
    raise ValueError(f"Unsupported book format: {suffix or '<no extension>'}")


# ---------------------------------------------------------------------------
# Resume state
# ---------------------------------------------------------------------------


BOOKS_FILE: Path = CONFIG_DIR / "books.json"


def _empty_book_state() -> dict[str, Any]:
    return {"books": {}}


def load_book_state() -> dict[str, Any]:
    if not BOOKS_FILE.exists():
        return _empty_book_state()
    try:
        raw = json.loads(BOOKS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return _empty_book_state()
    if not isinstance(raw, dict):
        return _empty_book_state()
    raw.setdefault("books", {})
    return raw


def save_book_state(state: dict[str, Any]) -> None:
    BOOKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    BOOKS_FILE.write_text(json.dumps(state, indent=2))


def resume_key_for(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(data).hexdigest()


def get_resume_index(state: dict[str, Any], key: str) -> int:
    entry = state.get("books", {}).get(key)
    if not entry:
        return 0
    try:
        return int(entry.get("token_index", 0))
    except (TypeError, ValueError):
        return 0


def set_resume_index(
    state: dict[str, Any],
    key: str,
    title: str,
    idx: int,
    when: datetime | None = None,
) -> None:
    when = datetime.now(timezone.utc) if when is None else when
    books = state.setdefault("books", {})
    books[key] = {
        "title": title,
        "token_index": int(idx),
        "updated_at": when.isoformat(),
    }


# ---------------------------------------------------------------------------
# Sliding-window WPM
# ---------------------------------------------------------------------------


class WpmWindow:
    """Tracks a sliding window of correct character events and reports
    the running WPM over the last ``window_seconds`` seconds.

    Until at least ``window_seconds`` have elapsed since the first
    event, the rate is normalised by elapsed time so the displayed
    WPM doesn't read absurdly low at the start of a session."""

    def __init__(self, window_seconds: float) -> None:
        self.window_seconds = float(window_seconds)
        self._events: deque[tuple[float, int]] = deque()
        self._first_event_time: float | None = None

    def add(self, chars: int, now: float | None = None) -> None:
        if chars <= 0:
            return
        ts = time.time() if now is None else now
        if self._first_event_time is None:
            self._first_event_time = ts
        self._events.append((ts, chars))
        self._evict(ts)

    def _evict(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def wpm(self, now: float | None = None) -> float:
        ts = time.time() if now is None else now
        self._evict(ts)
        if not self._events or self._first_event_time is None:
            return 0.0
        total_chars = sum(c for _, c in self._events)
        elapsed = ts - self._first_event_time
        denom = min(elapsed, self.window_seconds)
        if denom <= 0:
            return 0.0
        return (total_chars / 5.0) / (denom / 60.0)


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------


def first_word_index(tokens: list[BookToken], start: int = 0) -> int | None:
    for i in range(max(0, start), len(tokens)):
        if tokens[i].is_word:
            return i
    return None


def last_word_index(tokens: list[BookToken]) -> int | None:
    for i in range(len(tokens) - 1, -1, -1):
        if tokens[i].is_word:
            return i
    return None


def next_word_index(tokens: list[BookToken], cursor: int) -> int:
    nxt = first_word_index(tokens, cursor + 1)
    return nxt if nxt is not None else cursor


def prev_word_index(tokens: list[BookToken], cursor: int) -> int:
    for i in range(cursor - 1, -1, -1):
        if tokens[i].is_word:
            return i
    return cursor


def next_paragraph_word_index(book: Book, cursor: int) -> int:
    if not book.tokens:
        return cursor
    cur_para = book.tokens[cursor].paragraph if 0 <= cursor < len(book.tokens) else 0
    target = cur_para + 1
    while target < len(book.paragraph_starts):
        nxt = first_word_index(book.tokens, book.paragraph_starts[target])
        if nxt is not None:
            return nxt
        target += 1
    last = last_word_index(book.tokens)
    return last if last is not None else cursor


def prev_paragraph_word_index(book: Book, cursor: int) -> int:
    if not book.tokens:
        return cursor
    cur_para = book.tokens[cursor].paragraph if 0 <= cursor < len(book.tokens) else 0
    target = cur_para - 1
    while target >= 0:
        nxt = first_word_index(book.tokens, book.paragraph_starts[target])
        if nxt is not None:
            return nxt
        target -= 1
    first = first_word_index(book.tokens, 0)
    return first if first is not None else cursor


# ---------------------------------------------------------------------------
# Line layout
# ---------------------------------------------------------------------------


def layout_lines(tokens: list[BookToken], max_width: int) -> list[list[int]]:
    """Lay tokens out into lines no wider than ``max_width`` columns.

    Each line is represented as a list of token indices. Paragraph
    boundaries (paragraph index changing between consecutive tokens)
    force a line break and insert a single blank line between
    paragraphs. Words longer than ``max_width`` are placed alone on
    their line — we never split inside a word.
    """
    if max_width <= 0:
        max_width = 80
    lines: list[list[int]] = []
    current: list[int] = []
    current_width = 0
    last_paragraph: int | None = None

    for idx, tok in enumerate(tokens):
        if last_paragraph is not None and tok.paragraph != last_paragraph:
            # Paragraph break: flush current line and add a blank
            # spacer line so paragraphs read separately.
            if current:
                lines.append(current)
                current = []
                current_width = 0
            lines.append([])
        last_paragraph = tok.paragraph

        token_len = len(tok.text)
        # Width if appended: existing width + (1 for separating space if non-empty) + token_len
        added_width = token_len if not current else current_width + 1 + token_len
        if current and added_width > max_width:
            lines.append(current)
            current = [idx]
            current_width = token_len
        else:
            current.append(idx)
            current_width = added_width

    if current:
        lines.append(current)

    return lines


def line_index_for_token(lines: list[list[int]], token_idx: int) -> int:
    """Return the line index containing ``token_idx``, or 0 if not
    found (e.g. empty layout)."""
    for li, line in enumerate(lines):
        if line and line[0] <= token_idx <= line[-1]:
            return li
    return 0


# ---------------------------------------------------------------------------
# Textual app
# ---------------------------------------------------------------------------


class BookStatus(Static):
    pass


class BookText(Static):
    pass


class BookChord(Static):
    pass


class BookKeyboard(Static):
    pass


class BookApp(App):
    CSS = """
    #book-status {
        height: 1;
        padding: 0 2;
    }
    #book-text {
        height: 1fr;
        content-align: center middle;
        text-align: center;
        padding: 1 2;
    }
    #book-chord {
        height: 1;
        content-align: center middle;
        text-align: center;
    }
    #book-keyboard {
        dock: bottom;
        height: auto;
        content-align: center middle;
        text-align: center;
        padding: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", priority=True, show=False),
        Binding("left", "skip_word_back", "Word ←", show=False),
        Binding("right", "skip_word_fwd", "Word →", show=False),
        Binding("up", "skip_line_back", "Line ↑", show=False),
        Binding("down", "skip_line_fwd", "Line ↓", show=False),
        Binding("pageup", "skip_half_back", "Half-page ↑", show=False),
        Binding("pagedown", "skip_half_fwd", "Half-page ↓", show=False),
    ]

    def __init__(
        self,
        chords: list[dict[str, Any]],
        config: Any,
        path: Path,
        restart: bool = False,
        keyboard_layout: list[list[str]] | None = None,
        keyboard_kind: str = "standard",
        initial_theme: str | None = None,
        on_theme_change: Any = None,
    ) -> None:
        super().__init__()
        self.chords_map = {c["word"]: c for c in chords if c["chord"]}
        self.config = config
        self.path = path
        self.book = load_book(path)
        self.keyboard_layout = keyboard_layout
        self.keyboard_kind = keyboard_kind
        self._initial_theme = initial_theme
        self._on_theme_change = on_theme_change

        self.learned_words = self._collect_learned_words()
        self.resume_key = resume_key_for(path)
        self.book_state = load_book_state()
        if restart:
            set_resume_index(
                self.book_state, self.resume_key, self.book.title, 0
            )
            save_book_state(self.book_state)

        first = first_word_index(self.book.tokens, 0) or 0
        saved = get_resume_index(self.book_state, self.resume_key)
        self.cursor = self._clamp_to_word(saved if saved else first)

        self.letter_index = 0
        self.current_word_had_error = False
        self.flashing = False
        self.at_end_of_book = False

        self.wpm = WpmWindow(window_seconds=float(self.config.wpm_window_seconds))
        self._tick_handle = None

        # Pre-compute the line layout once. The line geometry only
        # depends on book + max_width; it never changes at runtime.
        self.lines = layout_lines(self.book.tokens, self.config.max_width)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _collect_learned_words(self) -> set[str]:
        progress = load_progress()
        learned: set[str] = set()
        for word in progress.get("words", {}):
            if word not in self.chords_map:
                continue
            card = get_card(progress, word)
            if card is not None and card.state == State.Review:
                learned.add(word)
        return learned

    def _clamp_to_word(self, idx: int) -> int:
        if not self.book.tokens:
            return 0
        idx = max(0, min(idx, len(self.book.tokens) - 1))
        if self.book.tokens[idx].is_word:
            return idx
        nxt = first_word_index(self.book.tokens, idx)
        if nxt is not None:
            return nxt
        return last_word_index(self.book.tokens) or 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield BookStatus(id="book-status")
        yield BookText(id="book-text")
        yield BookChord(id="book-chord")
        yield BookKeyboard(id="book-keyboard")
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"chordgen book — {self.book.title}"
        if self._initial_theme:
            try:
                self.theme = self._initial_theme
            except Exception:
                pass
        self._tick_handle = self.set_interval(1.0, self._tick)
        self.refresh_view()
        self.call_after_refresh(self.refresh_view)

    def watch_theme(self, theme: str) -> None:
        if self._on_theme_change is not None and theme:
            self._on_theme_change(theme)

    def _tick(self) -> None:
        # Re-render so the running WPM stays live even when the user
        # pauses typing.
        self.refresh_view()

    def on_resize(self, event) -> None:
        # The number of visible lines depends on the widget's height,
        # so a resize should re-flow the rendered window.
        self.refresh_view()

    def action_quit(self) -> None:
        self._persist_cursor()
        if self._tick_handle is not None:
            self._tick_handle.stop()
            self._tick_handle = None
        self.exit()

    # ------------------------------------------------------------------
    # Skip actions
    # ------------------------------------------------------------------

    def _move_cursor_to(self, idx: int) -> None:
        self.cursor = self._clamp_to_word(idx)
        self.letter_index = 0
        self.current_word_had_error = False
        self.at_end_of_book = False
        self._persist_cursor()
        self.refresh_view()

    def action_skip_word_fwd(self) -> None:
        self._move_cursor_to(next_word_index(self.book.tokens, self.cursor))

    def action_skip_word_back(self) -> None:
        self._move_cursor_to(prev_word_index(self.book.tokens, self.cursor))

    def action_skip_para_fwd(self) -> None:
        self._move_cursor_to(next_paragraph_word_index(self.book, self.cursor))

    def action_skip_para_back(self) -> None:
        self._move_cursor_to(prev_paragraph_word_index(self.book, self.cursor))

    def action_skip_half_fwd(self) -> None:
        self._jump_lines(self._half_page_lines())

    def action_skip_half_back(self) -> None:
        self._jump_lines(-self._half_page_lines())

    def action_skip_line_fwd(self) -> None:
        self._jump_lines(1)

    def action_skip_line_back(self) -> None:
        self._jump_lines(-1)

    def _visible_lines(self) -> int:
        """Number of text lines that fit in the #book-text widget
        right now. Falls back to ``_DEFAULT_VISIBLE_LINES`` before the
        widget is laid out."""
        try:
            widget = self.query_one("#book-text", BookText)
        except Exception:
            return _DEFAULT_VISIBLE_LINES
        # ``size`` is the outer box; padding is ``1 2`` (top/bottom = 1
        # each), so subtract 2 for the inner content height.
        h = widget.size.height - 2
        if h <= 0:
            return _DEFAULT_VISIBLE_LINES
        return h

    def _half_page_lines(self) -> int:
        return max(1, self._visible_lines() // 2)

    def _jump_lines(self, delta: int) -> None:
        if not self.lines:
            return
        cur_line = line_index_for_token(self.lines, self.cursor)
        target_line = max(0, min(len(self.lines) - 1, cur_line + delta))
        # Walk outwards if the target line is a paragraph spacer
        # (empty list of tokens) so the cursor always lands on a
        # real word.
        step = 1 if delta >= 0 else -1
        while 0 <= target_line < len(self.lines) and not self.lines[target_line]:
            target_line += step
        if target_line < 0 or target_line >= len(self.lines):
            return
        first_token_in_line = self.lines[target_line][0]
        # If that first token isn't a word (rare — leading punct.),
        # skip to the next word in the book from there.
        nxt_word = first_word_index(self.book.tokens, first_token_in_line)
        if nxt_word is None:
            return
        self._move_cursor_to(nxt_word)

    # ------------------------------------------------------------------
    # Typing
    # ------------------------------------------------------------------

    def on_key(self, event) -> None:
        if not self.book.tokens:
            return

        cur = self.book.tokens[self.cursor]
        if not cur.is_word:
            return

        if event.key == "backspace":
            if self.letter_index > 0:
                self.letter_index -= 1
                self.refresh_view()
            event.stop()
            return

        if event.key == "ctrl+w":
            if self.letter_index > 0:
                self.letter_index = 0
                self.refresh_view()
            event.stop()
            return

        key = event.character
        if key is None or len(key) != 1:
            return

        word = cur.text

        if self.letter_index < len(word):
            expected = word[self.letter_index]
            if key == expected:
                self.letter_index += 1
                self.wpm.add(1)
                self.refresh_view()
            else:
                self._flash_red()
            event.stop()
        else:
            if key == " ":
                self.wpm.add(1)
                self._complete_current_word()
            else:
                self._flash_red()
            event.stop()

    def _flash_red(self) -> None:
        self.current_word_had_error = True
        self.flashing = True
        self.refresh_view()
        self.set_timer(0.4, self._clear_flash)

    def _clear_flash(self) -> None:
        self.flashing = False
        self.refresh_view()

    def _complete_current_word(self) -> None:
        nxt = next_word_index(self.book.tokens, self.cursor)
        if nxt == self.cursor:
            # End of book — leave cursor on the last word and surface
            # an "End of book" status so the user knows there's
            # nothing more to type.
            self.at_end_of_book = True
            self.refresh_view()
            return
        self.cursor = nxt
        self.letter_index = 0
        self.current_word_had_error = False
        self._persist_cursor()
        self.refresh_view()

    def _persist_cursor(self) -> None:
        set_resume_index(
            self.book_state,
            self.resume_key,
            self.book.title,
            self.cursor,
        )
        save_book_state(self.book_state)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def refresh_view(self) -> None:
        self._render_status()
        self._render_text()
        self._render_chord()
        self._render_keyboard()

    def _render_status(self) -> None:
        widget = self.query_one("#book-status", BookStatus)
        total_paragraphs = max(1, len(self.book.paragraph_starts))
        cur_para = (
            self.book.tokens[self.cursor].paragraph + 1
            if self.book.tokens
            else 0
        )
        line = Text()
        line.append(self.book.title, style="bold")
        line.append("   ")
        line.append(f"¶ {cur_para}/{total_paragraphs}", style="dim")
        line.append("   ")
        line.append(f"{self.wpm.wpm():.0f} wpm (last {int(self.wpm.window_seconds)}s)", style="cyan")
        if self.at_end_of_book:
            line.append("   ")
            line.append("📖 End of book", style="bold green")
        widget.update(line)

    def _render_text(self) -> None:
        widget = self.query_one("#book-text", BookText)
        if not self.book.tokens or not self.lines:
            widget.update(Text("(empty book)", style="yellow"))
            return

        tokens = self.book.tokens
        cursor_line = line_index_for_token(self.lines, self.cursor)
        show = max(1, self._visible_lines())
        # The cursor's line is centred. With an even ``show`` we
        # bias one extra line below the cursor.
        above = (show - 1) // 2
        start_line = max(0, cursor_line - above)
        end_line = min(len(self.lines), start_line + show)
        # Re-anchor when near the end of the book.
        start_line = max(0, end_line - show)

        max_width = max(1, int(self.config.max_width))
        out = Text()
        for li in range(start_line, end_line):
            if li > start_line:
                out.append("\n")
            line = self.lines[li]
            line_text = Text()
            line_width = 0
            if line:
                for j, tok_idx in enumerate(line):
                    if j > 0:
                        line_text.append(" ")
                        line_width += 1
                    self._append_token(line_text, tokens[tok_idx], tok_idx)
                    line_width += len(tokens[tok_idx].text)
            # Pad each line to ``max_width`` with trailing spaces so
            # the lines form a uniform-width block — combined with
            # ``text-align: center`` this centres the block while
            # leaving the lines themselves left-aligned within it.
            if line_width < max_width:
                line_text.append(" " * (max_width - line_width))
            out.append(line_text)
        widget.update(out)

    def _append_token(self, out: Text, tok: BookToken, idx: int) -> None:
        text = tok.text
        if not tok.is_word:
            out.append(text)
            return

        if idx < self.cursor:
            out.append(text, style="green")
            return

        if idx == self.cursor:
            if self.flashing:
                out.append(text, style="bold red reverse")
                return
            typed = text[: self.letter_index]
            rest = text[self.letter_index :]
            if typed:
                out.append(typed, style="green")
            if rest:
                if tok.word_key in self.learned_words:
                    out.append(rest, style="bold yellow")
                else:
                    out.append(rest, style="bold")
            return

        # Upcoming token.
        if tok.word_key and tok.word_key in self.learned_words:
            out.append(text, style="yellow")
        else:
            out.append(text)

    def _current_word_chord(self) -> str:
        if not self.book.tokens:
            return ""
        tok = self.book.tokens[self.cursor]
        if not tok.is_word or not tok.word_key:
            return ""
        if tok.word_key not in self.learned_words:
            return ""
        row = self.chords_map.get(tok.word_key)
        if row is None:
            return ""
        return row.get("chord") or ""

    def _render_chord(self) -> None:
        widget = self.query_one("#book-chord", BookChord)
        if not self.current_word_had_error:
            widget.update(Text(""))
            return
        chord = self._current_word_chord()
        if not chord:
            widget.update(Text(""))
            return
        line = Text()
        line.append("chord: ", style="dim")
        line.append("+".join(chord), style="bold yellow")
        widget.update(line)

    def _render_keyboard(self) -> None:
        widget = self.query_one("#book-keyboard", BookKeyboard)
        if self.keyboard_layout is None:
            widget.update(Text(""))
            return
        highlights: set[str] = set()
        if self.current_word_had_error:
            chord = self._current_word_chord()
            highlights = set(chord)
        kb = render_keyboard(self.keyboard_layout, highlights, kind=self.keyboard_kind)
        widget.update(kb)
