import logging
from chordgen.chord import Chord, Option
from chordgen.config import GenOptions
from chordgen.utils import find_combinations


class Scorer:
    def __init__(self, options: GenOptions) -> None:
        self._options = options
        self._keyboard = options.keyboard.get_keyboard()

    def score(self, chord: Chord) -> Chord:
        # Reserved row: user has pinned a chord by hand on a row with no
        # frequency value. Skip option generation.
        if chord["chord"] and not chord.get("frequency"):
            return chord

        # Bypass the min_word_length floor for contractions — they're
        # short by construction and the user explicitly imported them.
        is_contraction = chord["category"] == "contraction"
        if (
            not is_contraction
            and len(chord["word"]) < self._options.min_word_length
        ):
            return chord

        # Keep the apostrophe in chord candidates: every chord must
        # contain the first character of the word (the prefix-lock
        # invariant in ``find_combinations``), so for ``'s`` we cannot
        # silently strip the leading ``'`` — that would let chord
        # ``s`` win, violating the invariant. Users with no comfortable
        # apostrophe key should set ``gen.key_replacement: "'": x``
        # (or similar) to remap it onto a real key. Without a mapping
        # the keyboard scorer rejects ``'`` and no chord is assigned,
        # which is the right failure mode (loud, not silent).
        word_for_scoring = chord["word"].lower()
        combinations = find_combinations(word_for_scoring)
        replacements = self._options.key_replacement
        if replacements:
            combinations = [
                "".join(replacements.get(c, c) for c in combo)
                for combo in combinations
            ]
        scores = [self._keyboard.score(combination) for combination in combinations]
        options: list[Option] = [
            {"chord": combination, "score": scores[i]}
            for i, combination in enumerate(combinations)
            if scores[i] != -1
        ]
        options = sorted(options, key=lambda x: x["score"])
        chord["options"] = options
        logging.debug(f"Computed options for {chord['word']}")
        return chord
