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


# Adjectives where ``pattern.en.comparative`` / ``superlative`` produce
# wrong forms (``properer``, ``wholeer``, ``chineseer``, ...). When a
# word lands in this set the inflector falls back to the analytic
# ``more X`` / ``most X`` form. Erring on the side of inclusion is
# safe — the cost of a false positive is the user sees ``more X`` /
# ``most X`` instead of ``Xer``/``Xest``, which is grammatically
# valid in English.
_NON_GRADABLE: frozenset[str] = frozenset({
    # Function/closed-class adjectives that are not gradable
    "other", "last", "first", "second", "next", "previous", "former",
    "latter", "main", "key", "mid", "rid", "same", "such", "whole",
    "entire", "single", "total", "complete", "absolute", "ultimate",
    "supreme", "unique", "perfect", "ideal", "ancient", "modern",
    "current", "recent", "present",
    # Pseudo-modifiers / determiner-ish
    "own", "real", "actual", "very", "mere",
    # Reaction/state adjectives that don't gradate via -er
    "alive", "awake", "asleep", "afraid", "aware", "alone", "alike",
    "ajar", "ablaze",
    # Compound/longer adjectives where pattern.en wrongly suffixes -er
    "welcome", "worth", "daily", "weekly", "monthly", "yearly",
    "possible", "impossible", "horrible", "terrible", "incredible",
    "responsible", "available", "comfortable", "reasonable",
    "valuable", "vulnerable",
    # Nationality/proper-ish adjectives
    "chinese", "english", "french", "german", "italian", "spanish",
    "british", "american", "european", "irish", "scottish", "japanese",
    # Multi-syllable -ous / -ive / -al / -ic that should always use more/most
    "famous", "various", "obvious", "serious", "conscious",
    "religious", "ridiculous", "dangerous", "gorgeous", "delicious",
    "previous", "nervous", "enormous",
    "positive", "negative", "expensive", "impressive", "massive",
    "exciting", "interesting", "amazing", "stunning", "delighted",
    "surprised", "tired", "scared", "worried", "upset", "pointless",
    "honest", "dishonest", "afraid",
    "general", "natural", "personal", "national", "international",
    "classical", "magical", "musical", "political", "economical",
    "logical", "criminal", "technical", "physical", "medical",
    "magic", "basic", "classic", "tragic", "scientific",
    "important", "different", "significant", "decent", "confident",
    "expert", "essential", "professional", "traditional",
    "official", "social", "central", "global", "local", "legal",
    "formal", "casual", "neutral", "fatal", "vital",
    "executive", "creative", "actual", "potential",
    "female", "male", "civil", "common", "human",
    "fabulous", "fantastic", "brilliant", "wonderful", "marvellous",
    "awesome", "awful", "rubbish", "bloody", "stunning",
    "victorian", "italian", "spanish", "french", "british",
    "honourable", "favourite", "extraordinary", "ordinary",
    "secret", "current", "unique", "individual", "particular",
    "additional", "average", "overall", "extra",
    "private", "public", "open", "shut", "closed", "free",
    "further", "either", "neither", "only", "main",
    "non", "anti", "pro", "ex", "semi",
})


# Compound-noun suffixes that never pluralise on their own (``something``
# stays singular; ``everyone``, ``nobody``, ``everywhere``).
_NON_PLURALIZABLE_SUFFIXES: tuple[str, ...] = (
    "thing", "one", "body", "where",
)

# Nouns the pluraliser should leave alone — interjections, mass /
# abstract nouns, and pseudo-words SUBTLEX surfaces as nouns.
_NON_PLURALIZABLE: frozenset[str] = frozenset({
    # Already-included pseudo-words that shouldn't pluralise
    "gonna", "wanna", "gotta", "kinda", "sorta", "lemme", "dunno",
    # Interjections / particles
    "hm", "hmm", "huh", "yeah", "yes", "no", "ok", "okay", "wow",
    "whoa", "ah", "oh", "ha", "hey", "uh", "um", "yo", "eh",
    # Mass / abstract nouns commonly seen
    "information", "advice", "luggage", "furniture", "music",
    "research", "evidence", "homework", "weather", "knowledge",
    "fun", "luck", "stuff", "progress", "hell",
    # Other oddballs from the CSV
    "whilst",
})


# Verbs whose ``pattern.en.conjugate`` output is unreliable. Each row
# spells out the four forms emitted into alt slots; ``""`` means the
# alt slot is left empty (used for pseudo-verbs like ``wanna`` /
# ``gotta`` and contraction stems like ``ca`` / ``wo`` / ``ai`` that
# slipped through SUBTLEX retag).
_IRREGULAR_VERBS: dict[str, dict[str, str]] = {
    "pay":    {"3sg": "pays",    "past": "paid",    "gerund": "paying",    "ppart": "paid"},
    "feed":   {"3sg": "feeds",   "past": "fed",     "gerund": "feeding",   "ppart": "fed"},
    "escape": {"3sg": "escapes", "past": "escaped", "gerund": "escaping",  "ppart": "escaped"},
    "bear":   {"3sg": "bears",   "past": "bore",    "gerund": "bearing",   "ppart": "born"},
    "lay":    {"3sg": "lays",    "past": "laid",    "gerund": "laying",    "ppart": "laid"},
    "wear":   {"3sg": "wears",   "past": "wore",    "gerund": "wearing",   "ppart": "worn"},
    "left":   {"3sg": "leaves",  "past": "left",    "gerund": "leaving",   "ppart": "left"},
    "ca":     {"3sg": "",        "past": "",        "gerund": "",          "ppart": ""},
    "wo":     {"3sg": "",        "past": "",        "gerund": "",          "ppart": ""},
    "ai":     {"3sg": "",        "past": "",        "gerund": "",          "ppart": ""},
    "wanna":  {"3sg": "",        "past": "",        "gerund": "",          "ppart": ""},
    "gotta":  {"3sg": "",        "past": "",        "gerund": "",          "ppart": ""},
    "gonna":  {"3sg": "",        "past": "",        "gerund": "",          "ppart": ""},
    # ``born`` is the past participle of ``bear``, not a verb base; if
    # SUBTLEX leaks it as a verb, suppress its alts entirely so the
    # row doesn't ship ``borns``/``borned``/``borning``.
    "born":   {"3sg": "",        "past": "",        "gerund": "",          "ppart": ""},
}


def _build_verb_inflector() -> Inflector:
    from pattern import en

    def _conjugate(word: str, tense: str, table_key: str) -> str:
        override = _IRREGULAR_VERBS.get(word.lower())
        if override is not None:
            return override[table_key]
        return en.conjugate(word, tense) or ""

    return {
        "3sg": lambda w: _conjugate(w, "3sg", "3sg"),
        "past": lambda w: _conjugate(w, "p", "past"),
        "gerund": lambda w: _conjugate(w, "part", "gerund"),
        "ppart": lambda w: _conjugate(w, "ppart", "ppart"),
    }


def _build_noun_inflector() -> Inflector:
    from pattern import en

    def _pluralize(word: str) -> str:
        lower = word.lower()
        if lower in _NON_PLURALIZABLE:
            return ""
        if any(lower.endswith(suf) for suf in _NON_PLURALIZABLE_SUFFIXES):
            return ""
        result = en.pluralize(word, pos=en.NOUN) or ""
        # Defensive: ``mps`` -> ``mpss``, ``ears`` -> ``earss``. If the
        # input already ends in ``s`` and the pluraliser only doubled
        # it, the input was morphologically plural already and the
        # produced form is junk.
        if (
            lower.endswith("s")
            and result.lower().endswith("ss")
            and result[:-1].lower() == lower
        ):
            return ""
        # Defensive: pattern.en's singularize disagrees with itself —
        # if singularize(w) != w then w was already plural even though
        # is_base_form let it through (e.g. when category was empty).
        if en.singularize(word, pos=en.NOUN) != word:
            return ""
        return result

    return {
        "plural": _pluralize,
        "singular": lambda w: en.singularize(w, pos=en.NOUN),
    }


def _build_adjective_inflector() -> Inflector:
    from pattern import en

    def _comparative(word: str) -> str:
        lower = word.lower()
        if lower in _NON_GRADABLE:
            return f"more {word}"
        result = en.comparative(word) or ""
        # Heuristic: pattern.en sometimes naively suffixes ``er`` to
        # words it shouldn't gradate (``properer``, ``furtherer``).
        # Words <= 5 chars are short enough that ``-er`` is usually
        # legitimate (``older``, ``nicer``, ``bigger``); longer words
        # default to the analytic ``more X`` form.
        if len(word) > 5 and result.lower() == f"{lower}er":
            return f"more {word}"
        return result

    def _superlative(word: str) -> str:
        lower = word.lower()
        if lower in _NON_GRADABLE:
            return f"most {word}"
        result = en.superlative(word) or ""
        if len(word) > 5 and result.lower() == f"{lower}est":
            return f"most {word}"
        return result

    return {
        "comparative": _comparative,
        "superlative": _superlative,
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
# (singular/plural) x distance (proximal/distal).
_DEMONSTRATIVE_GROUPS: list[dict[str, str]] = [
    # singular, plural, proximal, distal
    {"singular": "this",  "plural": "these", "proximal": "this",  "distal": "that"},
    {"singular": "that",  "plural": "those", "proximal": "this",  "distal": "that"},
    {"singular": "this",  "plural": "these", "proximal": "these", "distal": "those"},
    {"singular": "that",  "plural": "those", "proximal": "these", "distal": "those"},
]
_DEMONSTRATIVE_FORM_PRIORITY: tuple[str, ...] = (
    "singular", "plural", "proximal", "distal",
)
_DEMONSTRATIVE_LOOKUP: dict[str, int] = {
    "this": 0, "that": 1, "these": 2, "those": 3,
}


def _build_demonstrative_inflector() -> Inflector:
    def _resolve(word: str, target_form: str) -> str:
        idx = _DEMONSTRATIVE_LOOKUP.get(word.lower())
        if idx is None:
            return ""
        out = _DEMONSTRATIVE_GROUPS[idx][target_form]
        return "" if out.lower() == word.lower() else out

    return {
        form: (lambda w, f=form: _resolve(w, f))
        for form in _DEMONSTRATIVE_FORM_PRIORITY
    }


# Modal verbs paired present <-> past. ``must`` has no past form so
# its past slot is empty (the alt generator skips empty results).
_MODAL_PAIRS: list[tuple[str, str]] = [
    ("can", "could"),
    ("will", "would"),
    ("shall", "should"),
    ("may", "might"),
    ("must", ""),
]
_MODAL_LOOKUP: dict[str, dict[str, str]] = {}
for _pres, _past in _MODAL_PAIRS:
    _MODAL_LOOKUP[_pres] = {"present": _pres, "past": _past}
    if _past:
        _MODAL_LOOKUP[_past] = {"present": _pres, "past": _past}


def _build_modal_inflector() -> Inflector:
    def _resolve(word: str, target_form: str) -> str:
        row = _MODAL_LOOKUP.get(word.lower())
        if row is None:
            return ""
        out = row[target_form]
        return "" if out.lower() == word.lower() else out

    return {
        "present": lambda w: _resolve(w, "present"),
        "past": lambda w: _resolve(w, "past"),
    }


# Cardinal <-> ordinal number pairs covering 1-20, decades 30-90,
# and the round magnitudes hundred / thousand / million.
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
_NUMBER_LOOKUP: dict[str, dict[str, str]] = {}
for _card, _ord in _NUMBER_PAIRS:
    _NUMBER_LOOKUP[_card] = {"cardinal": _card, "ordinal": _ord}
    _NUMBER_LOOKUP[_ord] = {"cardinal": _card, "ordinal": _ord}


def _build_number_inflector() -> Inflector:
    def _resolve(word: str, target_form: str) -> str:
        row = _NUMBER_LOOKUP.get(word.lower())
        if row is None:
            return ""
        out = row[target_form]
        return "" if out.lower() == word.lower() else out

    return {
        "cardinal": lambda w: _resolve(w, "cardinal"),
        "ordinal": lambda w: _resolve(w, "ordinal"),
    }


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


# Closed-class base/root forms. A "base" row is the canonical lemma
# of its paradigm (e.g. ``this`` for demonstratives, the nominative
# pronouns for personal pronouns). Only base rows generate alts and
# contribute to alt-coverage during chord assignment, so a non-base
# row like ``that`` or ``your`` doesn't shadow its base.
_PRONOUN_BASES: frozenset[str] = frozenset(
    g["nominative"].lower() for g in _PRONOUN_GROUPS
)
_DEMONSTRATIVE_BASES: frozenset[str] = frozenset({"this"})
_MODAL_BASES: frozenset[str] = frozenset(pres for pres, _ in _MODAL_PAIRS)
_NUMBER_BASES: frozenset[str] = frozenset(card for card, _ in _NUMBER_PAIRS)


# Process-local cache of pattern.en.lemma / singularize results so the
# base-form check is cheap to call for every row across both the alt
# generator and the assigner.
_VERB_LEMMA_CACHE: dict[str, str] = {}
_NOUN_LEMMA_CACHE: dict[str, str] = {}
_NOUN_PLURAL_CACHE: dict[str, str] = {}


def _verb_lemma(word: str) -> str:
    cached = _VERB_LEMMA_CACHE.get(word)
    if cached is not None:
        return cached
    from pattern import en

    lemma = en.lemma(word) or word
    _VERB_LEMMA_CACHE[word] = lemma
    return lemma


def _noun_lemma(word: str) -> str:
    cached = _NOUN_LEMMA_CACHE.get(word)
    if cached is not None:
        return cached
    from pattern import en

    lemma = en.singularize(word, pos=en.NOUN) or word
    _NOUN_LEMMA_CACHE[word] = lemma
    return lemma


def _noun_plural(word: str) -> str:
    cached = _NOUN_PLURAL_CACHE.get(word)
    if cached is not None:
        return cached
    from pattern import en

    plural = en.pluralize(word, pos=en.NOUN) or word
    _NOUN_PLURAL_CACHE[word] = plural
    return plural


def is_base_form(word: str, category: str) -> bool:
    """Return True when ``word`` is the canonical base/root form of
    its category. Used by the alt generator (only base rows get alts
    populated, avoiding ``was``/``are``/``be`` all listing the same
    ``is/were/being``) and by the chord assigner (only base rows
    contribute to alt-coverage). Closed-class categories check a
    small lookup table; open-class categories (verb, noun) consult
    ``pattern.en`` to compare against the lemma. Categories without
    a base notion (``adjective``, ``adverb``, ``""``, ``contraction``,
    ...) treat every row as a base."""
    w = word.lower()
    if category == "pronoun":
        return w in _PRONOUN_BASES
    if category == "demonstrative":
        return w in _DEMONSTRATIVE_BASES
    if category == "modal":
        return w in _MODAL_BASES
    if category == "number":
        return w in _NUMBER_BASES
    if category == "verb":
        return _verb_lemma(w) == w
    if category == "noun":
        if _noun_lemma(w) != w:
            return False
        # Defensive: ``mps`` lemmatises to ``mps`` but is morphologically
        # plural — pluralising it would produce ``mpss``. Detect that
        # case by checking whether pluralise(w) only doubles the
        # trailing ``s``, which means ``w`` was already the plural.
        plural = _noun_plural(w)
        if w.endswith("s") and plural.lower().endswith("ss") and plural[:-1].lower() == w:
            return False
        return True
    return True


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
        # Only base/root rows generate alts. Otherwise verbs like
        # ``was``/``are``/``be`` would all list ``is``/``were``/
        # ``being`` (pattern.en conjugates from the lemma regardless
        # of input), and ``your``/``that``/``could`` would echo alts
        # that already live on their base row.
        if not is_base_form(word, category):
            return chord
        for i, form in enumerate(category_cfg.forms[:3], start=1):
            slot = f"alt{i}"
            if chord.get(slot):
                continue
            fn = inflector.get(form)
            if fn is None:
                continue
            try:
                inflected = fn(word) or ""
            except Exception:
                logging.exception(
                    f"Failed to inflect {word!r} as {category}/{form}"
                )
                continue
            # Identity forms (e.g. plural of "series" is "series",
            # past of "hurt" is "hurt") waste an alt slot and confuse
            # the assigner's alt-coverage logic — skip them.
            if inflected.lower() == word.lower():
                continue
            chord[slot] = inflected

        logging.debug(
            f"Alts for word {word}: {chord['alt1']}, {chord['alt2']}, {chord['alt3']}"
        )
        return chord
