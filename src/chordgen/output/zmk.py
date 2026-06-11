from chordgen.chord import Chord
from chordgen.constants import CONFIG_DIR
from pydantic import BaseModel, Field
from chordgen.pydantic import File

key_map = {
    "'": "QUOT",
    ";": "SEMI",
    ",": "COMMA",
    ".": "DOT",
    "-": "MINUS",
    " ": "SPC",
    "@": "AT",
    "?": "QUESTION",
    "←": "BSPC",
}


class ZmkOutput(BaseModel):
    chords_file: File = CONFIG_DIR / "zmk_chords.dtsi"
    macros_file: File = CONFIG_DIR / "zmk_macros.dtsi"
    chord_keys: list[str] = ["$"]
    shifted_chord_keys: list[str] = ["$", "#"]
    alt1_keys: list[str] = ["!"]
    alt2_keys: list[str] = ["@"]
    alt3_keys: list[str] = ["!", "@"]
    limit: int = Field(
        200,
        description="Limit the number of chords outputted. It will vary depending on MCU, but I have found ZMK to be quite limited compared to QMK with the number or chords it can fit.",
    )
    chord_timeout: int = 100

    key_positions: list[str] = Field(
        default=[
            "_qwertyuiop_",
            "_asdfghjkl;_",
            "_zxcvbnm,./_",
            "_!@#$_",
        ],
        description="Should contain the same number of characters as keys on your keyboard. Use _ to ignore a key. Chord, shift, alt1, alt2 can be represented by shifted characters such as $#!@. Spaces will be ignored and can be used for formatting.",
    )

    def output(self, chords: list[Chord]):
        key_positions = [
            item for items in self.key_positions for item in items if item != " "
        ]
        macros_output = """#define MACRO(NAME, BINDINGS) \\
        macro_##NAME: macro_##NAME { \\
            compatible = "zmk,behavior-macro"; \\
            #binding-cells = <0>; \\
            wait-ms = <0>; \\
            tap-ms = <10>; \\
            bindings = <BINDINGS>; \\
        };

"""

        chords_output = (
            """#define CHORD(NAME, BINDINGS, KEYPOS) \\
        chord_##NAME { \\
            timeout-ms = <"""
            + str(self.chord_timeout)
            + """>; \\
            bindings = <BINDINGS>; \\
            key-positions = <KEYPOS>; \\
            layers = <0>; \\
        };

"""
        )

        key_positions_map = {}
        for i, key in enumerate(key_positions):
            key_positions_map[key] = i

        def translate_keys(chord):
            result = []
            for k in chord:
                if k in key_positions_map:
                    result.append(key_positions_map[k])
                else:
                    raise Exception(
                        f'Unable to find key position for {k}, is it in "key_positions"?'
                    )
            result = [str(i) for i in result]
            return result

        def translate_macro(word, capitalize=False):
            result = []
            for i, k in enumerate(word):
                k = k.upper()
                kp = "&kp "
                if capitalize and i == 0:
                    kp += "LS("

                if k in key_map:
                    kp += key_map[k]
                else:
                    kp += k

                if capitalize and i == 0:
                    kp += ")"

                result.append(kp)
            return result

        # Convienience macros for punctuation
        for p in [";", ",", "."]:
            if p not in key_positions_map:
                continue
            name = f"c_{key_map[p]}"
            macro = translate_macro(f"←{p} ")
            positions = translate_keys([p] + self.chord_keys)
            macros_output += f"MACRO({name}, {' '.join(macro)})\n"
            chords_output += f"CHORD({name}, &macro_{name}, {' '.join(positions)})\n"

        alt_keys = [self.alt1_keys, self.alt2_keys, self.alt3_keys]
        count = 0
        for chord in chords:
            c = chord["chord"]
            if not c:
                continue

            count += 1
            if self.limit != 0 and count > self.limit:
                print(f"Stopping at chord {self.limit} due to limit setting")
                break

            words = [chord["word"], chord["alt1"], chord["alt2"], chord["alt3"]]
            for i, word in enumerate(words):
                if not word:
                    continue
                alt = []
                if i > 0:
                    alt = alt_keys[i - 1]
                name = f"c_{c}{'_' * i}".replace("'", "_")
                # Contractions (``'s``, ``'re``, ``n't``, ...) are typed
                # *after* a chorded word that already appended a space,
                # so we delete that space first via the ``←`` sentinel.
                # Detected by category rather than ``'`` in word so
                # genuine apostrophe words (``o'clock``) stay literal.
                is_contraction = chord["category"] == "contraction"
                bspc = "←" if is_contraction else ""
                macro = translate_macro(bspc + word + " ")

                positions = translate_keys(list(c) + self.chord_keys + alt)
                macros_output += f"MACRO({name}, {' '.join(macro)})\n"
                chords_output += (
                    f"CHORD({name}, &macro_{name}, {' '.join(positions)})\n"
                )

                if self.shifted_chord_keys and not is_contraction:
                    positions = translate_keys(list(c) + self.shifted_chord_keys + alt)
                    macro = translate_macro(word + " ", True)
                    macros_output += f"MACRO(s_{name}, {' '.join(macro)})\n"
                    chords_output += (
                        f"CHORD(s_{name}, &macro_s_{name}, {' '.join(positions)})\n"
                    )

        print(f"Writing {self.macros_file}")
        with open(self.macros_file, "w") as file:
            file.write(macros_output)

        print(f"Writing {self.chords_file}")
        with open(self.chords_file, "w") as file:
            file.write(chords_output)
