import json
from chordgen.chord import Chord
from chordgen.constants import CONFIG_DIR
from pydantic import BaseModel
from chordgen.pydantic import File


class CharaChorderOutput(BaseModel):
    file: File = CONFIG_DIR / "charachorder_chords.json"

    def translate_keys(self, chord: str):
        result = [ord(c) for c in chord]
        return result

    def output(self, chords: list[Chord]):
        output_chords = []
        for chord in chords:
            if not chord["chord"]:
                continue
            chord_keys = self.translate_keys(chord["chord"])
            word = chord["word"]
            word_keys = self.translate_keys(word)
            # Contractions (``'s``, ``'re``, ``n't``, ...) are typed
            # *after* a chorded word that already appended a space.
            # ASCII 8 (backspace) deletes that trailing space first
            # so the apostrophe attaches cleanly. Detected by category
            # rather than ``'`` in word so genuine apostrophe words
            # (``o'clock``) stay literal.
            if chord["category"] == "contraction":
                word_keys = [8] + word_keys
            output_chords.append([chord_keys, word_keys])

        output = {"charaVersion": 1, "type": "chords", "chords": output_chords}
        print(f"Writing {self.file}")
        with open(self.file, "w") as file:
            file.write(json.dumps(output))
