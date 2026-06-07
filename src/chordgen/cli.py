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
from chordgen.learn import LearnApp
from chordgen.drill import DrillApp
from chordgen.book import BookApp
from chordgen.keyboard_view import resolve_keyboard_layout, resolve_layout_key



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
    md = _yamlify_defaults(md)

    with open("docs/schema.md", "w") as f:
        f.write(md)


def _yamlify_defaults(md: str) -> str:
    """Render ``Default: `{...}` `` blobs as YAML code fences when the value
    is a non-trivial object (dict, or list of dicts). Scalars and simple
    arrays are left inline so the schema stays scannable."""
    import json

    import yaml

    def replace(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        raw = match.group("value")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return match.group(0)

        if not _is_complex_default(value):
            return match.group(0)

        block = yaml.safe_dump(
            value,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        ).rstrip()
        indent = re.match(r"[ \t]*", prefix).group(0)
        body_indent = indent + "  "
        body = "\n".join(body_indent + line for line in block.splitlines())
        return f"{prefix}Default:\n\n{body_indent}```yaml\n{body}\n{body_indent}```\n"

    # Match lines ending in `Default: \`<json>\`.` — the trailing period and
    # backticks are emitted by jsonschema2md.
    pattern = re.compile(
        r"(?P<prefix>^[ \t]*[-*] .*?)Default: `(?P<value>[^`\n]+)`\.\s*$",
        flags=re.MULTILINE,
    )
    return pattern.sub(replace, md)


def _is_complex_default(value: object) -> bool:
    if isinstance(value, dict) and value:
        return True
    if isinstance(value, list) and value and any(isinstance(item, (dict, list)) for item in value):
        return True
    return False


@app.command()
def learn():
    """Practice chording with a TUI."""
    chords = load_file(State.config.gen.file)
    resolved = resolve_keyboard_layout(State.config)
    keyboard_kind, keyboard_layout = resolved if resolved else ("standard", None)
    app = LearnApp(
        chords,
        State.config.learn,
        keyboard_layout=keyboard_layout,
        keyboard_kind=keyboard_kind,
        initial_theme=State.config.theme,
        on_theme_change=_persist_theme,
    )
    app.run()


@app.command()
def drill(
    words: list[str] = typer.Argument(
        None,
        help=(
            "Optional words to drill on instead of the graduated "
            "FSRS pool. Words without a chord in chords.csv are "
            "silently dropped."
        ),
    ),
    words_file: Path = typer.Option(
        None,
        "--words-file",
        "-f",
        help=(
            "Path to a file containing words to drill on (whitespace-"
            "separated). Combined with any positional WORDS arguments. "
            "Words without a chord in chords.csv are silently dropped."
        ),
    ),
):
    """Speed-drill on graduated words (no FSRS state changes).

    By default the word pool is restricted to words whose FSRS card
    has graduated to Review state. If WORDS or --words-file is given,
    drill on those words instead.
    """
    chords = load_file(State.config.gen.file)
    resolved = resolve_keyboard_layout(State.config)
    keyboard_kind, keyboard_layout = resolved if resolved else ("standard", None)

    custom_words: list[str] | None = None
    collected: list[str] = list(words) if words else []
    if words_file is not None:
        if not words_file.exists():
            print(f"Error: words file {words_file} does not exist")
            raise typer.Abort()
        collected.extend(words_file.read_text().split())
    if collected:
        custom_words = collected

    app = DrillApp(
        chords,
        State.config.drill,
        keyboard_layout=keyboard_layout,
        keyboard_kind=keyboard_kind,
        layout_key=resolve_layout_key(State.config),
        initial_theme=State.config.theme,
        on_theme_change=_persist_theme,
        custom_words=custom_words,
    )
    app.run()


@app.command()
def book(
    path: Path = typer.Argument(
        ..., help="Path to a book file (.txt, .md, or .epub) to type through."
    ),
    restart: bool = typer.Option(
        False,
        "--restart",
        help="Reset the saved cursor for this book and start from the beginning.",
    ),
):
    """Type through an arbitrary book.

    Renders a book's text in a TUI with the user's keyboard pinned
    to the bottom. Words for which the user has already learned a
    chord (FSRS Review state) are highlighted; mistyping a learned
    word reveals its chord on the keyboard. The cursor position is
    auto-saved so you can resume next time.
    """
    chords = load_file(State.config.gen.file)
    resolved = resolve_keyboard_layout(State.config)
    keyboard_kind, keyboard_layout = resolved if resolved else ("standard", None)
    if not path.exists():
        print(f"Error: book file {path} does not exist")
        raise typer.Abort()

    app = BookApp(
        chords=chords,
        config=State.config.book,
        path=path,
        restart=restart,
        keyboard_layout=keyboard_layout,
        keyboard_kind=keyboard_kind,
        initial_theme=State.config.theme,
        on_theme_change=_persist_theme,
    )
    app.run()


if __name__ == "__main__":
    app()
