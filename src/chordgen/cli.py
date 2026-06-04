import logging
import re
from pathlib import Path

import jsonschema2md
import typer

from chordgen.chord import load_file, validate_chords
from chordgen.config import (
    DEFAULT_CONFIG,
    Config,
    load_or_create_config,
    save_config,
)
from chordgen.constants import CONFIG_DIR
from chordgen.gen import gen as run_gen
from chordgen.vocab import SOURCES
from chordgen.vocab.pipeline import build_chords_csv
from chordgen.train import TrainApp
from chordgen.drill import DrillApp
from chordgen.keyboard_view import resolve_keyboard_layout



app = typer.Typer()


class State:
    config: Config
    config_path: Path


@app.callback()
def callback(
    ctx: typer.Context,
    config: Path = typer.Option(
        DEFAULT_CONFIG, "-c", "--config", help="Path to config file"
    ),
):
    logging.basicConfig(level="INFO")
    if ctx.invoked_subcommand != "setup":
        if not config.exists():
            print(
                f"Error: config {config} does not exist, run 'chordgen setup' to create it"
            )
            raise typer.Abort()

    loaded_config = load_or_create_config(config)
    if ctx.invoked_subcommand != "setup":
        if not loaded_config.gen.file.exists():
            print(
                f"Error: chord file {loaded_config.gen.file} does not exist, run 'chordgen setup' to create it"
            )
            raise typer.Abort()

    State.config = loaded_config
    State.config_path = config


def _persist_theme(theme: str) -> None:
    """Persist the user's currently-selected Textual theme back to
    ``config.yaml`` so it sticks across runs."""
    if State.config.theme == theme:
        return
    State.config.theme = theme
    save_config(State.config, State.config_path)


@app.command()
def setup(
    source: str = typer.Option(
        "subtlex-us",
        "--source",
        help=f"Vocabulary source. One of: {', '.join(sorted(SOURCES))}.",
    ),
    size: int = typer.Option(
        2000, "--size", help="Number of words to include in chords.csv."
    ),
    min_frequency: float = typer.Option(
        3.0,
        "--min-frequency",
        help=(
            "Filter words below this source-defined frequency. For SUBTLEX "
            "sources this is a Zipf value; 3.0 ~ 1 occurrence per million "
            "words. Lower includes rarer vocabulary."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing chords.csv. By default setup keeps it.",
    ),
):
    """Initialise config and chords.csv.

    chords.csv is generated from a frequency-ranked source (SUBTLEX by
    default). After setup, chords.csv is yours to edit by hand; running
    setup again without --force will not touch it.
    """
    chords_file = State.config.gen.file
    if chords_file.exists() and not force:
        print(
            f"chords.csv already exists at {chords_file}. "
            "Use --force to regenerate."
        )
        raise typer.Exit()

    if source not in SOURCES:
        print(
            f"Unknown source '{source}'. Available: {', '.join(sorted(SOURCES))}"
        )
        raise typer.Abort()

    cache_dir = CONFIG_DIR / "cache"
    build_chords_csv(
        source_name=source,
        output_file=chords_file,
        cache_dir=cache_dir,
        size=size,
        min_frequency=min_frequency,
    )

    print("Setup Complete")


@app.command()
def gen():
    run_gen(State.config.gen)


@app.command()
def output():
    chords = load_file(State.config.gen.file)
    validate_chords(chords)

    for format in State.config.output.formats:
        print(f"Running output format '{format}'")
        format = getattr(State.config.output, format)
        format.output(chords)


@app.command()
def schema():
    parser = jsonschema2md.Parser()
    md = "".join(parser.parse_schema(Config.model_json_schema()))
    pattern = r"/(?:Users|home)/[^/]+/"
    md = re.sub(pattern, "~/", md)

    with open("docs/schema.md", "w") as f:
        f.write(md)


@app.command()
def train():
    """Practice chording with a TUI."""
    chords = load_file(State.config.gen.file)
    resolved = resolve_keyboard_layout(State.config)
    keyboard_kind, keyboard_layout = resolved if resolved else ("standard", None)
    app = TrainApp(
        chords,
        State.config.train,
        keyboard_layout=keyboard_layout,
        keyboard_kind=keyboard_kind,
        initial_theme=State.config.theme,
        on_theme_change=_persist_theme,
    )
    app.run()


@app.command()
def drill():
    """Speed-drill on graduated words (no FSRS state changes)."""
    chords = load_file(State.config.gen.file)
    resolved = resolve_keyboard_layout(State.config)
    keyboard_kind, keyboard_layout = resolved if resolved else ("standard", None)
    app = DrillApp(
        chords,
        State.config.drill,
        keyboard_layout=keyboard_layout,
        keyboard_kind=keyboard_kind,
        initial_theme=State.config.theme,
        on_theme_change=_persist_theme,
    )
    app.run()


if __name__ == "__main__":
    app()
