from pathlib import Path
from typing import TypedDict
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
    options: list[Option] | None


def load_file(file: Path) -> list[Chord]:
    with open(file) as f:
        reader = csv.DictReader(f)
        chords: list[Chord] = [line for line in reader]
        return chords


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
