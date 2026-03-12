from chordgen.chord import Chord
from chordgen.constants import CONFIG_DIR
from pydantic import BaseModel
from chordgen.pydantic import File


class TrainingOutput(BaseModel):
    file: File = CONFIG_DIR / "training.txt"

    def output(self, chords: list[Chord]):
        index = 0
        line_words = ""
        line_chords = ""

        print(f"Writing {self.file}")
        with open(self.file, "w") as training_file:
            for chord in chords:
                c = chord["chord"]
                if not c:
                    continue
                word = chord["word"]
                line_words += f"{word} "
                line_chords += c + (" " * (len(word) + 1 - len(c)))
                index += 1
                if index % 10 == 0:
                    training_file.write(line_words.rstrip())
                    training_file.write("\n")
                    training_file.write(line_chords.rstrip())
                    training_file.write("\n")
                    line_words = ""
                    line_chords = ""
