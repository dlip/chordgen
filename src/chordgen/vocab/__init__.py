from chordgen.vocab.base import VocabRow, VocabSource
from chordgen.vocab.subtlex import SubtlexUK, SubtlexUS

SOURCES: dict[str, type[VocabSource]] = {
    "subtlex-us": SubtlexUS,
    "subtlex-uk": SubtlexUK,
}

__all__ = ["VocabRow", "VocabSource", "SOURCES"]
