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
    "category",
    "frequency",
    "alt1",
    "alt2",
    "alt3",
]

# Drop entries that aren't real lexical words (digits, punctuation,
# names with apostrophes etc.). SUBTLEX includes a lot of those near
# the top because subtitles are noisy. Mixed-case proper-noun-ish
# garbage and apostrophe-stripped contraction artifacts ('s, 't,
# 'll, 've) are filtered upstream by the source-side ``_propn`` /
# ``_letter`` sentinels, so accepting upper-case letters here is safe.
_WORD_RE = re.compile(r"^[A-Za-z]+$")

# Sentinel categories emitted by sources to flag rows for filtering.
# Anything starting with "_" is dropped; real categories never have one.
_DROP_PREFIX = "_"


def _accept(row: VocabRow) -> bool:
    word = row.word
    if not _WORD_RE.match(word):
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
        # Preserve native casing on disk; dedup case-insensitively so
        # `"The"` and `"the"` collapse into a single entry (the
        # higher-frequency one wins because SUBTLEX yields rows in
        # descending-frequency order).
        word = row.word
        key = word.lower()
        if key in seen:
            continue
        if row.frequency < min_frequency:
            continue
        if not _accept(row):
            continue
        seen.add(key)
        rows.append(VocabRow(word=word, frequency=row.frequency, category=row.category))

    rows.sort(key=lambda r: (-r.frequency, r.word.lower()))
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
                    "category": row.category,
                    "frequency": f"{row.frequency:.2f}",
                    "alt1": "",
                    "alt2": "",
                    "alt3": "",
                }
            )
    logging.info(f"Wrote {len(rows)} rows to {output_file}")
