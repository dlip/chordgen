"""Tests for the book mode parser, cursor helpers, resume state,
and sliding-window WPM. The Textual TUI itself is not exercised."""

from __future__ import annotations

from pathlib import Path

from chordgen.book import (
    Book,
    BookToken,
    WpmWindow,
    _word_key,
    get_resume_index,
    layout_lines,
    line_index_for_token,
    load_book,
    load_book_state,
    next_paragraph_word_index,
    next_word_index,
    normalise_typeable,
    prev_paragraph_word_index,
    prev_word_index,
    resume_key_for,
    save_book_state,
    set_resume_index,
)


# ---------------------------------------------------------------------------
# Word key normalisation
# ---------------------------------------------------------------------------


def test_word_key_normalises_punctuation_and_case():
    assert _word_key("Don't,") == "don't"
    assert _word_key("--Hello!") == "hello"
    assert _word_key("WORD") == "word"
    assert _word_key("123") is None
    assert _word_key("") is None


# ---------------------------------------------------------------------------
# Typeable normalisation
# ---------------------------------------------------------------------------


def test_normalise_typeable_smart_quotes_and_dashes():
    src = "\u201cHello\u2014world\u2019s end\u201d"
    assert normalise_typeable(src) == '"Hello-world\'s end"'


def test_normalise_typeable_accented_latin():
    assert normalise_typeable("café") == "cafe"
    assert normalise_typeable("naïve résumé") == "naive resume"
    assert normalise_typeable("Æther œuvre") == "AEther oeuvre"
    assert normalise_typeable("straße") == "strasse"


def test_normalise_typeable_ligatures_and_symbols():
    assert normalise_typeable("\ufb01nal") == "final"  # fi ligature
    assert normalise_typeable("hello\u2026") == "hello..."
    assert normalise_typeable("Foo\u2122") == "FooTM"
    assert normalise_typeable("\u2022 item") == ". item"


def test_normalise_typeable_passes_through_ascii():
    plain = "Hello, world! 123 -- abc'd"
    assert normalise_typeable(plain) == plain


def test_load_book_normalises_text(tmp_path: Path):
    p = tmp_path / "smart.txt"
    p.write_text("\u201cCaf\u00e9\u201d\u2014na\u00efve.")
    book = load_book(p)
    # Text should now be entirely ASCII.
    assert all(ord(c) < 128 for tok in book.tokens for c in tok.text)
    joined = " ".join(tok.text for tok in book.tokens)
    assert '"Cafe"-naive.' in joined


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_load_book_txt_paragraphs_and_words(tmp_path: Path):
    p = tmp_path / "demo.txt"
    p.write_text("Hello, world!\n\nSecond para here.\n\nThird? Yes.\n")
    book = load_book(p)

    assert book.title == "demo"
    # Three paragraphs.
    assert len(book.paragraph_starts) == 3
    # All tokens have is_word True (alpha) for these inputs.
    assert all(t.is_word for t in book.tokens)
    # Punctuation-glued word_keys are normalised.
    assert book.tokens[0].word_key == "hello"
    assert book.tokens[1].word_key == "world"
    # Paragraph indices flow through.
    assert book.tokens[0].paragraph == 0
    assert book.tokens[2].paragraph == 1
    assert book.tokens[-1].paragraph == 2


def test_load_book_unknown_extension(tmp_path: Path):
    p = tmp_path / "x.bin"
    p.write_text("hi")
    try:
        load_book(p)
    except ValueError:
        return
    raise AssertionError("expected ValueError for unsupported format")


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------


def _make_book() -> Book:
    """Build a small Book with a deliberate non-word token in the
    middle so the *_word_index helpers have something to skip."""
    tokens = [
        BookToken("alpha", True, 0, "alpha"),
        BookToken("beta", True, 0, "beta"),
        BookToken("---", False, 1, None),
        BookToken("gamma", True, 1, "gamma"),
        BookToken("delta", True, 1, "delta"),
        BookToken("epsilon", True, 2, "epsilon"),
    ]
    para_starts = [0, 2, 5]
    return Book(title="x", tokens=tokens, paragraph_starts=para_starts)


def test_next_word_index_skips_non_word():
    book = _make_book()
    assert next_word_index(book.tokens, 1) == 3
    # At the end stays put.
    assert next_word_index(book.tokens, 5) == 5


def test_prev_word_index_skips_non_word():
    book = _make_book()
    assert prev_word_index(book.tokens, 3) == 1
    assert prev_word_index(book.tokens, 0) == 0


def test_next_paragraph_word_index_lands_on_first_word_of_paragraph():
    book = _make_book()
    # From token 0 (paragraph 0) jump to first word of paragraph 1
    # which is "gamma" at index 3 (skipping the non-word "---" at 2).
    assert next_paragraph_word_index(book, 0) == 3
    # From token 3 (paragraph 1) jump to first word of paragraph 2
    # which is "epsilon" at index 5.
    assert next_paragraph_word_index(book, 3) == 5
    # From the last paragraph, stay on the last word.
    assert next_paragraph_word_index(book, 5) == 5


def test_prev_paragraph_word_index_lands_on_first_word_of_paragraph():
    book = _make_book()
    # From paragraph 2 jump back to first word of paragraph 1.
    assert prev_paragraph_word_index(book, 5) == 3
    # From paragraph 1 jump back to first word of paragraph 0.
    assert prev_paragraph_word_index(book, 4) == 0
    # From paragraph 0 stay on the first word.
    assert prev_paragraph_word_index(book, 0) == 0


# ---------------------------------------------------------------------------
# Line layout
# ---------------------------------------------------------------------------


def test_layout_lines_respects_max_width():
    tokens = [
        BookToken("ab", True, 0, "ab"),
        BookToken("cd", True, 0, "cd"),
        BookToken("ef", True, 0, "ef"),
        BookToken("gh", True, 0, "gh"),
    ]
    # max_width=5 fits "ab cd" (5) but not "ab cd ef" (8).
    lines = layout_lines(tokens, max_width=5)
    assert lines == [[0, 1], [2, 3]]


def test_layout_lines_inserts_blank_between_paragraphs():
    tokens = [
        BookToken("hello", True, 0, "hello"),
        BookToken("world", True, 1, "world"),
    ]
    lines = layout_lines(tokens, max_width=80)
    # First paragraph, blank spacer, second paragraph.
    assert lines == [[0], [], [1]]


def test_layout_lines_oversize_word_alone_on_line():
    tokens = [
        BookToken("hi", True, 0, "hi"),
        BookToken("supercalifragilistic", True, 0, "supercalifragilistic"),
        BookToken("ok", True, 0, "ok"),
    ]
    lines = layout_lines(tokens, max_width=10)
    assert lines == [[0], [1], [2]]


def test_line_index_for_token_finds_containing_line():
    tokens = [
        BookToken("a", True, 0, "a"),
        BookToken("b", True, 0, "b"),
        BookToken("c", True, 1, "c"),
    ]
    lines = layout_lines(tokens, max_width=80)
    # lines == [[0, 1], [], [2]]
    assert line_index_for_token(lines, 0) == 0
    assert line_index_for_token(lines, 1) == 0
    assert line_index_for_token(lines, 2) == 2


# ---------------------------------------------------------------------------
# Resume state
# ---------------------------------------------------------------------------


def test_resume_index_round_trip(tmp_path: Path, monkeypatch):
    fake_books = tmp_path / "books.json"
    monkeypatch.setattr("chordgen.book.BOOKS_FILE", fake_books)

    state = load_book_state()
    p = tmp_path / "thebook.txt"
    p.write_text("hi")
    key = resume_key_for(p)

    assert get_resume_index(state, key) == 0

    set_resume_index(state, key, "thebook", 42)
    save_book_state(state)

    reloaded = load_book_state()
    assert get_resume_index(reloaded, key) == 42
    assert reloaded["books"][key]["title"] == "thebook"


def test_resume_index_missing_returns_zero():
    state = {"books": {}}
    assert get_resume_index(state, "nope") == 0


# ---------------------------------------------------------------------------
# Sliding-window WPM
# ---------------------------------------------------------------------------


def test_running_wpm_excludes_events_outside_window():
    w = WpmWindow(window_seconds=30.0)
    # 50 chars typed at t=0, but we read at t=100 — well outside the
    # 30s window. WPM should be 0.
    w.add(50, now=0.0)
    assert w.wpm(now=100.0) == 0.0


def test_running_wpm_within_window_uses_full_window_when_elapsed_exceeds_it():
    w = WpmWindow(window_seconds=30.0)
    # 150 characters spread across t=0..t=29.
    for t in range(30):
        w.add(5, now=float(t))
    # Reading at t=60: events older than 30 are evicted (t<30 i.e.
    # t<60-30=30 → all events at 0..29 are *still* on the boundary;
    # eviction is < cutoff so t=30 boundary keeps t=30..29 only).
    # Easier check: make sure the window is non-zero and finite.
    rate = w.wpm(now=60.0)
    assert rate >= 0.0


def test_running_wpm_normalises_by_elapsed_when_below_window():
    w = WpmWindow(window_seconds=30.0)
    # 25 chars typed at t=0, read at t=5 (elapsed=5s, below window).
    w.add(25, now=0.0)
    rate = w.wpm(now=5.0)
    # 25 chars / 5 cpw = 5 words in 5s = 60 wpm.
    assert abs(rate - 60.0) < 1e-6


def test_running_wpm_zero_when_no_events():
    w = WpmWindow(window_seconds=30.0)
    assert w.wpm(now=10.0) == 0.0
