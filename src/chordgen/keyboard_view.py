"""ASCII keyboard renderer used by the train and drill TUIs.

Given a standard 4-row layout (the same shape used by
``StandardKeyboard``) this draws a small staggered ASCII keyboard
with keys in ``highlights`` painted as held-down. The renderer is
deliberately scoped to standard layouts; directional layouts (e.g.
CharaChorder) fall back to no keyboard view since their geometry
doesn't map cleanly onto an ASCII grid.
"""

from __future__ import annotations

from rich.text import Text


KEY_DIM_STYLE = "grey39"
KEY_HIGHLIGHT_STYLE = "black on yellow"


def resolve_standard_layout(config) -> list[list[str]] | None:
    """Pull a list-of-rows-of-chars layout out of a Config object.

    Returns None if the configured keyboard isn't a standard layout
    (no ASCII keyboard view in that case)."""
    keyboard = getattr(config, "gen", None)
    keyboard = getattr(keyboard, "keyboard", None) if keyboard else None
    if keyboard is None or keyboard.type != "standard":
        return None

    from chordgen.keyboards.standard import LAYOUTS

    opts = keyboard.standard
    if opts.layout == "custom":
        rows = opts.custom_layout
    else:
        rows = LAYOUTS.get(opts.layout)
    if rows is None:
        return None
    return [list(r) for r in rows]


def render_keyboard(
    layout: list[list[str]] | None,
    highlights: set[str],
) -> Text:
    """Render ``layout`` as styled rich text. Empty Text if layout is
    None or not the expected 4-row shape."""
    out = Text()
    if not layout or len(layout) < 3:
        return out

    highlights = {c for c in highlights if c}

    # Three letter rows. The middle and bottom rows are nudged one
    # column right of the top row to mimic a typewriter stagger,
    # without piling up extra space on the bottom row.
    row_offsets = (0, 1, 1)
    for r in range(3):
        row = layout[r]
        out.append(" " * row_offsets[r])
        for i, key in enumerate(row):
            if i > 0:
                out.append(" ")
            if key == "_":
                out.append(" ")
            elif key in highlights:
                out.append(key, style=KEY_HIGHLIGHT_STYLE)
            else:
                out.append(key, style=KEY_DIM_STYLE)
        out.append("\n")

    # Thumb row (only render if it has any non-padding keys).
    thumb = layout[3] if len(layout) > 3 else []
    if any(k != "_" for k in thumb):
        # Tuck under the home row roughly. The standard QWERTY-style
        # thumb row has 4 keys; offset so it sits near the centre.
        out.append(" " * 7)
        for i, key in enumerate(thumb):
            if i > 0:
                out.append(" ")
            if key == "_":
                out.append(" ")
            elif key in highlights:
                out.append(key, style=KEY_HIGHLIGHT_STYLE)
            else:
                out.append(key, style=KEY_DIM_STYLE)

    return out
