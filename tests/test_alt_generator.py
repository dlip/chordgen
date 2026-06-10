"""Tests for the closed-class lookup-table inflectors in
alt_generator (pronoun, demonstrative, modal, number)."""

from __future__ import annotations

from chordgen.alt_generator import _PRONOUN_LOOKUP, AltGenerator
from chordgen.chord import Chord
from chordgen.config import (
    AltOptions,
    DemonstrativeAltOptions,
    GenOptions,
    ModalAltOptions,
    NumberAltOptions,
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


# ---------------------------------------------------------------------
# Demonstrative
# ---------------------------------------------------------------------


def _demo_gen(forms: list[str] | None = None) -> AltGenerator:
    opts = (
        DemonstrativeAltOptions(forms=forms)
        if forms is not None
        else DemonstrativeAltOptions()
    )
    return AltGenerator(GenOptions(alts=AltOptions(overwrite=True, demonstrative=opts)))


def _demo_chord(word: str) -> Chord:
    return _empty_chord(word, category="demonstrative")


def test_demonstrative_default_forms_for_this():
    chord = _demo_gen().add_alt(_demo_chord("this"))
    # Default forms = ["number_flip", "distance_flip", "diagonal"].
    # this -> these (number flip), that (distance flip), those (diag).
    assert chord["alt1"] == "these"
    assert chord["alt2"] == "that"
    assert chord["alt3"] == "those"


def test_demonstrative_covers_all_others_from_any_input():
    # Every demonstrative must produce the other three under the
    # default form ordering, so the alt-coverage pass collapses the
    # whole paradigm down to the highest-frequency entry.
    for word in ("this", "that", "these", "those"):
        chord = _demo_gen().add_alt(_demo_chord(word))
        produced = {chord["alt1"], chord["alt2"], chord["alt3"]}
        expected = {"this", "that", "these", "those"} - {word}
        assert produced == expected, (word, produced)


def test_unknown_demonstrative_is_noop():
    chord = _demo_gen().add_alt(_demo_chord("yon"))
    assert chord["alt1"] == ""
    assert chord["alt2"] == ""
    assert chord["alt3"] == ""


# ---------------------------------------------------------------------
# Modal
# ---------------------------------------------------------------------


def _modal_gen(forms: list[str] | None = None) -> AltGenerator:
    opts = (
        ModalAltOptions(forms=forms) if forms is not None else ModalAltOptions()
    )
    return AltGenerator(GenOptions(alts=AltOptions(overwrite=True, modal=opts)))


def _modal_chord(word: str) -> Chord:
    return _empty_chord(word, category="modal")


def test_modal_flip_for_can():
    chord = _modal_gen().add_alt(_modal_chord("can"))
    assert chord["alt1"] == "could"
    assert chord["alt2"] == ""
    assert chord["alt3"] == ""


def test_modal_flip_from_past_side():
    # `would` is the past side; flip returns the present partner so
    # the lower-frequency form covers the higher-frequency one.
    chord = _modal_gen().add_alt(_modal_chord("would"))
    assert chord["alt1"] == "will"


def test_modal_must_has_no_partner():
    chord = _modal_gen().add_alt(_modal_chord("must"))
    assert chord["alt1"] == ""


# ---------------------------------------------------------------------
# Number
# ---------------------------------------------------------------------


def _num_gen(forms: list[str] | None = None) -> AltGenerator:
    opts = NumberAltOptions(forms=forms) if forms is not None else NumberAltOptions()
    return AltGenerator(GenOptions(alts=AltOptions(overwrite=True, number=opts)))


def _num_chord(word: str) -> Chord:
    return _empty_chord(word, category="number")


def test_number_flip_for_one():
    chord = _num_gen().add_alt(_num_chord("one"))
    assert chord["alt1"] == "first"


def test_number_flip_from_ordinal_side():
    chord = _num_gen().add_alt(_num_chord("third"))
    assert chord["alt1"] == "three"


def test_number_handles_decades_and_magnitudes():
    chord = _num_gen().add_alt(_num_chord("twenty"))
    assert chord["alt1"] == "twentieth"
    chord = _num_gen().add_alt(_num_chord("thousand"))
    assert chord["alt1"] == "thousandth"


def test_unknown_number_is_noop():
    chord = _num_gen().add_alt(_num_chord("zero"))
    assert chord["alt1"] == ""
