import logging
from typing import Literal
from pydantic import BaseModel, Field
import copy

FINGER_MAPPING = [
    [0, 1, 0, 0, 2, 0, 0, 3, 0, 0, 4, 0],
    [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4],
    [0, 1, 0, 0, 2, 0, 0, 3, 0, 0, 4, 0],
    [0, 5, 0],
    [5, 5, 5],
    [0, 5, 0],
    [0, 5, 0],
    [5, 5, 5],
    [0, 5, 0],
]


DIRECTION_MAPPING = [
    ["_", "u", "_", "_", "u", "_", "_", "u", "_", "_", "u", "_"],
    ["o", "c", "i", "o", "c", "i", "o", "c", "i", "o", "c", "i"],
    ["_", "d", "_", "_", "d", "_", "_", "d", "_", "_", "d", "_"],
    ["_", "u", "_"],
    ["o", "c", "i"],
    ["_", "d", "_"],
    ["_", "u", "_"],
    ["o", "c", "i"],
    ["_", "d", "_"],
]

LAYOUTS = {
    "charachorder": [
        "________________________",
        "___,_'._i__ra__l_jy_;___",
        "____u__o__e__t__n__s____",
        "_v__p_",
        "m_kf_h",
        "_c__d_",
        "____x_",
        "g_wb__",
        "_z__q_",
    ],
    "stained": [
        "_q__f__w__o__l__u__b__z_",
        "\\_'x_ky_hm_ci_gr_vp_j;_/",
        "____s__t__a__n__e__d__._",
        "______",
        "______",
        "______",
        "______",
        "______",
        "______",
    ],
    "svalboard_qwerty": [
        "_q__w__e__r__u__i__o__p_",
        "_a[_sb`dt\"fghj'yk:nl_];\\",
        "_z__x__c__v__m__,__.__/_",
        "______",
        "______",
        "______",
        "______",
        "______",
        "______",
    ],
}


class DirectionalKeyboardOptions(BaseModel):
    layout: Literal[tuple(LAYOUTS.keys()) + ("custom",)] = "charachorder"
    directional_change_penalty: int = Field(
        default=2,
        description="A penalty to add when chords have different directions per finger on the same hand. Can be set to -1 to disable this type of chord.",
    )

    custom_layout: list[str] = [
        "_X__X__X__X__X__X__X__X_",
        "X_XX_XX_XX_XX_XX_XX_XX_X",
        "_X__X__X__X__X__X__X__X_",
        "_X__X_",
        "X_XX_X",
        "_X__X_",
        "_X__X_",
        "X_XX_X",
        "_X__X_",
    ]

    effort_map: list[str] = [
        "040030020020",
        "695594493493",
        "030020010010",
        "030",
        "192",
        "040",
        "030",
        "192",
        "040",
    ]

    def create(self):
        return DirectionalKeyboard(self)


class DirectionalKeyboard:
    def __init__(self, options: DirectionalKeyboardOptions) -> None:
        if options.layout == "custom":
            self._layout = options.custom_layout
        else:
            self._layout = LAYOUTS[options.layout]

        # Break up into array of chars
        self._layout = [list(row) for row in self._layout]
        self._options = options

        # mirror maps
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

        copy.deepcopy(self._options.effort_map)
        for row in effort:
            row += row[::-1]

        direction = copy.deepcopy(DIRECTION_MAPPING)
        for row in direction:
            row += row[::-1]

        finger = copy.deepcopy(FINGER_MAPPING)
        for row in finger:
            reversed = [x + 5 if x > 0 else 0 for x in row[::-1]]
            row += reversed

        hand = copy.deepcopy(FINGER_MAPPING)
        for row in hand:
            row[:] = [0] * len(row)
            right = [1] * len(row)
            row += right

        self._effort_map = {}
        self._direction_map = {}
        self._finger_map = {}
        self._hand_map = {}

        for r in range(0, len(self._layout)):
            for c in range(0, len(self._layout[r])):
                self._effort_map[self._layout[r][c]] = effort[r][c]
                self._direction_map[self._layout[r][c]] = direction[r][c]
                self._finger_map[self._layout[r][c]] = finger[r][c]
                self._hand_map[self._layout[r][c]] = hand[r][c]

    def get_directional_changes(self, chord):
        result = 0
        directions = {0: set(), 1: set()}
        for c in chord:
            directions[self._hand_map[c]].add(self._direction_map[c])

        changes = 0
        for _, hand in directions.items():
            if len(hand) > 1:
                changes += len(hand) - 1

        return result

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

        seen = set()
        for char in chord:
            finger = self._finger_map[char]
            if finger in seen:
                logging.debug("rejected: same finger used more than once")
                return -1
            seen.add(finger)

        result = 0

        if self._options.directional_change_penalty != -1:
            changes = self.get_directional_changes(chord)
            result += changes * self._options.directional_change_penalty

        for i in range(0, len(chord)):
            result += self._effort_map[chord[i]]

        return result
