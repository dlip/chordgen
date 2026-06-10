"""SUBTLEX-US and SUBTLEX-UK vocabulary sources.

Both files share the same underlying data shape (word + Zipf frequency +
dominant POS) but are distributed in different formats and use slightly
different POS label sets, so each gets its own adapter.

POS values are normalised to chordgen alt categories: a small set of
lowercase tags that map 1:1 to entries in `gen.alts.<category>` config.
Only categories with inflectors are emitted (verb, noun, adjective,
adverb); everything else (determiners, prepositions, ...) becomes "" so
the alt generator skips it. Proper nouns are filtered out at ingest.
"""

import csv
import logging
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterator

from chordgen.vocab.base import VocabRow, VocabSource


# Mapping of native POS label -> chordgen alt category.
# SUBTLEX-US uses Title-cased labels, SUBTLEX-UK uses lowercase ones.
# We accept both forms via case-insensitive lookup.
#
# Sentinels (kept distinct from "" so we can drop them at ingest rather
# than carry through):
#   "_propn"  -> proper noun, filtered out (over-represented in subtitles)
#   "_letter" -> apostrophe-stripped contractions ('s, 't, 'll, 've), filtered
_POS_MAP: dict[str, str] = {
    "adjective": "adjective",
    "adverb": "adverb",
    "article": "",
    "conjunction": "",
    "determiner": "",
    "interjection": "",
    "letter": "_letter",
    "marker": "",
    "name": "_propn",
    "not": "",
    "noun": "noun",
    "number": "",
    "preposition": "",
    "pronoun": "pronoun",
    "to": "",
    "unclassified": "",
    "verb": "verb",
}


def _map_pos(label: str | None) -> str:
    if not label:
        return ""
    return _POS_MAP.get(label.strip().lower(), "")


# Surface forms produced when SUBTLEX splits English contractions on
# whitespace (`he's`, `we'll`, `I'm`, `you've`, `they're`, `she'd`, ...).
# Each tail's frequency is the aggregated count across every contraction
# ending in that tail, which makes them genuinely high-frequency tokens
# — we just need to restore the apostrophe and tag them so the alt
# generator skips them.
_CONTRACTION_TAILS: frozenset[str] = frozenset({
    "s", "re", "m", "ve", "ll", "d",
})

# Multi-character contraction surface forms that SUBTLEX *does* keep
# intact (with the apostrophe). Currently just ``n't`` (don't, can't,
# won't, ...). They flow through tagged ``contraction`` so the alt
# generator skips them and the output emitters apply the same
# backspace-then-apostrophe trick the leading-apostrophe forms use.
_CONTRACTION_WORDS: frozenset[str] = frozenset({"n't"})


def _rewrite_contraction_tail(word: str, category: str) -> tuple[str, str]:
    """If ``word`` is a SUBTLEX-split contraction tail, prepend an
    apostrophe and tag it with the ``contraction`` category. If it's
    a SUBTLEX-kept contraction word like ``n't``, retag it as a
    contraction without rewriting. Otherwise pass through unchanged.
    Contraction surface forms are inherently lowercase so the
    rewritten form is lower-cased."""
    lower = word.lower()
    if lower in _CONTRACTION_TAILS:
        return f"'{lower}", "contraction"
    if lower in _CONTRACTION_WORDS:
        return lower, "contraction"
    return word, category


def _download(url: str, dest: Path) -> None:
    if dest.exists():
        logging.info(f"Using cached {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    # SUBTLEX hosts reject the default urllib UA; pretend to be a browser.
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req) as resp, open(tmp, "wb") as f:
        while chunk := resp.read(64 * 1024):
            f.write(chunk)
    tmp.replace(dest)


def _extract_single(zip_path: Path, dest_dir: Path) -> Path:
    """Extract the (single) data file from a SUBTLEX zip archive."""
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        if len(names) != 1:
            raise RuntimeError(
                f"Expected exactly one file in {zip_path}, found: {names}"
            )
        zf.extract(names[0], dest_dir)
        return dest_dir / names[0]


class SubtlexUS(VocabSource):
    """SUBTLEX-US (American English, ~74k words, 51M-token subtitle corpus).

    Brysbaert, M., New, B., & Keuleers, E. (2012). Adding part-of-speech
    information to the SUBTLEX-US word frequencies.
    """

    name = "subtlex-us"
    url = (
        "https://www.ugent.be/pp/experimentele-psychologie/en/research/"
        "documents/subtlexus/subtlexus1.zip"
    )
    archive_name = "subtlex-us.zip"

    def fetch(self, cache_dir: Path) -> Path:
        zip_path = cache_dir / self.archive_name
        _download(self.url, zip_path)
        return _extract_single(zip_path, cache_dir)

    def parse(self, path: Path) -> Iterator[VocabRow]:
        # Imported lazily so users who never run setup don't need openpyxl
        # at import time.
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = ws.iter_rows(min_row=2, values_only=True)
        for r in rows:
            if not r or r[0] is None:
                continue
            word = str(r[0])
            freq_raw = r[14]  # "Zipf-value" column
            if freq_raw is None:
                continue
            try:
                frequency = float(freq_raw)
            except (TypeError, ValueError):
                continue
            word, category = _rewrite_contraction_tail(word, _map_pos(r[9]))
            yield VocabRow(word=word, frequency=frequency, category=category)
        wb.close()


class SubtlexUK(VocabSource):
    """SUBTLEX-UK (British English, ~160k words, BBC subtitle corpus).

    van Heuven, W.J.B., Mandera, P., Keuleers, E., & Brysbaert, M. (2014).
    SUBTLEX-UK: A new and improved word frequency database for British English.
    """

    name = "subtlex-uk"
    url = "https://psychology.nottingham.ac.uk/subtlex-uk/SUBTLEX-UK.txt.zip"
    archive_name = "subtlex-uk.zip"

    def fetch(self, cache_dir: Path) -> Path:
        zip_path = cache_dir / self.archive_name
        _download(self.url, zip_path)
        return _extract_single(zip_path, cache_dir)

    def parse(self, path: Path) -> Iterator[VocabRow]:
        with open(path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                word = (row.get("Spelling") or "").strip()
                if not word:
                    continue
                freq_raw = row.get("LogFreq(Zipf)")
                try:
                    frequency = float(freq_raw) if freq_raw else None
                except ValueError:
                    frequency = None
                if frequency is None:
                    continue
                word, category = _rewrite_contraction_tail(
                    word, _map_pos(row.get("DomPoS"))
                )
                yield VocabRow(word=word, frequency=frequency, category=category)
