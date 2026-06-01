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


class AltOptions(BaseModel):
    overwrite: bool = Field(
        default=False,
        description="Overwrite existing alt1/alt2/alt3 values in chords.csv. By default, non-empty alt slots are preserved.",
    )
    verb: VerbAltOptions = VerbAltOptions()
    noun: NounAltOptions = NounAltOptions()
    adjective: AdjectiveAltOptions = AdjectiveAltOptions()
    adverb: AdverbAltOptions = AdverbAltOptions()


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


class GenOptions(BaseModel):
    file: File = DEFAULT_CHORDS_FILE
    keyboard: KeyboardOptions = KeyboardOptions()
    alts: AltOptions = AltOptions()
    assignment: AssignmentOptions = AssignmentOptions()
    min_word_length: int = 3
    min_chord_length: int = Field(
        default=0,
        description="The minimum lenth a chord, setting this to 2 and disabling the chord key is a way to avoid needing a chord key. This works well on CharaChorder, but you will need to lower the chord timeout to avoid missfires on other keyboards.",
    )

    @field_validator("file", mode="after")
    @classmethod
    def ensure_parent_dir(cls, v: Path):
        v.parent.mkdir(parents=True, exist_ok=True)
        return v


class Config(BaseModel):
    gen: GenOptions = GenOptions()
    output: OutputOptions = OutputOptions()


def load_or_create_config(config_file: Path = DEFAULT_CONFIG) -> Config:
    if config_file != DEFAULT_CONFIG and not config_file.exists():
        raise Exception(f"Config file does not exist: {config_file}")

    config_file.parent.mkdir(parents=True, exist_ok=True)

    if config_file.exists():
        raw = yaml.safe_load(config_file.read_text()) or {}
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
