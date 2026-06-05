"""ASCII keyboard renderer used by the train and drill TUIs.

Two layout families are supported:

- *standard* (qwerty / colemak / etc.): 3 letter rows + 1 thumb row.
- *directional* (CharaChorder / Svalboard / etc.): 8 finger clusters
  arranged as 3-row plus signs, plus two 3x3 thumb clusters per hand.

Highlighted keys are painted as held-down so the user sees the
shape of the chord they need to press.
"""

from __future__ import annotations

from rich.text import Text


KEY_DIM_STYLE = "grey39"
KEY_HIGHLIGHT_STYLE = "black on yellow"


def resolve_keyboard_layout(config) -> tuple[str, list[list[str]]] | None:
    """Pull the configured keyboard layout out of a Config object.

    Returns ``(kind, rows)`` where ``kind`` is ``"standard"`` or
    ``"directional"``, or ``None`` if no layout could be resolved.
    """
    keyboard = getattr(config, "gen", None)
    keyboard = getattr(keyboard, "keyboard", None) if keyboard else None
    if keyboard is None:
        return None

    if keyboard.type == "standard":
        from chordgen.keyboards.standard import LAYOUTS

        opts = keyboard.standard
        rows = opts.custom_layout if opts.layout == "custom" else LAYOUTS.get(opts.layout)
        if rows is None:
            return None
        return ("standard", [list(r) for r in rows])

    if keyboard.type == "directional":
        from chordgen.keyboards.directional import LAYOUTS

        opts = keyboard.directional
        rows = opts.custom_layout if opts.layout == "custom" else LAYOUTS.get(opts.layout)
        if rows is None:
            return None
        return ("directional", [list(r) for r in rows])

    return None


# Backwards-compatible alias retained for the train/drill imports
# that still phrase things in terms of "standard". Returns just the
# rows (or None) — used where the kind is irrelevant.
def resolve_standard_layout(config) -> list[list[str]] | None:
    resolved = resolve_keyboard_layout(config)
    if resolved is None:
        return None
    return resolved[1]


def resolve_layout_key(config) -> str:
    """Return a stable identifier for the configured keyboard layout
    (e.g. ``"standard:qwerty"`` or ``"directional:charachorder"``).

    For ``layout="custom"`` the user-supplied ``custom_layout_name``
    is used in place of ``"custom"`` so that personal-best
    leaderboards can be split per custom layout. Falls back to
    ``"unknown"`` if no layout can be resolved."""
    keyboard = getattr(config, "gen", None)
    keyboard = getattr(keyboard, "keyboard", None) if keyboard else None
    if keyboard is None:
        return "unknown"
    kind = getattr(keyboard, "type", None) or "unknown"
    opts = getattr(keyboard, kind, None)
    name = getattr(opts, "layout", None) if opts is not None else None
    if name == "custom":
        custom_name = getattr(opts, "custom_layout_name", None) or "custom"
        name = custom_name
    return f"{kind}:{name or 'unknown'}"


def _append_key(out: Text, key: str, highlights: set[str]) -> None:
    if key == "_":
        out.append(" ")
    elif key in highlights:
        out.append(key, style=KEY_HIGHLIGHT_STYLE)
    else:
        out.append(key, style=KEY_DIM_STYLE)


def _render_standard(layout: list[list[str]], highlights: set[str]) -> Text:
    out = Text()
    if len(layout) < 3:
        return out

    # Three letter rows. A 2-space gap is inserted between the left
    # and right halves of the keyboard (between cols 5 and 6) so the
    # split between hands is obvious. Rows are flush-left rather than
    # typewriter-staggered so the hand splits align vertically.
    for r in range(3):
        row = layout[r]
        for i, key in enumerate(row):
            if i > 0:
                out.append(" ")
                if i == 6:
                    out.append(" ")
            _append_key(out, key, highlights)
        out.append("\n")

    thumb = layout[3] if len(layout) > 3 else []
    if any(k != "_" for k in thumb):
        out.append(" " * 7)
        for i, key in enumerate(thumb):
            if i > 0:
                out.append(" ")
                if i == 2:
                    out.append(" ")
            _append_key(out, key, highlights)

    return out


def _render_directional(layout: list[list[str]], highlights: set[str]) -> Text:
    """Render a CharaChorder/Svalboard-style finger-cluster layout.

    The layout is 9 rows: 3 letter rows of 24 chars (8 finger clusters,
    each 3 chars wide for outer/center/inner) followed by 6 thumb rows
    of 6 chars (two 3-row thumb clusters per hand). ``_`` marks empty
    cells. Left and right halves are separated by a 2-space gap;
    the thumb clusters are centered under each hand.
    """
    out = Text()
    if len(layout) < 3:
        return out

    # Letter clusters: 8 fingers across, each 3-cols-wide. A single
    # space separates clusters within a hand; an extra 1-space gap is
    # inserted between the 4th and 5th clusters (the hands' boundary)
    # so the split totals 2 spaces.
    for r in range(3):
        row = layout[r]
        for finger_idx in range(0, len(row), 3):
            cluster_num = finger_idx // 3
            if cluster_num > 0:
                out.append(" ")
                if cluster_num == 4:
                    out.append(" ")
            for c in row[finger_idx : finger_idx + 3]:
                _append_key(out, c, highlights)
        out.append("\n")

    if len(layout) < 9:
        return out

    # Thumb clusters: rows 3..5 are the upper thumb cluster, rows
    # 6..8 are the lower thumb cluster. Each row is 6 chars (3 left
    # + 3 right). Layout is centered text per line, so we pad the
    # thumb row to the same width as the letter rows and place the
    # thumbs under each hand.
    letter_row_width = 24 + 7 + 1  # 8 clusters of 3 + 7 inter-cluster + 1 hand gap
    out.append("\n")
    left_indent = 12
    inter_thumb = 2
    for cluster_start in (3, 6):
        for r in range(cluster_start, cluster_start + 3):
            row = layout[r]
            out.append(" " * left_indent)
            for c in row[:3]:
                _append_key(out, c, highlights)
            out.append(" " * inter_thumb)
            for c in row[3:6]:
                _append_key(out, c, highlights)
            written = left_indent + 3 + inter_thumb + 3
            if written < letter_row_width:
                out.append(" " * (letter_row_width - written))
            out.append("\n")
        out.append("\n")

    if out.plain.endswith("\n\n"):
        out.right_crop(1)

    return out


def render_keyboard(
    layout: list[list[str]] | None,
    highlights: set[str],
    kind: str = "standard",
) -> Text:
    """Render ``layout`` as styled rich text.

    ``kind`` selects the geometry: ``"standard"`` (3 letter rows + 1
    thumb row) or ``"directional"`` (3 letter rows of finger clusters
    + two thumb clusters). Returns an empty ``Text`` when ``layout``
    is missing.
    """
    if not layout:
        return Text()
    highlights = {c for c in highlights if c}
    if kind == "directional":
        return _render_directional(layout, highlights)
    return _render_standard(layout, highlights)
