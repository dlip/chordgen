import os

# Avoid Textual's pixel-mouse resize path, which can divide by zero when a
# terminal briefly reports a zero pixel size. Users may explicitly override it.
os.environ.setdefault("TEXTUAL_SMOOTH_SCROLL", "0")

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
from chordgen.gen import generate, write_chords
from chordgen.srs import load_progress, save_progress
from chordgen.vocab import SOURCES
from chordgen.vocab.pipeline import build_chords_csv
from chordgen.add import add_words
from chordgen.learn import LearnApp
from chordgen.drill import DrillApp
from chordgen.book import BookApp
from chordgen.keyboard_view import resolve_keyboard_layout, resolve_layout_key



app = typer.Typer(no_args_is_help=True)


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
    if ctx.invoked_subcommand in {"check", "difficult"}:
        State.config_path = config
        return
    if ctx.invoked_subcommand != "setup":
        if not config.exists():
            print(
                f"Error: config {config} does not exist, run 'chordgen setup' to create it"
            )
            raise typer.Abort()

    loaded_config = load_or_create_config(
        config, write_back=ctx.invoked_subcommand not in {"gen", "analyze"},
    )
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
    """Download vocabulary and create chords.csv.

    Fetches a frequency-ranked word list (SUBTLEX-US by default),
    scores every viable chord per word, and writes the initial
    chords.csv. After setup you own the file — edit by hand, re-run
    gen to refresh assignments, or run setup --force to start over.
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
def gen(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing chords or progress."),
    preserve_learned: bool = typer.Option(False, "--preserve-learned", help="Reserve learned mappings and their family slots for this run."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept changes to learned mappings without prompting."),
):
    """Score, generate alts, and assign chords to every word.

    Picks the optimal chord per word using a sparse minimum-weight
    bipartite matcher, fills alt1/alt2/alt3 via the category/inflector
    registry, and writes the result back to chords.csv.
    """
    progress = load_progress()
    try:
        result = generate(State.config.gen, progress=progress, preserve_learned=preserve_learned)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for change in result.changes:
        typer.echo(change)
    if result.learned_changes:
        typer.echo("Learned mappings changing: " + ", ".join(result.learned_changes))
    if dry_run:
        typer.echo("Dry run: no files written.")
        return
    if result.learned_changes and not yes:
        typer.confirm("Replace these learned mappings and relearn them?", abort=True)
    write_chords(State.config.gen, result.chords)
    if result.progress is not None and result.progress != progress:
        save_progress(result.progress)


@app.command()
def analyze(
    text: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True, help="Local TXT, Markdown, or EPUB text."),
    limit: int = typer.Option(20, "--limit", min=1, help="Maximum entries in each recommendation list."),
    baseline_wpm: float | None = typer.Option(None, "--baseline-wpm", help="Ordinary typing WPM for estimated recall-cost comparisons."),
):
    """Report personal-text coverage and useful next forms without writing files."""
    from chordgen.analysis import analyze_text, format_analysis
    from chordgen.book import load_book

    kind, layout = resolve_keyboard_layout(State.config) or ("standard", None)
    try:
        report = analyze_text(
            load_book(text), load_file(State.config.gen.file), load_progress(),
            keyboard_kind=kind, keyboard_layout=layout,
            limit=limit, baseline_wpm=baseline_wpm,
        )
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(format_analysis(report))


@app.command()
def check(
    limit: int = typer.Option(10, "--limit", min=1, help="Maximum examples per diagnostic group."),
):
    """Check dictionary, layout, exports, and progress without changing files."""
    from chordgen.check import format_check, run_check

    report = run_check(State.config_path)
    typer.echo(format_check(report, limit))
    if report.has_errors:
        raise typer.Exit(code=1)


@app.command()
def difficult(
    limit: int = typer.Option(10, "--limit", min=1, help="Maximum forms per difficulty list."),
):
    """Show lapses and longest unassisted recalls without changing files."""
    from chordgen.analysis import analyze_difficulty, format_difficulty
    from chordgen.check import read_inputs

    config, rows, progress, diagnostics = read_inputs(State.config_path)
    for finding in diagnostics.findings:
        typer.echo(f"[{finding.code}] {finding.message}")
        for example in finding.examples[:limit]:
            typer.echo(f"  {example}")
        if len(finding.examples) > limit:
            typer.echo(f"  ... {len(finding.examples) - limit} more")
    if diagnostics.has_errors:
        typer.echo("Difficulty analysis unavailable: invalid inputs. No files changed.")
        raise typer.Exit(code=1)
    resolved = resolve_keyboard_layout(config)
    if resolved is None:
        typer.echo("Identity comparison unavailable: keyboard layout could not be resolved. No files changed.")
        raise typer.Exit(code=1)
    kind, layout = resolved
    try:
        report = analyze_difficulty(
            rows, progress, keyboard_kind=kind, keyboard_layout=layout,
            leech_threshold=config.learn.leech_threshold,
        )
    except ValueError as exc:
        typer.echo(f"{exc} No files changed.")
        raise typer.Exit(code=1) from exc
    typer.echo(format_difficulty(report, limit))
    if report.invalid:
        raise typer.Exit(code=1)


@app.command()
def output():
    """Emit firmware and training files from chords.csv.

    Writes one file per enabled output format (qmk, zmk, kanata,
    charachorder, training). Configure which formats are active and
    their file paths under output.formats in config.yaml.
    """
    chords = load_file(State.config.gen.file)
    validate_chords(chords)

    for format in State.config.output.formats:
        print(f"Running output format '{format}'")
        format = getattr(State.config.output, format)
        format.output(chords)


@app.command()
def schema():
    """Regenerate docs/schema.md from the Pydantic config model."""
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
def learn(
    recall: bool = typer.Option(False, "--recall", help="Hide upcoming words and measure unassisted prompt-to-completion recall."),
):
    """Learn chords with spaced repetition.

    An interactive TUI that presents words one at a time. New words
    show their chord until you've typed them correctly a few times;
    once learned the chord is hidden and only revealed on a mistake.

    Backed by FSRS — each word is scheduled for review based on your
    performance, with daily quotas for new words and reviews and per-word
    speed grading. Use 'chordgen difficult' to inspect lapses and leeches.

    Press Ctrl+P to switch themes.
    """
    chords = load_file(State.config.gen.file)
    resolved = resolve_keyboard_layout(State.config)
    keyboard_kind, keyboard_layout = resolved if resolved else ("standard", None)
    app = LearnApp(
        chords,
        State.config.learn,
        recall=recall,
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
            "Optional words to drill on instead of the default "
            "graduated FSRS pool. Drill uses every word in the list "
            "that has a chord in chords.csv (regardless of FSRS "
            "state); graduated words are highlighted, the rest are "
            "shown dim."
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
    drill uses every word from that list that has a chord assigned
    (regardless of FSRS state); graduated words are highlighted in
    yellow, the rest are shown dim.
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


@app.command()
def add(
    words: list[str] = typer.Argument(
        None,
        help=(
            "Words to add to chords.csv. For each word the command "
            "interactively shows collision-free chord options, "
            "auto-detects the category, and appends the row with "
            "the chosen chord pinned (frequency left empty so future "
            "`chordgen gen` runs leave it alone). Alts are "
            "generated automatically from the category."
        ),
    ),
    words_file: Path = typer.Option(
        None,
        "--words-file",
        "-f",
        help=(
            "Path to a file containing words to add (whitespace-"
            "separated). Combined with any positional WORDS arguments."
        ),
    ),
):
    """Interactively add words to chords.csv.

    For each input word: skips it if it already exists (as a
    ``word`` row or any non-empty alt slot), shows the top
    collision-free chord options, auto-detects the category (with
    an override menu), validates a custom-typed chord through the
    same scorer the assigner uses, generates alts, and appends the
    row with the chord pinned (``frequency`` empty) so future
    ``chordgen gen`` runs leave it alone. The CSV is rewritten
    atomically after every accepted word.
    """
    collected: list[str] = list(words) if words else []
    if words_file is not None:
        if not words_file.exists():
            print(f"Error: words file {words_file} does not exist")
            raise typer.Abort()
        collected.extend(words_file.read_text().split())
    if not collected:
        print("Error: provide at least one word (positional or via --words-file)")
        raise typer.Abort()

    add_words(collected, State.config.gen)


if __name__ == "__main__":
    app()
