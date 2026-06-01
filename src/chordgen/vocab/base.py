from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class VocabRow:
    """A single word entry produced by a vocab source.

    `category` is a chordgen alt category: a lowercase tag matching a
    key under `gen.alts.<category>` in config (e.g. "verb", "noun",
    "adjective", "adverb"). Empty string for words with no inflectional
    alts. Sources may also emit underscore-prefixed sentinels (e.g.
    "_propn", "_letter") that the pipeline filters out before writing.
    """

    word: str
    zipf: float
    category: str = ""


class VocabSource(ABC):
    """Plug-in source for a frequency-ranked English vocabulary.

    Each source knows how to fetch its raw data file (cached on disk)
    and how to parse it into a stream of VocabRow ordered by descending
    frequency.
    """

    name: str

    @abstractmethod
    def fetch(self, cache_dir: Path) -> Path:
        """Download the raw source file into cache_dir, returning its path.

        Implementations should be idempotent: if the file is already
        present at the expected location, return it without re-downloading.
        """

    @abstractmethod
    def parse(self, path: Path) -> Iterator[VocabRow]:
        """Yield VocabRow records, in descending frequency order."""
