"""Interactive ``chordgen add`` flow.

Walks the user through adding new words to ``chords.csv`` one at a
time:

1. Skip words that already exist (as ``word`` or as a non-empty
   alt slot of another row).
2. Score the word against the configured keyboard, filter out
   collision-prone or too-short chords, and present a numbered
   menu of the top collision-free options.
3. Auto-detect the category (closed-class lookup, then pattern.en
   fallback) and let the user override.
4. Validate a custom-typed chord through the same scorer pipeline.
5. Run the alt generator on the accepted row, drop alt slots that
   collide with an existing word, and append the row to
   ``chords.csv`` (rewritten atomically after every accepted word
   so a Ctrl+C mid-batch keeps the words already accepted).

The new row is written with ``chord`` set and ``frequency`` empty
so the existing ``_is_reserved`` rule in
:mod:`chordgen.assigner` treats it as user-pinned in future
``chordgen gen`` runs.
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path
from typing import Callable

from chordgen.alt_generator import AltGenerator
from chordgen.chord import Chord, Option, load_file
from chordgen.config import GenOptions
from chordgen.scorer import Scorer
from chordgen.vocab.subtlex import closed_class_category


# Number of collision-free chord options to show per word. Small
# enough to scan, large enough to give choice.
_MAX_SHOW = 10

# ANSI colours used by the live chord prompt.
_ANSI_RESET = "\x1b[0m"
_ANSI_RED = "\x1b[31m"
_ANSI_GREEN = "\x1b[32m"
_ANSI_DIM = "\x1b[2m"

# Categories the user may pick from in the override menu. Order is
# stable so the numeric shortcuts don't shift between releases.
_CATEGORY_CHOICES: tuple[str, ...] = (
    "",
    "verb",
    "noun",
    "adjective",
    "adverb",
    "pronoun",
    "demonstrative",
    "modal",
    "number",
    "contraction",
)

# Same fieldnames as the ones written by setup / gen. Kept in sync
# with chord.Chord and vocab.pipeline._FIELDNAMES.
_FIELDNAMES = [
    "word",
    "chord",
    "category",
    "frequency",
    "alt1",
    "alt2",
    "alt3",
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def add_words(
    words: list[str],
    options: GenOptions,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Interactively add ``words`` to ``options.file`` (chords.csv).

    ``input_fn``/``output_fn`` are injected so tests can drive the
    prompts deterministically.
    """
    chords = load_file(options.file)
    existing_words = _build_existing_words(chords)
    existing_chord_keys = _build_existing_chord_keys(chords)

    scorer = Scorer(options)
    alt_generator = AltGenerator(options)
    keyboard = options.keyboard.get_keyboard()

    added = 0
    for raw in words:
        word = (raw or "").strip()
        if not word:
            continue
        lower = word.lower()
        if lower in existing_words:
            output_fn(f"{word}: already in chords.csv (skipping)")
            continue

        category = _detect_category(word)
        category = _prompt_category(word, category, input_fn, output_fn)

        row: Chord = {
            "word": word,
            "chord": "",
            "category": category,
            "frequency": "",
            "alt1": "",
            "alt2": "",
            "alt3": "",
            "options": None,
        }

        scored = scorer.score(dict(row))
        opts = scored.get("options") or []
        free = _collision_free_options(
            opts,
            existing_chord_keys,
            options.min_chord_length,
            _MAX_SHOW,
        )
        chosen = _prompt_chord(
            word,
            free,
            keyboard,
            options,
            existing_chord_keys,
            input_fn,
            output_fn,
        )
        if chosen is None:
            output_fn(f"{word}: skipped")
            continue

        row["chord"] = chosen
        # Run the alt generator on a freshly-allocated dict so the
        # ``options`` key (used by Scorer above) doesn't leak into
        # the file.
        alt_row: Chord = {
            "word": row["word"],
            "chord": row["chord"],
            "category": row["category"],
            "frequency": row["frequency"],
            "alt1": "",
            "alt2": "",
            "alt3": "",
            "options": None,
        }
        alt_generator.add_alt(alt_row)
        _filter_alt_collisions(alt_row, existing_words)
        row["alt1"] = alt_row.get("alt1", "")
        row["alt2"] = alt_row.get("alt2", "")
        row["alt3"] = alt_row.get("alt3", "")

        chords.append(row)
        existing_words.add(lower)
        for slot in ("alt1", "alt2", "alt3"):
            alt = (row.get(slot) or "").strip().lower()
            if alt:
                existing_words.add(alt)
        existing_chord_keys.add(_sorted_key(chosen))

        _write_chords_atomically(chords, options.file)
        added += 1
        alt_summary = ", ".join(
            f"{slot}={row[slot]}" for slot in ("alt1", "alt2", "alt3")
        )
        output_fn(f"+ {word} -> {chosen} ({alt_summary})")

    output_fn(f"Added {added} word{'s' if added != 1 else ''}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sorted_key(chord: str) -> str:
    return "".join(sorted(chord))


def _build_existing_words(chords: list[Chord]) -> set[str]:
    out: set[str] = set()
    for c in chords:
        word = (c.get("word") or "").strip().lower()
        if word:
            out.add(word)
        for slot in ("alt1", "alt2", "alt3"):
            alt = (c.get(slot) or "").strip().lower()
            if alt:
                out.add(alt)
    return out


def _build_existing_chord_keys(chords: list[Chord]) -> set[str]:
    out: set[str] = set()
    for c in chords:
        chord = (c.get("chord") or "").strip()
        if chord:
            out.add(_sorted_key(chord))
    return out


def _detect_category(word: str) -> str:
    """Return the auto-detected category for ``word``.

    Closed-class words are looked up in the SUBTLEX retag table
    first; everything else falls through to ``pattern.en.parse``
    which assigns a Penn Treebank tag we map to a chordgen category.
    Unknown / nonsense input returns ``""``.
    """
    cls = closed_class_category(word)
    if cls is not None:
        return cls
    try:
        from pattern import en

        parsed = en.parse(word, lemmata=False)
    except Exception:
        logging.exception("Failed to parse %r with pattern.en", word)
        return ""
    # ``parsed`` is a ``TaggedString`` whose ``str()`` looks like
    # ``"word/TAG/CHUNK/O"`` (whitespace-separated for multi-token
    # input). Take the first whitespace-token's POS tag.
    text = str(parsed)
    if not text:
        return ""
    first = text.split()[0]
    parts = first.split("/")
    if len(parts) < 2:
        return ""
    tag = parts[1]
    if tag.startswith("VB"):
        return "verb"
    if tag.startswith("NN"):
        return "noun"
    if tag.startswith("JJ"):
        return "adjective"
    if tag.startswith("RB"):
        return "adverb"
    return ""


def _collision_free_options(
    options: list[Option],
    existing_chord_keys: set[str],
    min_chord_length: int,
    max_show: int,
) -> list[Option]:
    """Return the top ``max_show`` options whose chord is at least
    ``min_chord_length`` long and whose sorted-key is not already in
    ``existing_chord_keys``. Preserves the score order from the
    scorer (ascending = better)."""
    out: list[Option] = []
    for opt in options:
        chord = opt["chord"]
        if len(chord) < min_chord_length:
            continue
        if _sorted_key(chord) in existing_chord_keys:
            continue
        out.append(opt)
        if len(out) >= max_show:
            break
    return out


def _prompt_category(
    word: str,
    default: str,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> str:
    """Show the category override menu, defaulting to ``default``.
    The user types a number or presses Enter to accept the default."""
    label = default if default else "(none)"
    output_fn(f"\nCategory for {word!r} (auto: {label}):")
    for i, choice in enumerate(_CATEGORY_CHOICES, start=1):
        marker = " *" if choice == default else ""
        display = choice if choice else "(none)"
        output_fn(f"  [{i}] {display}{marker}")
    raw = input_fn("Pick category [Enter to accept auto]: ").strip()
    if not raw:
        return default
    try:
        idx = int(raw)
    except ValueError:
        output_fn(f"Invalid input {raw!r}; keeping {label}")
        return default
    if not 1 <= idx <= len(_CATEGORY_CHOICES):
        output_fn(f"Out of range; keeping {label}")
        return default
    return _CATEGORY_CHOICES[idx - 1]


def _prompt_chord(
    word: str,
    options: list[Option],
    keyboard,
    gen_options: GenOptions,
    existing_chord_keys: set[str],
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> str | None:
    """Show the numbered chord menu and return the chosen chord.

    Loops indefinitely until the user enters a valid number, accepts
    the top option with Enter, or types a valid custom chord. Returns
    ``None`` only if the input stream is exhausted (e.g. EOF in a
    test or piped input).

    When stdin is a real TTY and the caller hasn't injected a custom
    ``input_fn``, switches to a live raw-mode prompt that recolours
    the chord red while it's invalid and green once it becomes a
    valid custom chord — submit with Enter.
    """
    output_fn(f"\nChord options for {word!r}:")
    if options:
        for i, opt in enumerate(options, start=1):
            output_fn(f"  [{i}] {opt['chord']}   score={opt['score']}")
    else:
        output_fn("  (no collision-free options found)")
    output_fn(
        "Pick a number, type a custom chord, or Enter to accept "
        "the top option."
    )

    if input_fn is input and _supports_live_prompt():
        return _prompt_chord_live(
            word, options, keyboard, gen_options, existing_chord_keys
        )

    while True:
        try:
            raw = input_fn("Chord: ").strip().lower()
        except (EOFError, StopIteration):
            return None
        if not raw and options:
            return options[0]["chord"]
        if raw and raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]["chord"]
            output_fn(f"Out of range; valid: 1..{len(options)}")
            continue
        # Custom chord candidate.
        ok, reason = _validate_custom_chord(
            raw,
            word,
            keyboard,
            gen_options,
            existing_chord_keys,
        )
        if ok:
            return raw
        output_fn(f"Invalid chord {raw!r}: {reason}")


def _supports_live_prompt() -> bool:
    """Return True iff stdin/stdout are real TTYs and ``termios`` is
    available — i.e. we can put the terminal into cbreak mode and
    redraw on each keystroke. Falls back to False on Windows / piped
    input / dumb terminals."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    try:
        import termios  # noqa: F401
        import tty  # noqa: F401
    except ImportError:
        return False
    return True


def _prompt_chord_live(
    word: str,
    options: list[Option],
    keyboard,
    gen_options: GenOptions,
    existing_chord_keys: set[str],
) -> str | None:
    """Live raw-mode chord prompt.

    Buffers each keystroke, redraws the line as ``Chord: <buffer>``
    with the buffer coloured red until it becomes a valid custom
    chord (or matches one of the offered options) and green once it
    does. Submitting with Enter accepts:

    - the top option if the buffer is empty,
    - the indexed option if the buffer is just digits in range,
    - the buffer as a custom chord if it validates.

    Pressing Enter while the buffer is invalid redraws and waits for
    more input. Ctrl-C raises ``KeyboardInterrupt`` (Typer handles
    it). Ctrl-D on an empty buffer returns ``None``.
    """
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf = ""
    out = sys.stdout

    def render() -> None:
        # Carriage return + clear-to-end-of-line, then redraw.
        out.write("\r\x1b[K")
        out.write("Chord: ")
        if not buf:
            out.flush()
            return
        valid, reason = _buffer_status(
            buf, word, options, keyboard, gen_options, existing_chord_keys
        )
        colour = _ANSI_GREEN if valid else _ANSI_RED
        out.write(f"{colour}{buf}{_ANSI_RESET}")
        if not valid and reason:
            out.write(f"   {_ANSI_DIM}({reason}){_ANSI_RESET}")
        out.flush()

    try:
        tty.setcbreak(fd)
        render()
        while True:
            ch = sys.stdin.read(1)
            if not ch:  # Ctrl-D on empty buffer.
                if not buf:
                    out.write("\n")
                    out.flush()
                    return None
                continue
            code = ord(ch)
            if code in (3,):  # Ctrl-C.
                out.write("\n")
                out.flush()
                raise KeyboardInterrupt
            if code in (10, 13):  # Enter.
                resolved = _resolve_buffer(
                    buf,
                    word,
                    options,
                    keyboard,
                    gen_options,
                    existing_chord_keys,
                )
                if resolved is not None:
                    out.write("\n")
                    out.flush()
                    return resolved
                # Invalid — keep prompting.
                continue
            if code in (127, 8):  # Backspace / DEL.
                buf = buf[:-1]
                render()
                continue
            if code < 32:  # Other control chars: ignore.
                continue
            buf += ch.lower()
            render()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _buffer_status(
    buf: str,
    word: str,
    options: list[Option],
    keyboard,
    gen_options: GenOptions,
    existing_chord_keys: set[str],
) -> tuple[bool, str | None]:
    """Return ``(valid, reason)`` describing what would happen if
    Enter were pressed right now.

    - Empty buffer → valid (resolves to the top option if any).
    - Pure-digit buffer → valid iff the index is in range.
    - Anything else → run through ``_validate_custom_chord``.

    ``reason`` is ``None`` when valid, otherwise a short human-
    readable explanation suitable for inline display.
    """
    if not buf:
        if options:
            return True, None
        return False, "no options available"
    if buf.isdigit():
        idx = int(buf)
        if 1 <= idx <= len(options):
            return True, None
        return False, f"out of range; valid: 1..{len(options)}"
    return _validate_custom_chord(
        buf, word, keyboard, gen_options, existing_chord_keys
    )


def _resolve_buffer(
    buf: str,
    word: str,
    options: list[Option],
    keyboard,
    gen_options: GenOptions,
    existing_chord_keys: set[str],
) -> str | None:
    """Return the chord ``buf`` would produce if Enter were pressed
    right now, or ``None`` if the buffer is currently invalid.

    - Empty buffer → top option (if any).
    - All digits → option at that 1-based index (if in range).
    - Otherwise → the buffer itself, validated as a custom chord.
    """
    valid, _ = _buffer_status(
        buf, word, options, keyboard, gen_options, existing_chord_keys
    )
    if not valid:
        return None
    if not buf:
        return options[0]["chord"]
    if buf.isdigit():
        return options[int(buf) - 1]["chord"]
    return buf


def _validate_custom_chord(
    chord: str,
    word: str,
    keyboard,
    gen_options: GenOptions,
    existing_chord_keys: set[str],
) -> tuple[bool, str | None]:
    """Validate a hand-typed chord. Returns ``(True, None)`` on
    success or ``(False, reason)`` describing why it was rejected.

    Mirrors the rules enforced by the scorer:

    - Chord must be at least ``gen.min_chord_length`` long.
    - The first character must equal the word's first character
      (the prefix-lock invariant in ``find_combinations``).
    - After applying ``gen.key_replacement``, every key must be on
      the keyboard (``keyboard.score`` returns ``-1`` otherwise).
    - Sorted-key must not collide with any chord already in
      ``chords.csv``.
    """
    if not chord:
        return False, "empty chord"
    if len(chord) < gen_options.min_chord_length:
        return (
            False,
            f"shorter than min_chord_length={gen_options.min_chord_length}",
        )
    if chord[0] != word.lower()[0]:
        return (
            False,
            f"first letter must match word ({word.lower()[0]!r})",
        )
    if _sorted_key(chord) in existing_chord_keys:
        return False, "collides with an existing chord"
    replacements = gen_options.key_replacement or {}
    mapped = "".join(replacements.get(c, c) for c in chord)
    if keyboard.score(mapped) == -1:
        return False, "one or more keys are not on the keyboard"
    return True, None


def _filter_alt_collisions(row: Chord, existing_words: set[str]) -> None:
    """Drop any alt slot whose generated form collides with an
    existing word in ``chords.csv``. Mutates ``row`` in place.

    Note: we don't compare against later alt slots within the same
    row because :class:`AltGenerator` already skips identity forms.
    """
    for slot in ("alt1", "alt2", "alt3"):
        alt = (row.get(slot) or "").strip().lower()
        if alt and alt in existing_words:
            row[slot] = ""


def _write_chords_atomically(chords: list[Chord], path: Path) -> None:
    """Rewrite ``chords.csv`` atomically: write to a sibling temp
    file then ``os.replace`` it over the target so a crash mid-write
    can't truncate the user's file."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=_FIELDNAMES,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(chords)
    os.replace(tmp, path)
