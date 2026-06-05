import logging
from typing import Literal
from pydantic import BaseModel, Field
import copy

FINGER_MAPPING = [
    [1, 1, 2, 3, 4, 4, 5, 5, 6, 7, 8, 8],
    [1, 1, 2, 3, 4, 4, 5, 5, 6, 7, 8, 8],
    [1, 1, 2, 3, 4, 4, 5, 5, 6, 7, 8, 8],
    [9, 9, 0, 0],
]


HAND_ROW_MAPPING = [
    ["tl", "tl", "tl", "tl", "tl", "tr", "tr", "tr", "tr", "tr", "tr", "tr"],
    ["ml", "ml", "ml", "ml", "ml", "mr", "mr", "mr", "mr", "mr", "mr", "mr"],
    ["bl", "bl", "bl", "bl", "bl", "br", "br", "br", "br", "br", "br", "br"],
    ["th", "th", "th", "th"],
]

BANNED_CHORDS = [
    # Index same row only
    [
        [0, 0, 0, 0, 1, 0],
        [0, 0, 0, 0, 0, 1],
        [0, 0, 0, 0, 0, 0],
        [0, 0],
    ],
    [
        [0, 0, 0, 0, 1, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1],
        [0, 0],
    ],
    [
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 0],
        [0, 0, 0, 0, 0, 1],
        [0, 0],
    ],
    [
        [0, 0, 0, 0, 0, 1],
        [0, 0, 0, 0, 1, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 0],
    ],
    [
        [0, 0, 0, 0, 0, 1],
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 0],
        [0, 0],
    ],
    [
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1],
        [0, 0, 0, 0, 1, 0],
        [0, 0],
    ],
    # Pinky same row only
    [
        [0, 1, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 0],
    ],
    [
        [0, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0],
        [0, 0],
    ],
    [
        [0, 0, 0, 0, 0, 0],
        [0, 1, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0],
        [0, 0],
    ],
    [
        [1, 0, 0, 0, 0, 0],
        [0, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 0],
    ],
    [
        [1, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 1, 0, 0, 0, 0],
        [0, 0],
    ],
    [
        [0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 0, 0],
        [0, 1, 0, 0, 0, 0],
        [0, 0],
    ],
    # Uncomfortable
    [
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1],
        [0, 0, 0, 1, 0, 0],
        [0, 0],
    ],
    [
        [0, 0, 1, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 1, 0, 0, 0, 0],
        [0, 0],
    ],
]

LAYOUTS = {
    "qwerty": [
        "_qwertyuiop_",
        "_asdfghjkl;_",
        "_zxcvbnm,./_",
        "____",
    ],
    "colemak": [
        "_qwfpgjluy;_",
        "_arstdhneio_",
        "_zxcvbkm,./_",
        "____",
    ],
    "colemak_dh": [
        "_qwfpbjluy;_",
        "_arstgmneio_",
        "_zxcdvkh,./_",
        "____",
    ],
    "canary": [
        "_wlypbzfou'_",
        "_crstgmneia_",
        "_qjvdkxh;,._",
        "____",
    ],
    "engram_2021": [
        "_byou'\"ldwvz",
        "_ciea,.htsnq",
        "_gxjk-?rmfp_",
        "____",
    ],
    "engram_en": [
        "_byou'\"dngvq",
        "_hiae,.trscz",
        "_kjxw-?mlfp_",
        "____",
    ],
    "enthium_v14": [
        "_qyou=xldpz_",
        "bciae-khtsnw",
        "_,,.;/jmgfv_",
        "__r_",
    ],
}


class StandardKeyboardOptions(BaseModel):
    layout: Literal[tuple(LAYOUTS.keys()) + ("custom",)] = "qwerty"
    scissor_penalty: int = Field(
        default=3,
        description="A penalty to add when pressing keys on the top and bottom rows together. Can be set to -1 to disable this type of chord.",
    )
    same_column_chord_penalty: int = Field(
        default=2,
        description="A penalty to add when pressing 2 keys and the same time with the same finger in the same column. Can be set to -1 to disable this type of chord.",
    )
    same_row_chord_penalty: int = Field(
        default=2,
        description="A penalty to add when pressing 2 keys and the same time with the same finger in the same row. Can be set to -1 to disable this type of chord.",
    )

    custom_layout: list[str] = [
        "_qwertyuiop_",
        "_asdfghjkl;_",
        "_zxcvbnm,./_",
        "____",
    ]

    custom_layout_name: str = Field(
        default="custom",
        description="Display name used for a custom layout in places like the drill score leaderboard. Only meaningful when layout='custom'.",
    )

    effort_map: list[str] = [
        "965446",
        "732116",
        "865536",
        "43",
    ]

    def create(self):
        return StandardKeyboard(self)


class StandardKeyboard:
    def __init__(self, options: StandardKeyboardOptions) -> None:
        if options.layout == "custom":
            self._layout = options.custom_layout
        else:
            self._layout = LAYOUTS[options.layout]

        # Break up into array of chars
        self._layout = [list(row) for row in self._layout]
        self._options = options

        effort = []
        for row in self._options.effort_map:
            r = []
            for c in row:
                if c.isnumeric():
                    r.append(int(c))
                else:
                    r.append(-1)
            # mirror
            r += r[::-1]
            effort.append(r)

        # self._finger_map = {}
        self._effort_map = {}
        self._hand_row_map = {}
        self._banned_chords_sets = []
        self._chord_map = copy.deepcopy(self._layout)
        self._chord_lookup = {}

        for r in range(0, len(self._layout)):
            for c in range(0, len(self._layout[r])):
                # self._finger_map[self._layout[r][c]] = FINGER_MAPPING[r][c]
                self._effort_map[self._layout[r][c]] = effort[r][c]
                self._hand_row_map[self._layout[r][c]] = HAND_ROW_MAPPING[r][c]
                self._chord_map[r][c] = 0
                self._chord_lookup[self._layout[r][c]] = (r, c)

        # Add mirrored chords and padding
        mirrored = []
        # banned chords, this left hand side is mirrored
        banned_chords = copy.deepcopy(BANNED_CHORDS)
        padding = [0, 0, 0, 0, 0, 0]
        for ban in banned_chords:
            mirror = []
            for r in range(0, len(ban)):
                mirror.append(padding + list(reversed(ban[r])))
                ban[r] += padding
            mirrored.append(mirror)
        banned_chords += mirrored

        for ban in banned_chords:
            s = set()
            for r in range(0, len(ban)):
                for c in range(0, len(ban[r])):
                    if ban[r][c]:
                        s.add(self._layout[r][c])
            self._banned_chords_sets.append(s)

    def get_scissor_count(self, chord):
        result = 0
        indexes = {
            "tl": 0,
            "ml": 0,
            "bl": 0,
            "tr": 0,
            "mr": 0,
            "br": 0,
            "th": 0,
        }
        for i in range(0, len(chord)):
            indexes[self._hand_row_map[chord[i]]] += 1

        if indexes["tl"] and indexes["bl"]:
            result += min(indexes["tl"], indexes["bl"])

        if indexes["tr"] and indexes["br"]:
            result += min(indexes["tr"], indexes["br"])

        return result

    def get_chord_map(self, chord: str):
        map = copy.deepcopy(self._chord_map)
        for c in chord:
            offset = self._chord_lookup[c]
            map[offset[0]][offset[1]] = 1
        return map

    def get_same_column_chord(self, chord_map) -> int:
        count = 0
        for i in range(0, len(chord_map[0])):
            if chord_map[0][i] and chord_map[1][i]:
                if self._options.same_column_chord_penalty == -1:
                    return -1

                count += 1

            # Top and bottom row on same finger is excluded
            if chord_map[0][i] and chord_map[2][i]:
                return -1

        return count

    def get_same_row_chord(self, chord_map) -> int:
        count = 0
        for r in range(0, len(chord_map)):
            for c in range(0, len(chord_map[r]) - 1):
                if (
                    chord_map[r][c]
                    and chord_map[r][c + 1]
                    and FINGER_MAPPING[r][c] == FINGER_MAPPING[r][c + 1]
                ):
                    if self._options.same_row_chord_penalty == -1:
                        return -1
                    count += 1

        return count

    def score(self, chord: str) -> int:
        for i in range(0, len(chord)):
            if chord[i] not in self._effort_map:
                logging.debug(f"rejected: letter '{chord[i]}' not in keyboard layout")
                return -1

        seen = set()
        for char in chord:
            if char in seen:
                logging.debug("rejected: duplicate letters")
                return -1
            seen.add(char)

        for ban in self._banned_chords_sets:
            if ban.issubset(seen):
                logging.debug("rejected: banned chord")
                return -1

        chord_map = self.get_chord_map(chord)
        result = 0
        same_column_chord = self.get_same_column_chord(chord_map)
        if same_column_chord == -1:
            logging.debug("rejected: same column chord")
            return -1

        result += same_column_chord * self._options.same_column_chord_penalty

        same_row_chord = self.get_same_row_chord(chord_map)
        if same_row_chord == -1:
            logging.debug("rejected: same column chord")
            return -1

        result += same_row_chord * self._options.same_row_chord_penalty

        scissor_count = self.get_scissor_count(chord)
        if scissor_count:
            if self._options.scissor_penalty == -1:
                logging.debug("rejected: scissor")
                return -1
            result += self._options.scissor_penalty * scissor_count

        for i in range(0, len(chord)):
            result += self._effort_map[chord[i]]

        return result
