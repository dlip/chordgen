"""Build chords.csv from a frequency-ranked vocabulary source."""

import csv
import logging
import re
from pathlib import Path

from chordgen.vocab import SOURCES, VocabRow, VocabSource

# Columns in the generated chords.csv. Must stay in sync with chord.Chord.
_FIELDNAMES = [
    "word",
    "chord",
    "reserved_chord",
    "category",
    "frequency",
    "alt1",
    "alt2",
    "alt3",
]

# Drop entries that aren't real lexical words (digits, punctuation,
# names with apostrophes etc.). SUBTLEX includes a lot of those near
# the top because subtitles are noisy.
_WORD_RE = re.compile(r"^[a-z]+$")

# The only valid single-letter English words. Anything else of length 1
# is a subtitle artifact (apostrophe-stripped contraction: 's, 't, ...).
_VALID_SINGLE_LETTERS = {"a", "i"}

# Sentinel categories emitted by sources to flag rows for filtering.
# Anything starting with "_" is dropped; real categories never have one.
_DROP_PREFIX = "_"


def _accept(row: VocabRow) -> bool:
    word = row.word.lower()
    if not _WORD_RE.match(word):
        return False
    if len(word) == 1 and word not in _VALID_SINGLE_LETTERS:
        return False
    if row.category.startswith(_DROP_PREFIX):
        # Sentinel categories (e.g. _propn for proper nouns,
        # _letter for stripped contractions) flag drop-on-ingest.
        return False
    return True


def build_chords_csv(
    source_name: str,
    output_file: Path,
    cache_dir: Path,
    size: int,
    min_frequency: float,
) -> None:
    """Fetch + parse a vocab source and write chords.csv."""
    if source_name not in SOURCES:
        raise ValueError(
            f"Unknown vocab source '{source_name}'. "
            f"Available: {sorted(SOURCES)}"
        )
    source: VocabSource = SOURCES[source_name]()

    cache_dir.mkdir(parents=True, exist_ok=True)
    raw_path = source.fetch(cache_dir)
    print(f"Parsing {raw_path.name}")

    seen: set[str] = set()
    rows: list[VocabRow] = []
    for row in source.parse(raw_path):
        word = row.word.lower()
        if word in seen:
            continue
        if row.frequency < min_frequency:
            continue
        if not _accept(row):
            continue
        seen.add(word)
        rows.append(VocabRow(word=word, frequency=row.frequency, category=row.category))

    rows.sort(key=lambda r: (-r.frequency, r.word))
    rows = rows[:size]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing {output_file} ({len(rows)} words from {source_name})")
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "word": row.word,
                    "chord": "",
                    "reserved_chord": "",
                    "category": row.category,
                    "frequency": f"{row.frequency:.2f}",
                    "alt1": "",
                    "alt2": "",
                    "alt3": "",
                }
            )
    logging.info(f"Wrote {len(rows)} rows to {output_file}")
