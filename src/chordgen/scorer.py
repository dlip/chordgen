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

        if len(chord["word"]) < self._options.min_word_length:
            return chord

        combinations = find_combinations(chord["word"].lower())
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
