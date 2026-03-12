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
            word_keys = self.translate_keys(chord["word"])
            output_chords.append([chord_keys, word_keys])

        output = {"charaVersion": 1, "type": "chords", "chords": output_chords}
        print(f"Writing {self.file}")
        with open(self.file, "w") as file:
            file.write(json.dumps(output))
