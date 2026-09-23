from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, TypedDict
import csv
import hashlib
import json


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


@dataclass(frozen=True)
class PracticeMapping:
    word: str
    base: str
    chord: str
    slot: int = 0
    frequency: str = ""

    @property
    def hint(self) -> str:
        return self.chord + (str(self.slot) if self.slot else "")

    def fingerprint(self, keyboard_kind: str, layout: list[list[str]] | None) -> str:
        payload = [self.word, self.base, sorted(self.chord), self.slot,
                   keyboard_kind, layout]
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def build_repertoire(chords: list[Chord]) -> dict[str, PracticeMapping]:
    """Assigned standalone forms, with primary precedence and first alt owner.

    Lookup keys are case-insensitive; prompts preserve the CSV spelling.
    """
    rows: dict[str, Chord] = {}
    out: dict[str, PracticeMapping] = {}
    standalone = [c for c in chords if c.get("category") != "contraction"]
    for c in standalone:
        word = c["word"]
        rows.setdefault(word.lower(), c)
        if c.get("chord"):
            out.setdefault(word.lower(), PracticeMapping(
                word, word, c["chord"], frequency=c.get("frequency", ""),
            ))
    for word, (base, slot, chord) in build_alt_index(standalone).items():
        row = rows.get(word.lower(), {})
        out.setdefault(word.lower(), PracticeMapping(
            word, base, chord, slot, row.get("frequency", ""),
        ))
    return out


def mapping_fingerprints(
    repertoire: dict[str, PracticeMapping],
    keyboard_kind: str,
    layout: list[list[str]] | None,
) -> dict[str, str]:
    return {m.word: m.fingerprint(keyboard_kind, layout) for m in repertoire.values()}


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
