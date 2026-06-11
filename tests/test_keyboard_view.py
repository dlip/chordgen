"""Tests for the ASCII keyboard renderer used by learn and drill."""

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


def test_render_keyboard_directional_includes_all_letters():
    from chordgen.keyboards.directional import LAYOUTS

    layout = [list(r) for r in LAYOUTS["charachorder"]]
    out = render_keyboard(layout, set(), kind="directional").plain
    for letter in "abcdefghijklmnopqrstuvwxyz":
        assert letter in out, f"missing {letter!r} in directional render"


def test_render_keyboard_directional_highlights_chord_keys():
    from chordgen.keyboards.directional import LAYOUTS

    layout = [list(r) for r in LAYOUTS["charachorder"]]
    out = render_keyboard(layout, {"r", "n"}, kind="directional")
    highlighted = [
        out.plain[s.start : s.end] for s in out.spans if s.style == KEY_HIGHLIGHT_STYLE
    ]
    assert "r" in highlighted
    assert "n" in highlighted


def test_render_keyboard_alt_slot_indicator_highlights_active_slot():
    out = render_keyboard(QWERTY, set(), alt_slot=2)
    plain = out.plain
    assert "alt1" in plain
    assert "alt2" in plain
    assert "alt3" in plain
    highlighted_chunks = [
        plain[s.start : s.end] for s in out.spans if s.style == KEY_HIGHLIGHT_STYLE
    ]
    assert "alt2" in highlighted_chunks
    assert "alt1" not in highlighted_chunks
    assert "alt3" not in highlighted_chunks


def test_render_keyboard_alt_slot_none_omits_indicator():
    out = render_keyboard(QWERTY, set())
    assert "alt1" not in out.plain
    assert "alt2" not in out.plain
    assert "alt3" not in out.plain


def test_render_keyboard_alt_slot_zero_shows_row_without_highlight():
    out = render_keyboard(QWERTY, set(), alt_slot=0)
    plain = out.plain
    assert "alt1" in plain
    assert "alt2" in plain
    assert "alt3" in plain
    highlighted_chunks = [
        plain[s.start : s.end] for s in out.spans if s.style == KEY_HIGHLIGHT_STYLE
    ]
    assert "alt1" not in highlighted_chunks
    assert "alt2" not in highlighted_chunks
    assert "alt3" not in highlighted_chunks
