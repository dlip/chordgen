"""Tests for the ASCII keyboard renderer used by train and drill."""

from chordgen.keyboard_view import (
    KEY_HIGHLIGHT_STYLE,
    render_keyboard,
)


QWERTY = [
    list("_qwertyuiop_"),
    list("_asdfghjkl;_"),
    list("_zxcvbnm,./_"),
    list("____"),
]


def test_render_keyboard_empty_layout_returns_empty_text():
    assert render_keyboard(None, set()).plain == ""
    assert render_keyboard([], set()).plain == ""


def test_render_keyboard_includes_all_letters_in_plain_text():
    out = render_keyboard(QWERTY, set()).plain
    for letter in "qwertyuiopasdfghjkl;zxcvbnm,./":
        assert letter in out, f"missing {letter!r}"


def test_render_keyboard_highlights_chord_keys():
    out = render_keyboard(QWERTY, {"a", "s"})
    spans = [(s.start, s.end, s.style) for s in out.spans]
    # Find the styled spans for the highlighted keys and confirm
    # they use the highlight style.
    highlighted_chars = []
    for start, end, style in spans:
        if style == KEY_HIGHLIGHT_STYLE:
            highlighted_chars.append(out.plain[start:end])
    assert "a" in highlighted_chars
    assert "s" in highlighted_chars


def test_render_keyboard_unknown_keys_are_ignored():
    # Highlighting a key that isn't on the layout shouldn't throw or
    # paint anything.
    out = render_keyboard(QWERTY, {"§"})
    for s in out.spans:
        assert s.style != KEY_HIGHLIGHT_STYLE
