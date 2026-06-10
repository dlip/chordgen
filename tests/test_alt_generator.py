"""Tests for the pronoun inflector in alt_generator."""

from __future__ import annotations

from chordgen.alt_generator import _PRONOUN_LOOKUP, AltGenerator
from chordgen.chord import Chord
from chordgen.config import (
    AltOptions,
    GenOptions,
    PronounAltOptions,
)


def _empty_chord(word: str, **overrides) -> Chord:
    chord: Chord = {
        "word": word,
        "chord": "",
        "category": "pronoun",
        "frequency": "7.00",
        "alt1": "",
        "alt2": "",
        "alt3": "",
        "options": None,
    }
    chord.update(overrides)  # type: ignore[typeddict-item]
    return chord


def _gen(
    forms: list[str] | None = None,
    overwrite: bool = True,
) -> AltGenerator:
    pronoun_opts = (
        PronounAltOptions(forms=forms) if forms is not None else PronounAltOptions()
    )
    options = GenOptions(
        alts=AltOptions(overwrite=overwrite, pronoun=pronoun_opts),
    )
    return AltGenerator(options)


def test_pronoun_lookup_is_deterministic_for_ambiguous_words():
    # `her` belongs to *she*'s objective and possessive_det; first
    # occurrence (objective) wins per priority order.
    assert _PRONOUN_LOOKUP["her"] == (3, "objective")
    # `his` belongs to *he*'s possessive_det and possessive_pron; the
    # nominative slot is `he`, objective `him`, so possessive_det wins.
    assert _PRONOUN_LOOKUP["his"] == (2, "possessive_det")


def test_pronoun_alt_generator_for_I():
    gen = _gen()  # default forms: objective, possessive_det, reflexive
    chord = gen.add_alt(_empty_chord("I"))
    assert chord["alt1"] == "me"
    assert chord["alt2"] == "my"
    assert chord["alt3"] == "myself"


def test_pronoun_alt_generator_skips_self():
    gen = _gen(forms=["objective", "possessive_det", "reflexive"])
    chord = gen.add_alt(_empty_chord("you"))
    # `you` is its own objective form, so slot 1 is skipped.
    assert chord["alt1"] == ""
    assert chord["alt2"] == "your"
    assert chord["alt3"] == "yourself"


def test_unknown_pronoun_is_noop():
    gen = _gen()
    chord = gen.add_alt(_empty_chord("thou"))
    assert chord["alt1"] == ""
    assert chord["alt2"] == ""
    assert chord["alt3"] == ""


def test_pronoun_alts_respect_overwrite_false():
    gen = _gen(overwrite=False)
    chord = gen.add_alt(_empty_chord("I", alt1="preset"))
    assert chord["alt1"] == "preset"
    assert chord["alt2"] == "my"
    assert chord["alt3"] == "myself"
