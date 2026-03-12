import logging
import re
from chordgen.chord import load_file, validate_chords
import typer
from pathlib import Path
import jsonschema2md

from chordgen.config import DEFAULT_CONFIG, Config, load_or_create_config
from chordgen.gen import gen as run_gen


app = typer.Typer()


class State:
    config: Config


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


@app.command()
def setup():
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

    with open("schema.md", "w") as f:
        f.write(md)


if __name__ == "__main__":
    app()
