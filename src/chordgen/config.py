from pathlib import Path
from typing import Literal
import yaml

from chordgen.constants import CONFIG_DIR
from chordgen.keyboards.directional import DirectionalKeyboardOptions
from chordgen.keyboards.standard import StandardKeyboardOptions
from chordgen.keyboards import Keyboard
from chordgen.output.charachorder import CharaChorderOutput
from chordgen.output.kanata import KanataOutput
from chordgen.output.qmk import QmkOutput
from chordgen.output.training import TrainingOutput
from chordgen.output.zmk import ZmkOutput
from pydantic import BaseModel, field_validator, Field
from chordgen.pydantic import File

DEFAULT_CONFIG = CONFIG_DIR / "config.yaml"
DEFAULT_CHORDS_FILE = CONFIG_DIR / "chords.csv"


class LearnOptions(BaseModel):
    show_words: int = Field(
        default=10,
        description="Number of words shown on screen at once during learning.",
    )
    new_words_per_day: int = Field(
        default=20,
        description=(
            "Maximum number of brand-new words introduced per "
            "calendar day, inspired by Anki's 'new cards per day' "
            "setting. Once the day's quota is exhausted no more new "
            "words are added until tomorrow."
        ),
    )
    reviews_per_day: int = Field(
        default=200,
        description=(
            "Maximum number of overdue / re-drilled review words "
            "surfaced per calendar day. Prevents a long absence from "
            "dumping the entire backlog at once."
        ),
    )
    leech_threshold: int = Field(
        default=8,
        description=(
            "Number of lapses (Again ratings on a graduated word) "
            "after which a word is considered a 'leech' and called "
            "out in the session summary. Set to 0 to disable leech "
            "detection."
        ),
    )
    mastery_threshold: int = Field(
        default=3,
        description=(
            "Number of total FSRS reviews before a word is considered "
            "mastered and its chord is hidden during practice. If you "
            "make a mistake on a mastered word, its chord is revealed "
            "again for that attempt."
        ),
    )
    learning_steps: int = Field(
        default=5,
        description=(
            "Number of consecutive correct repetitions a brand-new "
            "word must earn in one session before it graduates to "
            "Review state. Each error resets the step counter to "
            "zero so the word starts over."
        ),
    )
    show_chord_steps: int = Field(
        default=3,
        description=(
            "How many of the initial learning steps show the chord "
            "during the learning phase. After this many consecutive "
            "correct reps the chord is hidden for the remaining "
            "learning steps. An error resets the counter and the "
            "chord reappears."
        ),
    )
    relearn_steps: int = Field(
        default=2,
        description=(
            "Number of consecutive correct repetitions a lapsed "
            "word must earn before re-graduating to Review state. "
            "Each error resets the step counter to zero so the "
            "word starts over."
        ),
    )
    target_retention: float = Field(
        default=0.9,
        description=(
            "FSRS desired retention probability. The next review for "
            "each word is scheduled when its predicted recall falls "
            "to this value."
        ),
    )
    slow_wpm_fraction: float = Field(
        default=0.7,
        description=(
            "A correct word counts as 'slow' (FSRS hard) when its "
            "per-word WPM is below this fraction of the user's "
            "rolling median per-word WPM. Set to 0 to disable slow "
            "grading."
        ),
    )
    slow_min_samples: int = Field(
        default=20,
        description=(
            "Minimum number of recorded per-word WPM samples before "
            "slow grading activates. Until this is reached all "
            "correct words are graded 'good'."
        ),
    )


class DrillOptions(BaseModel):
    show_words: int = Field(
        default=10,
        description="Number of words shown on screen at once during a drill.",
    )
    mode: Literal["count", "time"] = Field(
        default="time",
        description=(
            "How a drill session ends: 'count' stops after a fixed "
            "number of words, 'time' stops when the timer runs out."
        ),
    )
    count: int = Field(
        default=25,
        description=(
            "Number of words drilled when ``mode = count``. "
            "Ignored when ``mode = time``."
        ),
    )
    time_seconds: int = Field(
        default=30,
        description=(
            "Duration of the drill in seconds when ``mode = time``. "
            "Ignored when ``mode = count``."
        ),
    )
    include_alts: bool = Field(
        default=True,
        description=(
            "When true, alt-slot inflections (alt1/alt2/alt3 columns "
            "of chords.csv) ride along into the drill pool whenever "
            "their base word is graduated. The chord shown after a "
            "stumble is suffixed with the slot digit (e.g. ``au1``) "
            "and the alt-slot indicator below the keyboard "
            "highlights the matching modifier. Set to false to drill "
            "only the base word from each chord row."
        ),
    )
    always_show_chords: bool = Field(
        default=False,
        description=(
            "When true, chords are revealed below every word in the "
            "drill row, not just on a stumble. Useful while you're "
            "still building muscle memory; turn off (default) once "
            "you want drill mode to test recall."
        ),
    )


class BookOptions(BaseModel):
    wpm_window_seconds: int = Field(
        default=30,
        description=(
            "Sliding window (in seconds) over which the running WPM "
            "is computed in book mode."
        ),
    )
    max_width: int = Field(
        default=80,
        description=(
            "Maximum width (in characters) of the rendered text "
            "block in book mode. Long paragraphs are wrapped to this "
            "width."
        ),
    )
    always_show_chords: bool = Field(
        default=False,
        description=(
            "When true, the chord for the current word is rendered "
            "beneath it the moment the cursor lands on it, instead "
            "of only after a stumble. Mirrors the drill option of "
            "the same name."
        ),
    )


class OutputOptions(BaseModel):
    formats: list[
        Literal[
            "qmk",
            "zmk",
            "charachorder",
            "kanata",
            "training",
        ]
    ] = [
        "qmk",
        "zmk",
        "charachorder",
        "kanata",
        "training",
    ]
    qmk: QmkOutput = QmkOutput()
    zmk: ZmkOutput = ZmkOutput()
    charachorder: CharaChorderOutput = CharaChorderOutput()
    kanata: KanataOutput = KanataOutput()
    training: TrainingOutput = TrainingOutput()


class KeyboardOptions(BaseModel):
    type: Literal["standard", "directional"] = "standard"
    standard: StandardKeyboardOptions = StandardKeyboardOptions()
    directional: DirectionalKeyboardOptions = DirectionalKeyboardOptions()

    _keyboard: Keyboard | None = None

    def get_keyboard(self):
        if not self._keyboard:
            self._keyboard = getattr(self, self.type).create()
        return self._keyboard


# Inflectional forms accepted per alt category. Each list slot maps to
# alt1/alt2/alt3 in chords.csv (so order matters and length <= 3).
VerbForm = Literal[
    "3sg",       # he/she/it walks
    "past",      # walked
    "gerund",    # walking (present participle)
    "ppart",     # walked / been (past participle)
]
NounForm = Literal["plural", "singular"]
AdjectiveForm = Literal["comparative", "superlative"]
AdverbForm = Literal["comparative", "superlative"]
PronounForm = Literal[
    "nominative",      # I, you, he, she, it, we, they
    "objective",       # me, you, him, her, it, us, them
    "possessive_det",  # my, your, his, her, its, our, their
    "possessive_pron", # mine, yours, his, hers, its, ours, theirs
    "reflexive",       # myself, yourself, himself, ...
]
DemonstrativeForm = Literal[
    "singular",   # this, that
    "plural",     # these, those
    "proximal",   # this, these
    "distal",     # that, those
]
ModalForm = Literal[
    "present",    # can, will, shall, may, must
    "past",       # could, would, should, might
]
NumberForm = Literal[
    "cardinal",   # one, two, three, ...
    "ordinal",    # first, second, third, ...
]


class _AltCategoryOptions(BaseModel):
    enabled: bool = True


class VerbAltOptions(_AltCategoryOptions):
    forms: list[VerbForm] = Field(
        default=["3sg", "past", "gerund"],
        max_length=3,
        description="Verb forms to fill alt1..alt3 with, in order.",
    )


class NounAltOptions(_AltCategoryOptions):
    forms: list[NounForm] = Field(
        default=["plural"],
        max_length=3,
        description="Noun forms to fill alt1..alt3 with, in order.",
    )


class AdjectiveAltOptions(_AltCategoryOptions):
    forms: list[AdjectiveForm] = Field(
        default=["comparative", "superlative"],
        max_length=3,
        description="Adjective forms to fill alt1..alt3 with, in order.",
    )


class AdverbAltOptions(_AltCategoryOptions):
    # No reliable adverb inflector in pattern.en; forms is empty by
    # default so enabling this category is a no-op until an inflector
    # is registered.
    forms: list[AdverbForm] = Field(
        default=[],
        max_length=3,
        description="Adverb forms to fill alt1..alt3 with, in order.",
    )


class PronounAltOptions(_AltCategoryOptions):
    forms: list[PronounForm] = Field(
        default=["objective", "possessive_det", "reflexive"],
        max_length=3,
        description="Pronoun forms to fill alt1..alt3 with, in order.",
    )


class DemonstrativeAltOptions(_AltCategoryOptions):
    forms: list[DemonstrativeForm] = Field(
        default=["plural", "distal"],
        max_length=3,
        description=(
            "Demonstrative forms to fill alt1..alt3 with, in order. "
            "Demonstratives are ``this``, ``that``, ``these``, and "
            "``those`` arranged on number (singular/plural) and "
            "distance (proximal/distal) axes."
        ),
    )


class ModalAltOptions(_AltCategoryOptions):
    forms: list[ModalForm] = Field(
        default=["past"],
        max_length=3,
        description=(
            "Modal-verb forms to fill alt1..alt3 with, in order. "
            "Modals are paired present <-> past: can/could, will/"
            "would, shall/should, may/might. ``must`` has no past "
            "form."
        ),
    )


class NumberAltOptions(_AltCategoryOptions):
    forms: list[NumberForm] = Field(
        default=["ordinal"],
        max_length=3,
        description=(
            "Number forms to fill alt1..alt3 with, in order. Numbers "
            "are cardinal/ordinal pairs (one/first, two/second, ...)."
        ),
    )


class AltOptions(BaseModel):
    overwrite: bool = Field(
        default=False,
        description="Overwrite existing alt1/alt2/alt3 values in chords.csv. By default, non-empty alt slots are preserved.",
    )
    verb: VerbAltOptions = VerbAltOptions()
    noun: NounAltOptions = NounAltOptions()
    adjective: AdjectiveAltOptions = AdjectiveAltOptions()
    adverb: AdverbAltOptions = AdverbAltOptions()
    pronoun: PronounAltOptions = PronounAltOptions()
    demonstrative: DemonstrativeAltOptions = DemonstrativeAltOptions()
    modal: ModalAltOptions = ModalAltOptions()
    number: NumberAltOptions = NumberAltOptions()


class AssignmentOptions(BaseModel):
    min_frequency_weight: float = Field(
        default=1.0,
        description=(
            "Floor for the weight applied to words missing a frequency value. "
            "Treats them as low-priority but still eligible."
        ),
    )
    unmatched_penalty: float = Field(
        default=10000.0,
        description=(
            "Cost charged per word that ends up without a chord. Acts as a "
            "soft constraint in the optimal matcher: if recovering a word "
            "would cost more than this, leaving it unmatched is allowed."
        ),
    )
    frequency_exponent: float = Field(
        default=3.0,
        description=(
            "Exponent applied to each word's frequency weight before it "
            "multiplies the chord score. 1.0 gives a linear cost model. "
            "Values > 1 (like the default 3.0) make frequent words "
            "dominate the cost so the matcher won't trade a "
            "common word's short chord to a rare word that happens to "
            "improve the global sum slightly. Must be > 0."
        ),
    )
    priority_tiers: list[int] = Field(
        default=[],
        description=(
            "Cumulative frequency-rank cutoffs for tiered assignment. The "
            "pool (already in descending-frequency order) is split at each "
            "cutoff, then each tier is solved by the optimal matcher in "
            "order, with previous tiers' chord keys reserved out. Default "
            "[] runs a single global pass. Example [500, 1000] runs three "
            "passes: top 500 -> next 500 -> rest. Cutoffs must be strictly "
            "increasing; values >= len(pool) are clamped."
        ),
    )

    @field_validator("priority_tiers", mode="after")
    @classmethod
    def _validate_tiers(cls, v: list[int]) -> list[int]:
        for n in v:
            if n <= 0:
                raise ValueError("priority_tiers entries must be > 0")
        if any(b <= a for a, b in zip(v, v[1:])):
            raise ValueError("priority_tiers must be strictly increasing")
        return v

    @field_validator("frequency_exponent", mode="after")
    @classmethod
    def _validate_frequency_exponent(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("frequency_exponent must be > 0")
        return v


class GenOptions(BaseModel):
    file: File = DEFAULT_CHORDS_FILE
    keyboard: KeyboardOptions = KeyboardOptions()
    alts: AltOptions = AltOptions()
    assignment: AssignmentOptions = AssignmentOptions()
    min_word_length: int = 3
    min_chord_length: int = Field(
        default=0,
        description="The minimum length a chord, setting this to 2 and disabling the chord key is a way to avoid needing a chord key. This works well on CharaChorder, but you will need to lower the chord timeout to avoid missfires on other keyboards.",
    )
    ignore_words: list[str] = Field(
        default=[],
        description=(
            "Words to ignore during ``chordgen gen``. Ignored words stay "
            "in chords.csv but are skipped when scoring and assigning "
            "chords, so they won't produce 'unable to find options' "
            "warnings and won't consume chord keys. Useful for low-value "
            "short words (fillers, interjections, dialect forms). Matching "
            "is case-insensitive."
        ),
    )
    key_replacement: dict[str, str] = Field(
        default={},
        description=(
            "Map characters to replacements when generating chord "
            "candidates. For example, if your keyboard lacks 'q' and "
            "'z', set {'q': 'k', 'z': 's'} so chords use 'k' instead "
            "of 'q' and 's' instead of 'z' -- the typed word is "
            "unaffected, only the chord string changes. Useful for "
            "remapping non-letter characters too: \"'\": x lets a "
            "word like \"o'clock\" earn a chord that contains 'x' "
            "wherever the apostrophe sits. Each key must be a single "
            "lowercase character; its replacement must be a single "
            "lowercase letter that exists on your keyboard."
        ),
    )
    debug: bool = Field(
        default=False,
        description=(
            "When true, gen writes a `debug` column to chords.csv "
            "containing per-row assignment diagnostics (assignment "
            "weight, chosen option score, and the top alternative "
            "candidates considered). Useful for understanding why a "
            "particular chord was assigned to a word. Default false."
        ),
    )

    @field_validator("file", mode="after")
    @classmethod
    def ensure_parent_dir(cls, v: Path):
        v.parent.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("key_replacement", mode="after")
    @classmethod
    def validate_key_replacement(cls, v: dict[str, str]) -> dict[str, str]:
        for key, replacement in v.items():
            # Source side accepts any single non-whitespace character
            # so users can remap punctuation like "'" to a real key.
            # Uppercase letters are still rejected because chord
            # candidates are generated from the lowercased word.
            if len(key) != 1 or key.isspace() or key != key.lower():
                raise ValueError(
                    f"key_replacement key {key!r} must be a single "
                    f"lowercase non-whitespace character"
                )
            if (
                len(replacement) != 1
                or not replacement.isalpha()
                or not replacement.islower()
            ):
                raise ValueError(
                    f"key_replacement value {replacement!r} for "
                    f"{key!r} must be a single lowercase letter"
                )
        return v


class Config(BaseModel):
    gen: GenOptions = GenOptions()
    output: OutputOptions = OutputOptions()
    learn: LearnOptions = LearnOptions()
    drill: DrillOptions = DrillOptions()
    book: BookOptions = BookOptions()
    theme: str = Field(
        default="textual-dark",
        description=(
            "Textual theme used by the learn and drill TUIs. Updated "
            "automatically when you change the theme via the in-app "
            "command palette (Ctrl+P)."
        ),
    )


def save_config(config: "Config", config_file: Path = DEFAULT_CONFIG) -> None:
    """Persist ``config`` back to ``config_file``."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(yaml.safe_dump(config.model_dump()))


def load_or_create_config(config_file: Path = DEFAULT_CONFIG) -> Config:
    if config_file != DEFAULT_CONFIG and not config_file.exists():
        raise Exception(f"Config file does not exist: {config_file}")

    config_file.parent.mkdir(parents=True, exist_ok=True)

    if config_file.exists():
        raw = yaml.safe_load(config_file.read_text()) or {}
        # Migrate old `train` config key to `learn`.
        if "train" in raw and "learn" not in raw:
            raw["learn"] = raw.pop("train")
            print(
                f"Note: migrated 'train' config key to 'learn' in "
                f"{config_file}; re-check any hand-edits."
            )
    else:
        print(f"Creating config {config_file}")
        raw = {}
        # write defaults immediately
        default_config = Config()
        config_file.write_text(yaml.safe_dump(default_config.model_dump()))
        return default_config

    # Validate + apply defaults
    config = Config.model_validate(raw)

    # Optionally rewrite file if missing fields were added
    config_file.write_text(yaml.safe_dump(config.model_dump()))

    return config
