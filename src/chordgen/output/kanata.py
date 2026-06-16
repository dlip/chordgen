from pathlib import Path
from chordgen.chord import Chord
from chordgen.constants import CONFIG_DIR
from pydantic import BaseModel, Field
from chordgen.pydantic import File


key_map = {
    " ": "spc",
    "←": "bspc",
}


class KanataOutput(BaseModel):
    file: File = CONFIG_DIR / "kanata_chords.kbd"
    chord_keys: list[str] = ["prtsc"]
    shifted_chord_keys: list[str] = ["prtsc", "ralt"]
    alt1_keys: list[str] = ["lalt"]
    alt2_keys: list[str] = ["spc"]
    alt3_keys: list[str] = ["lalt", "spc"]
    limit: int = 0
    chord_timeout: int = 100

    key_mapping: dict[str, str] = Field(
        default={},
        description="Since Kanata combos are based in the layout in defsrc (probably qwerty) you will need to remap the letters if you are using a custom layout eg. 'a': 'b'",
    )

    def output(self, chords: list[Chord]):
        output = "(defchordsv2\n"

        def translate_macro(word):
            result = []
            for k in word:
                if k in key_map:
                    result.append(key_map[k])
                elif k.isupper():
                    result.append("S-" + k.lower())
                else:
                    result.append(k)
            return result

        def translate_chord(chord):
            result = []
            for k in chord:
                if k in self.key_mapping:
                    result.append(self.key_mapping[k])
                else:
                    raise Exception(f"No key_map for {k}")
            return result

        alt_keys = [self.alt1_keys, self.alt2_keys, self.alt3_keys]
        count = 0
        for chord in chords:
            c = chord["chord"]
            if not c:
                continue

            count += 1
            if self.limit != 0 and count > self.limit:
                print(f"Stopping at line {self.limit} due to limit setting")
                break

            # Detect contractions by category, not by ``'`` in word, so
            # genuine apostrophe words (``o'clock``) stay literal.
            is_contraction = chord["category"] == "contraction"
            words = [chord["word"], chord["alt1"], chord["alt2"], chord["alt3"]]
            for i, word in enumerate(words):
                if not word:
                    continue
                alt = []
                if i > 0:
                    alt = alt_keys[i - 1]

                keys = translate_chord(c)
                # Contractions (``'s``, ``'re``, ``n't``, ...) are typed
                # *after* a chorded word that already appended a space,
                # so prepend the ``←`` sentinel to delete it first.
                bspc = "←" if is_contraction else ""
                macro = translate_macro(bspc + word + " ")

                output += f"  ({' '.join(self.chord_keys + alt)} {' '.join(keys)}) (macro {' '.join(macro)}) {self.chord_timeout} first-release ()\n"
                if self.shifted_chord_keys and not is_contraction:
                    shifted_macro = translate_macro(word.capitalize() + " ")
                    output += f"  ({' '.join(self.shifted_chord_keys + alt)} {' '.join(keys)}) (macro {' '.join(shifted_macro)}) {self.chord_timeout} first-release ()\n"

        output += ")"

        print(f"Writing {self.file}")
        with open(self.file, "w") as file:
            file.write(output)
