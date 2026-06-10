"""Generate inflected alt forms for words based on their category.

Each chord row carries a `category` (verb/noun/adjective/adverb/"") that
selects an Inflector. The inflector knows how to produce a set of named
forms (e.g. "3sg", "past", "plural"); the per-category config picks
which forms land in alt1/alt2/alt3 and in what order.

Adding a new category is a matter of registering an Inflector and a
matching pydantic options model in config.py.
"""

import logging
from typing import Callable

from chordgen.chord import Chord
from chordgen.config import GenOptions

# An inflector is a small registry: form-name -> function(word) -> str.
Inflector = dict[str, Callable[[str], str]]


def _build_verb_inflector() -> Inflector:
    from pattern import en

    return {
        "3sg": lambda w: en.conjugate(w, "3sg"),
        "past": lambda w: en.conjugate(w, "p"),
        "gerund": lambda w: en.conjugate(w, "part"),
        "ppart": lambda w: en.conjugate(w, "ppart"),
    }


def _build_noun_inflector() -> Inflector:
    from pattern import en

    return {
        "plural": lambda w: en.pluralize(w, pos=en.NOUN),
        "singular": lambda w: en.singularize(w, pos=en.NOUN),
    }


def _build_adjective_inflector() -> Inflector:
    from pattern import en

    return {
        "comparative": en.comparative,
        "superlative": en.superlative,
    }


# Closed-class English personal-pronoun lookup. Each row holds the
# five grammatical forms; the inflector dispatches on form name and
# the input word selects the row. Forms that coincide with the input
# word return "" so the alt-generator skips the slot. Stored verbatim
# so generated alts inherit the natural casing (notably ``I``).
_PRONOUN_GROUPS: list[dict[str, str]] = [
    # nominative, objective, possessive_det, possessive_pron, reflexive
    {"nominative": "I",    "objective": "me",   "possessive_det": "my",    "possessive_pron": "mine",   "reflexive": "myself"},
    {"nominative": "you",  "objective": "you",  "possessive_det": "your",  "possessive_pron": "yours",  "reflexive": "yourself"},
    {"nominative": "he",   "objective": "him",  "possessive_det": "his",   "possessive_pron": "his",    "reflexive": "himself"},
    {"nominative": "she",  "objective": "her",  "possessive_det": "her",   "possessive_pron": "hers",   "reflexive": "herself"},
    {"nominative": "it",   "objective": "it",   "possessive_det": "its",   "possessive_pron": "its",    "reflexive": "itself"},
    {"nominative": "we",   "objective": "us",   "possessive_det": "our",   "possessive_pron": "ours",   "reflexive": "ourselves"},
    {"nominative": "they", "objective": "them", "possessive_det": "their", "possessive_pron": "theirs", "reflexive": "themselves"},
]

# Priority order used to resolve ambiguous surface forms. ``her`` is
# both objective and possessive_det of *she* — first occurrence wins
# so behaviour stays deterministic.
_PRONOUN_FORM_PRIORITY: tuple[str, ...] = (
    "nominative",
    "objective",
    "possessive_det",
    "possessive_pron",
    "reflexive",
)

# word.lower() -> (group_index, originating_form). Lower-cased keys
# follow the project-wide rule that lookups always case-fold.
_PRONOUN_LOOKUP: dict[str, tuple[int, str]] = {}
for _idx, _grp in enumerate(_PRONOUN_GROUPS):
    for _form in _PRONOUN_FORM_PRIORITY:
        _PRONOUN_LOOKUP.setdefault(_grp[_form].lower(), (_idx, _form))


def _build_pronoun_inflector() -> Inflector:
    def _resolve(word: str, target_form: str) -> str:
        entry = _PRONOUN_LOOKUP.get(word.lower())
        if entry is None:
            return ""
        group_idx, _ = entry
        out = _PRONOUN_GROUPS[group_idx][target_form]
        return "" if out.lower() == word.lower() else out

    return {
        form: (lambda w, f=form: _resolve(w, f))
        for form in _PRONOUN_FORM_PRIORITY
    }


# Demonstratives: this/that/these/those laid out as a 2x2 of number
# (singular/plural) x distance (proximal/distal). Form names are
# axis-flip operators rather than static labels so every form returns
# a different demonstrative regardless of which one is the input —
# this lets the alt-coverage pass collapse the whole paradigm down
# to the highest-frequency demonstrative.
_DEMO_BY_AXES: dict[tuple[bool, bool], str] = {
    # (is_plural, is_distal) -> word
    (False, False): "this",
    (False, True): "that",
    (True, False): "these",
    (True, True): "those",
}
_DEMO_AXES: dict[str, tuple[bool, bool]] = {v: k for k, v in _DEMO_BY_AXES.items()}
_DEMONSTRATIVE_FORMS: tuple[str, ...] = (
    "number_flip",
    "distance_flip",
    "diagonal",
)


def _build_demonstrative_inflector() -> Inflector:
    def _resolve(word: str, target_form: str) -> str:
        axes = _DEMO_AXES.get(word.lower())
        if axes is None:
            return ""
        is_pl, is_dist = axes
        if target_form == "number_flip":
            return _DEMO_BY_AXES[(not is_pl, is_dist)]
        if target_form == "distance_flip":
            return _DEMO_BY_AXES[(is_pl, not is_dist)]
        if target_form == "diagonal":
            return _DEMO_BY_AXES[(not is_pl, not is_dist)]
        return ""

    return {
        form: (lambda w, f=form: _resolve(w, f))
        for form in _DEMONSTRATIVE_FORMS
    }


# Modal verbs paired present <-> past. ``must`` has no past form.
# The single ``flip`` form returns the *other* member of the pair,
# regardless of which side the input sits on, so the highest-
# frequency modal covers its partner as an alt and the partner
# skips the primary-chord pool. Returns "" for unpaired modals
# (``must``) on the past side.
_MODAL_PAIRS: list[tuple[str, str]] = [
    ("can", "could"),
    ("will", "would"),
    ("shall", "should"),
    ("may", "might"),
    ("must", ""),
]
_MODAL_PARTNER: dict[str, str] = {}
for _pres, _past in _MODAL_PAIRS:
    if _past:
        _MODAL_PARTNER[_pres] = _past
        _MODAL_PARTNER[_past] = _pres
    else:
        _MODAL_PARTNER[_pres] = ""


def _build_modal_inflector() -> Inflector:
    return {"flip": lambda w: _MODAL_PARTNER.get(w.lower(), "")}


# Cardinal <-> ordinal number pairs covering 1-20, decades 30-90,
# and the round magnitudes hundred / thousand / million. Same
# flip-only model as modals: a single ``flip`` form returns the
# partner so the highest-frequency form covers its counterpart.
_NUMBER_PAIRS: list[tuple[str, str]] = [
    ("one", "first"), ("two", "second"), ("three", "third"),
    ("four", "fourth"), ("five", "fifth"), ("six", "sixth"),
    ("seven", "seventh"), ("eight", "eighth"), ("nine", "ninth"),
    ("ten", "tenth"), ("eleven", "eleventh"), ("twelve", "twelfth"),
    ("thirteen", "thirteenth"), ("fourteen", "fourteenth"),
    ("fifteen", "fifteenth"), ("sixteen", "sixteenth"),
    ("seventeen", "seventeenth"), ("eighteen", "eighteenth"),
    ("nineteen", "nineteenth"), ("twenty", "twentieth"),
    ("thirty", "thirtieth"), ("forty", "fortieth"),
    ("fifty", "fiftieth"), ("sixty", "sixtieth"),
    ("seventy", "seventieth"), ("eighty", "eightieth"),
    ("ninety", "ninetieth"), ("hundred", "hundredth"),
    ("thousand", "thousandth"), ("million", "millionth"),
]
_NUMBER_PARTNER: dict[str, str] = {}
for _card, _ord in _NUMBER_PAIRS:
    _NUMBER_PARTNER[_card] = _ord
    _NUMBER_PARTNER[_ord] = _card


def _build_number_inflector() -> Inflector:
    return {"flip": lambda w: _NUMBER_PARTNER.get(w.lower(), "")}


# category -> factory. Factories are called lazily so users who don't
# enable a category never pay its import cost.
_INFLECTOR_FACTORIES: dict[str, Callable[[], Inflector]] = {
    "verb": _build_verb_inflector,
    "noun": _build_noun_inflector,
    "adjective": _build_adjective_inflector,
    "pronoun": _build_pronoun_inflector,
    "demonstrative": _build_demonstrative_inflector,
    "modal": _build_modal_inflector,
    "number": _build_number_inflector,
    # adverb has no reliable inflector — leave unregistered.
}


class AltGenerator:
    def __init__(self, options: GenOptions) -> None:
        self.options = options
        self._inflectors: dict[str, Inflector] = {}

    def _get_inflector(self, category: str) -> Inflector | None:
        if category not in _INFLECTOR_FACTORIES:
            return None
        if category not in self._inflectors:
            self._inflectors[category] = _INFLECTOR_FACTORIES[category]()
        return self._inflectors[category]

    def add_alt(self, chord: Chord) -> Chord:
        alts_cfg = self.options.alts
        if alts_cfg.overwrite:
            chord["alt1"] = ""
            chord["alt2"] = ""
            chord["alt3"] = ""

        category = chord.get("category", "")
        if not category:
            return chord

        category_cfg = getattr(alts_cfg, category, None)
        if category_cfg is None or not category_cfg.enabled:
            return chord

        inflector = self._get_inflector(category)
        if inflector is None:
            return chord

        word = chord["word"]
        for i, form in enumerate(category_cfg.forms[:3], start=1):
            slot = f"alt{i}"
            if chord.get(slot):
                continue
            fn = inflector.get(form)
            if fn is None:
                continue
            try:
                chord[slot] = fn(word) or ""
            except Exception:
                logging.exception(
                    f"Failed to inflect {word!r} as {category}/{form}"
                )

        logging.debug(
            f"Alts for word {word}: {chord['alt1']}, {chord['alt2']}, {chord['alt3']}"
        )
        return chord
