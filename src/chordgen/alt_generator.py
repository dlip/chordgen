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


# category -> factory. Factories are called lazily so users who don't
# enable a category never pay its import cost.
_INFLECTOR_FACTORIES: dict[str, Callable[[], Inflector]] = {
    "verb": _build_verb_inflector,
    "noun": _build_noun_inflector,
    "adjective": _build_adjective_inflector,
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
