from pathlib import Path
from typing import Literal
import yaml
import shutil

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


class GenOptions(BaseModel):
    file: File = DEFAULT_CHORDS_FILE
    keyboard: KeyboardOptions = KeyboardOptions()
    overwrite_alts: bool = False
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

    @field_validator("file", mode="after")
    @classmethod
    def create_file(cls, v: Path):
        if not v.exists():
            here = Path(__file__).resolve().parent
            source = here / "assets" / "chords.csv"
            shutil.copyfile(source, v)
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
