from pathlib import Path
from typing import NotRequired, TypedDict
import csv


class Option(TypedDict):
    chord: str
    score: int


class Chord(TypedDict):
    word: str
    chord: str
    category: str
    frequency: str
    alt1: str
    alt2: str
    alt3: str
    debug: NotRequired[str]
    options: list[Option] | None


def load_file(file: Path) -> list[Chord]:
    with open(file) as f:
        reader = csv.DictReader(f)
        chords: list[Chord] = [line for line in reader]
        return chords


def build_alt_index(chords: list[Chord]) -> dict[str, tuple[str, int, str]]:
    """Map every non-empty alt form to ``(base_word, slot, chord)``.

    Used by drill and book modes to surface alt-slot words alongside
    their base. Collisions keep the first occurrence to mirror the
    duplicate-chord policy in :func:`validate_chords`.
    """
    out: dict[str, tuple[str, int, str]] = {}
    for c in chords:
        chord = c.get("chord") or ""
        if not chord:
            continue
        for slot in (1, 2, 3):
            alt = (c.get(f"alt{slot}") or "").strip()
            if not alt or alt == c["word"]:
                continue
            out.setdefault(alt, (c["word"], slot, chord))
    return out


def validate_chords(chords: list[Chord]):
    used = {}

    for chord in chords:
        c = chord["chord"]
        if c:
            sorted_chord = "".join(sorted(c))
            if sorted_chord in used:
                raise Exception(
                    f"Error: chord '{c}' for word {chord['word']} already used by {used[sorted_chord]}"
                )

            used[sorted_chord] = chord["word"]
