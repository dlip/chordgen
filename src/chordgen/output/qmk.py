from chordgen.chord import Chord
from chordgen.constants import CONFIG_DIR
from pydantic import BaseModel
from chordgen.pydantic import File


qmk_key_codes = {
    ";": "KC_SCLN",
    ",": "KC_COMMA",
    ".": "KC_DOT",
    "'": "KC_QUOT",
    "-": "KC_MINUS",
}


class QmkOutput(BaseModel):
    file: File = CONFIG_DIR / "qmk_chords.def"
    chord_keys: list[str] = ["KC_CHORD"]
    shifted_chord_keys: list[str] = ["KC_CHORD", "KC_CHORD_SFT"]
    alt1_keys: list[str] = ["KC_CHORD_ALT1"]
    alt2_keys: list[str] = ["KC_CHORD_ALT2"]
    alt3_keys: list[str] = ["KC_CHORD_ALT1", "KC_CHORD_ALT2"]
    key_codes: dict[str, str] = {
        "A": "KC_SFT_A",
        "S": "KC_ALT_S",
        "D": "KC_GUI_D",
        "F": "KC_CTL_F",
        "J": "KC_CTL_J",
        "K": "KC_GUI_K",
        "L": "KC_ALT_L",
        ";": "KC_SFT_SEMI",
    }

    def translate_keys(self, chord):
        result = self.chord_keys.copy()
        key_codes = qmk_key_codes | self.key_codes

        for k in chord:
            k = k.upper()
            if k in key_codes:
                result.append(key_codes[k])
            elif k.isalnum():
                result.append(f"KC_{k}")
            else:
                raise Exception(
                    f"Unknown QMK code to map '{k}', add it to the chordgen config"
                )

        return result

    def output(self, chords: list[Chord]):
        alt_keys = [self.alt1_keys, self.alt2_keys, self.alt3_keys]
        output = ""
        for chord in chords:
            if not chord["chord"]:
                continue
            words = [chord["word"], chord["alt1"], chord["alt2"], chord["alt3"]]
            for i, word in enumerate(words):
                if not word:
                    continue
                keys = self.translate_keys(chord["chord"])
                alt = []
                if i > 0:
                    alt = alt_keys[i - 1]
                name = f"c_{chord['chord']}{i}".replace("'", "_").replace("-", "_")

                output += f'SUBS({name}, "{word} ", {", ".join(keys + alt)})\n'
                if self.shifted_chord_keys:
                    output += f'SUBS({name}s, "{word.capitalize()} ", {", ".join(keys + alt + self.shifted_chord_keys)})\n'

        print(f"Writing {self.file}")
        with open(self.file, "w") as file:
            file.write(output)
