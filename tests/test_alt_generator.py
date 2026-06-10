"""Tests for the closed-class lookup-table inflectors in
alt_generator (pronoun, demonstrative, modal, number)."""

from __future__ import annotations

from chordgen.alt_generator import _PRONOUN_LOOKUP, AltGenerator
from chordgen.chord import Chord
from chordgen.config import (
    AdjectiveAltOptions,
    AltOptions,
    DemonstrativeAltOptions,
    GenOptions,
    ModalAltOptions,
    NounAltOptions,
    NumberAltOptions,
    PronounAltOptions,
    VerbAltOptions,
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
    # default forms = ["plural", "distal"]
    assert chord["alt1"] == "these"
    assert chord["alt2"] == "that"
    assert chord["alt3"] == ""


def test_demonstrative_only_base_gets_alts():
    # Non-base demonstratives (that/these/those) early-return so
    # ``add_alt`` leaves their slots empty even if they'd resolve
    # via the inflector lookup. The base form ``this`` is the only
    # row that materialises demonstrative alts.
    chord = _demo_gen(
        forms=["singular", "plural", "proximal"],
    ).add_alt(_demo_chord("those"))
    assert chord["alt1"] == ""
    assert chord["alt2"] == ""
    assert chord["alt3"] == ""
    chord = _demo_gen(
        forms=["singular", "plural", "proximal"],
    ).add_alt(_demo_chord("this"))
    # this: singular=this (skipped), plural=these, proximal=this (skipped)
    assert chord["alt1"] == ""
    assert chord["alt2"] == "these"
    assert chord["alt3"] == ""


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


def test_modal_default_past_for_can():
    chord = _modal_gen().add_alt(_modal_chord("can"))
    assert chord["alt1"] == "could"
    assert chord["alt2"] == ""
    assert chord["alt3"] == ""


def test_modal_only_base_gets_alts():
    # The past-tense halves (could/would/should/might) are non-base,
    # so ``add_alt`` early-returns: their alt slots stay empty even
    # though the inflector could resolve them. Only the present-tense
    # base (can/will/shall/may/must) fills slots.
    chord = _modal_gen(forms=["present"]).add_alt(_modal_chord("would"))
    assert chord["alt1"] == ""
    chord = _modal_gen(forms=["present", "past"]).add_alt(_modal_chord("can"))
    # present=can (skipped), past=could
    assert chord["alt1"] == ""
    assert chord["alt2"] == "could"


def test_modal_must_has_no_past():
    chord = _modal_gen(forms=["past"]).add_alt(_modal_chord("must"))
    # must has no past partner so the slot stays empty.
    assert chord["alt1"] == ""


def test_modal_skips_self():
    # past form of `could` is `could` itself (it's the past slot of
    # the can/could pair); requesting `past` returns "" by the
    # self-skip rule.
    chord = _modal_gen(forms=["past"]).add_alt(_modal_chord("could"))
    assert chord["alt1"] == ""


# ---------------------------------------------------------------------
# Number
# ---------------------------------------------------------------------


def _num_gen(forms: list[str] | None = None) -> AltGenerator:
    opts = NumberAltOptions(forms=forms) if forms is not None else NumberAltOptions()
    return AltGenerator(GenOptions(alts=AltOptions(overwrite=True, number=opts)))


def _num_chord(word: str) -> Chord:
    return _empty_chord(word, category="number")


def test_number_default_ordinal_for_one():
    chord = _num_gen().add_alt(_num_chord("one"))
    assert chord["alt1"] == "first"


def test_number_only_base_gets_alts():
    # Ordinals (first/second/third/...) are non-base, so ``add_alt``
    # early-returns. Cardinals are the canonical base.
    chord = _num_gen(forms=["cardinal"]).add_alt(_num_chord("third"))
    assert chord["alt1"] == ""
    chord = _num_gen(forms=["cardinal", "ordinal"]).add_alt(_num_chord("three"))
    # cardinal=three (skipped), ordinal=third
    assert chord["alt1"] == ""
    assert chord["alt2"] == "third"


def test_number_handles_decades_and_magnitudes():
    chord = _num_gen(forms=["ordinal"]).add_alt(_num_chord("twenty"))
    assert chord["alt1"] == "twentieth"
    chord = _num_gen(forms=["ordinal"]).add_alt(_num_chord("thousand"))
    assert chord["alt1"] == "thousandth"


def test_unknown_number_is_noop():
    chord = _num_gen().add_alt(_num_chord("zero"))
    assert chord["alt1"] == ""


# ---------------------------------------------------------------------
# Base-form predicate (used by the assigner for alt-coverage)
# ---------------------------------------------------------------------


def test_is_base_form_closed_class():
    from chordgen.alt_generator import is_base_form

    # Pronouns: only nominatives are base.
    assert is_base_form("I", "pronoun")
    assert is_base_form("you", "pronoun")
    assert not is_base_form("me", "pronoun")
    assert not is_base_form("your", "pronoun")
    # Demonstratives: only ``this`` is base.
    assert is_base_form("this", "demonstrative")
    assert not is_base_form("that", "demonstrative")
    assert not is_base_form("these", "demonstrative")
    # Modals: only present-tense halves are base.
    assert is_base_form("can", "modal")
    assert not is_base_form("could", "modal")
    # Numbers: only cardinals are base.
    assert is_base_form("one", "number")
    assert not is_base_form("first", "number")


def test_is_base_form_open_class_passthrough():
    from chordgen.alt_generator import is_base_form

    # Verbs / nouns now consult pattern.en — only the lemma is base.
    assert is_base_form("run", "verb")
    assert not is_base_form("running", "verb")
    assert is_base_form("dog", "noun")
    assert not is_base_form("dogs", "noun")
    # Categories without a base notion treat every row as base.
    assert is_base_form("better", "adjective")
    assert is_base_form("anything", "")


# ---------------------------------------------------------------------
# Fix 5: noun base form detects already-plural words
# ---------------------------------------------------------------------


def test_is_base_form_detects_double_s_plural():
    from chordgen.alt_generator import is_base_form

    # ``mps`` and ``ears`` lemmatise to themselves but are
    # morphologically plural; pluralising would produce ``mpss`` /
    # ``earss``. Reject them as base forms so the alt generator
    # doesn't ship junk plurals.
    assert not is_base_form("mps", "noun")
    assert not is_base_form("ears", "noun")
    # Words that legitimately end in ``ss`` and survive pattern.en's
    # lemma check are still base forms — the defensive guard fires
    # only when ``pluralise(w)`` is exactly ``w + 's'`` and ``w``
    # already ended in ``s``. ``progress`` -> ``progress`` (no
    # change), so the defensive check rightly leaves it as base.
    assert is_base_form("progress", "noun")


# ---------------------------------------------------------------------
# Fix 2: non-gradable adjectives use ``more X`` / ``most X``
# ---------------------------------------------------------------------


def _adj_gen(forms: list[str] | None = None) -> AltGenerator:
    opts = (
        AdjectiveAltOptions(forms=forms)
        if forms is not None
        else AdjectiveAltOptions()
    )
    return AltGenerator(GenOptions(alts=AltOptions(overwrite=True, adjective=opts)))


def _adj_chord(word: str) -> Chord:
    return _empty_chord(word, category="adjective")


def test_non_gradable_adjective_uses_more_most():
    gen = _adj_gen()  # default forms = ["comparative", "superlative"]
    for word in ("other", "whole", "welcome", "chinese", "important"):
        chord = gen.add_alt(_adj_chord(word))
        assert chord["alt1"] == f"more {word}", word
        assert chord["alt2"] == f"most {word}", word


def test_gradable_adjective_regression():
    gen = _adj_gen()
    chord = gen.add_alt(_adj_chord("big"))
    assert chord["alt1"] == "bigger"
    assert chord["alt2"] == "biggest"
    chord = gen.add_alt(_adj_chord("nice"))
    assert chord["alt1"] == "nicer"
    assert chord["alt2"] == "nicest"


# ---------------------------------------------------------------------
# Fix 3: noun pluraliser suppresses invalid plurals
# ---------------------------------------------------------------------


def _noun_gen(forms: list[str] | None = None) -> AltGenerator:
    opts = NounAltOptions(forms=forms) if forms is not None else NounAltOptions()
    return AltGenerator(GenOptions(alts=AltOptions(overwrite=True, noun=opts)))


def _noun_chord(word: str) -> Chord:
    return _empty_chord(word, category="noun")


def test_noun_compound_suffix_not_pluralized():
    gen = _noun_gen()
    for word in ("something", "everyone", "nobody", "everywhere"):
        chord = gen.add_alt(_noun_chord(word))
        assert chord["alt1"] == "", word


def test_noun_pseudo_words_not_pluralized():
    gen = _noun_gen()
    for word in ("gonna", "wanna", "gotta", "yeah", "huh"):
        chord = gen.add_alt(_noun_chord(word))
        assert chord["alt1"] == "", word


def test_noun_already_plural_not_pluralized():
    gen = _noun_gen()
    # ``mps`` and ``ears`` are already morphologically plural and
    # should be rejected by ``is_base_form`` -> alt slots stay empty.
    chord = gen.add_alt(_noun_chord("mps"))
    assert chord["alt1"] == ""
    chord = gen.add_alt(_noun_chord("ears"))
    assert chord["alt1"] == ""


def test_noun_pluralizer_regression():
    gen = _noun_gen()
    chord = gen.add_alt(_noun_chord("dog"))
    assert chord["alt1"] == "dogs"
    chord = gen.add_alt(_noun_chord("box"))
    assert chord["alt1"] == "boxes"
    chord = gen.add_alt(_noun_chord("country"))
    assert chord["alt1"] == "countries"


# ---------------------------------------------------------------------
# Fix 4: irregular verb conjugation overrides
# ---------------------------------------------------------------------


def _verb_gen(forms: list[str] | None = None) -> AltGenerator:
    opts = (
        VerbAltOptions(forms=forms) if forms is not None else VerbAltOptions()
    )
    return AltGenerator(GenOptions(alts=AltOptions(overwrite=True, verb=opts)))


def _verb_chord(word: str) -> Chord:
    return _empty_chord(word, category="verb")


def test_verb_irregular_overrides():
    gen = _verb_gen(forms=["3sg", "past", "gerund"])
    chord = gen.add_alt(_verb_chord("pay"))
    assert chord["alt1"] == "pays"
    assert chord["alt2"] == "paid"
    assert chord["alt3"] == "paying"

    chord = gen.add_alt(_verb_chord("feed"))
    assert chord["alt1"] == "feeds"
    assert chord["alt2"] == "fed"
    assert chord["alt3"] == "feeding"

    chord = gen.add_alt(_verb_chord("escape"))
    assert chord["alt1"] == "escapes"
    assert chord["alt2"] == "escaped"
    assert chord["alt3"] == "escaping"

    chord = gen.add_alt(_verb_chord("bear"))
    assert chord["alt1"] == "bears"
    assert chord["alt2"] == "bore"
    assert chord["alt3"] == "bearing"


def test_verb_bear_ppart_is_born():
    gen = _verb_gen(forms=["ppart"])
    chord = gen.add_alt(_verb_chord("bear"))
    assert chord["alt1"] == "born"


def test_verb_pseudo_and_contraction_stems_yield_empty():
    gen = _verb_gen(forms=["3sg", "past", "gerund"])
    for word in ("wanna", "gotta", "gonna", "born", "ca", "wo", "ai"):
        chord = gen.add_alt(_verb_chord(word))
        assert chord["alt1"] == "", word
        assert chord["alt2"] == "", word
        assert chord["alt3"] == "", word


# ---------------------------------------------------------------------
# Identity self-alts are skipped for open-class inflectors too
# (e.g. past of "hurt" is "hurt", plural of "series" is "series").
# ---------------------------------------------------------------------


def test_verb_identity_past_skipped():
    gen = _verb_gen(forms=["3sg", "past", "gerund"])
    chord = gen.add_alt(_verb_chord("hurt"))
    assert chord["alt1"] == "hurts"
    assert chord["alt2"] == ""  # past of hurt is hurt — skipped
    assert chord["alt3"] == "hurting"


def test_noun_identity_plural_skipped():
    gen = _noun_gen(forms=["plural"])
    chord = gen.add_alt(_noun_chord("series"))
    assert chord["alt1"] == ""  # plural of series is series — skipped
