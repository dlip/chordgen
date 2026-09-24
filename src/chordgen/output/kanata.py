from chordgen.chord import Chord
from chordgen.output import assigned_rows
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

    def translate_chord(self, chord):
        result = []
        for key in chord:
            if key not in self.key_mapping:
                raise ValueError(f"No key_map for {key}")
            result.append(self.key_mapping[key])
        return result

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

        alt_keys = [self.alt1_keys, self.alt2_keys, self.alt3_keys]
        selected = assigned_rows(chords, self.limit)
        for chord in selected:
            c = chord["chord"]

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

                keys = self.translate_chord(c)
                # Contractions (``'s``, ``'re``, ``n't``, ...) are typed
                # *after* a chorded word that already appended a space,
                # so prepend the ``←`` sentinel to delete it first.
                bspc = "←" if is_contraction else ""
                macro = translate_macro(bspc + word + " ")

                output += f"  ({' '.join(self.chord_keys + alt)} {' '.join(keys)}) (macro {' '.join(macro)}) {self.chord_timeout} first-release ()\n"
                if self.shifted_chord_keys and not is_contraction:
                    shifted_macro = translate_macro(word.capitalize() + " ")
                    output += f"  ({' '.join(self.shifted_chord_keys + alt)} {' '.join(keys)}) (macro {' '.join(shifted_macro)}) {self.chord_timeout} first-release ()\n"

        if len(selected) < len(assigned_rows(chords)):
            print(f"Stopping at line {self.limit} due to limit setting")
        output += ")"

        print(f"Writing {self.file}")
        with open(self.file, "w") as file:
            file.write(output)
